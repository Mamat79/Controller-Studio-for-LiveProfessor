import pytest

from silemio_control_hub.windows_tray import (
    TrayCommand,
    index_tray_commands,
    tray_action_for_event,
)


def test_tray_clicks_decode_plain_windows_events():
    assert tray_action_for_event(0x0202) == "open"
    assert tray_action_for_event(0x0203) == "open"
    assert tray_action_for_event(0x0205) == "menu"
    assert tray_action_for_event(0x007B) == "menu"
    assert tray_action_for_event(0x0201) is None


def test_tray_clicks_decode_packed_notifyicon_events():
    icon_id = 1 << 16
    assert tray_action_for_event(icon_id | 0x0202) == "open"
    assert tray_action_for_event(icon_id | 0x0205) == "menu"


def test_tray_commands_are_indexed_in_display_order():
    commands = (
        TrayCommand("start", "Start", lambda: None),
        TrayCommand("stop", "Stop", lambda: None, enabled=False),
    )

    indexed = index_tray_commands(commands)

    assert [(identifier, command.key, command.enabled) for identifier, command in indexed.items()] == [
        (3100, "start", True),
        (3101, "stop", False),
    ]


def test_tray_command_keys_must_be_unique():
    with pytest.raises(ValueError, match="unique"):
        index_tray_commands(
            (
                TrayCommand("start", "Start", lambda: None),
                TrayCommand("start", "Start again", lambda: None),
            )
        )
