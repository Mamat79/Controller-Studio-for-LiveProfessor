from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class BridgeConfig:
    """Configuration persistante du pont.

    Le mode ``companion`` vise LiveProfessor >= 2023.0.8. Le mode ``generic``
    utilise un controleur OSC generique et reste utilisable avec LiveProfessor
    2.2.1, mais LiveProfessor ne fournit alors pas les noms de parametres.
    """

    mode: str = "companion"
    midi_input: str = "Faderfox EC4"
    midi_output: str = "Faderfox EC4"
    liveprofessor_host: str = "127.0.0.1"
    liveprofessor_port: int = 8010
    feedback_host: str = "127.0.0.1"
    feedback_port: int = 8011
    generic_prefix: str = "/EC4/Rotary"
    bank_size: int = 16
    max_controls: int = 99
    start_bank: int = 0
    echo_guard_ms: int = 100
    parameter_overlay_interval_ms: int = 120
    companion_refresh_delay_ms: int = 250
    name_refresh_delay_ms: int = 70
    feedback_confirm_timeout_ms: int = 800
    overlay_display_duration_ms: int = 1200
    reconnect_interval_s: float = 2.0
    display_enabled: bool = True
    persistent_parameter_display: bool = True
    display_only_supported_setups: bool = True
    target_setup: int = 13
    target_group: int = 3
    ui_language: str = "fr"
    minimize_to_tray_on_close: bool = True
    check_updates_on_startup: bool = True
    restrict_to_target: bool = True
    encoder_mappings: dict[str, list[dict[str, int]]] = field(default_factory=dict)
    setup_request_on_connect: bool = True
    plugin_label: str = "LiveProfessor"
    profile_file: str = ""
    show_hide_command: str = "/Command/PluginWindows/ShowHideselectedplugin"
    # OSC paths are case-sensitive. The installed LiveProfessor build accepts
    # this historical spelling; the documented `OnSelectedPlugin` variant is a no-op.
    enable_processing_command: str = "/Command/SelectedPlugin/EnableProcessingonselectedplugin"
    cue_previous_command: str = "/Command/CueLists/FirePreviousCue"
    cue_next_command: str = "/Command/CueLists/FireNextCue"
    snapshot_previous_command: str = "/Command/GlobalSnapshots/RecallPreviousGlobalSnapshot"
    snapshot_next_command: str = "/Command/GlobalSnapshots/RecallNextGlobalSnapshot"
    log_level: str = "INFO"
    extra: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.mode not in {"companion", "generic"}:
            raise ValueError("mode doit valoir 'companion' ou 'generic'")
        if not 1 <= self.liveprofessor_port <= 65535:
            raise ValueError("liveprofessor_port doit etre compris entre 1 et 65535")
        if not 1 <= self.feedback_port <= 65535:
            raise ValueError("feedback_port doit etre compris entre 1 et 65535")
        if self.bank_size != 16:
            raise ValueError("l'EC4 utilise exactement 16 encodeurs par banque")
        if not 1 <= self.max_controls <= 512:
            raise ValueError("max_controls doit etre compris entre 1 et 512")
        if self.start_bank < 0:
            raise ValueError("start_bank ne peut pas etre negatif")
        if self.echo_guard_ms < 0:
            raise ValueError("echo_guard_ms ne peut pas etre negatif")
        if not 1 <= self.parameter_overlay_interval_ms <= 2000:
            raise ValueError("parameter_overlay_interval_ms doit etre entre 1 et 2000")
        if not 1 <= self.companion_refresh_delay_ms <= 2000:
            raise ValueError("companion_refresh_delay_ms doit etre entre 1 et 2000")
        if not 1 <= self.name_refresh_delay_ms <= 2000:
            raise ValueError("name_refresh_delay_ms doit etre entre 1 et 2000")
        if not 100 <= self.feedback_confirm_timeout_ms <= 10000:
            raise ValueError("feedback_confirm_timeout_ms doit etre entre 100 et 10000")
        if not 200 <= self.overlay_display_duration_ms <= 5000:
            raise ValueError("overlay_display_duration_ms doit etre entre 200 et 5000")
        if self.reconnect_interval_s < 0.2:
            raise ValueError("reconnect_interval_s doit etre au moins 0,2 s")
        if not 1 <= self.target_setup <= 16:
            raise ValueError("target_setup doit etre compris entre 1 et 16")
        if not 1 <= self.target_group <= 16:
            raise ValueError("target_group doit etre compris entre 1 et 16")
        if self.ui_language not in {"fr", "en"}:
            raise ValueError("ui_language doit être 'fr' ou 'en'")
        for key, mapping in self.encoder_mappings.items():
            if not isinstance(key, str) or not isinstance(mapping, list) or len(mapping) != 16:
                raise ValueError("chaque mapping d'encodeurs doit contenir exactement 16 controles")
            for item in mapping:
                channel = int(item.get("channel", -1))
                control = int(item.get("control", -1))
                if not 0 <= channel <= 15 or not 0 <= control <= 127:
                    raise ValueError("mapping d'encodeur MIDI invalide")
                has_push_channel = "push_channel" in item
                has_push_note = "push_note" in item
                if has_push_channel != has_push_note:
                    raise ValueError("mapping de push MIDI incomplet")
                if has_push_channel:
                    push_channel = int(item["push_channel"])
                    push_note = int(item["push_note"])
                    if not 0 <= push_channel <= 15 or not 0 <= push_note <= 127:
                        raise ValueError("mapping de push MIDI invalide")
        if not self.generic_prefix.startswith("/"):
            raise ValueError("generic_prefix doit commencer par '/'")


