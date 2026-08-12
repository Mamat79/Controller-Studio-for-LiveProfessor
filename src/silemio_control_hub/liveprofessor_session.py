"""Conservative discovery of the project currently loaded by LiveProfessor."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True, slots=True)
class LiveProfessorSession:
    running: bool
    project_path: Path | None = None
    source: str | None = None


def _liveprofessor_is_running_windows() -> bool:
    if os.name != "nt":
        return False

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return False
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        has_entry = bool(kernel32.Process32FirstW(snapshot, ctypes.byref(entry)))
        while has_entry:
            executable = entry.szExeFile.casefold()
            if executable.startswith("liveprofessor") and executable.endswith(".exe"):
                return True
            has_entry = bool(kernel32.Process32NextW(snapshot, ctypes.byref(entry)))
    finally:
        kernel32.CloseHandle(snapshot)
    return False


def _default_settings_dirs() -> tuple[Path, ...]:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return ()
    vendor = Path(appdata) / "audiostrom"
    if not vendor.is_dir():
        return ()
    candidates = tuple(
        path for path in vendor.iterdir()
        if path.is_dir() and path.name.casefold().startswith("liveprofessor")
    )
    return tuple(sorted(candidates, key=lambda path: path.name.casefold(), reverse=True))


def _first_existing_recent_project(settings_dir: Path) -> Path | None:
    recent_projects = settings_dir / "RecentProjects.xml"
    if not recent_projects.is_file():
        return None
    try:
        root = ET.parse(recent_projects).getroot()
    except (OSError, ET.ParseError):
        return None
    for item in root.findall(".//ProjectFile"):
        raw_path = item.get("file", "").strip()
        if not raw_path:
            continue
        candidate = Path(os.path.expandvars(raw_path)).expanduser()
        if candidate.is_file() and candidate.suffix.casefold() == ".rack2":
            return candidate.resolve()
        # Only the first recorded project can represent the project currently
        # loaded. Falling back to an older entry would be unsafe.
        return None
    return None


def detect_liveprofessor_session(
    *,
    settings_dirs: tuple[Path, ...] | None = None,
    process_running: bool | None = None,
) -> LiveProfessorSession:
    """Return a project only when LiveProfessor is confirmed running.

    LiveProfessor 2 records the loaded/recent projects in order. The first existing
    entry is therefore used as an explicit candidate and is always shown to the user
    for confirmation before Controller Studio reads it.
    """

    running = (
        _liveprofessor_is_running_windows()
        if process_running is None
        else bool(process_running)
    )
    if not running:
        return LiveProfessorSession(running=False)

    override = os.environ.get("SILEMIO_LIVEPROFESSOR_CURRENT_PROJECT", "").strip()
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file() and candidate.suffix.casefold() == ".rack2":
            return LiveProfessorSession(True, candidate.resolve(), "environment")

    for settings_dir in settings_dirs or _default_settings_dirs():
        project = _first_existing_recent_project(Path(settings_dir))
        if project is not None:
            return LiveProfessorSession(True, project, "recent_projects")
    return LiveProfessorSession(running=True)
