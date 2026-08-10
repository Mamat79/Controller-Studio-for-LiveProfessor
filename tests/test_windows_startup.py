from pathlib import Path

import silemio_control_hub.windows_startup as windows_startup


class _Key:
    def __init__(self, registry):
        self.registry = registry

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Registry:
    HKEY_CURRENT_USER = object()
    KEY_QUERY_VALUE = 1
    KEY_SET_VALUE = 2
    REG_SZ = 3

    def __init__(self):
        self.values = {}

    def OpenKey(self, _root, path, _reserved, _access):
        if path not in self.values:
            raise FileNotFoundError(path)
        return _Key(self)

    def CreateKeyEx(self, _root, path, _reserved, _access):
        self.values.setdefault(path, {})
        return _Key(self)

    def QueryValueEx(self, _key, name):
        try:
            return self.values[windows_startup.RUN_KEY_PATH][name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc

    def SetValueEx(self, _key, name, _reserved, value_type, value):
        self.values[windows_startup.RUN_KEY_PATH][name] = (value, value_type)

    def DeleteValue(self, _key, name):
        try:
            del self.values[windows_startup.RUN_KEY_PATH][name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc


def test_packaged_startup_command_is_quoted_and_minimized(tmp_path):
    executable = tmp_path / "Controller Studio" / "Controller Studio.exe"

    command = windows_startup.startup_command(executable, frozen=True)

    assert command == f'"{executable.resolve()}" --minimized'


def test_development_startup_command_invokes_desktop_module(tmp_path):
    python = tmp_path / "Python Runtime" / "python.exe"

    command = windows_startup.startup_command(python, frozen=False)

    assert command == (
        f'"{python.resolve()}" -m silemio_control_hub.desktop --minimized'
    )


def test_startup_registration_round_trip(monkeypatch):
    registry = _Registry()
    monkeypatch.setattr(windows_startup, "_winreg", registry)
    command = r'"C:\Apps\Controller Studio.exe" --minimized'

    assert windows_startup.starts_with_windows(command) is False

    windows_startup.set_start_with_windows(True, command)

    assert windows_startup.read_startup_command() == command
    assert windows_startup.starts_with_windows(command) is True

    windows_startup.set_start_with_windows(False, command)

    assert windows_startup.read_startup_command() is None


def test_disabling_absent_startup_registration_is_idempotent(monkeypatch):
    registry = _Registry()
    monkeypatch.setattr(windows_startup, "_winreg", registry)

    windows_startup.set_start_with_windows(False)
