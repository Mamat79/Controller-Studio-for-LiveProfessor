"""Small native Windows notification-area adapter extracted from proven UI behavior."""

from __future__ import annotations

import os
import queue
import sys
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True, slots=True)
class TrayCommand:
    """One application command exposed by the notification-area menu."""

    key: str
    label: str
    callback: Callable[[], None]
    enabled: bool = True


def index_tray_commands(
    commands: Iterable[TrayCommand], *, first_id: int = 3100
) -> dict[int, TrayCommand]:
    """Assign stable per-menu native identifiers and reject ambiguous keys."""

    indexed: dict[int, TrayCommand] = {}
    seen: set[str] = set()
    for offset, command in enumerate(commands):
        if not command.key or command.key in seen:
            raise ValueError("tray command keys must be non-empty and unique")
        seen.add(command.key)
        indexed[first_id + offset] = command
    return indexed


def tray_action_for_event(l_param: int) -> str | None:
    """Decode both legacy and NOTIFYICON_VERSION_4 packed mouse events."""

    event_code = int(l_param) & 0xFFFF
    if event_code in (0x0202, 0x0203):
        return "open"
    if event_code in (0x0205, 0x007B):
        return "menu"
    return None


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _UINT_PTR = (
        wintypes.UINT_PTR
        if hasattr(wintypes, "UINT_PTR")
        else (
            ctypes.c_uint64
            if ctypes.sizeof(ctypes.c_void_p) == 8
            else ctypes.c_uint32
        )
    )

    class _NotifyIconData(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HANDLE),
            ("szTip", wintypes.WCHAR * 128),
        ]

    _LRESULT = (
        ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
    )
    _WNDPROC = ctypes.WINFUNCTYPE(
        _LRESULT,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )

    class _WindowClass(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("style", wintypes.UINT),
            ("lpfnWndProc", _WNDPROC),
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

    class _Point(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    _WM_TASKBARICON = 0x0400 + 1
    _HWND_MESSAGE = -3
    _NIM_ADD = 0x0
    _NIM_MODIFY = 0x1
    _NIM_DELETE = 0x2
    _NIF_MESSAGE = 0x1
    _NIF_ICON = 0x2
    _NIF_TIP = 0x4
    _IDI_APPLICATION = 32512
    _IMAGE_ICON = 1
    _LR_LOADFROMFILE = 0x0010
    _SM_CXSMICON = 49
    _SM_CYSMICON = 50
    _MF_STRING = 0x0000
    _MF_SEPARATOR = 0x0800
    _MF_GRAYED = 0x0001
    _MF_DISABLED = 0x0002
    _TPM_RIGHTBUTTON = 0x0002
    _TPM_RETURN_CMD = 0x0100
    _TPM_NONOTIFY = 0x0080
    _MENU_OPEN = 3001
    _MENU_QUIT = 3007


class WindowsTray:
    """Notification-area icon with native left-click and context-menu behavior."""

    def __init__(
        self,
        root,
        *,
        tooltip: str,
        open_label: str,
        quit_label: str,
        on_quit: Callable[[], None],
        command_provider: Callable[[], Iterable[TrayCommand]] | None = None,
        icon_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self.root = root
        self.tooltip = tooltip
        self.open_label = open_label
        self.quit_label = quit_label
        self.on_quit = on_quit
        self.command_provider = command_provider
        self.icon_path = os.fspath(icon_path) if icon_path is not None else None
        self.available = False
        self._closing = False
        self._icon_created = False
        self._data = None
        self._action_queue: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._poll_after_id = None
        self._icon_handle = None
        self._owns_icon = False
        if sys.platform == "win32":
            try:
                self._setup()
            except Exception:
                self.available = False
            if self.available:
                self._poll_after_id = self.root.after(50, self._poll_actions)

    def _setup(self) -> None:
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._tray_hwnd = 0
        self._class_atom = 0
        self._class_name = f"SiLeMIOControlHubTray_{os.getpid()}_{id(self):x}"
        self._window_proc_handle = None
        self._hinstance = None

        self._user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self._user32.DefWindowProcW.restype = _LRESULT
        self._user32.RegisterClassExW.argtypes = [ctypes.POINTER(_WindowClass)]
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
        self._user32.GetCursorPos.argtypes = [ctypes.POINTER(_Point)]
        self._user32.GetCursorPos.restype = ctypes.c_int
        self._user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
        self._user32.LoadIconW.restype = wintypes.HANDLE
        self._user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        self._user32.LoadImageW.restype = wintypes.HANDLE
        self._user32.DestroyIcon.argtypes = [wintypes.HANDLE]
        self._user32.DestroyIcon.restype = ctypes.c_bool
        self._user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        self._user32.GetSystemMetrics.restype = ctypes.c_int
        self._user32.CreatePopupMenu.restype = wintypes.HMENU
        self._user32.AppendMenuW.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            _UINT_PTR,
            wintypes.LPCWSTR,
        ]
        self._user32.AppendMenuW.restype = ctypes.c_bool
        self._user32.TrackPopupMenu.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            ctypes.c_void_p,
        ]
        self._user32.TrackPopupMenu.restype = ctypes.c_int
        self._user32.DestroyMenu.argtypes = [wintypes.HMENU]
        self._user32.DestroyMenu.restype = ctypes.c_bool
        self._kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self._kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        self._shell32.Shell_NotifyIconW.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(_NotifyIconData),
        ]
        self._shell32.Shell_NotifyIconW.restype = ctypes.c_bool

        icon = None
        if self.icon_path and os.path.isfile(self.icon_path):
            icon = self._user32.LoadImageW(
                None,
                self.icon_path,
                _IMAGE_ICON,
                self._user32.GetSystemMetrics(_SM_CXSMICON),
                self._user32.GetSystemMetrics(_SM_CYSMICON),
                _LR_LOADFROMFILE,
            )
            self._owns_icon = bool(icon)
        if not icon:
            icon = self._user32.LoadIconW(None, ctypes.c_void_p(_IDI_APPLICATION))
        if not icon:
            return
        self._icon_handle = icon
        self._window_proc_handle = _WNDPROC(self._window_proc)
        self._hinstance = self._kernel32.GetModuleHandleW(None)
        window_class = _WindowClass()
        window_class.cbSize = ctypes.sizeof(_WindowClass)
        window_class.lpfnWndProc = self._window_proc_handle
        window_class.hInstance = self._hinstance
        window_class.hIcon = icon
        window_class.hIconSm = icon
        window_class.lpszClassName = self._class_name
        self._class_atom = int(
            self._user32.RegisterClassExW(ctypes.byref(window_class))
        )
        if not self._class_atom:
            return
        self._tray_hwnd = int(
            self._user32.CreateWindowExW(
                0,
                self._class_name,
                self._class_name,
                0,
                0,
                0,
                0,
                0,
                ctypes.c_void_p(_HWND_MESSAGE),
                None,
                self._hinstance,
                None,
            )
            or 0
        )
        if not self._tray_hwnd:
            self._user32.UnregisterClassW(self._class_name, self._hinstance)
            self._class_atom = 0
            return
        data = _NotifyIconData()
        data.cbSize = ctypes.sizeof(_NotifyIconData)
        data.hWnd = self._tray_hwnd
        data.uID = 1
        data.uFlags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP
        data.uCallbackMessage = _WM_TASKBARICON
        data.hIcon = ctypes.c_void_p(icon)
        data.szTip = self.tooltip[:127]
        self._data = data
        self.available = True

    def _window_proc(self, hwnd: int, msg: int, w_param: int, l_param: int) -> int:
        if msg == _WM_TASKBARICON:
            action = tray_action_for_event(l_param)
            if action is not None:
                self._action_queue.put(action)
            return 0
        return self._user32.DefWindowProcW(hwnd, msg, w_param, l_param)

    def _poll_actions(self) -> None:
        self._poll_after_id = None
        if self._closing:
            return
        while True:
            try:
                action = self._action_queue.get_nowait()
            except queue.Empty:
                break
            if action == "open":
                self.restore()
            elif action == "menu":
                self._show_menu()
        self._poll_after_id = self.root.after(50, self._poll_actions)

    def _ensure_icon(self) -> bool:
        if not self.available or self._icon_created or self._data is None:
            return self._icon_created
        self._icon_created = bool(
            self._shell32.Shell_NotifyIconW(_NIM_ADD, ctypes.byref(self._data))
        )
        return self._icon_created

    def _show_menu(self) -> None:
        if not self.available or not self._ensure_icon():
            return
        menu = self._user32.CreatePopupMenu()
        if not menu:
            return
        try:
            self._user32.AppendMenuW(menu, _MF_STRING, _MENU_OPEN, self.open_label)
            indexed_commands: dict[int, TrayCommand] = {}
            if self.command_provider is not None:
                indexed_commands = index_tray_commands(tuple(self.command_provider()))
            if indexed_commands:
                self._user32.AppendMenuW(menu, _MF_SEPARATOR, 0, "")
                for command_id, command in indexed_commands.items():
                    flags = _MF_STRING
                    if not command.enabled:
                        flags |= _MF_GRAYED | _MF_DISABLED
                    self._user32.AppendMenuW(menu, flags, command_id, command.label)
            self._user32.AppendMenuW(menu, _MF_SEPARATOR, 0, "")
            self._user32.AppendMenuW(menu, _MF_STRING, _MENU_QUIT, self.quit_label)
            self._user32.SetForegroundWindow(self._tray_hwnd)
            point = _Point()
            if self._user32.GetCursorPos(ctypes.byref(point)) == 0:
                return
            selected = self._user32.TrackPopupMenu(
                menu,
                _TPM_RIGHTBUTTON | _TPM_RETURN_CMD | _TPM_NONOTIFY,
                int(point.x),
                int(point.y),
                0,
                self._tray_hwnd,
                None,
            )
            if selected == _MENU_OPEN:
                self.restore()
            elif selected == _MENU_QUIT:
                self.on_quit()
            elif selected in indexed_commands:
                command = indexed_commands[selected]
                if command.enabled:
                    command.callback()
        finally:
            self._user32.DestroyMenu(menu)

    def update_labels(self, *, tooltip: str, open_label: str, quit_label: str) -> None:
        self.tooltip = tooltip
        self.open_label = open_label
        self.quit_label = quit_label
        if self._data is not None:
            self._data.szTip = tooltip[:127]
            if self._icon_created:
                self._shell32.Shell_NotifyIconW(_NIM_MODIFY, ctypes.byref(self._data))

    def hide(self) -> None:
        if self.available and self._ensure_icon():
            self.root.withdraw()
        else:
            self.root.iconify()

    def restore(self) -> None:
        if self._closing:
            return
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except Exception:
                pass
            self._poll_after_id = None
        if sys.platform == "win32" and self.available:
            if self._icon_created and self._data is not None:
                try:
                    self._shell32.Shell_NotifyIconW(
                        _NIM_DELETE, ctypes.byref(self._data)
                    )
                except Exception:
                    pass
            if self._tray_hwnd:
                try:
                    self._user32.DestroyWindow(self._tray_hwnd)
                except Exception:
                    pass
            if self._class_atom:
                try:
                    self._user32.UnregisterClassW(
                        self._class_name, self._hinstance
                    )
                except Exception:
                    pass
            if self._owns_icon and self._icon_handle:
                try:
                    self._user32.DestroyIcon(self._icon_handle)
                except Exception:
                    pass
                self._icon_handle = None
                self._owns_icon = False
        self.available = False
