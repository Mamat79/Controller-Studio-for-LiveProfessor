from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from silemio_control_hub.controller_studio import (
    controller_profile_payload,
    default_controller_payload,
    editable_controller_payload,
    midi_binding_from_message,
    save_user_controller_profile,
    suggest_controller_profile_id,
    validate_controller_draft,
)
from silemio_control_hub.models import ControllerProfile, ProfileError


def test_profile_id_suggestion_is_schema_safe_and_accent_neutral():
    assert suggest_controller_profile_id("Béh/Ringer", "X Touch + Perso") == (
        "beh-ringer.x-touch-perso"
    )


def test_starter_profile_is_valid_and_round_trips():
    profile, payload = validate_controller_draft(default_controller_payload())
    assert profile.display_name == "Custom MIDI Controller"
    assert profile.bank_size == 8
    assert len(profile.controls) == 8
    assert ControllerProfile.from_dict(controller_profile_payload(profile)) == profile
    assert payload["status"] == "community"


def test_duplicate_is_personal_and_keeps_control_definitions():
    profile, _ = validate_controller_draft(default_controller_payload())
    duplicate = editable_controller_payload(profile, duplicate=True)
    cloned, _ = validate_controller_draft(duplicate)
    assert cloned.id == "custom.controller.custom"
    assert cloned.status == "community"
    assert cloned.controls == profile.controls


def test_user_profile_save_is_atomic_and_backs_up_replacement(tmp_path: Path):
    payload = default_controller_payload()
    first = save_user_controller_profile(payload, directory=tmp_path)
    assert first.path.is_file()
    assert first.backup_path is None

    payload["model"] = "MIDI Controller Mk II"
    with pytest.raises(ProfileError, match="existe déjà"):
        save_user_controller_profile(payload, directory=tmp_path)
    second = save_user_controller_profile(payload, directory=tmp_path, replace=True)
    assert second.backup_path is not None
    assert second.profile.profile_version == "1.0.1"
    assert json.loads(second.backup_path.read_text(encoding="utf-8"))["model"] == (
        "MIDI Controller"
    )
    assert json.loads(second.path.read_text(encoding="utf-8"))["model"] == (
        "MIDI Controller Mk II"
    )


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            SimpleNamespace(type="control_change", channel=0, control=74, value=63),
            {"message": "cc", "channel": 1, "number": 74},
        ),
        (
            SimpleNamespace(type="note_on", channel=9, note=40, velocity=127),
            {"message": "note", "channel": 10, "number": 40},
        ),
        (
            SimpleNamespace(type="pitchwheel", channel=2, pitch=42),
            {"message": "pitch_bend", "channel": 3},
        ),
    ],
)
def test_midi_learn_converts_common_messages(message, expected):
    assert midi_binding_from_message(message) == expected


def test_midi_learn_ignores_note_on_zero_and_unknown_messages():
    assert (
        midi_binding_from_message(
            SimpleNamespace(type="note_on", channel=0, note=40, velocity=0)
        )
        is None
    )
    assert midi_binding_from_message(SimpleNamespace(type="clock")) is None
