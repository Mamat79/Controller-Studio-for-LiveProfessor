"""Per-user Windows startup registration for the desktop application."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from .identity import FULL_PRODUCT_NAME

try:  # pragma: no cover - imported only on Windows in production
    import winreg as _winreg
except ImportError:  # pragma: no cover - exercised by Linux CI through the guard
    _winreg = None


RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = FULL_PRODUCT_NAME


def startup_command(
    executable: str | Path | None = None,
    *,
    frozen: bool | None = None,
) -> str:
    """Return the quoted command registered for a quiet notification-area launch."""

    target = Path(executable or sys.executable).expanduser().resolve()
    packaged = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    parts = [str(target)]
    if not packaged:
        parts.extend(("-m", "silemio_control_hub.desktop"))
    parts.append("--minimized")
    return subprocess.list2cmdline(parts)


def _registry_module():
    if _winreg is None:
        raise OSError("Windows startup registration is only available on Windows")
    return _winreg


def read_startup_command() -> str | None:
    """Read the current per-user startup command without changing the registry."""

    registry = _registry_module()
    try:
        with registry.OpenKey(
            registry.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            registry.KEY_QUERY_VALUE,
        ) as key:
            value, value_type = registry.QueryValueEx(key, RUN_VALUE_NAME)
    except FileNotFoundError:
        return None
    if value_type != registry.REG_SZ or not isinstance(value, str) or not value.strip():
        return None
    return value


def starts_with_windows(command: str | None = None) -> bool:
    """Return whether the current application command is registered at sign-in."""

    expected = command or startup_command()
    try:
        registered = read_startup_command()
    except OSError:
        return False
    return registered == expected


def set_start_with_windows(enabled: bool, command: str | None = None) -> None:
    """Create or remove the per-user startup entry."""

    registry = _registry_module()
    if enabled:
        with registry.CreateKeyEx(
            registry.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            registry.KEY_SET_VALUE,
        ) as key:
            registry.SetValueEx(
                key,
                RUN_VALUE_NAME,
                0,
                registry.REG_SZ,
                command or startup_command(),
            )
        return

    try:
        with registry.OpenKey(
            registry.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            registry.KEY_SET_VALUE,
        ) as key:
            registry.DeleteValue(key, RUN_VALUE_NAME)
    except FileNotFoundError:
        return
