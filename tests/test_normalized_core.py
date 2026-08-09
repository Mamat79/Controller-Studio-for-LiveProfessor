from types import SimpleNamespace

import pytest

from silemio_control_hub.adapters.devices import (
    EC4DeviceAdapter,
    GenericMidiDeviceAdapter,
    ProfileMidiDeviceAdapter,
)
from silemio_control_hub.events import (
    ControlFeedback,
    ModifierEvent,
    PressEvent,
    RotationEvent,
    TouchEvent,
)
from silemio_control_hub.models import ControllerProfile, ProfileError
from silemio_control_hub.registry import ControllerRegistry
from silemio_control_hub.simulator import ControllerSimulator
from silemio_control_hub.state import ControllerState


def _profile(**changes):
    raw = {
        "schema_version": 1,
        "id": "test.normalized",
        "manufacturer": "Test",
        "model": "Normalized",
        "bank_size": 3,
        "bank_count": 2,
        "page_count": 2,
        "capabilities": ["commands", "push", "touch", "values", "banks", "pages", "modifiers"],
        "controls": [
            {
                "id": "absolute",
                "kind": "absolute_encoder",
                "input": {"message": "cc", "channel": 1, "number": 10},
                "push": {"message": "note", "channel": 1, "number": 10},
                "feedback": {"value": {"message": "cc", "channel": 1, "number": 10}},
            },
            {
                "id": "relative",
                "kind": "relative_encoder",
                "input": {
                    "message": "cc",
                    "channel": 1,
                    "number": 11,
                    "mode": "twos_complement",
                },
            },
            {
                "id": "fader",
                "kind": "fader",
                "input": {"message": "cc", "channel": 1, "number": 12},
                "touch": {"message": "note", "channel": 1, "number": 12},
            },
        ],
        "modifiers": [
            {
                "id": "shift",
                "input": {"message": "note", "channel": 1, "number": 100},
                "behavior": "momentary",
            }
        ],
    }
    raw.update(changes)
    return ControllerProfile.from_dict(raw)


def test_ec4_profile_matches_verified_absolute_mapping():
    profile = ControllerRegistry().get("faderfox.ec4")
    first = profile.control("encoder_01")
    last = profile.control("encoder_16")
    assert first.kind.value == "absolute_encoder"
    assert (first.input.channel, first.input.number) == (13, 48)
    assert (last.input.channel, last.input.number) == (14, 80)
    assert (first.push.channel, first.push.number) == (13, 40)
    assert (last.push.channel, last.push.number) == (13, 55)
    assert profile.bank_count == 7
    assert profile.profile_version == "1.0.0"
    assert profile.last_bank_size == 3
    assert len(profile.controls_for_bank(6)) == 3
    assert [modifier.id for modifier in profile.modifiers] == ["shift"]


def test_profile_rejects_unknown_fields_and_unknown_capabilities():
    with pytest.raises(ProfileError, match="champs inconnus: executable"):
        _profile(executable="do-not-run")
    with pytest.raises(ProfileError, match="valeurs inconnues: network"):
        _profile(capabilities=["commands", "network"])


def test_profile_requires_relative_mode_and_unique_bindings():
    raw = {
        "schema_version": 1,
        "id": "test.relative",
        "manufacturer": "Test",
        "model": "Relative",
        "bank_size": 1,
        "controls": [
            {
                "id": "encoder",
                "kind": "relative_encoder",
                "input": {"message": "cc", "channel": 1, "number": 1},
            }
        ],
    }
    with pytest.raises(ProfileError, match="mode relatif"):
        ControllerProfile.from_dict(raw)
    raw["controls"][0]["input"]["mode"] = "twos_complement"
    raw["controls"].append(
        {
            "id": "duplicate",
            "kind": "relative_encoder",
            "input": {
                "message": "cc",
                "channel": 1,
                "number": 1,
                "mode": "twos_complement",
            },
        }
    )
    with pytest.raises(ProfileError, match="liaison MIDI dupliquée"):
        ControllerProfile.from_dict(raw)

    raw["controls"][1]["input"]["mode"] = "binary_offset"
    with pytest.raises(ProfileError, match="liaison MIDI dupliquée"):
        ControllerProfile.from_dict(raw)


def test_profile_midi_adapter_normalizes_rotation_press_touch_and_modifier():
    adapter = ProfileMidiDeviceAdapter(_profile())
    absolute = adapter.decode(
        SimpleNamespace(type="control_change", channel=0, control=10, value=64)
    )[0]
    relative = adapter.decode(
        SimpleNamespace(type="control_change", channel=0, control=11, value=127)
    )[0]
    pressed = adapter.decode(
        SimpleNamespace(type="note_on", channel=0, note=10, velocity=127)
    )[0]
    touched = adapter.decode(
        SimpleNamespace(type="note_on", channel=0, note=12, velocity=127)
    )[0]
    modifier = adapter.decode(
        SimpleNamespace(type="note_on", channel=0, note=100, velocity=127)
    )[0]

    assert isinstance(absolute, RotationEvent)
    assert absolute.value == pytest.approx(64 / 127)
    assert isinstance(relative, RotationEvent)
    assert relative.delta == -1
    assert isinstance(pressed, PressEvent) and pressed.pressed
    assert isinstance(touched, TouchEvent) and touched.touched
    assert isinstance(modifier, ModifierEvent) and modifier.active
    assert modifier.context.modifiers == frozenset({"shift"})


def test_profile_midi_adapter_encodes_value_feedback():
    adapter = ProfileMidiDeviceAdapter(_profile())
    assert adapter.encode_feedback(ControlFeedback("absolute", value=0.5)) == (
        bytes((0xB0, 10, 64)),
    )


def test_generic_and_ec4_adapters_emit_normalized_events():
    generic = GenericMidiDeviceAdapter()
    generic_event = generic.decode(
        SimpleNamespace(type="control_change", channel=0, control=0, value=127)
    )[0]
    assert generic_event == RotationEvent("control_01", value=1.0)

    ec4 = EC4DeviceAdapter()
    rotation = ec4.decode(
        SimpleNamespace(type="control_change", channel=12, control=48, value=32)
    )[0]
    push = ec4.decode(
        SimpleNamespace(type="note_on", channel=12, note=40, velocity=127)
    )[0]
    shift = ec4.decode(
        SimpleNamespace(
            type="sysex",
            data=tuple(bytes.fromhex("00 00 00 4e 2c 1b 4e 26 11 4e 2e 11")),
        )
    )[0]
    assert rotation.control_id == "encoder_01"
    assert rotation.value == pytest.approx(32 / 127)
    assert push == PressEvent("encoder_01", True)
    assert isinstance(shift, ModifierEvent)
    assert shift.context.modifiers == frozenset({"shift"})


def test_controller_state_clamps_layers_and_tracks_modifiers():
    state = ControllerState(_profile())
    assert state.set_bank(99) == 1
    assert state.set_page(99) == 1
    assert state.set_modifier("shift", True)
    assert state.context.bank == 1
    assert state.context.page == 1
    assert state.context.modifiers == frozenset({"shift"})
    assert not state.set_modifier("shift", False)


def test_simulator_uses_the_same_normalized_event_contract():
    simulator = ControllerSimulator(_profile())
    simulator.set_bank(1)
    simulator.set_page(1)
    simulator.modifier("shift")
    event = simulator.rotate("absolute", 0.25)
    assert event.value == 0.25
    assert event.context.bank == 1
    assert event.context.page == 1
    assert event.context.modifiers == frozenset({"shift"})
    with pytest.raises(ValueError, match="toucher"):
        simulator.touch("absolute")
