"""Generate the bilingual Controller Studio PDF manuals with ReportLab."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from silemio_control_hub import __version__  # noqa: E402


DISPLAY_VERSION = "V.2026"


OUTPUT_DIR = ROOT / "output" / "pdf"
PACKAGE_DIR = SRC / "silemio_control_hub" / "manuals"
ICON = SRC / "silemio_control_hub" / "assets" / "controller-studio.png"
PAYPAL_QR = SRC / "silemio_control_hub" / "assets" / "paypal-support-qr.png"
NAVY = colors.HexColor("#111820")
BLUE = colors.HexColor("#087D9D")
CYAN = colors.HexColor("#2CA9D6")
PALE = colors.HexColor("#EAF5F8")
LIGHT = colors.HexColor("#F4F7F8")
MID = colors.HexColor("#6A7C86")


CONTENT = {
    "fr": {
        "filename": "SiLeMIO-Controller-Studio-Notice-FR.pdf",
        "manual": "NOTICE COMPLETE",
        "subtitle": "Plugin Studio, contrôleurs MIDI, AutoMap et moteur EC4 pour LiveProfessor",
        "edition": "Édition française",
        "independent": (
            "Produit indépendant. LiveProfessor et les marques de plug-ins citées appartiennent "
            "à leurs éditeurs respectifs."
        ),
        "source_safe": (
            "Règle de sécurité : AutoMap ne modifie jamais le projet source. Une nouvelle copie "
            ".rack2 est toujours créée et validée avant enregistrement."
        ),
        "contents": "Sommaire",
        "toc": [
            "1. Démarrage rapide",
            "2. AutoMap : contrôleur, banques et sélection des plug-ins",
            "3. Plugin Studio : reconnaître et organiser les paramètres",
            "4. Contrôle EC4 en temps réel",
            "5. Banque de contrôleurs et fichiers .ctrl2",
            "6. Bibliothèque communautaire",
            "7. Interface, langues et zone de notification",
            "8. Mises à jour, notice et soutien",
            "9. Diagnostic, sécurité et limites actuelles",
        ],
        "sections": [
            (
                "1. Démarrage rapide",
                [
                    ("h2", "Avant de commencer"),
                    (
                        "p",
                        "Fermez EC4 Bridge avant de démarrer le moteur de Controller Studio. Les deux "
                        "applications utilisent les mêmes ports MIDI/OSC et ne doivent pas piloter "
                        "LiveProfessor simultanément. EC4 Bridge reste votre solution de secours tant "
                        "que la validation matérielle complète n'est pas terminée.",
                    ),
                    ("callout", "Ne sauvegardez jamais par-dessus votre projet LiveProfessor original. Utilisez uniquement la copie AutoMap créée par le logiciel."),
                    ("h2", "Connexion EC4 / LiveProfessor"),
                    (
                        "steps",
                        [
                            ("1", "Branchez l'EC4 et ouvrez LiveProfessor."),
                            ("2", "Dans l'onglet Live, choisissez les ports MIDI d'entrée et de sortie de l'EC4."),
                            ("3", "Vérifiez l'adresse 127.0.0.1, le port OSC 8010 et le port de retour 8011."),
                            ("4", "Sélectionnez le setup 13 et le groupe 3, ou utilisez le setup/groupe actuellement détecté."),
                            ("5", "Cliquez sur Démarrer. L'EC4 affiche le message de connexion Controller Studio / By Mamat."),
                        ],
                    ),
                    ("h2", "Préparer un projet"),
                    (
                        "p",
                        "Le bouton bleu AutoMap est disponible dès l'onglet Live, dans la banque de "
                        "contrôleurs et dans le menu Outils. Il ouvre l'assistant complet décrit au "
                        "chapitre suivant.",
                    ),
                ],
            ),
            (
                "2. AutoMap : contrôleur, banques et sélection des plug-ins",
                [
                    ("h2", "Principe"),
                    (
                        "p",
                        "AutoMap lit hors ligne les plug-ins et paramètres exposés dans un fichier .rack2. "
                        "Il crée des Controller Maps conditionnées par le plug-in sélectionné dans "
                        "LiveProfessor. Tourner un encodeur agit donc sur l'instance actuellement "
                        "sélectionnée, sans remapper manuellement chaque instance.",
                    ),
                    ("h2", "Procédure"),
                    (
                        "steps",
                        [
                            ("1", "Choisissez le projet source puis cliquez sur Analyser."),
                            ("2", "Choisissez le profil physique : Faderfox EC4 ou un autre profil disponible dans la banque."),
                            ("3", "Réutilisez de préférence le contrôleur Companion/OSC déjà présent dans le projet."),
                            ("4", "Choisissez UniBank ou FullBank."),
                            ("5", "Mappez tous les plug-ins ou activez Sélection personnalisée et cochez précisément les instances voulues."),
                            ("6", "Choisissez un nouveau nom de copie. Le fichier .ctrl2 correspondant est créé à côté."),
                        ],
                    ),
                    ("h2", "UniBank et FullBank"),
                    (
                        "table",
                        [
                            ["Mode", "EC4", "Utilisation"],
                            ["UniBank", "16 rotatifs", "Recommandé : une banque simple, labels faciles à vérifier."],
                            ["FullBank", "99 rotatifs", "Plusieurs banques pour les plug-ins riches en paramètres."],
                        ],
                    ),
                    ("h2", "Pourquoi réutiliser le contrôleur existant ?"),
                    (
                        "callout",
                        "Deux contrôleurs Companion partageant /Companion/RotaryN peuvent renvoyer deux listes de labels concurrentes. Controller Studio sélectionne désormais automatiquement l'unique contrôleur existant et vous avertit avant d'en créer un second.",
                    ),
                    (
                        "p",
                        "Les affectations manuelles existantes restent prioritaires. Pour un même type "
                        "de plug-in, Controller Studio réutilise un profil déterministe afin que toutes "
                        "les instances conservent le même ordre physique.",
                    ),
                ],
            ),
            (
                "3. Plugin Studio : reconnaître et organiser les paramètres",
                [
                    ("h2", "Analyser un projet"),
                    (
                        "steps",
                        [
                            ("1", "Ouvrez l'onglet Plug-ins puis choisissez un projet .rack2."),
                            ("2", "Cliquez sur Analyser les plug-ins. Les instances identiques sont regroupées par type."),
                            ("3", "Sélectionnez un type puis ouvrez Créer / modifier le profil."),
                            ("4", "Renseignez le nom, le libellé court, le type, le rôle, l'unité et la priorité des paramètres utiles."),
                            ("5", "Enregistrez le profil local puis cliquez sur Utiliser dans AutoMap."),
                        ],
                    ),
                    ("h2", "Priorité AutoMap"),
                    (
                        "p",
                        "Une priorité de 100 place le paramètre avant une priorité de 0 dans les "
                        "emplacements encore libres. Les affectations apprises ou manuelles et les "
                        "paramètres déjà préservés restent toujours prioritaires. Toutes les instances "
                        "du même type utilisent ensuite le même ordre.",
                    ),
                    ("h2", "Profils locaux sûrs"),
                    (
                        "p",
                        "Le profil est un fichier JSON déclaratif enregistré dans les données utilisateur. "
                        "Chaque mise à jour reçoit une nouvelle version et l'ancienne est sauvegardée. "
                        "Aucun code n'est téléchargé ou exécuté et le projet .rack2 analysé reste inchangé.",
                    ),
                    (
                        "callout",
                        "LiveProfessor enregistre les numéros de paramètres dans le .rack2, mais pas leurs vrais noms. Saisissez ou vérifiez donc les noms avant de partager un profil.",
                    ),
                ],
            ),
            (
                "4. Contrôle EC4 en temps réel",
                [
                    ("h2", "Banques, valeurs et labels"),
                    (
                        "p",
                        "Les 16 encodeurs physiques pilotent Rotary1 à Rotary16 en banque 1, puis "
                        "Rotary17 à Rotary32 en banque 2, etc. Les valeurs et ControllerNames renvoyés "
                        "par LiveProfessor sont remis dans la même banque avant affichage sur la grille "
                        "4 x 4 de l'EC4. Les boutons Banque précédente / suivante de l'interface suivent "
                        "le même index que les raccourcis Shift.",
                    ),
                    ("h2", "Raccourcis Shift"),
                    (
                        "table",
                        [
                            ["Push", "Action"],
                            ["1 / 2", "Banque précédente / suivante"],
                            ["3 / 4", "View Set précédent / suivant"],
                            ["5", "Afficher / masquer le plug-in sélectionné"],
                            ["6 / 10", "Chaîne précédente / suivante"],
                            ["7-8 / 11-12", "Plug-in précédent / suivant"],
                            ["9", "Activer / désactiver le traitement du plug-in"],
                            ["13 / 14", "Cue précédente / suivante"],
                            ["15 / 16", "Snapshot précédent / suivant"],
                            ["Push 16 seul", "Tap Tempo"],
                        ],
                    ),
                    ("h2", "Apprentissage MIDI"),
                    (
                        "p",
                        "Si un setup ou un groupe EC4 utilise d'autres messages, lancez l'apprentissage "
                        "des 16 rotatifs puis de leurs 16 push. Le mapping est enregistré par zone EC4. "
                        "La reconnexion, la lecture du setup/groupe et le rafraîchissement Companion sont "
                        "accessibles depuis l'onglet Live.",
                    ),
                ],
            ),
            (
                "5. Banque de contrôleurs et fichiers .ctrl2",
                [
                    ("h2", "Choisir ou créer un contrôleur"),
                    (
                        "p",
                        "La banque locale contient les profils intégrés et les profils installés depuis "
                        "la bibliothèque. Chaque profil décrit le matériel : messages MIDI, taille de "
                        "banque, pages, poussoirs, retours, écran et capacités. Le profil Faderfox EC4 "
                        "est vérifié ; un profil communautaire reste indiqué comme tel tant qu'il n'a "
                        "pas été testé sur le matériel réel.",
                    ),
                    ("h2", "Exporter le .ctrl2"),
                    (
                        "steps",
                        [
                            ("1", "Sélectionnez le contrôleur dans la banque."),
                            ("2", "Cliquez sur Exporter le contrôleur .ctrl2."),
                            ("3", "Dans LiveProfessor, ouvrez Hardware Controllers Setup puis Load from file."),
                            ("4", "Vérifiez l'hôte 127.0.0.1, l'entrée 8010 et le retour 8011."),
                        ],
                    ),
                    (
                        "p",
                        "L'assistant AutoMap exporte automatiquement le .ctrl2 adapté au mode UniBank "
                        "ou FullBank. Le fichier ne contient aucun réglage audio, projet personnel ni "
                        "licence de plug-in.",
                    ),
                ],
            ),
            (
                "6. Bibliothèque communautaire",
                [
                    ("h2", "Fonctionnement hors ligne"),
                    (
                        "p",
                        "Les profils installés sont mis en cache localement. Controller Studio démarre "
                        "et fonctionne sans Internet. Le menu Bibliothèque permet d'abord de prévisualiser "
                        "les nouveautés ; l'installation n'a lieu qu'après confirmation.",
                    ),
                    ("h2", "Contrôles de sécurité"),
                    (
                        "bullets",
                        [
                            "validation des schémas et refus des champs critiques inconnus ;",
                            "contrôle des versions et des empreintes SHA-256 ;",
                            "sauvegarde du cache courant puis remplacement atomique ;",
                            "profils déclaratifs uniquement : aucun code téléchargé n'est exécuté.",
                        ],
                    ),
                    ("h2", "Contribuer"),
                    (
                        "p",
                        "Un utilisateur peut proposer un profil de contrôleur ou de plug-in via GitHub. "
                        "Avant publication, retirez toute identité de machine, adresse réseau de production, "
                        "réglage personnel, projet .rack2 et information de licence.",
                    ),
                ],
            ),
            (
                "7. Interface, langues et zone de notification",
                [
                    ("h2", "Français / English"),
                    (
                        "p",
                        "La langue se change immédiatement dans Options > Langue. Les menus, fenêtres, "
                        "messages de diagnostic et la notice ouverte depuis Aide suivent cette préférence."
                    ),
                    ("h2", "Réduction dans le tray"),
                    (
                        "p",
                        "Avec l'option de fermeture vers la zone de notification, fermer ou réduire la "
                        "fenêtre masque l'interface sans arrêter le moteur. Un clic sur l'icône restaure "
                        "Controller Studio. Seule l'action explicite Quitter arrête le processus."
                    ),
                    ("h2", "Journal et diagnostic"),
                    (
                        "p",
                        "Le journal temps réel indique les ports MIDI, la connexion, les commandes OSC, "
                        "les changements de banque et les erreurs de retour. Le bouton Diagnostic rassemble "
                        "l'état du moteur, de l'EC4 et de LiveProfessor sans modifier la configuration."
                    ),
                ],
            ),
            (
                "8. Mises à jour, notice et soutien",
                [
                    ("h2", "Mise à jour de l'application"),
                    (
                        "p",
                        "Aide > Rechercher les mises à jour consulte la dernière GitHub Release stable. "
                        "Seul un installateur nommé pour SiLeMI/O Controller Studio est accepté ; une "
                        "ancienne version EC4 Bridge est ignorée. La taille et le SHA-256 sont vérifiés "
                        "avant le lancement de l'installateur."
                    ),
                    ("h2", "Notice localisée"),
                    (
                        "p",
                        "Aide > Ouvrir la notice PDF ouvre ce document lorsque l'interface est en français, "
                        "et le manuel anglais lorsque l'interface est en anglais. Les deux PDF sont inclus "
                        "dans l'application et restent disponibles hors ligne."
                    ),
                    ("h2", "Soutien facultatif"),
                    (
                        "support",
                        "Le menu Soutenir SiLeMI/O affiche un QR code et ouvre uniquement l'adresse PayPal.Me vérifiée. Le soutien est facultatif ; le logiciel et toutes ses fonctions restent disponibles gratuitement.",
                    ),
                ],
            ),
            (
                "9. Diagnostic, sécurité et limites actuelles",
                [
                    ("h2", "En cas de problème de labels"),
                    (
                        "steps",
                        [
                            ("1", "Vérifiez qu'un seul contrôleur Companion/OSC utilise les adresses /Companion/RotaryN."),
                            ("2", "Dans l'assistant AutoMap, choisissez Réutiliser EC4 plutôt que Créer un nouveau contrôleur."),
                            ("3", "Rafraîchissez Companion puis revenez à la banque 1."),
                            ("4", "Si nécessaire, recréez une copie depuis le projet source préservé."),
                        ],
                    ),
                    ("h2", "Limites actuelles"),
                    (
                        "bullets",
                        [
                            "LiveProfessor est actuellement le seul hôte pris en charge ;",
                            "le Faderfox EC4 est le contrôleur de référence validé ;",
                            "le X-Touch Compact doit être capturé et testé sur matériel réel avant d'être marqué vérifié ;",
                            "la parité complète avec EC4 Bridge doit encore être confirmée sur les 16 encodeurs/push, toutes les banques, Shift, les labels/valeurs, la reconnexion et le tray.",
                        ],
                    ),
                    ("callout", "Conservez EC4 Bridge installé comme solution de secours jusqu'à votre validation matérielle explicite de Controller Studio."),
                ],
            ),
        ],
    },
}


def english_content() -> dict:
    fr = CONTENT["fr"]
    return {
        "filename": "SiLeMIO-Controller-Studio-Manual-EN.pdf",
        "manual": "COMPLETE MANUAL",
        "subtitle": "Plugin Studio, MIDI controllers, AutoMap, and EC4 engine for LiveProfessor",
        "edition": "English edition",
        "independent": (
            "Independent product. LiveProfessor and the plug-in brands mentioned belong to "
            "their respective publishers."
        ),
        "source_safe": (
            "Safety rule: AutoMap never changes the source project. A new .rack2 copy is always "
            "created and validated before it is saved."
        ),
        "contents": "Contents",
        "toc": [
            "1. Quick start",
            "2. AutoMap: controller, banks, and plug-in selection",
            "3. Plugin Studio: recognize and organize parameters",
            "4. Real-time EC4 control",
            "5. Controller bank and .ctrl2 files",
            "6. Community library",
            "7. Interface, languages, and notification area",
            "8. Updates, manual, and support",
            "9. Diagnostics, safety, and current limitations",
        ],
        "sections": [
            (
                "1. Quick start",
                [
                    ("h2", "Before you begin"),
                    ("p", "Close EC4 Bridge before starting the Controller Studio engine. Both applications use the same MIDI/OSC ports and must not control LiveProfessor at the same time. Keep EC4 Bridge as your fallback until complete hardware acceptance is finished."),
                    ("callout", "Never save over your original LiveProfessor project. Use only the AutoMap copy created by the application."),
                    ("h2", "Connect EC4 and LiveProfessor"),
                    ("steps", [("1", "Connect the EC4 and open LiveProfessor."), ("2", "On the Live tab, select the EC4 MIDI input and output ports."), ("3", "Check address 127.0.0.1, OSC port 8010, and feedback port 8011."), ("4", "Select EC4 setup 13 and group 3, or use the currently detected setup/group."), ("5", "Click Start. The EC4 shows the Controller Studio / By Mamat connection message.")]),
                    ("h2", "Prepare a project"),
                    ("p", "The blue AutoMap button is available directly on the Live tab, in the controller bank, and in the Tools menu. It opens the complete assistant described in the next chapter."),
                ],
            ),
            (
                "2. AutoMap: controller, banks, and plug-in selection",
                [
                    ("h2", "How it works"),
                    ("p", "AutoMap reads the plug-ins and exposed parameters from a .rack2 file offline. It creates Controller Maps conditioned by the selected plug-in in LiveProfessor. A rotary therefore controls the currently selected instance without manually mapping every instance."),
                    ("h2", "Procedure"),
                    ("steps", [("1", "Choose the source project, then click Analyze."), ("2", "Choose the physical profile: Faderfox EC4 or another profile from the bank."), ("3", "Prefer reusing the Companion/OSC controller already present in the project."), ("4", "Choose UniBank or FullBank."), ("5", "Map all plug-ins, or enable Custom selection and check the exact instances you want."), ("6", "Choose a new copy name. The matching .ctrl2 file is created beside it.")]),
                    ("h2", "UniBank and FullBank"),
                    ("table", [["Mode", "EC4", "Use"], ["UniBank", "16 rotaries", "Recommended: one simple bank with easy-to-check labels."], ["FullBank", "99 rotaries", "Multiple banks for plug-ins with many parameters."]]),
                    ("h2", "Why reuse the existing controller?"),
                    ("callout", "Two Companion controllers sharing /Companion/RotaryN can return two competing label lists. Controller Studio now automatically selects the only existing controller and warns before creating a second one."),
                    ("p", "Existing manual assignments remain authoritative. Controller Studio reuses one deterministic profile for every instance of a plug-in type so each instance keeps the same physical order."),
                ],
            ),
            (
                "3. Plugin Studio: recognize and organize parameters",
                [
                    ("h2", "Analyze a project"),
                    ("steps", [("1", "Open the Plug-ins tab and choose a .rack2 project."), ("2", "Click Analyze plug-ins. Identical instances are grouped by type."), ("3", "Select a type, then open Create / edit profile."), ("4", "Enter the name, short label, kind, role, unit, and priority of useful parameters."), ("5", "Save the local profile, then click Use in AutoMap.")]),
                    ("h2", "AutoMap priority"),
                    ("p", "A priority of 100 places the parameter before a priority of 0 in free slots. Learned or manual assignments and preserved parameters always remain authoritative. Every instance of the same type then uses the same order."),
                    ("h2", "Safe local profiles"),
                    ("p", "The profile is a declarative JSON file stored in user data. Every update receives a new version and the previous file is backed up. No downloaded code is executed, and the analyzed .rack2 project remains unchanged."),
                    ("callout", "LiveProfessor stores parameter numbers in the .rack2, but not their real names. Enter or verify names before sharing a profile."),
                ],
            ),
            (
                "4. Real-time EC4 control",
                [
                    ("h2", "Banks, values, and labels"),
                    ("p", "The 16 physical encoders control Rotary1 through Rotary16 in bank 1, Rotary17 through Rotary32 in bank 2, and so on. Values and ControllerNames returned by LiveProfessor are placed back into the same bank before being shown on the EC4 4 x 4 grid. The Previous/Next Bank buttons use the same index as the Shift shortcuts."),
                    ("h2", "Shift shortcuts"),
                    ("table", [["Push", "Action"], ["1 / 2", "Previous / next bank"], ["3 / 4", "Previous / next View Set"], ["5", "Show / hide selected plug-in"], ["6 / 10", "Previous / next chain"], ["7-8 / 11-12", "Previous / next plug-in"], ["9", "Enable / disable plug-in processing"], ["13 / 14", "Previous / next cue"], ["15 / 16", "Previous / next snapshot"], ["Push 16 only", "Tap Tempo"]]),
                    ("h2", "MIDI learn"),
                    ("p", "If an EC4 setup or group uses different messages, learn the 16 rotaries and then their 16 pushes. The mapping is stored for that EC4 zone. Reconnect, setup/group readback, and Companion refresh are available on the Live tab."),
                ],
            ),
            (
                "5. Controller bank and .ctrl2 files",
                [
                    ("h2", "Choose or create a controller"),
                    ("p", "The local bank contains built-in profiles and profiles installed from the library. Each profile describes MIDI messages, bank size, pages, pushes, feedback, display, and capabilities. The Faderfox EC4 profile is verified; a community profile remains labelled as such until tested on real hardware."),
                    ("h2", "Export the .ctrl2 file"),
                    ("steps", [("1", "Select the controller in the bank."), ("2", "Click Export controller .ctrl2."), ("3", "In LiveProfessor, open Hardware Controllers Setup, then Load from file."), ("4", "Check host 127.0.0.1, input 8010, and feedback 8011.")]),
                    ("p", "The AutoMap assistant automatically exports the .ctrl2 file for UniBank or FullBank. It contains no audio settings, personal project, or plug-in licence information."),
                ],
            ),
            (
                "6. Community library",
                [
                    ("h2", "Offline operation"),
                    ("p", "Installed profiles are cached locally. Controller Studio starts and works without Internet. The Library menu previews changes first; installation occurs only after confirmation."),
                    ("h2", "Security checks"),
                    ("bullets", ["schema validation and rejection of unknown critical fields;", "version and SHA-256 verification;", "backup of the current cache followed by atomic replacement;", "declarative profiles only: downloaded code is never executed."]),
                    ("h2", "Contribute"),
                    ("p", "Users can propose controller or plug-in profiles through GitHub. Before publishing, remove machine identities, production network addresses, personal settings, .rack2 projects, and licence information."),
                ],
            ),
            (
                "7. Interface, languages, and notification area",
                [
                    ("h2", "Français / English"),
                    ("p", "Change the language immediately from Options > Language. Menus, windows, diagnostic messages, and the manual opened from Help follow this preference."),
                    ("h2", "Minimize to tray"),
                    ("p", "With close-to-notification-area enabled, closing or minimizing hides the interface without stopping the engine. Click the tray icon to restore Controller Studio. Only the explicit Quit action stops the process."),
                    ("h2", "Log and diagnostics"),
                    ("p", "The real-time log reports MIDI ports, connection, OSC commands, bank changes, and feedback errors. Diagnostics gathers the engine, EC4, and LiveProfessor state without changing the configuration."),
                ],
            ),
            (
                "8. Updates, manual, and support",
                [
                    ("h2", "Application update"),
                    ("p", "Help > Check for updates queries the latest stable GitHub Release. Only an installer named for SiLeMI/O Controller Studio is accepted; an old EC4 Bridge release is ignored. Size and SHA-256 are verified before the installer is launched."),
                    ("h2", "Localized manual"),
                    ("p", "Help > Open PDF manual opens the French notice when the interface is French and this English manual when the interface is English. Both PDFs are bundled and remain available offline."),
                    ("h2", "Optional support"),
                    ("support", "Support SiLeMI/O displays a QR code and opens only the validated PayPal.Me address. Support is optional; the software and every feature remain available free of charge."),
                ],
            ),
            (
                "9. Diagnostics, safety, and current limitations",
                [
                    ("h2", "If labels do not match"),
                    ("steps", [("1", "Check that only one Companion/OSC controller uses /Companion/RotaryN."), ("2", "In AutoMap, choose Reuse EC4 instead of Create a new controller."), ("3", "Refresh Companion, then return to bank 1."), ("4", "If needed, create a fresh copy from the preserved source project.")]),
                    ("h2", "Current limitations"),
                    ("bullets", ["LiveProfessor is currently the only supported host;", "Faderfox EC4 is the validated reference controller;", "X-Touch Compact messages must be captured and tested on real hardware before the profile can be marked verified;", "complete EC4 Bridge parity still requires hardware confirmation of all 16 encoders/pushes, every bank, Shift, labels/values, reconnection, and tray behavior."]),
                    ("callout", "Keep EC4 Bridge installed as a fallback until you explicitly accept Controller Studio on real hardware."),
                ],
            ),
        ],
    }


CONTENT["en"] = english_content()


# V.2026 deliberately presents one finished workflow instead of documenting
# individual hardware roadmaps. Controller-specific details belong in the
# contextual driver help, not in the product manual.
CONTENT = {
    "fr": {
        "filename": "Controller-Studio-for-LiveProfessor-Notice-FR.pdf",
        "manual": "NOTICE",
        "subtitle": "Contrôleurs MIDI, Plugin Studio et AutoMap pour LiveProfessor",
        "edition": "Édition française",
        "independent": (
            "Produit indépendant créé par SiLeMI/O. LiveProfessor et les marques de "
            "plug-ins citées appartiennent à leurs éditeurs respectifs."
        ),
        "source_safe": (
            "AutoMap ne modifie jamais le projet source. Une nouvelle copie .rack2 "
            "est créée et validée avant enregistrement."
        ),
        "contents": "Sommaire",
        "toc": [
            "1. Démarrage rapide",
            "2. Choisir un contrôleur et utiliser le mode Live",
            "3. Créer une copie AutoMap",
            "4. Organiser les paramètres avec Plugin Studio",
            "5. Bibliothèque de profils",
            "6. Interface, journal et mises à jour",
            "7. Sécurité et dépannage",
        ],
        "sections": [
            (
                "1. Démarrage rapide",
                [
                    ("h2", "Le parcours le plus court"),
                    (
                        "steps",
                        [
                            ("1", "Ouvrez la Banque de contrôleurs et choisissez le profil de votre matériel."),
                            ("2", "Exportez le fichier .ctrl2 si vous souhaitez ajouter ce contrôleur à LiveProfessor."),
                            ("3", "Cliquez sur AutoMap, choisissez un projet .rack2 et lancez l'analyse."),
                            ("4", "Sélectionnez les plug-ins voulus puis créez une nouvelle copie du projet."),
                            ("5", "Chargez le .ctrl2 et la copie AutoMap dans LiveProfessor."),
                        ],
                    ),
                    (
                        "callout",
                        "Conservez toujours le projet LiveProfessor original. Travaillez uniquement avec la copie créée par AutoMap.",
                    ),
                ],
            ),
            (
                "2. Choisir un contrôleur et utiliser le mode Live",
                [
                    ("h2", "Banque de contrôleurs"),
                    (
                        "p",
                        "Chaque profil décrit les commandes MIDI, les banques, les poussoirs, les retours et les capacités d'un contrôleur. Son état indique s'il est intégré, vérifié, local ou proposé par la communauté.",
                    ),
                    ("h2", "Contrôleur actif"),
                    (
                        "p",
                        "Le sélecteur de la page Live reste synchronisé avec la banque. Lorsqu'un pilote temps réel est disponible, les boutons Démarrer, Arrêter, les banques et les réglages adaptés deviennent accessibles. Sinon, le profil reste immédiatement utilisable pour l'export et AutoMap.",
                    ),
                    ("h2", "Exporter vers LiveProfessor"),
                    (
                        "steps",
                        [
                            ("1", "Sélectionnez le contrôleur dans la banque."),
                            ("2", "Cliquez sur Exporter le contrôleur .ctrl2."),
                            ("3", "Dans LiveProfessor, ouvrez Hardware Controllers Setup puis Load from file."),
                        ],
                    ),
                ],
            ),
            (
                "3. Créer une copie AutoMap",
                [
                    ("h2", "Analyser et choisir"),
                    (
                        "steps",
                        [
                            ("1", "Choisissez le projet source puis cliquez sur Analyser."),
                            ("2", "Choisissez le profil du contrôleur et réutilisez de préférence le contrôleur déjà présent dans le projet."),
                            ("3", "Sélectionnez tous les plug-ins ou cochez seulement les instances voulues."),
                            ("4", "Choisissez le nombre de commandes par banque puis créez la copie."),
                        ],
                    ),
                    ("h2", "Ordre des paramètres"),
                    (
                        "p",
                        "Les affectations manuelles existantes restent prioritaires. Les emplacements libres suivent ensuite le profil Plugin Studio afin que toutes les instances d'un même plug-in conservent le même ordre.",
                    ),
                    (
                        "callout",
                        "Créer plusieurs contrôleurs utilisant les mêmes adresses Companion peut mélanger les labels. Réutilisez le contrôleur existant lorsque l'assistant le propose.",
                    ),
                ],
            ),
            (
                "4. Organiser les paramètres avec Plugin Studio",
                [
                    ("h2", "Reconnaître un plug-in"),
                    (
                        "steps",
                        [
                            ("1", "Ouvrez l'onglet Plug-ins et choisissez un projet .rack2."),
                            ("2", "Analysez le projet : les instances identiques sont regroupées automatiquement."),
                            ("3", "Ouvrez le profil d'un type de plug-in."),
                            ("4", "Dans la barre supérieure de LiveProfessor, rappelez SiLeMI/O AutoMap - NomDuPlugin, et non la map Dynamic."),
                            ("5", "Cliquez sur Récupérer automatiquement les vrais noms."),
                            ("6", "Utilisez Tout cocher, Tout décocher ou les cases individuelles pour choisir les paramètres AutoMap."),
                            ("7", "Corrigez si nécessaire les noms et priorités, enregistrez localement, puis utilisez le profil dans AutoMap."),
                        ],
                    ),
                    ("h2", "Profils locaux sûrs"),
                    (
                        "p",
                        "Les profils sont des fichiers JSON déclaratifs. Chaque remplacement peut être sauvegardé, aucun code téléchargé n'est exécuté et le projet analysé reste inchangé.",
                    ),
                ],
            ),
            (
                "5. Bibliothèque de profils",
                [
                    ("h2", "Mettre à jour"),
                    (
                        "p",
                        "La bibliothèque publique fournit des profils de contrôleurs et de plug-ins. Vous pouvez prévisualiser les changements avant installation. Le cache local permet ensuite de travailler hors ligne.",
                    ),
                    ("h2", "Contribuer"),
                    (
                        "p",
                        "Dans la Banque de contrôleurs, Proposer à la bibliothèque valide le profil sélectionné, copie son JSON et ouvre le formulaire GitHub déjà titré. Collez le JSON, ajoutez la documentation ou les essais disponibles, puis envoyez.",
                    ),
                    (
                        "bullets",
                        [
                            "validation stricte du format ;",
                            "contrôle de version et SHA-256 ;",
                            "sauvegarde avant remplacement ;",
                            "aucun code exécutable dans les profils.",
                        ],
                    ),
                ],
            ),
            (
                "6. Interface, journal et mises à jour",
                [
                    ("h2", "Une première page simple"),
                    (
                        "p",
                        "La page Live garde uniquement le contrôleur actif, les commandes essentielles, l'état et le dernier événement. Les connexions MIDI/OSC sont dans Réglages et le journal complet s'ouvre dans une fenêtre séparée.",
                    ),
                    ("h2", "Langue et zone de notification"),
                    (
                        "p",
                        "Options > Langue bascule immédiatement entre français et anglais. La réduction dans la zone de notification masque la fenêtre sans arrêter un moteur actif ; Quitter arrête réellement l'application.",
                    ),
                    ("h2", "Notice, mises à jour et soutien"),
                    (
                        "p",
                        "Le menu Aide ouvre la notice dans la langue active et recherche les versions stables. Chaque installateur est contrôlé par sa taille et son empreinte SHA-256 avant lancement.",
                    ),
                    (
                        "support",
                        "Le soutien via PayPal est facultatif. Toutes les fonctions restent disponibles gratuitement.",
                    ),
                ],
            ),
            (
                "7. Sécurité et dépannage",
                [
                    ("h2", "Si un label ne correspond pas à la commande"),
                    (
                        "steps",
                        [
                            ("1", "Vérifiez qu'un seul contrôleur Companion utilise la même série d'adresses."),
                            ("2", "Rouvrez AutoMap et réutilisez le contrôleur déjà présent."),
                            ("3", "Vérifiez l'ordre du profil Plugin Studio et les affectations manuelles conservées."),
                            ("4", "Recréez une copie à partir du projet source préservé."),
                        ],
                    ),
                    ("h2", "Diagnostic"),
                    (
                        "p",
                        "Le journal séparé permet de copier les événements ou d'ouvrir le fichier complet. Le diagnostic contrôle les ports, la configuration et l'état du moteur sans modifier le projet LiveProfessor.",
                    ),
                ],
            ),
        ],
    },
    "en": {
        "filename": "Controller-Studio-for-LiveProfessor-Manual-EN.pdf",
        "manual": "MANUAL",
        "subtitle": "MIDI controllers, Plugin Studio, and AutoMap for LiveProfessor",
        "edition": "English edition",
        "independent": (
            "Independent product created by SiLeMI/O. LiveProfessor and the plug-in "
            "brands mentioned belong to their respective publishers."
        ),
        "source_safe": (
            "AutoMap never changes the source project. A new .rack2 copy is created "
            "and validated before it is saved."
        ),
        "contents": "Contents",
        "toc": [
            "1. Quick start",
            "2. Choose a controller and use Live mode",
            "3. Create an AutoMap copy",
            "4. Organize parameters with Plugin Studio",
            "5. Profile library",
            "6. Interface, log, and updates",
            "7. Safety and troubleshooting",
        ],
        "sections": [
            (
                "1. Quick start",
                [
                    ("h2", "The shortest workflow"),
                    ("steps", [("1", "Open the Controller bank and choose the profile for your hardware."), ("2", "Export the .ctrl2 file when you want to add that controller to LiveProfessor."), ("3", "Click AutoMap, choose a .rack2 project, and analyze it."), ("4", "Select the required plug-ins and create a new project copy."), ("5", "Load the .ctrl2 file and the AutoMap copy in LiveProfessor.")]),
                    ("callout", "Always preserve the original LiveProfessor project. Work only with the copy created by AutoMap."),
                ],
            ),
            (
                "2. Choose a controller and use Live mode",
                [
                    ("h2", "Controller bank"),
                    ("p", "Each profile describes MIDI controls, banks, pushes, feedback, and capabilities. Its status identifies it as built-in, verified, local, or community supplied."),
                    ("h2", "Active controller"),
                    ("p", "The Live page selector stays synchronized with the bank. When a real-time driver is available, Start, Stop, bank, and matching settings become available. Otherwise, the profile remains ready for export and AutoMap."),
                    ("h2", "Export to LiveProfessor"),
                    ("steps", [("1", "Select the controller in the bank."), ("2", "Click Export controller .ctrl2."), ("3", "In LiveProfessor, open Hardware Controllers Setup, then Load from file.")]),
                ],
            ),
            (
                "3. Create an AutoMap copy",
                [
                    ("h2", "Analyze and choose"),
                    ("steps", [("1", "Choose the source project, then click Analyze."), ("2", "Choose the controller profile and preferably reuse the controller already present in the project."), ("3", "Select all plug-ins or check only the required instances."), ("4", "Choose the number of controls per bank, then create the copy.")]),
                    ("h2", "Parameter order"),
                    ("p", "Existing manual assignments remain authoritative. Free slots then follow the Plugin Studio profile so every instance of a plug-in type keeps the same order."),
                    ("callout", "Multiple controllers sharing the same Companion addresses can mix labels. Reuse the existing controller when the assistant offers it."),
                ],
            ),
            (
                "4. Organize parameters with Plugin Studio",
                [
                    ("h2", "Recognize a plug-in"),
                    ("steps", [("1", "Open the Plug-ins tab and choose a .rack2 project."), ("2", "Analyze the project; matching instances are grouped automatically."), ("3", "Open the profile for one plug-in type."), ("4", "In the LiveProfessor top bar, recall SiLeMI/O AutoMap - PluginName, not the Dynamic map."), ("5", "Click Automatically retrieve real names."), ("6", "Use Select all, Select none, or individual checkboxes to choose AutoMap parameters."), ("7", "Adjust names and priorities if needed, save locally, then use the profile in AutoMap.")]),
                    ("h2", "Safe local profiles"),
                    ("p", "Profiles are declarative JSON files. Replaced versions can be backed up, downloaded code is never executed, and the analyzed project remains unchanged."),
                ],
            ),
            (
                "5. Profile library",
                [
                    ("h2", "Update"),
                    ("p", "The public library provides controller and plug-in profiles. Preview changes before installing them, then keep working offline from the local cache."),
                    ("h2", "Contribute"),
                    ("p", "In Controller bank, Submit to the library validates the selected profile, copies its JSON, and opens a pre-titled GitHub form. Paste the JSON, add available documentation or test results, then submit it."),
                    ("bullets", ["strict format validation;", "version and SHA-256 checks;", "backup before replacement;", "no executable code in profiles."]),
                ],
            ),
            (
                "6. Interface, log, and updates",
                [
                    ("h2", "A simple first page"),
                    ("p", "The Live page keeps only the active controller, essential actions, status, and last event. MIDI/OSC connections are under Settings, and the complete log opens in a separate window."),
                    ("h2", "Language and notification area"),
                    ("p", "Options > Language switches immediately between French and English. Minimizing to the notification area hides the window without stopping an active engine; Quit actually stops the application."),
                    ("h2", "Manual, updates, and support"),
                    ("p", "Help opens the manual in the active language and checks stable releases. Installer size and SHA-256 are verified before launch."),
                    ("support", "PayPal support is optional. Every feature remains available free of charge."),
                ],
            ),
            (
                "7. Safety and troubleshooting",
                [
                    ("h2", "When a label does not match a control"),
                    ("steps", [("1", "Check that only one Companion controller uses the same address range."), ("2", "Open AutoMap again and reuse the controller already in the project."), ("3", "Check the Plugin Studio order and preserved manual assignments."), ("4", "Create a fresh copy from the preserved source project.")]),
                    ("h2", "Diagnostics"),
                    ("p", "The separate log window can copy events or open the complete file. Diagnostics checks ports, configuration, and engine state without changing the LiveProfessor project."),
                ],
            ),
        ],
    },
}


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=29, textColor=NAVY, alignment=TA_CENTER, spaceAfter=5 * mm),
        "manual": ParagraphStyle("Manual", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=BLUE, alignment=TA_CENTER, tracking=1.2),
        "subtitle": ParagraphStyle("Subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=12, leading=17, textColor=MID, alignment=TA_CENTER),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=NAVY, spaceAfter=5 * mm),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=BLUE, spaceBefore=3 * mm, spaceAfter=2 * mm),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.3, leading=13.2, textColor=NAVY, alignment=TA_LEFT, spaceAfter=2.5 * mm),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=8, leading=11, textColor=MID, alignment=TA_CENTER),
        "toc": ParagraphStyle("Toc", parent=base["BodyText"], fontName="Helvetica", fontSize=10, leading=15, leftIndent=5 * mm, textColor=NAVY),
        "bullet": ParagraphStyle("Bullet", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13, leftIndent=6 * mm, firstLineIndent=-3 * mm, textColor=NAVY, spaceAfter=1.5 * mm),
        "callout": ParagraphStyle("Callout", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9.2, leading=13, textColor=NAVY, leftIndent=3 * mm, rightIndent=3 * mm),
        "table_header": ParagraphStyle("TableHeader", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=9.3, leading=13.2, textColor=colors.white, alignment=TA_LEFT),
    }


def page_footer(canvas, document):
    canvas.saveState()
    width, _height = A4
    canvas.setStrokeColor(colors.HexColor("#D8E2E6"))
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MID)
    canvas.drawString(18 * mm, 9.5 * mm, "Controller Studio for LiveProfessor")
    canvas.drawRightString(width - 18 * mm, 9.5 * mm, f"{document.page}")
    canvas.restoreState()


def styled_table(rows, style, widths=None):
    formatted = []
    for row_index, row in enumerate(rows):
        paragraph_style = style["table_header"] if row_index == 0 else style["body"]
        formatted.append([Paragraph(str(cell), paragraph_style) for cell in row])
    table = Table(formatted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C7D6DC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def add_blocks(story, blocks, style):
    for kind, payload in blocks:
        if kind == "h2":
            story.append(Paragraph(payload, style["h2"]))
        elif kind == "p":
            story.append(Paragraph(payload, style["body"]))
        elif kind == "callout":
            box = Table([[Paragraph(payload, style["callout"])]], colWidths=[166 * mm])
            box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.8, CYAN), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
            story.extend([box, Spacer(1, 2 * mm)])
        elif kind == "bullets":
            for item in payload:
                story.append(Paragraph(f"- {item}", style["bullet"]))
        elif kind == "steps":
            rows = [
                [Paragraph(str(number), style["body"]), Paragraph(text, style["body"])]
                for number, text in payload
            ]
            table = Table(rows, colWidths=[12 * mm, 154 * mm])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                        ("BACKGROUND", (0, 0), (0, -1), PALE),
                        ("TEXTCOLOR", (0, 0), (0, -1), BLUE),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C7D6DC")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.extend([table, Spacer(1, 2 * mm)])
        elif kind == "table":
            columns = len(payload[0])
            widths = [32 * mm, 35 * mm, 99 * mm] if columns == 3 else [42 * mm, 124 * mm]
            story.extend([styled_table(payload, style, widths=widths), Spacer(1, 2 * mm)])
        elif kind == "support":
            qr = Image(str(PAYPAL_QR), width=34 * mm, height=34 * mm)
            text = Paragraph(f"{payload}<br/><br/><font color='#087D9D'>https://www.paypal.com/paypalme/MamatLeroy</font>", style["body"])
            table = Table([[qr, text]], colWidths=[42 * mm, 124 * mm])
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.8, CYAN), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
            story.append(table)


def build_manual(language: str) -> Path:
    data = CONTENT[language]
    style = styles()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / data["filename"]
    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=20 * mm,
        title=f"Controller Studio for LiveProfessor - {data['manual']}",
        author="Mamat / SiLeMI/O",
        subject="Controller Studio for LiveProfessor",
    )
    story = [Spacer(1, 15 * mm)]
    if ICON.is_file():
        story.extend([Image(str(ICON), width=39 * mm, height=39 * mm), Spacer(1, 7 * mm)])
    story.extend(
        [
            Paragraph(data["manual"], style["manual"]),
            Spacer(1, 3 * mm),
            Paragraph("Controller Studio", style["title"]),
            Paragraph("for LiveProfessor", style["subtitle"]),
            Spacer(1, 8 * mm),
            Paragraph(data["subtitle"], style["subtitle"]),
            Spacer(1, 13 * mm),
            Paragraph(f"{data['edition']} - {DISPLAY_VERSION}", style["small"]),
            Paragraph("SiLeMI/O - By Mamat  -------[]--", style["small"]),
            Spacer(1, 12 * mm),
        ]
    )
    cover_box = Table([[Paragraph(data["source_safe"], style["callout"])]], colWidths=[145 * mm])
    cover_box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.8, CYAN), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story.extend([cover_box, Spacer(1, 8 * mm), Paragraph(data["independent"], style["small"]), PageBreak()])
    story.extend([Paragraph(data["contents"], style["h1"]), Spacer(1, 3 * mm)])
    for entry in data["toc"]:
        story.append(Paragraph(entry, style["toc"]))
        story.append(Spacer(1, 1.5 * mm))
    story.append(PageBreak())
    for index, (title, blocks) in enumerate(data["sections"]):
        story.append(Paragraph(title, style["h1"]))
        add_blocks(story, blocks, style)
        if index != len(data["sections"]) - 1:
            story.append(PageBreak())
    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    packaged = PACKAGE_DIR / data["filename"]
    shutil.copy2(output, packaged)
    return output


def main() -> int:
    for language in ("fr", "en"):
        output = build_manual(language)
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
