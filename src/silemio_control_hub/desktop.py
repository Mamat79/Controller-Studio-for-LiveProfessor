"""Bilingual Windows desktop shell for the independent SiLeMI/O product."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import hashlib
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .application_update import (
    NoCompatibleRelease,
    download_update,
    fetch_latest_release,
    is_newer_version,
    launch_installer,
)
from .adapters.devices.ec4_protocol import (
    main_display_message,
    parameter_grid_message,
    total_display_message,
)
from .adapters.hosts import export_liveprofessor_controller
from .adapters.hosts.liveprofessor_automap import (
    ProjectInventory,
    inspect_plugin_parameter_slots,
    inspect_project,
)
from .adapters.hosts.liveprofessor_controller import (
    bank_rotary_count,
    default_companion_template,
    logical_rotary_count,
)
from .desktop_settings import (
    DesktopSettings,
    default_desktop_settings_path,
    load_desktop_settings,
    save_desktop_settings,
)
from .controller_contribution import (
    controller_submission_url,
    validated_controller_payload,
)
from .controller_editor import ControllerEditorDialog
from .controller_studio import (
    default_controller_payload,
    editable_controller_payload,
    save_user_controller_profile,
)
from .controller_shortcuts import (
    SHORTCUT_ACTIONS,
    configurable_shortcut_bindings,
    default_shortcuts,
    effective_shortcuts,
    shortcut_binding_key,
)
from .identity import BRAND_NAME, FULL_PRODUCT_NAME, PRODUCT_NAME
from .help_resources import (
    PAYPAL_QR_PATH,
    PAYPAL_SUPPORT_URL,
    manual_path,
    open_local_document,
    open_paypal_support,
)
from .library_remote import GitHubLibraryClient, update_library
from .liveprofessor_session import detect_liveprofessor_session
from .plugin_profiles import (
    PluginParameterKind,
    PluginParameterProfile,
    PluginProfileError,
    PluginProfileLayer,
)
from .plugin_registry import PluginProfileRegistry, default_user_plugin_profile_dir
from .plugin_studio import (
    PluginProjectAnalysis,
    PluginTypeSummary,
    analyze_plugin_project,
    build_user_profile,
    capture_liveprofessor_parameter_names,
    compatible_user_profile,
    editable_parameters,
    merge_scanned_parameter_names,
    next_user_profile_version,
    request_liveprofessor_companion_names,
    retrieve_installed_parameter_names,
    save_user_profile,
)
from .registry import ControllerRegistry, default_user_profile_dir
from .runtime import (
    BridgeConfig,
    BridgeSnapshot,
    EC4LiveProfessorRuntime,
    configure_runtime_logging,
    default_log_path,
    load_config,
    save_config,
)
from .runtime.config import default_config_path, legacy_config_path
from .transports.midi import input_names, output_names
from .transports.osc import decode_message, encode_message
from .windows_tray import TrayCommand, WindowsTray
from .windows_startup import set_start_with_windows, starts_with_windows
from .workflow import prepare_liveprofessor_project


PRODUCT_ICON_PATH = Path(__file__).resolve().parent / "assets" / "controller-studio.ico"
PRODUCT_LOGO_PATH = Path(__file__).resolve().parent / "assets" / "controller-studio.png"
PRODUCT_SIDEBAR_LOGO_PATH = (
    Path(__file__).resolve().parent / "assets" / "controller-studio-sidebar.png"
)
DISPLAY_VERSION = f"V.{__version__}"
AUTO_START_RETRY_DELAYS_MS = (1200, 3000, 6000, 12000, 20000)


UI_TEXT = {
    "fr": {
        "window_title": "Controller Studio for LiveProfessor {version}",
        "loading": "Chargement du catalogue local…",
        "brand_context": "for LiveProfessor  •  {version}",
        "intro": (
            "Choisir un contrôleur, créer son fichier LiveProfessor et préparer "
            "une copie AutoMap sans modifier le projet source."
        ),
        "tab_live": "Live",
        "tab_controllers": "Banque de contrôleurs",
        "tab_plugins": "Plug-ins",
        "tab_library": "Bibliothèque",
        "nav_automap": "⚡  AutoMap",
        "sidebar_footer": "Journal · Aide · Réglages",
        "menu_file": "Fichier",
        "menu_options": "Options",
        "menu_tools": "Outils",
        "menu_library": "Bibliothèque",
        "menu_help": "Aide",
        "live_title": "Contrôle en direct / LiveProfessor",
        "live_description": (
            "Choisissez le contrôleur actif. La page n’affiche que les commandes "
            "utiles à son pilote temps réel."
        ),
        "active_controller": "Contrôleur actif",
        "automation_options": "Automatisation",
        "quick_access": "Accès rapides",
        "advanced_controller": "Réglages avancés du contrôleur",
        "advanced_controller_open": "▼  Réglages avancés du contrôleur",
        "advanced_controller_closed": "▶  Réglages avancés du contrôleur",
        "controllers_title": "Banque de contrôleurs",
        "controllers_description": (
            "Choisissez un profil existant, fabriquez votre contrôleur ou exportez "
            "son fichier LiveProfessor."
        ),
        "driver_ready": "PILOTE TEMPS RÉEL PRÊT",
        "driver_profile_only": "PROFIL AUTOMAP / EXPORT",
        "driver_profile_only_body": (
            "Ce profil est prêt pour l’export .ctrl2 et AutoMap. La page Live affiche "
            "son parcours compatible."
        ),
        "live_settings": "Réglages",
        "live_settings_title": "Réglages Live / MIDI / OSC",
        "live_settings_intro": (
            "Connexions du moteur temps réel. Les outils propres au pilote actif "
            "apparaissent uniquement lorsqu’ils sont disponibles."
        ),
        "responsiveness_settings": "Réactivité, feedback et Overlay (ms)",
        "responsiveness_intro": (
            "Réglages communs aux contrôleurs compatibles. Les valeurs d’origine "
            "conviennent dans la majorité des cas."
        ),
        "persistent_parameter_display": "Conserver les paramètres visibles après l’Overlay",
        "parameter_overlay_interval": "Mise à jour de l’Overlay (1–2000)",
        "companion_refresh_delay": "Rafraîchissement Companion après commande (1–2000)",
        "name_refresh_delay": "Rafraîchissement des noms / labels (1–2000)",
        "feedback_confirm_timeout": "Délai maximal du retour LiveProfessor (100–10000)",
        "overlay_display_duration": "Durée d’affichage de l’Overlay (200–5000)",
        "ec4_zone": "Fonctions spécifiques EC4 (setup / groupe)",
        "configure_active_controller": "Configurer / apprentissage MIDI…",
        "ec4_tools": "Outils EC4",
        "state_frame": "État",
        "last_event": "Dernier événement",
        "log_window": "Journal temps réel",
        "copy_all": "Tout copier",
        "clear_display": "Effacer l’affichage",
        "open_log_file": "Ouvrir le fichier",
        "open_log_folder": "Ouvrir le dossier",
        "save": "Enregistrer",
        "close": "Fermer",
        "midi_input": "Entrée MIDI",
        "midi_output": "Sortie MIDI",
        "liveprofessor_host": "Adresse LiveProfessor",
        "osc_output_port": "Port OSC",
        "osc_feedback_port": "Port de retour",
        "target_setup": "Setup EC4",
        "target_group": "Groupe EC4",
        "use_current_target": "Utiliser le setup / groupe actuel",
        "display_enabled": "Activer l’affichage EC4",
        "start": "Démarrer",
        "stop": "Arrêter",
        "restart": "Redémarrer",
        "refresh_midi": "Actualiser les ports MIDI",
        "reconnect_ec4": "Reconnecter l’EC4",
        "request_setup": "Lire setup / groupe",
        "refresh_companion": "Rafraîchir Companion",
        "test_display": "Tester l’affichage EC4",
        "learn_button": "Apprendre les 16 rotatifs + push",
        "learn_cancel": "Annuler l’apprentissage",
        "learning_progress": "Tournez le rotatif 1 (0/16)",
        "learn_rotary_prompt": "Tournez le rotatif {index}",
        "learn_push_prompt": "Appuyez sur le push {index}",
        "learn_default_label": "Mapping Ableton par défaut",
        "learn_saved_label": "Mapping appris et enregistré",
        "learn_progress_title": "Apprentissage MIDI",
        "learn_progress_message": (
            "Phase 1 : tournez légèrement les rotatifs 1 à 16 dans l’ordre. "
            "Phase 2 : appuyez ensuite sur leurs 16 push dans le même ordre."
        ),
        "learn_phase2_title": "Rotatifs terminés",
        "learn_phase2_message": (
            "Appuyez maintenant une fois sur les push 1 à 16, dans l’ordre."
        ),
        "learn_complete_title": "Apprentissage terminé",
        "learn_complete_message": "Les 16 rotatifs et leurs push sont enregistrés.",
        "unknown_state_title": "État EC4 inconnu",
        "unknown_state_message": (
            "Lisez d’abord le setup/groupe de l’EC4, puis recommencez."
        ),
        "wrong_zone_title": "Mauvaise zone EC4",
        "wrong_zone_message": (
            "Sélectionnez d’abord le setup {setup}, groupe {group} sur l’EC4."
        ),
        "diagnostic": "Diagnostic",
        "diagnostic_title": "Diagnostic Controller Studio",
        "shortcuts": "Raccourcis",
        "shortcuts_title": "Raccourcis — {controller}",
        "shortcuts_intro": (
            "Choisissez l’action de chaque bouton ou push. La configuration est "
            "enregistrée séparément pour ce contrôleur."
        ),
        "shortcuts_driver_note": (
            "Ce profil n’a pas encore de pilote Live direct : les choix sont conservés "
            "et seront utilisés dès qu’un pilote compatible est disponible."
        ),
        "shortcuts_no_controls": "Ce profil ne déclare aucun bouton ou push configurable.",
        "shortcut_control": "Contrôle",
        "shortcut_direct": "Appui direct",
        "shortcut_none": "— Aucune action —",
        "shortcut_save": "Enregistrer",
        "shortcut_reset": "Réglages d’origine",
        "shortcut_saved": "Raccourcis enregistrés pour {controller}.",
        "previous_bank": "Banque précédente",
        "next_bank": "Banque suivante",
        "import_legacy_config": "Importer la configuration EC4 Bridge…",
        "runtime_log": "Journal temps réel",
        "runtime_not_started": "Prêt — moteur arrêté",
        "runtime_running": "Moteur démarré.",
        "runtime_stopped": "Moteur arrêté.",
        "runtime_starting": "Démarrage du moteur temps réel…",
        "runtime_driver_unavailable": (
            "{controller} est prêt pour Export et AutoMap. Le moteur Live direct "
            "s’active pour les profils disposant d’un pilote."
        ),
        "runtime_error": "Erreur du moteur temps réel",
        "runtime_config_file_type": "Configuration JSON EC4 Bridge",
        "runtime_config_imported": "Configuration importée sans modifier EC4 Bridge : {path}",
        "runtime_config_import_error": "Import de configuration impossible",
        "runtime_snapshot": (
            "{state}  •  EC4 {midi}  •  Banque {bank}/{banks}  •  "
            "Setup {setup} / Groupe {group}"
        ),
        "midi_connected": "connecté",
        "midi_disconnected": "déconnecté",
        "setup_unknown": "?",
        "tray_start": "Démarrer le moteur",
        "tray_stop": "Arrêter le moteur",
        "tray_restart": "Redémarrer le moteur",
        "tray_log": "Afficher le journal",
        "tray_update": "Vérifier la bibliothèque",
        "export_controller": "Exporter le contrôleur .ctrl2…",
        "prepare_automap": "⚡ AutoMap — choisir les plug-ins…",
        "automap_title": "AutoMap LiveProfessor",
        "automap_intro": (
            "Analysez un projet, choisissez le contrôleur, le mode de banques et les "
            "plug-ins à mapper. Le projet source reste toujours inchangé."
        ),
        "automap_project": "Projet LiveProfessor source (.rack2)",
        "automap_current_project": "Projet actuellement ouvert dans LiveProfessor",
        "automap_choose_project": "Choisir un fichier .rack2",
        "automap_detect": "Détecter",
        "automap_detected": "Projet détecté : {path}",
        "automap_not_running": "LiveProfessor n’est pas ouvert.",
        "automap_not_detected": (
            "LiveProfessor est ouvert, mais aucun projet enregistré n’a été détecté."
        ),
        "automap_save_current_title": "Sauvegarder le projet dans LiveProfessor",
        "automap_save_current_body": (
            "Projet détecté :\n{path}\n\nDans LiveProfessor, enregistrez maintenant le "
            "projet (Ctrl+S). Revenez ensuite ici et cliquez sur Continuer.\n\n"
            "Controller Studio lira ce fichier et créera une copie : le projet source "
            "ne sera jamais modifié."
        ),
        "automap_browse": "Parcourir…",
        "automap_analyze": "Analyser",
        "automap_controller_profile": "Profil du contrôleur physique",
        "automap_project_controller": "Contrôleur Companion/OSC dans le projet",
        "automap_existing_controller": "Réutiliser {name} — {rotaries} rotatifs [#{uid}]",
        "automap_new_controller": "Créer un nouveau contrôleur depuis le profil choisi",
        "automap_duplicate_title": "Deux contrôleurs Companion/OSC",
        "automap_duplicate_warning": (
            "Le projet contient déjà un contrôleur. En créer un second peut mélanger les "
            "labels /Companion/RotaryN. Réutiliser le contrôleur existant est recommandé.\n\n"
            "Créer tout de même un nouveau contrôleur ?"
        ),
        "automap_bank_mode": "Mode de banques dans la copie",
        "automap_unibank": "UniBank — {count} paramètres (recommandé)",
        "automap_fullbank": "FullBank — {count} paramètres",
        "automap_scope": "Plug-ins à auto-mapper",
        "automap_all_plugins": "Tous les plug-ins détectés",
        "automap_selected_plugins": "Sélection personnalisée (cases à cocher)",
        "automap_select_all": "Tout cocher",
        "automap_select_none": "Tout décocher",
        "automap_plugin_list": "Instances détectées",
        "automap_status_empty": "Choisissez un projet puis cliquez sur Analyser.",
        "automap_status_inventory": (
            "{plugins} instance(s) compatible(s), {controllers} contrôleur(s) existant(s)."
        ),
        "automap_status_skipped": " {count} plug-in(s) incompatible(s) ignoré(s).",
        "automap_no_plugin_title": "Aucun plug-in sélectionné",
        "automap_no_plugin_body": "Cochez au moins une instance de plug-in.",
        "automap_create": "Créer la copie AutoMap…",
        "automap_running": "Création et validation de la copie AutoMap…",
        "automap_complete_body": (
            "Projet source préservé (SHA-256 {sha256}).\n\n"
            "Copie : {project}\nContrôleur : {controller}\n"
            "{plugins} type(s) de plug-in, {mappings} affectation(s)."
        ),
        "automap_open_title": "Ouvrir dans LiveProfessor ?",
        "automap_open_question": (
            "La copie a été validée. LiveProfessor remplacera le projet actuellement ouvert. "
            "Enregistrez-le avant de continuer.\n\nOuvrir la copie maintenant ?"
        ),
        "automap_open_error": "La copie est créée, mais son ouverture a échoué : {error}",
        "minimize": "Réduire dans la zone de notification",
        "quit": "Quitter",
        "close_to_tray": "Réduire dans la zone de notification à la fermeture",
        "start_with_windows": "Lancer Controller Studio avec Windows",
        "auto_start_runtime": (
            "Démarrer automatiquement la connexion du contrôleur sélectionné"
        ),
        "startup_windows_enabled": (
            "Controller Studio démarrera avec Windows dans la zone de notification."
        ),
        "startup_windows_disabled": "Démarrage avec Windows désactivé.",
        "startup_registration_error": "Démarrage avec Windows impossible : {error}",
        "runtime_auto_start_attempt": "Connexion automatique à {controller}…",
        "runtime_auto_start_retry": (
            "Connexion automatique impossible ; nouvel essai dans {seconds} s."
        ),
        "language": "Langue",
        "french": "Français",
        "english": "English",
        "preview_updates": "Prévisualiser les mises à jour",
        "install_update": "Installer après confirmation",
        "open_manual": "Ouvrir la notice PDF…",
        "manual_error_title": "Notice indisponible",
        "manual_error_body": "La notice n'a pas pu être ouverte : {error}",
        "check_app_updates": "Rechercher les mises à jour…",
        "app_update_checking": "Recherche d'une mise à jour Controller Studio…",
        "app_update_none": (
            "Aucune version compatible de Controller Studio n'est publiée pour le moment."
        ),
        "app_update_current_title": "Controller Studio est à jour",
        "app_update_current": "La version {version} est la version la plus récente.",
        "app_update_available_title": "Mise à jour {version} disponible",
        "app_update_available": (
            "Version installée : {current}\nVersion disponible : {version}\n\n"
            "Télécharger, vérifier le SHA-256 puis lancer l'installateur ?\n\n{notes}"
        ),
        "app_update_downloading": "Téléchargement et vérification de la mise à jour…",
        "app_update_launched_title": "Installateur lancé",
        "app_update_launched": (
            "L'installateur vérifié a été lancé depuis :\n{path}\n\n"
            "Suivez ses instructions pour terminer la mise à jour."
        ),
        "app_update_error_title": "Mise à jour impossible",
        "support": "Soutenir Controller Studio…",
        "support_title": "Soutenir Controller Studio",
        "support_intro": (
            "Controller Studio est développé indépendamment pour faciliter le contrôle de "
            "LiveProfessor. Si le logiciel vous est utile, vous pouvez soutenir son développement."
        ),
        "support_optional": (
            "Le soutien est entièrement facultatif : le logiciel reste gratuit et toutes ses "
            "fonctions restent disponibles."
        ),
        "support_open_paypal": "Ouvrir PayPal.Me",
        "support_close": "Fermer",
        "support_error_title": "Lien de soutien indisponible",
        "support_error": "Le lien PayPal.Me n'a pas pu être ouvert : {error}",
        "about": "À propos",
        "maker": "Fabricant",
        "model": "Modèle",
        "status": "Statut",
        "version": "Version",
        "controls": "Contrôles",
        "layout": "Banques / pages",
        "refresh": "Actualiser",
        "controller_create": "Créer un contrôleur…",
        "controller_edit": "Modifier / dupliquer…",
        "controller_import": "Importer un profil…",
        "controller_import_title": "Importer un profil de contrôleur JSON",
        "all_files": "Tous les fichiers",
        "controller_imported_title": "Contrôleur importé",
        "controller_imported_body": "{controller} est maintenant disponible dans votre banque.\n\n{path}",
        "contribute_controller": "Proposer à la bibliothèque…",
        "contribute_controller_title": "Proposer ce contrôleur",
        "contribute_controller_ready": (
            "Le profil validé de {controller} a été placé automatiquement dans le formulaire.\n\n"
            "GitHub va s’ouvrir uniquement pour identifier l’auteur, ajouter si possible la "
            "documentation ou les tests matériels, puis confirmer l’envoi."
        ),
        "contribute_controller_ready_clipboard": (
            "Le profil de {controller} est trop grand pour être placé dans le lien. Il a été "
            "copié dans le presse-papiers : collez-le dans la zone « Profil JSON » puis confirmez."
        ),
        "contribute_controller_error": "Contribution impossible",
        "controller_editor_title": "Fabriquer un contrôleur",
        "controller_editor_intro": (
            "Décrivez le contrôleur, ajoutez ses commandes ou apprenez-les directement en MIDI. "
            "Le profil est validé avant d’entrer dans votre banque et peut créer immédiatement "
            "le fichier .ctrl2 pour LiveProfessor."
        ),
        "controller_identity": "Identité et organisation",
        "controller_profile_id": "Identifiant",
        "controller_input_pattern": "Nom(s) entrée MIDI",
        "controller_output_pattern": "Nom(s) sortie MIDI",
        "controller_firmware": "Firmware (facultatif)",
        "controller_bank_size": "Contrôles / banque",
        "controller_bank_count": "Banques",
        "controller_page_count": "Pages",
        "controller_generate_id": "Générer l’identifiant",
        "controller_selected_control": "Commande sélectionnée",
        "controller_control_id": "Nom technique",
        "controller_control_kind": "Type",
        "controller_message": "Message",
        "controller_channel": "Canal",
        "controller_number": "N° MIDI",
        "controller_push": "Appui",
        "controller_kind_absolute": "Encodeur absolu",
        "controller_kind_relative": "Encodeur relatif",
        "controller_kind_fader": "Fader",
        "controller_kind_button": "Bouton",
        "controller_kind_pad": "Pad",
        "controller_message_note": "Note",
        "controller_message_pitch": "Pitch Bend",
        "controller_relative_mode": "Mode relatif",
        "controller_input_message": "Mouvement / entrée",
        "controller_push_enable": "Appui d’encodeur",
        "controller_midi_port": "Entrée MIDI à écouter",
        "controller_learn_input": "Apprendre le mouvement",
        "controller_learn_push": "Apprendre l’appui",
        "controller_learn_idle": "Sélectionnez une ligne puis lancez l’apprentissage MIDI.",
        "controller_learn_wait": "En écoute : actionnez {target} sur le contrôleur…",
        "controller_learn_target_input": "la commande",
        "controller_learn_target_push": "son appui",
        "controller_learn_received": "Reçu : {binding}",
        "controller_add_encoder": "+ Encodeur",
        "controller_add_relative": "+ Encodeur relatif",
        "controller_add_fader": "+ Fader",
        "controller_add_button": "+ Bouton",
        "controller_delete_control": "Supprimer",
        "controller_apply_control": "Appliquer à la ligne",
        "controller_close": "Fermer",
        "controller_submit": "Proposer à la bibliothèque",
        "controller_save_export": "Enregistrer + créer .ctrl2",
        "controller_save_local": "Enregistrer dans ma banque",
        "controller_invalid_title": "Profil de contrôleur invalide",
        "controller_need_one_control": "Un profil doit conserver au moins une commande.",
        "controller_select_control": "Sélectionnez d’abord une commande dans la liste.",
        "controller_midi_error": "Apprentissage MIDI impossible",
        "controller_fix_selected": "Corrigez la commande sélectionnée.",
        "controller_replace_title": "Remplacer ce profil personnel ?",
        "controller_replace_body": (
            "{name} existe déjà dans votre banque. Le remplacer ? Une sauvegarde sera conservée."
        ),
        "controller_backup": "Sauvegarde précédente : {path}",
        "controller_saved_title": "Contrôleur enregistré",
        "controller_saved_body": "{name} est disponible dans votre banque.\n\n{path}",
        "plugin_studio_title": "Plugin Studio",
        "plugin_studio_badge": "LOCAL • SÛR",
        "plugin_intro": (
            "Analysez un projet .rack2, regroupez ses instances par type et créez un "
            "profil local. AutoMap utilise ensuite vos priorités sans remplacer les "
            "affectations manuelles."
        ),
        "plugin": "Plug-in",
        "layer": "Couche",
        "parameters": "Paramètres",
        "plugin_project": "Projet LiveProfessor (.rack2)",
        "plugin_browse": "Parcourir…",
        "plugin_analyze": "Analyser les plug-ins",
        "plugin_format": "Format",
        "plugin_instances": "Instances",
        "plugin_recognition": "Reconnaissance",
        "plugin_profile": "Profil appliqué",
        "plugin_profile_raw": "Ordre brut LiveProfessor",
        "plugin_status_empty": "Choisissez un projet pour reconnaître ses plug-ins.",
        "plugin_status_running": "Analyse du projet et résolution des profils…",
        "plugin_catalog_status": "{profiles} profil(s) disponible(s). Analysez un projet pour les appliquer.",
        "plugin_status_analysis": "{types} type(s) reconnu(s), {instances} instance(s).",
        "plugin_analysis_ready": "Analyse terminée : {types} type(s), {instances} instance(s).",
        "plugin_analysis_error": "Analyse des plug-ins impossible",
        "plugin_scan_all": "Récupérer tous les vrais noms",
        "plugin_scan_all_title": "Récupérer tous les noms de paramètres",
        "plugin_scan_all_confirm": (
            "Controller Studio va lire les paramètres exposés par les {types} types de "
            "plug-ins installés, chacun dans un processus isolé. Seuls les inventaires "
            "dont le nombre correspond exactement au projet seront enregistrés. Les "
            "profils locaux existants seront sauvegardés avant mise à jour.\n\n"
            "Le projet .rack2 ne sera jamais modifié. Continuer ?"
        ),
        "plugin_scan_all_running": "Lecture des plug-ins installés…",
        "plugin_scan_all_progress": "Lecture {current}/{total} : {name}",
        "plugin_scan_all_success": (
            "{saved} profil(s) mis à jour avec les vrais noms.\n"
            "{skipped} plug-in(s) ignoré(s).{details}"
        ),
        "plugin_scan_all_details": (
            "\n\nDétails :\n{details}\n\nOuvrez le profil d'un plug-in ignoré pour "
            "utiliser automatiquement le secours LiveProfessor."
        ),
        "plugin_scan_all_none": "Aucun profil n'a pu être mis à jour.{details}",
        "plugin_edit": "Créer / modifier le profil…",
        "plugin_use_automap": "Utiliser dans AutoMap",
        "plugin_open_folder": "Dossier des profils",
        "plugin_folder_error": "Ouverture du dossier impossible",
        "plugin_select_required": "Plug-in requis",
        "plugin_select_required_body": "Sélectionnez d’abord un type de plug-in analysé.",
        "plugin_layer_raw": "Brut",
        "plugin_layer_suggested": "Suggéré",
        "plugin_layer_user": "Utilisateur",
        "plugin_kind_continuous": "Continu",
        "plugin_kind_toggle": "Interrupteur",
        "plugin_kind_enum": "Liste",
        "plugin_kind_meter": "Mesure",
        "plugin_editor_title": "Profil de plug-in — {name}",
        "plugin_editor_intro": (
            "Lisez automatiquement les vrais noms dans le plug-in installé, puis choisissez "
            "précisément les paramètres à inclure dans AutoMap."
        ),
        "plugin_editor_instances": "{instances} instance(s) • {parameters} paramètre(s)",
        "plugin_parameter_enabled": "AutoMap",
        "plugin_parameter_enabled_editor": "Inclure ce paramètre dans AutoMap",
        "plugin_select_all": "Tout cocher",
        "plugin_select_none": "Tout décocher",
        "plugin_enabled_count": "{enabled}/{total} paramètre(s) inclus",
        "plugin_capture_names": "Récupérer automatiquement les vrais noms",
        "plugin_capture_names_title": "Récupérer les vrais noms",
        "plugin_scan_direct_busy": "Lecture du plug-in installé…",
        "plugin_scan_direct_success": (
            "{count} vrai(s) nom(s) lu(s) directement dans le plug-in installé. "
            "Vérifiez-les avant d'enregistrer."
        ),
        "plugin_scan_fallback": (
            "La lecture directe de « {name} » n'a pas abouti :\n{error}\n\n"
            "Voulez-vous essayer l'interception du retour LiveProfessor ?"
        ),
        "plugin_capture_names_ready": (
            "Dans LiveProfessor, sélectionnez une instance de « {name} ». Dans la barre "
            "du haut, cliquez sur le nom de la map et choisissez exactement "
            "« SiLeMI/O AutoMap - {name} » — pas la map Dynamic. Si les libellés sont "
            "visibles sur votre contrôleur, cliquez sur OK. Sinon, changez brièvement de "
            "plug-in puis revenez sur « {name} » : Controller Studio intercepte les noms "
            "envoyés au contrôleur sans modifier le projet."
        ),
        "plugin_capture_busy": "Interception des noms en cours…",
        "plugin_capture_error": "Récupération impossible : {error}",
        "plugin_capture_missing": (
            "Aucun vrai nom n’a été reçu. Vérifiez que la bonne instance est sélectionnée "
            "et que « SiLeMI/O AutoMap - {name} » est la map active dans LiveProfessor "
            "(la map Dynamic ne convient pas), changez de plug-in puis revenez sur cette "
            "instance avant de réessayer."
        ),
        "plugin_capture_no_map": (
            "Le projet analysé ne contient pas encore de Controller Map exploitable pour "
            "ce plug-in. Créez ou ouvrez d’abord sa copie AutoMap."
        ),
        "plugin_capture_success": "{count} vrai(s) nom(s) récupéré(s). Vérifiez-les avant d’enregistrer.",
        "plugin_parameter_number": "N°",
        "plugin_parameter_name": "Nom",
        "plugin_short_label": "Libellé court",
        "plugin_parameter_kind": "Type",
        "plugin_parameter_role": "Rôle technique",
        "plugin_parameter_unit": "Unité",
        "plugin_parameter_importance": "Priorité",
        "plugin_parameter_editor": "Modifier le paramètre sélectionné",
        "plugin_parameter_apply": "Appliquer à la ligne",
        "plugin_parameter_reset": "Rétablir la ligne",
        "plugin_importance_help": "100 = placé avant 0 dans les emplacements AutoMap libres",
        "plugin_save_profile": "Enregistrer le profil local",
        "plugin_close": "Fermer",
        "plugin_profile_invalid": "Profil de plug-in invalide",
        "plugin_replace_title": "Mettre à jour le profil local ?",
        "plugin_replace_body": (
            "{name} existe déjà. Enregistrer une nouvelle version et sauvegarder "
            "la précédente ?"
        ),
        "plugin_profile_saved": "Profil local enregistré",
        "plugin_profile_saved_body": "Version {version}\n{path}\n{backup}",
        "plugin_backup_created": "Sauvegarde précédente : {path}",
        "plugin_profile_saved_status": "Profil de plug-in enregistré : {name}",
        "library_title": "Bibliothèque publique versionnée",
        "library_description": (
            "Controller Studio fonctionne hors ligne. L’aperçu ne modifie rien ; "
            "l’installation vérifie versions, schémas et SHA-256 avant un "
            "remplacement atomique."
        ),
        "library_token_note": (
            "Aucun jeton n’est requis pour la bibliothèque publique. GH_TOKEN ou "
            "GITHUB_TOKEN reste facultatif pour augmenter la limite GitHub ou utiliser un fork privé."
        ),
        "catalog_ready": (
            "Catalogue prêt : {controllers} contrôleur(s), {plugins} profil(s) de plug-in."
        ),
        "catalog_invalid": "Catalogue invalide",
        "catalog_invalid_status": "Catalogue invalide : {error}",
        "controller_required": "Contrôleur requis",
        "select_controller": "Sélectionnez d’abord un contrôleur.",
        "export_title": "Exporter le contrôleur LiveProfessor",
        "controller_file_type": "Contrôleur LiveProfessor",
        "replace_file": "Remplacer le fichier ?",
        "replace_file_body": "{name} existe déjà. Le remplacer ?",
        "export_error": "Export impossible",
        "controller_created": "Contrôleur créé",
        "controller_created_status": "Contrôleur créé : {name}",
        "export_details": (
            "{path}\n\n{rotaries} rotatifs, {buttons} boutons\nSHA-256 {sha256}"
        ),
        "source_title": "Choisir le projet LiveProfessor source (lecture seule)",
        "project_file_type": "Projet LiveProfessor",
        "destination_title": "Créer la copie AutoMap",
        "destination_forbidden": "Destination interdite",
        "destination_forbidden_body": (
            "La copie AutoMap doit être différente du projet source."
        ),
        "replace_copy": "Remplacer la copie ?",
        "replace_copy_body": "{name} existe déjà. La remplacer ?",
        "replace_controller": "Remplacer le contrôleur ?",
        "replace_controller_body": "{name} existe déjà. Le remplacer ?",
        "preparation_error": "Préparation impossible",
        "automap_created_status": "Copie AutoMap créée : {name}",
        "preparation_complete": "Préparation terminée",
        "preparation_details": (
            "Projet source préservé (SHA-256 {sha256}).\n\n"
            "Copie : {project}\nContrôleur : {controller}"
        ),
        "install_confirm": "Installer la mise à jour ?",
        "install_confirm_body": (
            "Le cache courant sera sauvegardé avant l’installation atomique."
        ),
        "installing_library": "Installation de la bibliothèque…",
        "reading_manifest": "Lecture du manifeste distant…",
        "library_current": "La bibliothèque est déjà à jour.",
        "library_installed": "Bibliothèque installée",
        "preview": "Aperçu",
        "update_error": "Mise à jour impossible",
        "library_unchanged": "Bibliothèque inchangée : {error}",
        "change_new": "NOUVEAU",
        "change_update": "MISE À JOUR",
        "change_downgrade": "RETOUR DE VERSION",
        "change_removed": "SUPPRIMÉ",
        "collection_controller": "contrôleur",
        "collection_plugin": "plug-in",
        "about_title": "À propos de Controller Studio",
        "about_body": (
            "Controller Studio for LiveProfessor {version}\n"
            "SiLeMI/O — By Mamat  -------[]--\n\n"
            "Produit indépendant qui reprend les comportements éprouvés d’EC4 Bridge.\n"
            "Interface française/anglaise, banque de contrôleurs, Plugin Studio et AutoMap."
        ),
        "tray_open": "Ouvrir Controller Studio",
        "tray_quit": "Quitter",
        "tray_hidden": "Controller Studio est réduit dans la zone de notification.",
        "settings_saved": "Préférences enregistrées.",
        "settings_error": "Impossible d’enregistrer les préférences : {error}",
        "status_builtin": "intégré",
        "status_verified": "vérifié",
        "status_community": "communautaire",
        "status_local": "local",
    },
    "en": {
        "window_title": "Controller Studio for LiveProfessor {version}",
        "loading": "Loading the local catalog…",
        "brand_context": "for LiveProfessor  •  {version}",
        "intro": (
            "Choose a controller, create its LiveProfessor file, and prepare an "
            "AutoMap copy without changing the source project."
        ),
        "tab_live": "Live",
        "tab_controllers": "Controller bank",
        "tab_plugins": "Plug-ins",
        "tab_library": "Library",
        "nav_automap": "⚡  AutoMap",
        "sidebar_footer": "Log · Help · Settings",
        "menu_file": "File",
        "menu_options": "Options",
        "menu_tools": "Tools",
        "menu_library": "Library",
        "menu_help": "Help",
        "live_title": "Live control / LiveProfessor",
        "live_description": (
            "Choose the active controller. This page only shows the controls useful "
            "to its real-time driver."
        ),
        "active_controller": "Active controller",
        "automation_options": "Automation",
        "quick_access": "Quick access",
        "advanced_controller": "Advanced controller settings",
        "advanced_controller_open": "▼  Advanced controller settings",
        "advanced_controller_closed": "▶  Advanced controller settings",
        "controllers_title": "Controller bank",
        "controllers_description": (
            "Choose an existing profile, build your controller, or export its "
            "LiveProfessor file."
        ),
        "driver_ready": "REAL-TIME DRIVER READY",
        "driver_profile_only": "AUTOMAP / EXPORT PROFILE",
        "driver_profile_only_body": (
            "This profile is ready for .ctrl2 export and AutoMap. The Live page shows "
            "its compatible workflow."
        ),
        "live_settings": "Settings",
        "live_settings_title": "Live / MIDI / OSC settings",
        "live_settings_intro": (
            "Real-time engine connections. Driver-specific tools only appear when "
            "they are available."
        ),
        "responsiveness_settings": "Responsiveness, feedback and Overlay (ms)",
        "responsiveness_intro": (
            "Shared settings for compatible controllers. The defaults suit most setups."
        ),
        "persistent_parameter_display": "Keep parameters visible after the Overlay",
        "parameter_overlay_interval": "Overlay update interval (1–2000)",
        "companion_refresh_delay": "Companion refresh after a command (1–2000)",
        "name_refresh_delay": "Name / label refresh delay (1–2000)",
        "feedback_confirm_timeout": "LiveProfessor feedback timeout (100–10000)",
        "overlay_display_duration": "Overlay display duration (200–5000)",
        "ec4_zone": "EC4-specific functions (setup / group)",
        "configure_active_controller": "Configure / MIDI Learn…",
        "ec4_tools": "EC4 tools",
        "state_frame": "Status",
        "last_event": "Last event",
        "log_window": "Real-time log",
        "copy_all": "Copy all",
        "clear_display": "Clear display",
        "open_log_file": "Open file",
        "open_log_folder": "Open folder",
        "save": "Save",
        "close": "Close",
        "midi_input": "MIDI input",
        "midi_output": "MIDI output",
        "liveprofessor_host": "LiveProfessor address",
        "osc_output_port": "OSC port",
        "osc_feedback_port": "Feedback port",
        "target_setup": "EC4 setup",
        "target_group": "EC4 group",
        "use_current_target": "Use current setup / group",
        "display_enabled": "Enable EC4 display",
        "start": "Start",
        "stop": "Stop",
        "restart": "Restart",
        "refresh_midi": "Refresh MIDI ports",
        "reconnect_ec4": "Reconnect EC4",
        "request_setup": "Read setup / group",
        "refresh_companion": "Refresh Companion",
        "test_display": "Test EC4 display",
        "learn_button": "Learn 16 rotaries + pushes",
        "learn_cancel": "Cancel MIDI learn",
        "learning_progress": "Turn rotary 1 (0/16)",
        "learn_rotary_prompt": "Turn rotary {index}",
        "learn_push_prompt": "Press push {index}",
        "learn_default_label": "Default Ableton mapping",
        "learn_saved_label": "Learned mapping saved",
        "learn_progress_title": "MIDI learn",
        "learn_progress_message": (
            "Phase 1: turn rotaries 1 to 16 in order. "
            "Phase 2: then press their 16 pushes in the same order."
        ),
        "learn_phase2_title": "Rotaries complete",
        "learn_phase2_message": "Now press pushes 1 to 16 once, in order.",
        "learn_complete_title": "MIDI learn complete",
        "learn_complete_message": "The 16 rotaries and their pushes are saved.",
        "unknown_state_title": "Unknown EC4 state",
        "unknown_state_message": "Read the EC4 setup/group first, then try again.",
        "wrong_zone_title": "Wrong EC4 zone",
        "wrong_zone_message": "Select setup {setup}, group {group} on the EC4 first.",
        "diagnostic": "Diagnostics",
        "diagnostic_title": "Controller Studio diagnostics",
        "shortcuts": "Shortcuts",
        "shortcuts_title": "Shortcuts — {controller}",
        "shortcuts_intro": (
            "Choose the action for each button or push. Settings are stored separately "
            "for this controller."
        ),
        "shortcuts_driver_note": (
            "This profile does not have a native Live driver yet. These choices are "
            "saved and will be used when a compatible driver is available."
        ),
        "shortcuts_no_controls": "This profile does not declare any configurable button or push.",
        "shortcut_control": "Control",
        "shortcut_direct": "Direct press",
        "shortcut_none": "— No action —",
        "shortcut_save": "Save",
        "shortcut_reset": "Factory settings",
        "shortcut_saved": "Shortcuts saved for {controller}.",
        "previous_bank": "Previous bank",
        "next_bank": "Next bank",
        "import_legacy_config": "Import EC4 Bridge configuration…",
        "runtime_log": "Real-time log",
        "runtime_not_started": "Ready — engine stopped",
        "runtime_running": "Engine started.",
        "runtime_stopped": "Engine stopped.",
        "runtime_starting": "Starting the real-time engine…",
        "runtime_driver_unavailable": (
            "{controller} is ready for Export and AutoMap. The direct Live engine "
            "activates for profiles that provide a driver."
        ),
        "runtime_error": "Real-time engine error",
        "runtime_config_file_type": "EC4 Bridge JSON configuration",
        "runtime_config_imported": "Configuration imported without changing EC4 Bridge: {path}",
        "runtime_config_import_error": "Configuration import failed",
        "runtime_snapshot": (
            "{state}  •  EC4 {midi}  •  Bank {bank}/{banks}  •  "
            "Setup {setup} / Group {group}"
        ),
        "midi_connected": "connected",
        "midi_disconnected": "disconnected",
        "setup_unknown": "?",
        "tray_start": "Start engine",
        "tray_stop": "Stop engine",
        "tray_restart": "Restart engine",
        "tray_log": "Show log",
        "tray_update": "Check library",
        "export_controller": "Export controller .ctrl2…",
        "prepare_automap": "⚡ AutoMap — choose plug-ins…",
        "automap_title": "LiveProfessor AutoMap",
        "automap_intro": (
            "Analyze a project, choose the controller, bank mode, and plug-ins to map. "
            "The source project always remains unchanged."
        ),
        "automap_project": "Source LiveProfessor project (.rack2)",
        "automap_current_project": "Project currently open in LiveProfessor",
        "automap_choose_project": "Choose a .rack2 file",
        "automap_detect": "Detect",
        "automap_detected": "Detected project: {path}",
        "automap_not_running": "LiveProfessor is not running.",
        "automap_not_detected": (
            "LiveProfessor is running, but no saved project could be detected."
        ),
        "automap_save_current_title": "Save the project in LiveProfessor",
        "automap_save_current_body": (
            "Detected project:\n{path}\n\nSave the project now in LiveProfessor "
            "(Ctrl+S). Then return here and click Continue.\n\nController Studio will "
            "read this file and create a copy; the source project is never changed."
        ),
        "automap_browse": "Browse…",
        "automap_analyze": "Analyze",
        "automap_controller_profile": "Physical controller profile",
        "automap_project_controller": "Companion/OSC controller in the project",
        "automap_existing_controller": "Reuse {name} — {rotaries} rotaries [#{uid}]",
        "automap_new_controller": "Create a new controller from the selected profile",
        "automap_duplicate_title": "Two Companion/OSC controllers",
        "automap_duplicate_warning": (
            "The project already contains a controller. Creating a second one can mix the "
            "/Companion/RotaryN labels. Reusing the existing controller is recommended.\n\n"
            "Create a new controller anyway?"
        ),
        "automap_bank_mode": "Bank mode in the copy",
        "automap_unibank": "UniBank — {count} parameters (recommended)",
        "automap_fullbank": "FullBank — {count} parameters",
        "automap_scope": "Plug-ins to auto-map",
        "automap_all_plugins": "All detected plug-ins",
        "automap_selected_plugins": "Custom selection (checkboxes)",
        "automap_select_all": "Select all",
        "automap_select_none": "Select none",
        "automap_plugin_list": "Detected instances",
        "automap_status_empty": "Choose a project, then click Analyze.",
        "automap_status_inventory": (
            "{plugins} compatible instance(s), {controllers} existing controller(s)."
        ),
        "automap_status_skipped": " {count} incompatible plug-in(s) skipped.",
        "automap_no_plugin_title": "No plug-in selected",
        "automap_no_plugin_body": "Select at least one plug-in instance.",
        "automap_create": "Create AutoMap copy…",
        "automap_running": "Creating and validating the AutoMap copy…",
        "automap_complete_body": (
            "Source project preserved (SHA-256 {sha256}).\n\n"
            "Copy: {project}\nController: {controller}\n"
            "{plugins} plug-in type(s), {mappings} assignment(s)."
        ),
        "automap_open_title": "Open in LiveProfessor?",
        "automap_open_question": (
            "The copy has been validated. LiveProfessor will replace the currently open "
            "project. Save it before continuing.\n\nOpen the copy now?"
        ),
        "automap_open_error": "The copy was created, but could not be opened: {error}",
        "minimize": "Minimize to notification area",
        "quit": "Quit",
        "close_to_tray": "Minimize to notification area when closing",
        "start_with_windows": "Launch Controller Studio with Windows",
        "auto_start_runtime": "Connect the selected controller automatically on startup",
        "startup_windows_enabled": (
            "Controller Studio will start with Windows in the notification area."
        ),
        "startup_windows_disabled": "Windows startup disabled.",
        "startup_registration_error": "Could not configure Windows startup: {error}",
        "runtime_auto_start_attempt": "Connecting automatically to {controller}…",
        "runtime_auto_start_retry": (
            "Automatic connection failed; trying again in {seconds} s."
        ),
        "language": "Language",
        "french": "Français",
        "english": "English",
        "preview_updates": "Preview updates",
        "install_update": "Install after confirmation",
        "open_manual": "Open PDF manual…",
        "manual_error_title": "Manual unavailable",
        "manual_error_body": "The manual could not be opened: {error}",
        "check_app_updates": "Check for updates…",
        "app_update_checking": "Checking for a Controller Studio update…",
        "app_update_none": (
            "No compatible Controller Studio release is published at this time."
        ),
        "app_update_current_title": "Controller Studio is up to date",
        "app_update_current": "Version {version} is the latest version.",
        "app_update_available_title": "Update {version} available",
        "app_update_available": (
            "Installed version: {current}\nAvailable version: {version}\n\n"
            "Download, verify SHA-256, and launch the installer?\n\n{notes}"
        ),
        "app_update_downloading": "Downloading and verifying the update…",
        "app_update_launched_title": "Installer launched",
        "app_update_launched": (
            "The verified installer was launched from:\n{path}\n\n"
            "Follow its instructions to complete the update."
        ),
        "app_update_error_title": "Update failed",
        "support": "Support Controller Studio…",
        "support_title": "Support Controller Studio",
        "support_intro": (
            "Controller Studio is independently developed to make LiveProfessor control easier. "
            "If the software helps you, you can support its development."
        ),
        "support_optional": (
            "Support is entirely optional: the software remains free and every feature stays "
            "available."
        ),
        "support_open_paypal": "Open PayPal.Me",
        "support_close": "Close",
        "support_error_title": "Support link unavailable",
        "support_error": "The PayPal.Me link could not be opened: {error}",
        "about": "About",
        "maker": "Manufacturer",
        "model": "Model",
        "status": "Status",
        "version": "Version",
        "controls": "Controls",
        "layout": "Banks / pages",
        "refresh": "Refresh",
        "controller_create": "Create a controller…",
        "controller_edit": "Edit / duplicate…",
        "controller_import": "Import a profile…",
        "controller_import_title": "Import a JSON controller profile",
        "all_files": "All files",
        "controller_imported_title": "Controller imported",
        "controller_imported_body": "{controller} is now available in your bank.\n\n{path}",
        "contribute_controller": "Submit to the library…",
        "contribute_controller_title": "Submit this controller",
        "contribute_controller_ready": (
            "The validated {controller} profile was inserted into the form automatically.\n\n"
            "GitHub will open only to identify the author, add hardware documentation or test "
            "details when available, and confirm the submission."
        ),
        "contribute_controller_ready_clipboard": (
            "The {controller} profile is too large for a pre-filled link. It was copied to the "
            "clipboard: paste it into “JSON profile”, then confirm the submission."
        ),
        "contribute_controller_error": "Unable to prepare contribution",
        "controller_editor_title": "Build a controller",
        "controller_editor_intro": (
            "Describe the controller, add its controls, or learn them directly from MIDI. "
            "The profile is validated before entering your bank and can immediately create "
            "the LiveProfessor .ctrl2 file."
        ),
        "controller_identity": "Identity and layout",
        "controller_profile_id": "Identifier",
        "controller_input_pattern": "MIDI input name(s)",
        "controller_output_pattern": "MIDI output name(s)",
        "controller_firmware": "Firmware (optional)",
        "controller_bank_size": "Controls / bank",
        "controller_bank_count": "Banks",
        "controller_page_count": "Pages",
        "controller_generate_id": "Generate identifier",
        "controller_selected_control": "Selected control",
        "controller_control_id": "Technical name",
        "controller_control_kind": "Type",
        "controller_message": "Message",
        "controller_channel": "Channel",
        "controller_number": "MIDI no.",
        "controller_push": "Push",
        "controller_kind_absolute": "Absolute encoder",
        "controller_kind_relative": "Relative encoder",
        "controller_kind_fader": "Fader",
        "controller_kind_button": "Button",
        "controller_kind_pad": "Pad",
        "controller_message_note": "Note",
        "controller_message_pitch": "Pitch Bend",
        "controller_relative_mode": "Relative mode",
        "controller_input_message": "Movement / input",
        "controller_push_enable": "Encoder push",
        "controller_midi_port": "MIDI input to listen to",
        "controller_learn_input": "Learn movement",
        "controller_learn_push": "Learn push",
        "controller_learn_idle": "Select a row, then start MIDI Learn.",
        "controller_learn_wait": "Listening: operate {target} on the controller…",
        "controller_learn_target_input": "the control",
        "controller_learn_target_push": "its push",
        "controller_learn_received": "Received: {binding}",
        "controller_add_encoder": "+ Encoder",
        "controller_add_relative": "+ Relative encoder",
        "controller_add_fader": "+ Fader",
        "controller_add_button": "+ Button",
        "controller_delete_control": "Delete",
        "controller_apply_control": "Apply to row",
        "controller_close": "Close",
        "controller_submit": "Submit to the library",
        "controller_save_export": "Save + create .ctrl2",
        "controller_save_local": "Save to my bank",
        "controller_invalid_title": "Invalid controller profile",
        "controller_need_one_control": "A profile must keep at least one control.",
        "controller_select_control": "Select a control in the list first.",
        "controller_midi_error": "MIDI Learn failed",
        "controller_fix_selected": "Fix the selected control.",
        "controller_replace_title": "Replace this personal profile?",
        "controller_replace_body": (
            "{name} already exists in your bank. Replace it? A backup will be kept."
        ),
        "controller_backup": "Previous backup: {path}",
        "controller_saved_title": "Controller saved",
        "controller_saved_body": "{name} is available in your bank.\n\n{path}",
        "plugin_studio_title": "Plugin Studio",
        "plugin_studio_badge": "LOCAL • SAFE",
        "plugin_intro": (
            "Analyze a .rack2 project, group its instances by type, and create a local "
            "profile. AutoMap then uses your priorities without replacing manual assignments."
        ),
        "plugin": "Plug-in",
        "layer": "Layer",
        "parameters": "Parameters",
        "plugin_project": "LiveProfessor project (.rack2)",
        "plugin_browse": "Browse…",
        "plugin_analyze": "Analyze plug-ins",
        "plugin_format": "Format",
        "plugin_instances": "Instances",
        "plugin_recognition": "Recognition",
        "plugin_profile": "Applied profile",
        "plugin_profile_raw": "Raw LiveProfessor order",
        "plugin_status_empty": "Choose a project to recognize its plug-ins.",
        "plugin_status_running": "Analyzing the project and resolving profiles…",
        "plugin_catalog_status": "{profiles} profile(s) available. Analyze a project to apply them.",
        "plugin_status_analysis": "{types} type(s) recognized, {instances} instance(s).",
        "plugin_analysis_ready": "Analysis complete: {types} type(s), {instances} instance(s).",
        "plugin_analysis_error": "Could not analyze plug-ins",
        "plugin_scan_all": "Retrieve all real names",
        "plugin_scan_all_title": "Retrieve all parameter names",
        "plugin_scan_all_confirm": (
            "Controller Studio will read the parameters exported by the {types} installed "
            "plug-in types, each in an isolated process. Only inventories whose count "
            "exactly matches the project will be saved. Existing local profiles will be "
            "backed up before they are updated.\n\nThe .rack2 project will never be "
            "modified. Continue?"
        ),
        "plugin_scan_all_running": "Reading installed plug-ins…",
        "plugin_scan_all_progress": "Reading {current}/{total}: {name}",
        "plugin_scan_all_success": (
            "{saved} profile(s) updated with real names.\n"
            "{skipped} plug-in(s) skipped.{details}"
        ),
        "plugin_scan_all_details": (
            "\n\nDetails:\n{details}\n\nOpen a skipped plug-in profile to "
            "automatically use the LiveProfessor fallback."
        ),
        "plugin_scan_all_none": "No profile could be updated.{details}",
        "plugin_edit": "Create / edit profile…",
        "plugin_use_automap": "Use in AutoMap",
        "plugin_open_folder": "Profiles folder",
        "plugin_folder_error": "Could not open the folder",
        "plugin_select_required": "Plug-in required",
        "plugin_select_required_body": "Select an analyzed plug-in type first.",
        "plugin_layer_raw": "Raw",
        "plugin_layer_suggested": "Suggested",
        "plugin_layer_user": "User",
        "plugin_kind_continuous": "Continuous",
        "plugin_kind_toggle": "Toggle",
        "plugin_kind_enum": "List",
        "plugin_kind_meter": "Meter",
        "plugin_editor_title": "Plug-in profile — {name}",
        "plugin_editor_intro": (
            "Automatically read the real names from the installed plug-in, then choose "
            "exactly which parameters AutoMap should include."
        ),
        "plugin_editor_instances": "{instances} instance(s) • {parameters} parameter(s)",
        "plugin_parameter_enabled": "AutoMap",
        "plugin_parameter_enabled_editor": "Include this parameter in AutoMap",
        "plugin_select_all": "Select all",
        "plugin_select_none": "Select none",
        "plugin_enabled_count": "{enabled}/{total} parameter(s) included",
        "plugin_capture_names": "Automatically retrieve real names",
        "plugin_capture_names_title": "Retrieve real names",
        "plugin_scan_direct_busy": "Reading the installed plug-in…",
        "plugin_scan_direct_success": (
            "{count} real name(s) read directly from the installed plug-in. "
            "Review them before saving."
        ),
        "plugin_scan_fallback": (
            "Direct inspection of “{name}” did not succeed:\n{error}\n\n"
            "Would you like to try intercepting LiveProfessor feedback?"
        ),
        "plugin_capture_names_ready": (
            "In LiveProfessor, select an instance of “{name}”. In the top bar, click the "
            "map name and choose exactly “SiLeMI/O AutoMap - {name}” — not the Dynamic "
            "map. If the labels are visible on your controller, click OK. Otherwise, "
            "briefly select another plug-in and return to “{name}”: Controller Studio "
            "intercepts the names sent to the controller without changing the project."
        ),
        "plugin_capture_busy": "Intercepting names…",
        "plugin_capture_error": "Could not retrieve names: {error}",
        "plugin_capture_missing": (
            "No real name was received. Check that the correct instance is selected and "
            "“SiLeMI/O AutoMap - {name}” is the active map in LiveProfessor (the Dynamic "
            "map cannot be used), select another plug-in and return to this instance, "
            "then try again."
        ),
        "plugin_capture_no_map": (
            "The analyzed project does not yet contain a usable Controller Map for this "
            "plug-in. Create or open its AutoMap copy first."
        ),
        "plugin_capture_success": "{count} real name(s) captured. Review them before saving.",
        "plugin_parameter_number": "No.",
        "plugin_parameter_name": "Name",
        "plugin_short_label": "Short label",
        "plugin_parameter_kind": "Kind",
        "plugin_parameter_role": "Technical role",
        "plugin_parameter_unit": "Unit",
        "plugin_parameter_importance": "Priority",
        "plugin_parameter_editor": "Edit selected parameter",
        "plugin_parameter_apply": "Apply to row",
        "plugin_parameter_reset": "Restore row",
        "plugin_importance_help": "100 = placed before 0 in free AutoMap slots",
        "plugin_save_profile": "Save local profile",
        "plugin_close": "Close",
        "plugin_profile_invalid": "Invalid plug-in profile",
        "plugin_replace_title": "Update local profile?",
        "plugin_replace_body": (
            "{name} already exists. Save a new version and back up the previous one?"
        ),
        "plugin_profile_saved": "Local profile saved",
        "plugin_profile_saved_body": "Version {version}\n{path}\n{backup}",
        "plugin_backup_created": "Previous backup: {path}",
        "plugin_profile_saved_status": "Plug-in profile saved: {name}",
        "library_title": "Versioned public library",
        "library_description": (
            "Controller Studio works offline. Preview does not change anything; installation "
            "checks versions, schemas, and SHA-256 before an atomic replacement."
        ),
        "library_token_note": (
            "No token is required for the public library. GH_TOKEN or GITHUB_TOKEN remains "
            "optional to increase the GitHub limit or use a private fork."
        ),
        "catalog_ready": (
            "Catalog ready: {controllers} controller(s), {plugins} plug-in profile(s)."
        ),
        "catalog_invalid": "Invalid catalog",
        "catalog_invalid_status": "Invalid catalog: {error}",
        "controller_required": "Controller required",
        "select_controller": "Select a controller first.",
        "export_title": "Export the LiveProfessor controller",
        "controller_file_type": "LiveProfessor controller",
        "replace_file": "Replace the file?",
        "replace_file_body": "{name} already exists. Replace it?",
        "export_error": "Export failed",
        "controller_created": "Controller created",
        "controller_created_status": "Controller created: {name}",
        "export_details": (
            "{path}\n\n{rotaries} rotaries, {buttons} buttons\nSHA-256 {sha256}"
        ),
        "source_title": "Choose the source LiveProfessor project (read-only)",
        "project_file_type": "LiveProfessor project",
        "destination_title": "Create the AutoMap copy",
        "destination_forbidden": "Destination not allowed",
        "destination_forbidden_body": (
            "The AutoMap copy must be different from the source project."
        ),
        "replace_copy": "Replace the copy?",
        "replace_copy_body": "{name} already exists. Replace it?",
        "replace_controller": "Replace the controller?",
        "replace_controller_body": "{name} already exists. Replace it?",
        "preparation_error": "Preparation failed",
        "automap_created_status": "AutoMap copy created: {name}",
        "preparation_complete": "Preparation complete",
        "preparation_details": (
            "Source project preserved (SHA-256 {sha256}).\n\n"
            "Copy: {project}\nController: {controller}"
        ),
        "install_confirm": "Install the update?",
        "install_confirm_body": (
            "The current cache will be backed up before atomic installation."
        ),
        "installing_library": "Installing the library…",
        "reading_manifest": "Reading the remote manifest…",
        "library_current": "The library is already up to date.",
        "library_installed": "Library installed",
        "preview": "Preview",
        "update_error": "Update failed",
        "library_unchanged": "Library unchanged: {error}",
        "change_new": "NEW",
        "change_update": "UPDATE",
        "change_downgrade": "DOWNGRADE",
        "change_removed": "REMOVED",
        "collection_controller": "controller",
        "collection_plugin": "plug-in",
        "about_title": "About Controller Studio",
        "about_body": (
            "Controller Studio for LiveProfessor {version}\n"
            "SiLeMI/O — By Mamat  -------[]--\n\n"
            "An independent product that carries forward proven EC4 Bridge behavior.\n"
            "French/English interface, controller bank, Plugin Studio, and AutoMap."
        ),
        "tray_open": "Open Controller Studio",
        "tray_quit": "Quit",
        "tray_hidden": "Controller Studio is minimized to the notification area.",
        "settings_saved": "Preferences saved.",
        "settings_error": "Could not save preferences: {error}",
        "status_builtin": "built-in",
        "status_verified": "verified",
        "status_community": "community",
        "status_local": "local",
    },
}


def translated_text(language: str, key: str, **values: object) -> str:
    catalog = UI_TEXT.get(language, UI_TEXT["fr"])
    text = catalog.get(key, UI_TEXT["fr"].get(key, key))
    return text.format(**values) if values else text


@dataclass(frozen=True, slots=True)
class ControllerTableRow:
    profile_id: str
    manufacturer: str
    model: str
    status: str
    version: str
    controls: int
    banks: int
    pages: int


def controller_table_rows(
    registry: ControllerRegistry | None = None,
) -> tuple[ControllerTableRow, ...]:
    active_registry = registry or ControllerRegistry()
    return tuple(
        ControllerTableRow(
            profile_id=profile.id,
            manufacturer=profile.manufacturer,
            model=profile.model,
            status=profile.status,
            version=profile.profile_version,
            controls=len(profile.controls),
            banks=profile.bank_count,
            pages=profile.page_count,
        )
        for profile in active_registry.all()
    )


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return cleaned or "controller"


def _widget_exists(widget: object) -> bool:
    try:
        return bool(widget.winfo_exists())
    except (AttributeError, tk.TclError):
        return False


def live_runtime_supported(profile_id: str | None) -> bool:
    """Return whether a native real-time driver exists for a controller profile."""

    return profile_id == "faderfox.ec4"


class ControlHubDesktop:
    def __init__(self, root: tk.Tk, *, start_minimized: bool = False) -> None:
        self.root = root
        self.settings_path = default_desktop_settings_path()
        self.settings = load_desktop_settings(self.settings_path)
        self.language_var = tk.StringVar(value=self.settings.language)
        self.close_to_tray_var = tk.BooleanVar(value=self.settings.close_to_tray)
        self.start_with_windows_var = tk.BooleanVar(value=starts_with_windows())
        self.auto_start_runtime_var = tk.BooleanVar(
            value=self.settings.auto_start_runtime
        )
        self._start_minimized = bool(start_minimized)
        self._auto_start_after_id = None
        self._auto_start_retry_index = 0
        self.runtime_config_path = default_config_path()
        self._configuration_load_error: str | None = None
        try:
            self.runtime_config = load_config()
        except Exception as exc:
            self.runtime_config = BridgeConfig()
            self._configuration_load_error = str(exc)
        self.runtime_config.ui_language = self.settings.language
        self.runtime: EC4LiveProfessorRuntime | None = None
        self.runtime_snapshot = BridgeSnapshot(
            running=False,
            midi_connected=False,
            active_bank=self.runtime_config.start_bank,
            bank_count=max(
                1,
                (self.runtime_config.max_controls + self.runtime_config.bank_size - 1)
                // self.runtime_config.bank_size,
            ),
            setup=None,
            group=None,
            status="Arrete",
        )
        self._runtime_events: queue.SimpleQueue[tuple[str, object]] = queue.SimpleQueue()
        self._runtime_poll_after_id = None
        self._runtime_log_lines: list[str] = []
        self.midi_input_var = tk.StringVar(value=self.runtime_config.midi_input)
        self.midi_output_var = tk.StringVar(value=self.runtime_config.midi_output)
        self.liveprofessor_host_var = tk.StringVar(
            value=self.runtime_config.liveprofessor_host
        )
        self.liveprofessor_port_var = tk.StringVar(
            value=str(self.runtime_config.liveprofessor_port)
        )
        self.feedback_port_var = tk.StringVar(value=str(self.runtime_config.feedback_port))
        self.target_setup_var = tk.StringVar(value=str(self.runtime_config.target_setup))
        self.target_group_var = tk.StringVar(value=str(self.runtime_config.target_group))
        self.display_enabled_var = tk.BooleanVar(value=self.runtime_config.display_enabled)
        self.persistent_display_var = tk.BooleanVar(
            value=self.runtime_config.persistent_parameter_display
        )
        self.parameter_overlay_interval_var = tk.StringVar(
            value=str(self.runtime_config.parameter_overlay_interval_ms)
        )
        self.companion_refresh_delay_var = tk.StringVar(
            value=str(self.runtime_config.companion_refresh_delay_ms)
        )
        self.name_refresh_delay_var = tk.StringVar(
            value=str(self.runtime_config.name_refresh_delay_ms)
        )
        self.feedback_timeout_var = tk.StringVar(
            value=str(self.runtime_config.feedback_confirm_timeout_ms)
        )
        self.overlay_display_duration_var = tk.StringVar(
            value=str(self.runtime_config.overlay_display_duration_ms)
        )
        self.runtime_status = tk.StringVar(value=self._t("runtime_not_started"))
        self.runtime_last_event = tk.StringVar(value="—")
        self.runtime_bank = tk.StringVar(value="1 / 1")
        self.learn_status = tk.StringVar(value=self._t("learn_default_label"))
        self._learning = False
        self._learn_phase = ""
        self._learn_controls: list[tuple[int, int]] = []
        self._learn_pushes: list[tuple[int, int]] = []
        self.registry = ControllerRegistry()
        self.plugin_registry = PluginProfileRegistry()
        self.status = tk.StringVar(value=self._t("loading"))
        self.selected_profile_id: str | None = self.settings.active_controller_id
        self.live_profile_var = tk.StringVar()
        self._live_profile_id_by_label: dict[str, str] = {}
        self._live_profile_label_by_id: dict[str, str] = {}
        self.log_window: tk.Toplevel | None = None
        self.live_settings_window: tk.Toplevel | None = None
        self._plugin_analysis: PluginProjectAnalysis | None = None
        self._plugin_summary_by_iid: dict[str, PluginTypeSummary] = {}
        self._plugin_analysis_running = False
        self._plugin_batch_running = False
        self._plugin_analysis_results: queue.SimpleQueue[
            tuple[PluginProjectAnalysis | None, PluginProfileRegistry | None, str | None]
        ] = queue.SimpleQueue()
        self._library_buttons: list[ttk.Button] = []
        self._closing = False
        self._suppress_unmap = False
        self.current_page = "live"
        self._live_advanced_open = False
        try:
            self.log_path = configure_runtime_logging(self.runtime_config.log_level)
        except OSError as exc:
            self.log_path = default_log_path()
            self._configuration_load_error = self._configuration_load_error or str(exc)

        root.geometry("1180x760")
        root.minsize(1080, 680)
        if PRODUCT_ICON_PATH.is_file():
            try:
                root.iconbitmap(default=str(PRODUCT_ICON_PATH))
            except tk.TclError:
                pass
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Unmap>", self._on_root_unmap)
        self._configure_style()
        self.tray = WindowsTray(
            root,
            tooltip=FULL_PRODUCT_NAME,
            open_label=self._t("tray_open"),
            quit_label=self._t("tray_quit"),
            on_quit=self.quit,
            command_provider=self._tray_commands,
            icon_path=PRODUCT_ICON_PATH,
        )
        self._build_ui()
        self.reload_catalog()
        self._runtime_poll_after_id = self.root.after(100, self._poll_runtime_events)
        self.root.after_idle(self.refresh_midi_ports)
        self._append_runtime_log(f"{FULL_PRODUCT_NAME} {DISPLAY_VERSION}")
        self._append_runtime_log(f"Journal : {self.log_path}")
        if self._configuration_load_error:
            self._append_runtime_log(
                f"Configuration par defaut utilisee: {self._configuration_load_error}"
            )
        self.root.after_idle(self._apply_initial_startup_preferences)

    def _t(self, key: str, **values: object) -> str:
        return translated_text(self.language_var.get(), key, **values)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", foreground="#445064")
        style.configure("Status.TLabel", padding=(10, 7))
        style.configure("TNotebook.Tab", padding=(14, 7), font=("Segoe UI Semibold", 9))
        style.configure("TButton", padding=(9, 5))
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 9))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 9))
        style.configure("Section.TLabelframe", padding=(12, 10))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI Semibold", 10))

    def _build_ui(self) -> None:
        self.root.title(self._t("window_title", version=DISPLAY_VERSION))
        self._build_menu()
        shell = ttk.Frame(self.root)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        sidebar = tk.Frame(shell, bg="#101c26", width=210)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        self.sidebar_logo_image: tk.PhotoImage | None = None
        if PRODUCT_SIDEBAR_LOGO_PATH.is_file():
            try:
                self.sidebar_logo_image = tk.PhotoImage(
                    file=str(PRODUCT_SIDEBAR_LOGO_PATH)
                )
            except tk.TclError:
                self.sidebar_logo_image = None
        if self.sidebar_logo_image is not None:
            tk.Label(
                sidebar,
                image=self.sidebar_logo_image,
                bg="#101c26",
                borderwidth=0,
            ).pack(pady=(16, 4))
        tk.Label(
            sidebar,
            text=PRODUCT_NAME,
            bg="#101c26",
            fg="#f2f8fb",
            font=("Segoe UI Semibold", 17),
            anchor="center",
            justify="center",
        ).pack(fill="x", padx=14, pady=(0 if self.sidebar_logo_image else 24, 2))
        tk.Label(
            sidebar,
            text=self._t("brand_context", version=DISPLAY_VERSION),
            bg="#101c26",
            fg="#8ca4b3",
            font=("Segoe UI", 9),
            anchor="center",
            justify="center",
        ).pack(fill="x", padx=14, pady=(0, 18))

        self.sidebar_buttons: dict[str, tk.Button] = {}
        nav = tk.Frame(sidebar, bg="#101c26")
        nav.pack(fill="x", padx=12)
        for page, label in (
            ("live", self._t("tab_live")),
            ("controllers", self._t("tab_controllers")),
            ("plugins", self._t("tab_plugins")),
            ("library", self._t("tab_library")),
        ):
            button = tk.Button(
                nav,
                text=label,
                command=lambda selected=page: self._show_page(selected),
                anchor="w",
                padx=14,
                pady=10,
                relief="flat",
                borderwidth=0,
                font=("Segoe UI Semibold", 10),
                cursor="hand2",
            )
            button.pack(fill="x", pady=2)
            self.sidebar_buttons[page] = button
        tk.Button(
            nav,
            text=self._t("nav_automap"),
            command=self.prepare_automap,
            bg="#08a7c8",
            fg="#ffffff",
            activebackground="#0ab4d7",
            activeforeground="#ffffff",
            anchor="w",
            padx=14,
            pady=10,
            relief="flat",
            borderwidth=0,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        ).pack(fill="x", pady=(12, 2))

        sidebar_footer = tk.Frame(sidebar, bg="#101c26")
        sidebar_footer.pack(side="bottom", fill="x", padx=20, pady=18)
        signature = tk.Frame(sidebar_footer, bg="#101c26")
        signature.pack(fill="x")
        tk.Label(
            signature,
            text=BRAND_NAME,
            bg="#101c26",
            fg="#19d6f2",
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).pack(side="left")
        tk.Label(
            signature,
            text="By Mamat",
            bg="#101c26",
            fg="#8ca4b3",
            font=("Segoe UI", 8),
            anchor="e",
        ).pack(side="right")
        tk.Label(
            sidebar_footer,
            text="-------[]--",
            bg="#101c26",
            fg="#8ca4b3",
            font=("Consolas", 8),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            sidebar_footer,
            text=self._t("sidebar_footer"),
            bg="#101c26",
            fg="#6f8999",
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(5, 0))

        content = ttk.Frame(shell, padding=(24, 20, 24, 14))
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.page_frames: dict[str, ttk.Frame] = {}
        live_tab = ttk.Frame(content)
        self.live_tab = live_tab
        controllers_tab = ttk.Frame(content)
        plugins_tab = ttk.Frame(content)
        library_tab = ttk.Frame(content)
        self.page_frames.update(
            live=live_tab,
            controllers=controllers_tab,
            plugins=plugins_tab,
            library=library_tab,
        )
        for frame in self.page_frames.values():
            frame.grid(row=0, column=0, sticky="nsew")
        self._build_live_tab(live_tab)
        self._build_controllers_tab(controllers_tab)
        self._build_plugins_tab(plugins_tab)
        self._build_library_tab(library_tab)
        self._show_page(self.current_page)

        ttk.Separator(self.root).pack(fill="x")
        ttk.Label(
            self.root,
            textvariable=self.status,
            style="Status.TLabel",
            anchor="w",
        ).pack(fill="x")

    def _show_page(self, page: str) -> None:
        if page not in self.page_frames:
            page = "live"
        self.current_page = page
        self.page_frames[page].tkraise()
        for name, button in self.sidebar_buttons.items():
            if name == page:
                button.configure(
                    bg="#173647",
                    fg="#ffffff",
                    activebackground="#1c455a",
                    activeforeground="#ffffff",
                )
            else:
                button.configure(
                    bg="#101c26",
                    fg="#b8c8d2",
                    activebackground="#17303f",
                    activeforeground="#ffffff",
                )

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=0)
        running = bool(self.runtime and self.runtime.running)
        supported = live_runtime_supported(self.selected_profile_id)
        file_menu.add_command(
            label=self._t("start"),
            command=self.start_runtime,
            state="normal" if supported and not running else "disabled",
        )
        file_menu.add_command(
            label=self._t("stop"),
            command=self.stop_runtime,
            state="normal" if running else "disabled",
        )
        file_menu.add_command(
            label=self._t("restart"),
            command=self.restart_runtime,
            state="normal" if supported else "disabled",
        )
        file_menu.add_separator()
        file_menu.add_command(
            label=self._t("export_controller"), command=self.export_controller
        )
        file_menu.add_command(
            label=self._t("prepare_automap"), command=self.prepare_automap
        )
        file_menu.add_command(label=self._t("minimize"), command=self.minimize_to_tray)
        file_menu.add_separator()
        file_menu.add_command(label=self._t("quit"), command=self.quit)
        menu.add_cascade(label=self._t("menu_file"), menu=file_menu)

        options_menu = tk.Menu(menu, tearoff=0)
        options_menu.add_checkbutton(
            label=self._t("close_to_tray"),
            variable=self.close_to_tray_var,
            command=self._save_close_to_tray,
        )
        options_menu.add_checkbutton(
            label=self._t("start_with_windows"),
            variable=self.start_with_windows_var,
            command=self._save_start_with_windows,
        )
        options_menu.add_checkbutton(
            label=self._t("auto_start_runtime"),
            variable=self.auto_start_runtime_var,
            command=self._save_auto_start_runtime,
        )
        options_menu.add_separator()
        language_menu = tk.Menu(options_menu, tearoff=0)
        language_menu.add_radiobutton(
            label=self._t("french"),
            variable=self.language_var,
            value="fr",
            command=self.change_language,
        )
        language_menu.add_radiobutton(
            label=self._t("english"),
            variable=self.language_var,
            value="en",
            command=self.change_language,
        )
        options_menu.add_cascade(label=self._t("language"), menu=language_menu)
        menu.add_cascade(label=self._t("menu_options"), menu=options_menu)

        tools_menu = tk.Menu(menu, tearoff=0)
        tools_menu.add_command(
            label=self._t("prepare_automap"), command=self.prepare_automap
        )
        menu.add_cascade(label=self._t("menu_tools"), menu=tools_menu)

        library_menu = tk.Menu(menu, tearoff=0)
        library_menu.add_command(
            label=self._t("preview_updates"),
            command=lambda: self.run_library_update(False),
        )
        library_menu.add_command(
            label=self._t("install_update"),
            command=lambda: self.run_library_update(True),
        )
        menu.add_cascade(label=self._t("menu_library"), menu=library_menu)

        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label=self._t("open_manual"), command=self.open_manual)
        help_menu.add_command(
            label=self._t("check_app_updates"),
            command=self.check_application_updates,
        )
        help_menu.add_separator()
        help_menu.add_command(label=self._t("support"), command=self.show_support)
        help_menu.add_separator()
        help_menu.add_command(label=self._t("about"), command=self.show_about)
        menu.add_cascade(label=self._t("menu_help"), menu=help_menu)
        self.root.configure(menu=menu)

    def _build_live_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(5, weight=1)
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=self._t("live_title"), style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text=self._t("live_description"),
            style="Subtitle.TLabel",
            wraplength=720,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 0))
        self.live_driver_badge = tk.Label(
            header,
            bg="#e9f7f1",
            fg="#16825d",
            font=("Segoe UI Semibold", 8),
            padx=10,
            pady=5,
        )
        self.live_driver_badge.grid(row=0, column=1, rowspan=2, sticky="ne")

        controller = ttk.LabelFrame(
            parent,
            text=self._t("active_controller"),
            padding=12,
            style="Section.TLabelframe",
        )
        controller.grid(row=1, column=0, sticky="ew")
        controller.columnconfigure(0, weight=1)
        self.live_controller_combo = ttk.Combobox(
            controller,
            textvariable=self.live_profile_var,
            state="readonly",
        )
        self.live_controller_combo.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.live_controller_combo.bind(
            "<<ComboboxSelected>>", self._select_live_controller
        )
        ttk.Button(
            controller,
            text=self._t("configure_active_controller"),
            command=self.edit_controller,
        ).grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.live_driver_note = ttk.Label(
            controller,
            style="Subtitle.TLabel",
            wraplength=780,
            justify="left",
        )
        self.live_driver_note.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(7, 0)
        )

        startup_options = ttk.LabelFrame(
            parent,
            text=self._t("automation_options"),
            padding=10,
            style="Section.TLabelframe",
        )
        startup_options.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        startup_options.columnconfigure(0, weight=1, uniform="automation")
        startup_options.columnconfigure(1, weight=1, uniform="automation")
        windows_start = tk.Checkbutton(
            startup_options,
            text=self._t("start_with_windows"),
            variable=self.start_with_windows_var,
            command=self._save_start_with_windows,
            anchor="w",
            justify="left",
            wraplength=300,
            bg="#ffffff",
            activebackground="#ffffff",
            highlightthickness=0,
            font=("Segoe UI", 9),
        )
        windows_start.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.auto_start_runtime_check = tk.Checkbutton(
            startup_options,
            text=self._t("auto_start_runtime"),
            variable=self.auto_start_runtime_var,
            command=self._save_auto_start_runtime,
            anchor="w",
            justify="left",
            wraplength=340,
            bg="#ffffff",
            activebackground="#ffffff",
            highlightthickness=0,
            font=("Segoe UI", 9),
        )
        self.auto_start_runtime_check.grid(row=0, column=1, sticky="ew")

        dashboard = ttk.Frame(parent)
        dashboard.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        dashboard.columnconfigure(0, weight=2, uniform="dashboard")
        dashboard.columnconfigure(1, weight=1, uniform="dashboard")
        dashboard.rowconfigure(0, weight=1)

        state_frame = ttk.LabelFrame(
            dashboard,
            text=self._t("state_frame"),
            padding=14,
            style="Section.TLabelframe",
        )
        state_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        state_frame.columnconfigure(0, weight=1)
        ttk.Label(
            state_frame,
            textvariable=self.runtime_status,
            wraplength=470,
            justify="left",
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, columnspan=3, sticky="ew")

        runtime_controls = ttk.Frame(state_frame)
        runtime_controls.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(13, 12))
        runtime_controls.columnconfigure(0, weight=1)
        self.runtime_start_button = tk.Button(
            runtime_controls,
            text=f"▶  {self._t('start')}",
            command=self.start_runtime,
            bg="#08a7c8",
            fg="#ffffff",
            activebackground="#0ab4d7",
            activeforeground="#ffffff",
            disabledforeground="#d7eef3",
            relief="flat",
            borderwidth=0,
            padx=16,
            pady=8,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        )
        self.runtime_stop_button = ttk.Button(
            runtime_controls, text=self._t("stop"), command=self.stop_runtime
        )
        self.runtime_restart_button = ttk.Button(
            runtime_controls, text=self._t("restart"), command=self.restart_runtime
        )
        self.runtime_start_button.grid(row=0, column=0, sticky="ew")
        self.runtime_stop_button.grid(row=0, column=1, padx=(8, 0))
        self.runtime_restart_button.grid(row=0, column=2, padx=(8, 0))

        self.runtime_action_buttons: list[ttk.Button] = []
        self.runtime_settings_action_buttons: list[ttk.Button] = []

        self.previous_bank_button = ttk.Button(
            state_frame,
            text=self._t("previous_bank"),
            command=lambda: self.change_bank(-1),
        )
        self.previous_bank_button.grid(row=2, column=0, sticky="w")
        ttk.Label(
            state_frame,
            textvariable=self.runtime_bank,
            width=9,
            anchor="center",
            font=("Segoe UI Semibold", 10),
        ).grid(row=2, column=1, padx=8)
        self.next_bank_button = ttk.Button(
            state_frame,
            text=self._t("next_bank"),
            command=lambda: self.change_bank(1),
        )
        self.next_bank_button.grid(row=2, column=2, sticky="e")
        ttk.Separator(state_frame).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(14, 10)
        )
        ttk.Label(
            state_frame,
            text=self._t("last_event"),
            style="Subtitle.TLabel",
        ).grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(
            state_frame,
            textvariable=self.runtime_last_event,
            anchor="w",
            justify="left",
            wraplength=470,
        ).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(3, 0))

        quick = ttk.LabelFrame(
            dashboard,
            text=self._t("quick_access"),
            padding=14,
            style="Section.TLabelframe",
        )
        quick.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        quick.columnconfigure(0, weight=1)
        ttk.Button(
            quick,
            text=self._t("log_window"),
            command=self.show_runtime_log,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            quick,
            text=self._t("shortcuts"),
            command=self.show_shortcuts,
        ).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            quick,
            text=self._t("diagnostic"),
            command=self.show_diagnostics,
        ).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            quick,
            text=self._t("minimize"),
            command=self.minimize_to_tray,
        ).grid(row=3, column=0, sticky="ew", pady=(8, 0))

        self.live_advanced_button = ttk.Button(
            parent,
            text=self._t("advanced_controller_closed"),
            command=self._toggle_live_advanced,
        )
        self.live_advanced_button.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self.live_advanced_frame = ttk.Frame(parent)
        self.live_advanced_frame.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        self.live_advanced_frame.columnconfigure(0, weight=1)
        self.live_advanced_frame.rowconfigure(1, weight=1)
        advanced_actions = ttk.Frame(self.live_advanced_frame)
        advanced_actions.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(
            advanced_actions,
            text=self._t("live_settings"),
            command=self.show_live_settings,
        ).pack(side="left")
        ttk.Button(
            advanced_actions,
            text=self._t("configure_active_controller"),
            command=self.edit_controller,
        ).pack(side="left", padx=(8, 0))
        self.ec4_live_frame = ttk.LabelFrame(
            self.live_advanced_frame,
            text=self._t("ec4_zone"),
            padding=10,
            style="Section.TLabelframe",
        )
        self.ec4_live_frame.grid(row=1, column=0, sticky="nsew")
        target_row = ttk.Frame(self.ec4_live_frame)
        target_row.pack(fill="x")
        ttk.Label(target_row, text=self._t("target_setup")).pack(side="left")
        ttk.Spinbox(
            target_row,
            from_=1,
            to=16,
            width=5,
            textvariable=self.target_setup_var,
        ).pack(side="left", padx=(6, 14))
        ttk.Label(target_row, text=self._t("target_group")).pack(side="left")
        ttk.Spinbox(
            target_row,
            from_=1,
            to=16,
            width=5,
            textvariable=self.target_group_var,
        ).pack(side="left", padx=(6, 14))
        current_target = ttk.Button(
            target_row,
            text=self._t("use_current_target"),
            command=self.use_current_target,
        )
        current_target.pack(side="left")
        ttk.Button(
            target_row, text=self._t("shortcuts"), command=self.show_shortcuts
        ).pack(side="right")

        learn_row = ttk.Frame(self.ec4_live_frame)
        learn_row.pack(fill="x", pady=(8, 0))
        self.learn_button = ttk.Button(
            learn_row,
            text=self._t("learn_cancel" if self._learning else "learn_button"),
            command=self.toggle_midi_learn,
        )
        self.learn_button.pack(side="left", padx=(6, 8))
        self.runtime_action_buttons.extend((current_target, self.learn_button))
        ttk.Label(learn_row, textvariable=self.learn_status).pack(side="left")
        ttk.Button(
            learn_row, text=self._t("diagnostic"), command=self.show_diagnostics
        ).pack(side="right")
        if self._live_advanced_open:
            self.live_advanced_button.configure(
                text=self._t("advanced_controller_open")
            )
        else:
            self.live_advanced_frame.grid_remove()
        self._update_mapping_status()
        self._set_runtime_widget_states()

    def _toggle_live_advanced(self) -> None:
        self._live_advanced_open = not self._live_advanced_open
        if self._live_advanced_open:
            self.live_advanced_frame.grid()
            self.live_advanced_button.configure(
                text=self._t("advanced_controller_open")
            )
        else:
            self.live_advanced_frame.grid_remove()
            self.live_advanced_button.configure(
                text=self._t("advanced_controller_closed")
            )

    def _build_controllers_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        ttk.Label(
            parent,
            text=self._t("controllers_title"),
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            parent,
            text=self._t("controllers_description"),
            style="Subtitle.TLabel",
            wraplength=850,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 12))
        columns = ("maker", "model", "status", "version", "controls", "layout")
        self.controller_tree = ttk.Treeview(
            parent,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        headings = {
            "maker": self._t("maker"),
            "model": self._t("model"),
            "status": self._t("status"),
            "version": self._t("version"),
            "controls": self._t("controls"),
            "layout": self._t("layout"),
        }
        widths = {
            "maker": 150,
            "model": 260,
            "status": 100,
            "version": 90,
            "controls": 90,
            "layout": 120,
        }
        for column in columns:
            self.controller_tree.heading(column, text=headings[column])
            self.controller_tree.column(column, width=widths[column], anchor="w")
        scrollbar = ttk.Scrollbar(
            parent, orient="vertical", command=self.controller_tree.yview
        )
        self.controller_tree.configure(yscrollcommand=scrollbar.set)
        self.controller_tree.grid(row=2, column=0, sticky="nsew")
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.controller_tree.bind("<<TreeviewSelect>>", self._select_controller)
        self.controller_tree.bind("<Double-1>", lambda _event: self.edit_controller())

        actions = ttk.Frame(parent, padding=(0, 12, 0, 0))
        actions.grid(row=3, column=0, columnspan=2, sticky="ew")
        primary = ttk.Frame(actions)
        primary.pack(fill="x")
        tk.Button(
            primary,
            text=self._t("controller_create"),
            command=self.create_controller,
            bg="#087d9d",
            fg="#ffffff",
            activebackground="#0aa1c9",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=5,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        ).pack(side="left")
        ttk.Button(
            primary,
            text=self._t("controller_edit"),
            command=self.edit_controller,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            primary,
            text=self._t("controller_import"),
            command=self.import_controller,
        ).pack(side="left", padx=(8, 0))
        secondary = ttk.Frame(actions)
        secondary.pack(fill="x", pady=(7, 0))
        ttk.Button(secondary, text=self._t("refresh"), command=self.reload_catalog).pack(
            side="left"
        )
        ttk.Button(
            secondary,
            text=self._t("export_controller"),
            command=self.export_controller,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            secondary,
            text=self._t("contribute_controller"),
            command=self.contribute_controller,
        ).pack(side="left", padx=(8, 0))

    def _build_plugins_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(4, weight=1)
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text=self._t("plugin_studio_title"),
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            header,
            text=self._t("plugin_studio_badge"),
            bg="#dff5fb",
            fg="#087d9d",
            font=("Segoe UI Semibold", 8),
            padx=9,
            pady=3,
        ).grid(row=0, column=1, sticky="e")
        ttk.Label(
            parent,
            text=self._t("plugin_intro"),
            style="Subtitle.TLabel",
            wraplength=850,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        source = ttk.Frame(parent)
        source.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        source.columnconfigure(1, weight=1)
        self.plugin_project_var = tk.StringVar()
        ttk.Label(source, text=self._t("plugin_project")).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        ttk.Entry(source, textvariable=self.plugin_project_var).grid(
            row=0, column=1, sticky="ew"
        )
        ttk.Button(
            source,
            text=self._t("plugin_browse"),
            command=self._browse_plugin_project,
        ).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(
            source,
            text=self._t("plugin_analyze"),
            command=self._analyze_plugin_project,
        ).grid(row=0, column=3, padx=(8, 0))

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        self.plugin_analysis_status_var = tk.StringVar(
            value=self._t("plugin_status_empty")
        )
        ttk.Label(
            toolbar,
            textvariable=self.plugin_analysis_status_var,
            style="Subtitle.TLabel",
            wraplength=820,
            justify="left",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 7))
        plugin_actions = ttk.Frame(toolbar)
        plugin_actions.grid(row=1, column=0, sticky="ew")
        self.plugin_scan_all_button = ttk.Button(
            plugin_actions,
            text=self._t("plugin_scan_all"),
            command=self._scan_all_plugin_names,
            state="disabled",
            style="Accent.TButton",
        )
        self.plugin_scan_all_button.pack(side="left")
        self.plugin_edit_button = ttk.Button(
            plugin_actions,
            text=self._t("plugin_edit"),
            command=self._open_plugin_profile_editor,
            state="disabled",
        )
        self.plugin_edit_button.pack(side="left", padx=(8, 0))
        self.plugin_automap_button = ttk.Button(
            plugin_actions,
            text=self._t("plugin_use_automap"),
            command=self._use_plugin_project_in_automap,
            state="disabled",
        )
        self.plugin_automap_button.pack(side="left", padx=(8, 0))
        ttk.Button(
            plugin_actions,
            text=self._t("plugin_open_folder"),
            command=self._open_plugin_profile_folder,
        ).pack(side="right")

        tree_frame = ttk.Frame(parent)
        tree_frame.grid(row=4, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.plugin_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "format", "instances", "parameters", "layer", "profile"),
            show="headings",
            selectmode="browse",
        )
        for column, label, width in (
            ("name", self._t("plugin"), 240),
            ("format", self._t("plugin_format"), 80),
            ("instances", self._t("plugin_instances"), 75),
            ("parameters", self._t("parameters"), 85),
            ("layer", self._t("plugin_recognition"), 110),
            ("profile", self._t("plugin_profile"), 230),
        ):
            self.plugin_tree.heading(column, text=label)
            self.plugin_tree.column(column, width=width, anchor="w")
        plugin_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.plugin_tree.yview
        )
        self.plugin_tree.configure(yscrollcommand=plugin_scroll.set)
        self.plugin_tree.tag_configure("even", background="#f3f7f9")
        self.plugin_tree.grid(row=0, column=0, sticky="nsew")
        plugin_scroll.grid(row=0, column=1, sticky="ns")
        self.plugin_tree.bind("<<TreeviewSelect>>", self._select_plugin_type)
        self.plugin_tree.bind(
            "<Double-1>", lambda _event: self._open_plugin_profile_editor()
        )

    def _build_library_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Label(
            parent,
            text=self._t("library_title"),
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            parent,
            text=self._t("library_description"),
            wraplength=780,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 16))
        actions = ttk.Frame(parent)
        actions.grid(row=2, column=0, sticky="w")
        preview = ttk.Button(
            actions,
            text=self._t("preview_updates"),
            command=lambda: self.run_library_update(False),
        )
        apply_update = ttk.Button(
            actions,
            text=self._t("install_update"),
            command=lambda: self.run_library_update(True),
        )
        preview.pack(side="left")
        apply_update.pack(side="left", padx=(8, 0))
        self._library_buttons.extend((preview, apply_update))
        ttk.Label(
            parent,
            text=self._t("library_token_note"),
            style="Subtitle.TLabel",
            wraplength=780,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(18, 0))

    def _display_status(self, status: str) -> str:
        return self._t(f"status_{status}")

    def _plugin_layer_text(self, layer: PluginProfileLayer) -> str:
        return self._t(f"plugin_layer_{layer.value}")

    def _plugin_kind_text(self, kind: PluginParameterKind) -> str:
        return self._t(f"plugin_kind_{kind.value}")

    def _populate_plugin_catalog(self, profiles) -> None:
        for item in self.plugin_tree.get_children():
            self.plugin_tree.delete(item)
        self._plugin_summary_by_iid = {}
        for index, profile in enumerate(profiles):
            self.plugin_tree.insert(
                "",
                "end",
                iid=f"plugin-profile-{index}",
                tags=(("even",) if index % 2 == 0 else ()),
                values=(
                    profile.plugin_name,
                    profile.identity.plugin_format,
                    "—",
                    len(profile.parameters),
                    self._plugin_layer_text(profile.layer),
                    f"{profile.id}  v{profile.profile_version}",
                ),
            )
        self.plugin_analysis_status_var.set(
            self._t("plugin_catalog_status", profiles=len(profiles))
        )
        self.plugin_edit_button.configure(state="disabled")
        self.plugin_scan_all_button.configure(state="disabled")
        self.plugin_automap_button.configure(state="disabled")

    def _populate_plugin_analysis(self, analysis: PluginProjectAnalysis) -> None:
        for item in self.plugin_tree.get_children():
            self.plugin_tree.delete(item)
        self._plugin_summary_by_iid = {}
        for index, summary in enumerate(analysis.plugin_types):
            iid = f"plugin-type-{index}"
            self._plugin_summary_by_iid[iid] = summary
            applied = ", ".join(summary.resolved.applied_profile_ids)
            if not applied:
                applied = self._t("plugin_profile_raw")
            self.plugin_tree.insert(
                "",
                "end",
                iid=iid,
                tags=(("even",) if index % 2 == 0 else ()),
                values=(
                    summary.observation.name,
                    summary.observation.plugin_format,
                    len(summary.instances),
                    len(summary.observation.parameters),
                    self._plugin_layer_text(summary.resolved.layer),
                    applied,
                ),
            )
        self.plugin_analysis_status_var.set(
            self._t(
                "plugin_status_analysis",
                types=len(analysis.plugin_types),
                instances=analysis.instance_count,
            )
        )
        self.plugin_edit_button.configure(state="disabled")
        self.plugin_scan_all_button.configure(
            state="normal" if analysis.plugin_types else "disabled"
        )
        self.plugin_automap_button.configure(state="normal")
        if analysis.plugin_types:
            first = "plugin-type-0"
            self.plugin_tree.selection_set(first)
            self.plugin_tree.focus(first)
            self.plugin_edit_button.configure(state="normal")

    def _selected_plugin_summary(self) -> PluginTypeSummary | None:
        selected = self.plugin_tree.selection()
        if not selected:
            return None
        return self._plugin_summary_by_iid.get(selected[0])

    def _select_plugin_type(self, _event=None) -> None:
        state = (
            "normal"
            if self._selected_plugin_summary() is not None
            and not self._plugin_batch_running
            else "disabled"
        )
        self.plugin_edit_button.configure(state=state)

    def _browse_plugin_project(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title=self._t("source_title"),
            filetypes=((self._t("project_file_type"), "*.rack2"),),
        )
        if selected:
            self.plugin_project_var.set(selected)
            self._analyze_plugin_project()

    def _analyze_plugin_project(self) -> None:
        if self._plugin_analysis_running:
            return
        path = Path(self.plugin_project_var.get().strip())
        self._plugin_analysis_running = True
        self.plugin_analysis_status_var.set(self._t("plugin_status_running"))
        self.plugin_edit_button.configure(state="disabled")
        self.plugin_scan_all_button.configure(state="disabled")
        self.plugin_automap_button.configure(state="disabled")

        def worker() -> None:
            try:
                registry = PluginProfileRegistry()
                analysis = analyze_plugin_project(path, registry.all())
            except Exception as exc:
                self._plugin_analysis_results.put((None, None, str(exc)))
                return
            self._plugin_analysis_results.put((analysis, registry, None))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(40, self._poll_plugin_analysis_result)

    def _poll_plugin_analysis_result(self) -> None:
        try:
            analysis, registry, error = self._plugin_analysis_results.get_nowait()
        except queue.Empty:
            if self._plugin_analysis_running:
                self.root.after(40, self._poll_plugin_analysis_result)
            return
        self._finish_plugin_analysis(analysis, registry, error)

    def _finish_plugin_analysis(
        self,
        analysis: PluginProjectAnalysis | None,
        registry: PluginProfileRegistry | None,
        error: str | None,
    ) -> None:
        self._plugin_analysis_running = False
        if error is not None or analysis is None or registry is None:
            self._plugin_analysis = None
            self.plugin_analysis_status_var.set(error or self._t("plugin_analysis_error"))
            self.plugin_edit_button.configure(state="disabled")
            self.plugin_scan_all_button.configure(state="disabled")
            self.plugin_automap_button.configure(state="disabled")
            messagebox.showerror(
                self._t("plugin_analysis_error"),
                error or self._t("plugin_analysis_error"),
                parent=self.root,
            )
            return
        self.plugin_registry = registry
        self._plugin_analysis = analysis
        self.plugin_project_var.set(str(analysis.path))
        self._populate_plugin_analysis(analysis)
        self.status.set(
            self._t(
                "plugin_analysis_ready",
                types=len(analysis.plugin_types),
                instances=analysis.instance_count,
            )
        )

    def _open_plugin_profile_folder(self) -> None:
        folder = default_user_plugin_profile_dir()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(folder))
        except OSError as exc:
            messagebox.showerror(
                self._t("plugin_folder_error"),
                str(exc),
                parent=self.root,
            )

    def _use_plugin_project_in_automap(self) -> None:
        analysis = self._plugin_analysis
        if analysis is None:
            return
        self.prepare_automap()
        self.automap_project_var.set(str(analysis.path))
        self._analyze_automap_project()

    def _scan_all_plugin_names(self) -> None:
        analysis = self._plugin_analysis
        if analysis is None or self._plugin_batch_running:
            return
        if not messagebox.askyesno(
            self._t("plugin_scan_all_title"),
            self._t("plugin_scan_all_confirm", types=len(analysis.plugin_types)),
            parent=self.root,
        ):
            return

        self._plugin_batch_running = True
        self.plugin_scan_all_button.configure(state="disabled")
        self.plugin_edit_button.configure(state="disabled")
        self.plugin_automap_button.configure(state="disabled")
        self.plugin_analysis_status_var.set(self._t("plugin_scan_all_running"))

        def show_progress(current: int, name: str) -> None:
            if self._closing:
                return
            self.plugin_analysis_status_var.set(
                self._t(
                    "plugin_scan_all_progress",
                    current=current,
                    total=len(analysis.plugin_types),
                    name=name,
                )
            )

        def worker() -> None:
            prepared: list[tuple[PluginTypeSummary, object]] = []
            errors: list[str] = []
            try:
                profiles = list(PluginProfileRegistry().all())
                for index, summary in enumerate(analysis.plugin_types, start=1):
                    self.root.after(
                        0,
                        lambda current=index, name=summary.observation.name: show_progress(
                            current, name
                        ),
                    )
                    try:
                        scan = retrieve_installed_parameter_names(summary)
                        parameters = merge_scanned_parameter_names(
                            editable_parameters(summary.resolved),
                            scan,
                        )
                        current_profile = compatible_user_profile(
                            profiles,
                            summary.observation,
                        )
                        profile = build_user_profile(
                            summary.observation,
                            parameters,
                            profile_id=(
                                current_profile.id
                                if current_profile is not None
                                else None
                            ),
                            profile_version=next_user_profile_version(
                                profiles,
                                summary.observation,
                            ),
                        )
                        prepared.append((summary, profile))
                        profiles.append(profile)
                    except Exception as exc:
                        errors.append(f"{summary.observation.name}: {exc}")

                current_hash = hashlib.sha256(analysis.path.read_bytes()).hexdigest().upper()
                if current_hash != analysis.source_sha256:
                    prepared.clear()
                    errors.append(
                        "Le projet LiveProfessor a changé pendant la lecture ; "
                        "aucun profil n'a été enregistré."
                    )

                saved = 0
                for summary, profile in prepared:
                    try:
                        destination = (
                            default_user_plugin_profile_dir() / f"{profile.id}.json"
                        )
                        save_user_profile(profile, replace=destination.exists())
                        saved += 1
                    except Exception as exc:
                        errors.append(f"{summary.observation.name}: {exc}")
            except Exception as exc:
                saved = 0
                errors.append(str(exc))

            self.root.after(0, lambda: finish(saved, errors))

        def finish(saved: int, errors: list[str]) -> None:
            self._plugin_batch_running = False
            if self._closing:
                return
            detail_lines = errors[:8]
            if len(errors) > len(detail_lines):
                detail_lines.append(f"… +{len(errors) - len(detail_lines)}")
            details = (
                self._t("plugin_scan_all_details", details="\n".join(detail_lines))
                if detail_lines
                else ""
            )
            if saved:
                body = self._t(
                    "plugin_scan_all_success",
                    saved=saved,
                    skipped=len(errors),
                    details=details,
                )
                if errors:
                    messagebox.showwarning(
                        self._t("plugin_scan_all_title"), body, parent=self.root
                    )
                else:
                    messagebox.showinfo(
                        self._t("plugin_scan_all_title"), body, parent=self.root
                    )
            else:
                messagebox.showerror(
                    self._t("plugin_scan_all_title"),
                    self._t("plugin_scan_all_none", details=details),
                    parent=self.root,
                )
            self._analyze_plugin_project()

        threading.Thread(
            target=worker,
            name="installed-plugin-batch-scanner",
            daemon=True,
        ).start()

    def _open_plugin_profile_editor(self) -> None:
        summary = self._selected_plugin_summary()
        if summary is None:
            messagebox.showwarning(
                self._t("plugin_select_required"),
                self._t("plugin_select_required_body"),
                parent=self.root,
            )
            return

        parameters = list(editable_parameters(summary.resolved))
        loaded_parameters = tuple(parameters)
        window = tk.Toplevel(self.root)
        window.title(
            self._t("plugin_editor_title", name=summary.observation.name)
        )
        window.geometry("940x680")
        window.minsize(800, 580)
        window.transient(self.root)
        if PRODUCT_ICON_PATH.is_file():
            try:
                window.iconbitmap(default=str(PRODUCT_ICON_PATH))
            except tk.TclError:
                pass

        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        ttk.Label(
            frame,
            text=self._t("plugin_editor_intro"),
            style="Subtitle.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        identity = (
            f"{summary.observation.stable_id}  •  "
            f"{summary.observation.parameter_fingerprint}"
        )
        identity_var = tk.StringVar(value=identity)
        ttk.Entry(
            frame,
            textvariable=identity_var,
            state="readonly",
        ).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(
            frame,
            text=self._t(
                "plugin_editor_instances",
                instances=len(summary.instances),
                parameters=len(parameters),
            ),
        ).grid(row=2, column=0, sticky="w", pady=(0, 6))

        table = ttk.Frame(frame)
        table.grid(row=3, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        parameter_tree = ttk.Treeview(
            table,
            columns=("enabled", "number", "name", "short", "kind", "role", "importance"),
            show="headings",
            selectmode="browse",
        )
        for column, label, width in (
            ("enabled", self._t("plugin_parameter_enabled"), 72),
            ("number", self._t("plugin_parameter_number"), 48),
            ("name", self._t("plugin_parameter_name"), 260),
            ("short", self._t("plugin_short_label"), 110),
            ("kind", self._t("plugin_parameter_kind"), 110),
            ("role", self._t("plugin_parameter_role"), 140),
            ("importance", self._t("plugin_parameter_importance"), 85),
        ):
            parameter_tree.heading(column, text=label)
            parameter_tree.column(column, width=width, anchor="w")
        parameter_scroll = ttk.Scrollbar(
            table, orient="vertical", command=parameter_tree.yview
        )
        parameter_tree.configure(yscrollcommand=parameter_scroll.set)
        parameter_tree.grid(row=0, column=0, sticky="nsew")
        parameter_scroll.grid(row=0, column=1, sticky="ns")

        def refresh_parameter_row(index: int) -> None:
            parameter = parameters[index]
            parameter_tree.item(
                f"parameter-{index}",
                values=(
                    "☑" if parameter.enabled else "☐",
                    index + 1,
                    parameter.name,
                    parameter.short_label,
                    self._plugin_kind_text(parameter.kind),
                    parameter.role or "",
                    parameter.importance,
                ),
            )

        for index, parameter in enumerate(parameters):
            parameter_tree.insert(
                "",
                "end",
                iid=f"parameter-{index}",
                values=(
                    "☑" if parameter.enabled else "☐",
                    index + 1,
                    parameter.name,
                    parameter.short_label,
                    self._plugin_kind_text(parameter.kind),
                    parameter.role or "",
                    parameter.importance,
                ),
            )

        included_var = tk.StringVar()

        def refresh_included_count() -> None:
            included_var.set(
                self._t(
                    "plugin_enabled_count",
                    enabled=sum(parameter.enabled for parameter in parameters),
                    total=len(parameters),
                )
            )

        def set_all_parameters(enabled: bool) -> None:
            for index, parameter in enumerate(parameters):
                parameters[index] = replace(parameter, enabled=enabled)
                refresh_parameter_row(index)
            refresh_included_count()
            load_parameter()

        def toggle_parameter(index: int) -> None:
            parameters[index] = replace(
                parameters[index], enabled=not parameters[index].enabled
            )
            refresh_parameter_row(index)
            refresh_included_count()
            load_parameter()

        def toggle_parameter_from_pointer(event) -> str | None:
            row = parameter_tree.identify_row(event.y)
            column = parameter_tree.identify_column(event.x)
            if row and column == "#1":
                parameter_tree.selection_set(row)
                toggle_parameter(int(row.removeprefix("parameter-")))
                return "break"
            return None

        def toggle_selected_parameter(_event=None) -> str:
            index = selected_parameter_index()
            if index is not None:
                toggle_parameter(index)
            return "break"

        selection_bar = ttk.Frame(table)
        selection_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            selection_bar,
            text=self._t("plugin_select_all"),
            command=lambda: set_all_parameters(True),
        ).pack(side="left")
        ttk.Button(
            selection_bar,
            text=self._t("plugin_select_none"),
            command=lambda: set_all_parameters(False),
        ).pack(side="left", padx=(8, 0))

        def begin_liveprofessor_capture() -> None:
            nonlocal parameters
            if not messagebox.askokcancel(
                self._t("plugin_capture_names_title"),
                self._t("plugin_capture_names_ready", name=summary.observation.name),
                parent=window,
            ):
                capture_button.configure(
                    state="normal",
                    text=self._t("plugin_capture_names"),
                )
                return
            capture_button.configure(
                state="disabled",
                text=self._t("plugin_capture_busy"),
            )

            def finish_capture(live_names: tuple[str, ...]) -> None:
                nonlocal parameters
                capture_button.configure(
                    state="normal",
                    text=self._t("plugin_capture_names"),
                )
                analysis = self._plugin_analysis
                if analysis is None:
                    return
                try:
                    updated, count = capture_liveprofessor_parameter_names(
                        parameters,
                        project=analysis.path,
                        plugin_uid=summary.instances[0].plugin_uid,
                        live_names=live_names,
                    )
                except PluginProfileError:
                    messagebox.showwarning(
                        self._t("plugin_capture_names_title"),
                        self._t("plugin_capture_no_map"),
                        parent=window,
                    )
                    return
                if count <= 0:
                    messagebox.showwarning(
                        self._t("plugin_capture_names_title"),
                        self._t(
                            "plugin_capture_missing",
                            name=summary.observation.name,
                        ),
                        parent=window,
                    )
                    return
                parameters = list(updated)
                for index in range(len(parameters)):
                    refresh_parameter_row(index)
                refresh_included_count()
                load_parameter()
                messagebox.showinfo(
                    self._t("plugin_capture_names_title"),
                    self._t("plugin_capture_success", count=count),
                    parent=window,
                )

            def fail_capture(error: str) -> None:
                capture_button.configure(
                    state="normal",
                    text=self._t("plugin_capture_names"),
                )
                messagebox.showwarning(
                    self._t("plugin_capture_names_title"),
                    self._t("plugin_capture_error", error=error),
                    parent=window,
                )

            runtime = self.runtime
            if runtime is not None and runtime.running:
                analysis = self._plugin_analysis
                if analysis is None:
                    fail_capture("aucun projet LiveProfessor analysé")
                    return
                required_slots = tuple(
                    inspect_plugin_parameter_slots(
                        analysis.path,
                        plugin_uid=summary.instances[0].plugin_uid,
                    )
                )

                def collect_runtime_names() -> None:
                    try:
                        live_names = runtime.capture_companion_names(
                            required_indices=required_slots,
                        )
                    except Exception as exc:
                        error = str(exc)
                        window.after(0, lambda: fail_capture(error))
                        return
                    window.after(0, lambda: finish_capture(live_names))

                threading.Thread(
                    target=collect_runtime_names,
                    name="liveprofessor-runtime-name-capture",
                    daemon=True,
                ).start()
                return

            try:
                request_host = self.liveprofessor_host_var.get().strip() or "127.0.0.1"
                request_port = int(self.liveprofessor_port_var.get().strip())
                feedback_port = int(self.feedback_port_var.get().strip())
            except ValueError:
                fail_capture("ports OSC invalides")
                return

            def collect_names() -> None:
                try:
                    live_names = request_liveprofessor_companion_names(
                        host=request_host,
                        request_port=request_port,
                        feedback_host=self.runtime_config.feedback_host,
                        feedback_port=feedback_port,
                    )
                except Exception as exc:
                    error = str(exc)
                    window.after(0, lambda: fail_capture(error))
                    return
                window.after(0, lambda: finish_capture(live_names))

            threading.Thread(
                target=collect_names,
                name="liveprofessor-name-capture",
                daemon=True,
            ).start()

        def capture_names_automatically() -> None:
            nonlocal parameters
            capture_button.configure(
                state="disabled",
                text=self._t("plugin_scan_direct_busy"),
            )

            def finish_direct_scan(scan) -> None:
                nonlocal parameters
                try:
                    parameters = list(
                        merge_scanned_parameter_names(parameters, scan)
                    )
                except Exception as exc:
                    offer_liveprofessor_fallback(str(exc))
                    return
                capture_button.configure(
                    state="normal",
                    text=self._t("plugin_capture_names"),
                )
                for index in range(len(parameters)):
                    refresh_parameter_row(index)
                refresh_included_count()
                load_parameter()
                messagebox.showinfo(
                    self._t("plugin_capture_names_title"),
                    self._t(
                        "plugin_scan_direct_success",
                        count=len(parameters),
                    ),
                    parent=window,
                )

            def offer_liveprofessor_fallback(error: str) -> None:
                capture_button.configure(
                    state="normal",
                    text=self._t("plugin_capture_names"),
                )
                if messagebox.askyesno(
                    self._t("plugin_capture_names_title"),
                    self._t(
                        "plugin_scan_fallback",
                        name=summary.observation.name,
                        error=error,
                    ),
                    parent=window,
                ):
                    begin_liveprofessor_capture()

            def scan_installed_plugin() -> None:
                try:
                    scan = retrieve_installed_parameter_names(summary)
                except Exception as exc:
                    error = str(exc)
                    window.after(0, lambda: offer_liveprofessor_fallback(error))
                    return
                window.after(0, lambda: finish_direct_scan(scan))

            threading.Thread(
                target=scan_installed_plugin,
                name="installed-plugin-name-scanner",
                daemon=True,
            ).start()

        capture_button = ttk.Button(
            selection_bar,
            text=self._t("plugin_capture_names"),
            command=capture_names_automatically,
            style="Accent.TButton",
        )
        capture_button.pack(side="left", padx=(16, 0))
        ttk.Label(
            selection_bar,
            textvariable=included_var,
            style="Subtitle.TLabel",
        ).pack(side="right")
        refresh_included_count()

        editor = ttk.LabelFrame(
            frame,
            text=self._t("plugin_parameter_editor"),
            padding=10,
        )
        editor.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        editor.columnconfigure(1, weight=1)
        editor.columnconfigure(3, weight=1)
        name_var = tk.StringVar()
        short_var = tk.StringVar()
        unit_var = tk.StringVar()
        role_var = tk.StringVar()
        kind_var = tk.StringVar()
        importance_var = tk.StringVar()
        enabled_var = tk.BooleanVar(value=True)
        ttk.Label(editor, text=self._t("plugin_parameter_name")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(editor, textvariable=name_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 14)
        )
        ttk.Label(editor, text=self._t("plugin_short_label")).grid(
            row=0, column=2, sticky="w"
        )
        ttk.Entry(editor, textvariable=short_var, width=18).grid(
            row=0, column=3, sticky="ew", padx=(6, 0)
        )
        ttk.Label(editor, text=self._t("plugin_parameter_kind")).grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        kind_by_label = {
            self._plugin_kind_text(kind): kind for kind in PluginParameterKind
        }
        ttk.Combobox(
            editor,
            textvariable=kind_var,
            values=tuple(kind_by_label),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=(6, 14), pady=(8, 0))
        ttk.Label(editor, text=self._t("plugin_parameter_role")).grid(
            row=1, column=2, sticky="w", pady=(8, 0)
        )
        ttk.Entry(editor, textvariable=role_var).grid(
            row=1, column=3, sticky="ew", padx=(6, 0), pady=(8, 0)
        )
        ttk.Label(editor, text=self._t("plugin_parameter_unit")).grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Entry(editor, textvariable=unit_var).grid(
            row=2, column=1, sticky="ew", padx=(6, 14), pady=(8, 0)
        )
        ttk.Label(editor, text=self._t("plugin_parameter_importance")).grid(
            row=2, column=2, sticky="w", pady=(8, 0)
        )
        ttk.Spinbox(
            editor,
            textvariable=importance_var,
            from_=0,
            to=100,
            width=8,
        ).grid(row=2, column=3, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Checkbutton(
            editor,
            text=self._t("plugin_parameter_enabled_editor"),
            variable=enabled_var,
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))

        def selected_parameter_index() -> int | None:
            selected = parameter_tree.selection()
            if not selected:
                return None
            return int(selected[0].removeprefix("parameter-"))

        def load_parameter(_event=None) -> None:
            index = selected_parameter_index()
            if index is None:
                return
            parameter = parameters[index]
            name_var.set(parameter.name)
            short_var.set(parameter.short_label)
            unit_var.set(parameter.unit)
            role_var.set(parameter.role or "")
            kind_var.set(self._plugin_kind_text(parameter.kind))
            importance_var.set(str(parameter.importance))
            enabled_var.set(parameter.enabled)

        def apply_parameter(*, show_error: bool = True) -> bool:
            index = selected_parameter_index()
            if index is None:
                return True
            selected_kind = kind_by_label.get(kind_var.get())
            try:
                raw = {
                    "stable_id": parameters[index].stable_id,
                    "name": name_var.get().strip(),
                    "short_label": short_var.get().strip(),
                    "unit": unit_var.get().strip(),
                    "kind": selected_kind.value if selected_kind is not None else "",
                    "importance": int(importance_var.get()),
                    "enabled": bool(enabled_var.get()),
                }
                role = role_var.get().strip()
                if role:
                    raw["role"] = role
                parameters[index] = PluginParameterProfile.from_dict(raw, index=index)
            except (ValueError, TypeError) as exc:
                if show_error:
                    messagebox.showerror(
                        self._t("plugin_profile_invalid"),
                        str(exc),
                        parent=window,
                    )
                return False
            refresh_parameter_row(index)
            refresh_included_count()
            return True

        def reset_parameter() -> None:
            index = selected_parameter_index()
            if index is None:
                return
            parameters[index] = loaded_parameters[index]
            refresh_parameter_row(index)
            refresh_included_count()
            load_parameter()

        button_row = ttk.Frame(editor)
        button_row.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Button(
            button_row,
            text=self._t("plugin_parameter_apply"),
            command=apply_parameter,
        ).pack(side="left")
        ttk.Button(
            button_row,
            text=self._t("plugin_parameter_reset"),
            command=reset_parameter,
        ).pack(side="left", padx=(8, 0))
        ttk.Label(
            button_row,
            text=self._t("plugin_importance_help"),
            style="Subtitle.TLabel",
        ).pack(side="right")

        parameter_tree.bind("<Double-1>", toggle_parameter_from_pointer)
        parameter_tree.bind("<space>", toggle_selected_parameter)

        actions = ttk.Frame(frame)
        actions.grid(row=5, column=0, sticky="ew", pady=(12, 0))

        def save_profile() -> None:
            if not apply_parameter():
                return
            try:
                profiles = PluginProfileRegistry().all()
                current = compatible_user_profile(profiles, summary.observation)
                profile = build_user_profile(
                    summary.observation,
                    parameters,
                    profile_id=(current.id if current is not None else None),
                    profile_version=next_user_profile_version(
                        profiles, summary.observation
                    ),
                )
                destination = default_user_plugin_profile_dir() / f"{profile.id}.json"
                replace_profile = destination.exists()
                if replace_profile and not messagebox.askyesno(
                    self._t("plugin_replace_title"),
                    self._t("plugin_replace_body", name=destination.name),
                    parent=window,
                ):
                    return
                result = save_user_profile(profile, replace=replace_profile)
            except Exception as exc:
                messagebox.showerror(
                    self._t("plugin_profile_invalid"),
                    str(exc),
                    parent=window,
                )
                return
            backup = (
                self._t("plugin_backup_created", path=result.backup_path)
                if result.backup_path is not None
                else ""
            )
            messagebox.showinfo(
                self._t("plugin_profile_saved"),
                self._t(
                    "plugin_profile_saved_body",
                    path=result.path,
                    version=result.profile.profile_version,
                    backup=backup,
                ),
                parent=window,
            )
            window.destroy()
            self.reload_catalog()
            self.status.set(
                self._t("plugin_profile_saved_status", name=result.path.name)
            )

        ttk.Button(
            actions,
            text=self._t("plugin_close"),
            command=window.destroy,
        ).pack(side="right")
        tk.Button(
            actions,
            text=self._t("plugin_save_profile"),
            command=save_profile,
            bg="#087d9d",
            fg="#ffffff",
            activebackground="#0aa1c9",
            activeforeground="#ffffff",
            relief="flat",
            borderwidth=0,
            padx=14,
            pady=5,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        ).pack(side="right", padx=(0, 8))

        parameter_tree.bind("<<TreeviewSelect>>", load_parameter)
        if parameters:
            parameter_tree.selection_set("parameter-0")
            parameter_tree.focus("parameter-0")
            load_parameter()

    def reload_catalog(self, preferred_profile_id: str | None = None) -> None:
        previous = preferred_profile_id or self.selected_profile_id
        for item in self.controller_tree.get_children():
            self.controller_tree.delete(item)
        for item in self.plugin_tree.get_children():
            self.plugin_tree.delete(item)
        try:
            rows = controller_table_rows(self.registry)
            for row in rows:
                self.controller_tree.insert(
                    "",
                    "end",
                    iid=row.profile_id,
                    values=(
                        row.manufacturer,
                        row.model,
                        self._display_status(row.status),
                        row.version,
                        row.controls,
                        f"{row.banks} / {row.pages}",
                    ),
                )
            self.plugin_registry = PluginProfileRegistry()
            plugins = self.plugin_registry.all()
            if self._plugin_analysis is not None:
                self._plugin_analysis = analyze_plugin_project(
                    self._plugin_analysis.path,
                    plugins,
                )
                self._populate_plugin_analysis(self._plugin_analysis)
            else:
                self._populate_plugin_catalog(plugins)
            available = {row.profile_id for row in rows}
            default_profile = (
                "faderfox.ec4"
                if "faderfox.ec4" in available
                else (rows[0].profile_id if rows else None)
            )
            selected = previous if previous in available else default_profile
            if selected is not None:
                self.controller_tree.selection_set(selected)
                self.controller_tree.focus(selected)
            self.selected_profile_id = selected
            self._refresh_live_controller_choices()
            self._apply_live_profile_state()
            self.status.set(
                self._t(
                    "catalog_ready",
                    controllers=len(rows),
                    plugins=len(plugins),
                )
            )
        except Exception as exc:
            self.status.set(self._t("catalog_invalid_status", error=exc))
            messagebox.showerror(
                self._t("catalog_invalid"), str(exc), parent=self.root
            )

    def _select_controller(self, _event=None) -> None:
        selected = self.controller_tree.selection()
        profile_id = selected[0] if selected else None
        if profile_id == self.selected_profile_id:
            return
        if self.runtime is not None and self.runtime.running:
            self.stop_runtime()
        self.selected_profile_id = profile_id
        self._remember_active_controller(profile_id)
        self.live_profile_var.set(self._live_profile_label_by_id.get(profile_id, ""))
        self._apply_live_profile_state()

    def _refresh_live_controller_choices(self) -> None:
        labels: list[str] = []
        self._live_profile_id_by_label = {}
        self._live_profile_label_by_id = {}
        for profile in self.registry.all():
            label = f"{profile.manufacturer} — {profile.model}"
            if label in self._live_profile_id_by_label:
                label = f"{label} [{profile.id}]"
            labels.append(label)
            self._live_profile_id_by_label[label] = profile.id
            self._live_profile_label_by_id[profile.id] = label
        if hasattr(self, "live_controller_combo"):
            self.live_controller_combo.configure(values=tuple(labels))
        self.live_profile_var.set(
            self._live_profile_label_by_id.get(self.selected_profile_id, "")
        )

    def _select_live_controller(self, _event=None) -> None:
        profile_id = self._live_profile_id_by_label.get(self.live_profile_var.get())
        if profile_id is None or profile_id == self.selected_profile_id:
            return
        if self.runtime is not None and self.runtime.running:
            self.stop_runtime()
        self.selected_profile_id = profile_id
        self._remember_active_controller(profile_id)
        if hasattr(self, "controller_tree"):
            self.controller_tree.selection_set(profile_id)
            self.controller_tree.focus(profile_id)
            self.controller_tree.see(profile_id)
        self._apply_live_profile_state()

    def _remember_active_controller(self, profile_id: str | None) -> None:
        if profile_id == self.settings.active_controller_id:
            return
        self.settings = replace(self.settings, active_controller_id=profile_id)
        try:
            save_desktop_settings(self.settings, self.settings_path)
        except OSError as exc:
            self.status.set(self._t("settings_error", error=exc))

    def _active_controller_label(self) -> str:
        if self.selected_profile_id is None:
            return self.live_profile_var.get() or "—"
        try:
            profile = self.registry.get(self.selected_profile_id)
        except Exception:
            return self.live_profile_var.get() or self.selected_profile_id
        return f"{profile.manufacturer} {profile.model}"

    def _apply_live_profile_state(self) -> None:
        supported = live_runtime_supported(self.selected_profile_id)
        if hasattr(self, "live_driver_badge"):
            self.live_driver_badge.configure(
                text=self._t("driver_ready" if supported else "driver_profile_only"),
                bg="#dff5fb" if supported else "#f2eee2",
                fg="#087d9d" if supported else "#705d1d",
            )
            self.live_driver_note.configure(
                text="" if supported else self._t("driver_profile_only_body")
            )
        if hasattr(self, "ec4_live_frame"):
            if supported:
                self.ec4_live_frame.grid()
            else:
                self.ec4_live_frame.grid_remove()
        if hasattr(self, "live_settings_ec4_frame") and _widget_exists(
            self.live_settings_ec4_frame
        ):
            if supported:
                self.live_settings_ec4_frame.grid()
            else:
                self.live_settings_ec4_frame.grid_remove()
            if self.live_settings_window is not None and _widget_exists(
                self.live_settings_window
            ):
                self.live_settings_window.geometry(
                    f"920x{640 if supported else 500}"
                )
        if not supported and not (self.runtime and self.runtime.running):
            self.runtime_status.set(
                self._t(
                    "runtime_driver_unavailable",
                    controller=self._active_controller_label(),
                )
            )
        elif not (self.runtime and self.runtime.running):
            self.runtime_status.set(self._t("runtime_not_started"))
        self._set_runtime_widget_states()
        self._build_menu()

    def _selected_profile(self):
        if self.selected_profile_id is None:
            messagebox.showwarning(
                self._t("controller_required"),
                self._t("select_controller"),
                parent=self.root,
            )
            return None
        return self.registry.get(self.selected_profile_id)

    def create_controller(self) -> None:
        self._show_controller_editor(default_controller_payload())

    def edit_controller(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        source = self.registry.source(profile.id).resolve()
        user_root = default_user_profile_dir().resolve()
        try:
            is_personal = source.is_relative_to(user_root)
        except ValueError:
            is_personal = False
        self._show_controller_editor(
            editable_controller_payload(profile, duplicate=not is_personal)
        )

    def _show_controller_editor(self, payload: dict[str, object]) -> None:
        current = getattr(self, "controller_editor", None)
        try:
            if current is not None and current.window.winfo_exists():
                current.window.destroy()
        except tk.TclError:
            pass

        def saved(profile_id: str) -> None:
            self.registry = ControllerRegistry()
            self.reload_catalog(preferred_profile_id=profile_id)

        def contribute(profile_id: str) -> None:
            saved(profile_id)
            self.root.after_idle(lambda: self.contribute_controller(profile_id))

        self.controller_editor = ControllerEditorDialog(
            self.root,
            translator=self._t,
            payload=payload,
            on_saved=saved,
            on_contribute=contribute,
            icon_path=PRODUCT_ICON_PATH,
        )

    def import_controller(self) -> None:
        source = filedialog.askopenfilename(
            parent=self.root,
            title=self._t("controller_import_title"),
            filetypes=(("JSON", "*.json"), (self._t("all_files"), "*.*")),
        )
        if not source:
            return
        try:
            profile = ControllerRegistry.load_file(Path(source))
            payload = editable_controller_payload(profile, duplicate=False)
            destination = default_user_profile_dir() / f"{profile.id}.json"
            replace_file = destination.exists() and messagebox.askyesno(
                self._t("controller_replace_title"),
                self._t("controller_replace_body", name=destination.name),
                parent=self.root,
            )
            if destination.exists() and not replace_file:
                return
            result = save_user_controller_profile(payload, replace=replace_file)
            self.registry = ControllerRegistry()
            self.reload_catalog(preferred_profile_id=result.profile.id)
        except Exception as exc:
            messagebox.showerror(
                self._t("controller_invalid_title"), str(exc), parent=self.root
            )
            return
        messagebox.showinfo(
            self._t("controller_imported_title"),
            self._t(
                "controller_imported_body",
                controller=result.profile.display_name,
                path=result.path,
            ),
            parent=self.root,
        )

    def contribute_controller(self, profile_id: str | None = None) -> None:
        if profile_id is not None:
            self.selected_profile_id = profile_id
        profile = self._selected_profile()
        if profile is None:
            return
        clipboard_fallback = False
        try:
            source = self.registry.source(profile.id)
            contribution, payload = validated_controller_payload(
                source,
                expected_profile_id=profile.id,
            )
            url = controller_submission_url(contribution, payload=payload)
            if len(url) > 30_000:
                clipboard_fallback = True
                self.root.clipboard_clear()
                self.root.clipboard_append(payload)
                self.root.update_idletasks()
                url = controller_submission_url(contribution)
            if not webbrowser.open(url):
                raise OSError("le navigateur n’a pas accepté le lien GitHub")
        except Exception as exc:
            messagebox.showerror(
                self._t("contribute_controller_error"),
                str(exc),
                parent=self.root,
            )
            return
        messagebox.showinfo(
            self._t("contribute_controller_title"),
            self._t(
                (
                    "contribute_controller_ready_clipboard"
                    if clipboard_fallback
                    else "contribute_controller_ready"
                ),
                controller=contribution.display_name,
            ),
            parent=self.root,
        )

    def export_controller(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        initial = _safe_filename(f"Controller-Studio-{profile.manufacturer}-{profile.model}")
        destination = filedialog.asksaveasfilename(
            parent=self.root,
            title=self._t("export_title"),
            defaultextension=".ctrl2",
            filetypes=((self._t("controller_file_type"), "*.ctrl2"),),
            initialfile=f"{initial}.ctrl2",
        )
        if not destination:
            return
        path = Path(destination)
        replace_file = path.exists() and messagebox.askyesno(
            self._t("replace_file"),
            self._t("replace_file_body", name=path.name),
            parent=self.root,
        )
        if path.exists() and not replace_file:
            return
        try:
            result = export_liveprofessor_controller(
                profile, path, replace=replace_file
            )
        except Exception as exc:
            messagebox.showerror(self._t("export_error"), str(exc), parent=self.root)
            return
        self.status.set(self._t("controller_created_status", name=result.path.name))
        messagebox.showinfo(
            self._t("controller_created"),
            self._t(
                "export_details",
                path=result.path,
                rotaries=result.rotary_count,
                buttons=result.button_count,
                sha256=result.sha256,
            ),
            parent=self.root,
        )

    def prepare_automap(self) -> None:
        window = getattr(self, "automap_window", None)
        try:
            if window is not None and window.winfo_exists():
                window.deiconify()
                window.lift()
                window.focus_force()
                return
        except tk.TclError:
            pass

        window = tk.Toplevel(self.root)
        self.automap_window = window
        window.title(self._t("automap_title"))
        window.geometry("880x740")
        window.minsize(760, 620)
        window.transient(self.root)
        if PRODUCT_ICON_PATH.is_file():
            try:
                window.iconbitmap(default=str(PRODUCT_ICON_PATH))
            except tk.TclError:
                pass

        self.automap_project_var = tk.StringVar()
        self.automap_source_mode_var = tk.StringVar(value="file")
        self.automap_detection_var = tk.StringVar()
        self.automap_profile_var = tk.StringVar()
        self.automap_project_controller_var = tk.StringVar()
        self.automap_bank_mode_var = tk.StringVar(value="unibank")
        self.automap_scope_var = tk.StringVar(value="all")
        self.automap_status_var = tk.StringVar(value=self._t("automap_status_empty"))
        self._automap_inventory: ProjectInventory | None = None
        self._automap_plugin_vars = []
        self._automap_controller_by_label: dict[str, int | None] = {}

        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(9, weight=1)
        ttk.Label(
            frame,
            text=self._t("automap_intro"),
            wraplength=820,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 12))

        source_row = ttk.Frame(frame)
        source_row.grid(row=1, column=0, columnspan=3, sticky="ew")
        source_row.columnconfigure(3, weight=1)
        ttk.Label(source_row, text=self._t("automap_project")).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )
        ttk.Radiobutton(
            source_row,
            text=self._t("automap_current_project"),
            variable=self.automap_source_mode_var,
            value="current",
            command=lambda: self._set_automap_source_mode("current"),
        ).grid(row=0, column=1, sticky="w", padx=(0, 10))
        ttk.Radiobutton(
            source_row,
            text=self._t("automap_choose_project"),
            variable=self.automap_source_mode_var,
            value="file",
            command=lambda: self._set_automap_source_mode("file"),
        ).grid(row=0, column=2, sticky="w")
        ttk.Button(
            source_row,
            text=self._t("automap_detect"),
            command=lambda: self._set_automap_source_mode("current"),
        ).grid(row=0, column=4, sticky="e", padx=(8, 0))
        ttk.Label(
            source_row,
            textvariable=self.automap_detection_var,
            foreground="#476273",
            wraplength=800,
            justify="left",
        ).grid(row=1, column=0, columnspan=5, sticky="ew", pady=(4, 0))
        self.automap_project_entry = ttk.Entry(
            frame, textvariable=self.automap_project_var
        )
        self.automap_project_entry.grid(
            row=2, column=0, sticky="ew", pady=(4, 10)
        )
        self.automap_browse_button = ttk.Button(
            frame, text=self._t("automap_browse"), command=self._browse_automap_project
        )
        self.automap_browse_button.grid(
            row=2, column=1, padx=(8, 0), pady=(4, 10)
        )
        ttk.Button(
            frame, text=self._t("automap_analyze"), command=self._analyze_automap_project
        ).grid(row=2, column=2, padx=(8, 0), pady=(4, 10))

        choices = self.registry.all()
        self._automap_profile_by_label = {
            profile.display_name: profile for profile in choices
        }
        ttk.Label(frame, text=self._t("automap_controller_profile")).grid(
            row=3, column=0, sticky="w"
        )
        self.automap_profile_combo = ttk.Combobox(
            frame,
            textvariable=self.automap_profile_var,
            values=tuple(self._automap_profile_by_label),
            state="readonly",
        )
        self.automap_profile_combo.grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=(4, 10)
        )
        default_profile = next(
            (profile for profile in choices if profile.id == self.selected_profile_id),
            choices[0] if choices else None,
        )
        if default_profile is not None:
            self.automap_profile_var.set(default_profile.display_name)
        self.automap_profile_combo.bind(
            "<<ComboboxSelected>>", lambda _event: self._update_automap_bank_options()
        )

        options = ttk.Frame(frame)
        options.grid(row=5, column=0, columnspan=3, sticky="ew")
        options.columnconfigure(0, weight=1)
        options.columnconfigure(1, weight=1)
        bank_frame = ttk.LabelFrame(
            options, text=self._t("automap_bank_mode"), padding=8
        )
        bank_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.automap_unibank_radio = ttk.Radiobutton(
            bank_frame,
            variable=self.automap_bank_mode_var,
            value="unibank",
        )
        self.automap_unibank_radio.pack(anchor="w")
        self.automap_fullbank_radio = ttk.Radiobutton(
            bank_frame,
            variable=self.automap_bank_mode_var,
            value="fullbank",
        )
        self.automap_fullbank_radio.pack(anchor="w", pady=(4, 0))

        scope_frame = ttk.LabelFrame(options, text=self._t("automap_scope"), padding=8)
        scope_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ttk.Radiobutton(
            scope_frame,
            text=self._t("automap_all_plugins"),
            variable=self.automap_scope_var,
            value="all",
            command=self._update_automap_plugin_states,
        ).pack(anchor="w")
        ttk.Radiobutton(
            scope_frame,
            text=self._t("automap_selected_plugins"),
            variable=self.automap_scope_var,
            value="selected",
            command=self._update_automap_plugin_states,
        ).pack(anchor="w", pady=(4, 0))

        ttk.Label(frame, text=self._t("automap_project_controller")).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )
        self.automap_project_controller_combo = ttk.Combobox(
            frame,
            textvariable=self.automap_project_controller_var,
            state="readonly",
        )
        self.automap_project_controller_combo.grid(
            row=7, column=0, columnspan=3, sticky="ew", pady=(4, 10)
        )

        toolbar = ttk.Frame(frame)
        toolbar.grid(row=8, column=0, columnspan=3, sticky="ew")
        ttk.Label(toolbar, text=self._t("automap_plugin_list")).pack(side="left")
        self.automap_select_none_button = ttk.Button(
            toolbar,
            text=self._t("automap_select_none"),
            command=lambda: self._set_automap_plugins(False),
        )
        self.automap_select_none_button.pack(side="right")
        self.automap_select_all_button = ttk.Button(
            toolbar,
            text=self._t("automap_select_all"),
            command=lambda: self._set_automap_plugins(True),
        )
        self.automap_select_all_button.pack(side="right", padx=(0, 6))

        plugin_box = ttk.Frame(frame, relief="sunken", borderwidth=1)
        plugin_box.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(4, 8))
        plugin_box.columnconfigure(0, weight=1)
        plugin_box.rowconfigure(0, weight=1)
        self.automap_plugin_canvas = tk.Canvas(
            plugin_box, highlightthickness=0, height=210
        )
        plugin_scroll = ttk.Scrollbar(
            plugin_box, orient="vertical", command=self.automap_plugin_canvas.yview
        )
        self.automap_plugin_canvas.configure(yscrollcommand=plugin_scroll.set)
        self.automap_plugin_canvas.grid(row=0, column=0, sticky="nsew")
        plugin_scroll.grid(row=0, column=1, sticky="ns")
        self.automap_plugin_frame = ttk.Frame(self.automap_plugin_canvas)
        self._automap_canvas_window = self.automap_plugin_canvas.create_window(
            (0, 0), window=self.automap_plugin_frame, anchor="nw"
        )
        self.automap_plugin_frame.bind(
            "<Configure>",
            lambda _event: self.automap_plugin_canvas.configure(
                scrollregion=self.automap_plugin_canvas.bbox("all")
            ),
        )
        self.automap_plugin_canvas.bind(
            "<Configure>",
            lambda event: self.automap_plugin_canvas.itemconfigure(
                self._automap_canvas_window, width=event.width
            ),
        )

        ttk.Label(
            frame,
            textvariable=self.automap_status_var,
            wraplength=820,
            justify="left",
        ).grid(row=10, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self.automap_create_button = tk.Button(
            frame,
            text=self._t("automap_create"),
            command=self._create_automap_copy,
            state="disabled",
            bg="#087d9d",
            fg="#ffffff",
            activebackground="#0aa1c9",
            activeforeground="#ffffff",
            disabledforeground="#b8c5cb",
            relief="flat",
            borderwidth=0,
            padx=16,
            pady=7,
            font=("Segoe UI Semibold", 10),
            cursor="hand2",
        )
        self.automap_create_button.grid(row=10, column=2, sticky="e")
        self._update_automap_bank_options()
        self._update_automap_plugin_states()
        window.after_idle(lambda: self._detect_current_automap_project(silent=True))

        def close_window() -> None:
            self.automap_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_window)

    def _selected_automap_profile(self):
        return self._automap_profile_by_label.get(self.automap_profile_var.get())

    def _update_automap_bank_options(self) -> None:
        profile = self._selected_automap_profile()
        if profile is None:
            return
        unibank = bank_rotary_count(profile)
        fullbank = logical_rotary_count(profile)
        self.automap_unibank_radio.configure(
            text=self._t("automap_unibank", count=unibank)
        )
        self.automap_fullbank_radio.configure(
            text=self._t("automap_fullbank", count=fullbank),
            state="normal" if fullbank > unibank else "disabled",
        )
        if fullbank <= unibank:
            self.automap_bank_mode_var.set("unibank")

    def _browse_automap_project(self) -> None:
        self._set_automap_source_mode("file", detect=False)
        selected = filedialog.askopenfilename(
            parent=self.automap_window or self.root,
            title=self._t("source_title"),
            filetypes=((self._t("project_file_type"), "*.rack2"),),
        )
        if selected:
            self.automap_project_var.set(selected)
            self._analyze_automap_project()

    def _set_automap_source_mode(self, mode: str, *, detect: bool = True) -> None:
        if mode not in {"current", "file"}:
            return
        self.automap_source_mode_var.set(mode)
        current = mode == "current"
        self.automap_project_entry.configure(
            state="readonly" if current else "normal"
        )
        self.automap_browse_button.configure(
            state="disabled" if current else "normal"
        )
        if current and detect:
            self._detect_current_automap_project(silent=False)
        elif not current:
            self.automap_detection_var.set("")

    def _detect_current_automap_project(self, *, silent: bool) -> bool:
        session = detect_liveprofessor_session()
        if session.project_path is not None:
            self.automap_source_mode_var.set("current")
            self.automap_project_var.set(str(session.project_path))
            self.automap_detection_var.set(
                self._t("automap_detected", path=session.project_path)
            )
            self.automap_project_entry.configure(state="readonly")
            self.automap_browse_button.configure(state="disabled")
            return True
        if session.running:
            message = self._t("automap_not_detected")
        else:
            message = self._t("automap_not_running")
        if not silent or self.automap_source_mode_var.get() == "current":
            self.automap_detection_var.set(message)
        if silent:
            self.automap_source_mode_var.set("file")
            self.automap_project_entry.configure(state="normal")
            self.automap_browse_button.configure(state="normal")
        return False

    def _analyze_automap_project(self) -> None:
        if self.automap_source_mode_var.get() == "current":
            if not self._detect_current_automap_project(silent=False):
                return
            if not messagebox.askokcancel(
                self._t("automap_save_current_title"),
                self._t(
                    "automap_save_current_body",
                    path=self.automap_project_var.get(),
                ),
                parent=self.automap_window or self.root,
            ):
                return
        try:
            inventory = inspect_project(
                Path(self.automap_project_var.get()),
                controller_template=default_companion_template(),
            )
        except Exception as exc:
            self._automap_inventory = None
            self.automap_create_button.configure(state="disabled")
            messagebox.showerror(
                self._t("preparation_error"),
                str(exc),
                parent=self.automap_window or self.root,
            )
            return

        self._automap_inventory = inventory
        existing = tuple(item for item in inventory.controllers if not item.is_embedded)
        self._automap_controller_by_label = {}
        for controller in existing:
            label = self._t(
                "automap_existing_controller",
                name=controller.name,
                rotaries=controller.rotary_count,
                uid=controller.controller_uid,
            )
            self._automap_controller_by_label[label] = controller.controller_uid
        new_label = self._t("automap_new_controller")
        self._automap_controller_by_label[new_label] = None
        controller_labels = tuple(self._automap_controller_by_label)
        self.automap_project_controller_combo.configure(values=controller_labels)
        self.automap_project_controller_var.set(controller_labels[0])

        for child in self.automap_plugin_frame.winfo_children():
            child.destroy()
        self._automap_plugin_vars = []
        language = self.language_var.get()
        for row, plugin in enumerate(inventory.plugins):
            selected = tk.BooleanVar(value=True)
            unit = "paramètres" if language == "fr" else "parameters"
            label = f"{plugin.name} — {plugin.parameter_count} {unit} [#{plugin.plugin_uid}]"
            check = ttk.Checkbutton(
                self.automap_plugin_frame,
                text=label,
                variable=selected,
            )
            check.grid(row=row, column=0, sticky="w", padx=8, pady=2)
            self._automap_plugin_vars.append((plugin, selected, check))
        status = self._t(
            "automap_status_inventory",
            plugins=len(inventory.plugins),
            controllers=len(existing),
        )
        if inventory.skipped_plugins:
            status += self._t(
                "automap_status_skipped", count=len(inventory.skipped_plugins)
            )
        self.automap_status_var.set(status)
        self.automap_create_button.configure(state="normal")
        self._update_automap_plugin_states()

    def _update_automap_plugin_states(self) -> None:
        selected_scope = self.automap_scope_var.get() == "selected"
        state = "normal" if selected_scope else "disabled"
        for _plugin, variable, check in getattr(self, "_automap_plugin_vars", []):
            if not selected_scope:
                variable.set(True)
            check.configure(state=state)
        if hasattr(self, "automap_select_all_button"):
            self.automap_select_all_button.configure(state=state)
            self.automap_select_none_button.configure(state=state)

    def _set_automap_plugins(self, selected: bool) -> None:
        self.automap_scope_var.set("selected")
        for _plugin, variable, _check in self._automap_plugin_vars:
            variable.set(selected)
        self._update_automap_plugin_states()

    def _create_automap_copy(self) -> None:
        inventory = self._automap_inventory
        profile = self._selected_automap_profile()
        if inventory is None or profile is None:
            return
        plugin_uids = None
        if self.automap_scope_var.get() == "selected":
            plugin_uids = tuple(
                plugin.plugin_uid
                for plugin, selected, _check in self._automap_plugin_vars
                if selected.get()
            )
            if not plugin_uids:
                messagebox.showwarning(
                    self._t("automap_no_plugin_title"),
                    self._t("automap_no_plugin_body"),
                    parent=self.automap_window or self.root,
                )
                return

        selected_controller_uid = self._automap_controller_by_label.get(
            self.automap_project_controller_var.get()
        )
        existing = tuple(item for item in inventory.controllers if not item.is_embedded)
        embed_new = selected_controller_uid is None
        if embed_new and existing and not messagebox.askyesno(
            self._t("automap_duplicate_title"),
            self._t("automap_duplicate_warning"),
            parent=self.automap_window or self.root,
        ):
            return

        destination_name = filedialog.asksaveasfilename(
            parent=self.automap_window or self.root,
            title=self._t("destination_title"),
            defaultextension=".rack2",
            filetypes=((self._t("project_file_type"), "*.rack2"),),
            initialdir=str(inventory.path.parent),
            initialfile=f"{inventory.path.stem}-Controller-Studio-AutoMap.rack2",
        )
        if not destination_name:
            return
        destination = Path(destination_name)
        if inventory.path.resolve() == destination.resolve():
            messagebox.showerror(
                self._t("destination_forbidden"),
                self._t("destination_forbidden_body"),
                parent=self.automap_window or self.root,
            )
            return
        controller = destination.with_suffix(".ctrl2")
        replace_project = destination.exists() and messagebox.askyesno(
            self._t("replace_copy"),
            self._t("replace_copy_body", name=destination.name),
            parent=self.automap_window or self.root,
        )
        if destination.exists() and not replace_project:
            return
        replace_controller = controller.exists() and messagebox.askyesno(
            self._t("replace_controller"),
            self._t("replace_controller_body", name=controller.name),
            parent=self.automap_window or self.root,
        )
        if controller.exists() and not replace_controller:
            return

        target_count = (
            logical_rotary_count(profile)
            if self.automap_bank_mode_var.get() == "fullbank"
            else bank_rotary_count(profile)
        )
        self.automap_create_button.configure(state="disabled")
        self.automap_status_var.set(self._t("automap_running"))

        def worker() -> None:
            try:
                result = prepare_liveprofessor_project(
                    profile,
                    inventory.path,
                    destination,
                    controller,
                    plugin_uids=plugin_uids,
                    project_controller_uid=(
                        None if embed_new else selected_controller_uid
                    ),
                    embed_new_controller=embed_new,
                    target_rotary_count=target_count,
                    replace_project=replace_project,
                    replace_controller=replace_controller,
                    plugin_profiles=PluginProfileRegistry().all(),
                )
            except Exception as exc:
                error = str(exc)
                self.root.after(0, lambda: self._finish_automap_job(None, error))
                return
            self.root.after(0, lambda: self._finish_automap_job(result, None))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_automap_job(self, result, error: str | None) -> None:
        try:
            if self.automap_window is not None and self.automap_window.winfo_exists():
                self.automap_create_button.configure(state="normal")
        except tk.TclError:
            pass
        parent = self.automap_window or self.root
        if error is not None:
            self.automap_status_var.set(error)
            messagebox.showerror(self._t("preparation_error"), error, parent=parent)
            return
        self.automap_status_var.set(
            self._t("automap_created_status", name=result.automap.output_path.name)
        )
        details = self._t(
            "automap_complete_body",
            sha256=result.source_sha256,
            project=result.automap.output_path,
            controller=result.controller.path,
            plugins=len(result.automap.mapped_plugins),
            mappings=result.automap.mapped_rotaries,
        )
        open_now = messagebox.askyesno(
            self._t("automap_open_title"),
            f"{details}\n\n{self._t('automap_open_question')}",
            parent=parent,
        )
        if open_now:
            try:
                os.startfile(str(result.automap.output_path))
            except OSError as exc:
                messagebox.showerror(
                    self._t("automap_open_title"),
                    self._t("automap_open_error", error=exc),
                    parent=parent,
                )

    def run_library_update(self, apply: bool) -> None:
        if apply and not messagebox.askyesno(
            self._t("install_confirm"),
            self._t("install_confirm_body"),
            parent=self.root,
        ):
            return
        for button in self._library_buttons:
            button.configure(state="disabled")
        self.status.set(
            self._t("installing_library") if apply else self._t("reading_manifest")
        )

        def worker() -> None:
            try:
                result = update_library(GitHubLibraryClient(), apply=apply)
                changes = result.preview.changes
                if changes:
                    details = "\n".join(
                        f"{self._change_kind(item.kind)} — "
                        f"{self._collection_name(item.collection)} {item.id}: "
                        f"{item.current_version or '—'} → {item.remote_version or '—'}"
                        for item in changes
                    )
                else:
                    details = self._t("library_current")
                title = (
                    self._t("library_installed")
                    if result.applied and changes
                    else self._t("preview")
                )
                self.root.after(
                    0, lambda: self._finish_library_job(title, details, None)
                )
            except Exception as exc:
                error = str(exc)
                self.root.after(
                    0,
                    lambda: self._finish_library_job(
                        self._t("update_error"), "", error
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _change_kind(self, kind: str) -> str:
        return self._t(f"change_{kind}")

    def _collection_name(self, collection: str) -> str:
        return self._t(f"collection_{collection}")

    def _finish_library_job(
        self, title: str, details: str, error: str | None
    ) -> None:
        for button in self._library_buttons:
            button.configure(state="normal")
        if error is not None:
            self.status.set(self._t("library_unchanged", error=error))
            messagebox.showerror(title, error, parent=self.root)
            return
        self.status.set(title)
        messagebox.showinfo(title, details, parent=self.root)
        self.registry = ControllerRegistry()
        self.reload_catalog()

    def _tray_commands(self) -> tuple[TrayCommand, ...]:
        running = bool(self.runtime and self.runtime.running)
        supported = live_runtime_supported(self.selected_profile_id)
        return (
            TrayCommand(
                "start",
                self._t("tray_start"),
                self.start_runtime,
                enabled=supported and not running,
            ),
            TrayCommand("stop", self._t("tray_stop"), self.stop_runtime, enabled=running),
            TrayCommand(
                "restart",
                self._t("tray_restart"),
                self.restart_runtime,
                enabled=supported,
            ),
            TrayCommand("log", self._t("tray_log"), self.show_runtime_log),
            TrayCommand("update", self._t("tray_update"), self._tray_library_preview),
        )

    def _tray_library_preview(self) -> None:
        self.tray.restore()
        self.run_library_update(False)

    def _runtime_config_from_form(self) -> BridgeConfig:
        config = replace(
            self.runtime_config,
            midi_input=self.midi_input_var.get().strip(),
            midi_output=self.midi_output_var.get().strip(),
            liveprofessor_host=self.liveprofessor_host_var.get().strip(),
            liveprofessor_port=int(self.liveprofessor_port_var.get().strip()),
            feedback_host="127.0.0.1",
            feedback_port=int(self.feedback_port_var.get().strip()),
            target_setup=int(self.target_setup_var.get().strip()),
            target_group=int(self.target_group_var.get().strip()),
            display_enabled=bool(self.display_enabled_var.get()),
            persistent_parameter_display=bool(self.persistent_display_var.get()),
            parameter_overlay_interval_ms=int(
                self.parameter_overlay_interval_var.get().strip()
            ),
            companion_refresh_delay_ms=int(
                self.companion_refresh_delay_var.get().strip()
            ),
            name_refresh_delay_ms=int(self.name_refresh_delay_var.get().strip()),
            feedback_confirm_timeout_ms=int(self.feedback_timeout_var.get().strip()),
            overlay_display_duration_ms=int(
                self.overlay_display_duration_var.get().strip()
            ),
            ui_language=self.language_var.get(),
        )
        config.validate()
        return config

    def _apply_runtime_config_to_form(self, config: BridgeConfig) -> None:
        self.runtime_config = config
        self.midi_input_var.set(config.midi_input)
        self.midi_output_var.set(config.midi_output)
        self.liveprofessor_host_var.set(config.liveprofessor_host)
        self.liveprofessor_port_var.set(str(config.liveprofessor_port))
        self.feedback_port_var.set(str(config.feedback_port))
        self.target_setup_var.set(str(config.target_setup))
        self.target_group_var.set(str(config.target_group))
        self.display_enabled_var.set(config.display_enabled)
        self.persistent_display_var.set(config.persistent_parameter_display)
        self.parameter_overlay_interval_var.set(str(config.parameter_overlay_interval_ms))
        self.companion_refresh_delay_var.set(str(config.companion_refresh_delay_ms))
        self.name_refresh_delay_var.set(str(config.name_refresh_delay_ms))
        self.feedback_timeout_var.set(str(config.feedback_confirm_timeout_ms))
        self.overlay_display_duration_var.set(str(config.overlay_display_duration_ms))

    def refresh_midi_ports(self) -> None:
        try:
            inputs = input_names()
            outputs = output_names()
        except Exception as exc:
            self._append_runtime_log(f"Inventaire MIDI impossible: {exc}")
            return
        configured_input = self.midi_input_var.get().strip()
        configured_output = self.midi_output_var.get().strip()
        if configured_input and configured_input not in inputs:
            inputs.append(configured_input)
        if configured_output and configured_output not in outputs:
            outputs.append(configured_output)
        if hasattr(self, "midi_input_combo"):
            try:
                if self.midi_input_combo.winfo_exists():
                    self.midi_input_combo.configure(values=tuple(inputs))
                    self.midi_output_combo.configure(values=tuple(outputs))
            except tk.TclError:
                pass
        self._append_runtime_log(
            f"Ports MIDI: {len(inputs)} entree(s), {len(outputs)} sortie(s)"
        )

    def import_legacy_runtime_config(self) -> None:
        source = legacy_config_path()
        if not source.is_file():
            selected = filedialog.askopenfilename(
                parent=self.root,
                title=self._t("import_legacy_config"),
                filetypes=(
                    (self._t("runtime_config_file_type"), "*.json"),
                    ("JSON", "*.json"),
                ),
            )
            if not selected:
                return
            source = Path(selected)
        was_running = bool(self.runtime and self.runtime.running)
        try:
            imported = load_config(source)
            imported.ui_language = self.language_var.get()
            if was_running:
                self.stop_runtime()
            save_config(imported, self.runtime_config_path)
            self._apply_runtime_config_to_form(imported)
            self.refresh_midi_ports()
            if was_running:
                self.start_runtime()
        except Exception as exc:
            messagebox.showerror(
                self._t("runtime_config_import_error"), str(exc), parent=self.root
            )
            return
        details = self._t("runtime_config_imported", path=source)
        self._append_runtime_log(details)
        self.status.set(details)
        messagebox.showinfo(
            self._t("import_legacy_config"), details, parent=self.root
        )

    def _queue_runtime_snapshot(self, snapshot: BridgeSnapshot) -> None:
        self._runtime_events.put(("snapshot", snapshot))

    def _queue_runtime_log(self, message: str) -> None:
        self._runtime_events.put(("log", str(message)))

    def _poll_runtime_events(self) -> None:
        self._runtime_poll_after_id = None
        if self._closing:
            return
        while True:
            try:
                event, payload = self._runtime_events.get_nowait()
            except queue.Empty:
                break
            try:
                if event == "snapshot" and isinstance(payload, BridgeSnapshot):
                    self._apply_runtime_snapshot(payload)
                elif event == "log":
                    self._append_runtime_log(str(payload))
                elif event == "midi_learn" and isinstance(payload, tuple):
                    self._capture_midi_learn(*payload)
            except Exception as exc:
                self._append_runtime_log(f"Evenement temps reel ignore: {exc}")
                if event == "midi_learn":
                    self._cancel_midi_learn()
        self._runtime_poll_after_id = self.root.after(100, self._poll_runtime_events)

    def _translated_runtime_state(self, state: str) -> str:
        if self.language_var.get() != "en":
            return state
        exact = {
            "Arrete": "Stopped",
            "Recherche du Faderfox EC4": "Searching for Faderfox EC4",
            "Connecte": "Connected",
            "EC4 deconnecte - nouvelle tentative automatique": (
                "EC4 disconnected — automatic retry"
            ),
            "Reconnexion EC4 demandee": "EC4 reconnection requested",
        }
        if state in exact:
            return exact[state]
        if state.startswith("Port OSC indisponible:"):
            return "OSC port unavailable:" + state.partition(":")[2]
        return state

    def _apply_runtime_snapshot(self, snapshot: BridgeSnapshot) -> None:
        running_changed = snapshot.running != self.runtime_snapshot.running
        self.runtime_snapshot = snapshot
        setup = (
            snapshot.setup + 1
            if snapshot.setup is not None
            else self._t("setup_unknown")
        )
        group = (
            snapshot.group + 1
            if snapshot.group is not None
            else self._t("setup_unknown")
        )
        self.runtime_status.set(
            self._t(
                "runtime_snapshot",
                state=self._translated_runtime_state(snapshot.status),
                midi=self._t(
                    "midi_connected" if snapshot.midi_connected else "midi_disconnected"
                ),
                bank=snapshot.active_bank + 1,
                banks=snapshot.bank_count,
                setup=setup,
                group=group,
            )
        )
        self.runtime_bank.set(f"{snapshot.active_bank + 1} / {snapshot.bank_count}")
        self._set_runtime_widget_states()
        if running_changed:
            self._build_menu()

    def _append_runtime_log(self, message: str) -> None:
        line = f"{time.strftime('%H:%M:%S')}  {message}\n"
        self._runtime_log_lines.append(line)
        self.runtime_last_event.set(message)
        if len(self._runtime_log_lines) > 2000:
            del self._runtime_log_lines[:500]
        if hasattr(self, "runtime_log_text"):
            try:
                if self.runtime_log_text.winfo_exists():
                    self.runtime_log_text.configure(state="normal")
                    self.runtime_log_text.insert("end", line)
                    self.runtime_log_text.see("end")
                    self.runtime_log_text.configure(state="disabled")
            except tk.TclError:
                pass

    def _render_runtime_log(self) -> None:
        if not hasattr(self, "runtime_log_text"):
            return
        self.runtime_log_text.configure(state="normal")
        self.runtime_log_text.delete("1.0", "end")
        self.runtime_log_text.insert("end", "".join(self._runtime_log_lines))
        self.runtime_log_text.see("end")
        self.runtime_log_text.configure(state="disabled")

    def _set_runtime_widget_states(self) -> None:
        if not hasattr(self, "runtime_start_button"):
            return
        running = bool(self.runtime and self.runtime.running)
        supported = live_runtime_supported(self.selected_profile_id)
        self.runtime_start_button.configure(
            state="normal" if supported and not running else "disabled"
        )
        self.runtime_stop_button.configure(state="normal" if running else "disabled")
        self.runtime_restart_button.configure(
            state="normal" if supported else "disabled"
        )
        for button in self.runtime_action_buttons:
            button.configure(state="normal" if supported and running else "disabled")
        for button in self.runtime_settings_action_buttons:
            try:
                button.configure(
                    state="normal" if supported and running else "disabled"
                )
            except tk.TclError:
                pass
        state = "normal" if supported and running else "disabled"
        self.previous_bank_button.configure(state=state)
        self.next_bank_button.configure(state=state)

    def start_runtime(self, *, interactive: bool = True) -> bool:
        if self.runtime and self.runtime.running:
            return True
        if not live_runtime_supported(self.selected_profile_id):
            details = self._t(
                "runtime_driver_unavailable",
                controller=self._active_controller_label(),
            )
            self.runtime_status.set(details)
            self._append_runtime_log(details)
            if interactive:
                messagebox.showinfo(
                    self._t("live_title"),
                    details,
                    parent=self.root,
                )
            return False
        self.runtime_status.set(self._t("runtime_starting"))
        try:
            config = self._runtime_config_from_form()
            save_config(config, self.runtime_config_path)
            self.log_path = configure_runtime_logging(config.log_level)
            active_profile = self.registry.get(self.selected_profile_id)
            runtime = EC4LiveProfessorRuntime(
                config,
                status_callback=self._queue_runtime_snapshot,
                log_callback=self._queue_runtime_log,
                shortcut_bindings=effective_shortcuts(
                    active_profile,
                    self.settings.shortcuts_by_controller,
                ),
            )
            self.runtime_config = config
            self.runtime = runtime
            runtime.start()
            self._apply_runtime_snapshot(runtime.snapshot())
            self.status.set(self._t("runtime_running"))
            return True
        except Exception as exc:
            runtime = self.runtime
            self.runtime = None
            if runtime is not None:
                try:
                    runtime.stop()
                except Exception:
                    pass
            self.runtime_status.set(str(exc))
            self._append_runtime_log(f"Demarrage impossible: {exc}")
            self._set_runtime_widget_states()
            if interactive:
                messagebox.showerror(self._t("runtime_error"), str(exc), parent=self.root)
            return False

    def stop_runtime(self) -> None:
        runtime = self.runtime
        if runtime is None:
            return
        self._cancel_midi_learn()
        try:
            runtime.stop()
            self._apply_runtime_snapshot(runtime.snapshot())
        except Exception as exc:
            self._append_runtime_log(f"Arret incomplet: {exc}")
        finally:
            self.runtime = None
            self.runtime_status.set(self._t("runtime_not_started"))
            self._set_runtime_widget_states()
            if not self._closing:
                self._build_menu()
                self.status.set(self._t("runtime_stopped"))

    def restart_runtime(self) -> None:
        self.stop_runtime()
        self.start_runtime()

    def _active_runtime(self) -> EC4LiveProfessorRuntime | None:
        if self.runtime is None or not self.runtime.running:
            self.runtime_status.set(self._t("runtime_not_started"))
            return None
        return self.runtime

    def reconnect_ec4(self) -> None:
        runtime = self._active_runtime()
        if runtime:
            runtime.reconnect_midi()

    def request_setup_state(self) -> None:
        runtime = self._active_runtime()
        if runtime:
            runtime.request_setup_state()

    def refresh_companion(self) -> None:
        runtime = self._active_runtime()
        if runtime:
            runtime.refresh_companion()

    def test_ec4_display(self) -> None:
        runtime = self._active_runtime()
        if runtime:
            runtime.demo_display()

    def change_bank(self, delta: int) -> None:
        runtime = self._active_runtime()
        if runtime:
            runtime.change_bank(delta)

    def use_current_target(self) -> None:
        runtime = self._active_runtime()
        if runtime is None:
            messagebox.showinfo(
                self._t("live_title"), self._t("runtime_not_started"), parent=self.root
            )
            return
        snapshot = runtime.snapshot()
        if snapshot.setup is None or snapshot.group is None:
            messagebox.showinfo(
                self._t("unknown_state_title"),
                self._t("unknown_state_message"),
                parent=self.root,
            )
            return
        setup, group = snapshot.setup + 1, snapshot.group + 1
        self.target_setup_var.set(str(setup))
        self.target_group_var.set(str(group))
        try:
            config = self._runtime_config_from_form()
            save_config(config, self.runtime_config_path)
            self.runtime_config = config
            runtime.set_target(setup, group)
        except Exception as exc:
            messagebox.showerror(self._t("runtime_error"), str(exc), parent=self.root)
            return
        self._update_mapping_status()
        self._append_runtime_log(
            f"Zone EC4 enregistree: setup {setup}, groupe {group}"
        )

    def _mapping_key(self) -> str:
        return f"{int(self.target_setup_var.get())}:{int(self.target_group_var.get())}"

    def _update_mapping_status(self) -> None:
        try:
            mapping = self.runtime_config.encoder_mappings.get(self._mapping_key())
        except (TypeError, ValueError):
            mapping = None
        self.learn_status.set(
            self._t("learn_saved_label" if mapping and len(mapping) == 16 else "learn_default_label")
        )

    def toggle_midi_learn(self) -> None:
        if self._learning:
            self._cancel_midi_learn()
            return
        runtime = self._active_runtime()
        if runtime is None:
            messagebox.showinfo(
                self._t("live_title"), self._t("runtime_not_started"), parent=self.root
            )
            return
        snapshot = runtime.snapshot()
        target = (int(self.target_setup_var.get()), int(self.target_group_var.get()))
        current = (
            snapshot.setup + 1 if snapshot.setup is not None else None,
            snapshot.group + 1 if snapshot.group is not None else None,
        )
        if current != target:
            messagebox.showinfo(
                self._t("wrong_zone_title"),
                self._t("wrong_zone_message", setup=target[0], group=target[1]),
                parent=self.root,
            )
            return
        try:
            config = self._runtime_config_from_form()
            config.encoder_mappings = dict(config.encoder_mappings)
            save_config(config, self.runtime_config_path)
            self.runtime_config = config
            runtime.config.encoder_mappings = config.encoder_mappings
            runtime.set_target(*target)
        except Exception as exc:
            messagebox.showerror(self._t("runtime_error"), str(exc), parent=self.root)
            return
        self._learning = True
        self._learn_controls = []
        self._learn_pushes = []
        self._learn_phase = "cc"
        self.learn_button.configure(text=self._t("learn_cancel"))
        self.learn_status.set(self._t("learning_progress"))
        runtime.set_midi_learn_callback(self._queue_midi_learn)
        self._append_runtime_log(
            "Apprentissage MIDI: rotatifs 1 a 16, puis push 1 a 16"
        )
        messagebox.showinfo(
            self._t("learn_progress_title"),
            self._t("learn_progress_message"),
            parent=self.root,
        )

    def _queue_midi_learn(
        self, kind: str, channel: int, identifier: int, value: int
    ) -> bool:
        self._runtime_events.put(
            ("midi_learn", (kind, int(channel), int(identifier), int(value)))
        )
        return True

    def _capture_midi_learn(
        self, kind: str, channel: int, identifier: int, _value: int
    ) -> None:
        if not self._learning:
            return
        if self._learn_phase == "cc" and kind != "cc":
            return
        if self._learn_phase == "note" and kind != "note":
            return
        learned = self._learn_controls if self._learn_phase == "cc" else self._learn_pushes
        address = (channel, identifier)
        if address in learned:
            return
        learned.append(address)
        number = len(learned)
        label = "CC" if self._learn_phase == "cc" else "Push"
        self._append_runtime_log(
            f"{label} {number}: canal {channel + 1}, numero {identifier}"
        )
        if number < 16:
            key = "learn_rotary_prompt" if self._learn_phase == "cc" else "learn_push_prompt"
            self.learn_status.set(f"{self._t(key, index=number + 1)} ({number}/16)")
            return
        if self._learn_phase == "cc":
            self._learn_phase = "note"
            self.learn_status.set(self._t("learn_push_prompt", index=1) + " (0/16)")
            messagebox.showinfo(
                self._t("learn_phase2_title"),
                self._t("learn_phase2_message"),
                parent=self.root,
            )
            return

        mapping = [
            {
                "channel": rotary_channel,
                "control": rotary_control,
                "push_channel": push_channel,
                "push_note": push_note,
            }
            for (rotary_channel, rotary_control), (push_channel, push_note) in zip(
                self._learn_controls, self._learn_pushes
            )
        ]
        key = self._mapping_key()
        config = self._runtime_config_from_form()
        config.encoder_mappings = dict(config.encoder_mappings)
        config.encoder_mappings[key] = mapping
        config.validate()
        save_config(config, self.runtime_config_path)
        self.runtime_config = config
        if self.runtime is not None:
            self.runtime.config.encoder_mappings = config.encoder_mappings
            self.runtime.set_midi_learn_callback(None)
            self.runtime.refresh_target()
        self._learning = False
        self._learn_phase = ""
        self.learn_button.configure(text=self._t("learn_button"))
        self.learn_status.set(self._t("learn_saved_label"))
        self._append_runtime_log(f"Mapping MIDI enregistre pour la zone {key}")
        messagebox.showinfo(
            self._t("learn_complete_title"),
            self._t("learn_complete_message"),
            parent=self.root,
        )

    def _cancel_midi_learn(self) -> None:
        if self.runtime is not None:
            self.runtime.set_midi_learn_callback(None)
        if self._learning:
            self._append_runtime_log("Apprentissage MIDI annule")
        self._learning = False
        self._learn_controls = []
        self._learn_pushes = []
        self._learn_phase = ""
        if hasattr(self, "learn_button"):
            self.learn_button.configure(text=self._t("learn_button"))
        self._update_mapping_status()

    def show_diagnostics(self) -> None:
        lines = [f"{FULL_PRODUCT_NAME} {__version__}"]
        try:
            config = self._runtime_config_from_form()
            config.validate()
            packet = encode_message("/silemio/diagnostic", [1, "ok"])
            assert decode_message(packet) == ("/silemio/diagnostic", [1, "ok"])
            assert len(main_display_message([f"P{i + 1}" for i in range(16)])) == 206
            assert len(parameter_grid_message([f"P{i + 1}" for i in range(16)])) == 257
            assert len(total_display_message(["SiLeMI/O", "Controller Studio"])) == 257
            lines.append("Configuration / OSC / SysEx: OK")
            lines.append("MIDI inputs: " + (", ".join(input_names()) or "none"))
            lines.append("MIDI outputs: " + (", ".join(output_names()) or "none"))
            snapshot = self.runtime.snapshot() if self.runtime else self.runtime_snapshot
            lines.append(
                f"Runtime: {snapshot.status}; bank {snapshot.active_bank + 1}/{snapshot.bank_count}"
            )
            lines.append(f"Log: {self.log_path}")
        except Exception as exc:
            lines.append(f"ERROR: {exc}")
        messagebox.showinfo(
            self._t("diagnostic_title"), "\n".join(lines), parent=self.root
        )

    def show_shortcuts(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return

        window = tk.Toplevel(self.root)
        window.title(
            self._t("shortcuts_title", controller=profile.display_name)
        )
        window.geometry("920x650")
        window.minsize(760, 520)
        window.transient(self.root)
        if PRODUCT_ICON_PATH.is_file():
            try:
                window.iconbitmap(default=str(PRODUCT_ICON_PATH))
            except tk.TclError:
                pass

        outer = ttk.Frame(window, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        ttk.Label(
            outer,
            text=self._t("shortcuts_intro"),
            wraplength=850,
            justify="left",
        ).grid(row=0, column=0, sticky="ew")
        if not live_runtime_supported(profile.id):
            ttk.Label(
                outer,
                text=self._t("shortcuts_driver_note"),
                wraplength=850,
                justify="left",
                foreground="#6a5a1a",
            ).grid(row=1, column=0, sticky="ew", pady=(6, 10))

        controls = tuple(control for control in profile.controls if control.supports_press)
        if not controls:
            ttk.Label(outer, text=self._t("shortcuts_no_controls")).grid(
                row=2, column=0, sticky="nw", pady=(20, 0)
            )
            ttk.Button(outer, text=self._t("close"), command=window.destroy).grid(
                row=3, column=0, sticky="e", pady=(12, 0)
            )
            return

        choices = (self._t("shortcut_none"),) + tuple(
            action.label(self.language_var.get()) for action in SHORTCUT_ACTIONS
        )
        action_by_label = {
            action.label(self.language_var.get()): action.id
            for action in SHORTCUT_ACTIONS
        }
        label_by_action = {
            action.id: action.label(self.language_var.get())
            for action in SHORTCUT_ACTIONS
        }
        current = effective_shortcuts(
            profile,
            self.settings.shortcuts_by_controller,
        )
        bindings = set(configurable_shortcut_bindings(profile))
        variables: dict[str, tk.StringVar] = {}

        box = ttk.Frame(outer, relief="sunken", borderwidth=1)
        box.grid(row=2, column=0, sticky="nsew", pady=(4, 10))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        canvas = tk.Canvas(box, highlightthickness=0)
        scrollbar = ttk.Scrollbar(box, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        table = ttk.Frame(canvas, padding=8)
        table_window = canvas.create_window((0, 0), window=table, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(table_window, width=event.width),
        )
        table.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        columns = ((None, self._t("shortcut_direct")),) + tuple(
            (modifier.id, modifier.id.replace("_", " ").title())
            for modifier in profile.modifiers
        )
        ttk.Label(
            table,
            text=self._t("shortcut_control"),
            font=("Segoe UI Semibold", 9),
        ).grid(row=0, column=0, sticky="w", padx=(2, 10), pady=(0, 6))
        table.columnconfigure(0, weight=1)
        for column, (_modifier_id, heading) in enumerate(columns, start=1):
            ttk.Label(
                table,
                text=heading,
                font=("Segoe UI Semibold", 9),
            ).grid(row=0, column=column, sticky="ew", padx=4, pady=(0, 6))
            table.columnconfigure(column, weight=2)

        for row, control in enumerate(controls, start=1):
            ttk.Label(
                table,
                text=control.id.replace("_", " ").title(),
            ).grid(row=row, column=0, sticky="w", padx=(2, 10), pady=3)
            for column, (modifier_id, _heading) in enumerate(columns, start=1):
                binding = shortcut_binding_key(control.id, modifier_id)
                if binding not in bindings:
                    continue
                selected = current.get(binding, "")
                variable = tk.StringVar(
                    value=label_by_action.get(selected, self._t("shortcut_none"))
                )
                variables[binding] = variable
                ttk.Combobox(
                    table,
                    textvariable=variable,
                    values=choices,
                    state="readonly",
                    width=28,
                ).grid(row=row, column=column, sticky="ew", padx=4, pady=3)

        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew")

        def reset_shortcuts() -> None:
            factory = default_shortcuts(profile)
            for binding, variable in variables.items():
                variable.set(
                    label_by_action.get(
                        factory.get(binding, ""), self._t("shortcut_none")
                    )
                )

        def save_shortcuts() -> None:
            controller_bindings = {
                binding: action_by_label.get(variable.get(), "")
                for binding, variable in variables.items()
            }
            all_shortcuts = {
                controller_id: dict(saved_bindings)
                for controller_id, saved_bindings in self.settings.shortcuts_by_controller.items()
            }
            all_shortcuts[profile.id] = controller_bindings
            self.settings = replace(
                self.settings,
                shortcuts_by_controller=all_shortcuts,
            )
            try:
                save_desktop_settings(self.settings, self.settings_path)
            except OSError as exc:
                messagebox.showerror(
                    self._t("shortcuts_title", controller=profile.display_name),
                    str(exc),
                    parent=window,
                )
                return
            if self.runtime is not None and profile.id == self.selected_profile_id:
                self.runtime.set_shortcut_bindings(
                    effective_shortcuts(profile, all_shortcuts)
                )
            messagebox.showinfo(
                self._t("shortcuts_title", controller=profile.display_name),
                self._t("shortcut_saved", controller=profile.display_name),
                parent=window,
            )

        ttk.Button(
            actions,
            text=self._t("shortcut_reset"),
            command=reset_shortcuts,
        ).pack(side="left")
        ttk.Button(
            actions,
            text=self._t("close"),
            command=window.destroy,
        ).pack(side="right")
        ttk.Button(
            actions,
            text=self._t("shortcut_save"),
            command=save_shortcuts,
            style="Accent.TButton",
        ).pack(side="right", padx=(0, 8))

    def show_live_settings(self) -> None:
        window = self.live_settings_window
        try:
            if window is not None and window.winfo_exists():
                window.deiconify()
                window.lift()
                window.focus_force()
                return
        except tk.TclError:
            pass

        window = tk.Toplevel(self.root)
        self.live_settings_window = window
        window.title(self._t("live_settings_title"))
        supported = live_runtime_supported(self.selected_profile_id)
        window.geometry(f"920x{640 if supported else 500}")
        window.minsize(800, 470)
        window.transient(self.root)
        if PRODUCT_ICON_PATH.is_file():
            try:
                window.iconbitmap(default=str(PRODUCT_ICON_PATH))
            except tk.TclError:
                pass

        frame = ttk.Frame(window, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(
            frame,
            text=self._t("live_settings_intro"),
            style="Subtitle.TLabel",
            wraplength=840,
            justify="left",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        connection = ttk.LabelFrame(frame, text="MIDI / OSC", padding=10)
        connection.grid(row=1, column=0, sticky="ew")
        connection.columnconfigure(1, weight=1)
        connection.columnconfigure(3, weight=1)
        ttk.Label(connection, text=self._t("midi_input")).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=3
        )
        self.midi_input_combo = ttk.Combobox(
            connection, textvariable=self.midi_input_var, state="normal"
        )
        self.midi_input_combo.grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(connection, text=self._t("midi_output")).grid(
            row=0, column=2, sticky="w", padx=(14, 6), pady=3
        )
        self.midi_output_combo = ttk.Combobox(
            connection, textvariable=self.midi_output_var, state="normal"
        )
        self.midi_output_combo.grid(row=0, column=3, sticky="ew", pady=3)
        ttk.Label(connection, text=self._t("liveprofessor_host")).grid(
            row=1, column=0, sticky="w", padx=(0, 6), pady=3
        )
        ttk.Entry(connection, textvariable=self.liveprofessor_host_var).grid(
            row=1, column=1, sticky="ew", pady=3
        )
        ttk.Label(connection, text=self._t("osc_output_port")).grid(
            row=1, column=2, sticky="w", padx=(14, 6), pady=3
        )
        ports = ttk.Frame(connection)
        ports.grid(row=1, column=3, sticky="ew", pady=3)
        ports.columnconfigure(0, weight=1)
        ports.columnconfigure(2, weight=1)
        ttk.Entry(ports, textvariable=self.liveprofessor_port_var, width=8).grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Label(ports, text=self._t("osc_feedback_port")).grid(
            row=0, column=1, sticky="w", padx=(12, 6)
        )
        ttk.Entry(ports, textvariable=self.feedback_port_var, width=8).grid(
            row=0, column=2, sticky="ew"
        )
        ttk.Button(
            connection,
            text=self._t("refresh_midi"),
            command=self.refresh_midi_ports,
        ).grid(row=2, column=3, sticky="e", pady=(7, 0))

        responsiveness = ttk.LabelFrame(
            frame, text=self._t("responsiveness_settings"), padding=10
        )
        responsiveness.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        responsiveness.columnconfigure(1, weight=1)
        responsiveness.columnconfigure(3, weight=1)
        ttk.Label(
            responsiveness,
            text=self._t("responsiveness_intro"),
            wraplength=840,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 6))
        timing_fields = (
            ("parameter_overlay_interval", self.parameter_overlay_interval_var, 1, 2000),
            ("companion_refresh_delay", self.companion_refresh_delay_var, 1, 2000),
            ("name_refresh_delay", self.name_refresh_delay_var, 1, 2000),
            ("feedback_confirm_timeout", self.feedback_timeout_var, 100, 10000),
            ("overlay_display_duration", self.overlay_display_duration_var, 200, 5000),
        )
        for index, (label_key, variable, minimum, maximum) in enumerate(timing_fields):
            row = 1 + index // 2
            column = (index % 2) * 2
            ttk.Label(responsiveness, text=self._t(label_key)).grid(
                row=row, column=column, sticky="w", padx=(0, 6), pady=3
            )
            ttk.Spinbox(
                responsiveness,
                from_=minimum,
                to=maximum,
                textvariable=variable,
                width=9,
            ).grid(row=row, column=column + 1, sticky="w", padx=(0, 16), pady=3)
        ttk.Checkbutton(
            responsiveness,
            text=self._t("persistent_parameter_display"),
            variable=self.persistent_display_var,
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(7, 0))

        self.live_settings_ec4_frame = ttk.LabelFrame(
            frame, text=self._t("ec4_tools"), padding=10
        )
        self.live_settings_ec4_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.live_settings_ec4_frame.columnconfigure(0, weight=1)
        self.live_settings_ec4_frame.columnconfigure(1, weight=1)
        ttk.Checkbutton(
            self.live_settings_ec4_frame,
            text=self._t("display_enabled"),
            variable=self.display_enabled_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 7))
        ec4_actions = (
            (self._t("import_legacy_config"), self.import_legacy_runtime_config),
            (self._t("reconnect_ec4"), self.reconnect_ec4),
            (self._t("request_setup"), self.request_setup_state),
            (self._t("refresh_companion"), self.refresh_companion),
            (self._t("test_display"), self.test_ec4_display),
        )
        for index, (label, command) in enumerate(ec4_actions):
            button = ttk.Button(
                self.live_settings_ec4_frame, text=label, command=command
            )
            row = 1 + index // 2
            column = index % 2
            button.grid(
                row=row,
                column=column,
                columnspan=2 if index == len(ec4_actions) - 1 else 1,
                sticky="ew",
                padx=(0 if column == 0 else 5, 5 if column == 0 else 0),
                pady=3,
            )
            if index > 0:
                self.runtime_settings_action_buttons.append(button)

        footer = ttk.Frame(frame)
        footer.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(
            footer,
            text=self._t("save"),
            command=self._save_live_settings,
        ).pack(side="right")
        ttk.Button(
            footer,
            text=self._t("close"),
            command=window.withdraw,
        ).pack(side="right", padx=(0, 7))
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        self._apply_live_profile_state()
        self.refresh_midi_ports()

    def _save_live_settings(self) -> None:
        was_running = bool(self.runtime and self.runtime.running)
        try:
            config = self._runtime_config_from_form()
            save_config(config, self.runtime_config_path)
            self.runtime_config = config
        except Exception as exc:
            messagebox.showerror(
                self._t("runtime_error"), str(exc), parent=self.live_settings_window
            )
            return
        if was_running:
            self.stop_runtime()
            self.start_runtime()
        self._update_mapping_status()
        self.status.set(self._t("settings_saved"))
        self._append_runtime_log(self._t("settings_saved"))

    def show_runtime_log(self) -> None:
        self.tray.restore()
        window = self.log_window
        try:
            if window is not None and window.winfo_exists():
                window.deiconify()
                window.lift()
                window.focus_force()
                return
        except tk.TclError:
            pass
        window = tk.Toplevel(self.root)
        self.log_window = window
        window.title(self._t("log_window"))
        window.geometry("820x460")
        window.minsize(640, 320)
        window.transient(self.root)
        if PRODUCT_ICON_PATH.is_file():
            try:
                window.iconbitmap(default=str(PRODUCT_ICON_PATH))
            except tk.TclError:
                pass
        frame = ttk.Frame(window, padding=8)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.runtime_log_text = tk.Text(
            frame,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            bg="#111820",
            fg="#d8e7ed",
            insertbackground="#ffffff",
        )
        self.runtime_log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            frame, orient="vertical", command=self.runtime_log_text.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.runtime_log_text.configure(yscrollcommand=scrollbar.set)
        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(
            buttons, text=self._t("copy_all"), command=self._copy_runtime_log
        ).pack(side="left")
        ttk.Button(
            buttons,
            text=self._t("clear_display"),
            command=self._clear_runtime_log_display,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            buttons,
            text=self._t("open_log_file"),
            command=self._open_runtime_log_file,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            buttons,
            text=self._t("open_log_folder"),
            command=self._open_runtime_log_folder,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            buttons, text=self._t("close"), command=window.withdraw
        ).pack(side="right")
        window.protocol("WM_DELETE_WINDOW", window.withdraw)
        self._render_runtime_log()

    def _copy_runtime_log(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append("".join(self._runtime_log_lines))

    def _clear_runtime_log_display(self) -> None:
        self._runtime_log_lines.clear()
        self.runtime_last_event.set("—")
        self._render_runtime_log()

    def _open_runtime_log_file(self) -> None:
        if self.log_path.is_file():
            os.startfile(str(self.log_path))

    def _open_runtime_log_folder(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self.log_path.parent))

    def _save_settings(self) -> bool:
        try:
            save_desktop_settings(self.settings, self.settings_path)
        except OSError as exc:
            self.status.set(self._t("settings_error", error=exc))
            return False
        self.status.set(self._t("settings_saved"))
        return True

    def _save_close_to_tray(self) -> None:
        self.settings = replace(
            self.settings,
            close_to_tray=bool(self.close_to_tray_var.get()),
        )
        self._save_settings()

    def _save_start_with_windows(self) -> None:
        enabled = bool(self.start_with_windows_var.get())
        try:
            set_start_with_windows(enabled)
        except OSError as exc:
            self.start_with_windows_var.set(not enabled)
            details = self._t("startup_registration_error", error=exc)
            self.status.set(details)
            messagebox.showerror(self._t("menu_options"), details, parent=self.root)
            return
        self.status.set(
            self._t("startup_windows_enabled" if enabled else "startup_windows_disabled")
        )

    def _save_auto_start_runtime(self) -> None:
        enabled = bool(self.auto_start_runtime_var.get())
        self.settings = replace(self.settings, auto_start_runtime=enabled)
        self._save_settings()
        if not enabled and self._auto_start_after_id is not None:
            try:
                self.root.after_cancel(self._auto_start_after_id)
            except Exception:
                pass
            self._auto_start_after_id = None

    def _apply_initial_startup_preferences(self) -> None:
        if self._start_minimized:
            self.minimize_to_tray()
        if not self.settings.auto_start_runtime:
            return
        self._auto_start_retry_index = 0
        self._schedule_automatic_runtime_start(AUTO_START_RETRY_DELAYS_MS[0])

    def _schedule_automatic_runtime_start(self, delay_ms: int) -> None:
        if self._closing or not self.settings.auto_start_runtime:
            return
        self._auto_start_after_id = self.root.after(
            max(0, int(delay_ms)), self._attempt_automatic_runtime_start
        )

    def _attempt_automatic_runtime_start(self) -> None:
        self._auto_start_after_id = None
        if self._closing or not self.settings.auto_start_runtime:
            return
        controller = self._active_controller_label()
        self.status.set(self._t("runtime_auto_start_attempt", controller=controller))
        self._append_runtime_log(
            self._t("runtime_auto_start_attempt", controller=controller)
        )
        if not live_runtime_supported(self.selected_profile_id):
            self.start_runtime(interactive=False)
            return
        if self.start_runtime(interactive=False):
            return
        self._auto_start_retry_index += 1
        if self._auto_start_retry_index >= len(AUTO_START_RETRY_DELAYS_MS):
            return
        delay = AUTO_START_RETRY_DELAYS_MS[self._auto_start_retry_index]
        details = self._t(
            "runtime_auto_start_retry",
            seconds=max(1, round(delay / 1000)),
        )
        self.status.set(details)
        self._append_runtime_log(details)
        self._schedule_automatic_runtime_start(delay)

    def change_language(self) -> None:
        selected = self.selected_profile_id
        self.settings = replace(self.settings, language=self.language_var.get())
        self._save_settings()
        self.runtime_config.ui_language = self.language_var.get()
        if self.runtime is not None:
            self.runtime.config.ui_language = self.language_var.get()
        try:
            save_config(self.runtime_config, self.runtime_config_path)
        except OSError as exc:
            self._append_runtime_log(f"Langue non enregistree dans le moteur: {exc}")
        self.tray.update_labels(
            tooltip=FULL_PRODUCT_NAME,
            open_label=self._t("tray_open"),
            quit_label=self._t("tray_quit"),
        )
        for child in self.root.winfo_children():
            child.destroy()
        self.log_window = None
        self.live_settings_window = None
        for stale_widget in (
            "runtime_log_text",
            "live_settings_ec4_frame",
            "midi_input_combo",
            "midi_output_combo",
        ):
            if hasattr(self, stale_widget):
                delattr(self, stale_widget)
        self._library_buttons = []
        self.status.set(self._t("loading"))
        self._build_ui()
        self.reload_catalog(selected)
        self._apply_runtime_snapshot(self.runtime_snapshot)
        self.root.after_idle(self.refresh_midi_ports)

    def minimize_to_tray(self) -> None:
        self.status.set(self._t("tray_hidden"))
        self.tray.hide()

    def _on_root_unmap(self, _event: object) -> None:
        if self._suppress_unmap or self._closing:
            return
        try:
            if self.root.state() != "iconic":
                return
        except Exception:
            return
        self._suppress_unmap = True
        try:
            self.root.after_idle(self.minimize_to_tray)
        finally:
            self._suppress_unmap = False

    def on_close(self) -> None:
        if bool(self.close_to_tray_var.get()):
            self.minimize_to_tray()
        else:
            self.quit()

    def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._auto_start_after_id is not None:
            try:
                self.root.after_cancel(self._auto_start_after_id)
            except Exception:
                pass
            self._auto_start_after_id = None
        if self._runtime_poll_after_id is not None:
            try:
                self.root.after_cancel(self._runtime_poll_after_id)
            except Exception:
                pass
            self._runtime_poll_after_id = None
        self.stop_runtime()
        self.tray.close()
        self.root.destroy()

    def open_manual(self) -> None:
        try:
            open_local_document(manual_path(self.language_var.get()))
        except (OSError, ValueError) as exc:
            messagebox.showerror(
                self._t("manual_error_title"),
                self._t("manual_error_body", error=exc),
                parent=self.root,
            )

    def show_support(self) -> None:
        window = getattr(self, "support_window", None)
        try:
            if window is not None and window.winfo_exists():
                window.deiconify()
                window.lift()
                return
        except tk.TclError:
            pass
        window = tk.Toplevel(self.root)
        self.support_window = window
        window.title(self._t("support_title"))
        window.resizable(False, False)
        window.transient(self.root)
        if PRODUCT_ICON_PATH.is_file():
            try:
                window.iconbitmap(default=str(PRODUCT_ICON_PATH))
            except tk.TclError:
                pass
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=self._t("support_intro"),
            wraplength=470,
            justify="center",
        ).pack(fill="x")
        if PAYPAL_QR_PATH.is_file():
            try:
                image = tk.PhotoImage(file=str(PAYPAL_QR_PATH)).subsample(2, 2)
                self._support_qr_photo = image
                ttk.Label(frame, image=image).pack(pady=12)
            except tk.TclError:
                pass
        ttk.Label(
            frame,
            text=PAYPAL_SUPPORT_URL,
            foreground="#245b75",
            font=("Segoe UI", 9),
        ).pack()
        ttk.Label(
            frame,
            text=self._t("support_optional"),
            wraplength=470,
            justify="center",
        ).pack(fill="x", pady=(10, 12))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(
            buttons,
            text=self._t("support_open_paypal"),
            command=self._open_paypal_support,
        ).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ttk.Button(
            buttons,
            text=self._t("support_close"),
            command=window.destroy,
        ).pack(side="left", expand=True, fill="x", padx=(5, 0))

        def close_window() -> None:
            self.support_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_window)

    def _open_paypal_support(self) -> None:
        try:
            open_paypal_support()
        except (OSError, ValueError) as exc:
            messagebox.showerror(
                self._t("support_error_title"),
                self._t("support_error", error=exc),
                parent=self.support_window or self.root,
            )

    def check_application_updates(self) -> None:
        self.status.set(self._t("app_update_checking"))

        def worker() -> None:
            try:
                release = fetch_latest_release()
            except NoCompatibleRelease as exc:
                self.root.after(
                    0,
                    lambda: self._finish_application_update_check(
                        None, str(exc), compatible=False
                    ),
                )
                return
            except Exception as exc:
                error = str(exc)
                self.root.after(
                    0,
                    lambda: self._finish_application_update_check(
                        None, error, compatible=True
                    ),
                )
                return
            self.root.after(
                0,
                lambda: self._finish_application_update_check(
                    release, None, compatible=True
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_application_update_check(
        self, release, error: str | None, *, compatible: bool
    ) -> None:
        if error is not None:
            if compatible:
                self.status.set(self._t("app_update_error_title"))
                messagebox.showerror(
                    self._t("app_update_error_title"), error, parent=self.root
                )
            else:
                self.status.set(self._t("app_update_none"))
                messagebox.showinfo(
                    self._t("check_app_updates"),
                    self._t("app_update_none"),
                    parent=self.root,
                )
            return
        if not is_newer_version(release.version, __version__):
            self.status.set(self._t("app_update_current_title"))
            messagebox.showinfo(
                self._t("app_update_current_title"),
                self._t("app_update_current", version=__version__),
                parent=self.root,
            )
            return
        notes = release.notes.strip()
        if len(notes) > 1200:
            notes = f"{notes[:1197]}…"
        if not messagebox.askyesno(
            self._t("app_update_available_title", version=release.version),
            self._t(
                "app_update_available",
                current=__version__,
                version=release.version,
                notes=notes,
            ),
            parent=self.root,
        ):
            self.status.set(self._t("app_update_available_title", version=release.version))
            return
        self.status.set(self._t("app_update_downloading"))

        def worker() -> None:
            try:
                result = download_update(release)
            except Exception as exc:
                error = str(exc)
                self.root.after(0, lambda: self._finish_application_download(None, error))
                return
            self.root.after(0, lambda: self._finish_application_download(result, None))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_application_download(self, result, error: str | None) -> None:
        if error is not None:
            self.status.set(self._t("app_update_error_title"))
            messagebox.showerror(
                self._t("app_update_error_title"), error, parent=self.root
            )
            return
        try:
            launch_installer(result.path)
        except Exception as exc:
            self.status.set(self._t("app_update_error_title"))
            messagebox.showerror(
                self._t("app_update_error_title"), str(exc), parent=self.root
            )
            return
        self.status.set(
            self._t("app_update_available_title", version=result.release.version)
        )
        messagebox.showinfo(
            self._t("app_update_launched_title"),
            self._t("app_update_launched", path=result.path),
            parent=self.root,
        )

    def show_about(self) -> None:
        messagebox.showinfo(
            self._t("about_title"),
            self._t("about_body", version=DISPLAY_VERSION),
            parent=self.root,
        )


def start_minimized_requested(arguments: list[str] | None = None) -> bool:
    values = sys.argv[1:] if arguments is None else arguments
    return "--minimized" in values


def main(arguments: list[str] | None = None) -> int:
    root = tk.Tk()
    ControlHubDesktop(root, start_minimized=start_minimized_requested(arguments))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
