from __future__ import annotations

from typing import Any

from ...events import ControlFeedback, ModifierEvent, PressEvent, RotationEvent, TouchEvent
from ...models import (
    ControlDefinition,
    ControlKind,
    ControllerProfile,
    MessageKind,
    MidiBinding,
)
from ...state import ControllerState
from ..base import DeviceAdapter


def _message_identity(message: Any) -> tuple[MessageKind, int | None, int | None] | None:
    message_type = getattr(message, "type", None)
    channel = getattr(message, "channel", None)
    profile_channel = channel + 1 if isinstance(channel, int) else None
    if message_type == "control_change":
        return MessageKind.CC, profile_channel, getattr(message, "control", None)
    if message_type in {"note_on", "note_off"}:
        return MessageKind.NOTE, profile_channel, getattr(message, "note", None)
    if message_type == "pitchwheel":
        return MessageKind.PITCH_BEND, profile_channel, None
    return None


def _pressed(message: Any) -> bool:
    message_type = getattr(message, "type", None)
    if message_type == "note_off":
        return False
    if message_type == "note_on":
        return int(getattr(message, "velocity", 0)) > 0
    if message_type == "control_change":
        return int(getattr(message, "value", 0)) >= 64
    return bool(getattr(message, "value", 0))


def decode_relative(value: int, mode: str) -> float:
    if not 0 <= value <= 127:
        raise ValueError("une valeur MIDI relative doit être comprise entre 0 et 127")
    if mode == "twos_complement":
        return float(value if value <= 63 else value - 128)
    if mode == "binary_offset":
        return float(value - 64)
    if mode == "signed_bit":
        return float(-(value & 0x3F) if value & 0x40 else value & 0x3F)
    if mode == "increment_decrement":
        if value == 1:
            return 1.0
        if value == 127:
            return -1.0
        return 0.0
    raise ValueError(f"mode MIDI relatif inconnu: {mode}")


def _normalized_value(message: Any) -> float:
    message_type = getattr(message, "type", None)
    if message_type == "pitchwheel":
        return max(0.0, min(1.0, (int(getattr(message, "pitch", 0)) + 8192) / 16383))
    return max(0.0, min(1.0, int(getattr(message, "value", 0)) / 127))


def _binding_bytes(binding: MidiBinding, normalized: float) -> bytes:
    value = max(0, min(127, round(normalized * 127)))
    channel = (binding.channel or 1) - 1
    if binding.message == MessageKind.CC:
        return bytes((0xB0 | channel, binding.number or 0, value))
    if binding.message == MessageKind.NOTE:
        return bytes((0x90 | channel, binding.number or 0, value))
    if binding.message == MessageKind.PITCH_BEND:
        wide = max(0, min(16383, round(normalized * 16383)))
        return bytes((0xE0 | channel, wide & 0x7F, (wide >> 7) & 0x7F))
    return b""


class ProfileMidiDeviceAdapter(DeviceAdapter):
    """Profile-driven MIDI adapter producing hardware-neutral events."""

    def __init__(self, profile: ControllerProfile, state: ControllerState | None = None) -> None:
        self.profile = profile
        self.profile_id = profile.id
        self.state = state or ControllerState(profile)
        self._inputs: dict[tuple[MessageKind, int | None, int | None], ControlDefinition] = {}
        self._pushes: dict[tuple[MessageKind, int | None, int | None], ControlDefinition] = {}
        self._touches: dict[tuple[MessageKind, int | None, int | None], ControlDefinition] = {}
        self._modifiers: dict[tuple[MessageKind, int | None, int | None], str] = {}
        for control in profile.controls:
            if control.input.message != MessageKind.SYSEX:
                self._inputs[self._key(control.input)] = control
            if control.push is not None and control.push.message != MessageKind.SYSEX:
                self._pushes[self._key(control.push)] = control
            if control.touch is not None and control.touch.message != MessageKind.SYSEX:
                self._touches[self._key(control.touch)] = control
        for modifier in profile.modifiers:
            if modifier.input.message != MessageKind.SYSEX:
                self._modifiers[self._key(modifier.input)] = modifier.id

    @staticmethod
    def _key(binding: MidiBinding) -> tuple[MessageKind, int | None, int | None]:
        return binding.message, binding.channel, binding.number

    def decode(self, message: Any) -> tuple[object, ...]:
        identity = _message_identity(message)
        if identity is None:
            return ()
        modifier_id = self._modifiers.get(identity)
        if modifier_id is not None:
            active = self.state.set_modifier(modifier_id, _pressed(message))
            return (ModifierEvent(modifier_id, active, self.state.context),)
        control = self._pushes.get(identity)
        if control is not None:
            return (PressEvent(control.id, _pressed(message), self.state.context),)
        control = self._touches.get(identity)
        if control is not None:
            return (TouchEvent(control.id, _pressed(message), self.state.context),)
        control = self._inputs.get(identity)
        if control is None:
            return ()
        if control.kind == ControlKind.RELATIVE_ENCODER:
            raw_value = int(getattr(message, "value", 0))
            return (
                RotationEvent(
                    control.id,
                    self.state.context,
                    delta=decode_relative(raw_value, control.input.mode or ""),
                ),
            )
        if control.supports_rotation:
            return (
                RotationEvent(control.id, self.state.context, value=_normalized_value(message)),
            )
        return (PressEvent(control.id, _pressed(message), self.state.context),)

    def encode_feedback(self, feedback: Any) -> tuple[bytes, ...]:
        if not isinstance(feedback, ControlFeedback):
            return ()
        try:
            control = self.profile.control(feedback.control_id)
        except KeyError:
            return ()
        if control.feedback is None:
            return ()
        messages: list[bytes] = []
        if feedback.value is not None and control.feedback.value is not None:
            encoded = _binding_bytes(control.feedback.value, feedback.value)
            if encoded:
                messages.append(encoded)
        if feedback.led is not None and control.feedback.led is not None:
            encoded = _binding_bytes(control.feedback.led, 1.0 if feedback.led else 0.0)
            if encoded:
                messages.append(encoded)
        if feedback.color is not None:
            colors = control.feedback.supported_colors
            if feedback.color not in colors:
                return tuple(messages)
            if control.feedback.color is not None and len(colors) > 1:
                encoded = _binding_bytes(
                    control.feedback.color,
                    colors.index(feedback.color) / (len(colors) - 1),
                )
                if encoded:
                    messages.append(encoded)
        return tuple(messages)
