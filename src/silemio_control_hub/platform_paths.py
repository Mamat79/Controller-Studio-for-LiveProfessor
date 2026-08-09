"""Per-user platform paths with explicit packaged-launch awareness."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import uuid

from .identity import PREVIOUS_WINDOWS_PRODUCT_FOLDER, WINDOWS_PRODUCT_FOLDER


def _registry_local_app_data() -> Path | None:
    """Read the Explorer user-folder setting as a compatibility fallback."""

    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            value, _value_type = winreg.QueryValueEx(key, "Local AppData")
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    expanded = Path(os.path.expandvars(value)).expanduser()
    return expanded if expanded.is_absolute() else None


def _windows_unredirected_local_app_data() -> Path | None:
    """Ask Windows for the nominal Local AppData path without path substitution.

    Windows can still virtualize later file access when a packaged process owns
    the launch; callers must therefore treat the returned path as logical.
    """

    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _Guid(ctypes.Structure):
            _fields_ = [
                ("data1", wintypes.DWORD),
                ("data2", wintypes.WORD),
                ("data3", wintypes.WORD),
                ("data4", ctypes.c_ubyte * 8),
            ]

        folder_id = _Guid.from_buffer_copy(
            uuid.UUID("f1b32785-6fba-4fcf-9d55-7b8e7f157091").bytes_le
        )
        raw_path = ctypes.c_void_p()
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_Guid),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole32.CoTaskMemFree.restype = None
        # KF_FLAG_NO_PACKAGE_REDIRECTION keeps data stable when a packaged
        # launcher starts this ordinary desktop executable.
        result = shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id),
            0x00010000,
            None,
            ctypes.byref(raw_path),
        )
        if result != 0 or not raw_path.value:
            return None
        try:
            value = ctypes.wstring_at(raw_path.value)
        finally:
            ole32.CoTaskMemFree(raw_path)
        return Path(value) if value else None
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _windows_local_app_data() -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        buffer = ctypes.create_unicode_buffer(32768)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.SHGetFolderPathW.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
        ]
        shell32.SHGetFolderPathW.restype = ctypes.c_long
        result = shell32.SHGetFolderPathW(None, 0x001C, None, 0, buffer)
        if result == 0 and buffer.value:
            return Path(buffer.value)
    except (AttributeError, OSError, ValueError):
        return None
    return None


def local_app_data_dir() -> Path:
    """Return logical Local AppData, with an explicit test override."""

    override = os.environ.get("SILEMIO_LOCAL_APP_DATA")
    if override:
        return Path(override).expanduser()
    unredirected = _windows_unredirected_local_app_data()
    if unredirected is not None:
        return unredirected
    registry = _registry_local_app_data()
    if registry is not None:
        return registry
    native = _windows_local_app_data()
    if native is not None:
        return native
    environment = os.environ.get("LOCALAPPDATA")
    if environment:
        return Path(environment).expanduser()
    return Path.home() / ".local" / "share"


def product_data_dir() -> Path:
    """Authoritative per-user data root for Controller Studio."""

    return local_app_data_dir() / WINDOWS_PRODUCT_FOLDER


def previous_product_data_dir() -> Path:
    """Read-only migration source used by pre-V.2026 branded builds."""

    return local_app_data_dir() / PREVIOUS_WINDOWS_PRODUCT_FOLDER


def legacy_control_hub_data_dir() -> Path:
    """Read-only migration source used by pre-rename development builds."""

    return local_app_data_dir() / "SiLeMIO Control Hub"
