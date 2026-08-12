import json

import pytest

from silemio_control_hub.desktop_settings import (
    DesktopSettings,
    default_desktop_settings_path,
    load_desktop_settings,
    save_desktop_settings,
)


def test_desktop_settings_round_trip_is_atomic(tmp_path):
    path = tmp_path / "settings.json"

    saved = save_desktop_settings(
        DesktopSettings(
            language="en",
            close_to_tray=False,
            active_controller_id="behringer.x-touch-compact.layer-a",
            auto_start_runtime=True,
            shortcuts_by_controller={
                "faderfox.ec4": {
                    "shift+encoder_01": "next_bank",
                    "encoder_16": "",
                }
            },
        ),
        path,
    )

    assert saved == path.resolve()
    assert load_desktop_settings(path) == DesktopSettings(
        language="en",
        close_to_tray=False,
        active_controller_id="behringer.x-touch-compact.layer-a",
        auto_start_runtime=True,
        shortcuts_by_controller={
            "faderfox.ec4": {
                "shift+encoder_01": "next_bank",
                "encoder_16": "",
            }
        },
    )
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_desktop_settings_fall_back_without_rewriting(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"language": "xx", "close_to_tray": "yes"}),
        encoding="utf-8",
    )

    assert load_desktop_settings(path) == DesktopSettings()
    assert json.loads(path.read_text(encoding="utf-8"))["language"] == "xx"


def test_default_settings_path_uses_local_app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("SILEMIO_LOCAL_APP_DATA", str(tmp_path))

    assert default_desktop_settings_path() == (
        tmp_path / "Controller Studio for LiveProfessor" / "desktop-settings.json"
    )


def test_previous_branded_settings_are_loaded_without_being_moved(tmp_path, monkeypatch):
    monkeypatch.setenv("SILEMIO_LOCAL_APP_DATA", str(tmp_path))
    previous = tmp_path / "SiLeMIO Controller Studio" / "desktop-settings.json"
    previous.parent.mkdir(parents=True)
    previous.write_text(
        json.dumps({"language": "en", "close_to_tray": False}),
        encoding="utf-8",
    )

    assert load_desktop_settings() == DesktopSettings(
        language="en", close_to_tray=False
    )
    assert previous.is_file()
    assert not default_desktop_settings_path().exists()


def test_pre_rename_settings_are_loaded_without_being_moved(tmp_path, monkeypatch):
    monkeypatch.setenv("SILEMIO_LOCAL_APP_DATA", str(tmp_path))
    legacy = tmp_path / "SiLeMIO Control Hub" / "desktop-settings.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps({"language": "en", "close_to_tray": False}),
        encoding="utf-8",
    )

    assert load_desktop_settings() == DesktopSettings(
        language="en", close_to_tray=False
    )
    assert legacy.is_file()
    assert not default_desktop_settings_path().exists()


def test_unsupported_language_is_never_persisted(tmp_path):
    with pytest.raises(ValueError, match="unsupported desktop language"):
        save_desktop_settings(DesktopSettings(language="de"), tmp_path / "settings.json")


def test_empty_active_controller_is_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "language": "fr",
                "close_to_tray": True,
                "active_controller_id": "",
                "auto_start_runtime": "yes",
            }
        ),
        encoding="utf-8",
    )

    assert load_desktop_settings(path).active_controller_id is None
    assert load_desktop_settings(path).auto_start_runtime is False


def test_invalid_shortcut_settings_are_filtered(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "shortcuts_by_controller": {
                    "faderfox.ec4": {
                        "shift+encoder_01": "next_bank",
                        "shift+encoder_02": "not-an-action",
                        "encoder_16": "",
                    },
                    "bad": "not-a-dictionary",
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_desktop_settings(path).shortcuts_by_controller == {
        "faderfox.ec4": {
            "shift+encoder_01": "next_bank",
            "encoder_16": "",
        }
    }
