from __future__ import annotations

import argparse
import logging
import os
import queue
import shutil
import sys
import threading
import time
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _WIN_UINT_PTR = (
        wintypes.UINT_PTR
        if hasattr(wintypes, "UINT_PTR")
        else (ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32)
    )

    class NOTIFYICONDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HANDLE),
            ("szTip", wintypes.WCHAR * 128),
        ]

    LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HANDLE),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HANDLE),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
            ("hIconSm", wintypes.HANDLE),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    _WIN_USER = 0x0400
    _WM_TASKBARICON = _WIN_USER + 1
    _WM_LBUTTONUP = 0x0202
    _WM_LBUTTONDOWN = 0x0201
    _WM_LBUTTONDBLCLK = 0x0203
    _WM_RBUTTONUP = 0x0205
    _WM_RBUTTONDOWN = 0x0204
    _WM_CONTEXTMENU = 0x007B
    _HWND_MESSAGE = -3
    _NIM_ADD = 0x0
    _NIM_MODIFY = 0x1
    _NIM_DELETE = 0x2
    _NIF_MESSAGE = 0x1
    _NIF_ICON = 0x2
    _NIF_TIP = 0x4
    _IDI_APPLICATION = 32512
    _IMAGE_ICON = 1
    _LR_LOADFROMFILE = 0x10
    _LR_DEFAULTSIZE = 0x40
    _MF_STRING = 0x0000
    _MF_SEPARATOR = 0x0800
    _MF_GRAYED = 0x00000001
    _MF_DISABLED = 0x00000002
    _TPM_RIGHTBUTTON = 0x0002
    _TPM_RETURN_CMD = 0x0100
    _TPM_NONOTIFY = 0x0080
    _TRAY_MENU_OPEN = 3001
    _TRAY_MENU_START = 3002
    _TRAY_MENU_STOP = 3003
    _TRAY_MENU_RESTART = 3004
    _TRAY_MENU_LOG = 3005
    _TRAY_MENU_UPDATE = 3006
    _TRAY_MENU_QUIT = 3007

from . import __version__
from .bridge import BridgeSnapshot, EC4LiveProfessorBridge
from .config import BridgeConfig, default_config_path, default_data_dir, load_config, save_config
from .ec4_protocol import main_display_message, parameter_grid_message, total_display_message
from .external_links import (
    CONTRIBUTE_URL,
    ISSUES_URL,
    PAYPAL_URL,
    RELEASES_URL,
    REPOSITORY_URL,
    open_external_url,
)
from .midi_backend import MidiBackendError, input_names, output_names
from .osc_codec import decode_message, encode_message
from .update_service import ReleaseInfo, fetch_latest_release, is_newer_version


CONTROLLER_TEMPLATES = (
    "Ec4-UniBank.ctrl2",
    "Ec4-FullBank.ctrl2",
)


def controller_template_path(
    filename: str = "Ec4-FullBank.ctrl2",
    candidates: list[Path] | None = None,
) -> Path:
    """Locate the neutral LiveProfessor controller shipped with the bridge."""

    if filename not in CONTROLLER_TEMPLATES:
        raise ValueError(f"modele de controleur inconnu: {filename}")
    if candidates is None:
        candidates = []
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            candidates.append(Path(bundle_dir) / filename)
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / filename)
        candidates.extend(
            [
                Path(__file__).resolve().parents[2] / filename,
                Path.cwd() / filename,
            ]
        )

    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError(f"{filename} est absent de l'application")


def copy_controller_template(destination: Path, source: Path | None = None) -> Path:
    source_path = (source or controller_template_path()).resolve()
    destination_path = Path(destination).expanduser()
    if destination_path.is_dir():
        destination_path = destination_path / source_path.name
    destination_path = destination_path.resolve()
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path != destination_path:
        shutil.copy2(source_path, destination_path)
    return destination_path


def tray_action_for_event(l_param: int) -> str | None:
    # Windows can provide the notification either as a plain mouse message
    # (legacy NOTIFYICONDATA behavior) or packed in the low word of lParam
    # (NOTIFYICON_VERSION_4 / recent Windows shells).  Comparing the complete
    # pointer-sized value made real clicks look unknown while synthetic tests
    # using a plain 0x0202 succeeded.
    event_code = int(l_param) & 0xFFFF
    if event_code in (0x0202, 0x0203):
        return "open"
    if event_code in (0x0205, 0x007B):
        return "menu"
    return None


