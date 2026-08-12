import json
from pathlib import Path

from silemio_control_hub.controller_shortcuts import (
    EC4_DEFAULT_SHORTCUTS,
    configurable_shortcut_bindings,
    effective_shortcuts,
)
from silemio_control_hub.models import ControllerProfile


ROOT = Path(__file__).resolve().parents[1]


def load_profile(name: str) -> ControllerProfile:
    payload = json.loads(
        (ROOT / "src" / "silemio_control_hub" / "controller_profiles" / name).read_text(
            encoding="utf-8"
        )
    )
    return ControllerProfile.from_dict(payload)


def test_ec4_factory_shortcuts_preserve_bridge_behavior():
    profile = load_profile("faderfox-ec4.json")

    assert effective_shortcuts(profile, {}) == EC4_DEFAULT_SHORTCUTS
    assert "encoder_16" in configurable_shortcut_bindings(profile)
    assert "shift+encoder_01" in configurable_shortcut_bindings(profile)


def test_controller_override_can_reassign_and_remove_factory_shortcuts():
    profile = load_profile("faderfox-ec4.json")

    result = effective_shortcuts(
        profile,
        {
            profile.id: {
                "shift+encoder_01": "next_snapshot",
                "encoder_16": "",
            }
        },
    )

    assert result["shift+encoder_01"] == "next_snapshot"
    assert "encoder_16" not in result


def test_non_ec4_bindings_are_derived_from_real_profile_buttons():
    profile = load_profile("novation-launch-control-xl2-user-template.json")
    bindings = configurable_shortcut_bindings(profile)

    assert bindings
    assert all("encoder_" not in binding for binding in bindings)
    assert effective_shortcuts(profile, {}) == {}

