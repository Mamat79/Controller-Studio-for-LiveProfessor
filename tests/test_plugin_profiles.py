import copy
from pathlib import Path

import pytest

from silemio_control_hub.plugin_profiles import (
    ObservedParameter,
    PluginObservation,
    PluginProfile,
    PluginProfileError,
    PluginProfileLayer,
    PluginProfileResolver,
    compact_label,
)


def _observation(*, stable_id="VST3-Test-b86068d4-ca0ebedb", version=None):
    return PluginObservation(
        plugin_format="VST3",
        stable_id=stable_id,
        name="Test Compressor",
        manufacturer="Test Audio",
        version=version,
        parameters=(
            ObservedParameter(0, "input", "Input Gain"),
            ObservedParameter(1, "bypass", "Bypass"),
            ObservedParameter(2, "output", "Output Gain"),
        ),
    )


def _profile(
    observation,
    *,
    profile_id="test.compressor.suggested",
    profile_version="1.0.0",
    layer="suggested",
    status=None,
    parameters=None,
):
    return {
        "schema_version": 1,
        "profile_version": profile_version,
        "id": profile_id,
        "status": status or ("local" if layer == "user" else "community"),
        "layer": layer,
        "plugin_name": observation.name,
        "manufacturer": observation.manufacturer,
        "identity": {
            "format": observation.plugin_format,
            "stable_id": observation.stable_id,
            "parameter_fingerprint": observation.parameter_fingerprint,
            **({"version": observation.version} if observation.version else {}),
        },
        "parameters": parameters
        or [
            {
                "stable_id": "input",
                "name": "Input",
                "short_label": "IN",
                "unit": "dB",
                "role": "input_gain",
                "importance": 90,
            }
        ],
    }


def test_parameter_fingerprint_uses_structure_not_display_names():
    first = _observation()
    renamed = PluginObservation(
        plugin_format=first.plugin_format,
        stable_id=first.stable_id,
        name=first.name,
        manufacturer=first.manufacturer,
        parameters=tuple(
            ObservedParameter(parameter.position, parameter.stable_id, f"Nom {parameter.position}")
            for parameter in first.parameters
        ),
    )

    assert first.parameter_fingerprint == renamed.parameter_fingerprint


def test_suggested_profile_overlays_raw_without_losing_unprofiled_parameters():
    observation = _observation()
    suggested = PluginProfile.from_dict(_profile(observation))

    result = PluginProfileResolver([suggested]).resolve(observation)

    assert result.layer == PluginProfileLayer.SUGGESTED
    assert result.applied_profile_ids == (suggested.id,)
    assert [parameter.stable_id for parameter in result.parameters] == [
        "input",
        "bypass",
        "output",
    ]
    assert result.parameters[0].name == "Input"
    assert result.parameters[0].importance == 90
    assert result.parameters[0].source_layer == PluginProfileLayer.SUGGESTED
    assert result.parameters[1].name == "Bypass"
    assert result.parameters[1].source_layer == PluginProfileLayer.RAW


def test_user_profile_has_priority_over_suggested_profile_parameter_by_parameter():
    observation = _observation()
    suggested = PluginProfile.from_dict(_profile(observation))
    user = PluginProfile.from_dict(
        _profile(
            observation,
            profile_id="local.test-compressor",
            layer="user",
            parameters=[
                {
                    "stable_id": "input",
                    "name": "Mon entrée",
                    "short_label": "ENTRÉE",
                    "importance": 100,
                }
            ],
        )
    )

    result = PluginProfileResolver([suggested, user]).resolve(observation)

    assert result.layer == PluginProfileLayer.USER
    assert result.applied_profile_ids == (suggested.id, user.id)
    assert result.parameters[0].name == "Mon entrée"
    assert result.parameters[0].source_layer == PluginProfileLayer.USER


def test_newest_compatible_profile_is_selected_within_one_layer():
    observation = _observation()
    old = PluginProfile.from_dict(_profile(observation, profile_version="1.0.0"))
    new_raw = _profile(observation, profile_version="1.2.0")
    new_raw["parameters"][0]["name"] = "Newest Input"
    new = PluginProfile.from_dict(new_raw)

    result = PluginProfileResolver([old, new]).resolve(observation)

    assert result.applied_profile_ids == (new.id,)
    assert result.parameters[0].name == "Newest Input"


def test_identity_mismatch_falls_back_to_raw_instead_of_guessing():
    observation = _observation()
    other = _observation(stable_id="VST3-Another-00000001")
    suggested = PluginProfile.from_dict(_profile(other))

    result = PluginProfileResolver([suggested]).resolve(observation)

    assert result.layer == PluginProfileLayer.RAW
    assert result.applied_profile_ids == ()
    assert all(
        parameter.source_layer == PluginProfileLayer.RAW
        for parameter in result.parameters
    )


def test_versioned_identity_requires_the_observed_version_to_match():
    versioned = _observation(version="2.0.0")
    profile = PluginProfile.from_dict(_profile(versioned))

    assert PluginProfileResolver([profile]).resolve(versioned).layer == PluginProfileLayer.SUGGESTED
    assert (
        PluginProfileResolver([profile]).resolve(_observation(version="2.1.0")).layer
        == PluginProfileLayer.RAW
    )


def test_profile_validation_rejects_unknown_fields_duplicates_and_raw_files():
    observation = _observation()
    unknown = _profile(observation)
    unknown["executable"] = "payload.py"
    with pytest.raises(PluginProfileError, match="champs inconnus: executable"):
        PluginProfile.from_dict(unknown)

    duplicate = _profile(observation)
    duplicate["parameters"].append(copy.deepcopy(duplicate["parameters"][0]))
    with pytest.raises(PluginProfileError, match="stable_id dupliqués"):
        PluginProfile.from_dict(duplicate)

    raw = _profile(observation)
    raw["layer"] = "raw"
    with pytest.raises(PluginProfileError, match="couche raw"):
        PluginProfile.from_dict(raw)


def test_resolver_rejects_a_selected_profile_with_an_unknown_parameter():
    observation = _observation()
    malformed = _profile(
        observation,
        parameters=[{"stable_id": "ghost", "name": "Ghost"}],
    )
    profile = PluginProfile.from_dict(malformed)

    with pytest.raises(PluginProfileError, match="paramètres absents: ghost"):
        PluginProfileResolver([profile]).resolve(observation)


def test_compact_label_is_generic_and_has_a_deterministic_fallback():
    assert compact_label("Fréquence (Hz)", maximum=8) == "Fréquenc"
    assert compact_label("---", fallback_index=4, maximum=4) == "P005"


def test_repository_example_profile_matches_schema_loader():
    example = Path(__file__).parents[1] / "profiles-exemple-plugin.json"

    profile = PluginProfile.load_file(example)

    assert profile.id == "example.plugin"
    assert profile.layer == PluginProfileLayer.SUGGESTED