def configure_logging(level: str = "INFO") -> Path:
    data_dir = default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "bridge.log"
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not root.handlers:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        file_handler = RotatingFileHandler(
            log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        if not getattr(sys, "frozen", False):
            console = logging.StreamHandler()
            console.setFormatter(formatter)
            root.addHandler(console)
    return log_path


def protocol_self_test() -> list[str]:
    results: list[str] = []
    packet = encode_message("/EC4/Test", [1, 0.5, "ok", True])
    address, args = decode_message(packet)
    assert address == "/EC4/Test" and args[0] == 1 and args[2] == "ok" and args[3] is True
    results.append("OSC encode/decode: OK")
    main = main_display_message([f"P{i + 1}" for i in range(16)])
    assert main[0] == 0xF0 and main[-1] == 0xF7 and len(main) == 206
    results.append("SysEx affichage principal: OK")
    total = total_display_message(["EC4", "LiveProfessor", "Banque 1", "Test"])
    assert total[0] == 0xF0 and total[-1] == 0xF7 and len(total) == 257
    results.append("SysEx affichage total: OK")
    grid = parameter_grid_message([f"P{i + 1}" for i in range(16)])
    assert grid[0] == 0xF0 and grid[-1] == 0xF7 and len(grid) == 257
    results.append("SysEx grille de parametres: OK")
    for filename in CONTROLLER_TEMPLATES:
        controller = controller_template_path(filename)
        assert controller.is_file() and controller.stat().st_size > 0
        results.append(f"Controleur LiveProfessor {filename}: OK")
    return results


UI_TEXT = {
    "fr": {
        "window_title": "EC4 Bridge {version} | SiLeMI/O | By Mamat",
        "mode_label": "Mode LiveProfessor",
        "mode_help": "Companion: noms/valeurs dynamiques | Generic: libelles de profil",
        "mode_companion": "companion",
        "mode_generic": "generic",
        "midi_in_label": "Entree MIDI",
        "midi_out_label": "Sortie MIDI",
        "refresh_ports": "Actualiser les ports MIDI",
        "lp_host_label": "Adresse LiveProfessor",
        "lp_port_label": "Port LP",
        "lp_return_label": "Retour",
        "profile_label": "Profil de noms (optionnel)",
        "zone_label": "Zone EC4 dédiee",
        "setup_label": "Setup",
        "group_label": "Groupe",
        "use_current_target": "Utiliser le setup/groupe actuel",
        "mapping_label": "Mapping des encodeurs",
        "learn_button": "Apprendre rotatifs + push",
        "learn_cancel": "Annuler l'apprentissage",
        "learning_progress": "Tournez l'encodeur 1",
        "learn_rotary_prompt": "Tournez le rotatif {index}",
        "learn_push_prompt": "Appuyez sur le push {index}",
        "display_check": "Activer l'affichage SysEx EC4",
        "persistent_check": "Afficher en permanence les parametres du plugin selectionne",
        "speed_section": "Réactivité (ms)",
        "speed_overlay_interval": "Mise a jour de l'overlay (1-2000)",
        "speed_refresh_companion": "Refresh Companion apres commande (1-2000)",
        "speed_refresh_label": "Refresh nom/label (1-2000)",
        "speed_feedback_timeout": "Timeout retour LiveProfessor (100-10000)",
        "speed_overlay_duration": "Duree overlay (200-5000)",
        "start": "Démarrer",
        "stop": "Arrêter",
        "save": "Enregistrer",
        "diagnostic": "Diagnostic",
        "shortcuts": "Raccourcis EC4",
        "copy_controller_unibank": "CTRL2 UniBank…",
        "copy_controller_fullbank": "CTRL2 FullBank…",
        "controller_guide": "Comment importer les CTRL2…",
        "controller_copy_title": "Copier le contrôleur LiveProfessor {name}",
        "controller_file_type": "Contrôleur LiveProfessor",
        "controller_missing_title": "Fichier contrôleur introuvable",
        "controller_missing_message": "Le fichier {name} intégré est introuvable.",
        "controller_copy_error_title": "Copie impossible",
        "controller_copy_success_title": "Contrôleur copié",
        "controller_copy_success": "Le fichier a été copié ici :\n{path}",
        "controller_guide_title": "Importer un CTRL2 dans LiveProfessor",
        "controller_guide_text": (
            "Choisissez d'abord le modèle adapté :\n"
            "• UniBank : 16 rotatifs, pour une seule banque simple.\n"
            "• FullBank : 99 rotatifs, pour utiliser toutes les banques du bridge.\n"
            "Les deux modèles contiennent 16 boutons.\n\n"
            "1. Dans le bridge, choisissez Outils > CTRL2 UniBank ou CTRL2 FullBank "
            "et enregistrez le fichier dans un dossier facile à retrouver.\n"
            "2. Dans LiveProfessor, ouvrez Controllers > Hardware Controllers Setup.\n"
            "3. Cliquez sur Load from file / Charger depuis un fichier.\n"
            "4. Sélectionnez le fichier CTRL2 copié.\n"
            "5. Sélectionnez le contrôleur EC4 importé et vérifiez : "
            "127.0.0.1, entrée 8010, retour 8011.\n"
            "6. Ouvrez Map Controllers pour affecter les Rotary disponibles et "
            "GenericButton1 à GenericButton15 aux paramètres du plugin.\n\n"
            "Pour un bouton marche/arrêt, activez la transformation Toggle. "
            "Le push 16 reste réservé au Tap Tempo."
        ),
        "test_display": "Tester l'ecran EC4",
        "minimize": "Réduire",
        "quit": "Quitter",
        "state_frame": "Etat",
        "status_stopped": "Arrêté",
        "bank_previous": "Banque precedente",
        "bank_next": "Banque suivante",
        "log_frame": "Journal",
        "language_label": "Langue",
        "language_note": "Changement immédiat.",
        "invalid_configuration": "Configuration invalide",
        "bridge_start_error_title": "Démarrage impossible",
        "bridge_stopped_title": "Pont arrêté",
        "bridge_start_msg": "Démarrez d'abord le pont.",
        "ec4_absent_title": "EC4 absent",
        "ec4_absent_msg": "Connectez l'EC4 puis attendez l'état Connecté.",
        "unknown_state_title": "Etat EC4 inconnu",
        "unknown_state_message": "Changez une fois de setup ou de groupe sur l'EC4, puis recommencez.",
        "wrong_zone_title": "Mauvaise zone EC4",
        "wrong_zone_message": "Sélectionnez d'abord le setup {setup}, groupe {group} sur l'EC4.",
        "learn_progress_title": "Apprentissage MIDI",
        "learn_progress_message": "Phase 1 : tournez légèrement le rotatif 1, puis le 2, jusqu'au 16. "
        "Phase 2 : vous appuierez ensuite sur leurs 16 push dans le même ordre.",
        "learn_phase2_title": "Rotatifs termines",
        "learn_phase2_message": "Appuyez maintenant une fois sur le push 1, puis 2, jusqu'au 16.",
        "learn_complete_title": "Apprentissage terminé",
        "learn_complete_message": "Les 16 encodeurs sont enregistres.",
        "learn_cancelled_status": "Apprentissage annule",
        "diagnostic_title": "Diagnostic",
        "shortcuts_title": "Raccourcis EC4",
        "shortcuts_text": (
            "Shift + push 1 / 2 : banque precedente / suivante\n"
            "Shift + push 3 / 4 : Viewset precedent / suivant\n\n"
            "Shift + push 5 : afficher / masquer le plugin\n"
            "Shift + push 9 : activer / desactiver le plugin\n"
            "Shift + push 6 : chaine precedente\n"
            "Shift + push 7 / 8 : plugin precedent / suivant\n"
            "Shift + push 10 : chaine suivante\n"
            "Shift + push 11 / 12 : plugin precedent / suivant\n"
            "Shift + push 13 / 14 : cue precedent / suivant\n"
            "Shift + push 15 / 16 : snapshot precedent / suivant\n"
            "Push 16 seul : Tap Tempo"
        ),
        "learn_default_label": "Mapping Ableton par defaut",
        "learn_saved_label": "Mapping appris et enregistre",
        "tray_open": "Ouvrir",
        "tray_start": "Démarrer le serveur",
        "tray_stop": "Arrêter le serveur",
        "tray_restart": "Redémarrer le serveur",
        "tray_log": "Ouvrir le journal",
        "tray_update": "Vérifier les mises à jour",
        "tray_quit": "Quitter",
        "menu_file": "Fichier",
        "menu_view": "Affichage",
        "menu_tools": "Outils",
        "menu_help": "Aide",
        "settings": "Réglages…",
        "connections": "Connexions et rafraîchissement…",
        "log_window": "Journal…",
        "updates": "Vérifier les mises à jour…",
        "about": "À propos",
        "repository": "Dépôt GitHub",
        "releases": "Releases GitHub",
        "report_bug": "Signaler un bug",
        "contribute": "Contribuer",
        "support": "Soutenir via PayPal",
        "last_event": "Dernier événement",
        "save_close": "Enregistrer et fermer",
        "open_log_file": "Ouvrir le fichier",
        "open_log_folder": "Ouvrir le dossier",
        "copy_all": "Copier tout",
        "clear_display": "Effacer l’affichage",
        "refresh_companion": "Rafraîchir Companion",
        "reconnect_ec4": "Reconnecter l’EC4",
        "request_setup": "Redemander setup/groupe",
        "check_updates_startup": "Vérifier les mises à jour au démarrage",
        "minimize_on_close": "Réduire dans la zone de notification à la fermeture",
        "language_en": "English",
        "language_fr": "Français",
        "bank_label": "Banque",
    },
    "en": {
        "window_title": "EC4 Bridge {version} | SiLeMI/O | By Mamat",
        "mode_label": "LiveProfessor mode",
        "mode_help": "Companion: dynamic names/values | Generic: profile labels",
        "mode_companion": "companion",
        "mode_generic": "generic",
        "midi_in_label": "MIDI Input",
        "midi_out_label": "MIDI Output",
        "refresh_ports": "Refresh MIDI ports",
        "lp_host_label": "LiveProfessor Address",
        "lp_port_label": "LP Port",
        "lp_return_label": "Feedback",
        "profile_label": "Name profile (optional)",
        "zone_label": "EC4 dedicated zone",
        "setup_label": "Setup",
        "group_label": "Group",
        "use_current_target": "Use current setup/group",
        "mapping_label": "Encoder mapping",
        "learn_button": "Learn rotaries + push",
        "learn_cancel": "Cancel learn",
        "learning_progress": "Turn rotary 1",
        "learn_rotary_prompt": "Turn rotary {index}",
        "learn_push_prompt": "Press push {index}",
        "display_check": "Enable EC4 SysEx display",
        "persistent_check": "Keep plugin parameters visible",
        "speed_section": "Responsiveness (ms)",
        "speed_overlay_interval": "Parameter overlay update (1-2000)",
        "speed_refresh_companion": "Refresh Companion after command (1-2000)",
        "speed_refresh_label": "Label refresh (1-2000)",
        "speed_feedback_timeout": "LiveProfessor feedback timeout (100-10000)",
        "speed_overlay_duration": "Overlay duration (200-5000)",
        "start": "Start",
        "stop": "Stop",
        "save": "Save",
        "diagnostic": "Diagnostics",
        "shortcuts": "EC4 shortcuts",
        "copy_controller_unibank": "UniBank CTRL2…",
        "copy_controller_fullbank": "FullBank CTRL2…",
        "controller_guide": "How to import the CTRL2 files…",
        "controller_copy_title": "Copy the {name} LiveProfessor controller",
        "controller_file_type": "LiveProfessor controller",
        "controller_missing_title": "Controller file not found",
        "controller_missing_message": "The embedded {name} file could not be found.",
        "controller_copy_error_title": "Copy failed",
        "controller_copy_success_title": "Controller copied",
        "controller_copy_success": "The file was copied here:\n{path}",
        "controller_guide_title": "Import a CTRL2 file into LiveProfessor",
        "controller_guide_text": (
            "First choose the appropriate template:\n"
            "• UniBank: 16 rotaries for a single, simple bank.\n"
            "• FullBank: 99 rotaries to use every bridge bank.\n"
            "Both templates contain 16 buttons.\n\n"
            "1. In the bridge, choose Tools > UniBank CTRL2 or FullBank CTRL2 "
            "and save the file in an easy-to-find folder.\n"
            "2. In LiveProfessor, open Controllers > Hardware Controllers Setup.\n"
            "3. Click Load from file.\n"
            "4. Select the copied CTRL2 file.\n"
            "5. Select the imported EC4 controller and verify: "
            "127.0.0.1, input 8010, feedback 8011.\n"
            "6. Open Map Controllers and assign the available Rotary controls and "
            "GenericButton1 through GenericButton15 to plugin parameters.\n\n"
            "Enable the Toggle transformation for an on/off parameter. "
            "Push 16 remains reserved for Tap Tempo."
        ),
        "test_display": "Test EC4 screen",
        "minimize": "Minimize",
        "quit": "Quit",
        "state_frame": "Status",
        "status_stopped": "Stopped",
        "bank_previous": "Previous bank",
        "bank_next": "Next bank",
        "log_frame": "Log",
        "language_label": "Language",
        "language_note": "Changes apply immediately.",
        "invalid_configuration": "Invalid configuration",
        "bridge_start_error_title": "Cannot start",
        "bridge_stopped_title": "Bridge stopped",
        "bridge_start_msg": "Start the bridge first.",
        "ec4_absent_title": "EC4 absent",
        "ec4_absent_msg": "Connect the EC4 and wait for status CONNECTED.",
        "unknown_state_title": "Unknown EC4 state",
        "unknown_state_message": "Change setup or group on EC4 once, then try again.",
        "wrong_zone_title": "Wrong EC4 zone",
        "wrong_zone_message": "Select setup {setup}, group {group} on EC4 first.",
        "learn_progress_title": "MIDI learn",
        "learn_progress_message": (
            "Phase 1: turn rotary 1, then 2, ... to 16. "
            "Phase 2: press all 16 pushes in the same order."
        ),
        "learn_phase2_title": "Rotaries done",
        "learn_phase2_message": "Press push 1 then 2 ... up to 16 once each.",
        "learn_complete_title": "Learning done",
        "learn_complete_message": "The 16 encoders are now mapped.",
        "learn_cancelled_status": "Learning cancelled",
        "diagnostic_title": "Diagnostics",
        "shortcuts_title": "EC4 shortcuts",
        "shortcuts_text": (
            "Shift + push 1 / 2: previous / next bank\n"
            "Shift + push 3 / 4: previous / next viewset\n\n"
            "Shift + push 5: show / hide selected plugin\n"
            "Shift + push 9: enable / disable selected plugin\n"
            "Shift + push 6: previous chain\n"
            "Shift + push 7 / 8: previous / next plugin\n"
            "Shift + push 10: next chain\n"
            "Shift + push 11 / 12: previous / next plugin\n"
            "Shift + push 13 / 14: previous / next cue\n"
            "Shift + push 15 / 16: previous / next global snapshot\n"
            "Push 16 only: Tap Tempo"
        ),
        "learn_default_label": "Default Ableton mapping",
        "learn_saved_label": "Learning saved",
        "tray_open": "Open",
        "tray_start": "Start bridge",
        "tray_stop": "Stop bridge",
        "tray_restart": "Restart bridge",
        "tray_log": "Open log",
        "tray_update": "Check for updates",
        "tray_quit": "Quit",
        "menu_file": "File",
        "menu_view": "View",
        "menu_tools": "Tools",
        "menu_help": "Help",
        "settings": "Settings…",
        "connections": "Connections and refresh…",
        "log_window": "Log…",
        "updates": "Check for updates…",
        "about": "About",
        "repository": "GitHub repository",
        "releases": "GitHub releases",
        "report_bug": "Report a bug",
        "contribute": "Contribute",
        "support": "Support via PayPal",
        "last_event": "Last event",
        "save_close": "Save and close",
        "open_log_file": "Open file",
        "open_log_folder": "Open folder",
        "copy_all": "Copy all",
        "clear_display": "Clear display",
        "refresh_companion": "Refresh Companion",
        "reconnect_ec4": "Reconnect EC4",
        "request_setup": "Request setup/group again",
        "check_updates_startup": "Check for updates on startup",
        "minimize_on_close": "Minimize to notification area on close",
        "language_en": "English",
        "language_fr": "French",
        "bank_label": "Bank",
    },
}


class BridgeGUI:
    def __init__(self, config_path: Path) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.config_path = config_path
        self.config = load_config(config_path)
        self.bridge: EC4LiveProfessorBridge | None = None

        self.root = tk.Tk()
        self.ui_language_var = tk.StringVar(master=self.root, value=self.config.ui_language)
        self.root.title(self._t("window_title", version=__version__))
        self.root.geometry("760x470")
        self.root.minsize(680, 420)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._suppress_unmap = False
        self.root.bind("<Unmap>", self._on_root_unmap)
        self._tray_ready = False
        self._tray_icon_created = False
        self._tray_action_queue: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._tray_poll_after_id = None
        self._tray_data: NOTIFYICONDATA | None = None
        self._tray_window_proc_handle = None
        self._tray_loaded_icon = None
        self._tray_uses_file_icon = False
        self._tray_icon_path = str((Path(__file__).resolve().parent / "assets" / "ec4lp.ico").resolve())
        if sys.platform != "win32":
            self._tray_ready = False
        if sys.platform == "win32":
            self._setup_tray_infrastructure()

        self.mode_var = tk.StringVar(value=self.config.mode)
        self.midi_in_var = tk.StringVar(value=self.config.midi_input)
        self.midi_out_var = tk.StringVar(value=self.config.midi_output)
        self.host_var = tk.StringVar(value=self.config.liveprofessor_host)
        self.lp_port_var = tk.StringVar(value=str(self.config.liveprofessor_port))
        self.feedback_port_var = tk.StringVar(value=str(self.config.feedback_port))
        self.profile_var = tk.StringVar(value=self.config.profile_file)
        self.display_var = tk.BooleanVar(value=self.config.display_enabled)
        self.persistent_display_var = tk.BooleanVar(
            value=self.config.persistent_parameter_display
        )
        self.minimize_on_close_var = tk.BooleanVar(
            value=self.config.minimize_to_tray_on_close
        )
        self.check_updates_var = tk.BooleanVar(
            value=self.config.check_updates_on_startup
        )
        self.parameter_overlay_interval_var = tk.StringVar(
            value=str(self.config.parameter_overlay_interval_ms)
        )
        self.companion_refresh_delay_var = tk.StringVar(
            value=str(self.config.companion_refresh_delay_ms)
        )
        self.name_refresh_delay_var = tk.StringVar(
            value=str(self.config.name_refresh_delay_ms)
        )
        self.feedback_timeout_var = tk.StringVar(
            value=str(self.config.feedback_confirm_timeout_ms)
        )
        self.overlay_display_duration_var = tk.StringVar(
            value=str(self.config.overlay_display_duration_ms)
        )
        self.ui_language_var.trace_add("write", self._on_language_change)
        self.target_setup_var = tk.StringVar(value=str(self.config.target_setup))
        self.target_group_var = tk.StringVar(value=str(self.config.target_group))
        self.status_var = tk.StringVar(value=self._t("status_stopped"))
        self.bank_var = tk.StringVar(value=f"{self._t('bank_label')} 1")
        self.learn_var = tk.StringVar(value=self._t("learn_default_label"))
        self.last_event_var = tk.StringVar(value="—")
        self._status_key = "status_stopped"
        self._language_bindings = []
        self._learn_controls: list[tuple[int, int]] = []
        self._learn_pushes: list[tuple[int, int]] = []
        self._learn_phase = ""
        self._learning = False
        self._closing = False
        self._log_lines: list[str] = []
        self.settings_window = None
        self.log_window = None
        self.connections_window = None
        self.about_window = None
        self._tray_icon_path = str((Path(__file__).resolve().parent / "assets" / "ec4lp.ico").resolve())

        self._build()
        self._tray_poll_after_id = self.root.after(50, self._poll_tray_actions)
        self._update_mapping_status()
        self.refresh_ports()
        self._append_log(f"Configuration: {self.config_path}")
        if self.config.check_updates_on_startup:
            self.root.after(1500, lambda: self.check_updates(silent=True))

    def _language_code(self) -> str:
        value = "fr"
        if hasattr(self, "ui_language_var"):
            value = str(self.ui_language_var.get()).strip().lower()
        elif hasattr(self, "config") and hasattr(self.config, "ui_language"):
            value = str(self.config.ui_language).strip().lower()
        return value if value in {"fr", "en"} else "fr"

    def _t(self, key: str, **format_args: object) -> str:
        value = UI_TEXT.get(self._language_code(), {}).get(key, key)
        if isinstance(value, str):
            return value.format(**format_args) if format_args else value
        return str(key)

    def _on_language_change(self, *_) -> None:
        self.config.ui_language = self._language_code()
        self.root.title(self._t("window_title", version=__version__))
        self._refresh_language()
        self._rebuild_visible_secondary_windows()

    def _rebuild_visible_secondary_windows(self) -> None:
        windows = (
            ("settings_window", self.show_settings),
            ("log_window", self.show_log_window),
            ("connections_window", self.show_connections_window),
        )
        for attribute, opener in windows:
            window = getattr(self, attribute, None)
            if window is None or not window.winfo_exists() or window.state() == "withdrawn":
                continue
            if attribute == "settings_window":
                if hasattr(self, "input_combo"):
                    del self.input_combo
                if hasattr(self, "output_combo"):
                    del self.output_combo
            window.destroy()
            setattr(self, attribute, None)
            self.root.after_idle(opener)

    def _register_text_widget(
        self,
        widget: object,
        option: str,
        key: str,
    ) -> None:
        self._language_bindings.append((widget, option, key))

    def _set_window_icons(self) -> None:
        if sys.platform != "win32":
            return
        icon_path = Path(self._tray_icon_path) if hasattr(self, "_tray_icon_path") else None
        if icon_path is None or not icon_path.exists():
            return
        try:
            self.root.call("wm", "iconphoto", self.root._w, "")
            self.root.iconbitmap(default=str(icon_path))
            self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _refresh_language(self) -> None:
        for widget, option, key in self._language_bindings:
            try:
                widget.configure(**{option: self._t(key)})
            except Exception:
                pass
        if hasattr(self, "start_button"):
            self.start_button.configure(text=self._t("start"))
        if hasattr(self, "stop_button"):
            self.stop_button.configure(text=self._t("stop"))
        if hasattr(self, "learn_button"):
            self.learn_button.configure(
                text=self._t("learn_cancel" if self._learning else "learn_button")
            )
        if hasattr(self, "state_previous_button"):
            self.state_previous_button.configure(text=self._t("bank_previous"))
        if hasattr(self, "state_next_button"):
            self.state_next_button.configure(text=self._t("bank_next"))
        if self.status_var.get() in {
            self._t("status_stopped"),
            UI_TEXT["fr"].get("status_stopped", ""),
            UI_TEXT["en"].get("status_stopped", ""),
        }:
            self.status_var.set(self._t("status_stopped"))
        self._update_mapping_status()
        if hasattr(self, "menu_bar"):
            self._build_menu()

    def _ensure_tray_setup(self) -> None:
        if not sys.platform == "win32":
            return
        if self._tray_ready and self._tray_data is not None:
            return
        self._setup_tray_infrastructure()

    def _setup_tray_infrastructure(self) -> None:
        if sys.platform != "win32":
            return
        self._set_window_icons()
        if Path(self._tray_icon_path).exists():
            try:
                self.root.iconbitmap(self._tray_icon_path)
            except Exception:
                pass

        self._tray_ready = False
        self._tray_icon_created = False
        self._tray_data = None
        self._tray_window_proc_handle = None
        self._tray_loaded_icon = None
        self._tray_uses_file_icon = False
        self._track_popup_menu = None
        self._tray_hwnd = 0
        self._tray_class_name = ""
        self._tray_class_atom = 0
        self._tray_hinstance = None

        self.root.update_idletasks()
        self._tray_msg = _WM_TASKBARICON
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        self._user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self._user32.DefWindowProcW.restype = LRESULT
        self._user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
        self._user32.RegisterClassExW.restype = wintypes.WORD
        self._user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            ctypes.c_void_p,
        ]
        self._user32.CreateWindowExW.restype = wintypes.HWND
        self._user32.DestroyWindow.argtypes = [wintypes.HWND]
        self._user32.DestroyWindow.restype = ctypes.c_bool
        self._user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
        self._user32.UnregisterClassW.restype = ctypes.c_bool
        self._user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self._user32.SetForegroundWindow.restype = ctypes.c_bool
        self._user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        self._user32.GetCursorPos.restype = ctypes.c_int
        self._user32.CreatePopupMenu.argtypes = []
        self._user32.CreatePopupMenu.restype = wintypes.HMENU
        self._user32.AppendMenuW.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            _WIN_UINT_PTR,
            wintypes.LPCWSTR,
        ]
        self._user32.AppendMenuW.restype = ctypes.c_bool
        self._track_popup_menu = self._resolve_user32_function(
            ("TrackPopupMenuW", "TrackPopupMenu", "TrackPopupMenuA"),
            [
                wintypes.HMENU,
                wintypes.UINT,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.HWND,
                ctypes.c_void_p,
            ],
            ctypes.c_int,
        )
        if self._track_popup_menu is not None:
            self._track_popup_menu.argtypes = [
                wintypes.HMENU,
                wintypes.UINT,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.HWND,
                ctypes.c_void_p,
            ]
            self._track_popup_menu.restype = ctypes.c_int
        self._user32.DestroyMenu.argtypes = [wintypes.HMENU]
        self._user32.DestroyMenu.restype = ctypes.c_bool
        self._kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self._kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        self._shell32.Shell_NotifyIconW.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(NOTIFYICONDATA),
        ]
        self._shell32.Shell_NotifyIconW.restype = ctypes.c_bool

        icon = None
        if Path(self._tray_icon_path).exists():
            icon = self._user32.LoadImageW(
                None,
                str(self._tray_icon_path),
                _IMAGE_ICON,
                0,
                0,
                _LR_LOADFROMFILE | _LR_DEFAULTSIZE,
            )
            if icon:
                self._tray_uses_file_icon = True
        if not icon:
            icon = self._user32.LoadIconW(None, _IDI_APPLICATION)
        if not icon:
            icon = self._user32.LoadIconW(None, 1)
        if not icon:
            return

        try:
            self._tray_window_proc_handle = WNDPROC(self._on_tray_window_proc)
        except Exception:
            self._tray_window_proc_handle = None
        if self._tray_window_proc_handle is None:
            return

        self._tray_hinstance = self._kernel32.GetModuleHandleW(None)
        self._tray_class_name = (
            f"EC4LiveProfessorTray_{os.getpid()}_{id(self):x}"
        )
        window_class = WNDCLASSEXW()
        window_class.cbSize = ctypes.sizeof(WNDCLASSEXW)
        window_class.lpfnWndProc = self._tray_window_proc_handle
        window_class.hInstance = self._tray_hinstance
        window_class.lpszClassName = self._tray_class_name
        self._tray_class_atom = int(
            self._user32.RegisterClassExW(ctypes.byref(window_class))
        )
        if not self._tray_class_atom:
            self._tray_window_proc_handle = None
            return

        self._tray_hwnd = int(
            self._user32.CreateWindowExW(
                0,
                self._tray_class_name,
                self._tray_class_name,
                0,
                0,
                0,
                0,
                0,
                ctypes.c_void_p(_HWND_MESSAGE),
                None,
                self._tray_hinstance,
                None,
            )
            or 0
        )
        if not self._tray_hwnd:
            self._user32.UnregisterClassW(
                self._tray_class_name, self._tray_hinstance
            )
            self._tray_class_atom = 0
            self._tray_window_proc_handle = None
            return

        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        self._tray_loaded_icon = icon
        nid.hWnd = self._tray_hwnd
        nid.uID = 1
        nid.uFlags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP
        nid.uCallbackMessage = self._tray_msg
        nid.hIcon = ctypes.c_void_p(icon)
        nid.szTip = "EC4 Bridge"
        self._tray_data = nid
        self._tray_tip = nid.szTip
        self._tray_has_callback = True
        self._tray_ready = True
    def _resolve_user32_function(
        self,
        names: tuple[str, ...] | list[str],
        argtypes,
        restype,
    ):
        if not sys.platform == "win32":
            return None
        for name in names:
            try:
                return getattr(self._user32, name)
            except AttributeError:
                pass
            except Exception:
                continue

        try:
            GetModuleHandleW = self._kernel32.GetModuleHandleW
            GetProcAddress = self._kernel32.GetProcAddress
            GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            GetModuleHandleW.restype = ctypes.c_void_p
            GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            GetProcAddress.restype = ctypes.c_void_p
            module = GetModuleHandleW("user32.dll")
            if not module:
                return None
            for name in names:
                addr = GetProcAddress(module, str(name).encode("ascii"))
                if not addr:
                    continue
                return ctypes.WINFUNCTYPE(restype, *argtypes)(addr)
        except Exception:
            return None
        return None

    def _on_tray_window_proc(self, hwnd: int, msg: int, w_param: int, l_param: int) -> int:
        if msg == self._tray_msg:
            action = tray_action_for_event(l_param)
            if action is not None:
                self._tray_action_queue.put(action)
            return 0
        return self._user32.DefWindowProcW(hwnd, msg, w_param, l_param)

    def _poll_tray_actions(self) -> None:
        self._tray_poll_after_id = None
        if self._closing:
            return
        while True:
            try:
                action = self._tray_action_queue.get_nowait()
            except queue.Empty:
                break
            if action == "open":
                self._restore_from_tray()
            elif action == "menu":
                self._show_tray_menu()
        if not self._closing:
            self._tray_poll_after_id = self.root.after(50, self._poll_tray_actions)

    def _show_tray_context_fallback(self, x: int, y: int) -> None:
        menu = self.tk.Menu(self.root, tearoff=0)
        running = bool(self.bridge and self.bridge.running)
        menu.add_command(label=self._t("tray_open"), command=self._restore_from_tray)
        menu.add_separator()
        if running:
            menu.add_command(label=self._t("tray_start"), state="disabled")
            menu.add_command(label=self._t("tray_stop"), command=self.stop)
        else:
            menu.add_command(label=self._t("tray_start"), command=self.start)
            menu.add_command(label=self._t("tray_stop"), state="disabled")
        menu.add_command(label=self._t("tray_restart"), command=self.restart)
        menu.add_command(label=self._t("tray_log"), command=self.show_log_window)
        menu.add_command(label=self._t("tray_update"), command=self.check_updates)
        menu.add_separator()
        menu.add_command(label=self._t("tray_quit"), command=self.quit)

        try:
            menu.tk_popup(x, y)
            menu.grab_release()
        except Exception:
            pass
        finally:
            try:
                menu.unpost()
            except Exception:
                pass
            try:
                menu.destroy()
            except Exception:
                pass

    def _show_tray_menu(self) -> None:
        if sys.platform != "win32":
            return
        if not self._tray_ready:
            return
        self._ensure_tray_icon()
        if not self._tray_icon_created:
            return

        if self._track_popup_menu is None:
            point = POINT()
            if self._user32.GetCursorPos(ctypes.byref(point)) != 0:
                self._show_tray_context_fallback(int(point.x), int(point.y))
            return

        menu = self._user32.CreatePopupMenu()
        if not menu:
            return

        selected = 0
        selected_from_tracker = False
        try:
            running = bool(self.bridge and self.bridge.running)
            start_flags = _MF_STRING if not running else (_MF_GRAYED | _MF_DISABLED)
            stop_flags = _MF_STRING if running else (_MF_GRAYED | _MF_DISABLED)

            self._user32.AppendMenuW(menu, _MF_STRING, _TRAY_MENU_OPEN, self._t("tray_open"))
            self._user32.AppendMenuW(menu, _MF_SEPARATOR, 0, "")
            self._user32.AppendMenuW(menu, start_flags, _TRAY_MENU_START, self._t("tray_start"))
            self._user32.AppendMenuW(menu, stop_flags, _TRAY_MENU_STOP, self._t("tray_stop"))
            self._user32.AppendMenuW(menu, _MF_STRING, _TRAY_MENU_RESTART, self._t("tray_restart"))
            self._user32.AppendMenuW(menu, _MF_STRING, _TRAY_MENU_LOG, self._t("tray_log"))
            self._user32.AppendMenuW(menu, _MF_STRING, _TRAY_MENU_UPDATE, self._t("tray_update"))
            self._user32.AppendMenuW(menu, _MF_SEPARATOR, 0, "")
            self._user32.AppendMenuW(menu, _MF_STRING, _TRAY_MENU_QUIT, self._t("tray_quit"))

            if self._tray_hwnd:
                try:
                    self._user32.SetForegroundWindow(self._tray_hwnd)
                except Exception:
                    pass

            point = POINT()
            if self._user32.GetCursorPos(ctypes.byref(point)) != 0:
                selected = self._track_popup_menu(
                    menu,
                    _TPM_RIGHTBUTTON | _TPM_RETURN_CMD | _TPM_NONOTIFY,
                    int(point.x),
                    int(point.y),
                    0,
                    self._tray_hwnd,
                    None,
                )
                selected_from_tracker = True

            if selected == _TRAY_MENU_OPEN:
                self._restore_from_tray()
            elif selected == _TRAY_MENU_START:
                self.start()
            elif selected == _TRAY_MENU_STOP:
                self.stop()
            elif selected == _TRAY_MENU_RESTART:
                self.restart()
            elif selected == _TRAY_MENU_LOG:
                self.show_log_window()
            elif selected == _TRAY_MENU_UPDATE:
                self.check_updates()
            elif selected == _TRAY_MENU_QUIT:
                self.quit()
        except Exception:
            selected_from_tracker = False
            if self._user32.GetCursorPos(ctypes.byref(point)) != 0:
                self._show_tray_context_fallback(int(point.x), int(point.y))
        finally:
            try:
                self._user32.DestroyMenu(menu)
            except Exception:
                pass
            if not selected_from_tracker and selected == 0:
                # Explicit fallback only when no native menu item was successfully selected.
                pass

    def _restore_from_tray(self) -> None:
        if self._closing:
            return
        if sys.platform != "win32":
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            return
        try:
            self._ensure_tray_setup()
            if self._tray_ready and self._tray_data is not None:
                self._ensure_tray_icon()
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass

    def _on_root_unmap(self, _event: object) -> None:
        if self._suppress_unmap:
            return
        if self._closing:
            return
        try:
            if self.root.state() != "iconic":
                return
        except Exception:
            return
        self._suppress_unmap = True
        try:
            self.root.after_idle(self.minimize_to_taskbar)
        finally:
            self._suppress_unmap = False

    def _build_menu(self) -> None:
        tk = self.tk
        menu_bar = tk.Menu(self.root)
        running = bool(self.bridge and self.bridge.running)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(
            label=self._t("start"), command=self.start, state="disabled" if running else "normal"
        )
        file_menu.add_command(
            label=self._t("stop"), command=self.stop, state="normal" if running else "disabled"
        )
        file_menu.add_command(label=self._t("save"), command=self.save)
        file_menu.add_separator()
        file_menu.add_command(label=self._t("minimize"), command=self.minimize_to_taskbar)
        file_menu.add_command(label=self._t("quit"), command=self.quit)
        menu_bar.add_cascade(label=self._t("menu_file"), menu=file_menu)

        view_menu = tk.Menu(menu_bar, tearoff=0)
        view_menu.add_command(label=self._t("log_window"), command=self.show_log_window)
        view_menu.add_command(label=self._t("diagnostic"), command=self.diagnostic)
        menu_bar.add_cascade(label=self._t("menu_view"), menu=view_menu)

        tools_menu = tk.Menu(menu_bar, tearoff=0)
        tools_menu.add_command(label=self._t("settings"), command=self.show_settings)
        tools_menu.add_command(label=self._t("connections"), command=self.show_connections_window)
        tools_menu.add_command(label=self._t("learn_button"), command=self.toggle_midi_learn)
        tools_menu.add_command(label=self._t("test_display"), command=self.demo_display)
        tools_menu.add_command(
            label=self._t("copy_controller_unibank"),
            command=lambda: self.copy_controller_file("Ec4-UniBank.ctrl2"),
        )
        tools_menu.add_command(
            label=self._t("copy_controller_fullbank"),
            command=lambda: self.copy_controller_file("Ec4-FullBank.ctrl2"),
        )
        tools_menu.add_separator()
        tools_menu.add_command(label=self._t("updates"), command=self.check_updates)
        language_menu = tk.Menu(tools_menu, tearoff=0)
        language_menu.add_radiobutton(
            label="Français", variable=self.ui_language_var, value="fr"
        )
        language_menu.add_radiobutton(
            label="English", variable=self.ui_language_var, value="en"
        )
        tools_menu.add_cascade(label=self._t("language_label"), menu=language_menu)
        menu_bar.add_cascade(label=self._t("menu_tools"), menu=tools_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(
            label=self._t("controller_guide"), command=self.show_controller_guide
        )
        help_menu.add_separator()
        help_menu.add_command(
            label=self._t("repository"), command=lambda: self._open_link(REPOSITORY_URL)
        )
        help_menu.add_command(
            label=self._t("releases"), command=lambda: self._open_link(RELEASES_URL)
        )
        help_menu.add_command(
            label=self._t("report_bug"), command=lambda: self._open_link(ISSUES_URL)
        )
        help_menu.add_command(
            label=self._t("contribute"), command=lambda: self._open_link(CONTRIBUTE_URL)
        )
        help_menu.add_command(
            label=self._t("support"), command=lambda: self._open_link(PAYPAL_URL)
        )
        help_menu.add_separator()
        help_menu.add_command(label=self._t("about"), command=self.show_about)
        menu_bar.add_cascade(label=self._t("menu_help"), menu=help_menu)

        self.menu_bar = menu_bar
        self.root.configure(menu=menu_bar)

    def _build(self) -> None:
        tk = self.tk
        ttk = self.ttk
        self._build_menu()

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)

        brand = tk.Frame(
            main,
            bg="#111820",
            height=62,
            highlightthickness=1,
            highlightbackground="#2a4050",
        )
        brand.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        brand.grid_propagate(False)
        tk.Label(
            brand,
            text="EC4 Bridge",
            bg="#111820",
            fg="#e8f4f8",
            font=("Segoe UI Semibold", 18),
        ).pack(side="left", padx=(16, 12))
        tk.Label(
            brand,
            text=f"LiveProfessor  •  v{__version__}",
            bg="#111820",
            fg="#91a9b5",
            font=("Segoe UI", 11),
        ).pack(side="left")

        signature = tk.Frame(brand, bg="#111820")
        signature.pack(side="right", padx=12)
        tk.Label(
            signature,
            text="SiLeMI/O",
            bg="#111820",
            fg="#43d6ff",
            font=("Segoe UI Semibold", 13),
        ).pack(side="left", padx=(0, 10))
        tk.Label(
            signature,
            text="By Mamat\n-----[]---",
            bg="#111820",
            fg="#91a9b5",
            font=("Segoe UI", 9),
            anchor="e",
            justify="right",
        ).pack(side="left")

        action_frame = ttk.Frame(main)
        action_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.start_button = ttk.Button(action_frame, text=self._t("start"), command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            action_frame, text=self._t("stop"), command=self.stop, state="disabled"
        )
        self.stop_button.pack(side="left", padx=6)
        self.minimize_button = ttk.Button(
            action_frame, text=self._t("minimize"), command=self.minimize_to_taskbar
        )
        self.minimize_button.pack(side="left", padx=6)
        self.quit_button = ttk.Button(action_frame, text=self._t("quit"), command=self.quit)
        self.quit_button.pack(side="left", padx=6)
        self.settings_button = ttk.Button(
            action_frame, text=self._t("settings"), command=self.show_settings
        )
        self.settings_button.pack(side="right")
        for widget, key in (
            (self.start_button, "start"),
            (self.stop_button, "stop"),
            (self.minimize_button, "minimize"),
            (self.quit_button, "quit"),
            (self.settings_button, "settings"),
        ):
            self._register_text_widget(widget, "text", key)

        state_frame = ttk.LabelFrame(main, text=self._t("state_frame"), padding=10)
        state_frame.grid(row=2, column=0, sticky="ew", pady=4)
        state_frame.columnconfigure(0, weight=1)
        self._register_text_widget(state_frame, "text", "state_frame")
        ttk.Label(state_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.state_previous_button = ttk.Button(
            state_frame, text=self._t("bank_previous"), command=lambda: self.change_bank(-1)
        )
        self.state_previous_button.grid(row=0, column=1, padx=4)
        ttk.Label(state_frame, textvariable=self.bank_var, width=16, anchor="center").grid(
            row=0, column=2
        )
        self.state_next_button = ttk.Button(
            state_frame, text=self._t("bank_next"), command=lambda: self.change_bank(1)
        )
        self.state_next_button.grid(row=0, column=3, padx=4)
        self._register_text_widget(self.state_previous_button, "text", "bank_previous")
        self._register_text_widget(self.state_next_button, "text", "bank_next")

        target_frame = ttk.LabelFrame(main, text=self._t("zone_label"), padding=10)
        target_frame.grid(row=3, column=0, sticky="ew", pady=6)
        self._register_text_widget(target_frame, "text", "zone_label")
        self.setup_label = ttk.Label(target_frame, text=self._t("setup_label"))
        self.setup_label.pack(side="left")
        ttk.Spinbox(
            target_frame, from_=1, to=16, textvariable=self.target_setup_var, width=5
        ).pack(side="left", padx=(4, 14))
        self.group_label = ttk.Label(target_frame, text=self._t("group_label"))
        self.group_label.pack(side="left")
        ttk.Spinbox(
            target_frame, from_=1, to=16, textvariable=self.target_group_var, width=5
        ).pack(side="left", padx=(4, 14))
        self.use_current_target_button = ttk.Button(
            target_frame, text=self._t("use_current_target"), command=self.use_current_target
        )
        self.use_current_target_button.pack(side="left")
        self._register_text_widget(self.setup_label, "text", "setup_label")
        self._register_text_widget(self.group_label, "text", "group_label")
        self._register_text_widget(self.use_current_target_button, "text", "use_current_target")

        learn_frame = ttk.Frame(main)
        learn_frame.grid(row=4, column=0, sticky="ew", pady=8)
        self.learn_button = ttk.Button(
            learn_frame, text=self._t("learn_button"), command=self.toggle_midi_learn
        )
        self.learn_button.pack(side="left")
        ttk.Label(learn_frame, textvariable=self.learn_var).pack(side="left", padx=12)
        self.shortcuts_button = ttk.Button(
            learn_frame, text=self._t("shortcuts"), command=self.show_shortcuts
        )
        self.shortcuts_button.pack(side="right")
        self.copy_controller_unibank_button = ttk.Button(
            learn_frame,
            text=self._t("copy_controller_unibank"),
            command=lambda: self.copy_controller_file("Ec4-UniBank.ctrl2"),
        )
        self.copy_controller_unibank_button.pack(side="right", padx=(0, 8))
        self.copy_controller_fullbank_button = ttk.Button(
            learn_frame,
            text=self._t("copy_controller_fullbank"),
            command=lambda: self.copy_controller_file("Ec4-FullBank.ctrl2"),
        )
        self.copy_controller_fullbank_button.pack(side="right", padx=(0, 8))
        self._register_text_widget(self.learn_button, "text", "learn_button")
        self._register_text_widget(self.shortcuts_button, "text", "shortcuts")
        self._register_text_widget(
            self.copy_controller_unibank_button, "text", "copy_controller_unibank"
        )
        self._register_text_widget(
            self.copy_controller_fullbank_button, "text", "copy_controller_fullbank"
        )

        event_frame = ttk.LabelFrame(main, text=self._t("last_event"), padding=8)
        event_frame.grid(row=5, column=0, sticky="nsew", pady=(8, 0))
        main.rowconfigure(5, weight=1)
        self._register_text_widget(event_frame, "text", "last_event")
        ttk.Label(
            event_frame, textvariable=self.last_event_var, anchor="w", wraplength=680
        ).pack(fill="both", expand=True)

    def _build_legacy(self) -> None:
        tk = self.tk
        ttk = self.ttk
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)

        row = 0
        brand = tk.Frame(main, bg="#111820", height=58, highlightthickness=1, highlightbackground="#2a4050")
        brand.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        brand.grid_propagate(False)
        tk.Label(
            brand,
            text="SiLeMI/O",
            bg="#111820",
            fg="#43d6ff",
            font=("Segoe UI Semibold", 18),
        ).pack(side="left", padx=(16, 12))
        tk.Label(
            brand,
            text="EC4 × LiveProfessor",
            bg="#111820",
            fg="#e8f4f8",
            font=("Segoe UI", 11),
        ).pack(side="left")
        tk.Label(
            brand,
            text="By Mamat\n-----[]---",
            bg="#111820",
            fg="#91a9b5",
            font=("Segoe UI", 9),
            width=24,
            anchor="e",
        ).pack(side="right", padx=12)

        row += 1
        self.mode_label = ttk.Label(main, text=self._t("mode_label"))
        self.mode_label.grid(row=row, column=0, sticky="w", pady=4)
        self._register_text_widget(self.mode_label, "text", "mode_label")
        mode = ttk.Combobox(
            main,
            textvariable=self.mode_var,
            values=("companion", "generic"),
            state="readonly",
            width=22,
        )
        mode.grid(row=row, column=1, sticky="ew", pady=4)
        self.mode_help_label = ttk.Label(main, text=self._t("mode_help"))
        self.mode_help_label.grid(row=row, column=2, sticky="w", padx=(8, 0))
        self._register_text_widget(self.mode_help_label, "text", "mode_help")

        row += 1
        self.midi_in_label = ttk.Label(main, text=self._t("midi_in_label"))
        self.midi_in_label.grid(row=row, column=0, sticky="w", pady=4)
        self._register_text_widget(self.midi_in_label, "text", "midi_in_label")
        self.input_combo = ttk.Combobox(main, textvariable=self.midi_in_var)
        self.input_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)

        row += 1
        self.midi_out_label = ttk.Label(main, text=self._t("midi_out_label"))
        self.midi_out_label.grid(row=row, column=0, sticky="w", pady=4)
        self._register_text_widget(self.midi_out_label, "text", "midi_out_label")
        self.output_combo = ttk.Combobox(main, textvariable=self.midi_out_var)
        self.output_combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)

        row += 1
        self.refresh_ports_button = ttk.Button(
            main, text=self._t("refresh_ports"), command=self.refresh_ports
        )
        self.refresh_ports_button.grid(row=row, column=1, sticky="w", pady=(0, 8))
        self._register_text_widget(self.refresh_ports_button, "text", "refresh_ports")

        row += 1
        action_frame = ttk.Frame(main)
        action_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=10)
        self.start_button = ttk.Button(action_frame, text=self._t("start"), command=self.start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(action_frame, text=self._t("stop"), command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=6)
        self.save_button = ttk.Button(action_frame, text=self._t("save"), command=self.save)
        self.save_button.pack(side="left", padx=6)
        self.diagnostic_button = ttk.Button(
            action_frame, text=self._t("diagnostic"), command=self.diagnostic
        )
        self.diagnostic_button.pack(side="left", padx=6)
        self.shortcuts_button = ttk.Button(
            action_frame, text=self._t("shortcuts"), command=self.show_shortcuts
        )
        self.shortcuts_button.pack(side="left", padx=6)
        self.demo_button = ttk.Button(action_frame, text=self._t("test_display"), command=self.demo_display)
        self.demo_button.pack(side="left", padx=6)
        self.minimize_button = ttk.Button(action_frame, text=self._t("minimize"), command=self.minimize_to_taskbar)
        self.minimize_button.pack(side="left", padx=6)
        self.quit_button = ttk.Button(action_frame, text=self._t("quit"), command=self.quit)
        self.quit_button.pack(side="left", padx=6)

        self._register_text_widget(self.start_button, "text", "start")
        self._register_text_widget(self.stop_button, "text", "stop")
        self._register_text_widget(self.save_button, "text", "save")
        self._register_text_widget(self.diagnostic_button, "text", "diagnostic")
        self._register_text_widget(self.shortcuts_button, "text", "shortcuts")
        self._register_text_widget(self.demo_button, "text", "test_display")
        self._register_text_widget(self.minimize_button, "text", "minimize")
        self._register_text_widget(self.quit_button, "text", "quit")

        row += 1
        ttk.Separator(main).grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        row += 1
        self.lp_host_label = ttk.Label(main, text=self._t("lp_host_label"))
        self.lp_host_label.grid(row=row, column=0, sticky="w", pady=4)
        self._register_text_widget(self.lp_host_label, "text", "lp_host_label")
        ttk.Entry(main, textvariable=self.host_var).grid(row=row, column=1, sticky="ew", pady=4)
        ports = ttk.Frame(main)
        ports.grid(row=row, column=2, sticky="ew", padx=(8, 0))
        self.lp_port_label = ttk.Label(ports, text=self._t("lp_port_label"))
        self.lp_port_label.pack(side="left")
        self._register_text_widget(self.lp_port_label, "text", "lp_port_label")
        ttk.Entry(ports, textvariable=self.lp_port_var, width=7).pack(side="left", padx=(4, 12))
        self.lp_return_label = ttk.Label(ports, text=self._t("lp_return_label"))
        self.lp_return_label.pack(side="left")
        self._register_text_widget(self.lp_return_label, "text", "lp_return_label")
        ttk.Entry(ports, textvariable=self.feedback_port_var, width=7).pack(side="left", padx=4)

        row += 1
        self.profile_label = ttk.Label(main, text=self._t("profile_label"))
        self.profile_label.grid(row=row, column=0, sticky="w", pady=4)
        self._register_text_widget(self.profile_label, "text", "profile_label")
        ttk.Entry(main, textvariable=self.profile_var).grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=4
        )

        row += 1
        self.zone_label = ttk.Label(main, text=self._t("zone_label"))
        self.zone_label.grid(row=row, column=0, sticky="w", pady=4)
        self._register_text_widget(self.zone_label, "text", "zone_label")
        target = ttk.Frame(main)
        target.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        self.setup_label = ttk.Label(target, text=self._t("setup_label"))
        self.setup_label.pack(side="left")
        self._register_text_widget(self.setup_label, "text", "setup_label")
        ttk.Spinbox(target, from_=1, to=16, textvariable=self.target_setup_var, width=5).pack(
            side="left", padx=(4, 12)
        )
        self.group_label = ttk.Label(target, text=self._t("group_label"))
        self.group_label.pack(side="left")
        self._register_text_widget(self.group_label, "text", "group_label")
        ttk.Spinbox(target, from_=1, to=16, textvariable=self.target_group_var, width=5).pack(
            side="left", padx=(4, 12)
        )
        self.use_current_target_button = ttk.Button(target, text=self._t("use_current_target"), command=self.use_current_target)
        self.use_current_target_button.pack(side="left")
        self._register_text_widget(self.use_current_target_button, "text", "use_current_target")

        row += 1
        self.mapping_label = ttk.Label(main, text=self._t("mapping_label"))
        self.mapping_label.grid(row=row, column=0, sticky="w", pady=4)
        self._register_text_widget(self.mapping_label, "text", "mapping_label")
        learn_frame = ttk.Frame(main)
        learn_frame.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        self.learn_button = ttk.Button(
            learn_frame,
            text=self._t("learn_button"),
            command=self.toggle_midi_learn,
        )
        self.learn_button.pack(side="left")
        self._register_text_widget(self.learn_button, "text", "learn_button")
        ttk.Label(learn_frame, textvariable=self.learn_var).pack(side="left", padx=12)

        row += 1
        self.display_check = ttk.Checkbutton(main, text=self._t("display_check"), variable=self.display_var)
        self.display_check.grid(
            row=row, column=1, columnspan=2, sticky="w", pady=4
        )
        self._register_text_widget(self.display_check, "text", "display_check")

        row += 1
        self.persistent_display_check = ttk.Checkbutton(
            main,
            text=self._t("persistent_check"),
            variable=self.persistent_display_var,
        )
        self.persistent_display_check.grid(row=row, column=1, columnspan=2, sticky="w", pady=4)
        self._register_text_widget(self.persistent_display_check, "text", "persistent_check")

        row += 1
        self.speed_frame = ttk.LabelFrame(main, text=self._t("speed_section"), padding=6)
        self.speed_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=8)
        self._register_text_widget(self.speed_frame, "text", "speed_section")
        for index in (0, 1):
            self.speed_frame.columnconfigure(index, weight=1)
        self.speed_overlay_interval_label = ttk.Label(self.speed_frame, text=self._t("speed_overlay_interval"))
        self._register_text_widget(self.speed_overlay_interval_label, "text", "speed_overlay_interval")
        self.speed_overlay_interval_label.grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(self.speed_frame, textvariable=self.parameter_overlay_interval_var, width=8).grid(
            row=0, column=1, sticky="w"
        )
        self.speed_refresh_companion_label = ttk.Label(self.speed_frame, text=self._t("speed_refresh_companion"))
        self._register_text_widget(self.speed_refresh_companion_label, "text", "speed_refresh_companion")
        self.speed_refresh_companion_label.grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Entry(self.speed_frame, textvariable=self.companion_refresh_delay_var, width=8).grid(
            row=1, column=1, sticky="w", pady=(4, 0)
        )
        self.speed_refresh_label_label = ttk.Label(self.speed_frame, text=self._t("speed_refresh_label"))
        self._register_text_widget(self.speed_refresh_label_label, "text", "speed_refresh_label")
        self.speed_refresh_label_label.grid(
            row=2, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Entry(self.speed_frame, textvariable=self.name_refresh_delay_var, width=8).grid(
            row=2, column=1, sticky="w", pady=(4, 0)
        )
        self.speed_feedback_timeout_label = ttk.Label(self.speed_frame, text=self._t("speed_feedback_timeout"))
        self._register_text_widget(self.speed_feedback_timeout_label, "text", "speed_feedback_timeout")
        self.speed_feedback_timeout_label.grid(
            row=3, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Entry(self.speed_frame, textvariable=self.feedback_timeout_var, width=8).grid(
            row=3, column=1, sticky="w", pady=(4, 0)
        )
        self.speed_overlay_duration_label = ttk.Label(self.speed_frame, text=self._t("speed_overlay_duration"))
        self._register_text_widget(self.speed_overlay_duration_label, "text", "speed_overlay_duration")
        self.speed_overlay_duration_label.grid(
            row=4, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Entry(self.speed_frame, textvariable=self.overlay_display_duration_var, width=8).grid(
            row=4, column=1, sticky="w", pady=(4, 0)
        )

        row += 1
        language = ttk.Frame(main)
        language.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.language_label = ttk.Label(language, text=self._t("language_label"))
        self.language_label.pack(side="left")
        self._register_text_widget(self.language_label, "text", "language_label")
        ttk.Combobox(
            language,
            textvariable=self.ui_language_var,
            values=("fr", "en"),
            width=10,
            state="readonly",
        ).pack(side="left", padx=(8, 12))
        self.language_note_label = ttk.Label(language, text=self._t("language_note"))
        self.language_note_label.pack(side="left")
        self._register_text_widget(self.language_note_label, "text", "language_note")

        row += 1
        state_frame = ttk.LabelFrame(main, text=self._t("state_frame"), padding=8)
        state_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=4)
        state_frame.columnconfigure(0, weight=1)
        self._register_text_widget(state_frame, "text", "state_frame")
        ttk.Label(state_frame, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.state_previous_button = ttk.Button(
            state_frame, text=self._t("bank_previous"), command=lambda: self.change_bank(-1)
        )
        self._register_text_widget(self.state_previous_button, "text", "bank_previous")
        self.state_previous_button.grid(
            row=0, column=1, padx=4
        )
        ttk.Label(state_frame, textvariable=self.bank_var, width=14, anchor="center").grid(
            row=0, column=2
        )
        self.state_next_button = ttk.Button(
            state_frame, text=self._t("bank_next"), command=lambda: self.change_bank(1)
        )
        self._register_text_widget(self.state_next_button, "text", "bank_next")
        self.state_next_button.grid(row=0, column=3, padx=4)

        row += 1
        log_frame = ttk.LabelFrame(main, text=self._t("log_frame"), padding=6)
        log_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        self.log_frame = log_frame
        self._register_text_widget(log_frame, "text", "log_frame")
        main.rowconfigure(row, weight=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=14, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

    def show_settings(self) -> None:
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.deiconify()
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        ttk = self.ttk
        window = self.tk.Toplevel(self.root)
        self.settings_window = window
        window.title(self._t("settings"))
        window.geometry("700x590")
        window.transient(self.root)
        self._set_window_icons()

        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        connections = ttk.Frame(notebook, padding=12)
        ec4 = ttk.Frame(notebook, padding=12)
        display = ttk.Frame(notebook, padding=12)
        advanced = ttk.Frame(notebook, padding=12)
        notebook.add(connections, text=self._t("connections"))
        notebook.add(ec4, text="EC4")
        notebook.add(display, text=self._t("menu_view"))
        notebook.add(advanced, text=self._t("menu_tools"))

        for frame in (connections, ec4, display, advanced):
            frame.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(connections, text=self._t("mode_label")).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(
            connections,
            textvariable=self.mode_var,
            values=("companion", "generic"),
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1
        ttk.Label(connections, text=self._t("midi_in_label")).grid(row=row, column=0, sticky="w", pady=4)
        self.input_combo = ttk.Combobox(connections, textvariable=self.midi_in_var)
        self.input_combo.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1
        ttk.Label(connections, text=self._t("midi_out_label")).grid(row=row, column=0, sticky="w", pady=4)
        self.output_combo = ttk.Combobox(connections, textvariable=self.midi_out_var)
        self.output_combo.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1
        ttk.Button(
            connections, text=self._t("refresh_ports"), command=self.refresh_ports
        ).grid(row=row, column=1, sticky="w", pady=(0, 10))
        row += 1
        ttk.Label(connections, text=self._t("lp_host_label")).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(connections, textvariable=self.host_var).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1
        ttk.Label(connections, text=self._t("lp_port_label")).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(connections, textvariable=self.lp_port_var).grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        ttk.Label(connections, text=self._t("lp_return_label")).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(connections, textvariable=self.feedback_port_var).grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        ttk.Label(connections, text=self._t("profile_label")).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(connections, textvariable=self.profile_var).grid(row=row, column=1, sticky="ew", pady=4)

        ttk.Label(ec4, text=self._t("setup_label")).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Spinbox(ec4, from_=1, to=16, textvariable=self.target_setup_var, width=6).grid(
            row=0, column=1, sticky="w", pady=4
        )
        ttk.Label(ec4, text=self._t("group_label")).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Spinbox(ec4, from_=1, to=16, textvariable=self.target_group_var, width=6).grid(
            row=1, column=1, sticky="w", pady=4
        )
        ttk.Button(
            ec4, text=self._t("use_current_target"), command=self.use_current_target
        ).grid(row=2, column=1, sticky="w", pady=8)
        ttk.Button(ec4, text=self._t("learn_button"), command=self.toggle_midi_learn).grid(
            row=3, column=1, sticky="w", pady=8
        )
        ttk.Label(ec4, textvariable=self.learn_var).grid(row=4, column=1, sticky="w")

        ttk.Checkbutton(
            display, text=self._t("display_check"), variable=self.display_var
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(
            display, text=self._t("persistent_check"), variable=self.persistent_display_var
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Button(display, text=self._t("test_display"), command=self.demo_display).grid(
            row=2, column=0, sticky="w", pady=8
        )

        advanced_fields = (
            ("speed_overlay_interval", self.parameter_overlay_interval_var),
            ("speed_refresh_companion", self.companion_refresh_delay_var),
            ("speed_refresh_label", self.name_refresh_delay_var),
            ("speed_feedback_timeout", self.feedback_timeout_var),
            ("speed_overlay_duration", self.overlay_display_duration_var),
        )
        for row, (key, variable) in enumerate(advanced_fields):
            ttk.Label(advanced, text=self._t(key)).grid(row=row, column=0, sticky="w", pady=4)
            ttk.Entry(advanced, textvariable=variable, width=10).grid(
                row=row, column=1, sticky="w", pady=4
            )
        row = len(advanced_fields)
        ttk.Checkbutton(
            advanced,
            text=self._t("minimize_on_close"),
            variable=self.minimize_on_close_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(12, 4))
        ttk.Checkbutton(
            advanced,
            text=self._t("check_updates_startup"),
            variable=self.check_updates_var,
        ).grid(row=row + 1, column=0, columnspan=2, sticky="w", pady=4)

        footer = ttk.Frame(window, padding=(10, 0, 10, 10))
        footer.pack(fill="x")

        def save_and_close() -> None:
            self.save()
            close_window()

        def close_window() -> None:
            if hasattr(self, "input_combo"):
                del self.input_combo
            if hasattr(self, "output_combo"):
                del self.output_combo
            self.settings_window = None
            window.destroy()

        ttk.Button(footer, text=self._t("save_close"), command=save_and_close).pack(side="right")
        ttk.Button(footer, text=self._t("quit"), command=close_window).pack(side="right", padx=6)
        window.protocol("WM_DELETE_WINDOW", close_window)
        self.refresh_ports()

    def show_log_window(self) -> None:
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.deiconify()
            self.log_window.lift()
            self.log_window.focus_force()
            return
        window = self.tk.Toplevel(self.root)
        self.log_window = window
        window.title(self._t("log_window"))
        window.geometry("820x460")
        frame = self.ttk.Frame(window, padding=8)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.log_text = self.tk.Text(frame, wrap="word", state="normal")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.insert("1.0", "".join(self._log_lines))
        self.log_text.configure(state="disabled")
        scroll = self.ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)
        buttons = self.ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.ttk.Button(buttons, text=self._t("copy_all"), command=self._copy_log).pack(side="left")
        self.ttk.Button(
            buttons, text=self._t("clear_display"), command=self._clear_log_display
        ).pack(side="left", padx=5)
        self.ttk.Button(
            buttons, text=self._t("open_log_file"), command=self._open_log_file
        ).pack(side="left", padx=5)
        self.ttk.Button(
            buttons, text=self._t("open_log_folder"), command=self._open_log_folder
        ).pack(side="left", padx=5)

        def hide() -> None:
            window.withdraw()

        window.protocol("WM_DELETE_WINDOW", hide)

    def _copy_log(self) -> None:
        content = "".join(self._log_lines)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)

    def _clear_log_display(self) -> None:
        if hasattr(self, "log_text") and self.log_text.winfo_exists():
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")

    def _open_log_file(self) -> None:
        path = default_data_dir() / "bridge.log"
        if path.exists():
            os.startfile(path)

    def _open_log_folder(self) -> None:
        folder = default_data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def show_connections_window(self) -> None:
        if self.connections_window is not None and self.connections_window.winfo_exists():
            self.connections_window.deiconify()
            self.connections_window.lift()
            return
        window = self.tk.Toplevel(self.root)
        self.connections_window = window
        window.title(self._t("connections"))
        frame = self.ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)
        self.ttk.Button(frame, text=self._t("refresh_ports"), command=self.refresh_ports).pack(
            fill="x", pady=4
        )
        self.ttk.Button(frame, text=self._t("reconnect_ec4"), command=self.reconnect_ec4).pack(
            fill="x", pady=4
        )
        self.ttk.Button(frame, text=self._t("request_setup"), command=self.request_setup).pack(
            fill="x", pady=4
        )
        self.ttk.Button(
            frame, text=self._t("refresh_companion"), command=self.refresh_companion
        ).pack(fill="x", pady=4)

        def hide() -> None:
            window.withdraw()

        window.protocol("WM_DELETE_WINDOW", hide)

    def reconnect_ec4(self) -> None:
        if self.bridge and self.bridge.running:
            self.bridge.reconnect_midi()

    def request_setup(self) -> None:
        if self.bridge and self.bridge.running:
            self.bridge.request_setup_state()

    def refresh_companion(self) -> None:
        if self.bridge and self.bridge.running:
            self.bridge.refresh_companion()

    def restart(self) -> None:
        self.stop()
        self.root.after(100, self.start)

    def _open_link(self, url: str) -> None:
        try:
            if not open_external_url(url):
                raise OSError("le navigateur n'a pas accepte la demande")
        except Exception as exc:
            self.messagebox.showerror(self._t("menu_help"), str(exc))

    def show_about(self) -> None:
        message = (
            f"EC4 LiveProfessor Bridge {__version__}\n\n"
            "SiLeMI/O\nBy Mamat\n----[]--\n\n"
            "Bridge MIDI / OSC / SysEx. Aucun audio ne traverse l'application."
        )
        self.messagebox.showinfo(self._t("about"), message)

    def check_updates(self, silent: bool = False) -> None:
        self._append_log("Vérification des mises à jour GitHub…")

        def worker() -> None:
            try:
                release = fetch_latest_release()
                self.root.after(0, self._apply_update_result, release, silent, None)
            except Exception as exc:
                self.root.after(0, self._apply_update_result, None, silent, exc)

        threading.Thread(target=worker, name="github-update-check", daemon=True).start()

    def _apply_update_result(
        self,
        release: ReleaseInfo | None,
        silent: bool,
        error: Exception | None,
    ) -> None:
        if error is not None:
            self._append_log(f"Mise à jour indisponible: {error}")
            if not silent:
                self.messagebox.showwarning(self._t("updates"), str(error))
            return
        assert release is not None
        if not is_newer_version(release.version, __version__):
            self._append_log(f"Version {__version__}: à jour")
            if not silent:
                self.messagebox.showinfo(
                    self._t("updates"), f"La version {__version__} est à jour."
                )
            return
        notes = release.notes or "Aucune note de version."
        size = f"{release.asset_size / 1_048_576:.1f} Mo" if release.asset_size else "inconnue"
        message = (
            f"Version installée : {__version__}\n"
            f"Version disponible : {release.version}\n"
            f"Fichier : {release.asset_name or 'release GitHub'} ({size})\n\n"
            f"{notes[:1800]}\n\nOuvrir la release pour télécharger la mise à jour ?"
        )
        if self.messagebox.askyesno(self._t("updates"), message):
            self._open_link(RELEASES_URL)

    def _config_from_form(self) -> BridgeConfig:
        config = replace(
            self.config,
            mode=self.mode_var.get().strip(),
            midi_input=self.midi_in_var.get().strip(),
            midi_output=self.midi_out_var.get().strip(),
            liveprofessor_host=self.host_var.get().strip(),
            liveprofessor_port=int(self.lp_port_var.get()),
            feedback_port=int(self.feedback_port_var.get()),
            profile_file=self.profile_var.get().strip(),
            display_enabled=bool(self.display_var.get()),
            persistent_parameter_display=bool(self.persistent_display_var.get()),
            parameter_overlay_interval_ms=int(self.parameter_overlay_interval_var.get()),
            companion_refresh_delay_ms=int(self.companion_refresh_delay_var.get()),
            name_refresh_delay_ms=int(self.name_refresh_delay_var.get()),
            feedback_confirm_timeout_ms=int(self.feedback_timeout_var.get()),
            overlay_display_duration_ms=int(self.overlay_display_duration_var.get()),
            ui_language=self.ui_language_var.get().strip().lower(),
            minimize_to_tray_on_close=bool(self.minimize_on_close_var.get()),
            check_updates_on_startup=bool(self.check_updates_var.get()),
            target_setup=int(self.target_setup_var.get()),
            target_group=int(self.target_group_var.get()),
            restrict_to_target=True,
        )
        config.validate()
        return config

    def refresh_ports(self) -> None:
        try:
            inputs = input_names()
            outputs = output_names()
            if hasattr(self, "input_combo") and self.input_combo.winfo_exists():
                self.input_combo.configure(values=inputs)
            if hasattr(self, "output_combo") and self.output_combo.winfo_exists():
                self.output_combo.configure(values=outputs)
            self._append_log(f"Ports MIDI: {len(inputs)} entree(s), {len(outputs)} sortie(s)")
            for name in inputs:
                if "faderfox" in name.casefold():
                    self.midi_in_var.set(name)
                    break
            for name in outputs:
                if "faderfox" in name.casefold():
                    self.midi_out_var.set(name)
                    break
        except Exception as exc:
            self._append_log(f"Inventaire MIDI impossible: {exc}")

    def save(self) -> None:
        try:
            self.config = self._config_from_form()
            path = save_config(self.config, self.config_path)
            self._append_log(f"Configuration enregistree: {path}")
        except Exception as exc:
            self.messagebox.showerror(self._t("invalid_configuration"), str(exc))

    def start(self) -> None:
        try:
            if self.bridge:
                self.bridge.stop()
            self.config = self._config_from_form()
            save_config(self.config, self.config_path)
            self.bridge = EC4LiveProfessorBridge(
                self.config,
                status_callback=self._queue_snapshot,
                log_callback=self._queue_log,
            )
            self.bridge.start()
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self._build_menu()
        except Exception as exc:
            self._append_log(f"Demarrage impossible: {exc}")
            self.messagebox.showerror(self._t("bridge_start_error_title"), str(exc))

    def stop(self) -> None:
        self._cancel_midi_learn()
        if self.bridge:
            self.bridge.stop()
            self.bridge = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_var.set(self._t("status_stopped"))
        if not self._closing:
            self._build_menu()

    def change_bank(self, delta: int) -> None:
        if self.bridge:
            self.bridge.change_bank(delta)

    def demo_display(self) -> None:
        if not self.bridge or not self.bridge.running:
            self.messagebox.showinfo(self._t("bridge_stopped_title"), self._t("bridge_start_msg"))
            return
        if not self.bridge.snapshot().midi_connected:
            self.messagebox.showinfo(self._t("ec4_absent_title"), self._t("ec4_absent_msg"))
            return
        self.bridge.demo_display()

    def use_current_target(self) -> None:
        if not self.bridge or not self.bridge.running:
            self.messagebox.showinfo(self._t("bridge_stopped_title"), self._t("bridge_start_msg"))
            return
        snapshot = self.bridge.snapshot()
        if snapshot.setup is None or snapshot.group is None:
            self.messagebox.showinfo(
                self._t("unknown_state_title"),
                self._t("unknown_state_message"),
            )
            return
        setup = snapshot.setup + 1
        group = snapshot.group + 1
        self.target_setup_var.set(str(setup))
        self.target_group_var.set(str(group))
        try:
            self.config = self._config_from_form()
            save_config(self.config, self.config_path)
            self.bridge.set_target(setup, group)
            self._update_mapping_status()
            self._append_log(f"Zone EC4 enregistree: setup {setup}, groupe {group}")
        except Exception as exc:
            self.messagebox.showerror(self._t("invalid_configuration"), str(exc))

    def _mapping_key(self) -> str:
        return f"{int(self.target_setup_var.get())}:{int(self.target_group_var.get())}"

    def _update_mapping_status(self) -> None:
        mapping = self.config.encoder_mappings.get(self._mapping_key())
        if mapping and len(mapping) == 16:
            self.learn_var.set(self._t("learn_saved_label"))
        else:
            self.learn_var.set(self._t("learn_default_label"))

    def toggle_midi_learn(self) -> None:
        if self._learning:
            self._cancel_midi_learn()
            return
        if not self.bridge or not self.bridge.running:
            self.messagebox.showinfo(self._t("bridge_stopped_title"), self._t("bridge_start_msg"))
            return
        snapshot = self.bridge.snapshot()
        target = (int(self.target_setup_var.get()), int(self.target_group_var.get()))
        current = (
                snapshot.setup + 1 if snapshot.setup is not None else None,
                snapshot.group + 1 if snapshot.group is not None else None,
            )
        if current != target:
            self.messagebox.showinfo(
                self._t("wrong_zone_title"),
                self._t("wrong_zone_message", setup=target[0], group=target[1]),
            )
            return
        try:
            self.config = self._config_from_form()
            save_config(self.config, self.config_path)
            self.bridge.config.encoder_mappings = self.config.encoder_mappings
            self.bridge.set_target(*target)
        except Exception as exc:
            self.messagebox.showerror(self._t("invalid_configuration"), str(exc))
            return
        self._learning = True
        self._learn_controls = []
        self._learn_pushes = []
        self._learn_phase = "cc"
        self.learn_button.configure(text=self._t("learn_cancel"))
        self.learn_var.set(self._t("learning_progress"))
        self.bridge.set_midi_learn_callback(self._queue_midi_learn)
        self._append_log("Apprentissage MIDI: tournez les encodeurs 1 a 16 dans l'ordre")
        self.messagebox.showinfo(
            self._t("learn_progress_title"),
            self._t("learn_progress_message"),
        )

    def _queue_midi_learn(self, kind: str, channel: int, identifier: int, value: int) -> bool:
        self.root.after(0, self._capture_midi_learn, kind, channel, identifier, value)
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
        label = "CC" if self._learn_phase == "cc" else "Note push"
        self._append_log(f"{label} {number}: canal {channel + 1}, numero {identifier}")
        if number < 16:
            if self._learn_phase == "cc":
                self.learn_var.set(
                    f"{self._t('learn_rotary_prompt').format(index=number + 1)} ({number}/16)"
                )
            else:
                self.learn_var.set(
                    f"{self._t('learn_push_prompt').format(index=number + 1)} ({number}/16)"
                )
            return
        if self._learn_phase == "cc":
            self._learn_phase = "note"
            self.learn_var.set(self._t("learn_push_prompt").format(index=1) + " (0/16 push)")
            self._append_log("Rotatifs appris. Appuyez maintenant sur les push 1 a 16")
            self.messagebox.showinfo(
                self._t("learn_phase2_title"),
                self._t("learn_phase2_message"),
            )
            return
        mapping = [
            {
                "channel": learned_channel,
                "control": learned_control,
                "push_channel": push_channel,
                "push_note": push_note,
            }
            for (learned_channel, learned_control), (push_channel, push_note) in zip(
                self._learn_controls, self._learn_pushes
            )
        ]
        key = self._mapping_key()
        self.config.encoder_mappings[key] = mapping
        if self.bridge:
            self.bridge.config.encoder_mappings = self.config.encoder_mappings
            self.bridge.set_midi_learn_callback(None)
            self.bridge.refresh_target()
        save_config(self.config, self.config_path)
        self._learning = False
        self._learn_phase = ""
        self.learn_button.configure(text=self._t("learn_button"))
        self.learn_var.set(self._t("learn_saved_label"))
        self._append_log(f"Mapping MIDI enregistre pour la zone {key}")
        self.messagebox.showinfo(self._t("learn_complete_title"), self._t("learn_complete_message"))

    def _cancel_midi_learn(self) -> None:
        if self.bridge:
            self.bridge.set_midi_learn_callback(None)
        if self._learning:
            self._append_log("Apprentissage MIDI annule")
        self._learning = False
        self._learn_controls = []
        self._learn_pushes = []
        self._learn_phase = ""
        if hasattr(self, "learn_button"):
            self.learn_button.configure(text=self._t("learn_button"))
        if hasattr(self, "learn_var"):
            self._update_mapping_status()

    def diagnostic(self) -> None:
        lines = [f"EC4 LiveProfessor Bridge {__version__}"]
        try:
            lines.extend(protocol_self_test())
            lines.append("Entrees MIDI: " + (", ".join(input_names()) or "aucune"))
            lines.append("Sorties MIDI: " + (", ".join(output_names()) or "aucune"))
        except Exception as exc:
            lines.append(f"ERREUR: {exc}")
        self.messagebox.showinfo(self._t("diagnostic_title"), "\n".join(lines))

    def show_shortcuts(self) -> None:
        self.messagebox.showinfo(self._t("shortcuts_title"), self._t("shortcuts_text"))

    def show_controller_guide(self) -> None:
        self.messagebox.showinfo(
            self._t("controller_guide_title"),
            self._t("controller_guide_text"),
        )

    def copy_controller_file(self, filename: str) -> None:
        try:
            source = controller_template_path(filename)
        except Exception:
            self.messagebox.showerror(
                self._t("controller_missing_title"),
                self._t("controller_missing_message", name=filename),
            )
            return
        destination = self.filedialog.asksaveasfilename(
            parent=self.root,
            title=self._t("controller_copy_title", name=filename),
            initialfile=filename,
            defaultextension=".ctrl2",
            filetypes=(
                (self._t("controller_file_type"), "*.ctrl2"),
                (
                    "Tous les fichiers" if self._language_code() == "fr" else "All files",
                    "*.*",
                ),
            ),
        )
        if not destination:
            return
        try:
            copied = copy_controller_template(Path(destination), source=source)
        except Exception as exc:
            self.messagebox.showerror(self._t("controller_copy_error_title"), str(exc))
            return
        self.messagebox.showinfo(
            self._t("controller_copy_success_title"),
            self._t("controller_copy_success", path=copied)
            + "\n\n"
            + self._t("controller_guide_text"),
        )

    def _queue_snapshot(self, snapshot: BridgeSnapshot) -> None:
        self.root.after(0, self._apply_snapshot, snapshot)

    def _apply_snapshot(self, snapshot: BridgeSnapshot) -> None:
        details = snapshot.status
        if snapshot.setup is not None:
            details += f" | Setup {snapshot.setup + 1}, groupe {snapshot.group + 1}"
        self.status_var.set(details)
        self.bank_var.set(f"{self._t('bank_label')} {snapshot.active_bank + 1}/{snapshot.bank_count}")

    def _queue_log(self, message: str) -> None:
        self.root.after(0, self._append_log, message)

    def _append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        line = f"{stamp}  {message}\n"
        self._log_lines.append(line)
        if len(self._log_lines) > 2000:
            del self._log_lines[:500]
        self.last_event_var.set(message)
        if hasattr(self, "log_text") and self.log_text.winfo_exists():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

    def _ensure_tray_icon(self) -> bool:
        if not self._tray_ready or self._tray_icon_created:
            return self._tray_icon_created
        if self._tray_data is None:
            return False
        try:
            result = self._shell32.Shell_NotifyIconW(_NIM_ADD, ctypes.byref(self._tray_data))
            self._tray_icon_created = bool(result)
            if self._tray_icon_created:
                return True
        except Exception:
            return False
        return False

    def _remove_tray_icon(self) -> None:
        if not self._tray_ready or not self._tray_icon_created:
            return
        if self._tray_data is not None:
            try:
                self._shell32.Shell_NotifyIconW(_NIM_DELETE, ctypes.byref(self._tray_data))
            except Exception:
                pass
        if self._tray_loaded_icon is not None and self._tray_uses_file_icon:
            try:
                self._user32.DestroyIcon(self._tray_loaded_icon)
            except Exception:
                pass
            self._tray_loaded_icon = None
        self._tray_icon_created = False

    def _destroy_tray_infrastructure(self) -> None:
        if sys.platform != "win32":
            return
        self._remove_tray_icon()
        tray_hwnd = int(getattr(self, "_tray_hwnd", 0) or 0)
        if tray_hwnd and hasattr(self, "_user32"):
            try:
                self._user32.DestroyWindow(tray_hwnd)
            except Exception:
                pass
        self._tray_hwnd = 0
        class_name = str(getattr(self, "_tray_class_name", "") or "")
        class_atom = int(getattr(self, "_tray_class_atom", 0) or 0)
        if class_atom and class_name and hasattr(self, "_user32"):
            try:
                self._user32.UnregisterClassW(
                    class_name, getattr(self, "_tray_hinstance", None)
                )
            except Exception:
                pass
        self._tray_class_atom = 0
        self._tray_window_proc_handle = None
        self._tray_ready = False

    def minimize_to_taskbar(self) -> None:
        if sys.platform != "win32":
            self.root.iconify()
            return
        self._ensure_tray_setup()
        if self._tray_ready and self._ensure_tray_icon():
            self.root.withdraw()
            return
        self.root.iconify()

    def quit(self) -> None:
        if self._closing:
            return
        self._closing = True
        tray_poll_after_id = getattr(self, "_tray_poll_after_id", None)
        if tray_poll_after_id is not None:
            try:
                self.root.after_cancel(tray_poll_after_id)
            except Exception:
                pass
            self._tray_poll_after_id = None
        self._destroy_tray_infrastructure()
        try:
            self.stop()
        finally:
            self.root.destroy()

    def on_close(self) -> None:
        if bool(self.minimize_on_close_var.get()):
            self.minimize_to_taskbar()
        else:
            self.quit()

    def run(self) -> None:
        self.root.mainloop()


def run_headless(config_path: Path) -> int:
    config = load_config(config_path)
    configure_logging(config.log_level)
    bridge = EC4LiveProfessorBridge(config, log_callback=print)
    bridge.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        bridge.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pont Faderfox EC4 vers LiveProfessor")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--list-midi", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    configure_logging(config.log_level)
    if args.self_test:
        for result in protocol_self_test():
            print(result)
        return 0
    if args.list_midi:
        print("Entrees MIDI:")
        for name in input_names():
            print(f"  {name}")
        print("Sorties MIDI:")
        for name in output_names():
            print(f"  {name}")
        return 0
    if args.headless:
        return run_headless(args.config)
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    BridgeGUI(args.config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
