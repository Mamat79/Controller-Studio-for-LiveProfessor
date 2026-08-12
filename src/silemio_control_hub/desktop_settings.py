"""Small, local-only desktop preferences with atomic persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import uuid

from .platform_paths import (
    legacy_control_hub_data_dir,
    previous_product_data_dir,
    product_data_dir,
)
from .controller_shortcuts import normalize_shortcuts_by_controller


SUPPORTED_LANGUAGES = frozenset({"fr", "en"})


@dataclass(frozen=True, slots=True)
class DesktopSettings:
    language: str = "fr"
    close_to_tray: bool = True
    active_controller_id: str | None = None
    auto_start_runtime: bool = False
    shortcuts_by_controller: dict[str, dict[str, str]] = field(default_factory=dict)


def default_desktop_settings_path() -> Path:
    return product_data_dir() / "desktop-settings.json"


def legacy_desktop_settings_path() -> Path:
    return legacy_control_hub_data_dir() / "desktop-settings.json"


def previous_desktop_settings_path() -> Path:
    return previous_product_data_dir() / "desktop-settings.json"


def load_desktop_settings(path: Path | None = None) -> DesktopSettings:
    source = Path(path or default_desktop_settings_path()).expanduser()
    if path is None and not source.is_file():
        for candidate in (
            previous_desktop_settings_path(),
            legacy_desktop_settings_path(),
        ):
            if candidate.is_file():
                source = candidate
                break
    if not source.is_file():
        return DesktopSettings()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return DesktopSettings()
    if not isinstance(raw, dict):
        return DesktopSettings()
    language = raw.get("language", "fr")
    close_to_tray = raw.get("close_to_tray", True)
    active_controller_id = raw.get("active_controller_id")
    auto_start_runtime = raw.get("auto_start_runtime", False)
    shortcuts_by_controller = normalize_shortcuts_by_controller(
        raw.get("shortcuts_by_controller", {})
    )
    if language not in SUPPORTED_LANGUAGES:
        language = "fr"
    if not isinstance(close_to_tray, bool):
        close_to_tray = True
    if not isinstance(active_controller_id, str) or not active_controller_id.strip():
        active_controller_id = None
    if not isinstance(auto_start_runtime, bool):
        auto_start_runtime = False
    return DesktopSettings(
        language=language,
        close_to_tray=close_to_tray,
        active_controller_id=active_controller_id,
        auto_start_runtime=auto_start_runtime,
        shortcuts_by_controller=shortcuts_by_controller,
    )


def save_desktop_settings(
    settings: DesktopSettings,
    path: Path | None = None,
) -> Path:
    if settings.language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"unsupported desktop language: {settings.language}")
    destination = Path(path or default_desktop_settings_path()).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(
        f".{destination.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        temporary.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination
