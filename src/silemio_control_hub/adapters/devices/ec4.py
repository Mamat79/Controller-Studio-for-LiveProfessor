from __future__ import annotations

from typing import Any

from .ec4_protocol import (
    main_display_message,
    parameter_grid_message,
    parse_button_sysex,
    parse_setup_response,
)

from ...events import (
    ControlFeedback,
    DeviceStateEvent,
    DisplayFeedback,
    ModifierEvent,
    PressEvent,
)
from ...models import ControllerProfile
from ...registry import ControllerRegistry
from ...state import ControllerState
from .profile_midi import ProfileMidiDeviceAdapter


def _sysex_bytes(message: Any) -> bytes | None:
    if getattr(message, "type", None) == "sysex":
        return bytes((0xF0, *getattr(message, "data", ()), 0xF7))
    if isinstance(message, (bytes, bytearray, tuple, list)):
        return bytes(message)
    return None


class EC4DeviceAdapter(ProfileMidiDeviceAdapter):
    """EC4 specialization over the profile-driven MIDI adapter."""

    profile_id = "faderfox.ec4"

    def __init__(
        self,
        profile: ControllerProfile | None = None,
        state: ControllerState | None = None,
    ) -> None:
        super().__init__(profile or ControllerRegistry().get(self.profile_id), state)

    def decode(self, message: Any) -> tuple[object, ...]:
        data = _sysex_bytes(message)
        if data is None or not data.startswith(bytes((0xF0,))):
            return super().decode(message)
        setup = parse_setup_response(data)
        if setup is not None:
            return (
                DeviceStateEvent("setup", {"setup": setup.setup, "group": setup.group}),
            )
        button = parse_button_sysex(data)
        if button is None:
            return ()
        if button.kind == "shift":
            active = self.state.set_modifier("shift", button.pressed)
            return (ModifierEvent("shift", active, self.state.context),)
        if button.kind == "shift_push" and button.index is not None:
            if button.pressed and "shift" not in self.state.modifiers:
                self.state.set_modifier("shift", True)
            return (
                PressEvent(
                    f"encoder_{button.index + 1:02d}",
                    button.pressed,
                    self.state.context,
                ),
            )
        return (
            DeviceStateEvent(
                "device_button",
                {"kind": button.kind, "index": button.index, "pressed": button.pressed},
            ),
        )

    def encode_feedback(self, feedback: Any) -> tuple[bytes, ...]:
        if isinstance(feedback, ControlFeedback):
            return super().encode_feedback(feedback)
        if isinstance(feedback, DisplayFeedback):
            labels = list(feedback.labels)
            mode = feedback.mode
        elif isinstance(feedback, dict):
            labels = feedback.get("labels")
            if not isinstance(labels, list):
                return ()
            labels = [str(item) for item in labels]
            mode = str(feedback.get("mode", "grid"))
        else:
            return ()
        if mode == "main":
            return (main_display_message(labels),)
        return (parameter_grid_message(labels),)
