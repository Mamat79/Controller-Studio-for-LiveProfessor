"""Per-user startup registration for Windows and macOS."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import plistlib
import sys

from .identity import FULL_PRODUCT_NAME
from .windows_startup import (
    set_start_with_windows,
    starts_with_windows,
)


MACOS_LAUNCH_AGENT_ID = "io.silemio.controller-studio"


def startup_arguments(
    executable: str | Path | None = None,
    *,
    frozen: bool | None = None,
) -> tuple[str, ...]:
    target = Path(executable or sys.executable).expanduser().resolve()
    packaged = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    arguments = [str(target)]
    if not packaged:
        arguments.extend(("-m", "silemio_control_hub.desktop"))
    arguments.append("--minimized")
    return tuple(arguments)


def macos_launch_agent_path(base_directory: Path | None = None) -> Path:
    root = Path(base_directory) if base_directory is not None else Path.home() / "Library" / "LaunchAgents"
    return root / f"{MACOS_LAUNCH_AGENT_ID}.plist"


def _macos_launch_agent_payload(arguments: Sequence[str]) -> bytes:
    return plistlib.dumps(
        {
            "Label": MACOS_LAUNCH_AGENT_ID,
            "ProgramArguments": [str(item) for item in arguments],
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        },
        fmt=plistlib.FMT_XML,
        sort_keys=True,
    )


def starts_with_system(
    command: str | Sequence[str] | None = None,
    *,
    platform_name: str | None = None,
    launch_agents_dir: Path | None = None,
) -> bool:
    active_platform = platform_name or sys.platform
    if active_platform == "win32":
        return starts_with_windows(command if isinstance(command, str) else None)
    if active_platform != "darwin":
        return False
    arguments = tuple(command) if command is not None and not isinstance(command, str) else startup_arguments()
    path = macos_launch_agent_path(launch_agents_dir)
    try:
        payload = plistlib.loads(path.read_bytes())
    except (FileNotFoundError, OSError, plistlib.InvalidFileException):
        return False
    return (
        payload.get("Label") == MACOS_LAUNCH_AGENT_ID
        and payload.get("ProgramArguments") == list(arguments)
        and payload.get("RunAtLoad") is True
    )


def set_start_with_system(
    enabled: bool,
    command: str | Sequence[str] | None = None,
    *,
    platform_name: str | None = None,
    launch_agents_dir: Path | None = None,
) -> None:
    active_platform = platform_name or sys.platform
    if active_platform == "win32":
        set_start_with_windows(enabled, command if isinstance(command, str) else None)
        return
    if active_platform != "darwin":
        raise OSError(f"startup registration is unavailable on {active_platform}")
    path = macos_launch_agent_path(launch_agents_dir)
    if not enabled:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    arguments = tuple(command) if command is not None and not isinstance(command, str) else startup_arguments()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".plist.tmp")
    temporary.write_bytes(_macos_launch_agent_payload(arguments))
    temporary.replace(path)


def startup_platform_label(platform_name: str | None = None) -> str:
    active_platform = platform_name or sys.platform
    if active_platform == "darwin":
        return "macOS"
    if active_platform == "win32":
        return "Windows"
    return FULL_PRODUCT_NAME