def default_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "EC4LiveProfessorBridge"
    return Path.home() / ".ec4-liveprofessor-bridge"


def executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def default_config_path() -> Path:
    portable = executable_dir() / "config.json"
    if portable.exists():
        return portable
    return default_data_dir() / "config.json"


def load_config(path: Path | None = None) -> BridgeConfig:
    path = path or default_config_path()
    if not path.exists():
        config = BridgeConfig()
        config.validate()
        return config
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict):
        raise TypeError("le fichier de configuration doit contenir un objet JSON de type dictionnaire")

    defaults = BridgeConfig()
    normalized = dict(raw)

    legacy_migrations = {
        "show_hide_command": (
            "/Command/PluginWindows/ShowHideSelectedPlugin",
            "/Command/PluginWindows/ShowHideselectedplugin",
        ),
        "enable_processing_command": (
            "/Command/SelectedPlugin/EnableProcessingOnSelectedPlugin",
            "/Command/SelectedPlugin/EnableProcessingonselectedplugin",
        ),
        "cue_previous_command": (
            "/Command/CueList/RecallPreviousCue",
            "/Command/CueLists/FirePreviousCue",
        ),
        "cue_next_command": (
            "/Command/CueList/RecallNextCue",
            "/Command/CueLists/FireNextCue",
        ),
    }
    for key, (old_value, new_value) in legacy_migrations.items():
        if (
            key in normalized
            and isinstance(normalized[key], str)
            and normalized[key].strip() == old_value
        ):
            normalized[key] = new_value

    # Keep legacy installations working: keep current keys even if empty/invalidly
    # typed and fill missing values with the current defaults.
    normalized.setdefault("show_hide_command", defaults.show_hide_command)
    normalized.setdefault("enable_processing_command", defaults.enable_processing_command)
    normalized.setdefault(
        "snapshot_previous_command",
        defaults.snapshot_previous_command,
    )
    normalized.setdefault("snapshot_next_command", defaults.snapshot_next_command)

    known = set(BridgeConfig.__dataclass_fields__)
    kwargs = {key: value for key, value in normalized.items() if key in known}
    config = BridgeConfig(**kwargs)
    config.extra.update({key: value for key, value in raw.items() if key not in known})
    config.validate()
    return config


def save_config(config: BridgeConfig, path: Path | None = None) -> Path:
    config.validate()
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(config)
    extra = data.pop("extra", {})
    data.update(extra)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)
    return path
