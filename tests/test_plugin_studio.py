import hashlib

import pytest

from silemio_control_hub.adapters.hosts.liveprofessor_automap import (
    ProjectPlugin,
    _plugin_assignments,
)
from silemio_control_hub.formats.juce_value_tree import ValueTree
from silemio_control_hub.plugin_profiles import (
    PluginObservation,
    PluginParameterKind,
    PluginParameterProfile,
    PluginProfile,
    PluginProfileError,
    PluginProfileLayer,
    PluginProfileResolver,
)
from silemio_control_hub.plugin_registry import PluginProfileRegistry
from silemio_control_hub.plugin_studio import (
    analyze_plugin_project,
    build_user_profile,
    capture_liveprofessor_parameter_names,
    default_user_profile_id,
    editable_parameters,
    next_user_profile_version,
    request_liveprofessor_companion_names,
    save_user_profile,
)


def _observation(*, stable_id="VST3-Test-1234", parameter_count=3):
    return PluginObservation.from_parameter_count(
        plugin_format="VST3",
        stable_id=stable_id,
        name="Très Bon Compresseur",
        parameter_count=parameter_count,
    )


def _parameters(observation, *, first_name="Input"):
    return tuple(
        PluginParameterProfile(
            stable_id=parameter.stable_id,
            name=first_name if parameter.position == 0 else f"Parameter {parameter.position + 1}",
            short_label="IN" if parameter.position == 0 else f"P{parameter.position + 1}",
            role="input_gain" if parameter.position == 0 else None,
            kind=(
                PluginParameterKind.CONTINUOUS
                if parameter.position == 0
                else PluginParameterKind.TOGGLE
            ),
            importance=90 if parameter.position == 0 else 50,
            enabled=parameter.position != 2,
        )
        for parameter in observation.parameters
    )


def test_user_profile_builder_round_trips_every_declarative_field():
    observation = _observation()
    profile = build_user_profile(observation, _parameters(observation))

    reloaded = PluginProfile.from_dict(profile.to_dict())

    assert reloaded == profile
    assert profile.layer == PluginProfileLayer.USER
    assert profile.status == "local"
    assert profile.parameters[0].role == "input_gain"
    assert profile.parameters[1].kind == PluginParameterKind.TOGGLE
    assert profile.parameters[2].enabled is False


def test_default_local_profile_id_is_safe_stable_and_identity_specific():
    first = _observation()
    same = _observation()
    other = _observation(stable_id="VST3-Other-1234")

    assert default_user_profile_id(first) == default_user_profile_id(same)
    assert default_user_profile_id(first).startswith("local.tres-bon-compresseur.")
    assert default_user_profile_id(first) != default_user_profile_id(other)


def test_atomic_user_profile_save_requires_replace_and_keeps_backup_out_of_registry(
    tmp_path,
):
    observation = _observation()
    first = build_user_profile(observation, _parameters(observation))
    saved = save_user_profile(first, directory=tmp_path)

    with pytest.raises(PluginProfileError, match="autorisez explicitement"):
        save_user_profile(first, directory=tmp_path)

    second = build_user_profile(
        observation,
        _parameters(observation, first_name="My Input"),
        profile_id=first.id,
        profile_version="1.0.1",
    )
    replaced = save_user_profile(second, directory=tmp_path, replace=True)
    registry = PluginProfileRegistry(
        profile_directories=[tmp_path],
        library_cache_root=tmp_path / "cache",
    )

    assert saved.path == replaced.path
    assert replaced.backup_path is not None
    assert replaced.backup_path.parent == tmp_path / "backups"
    assert PluginProfile.load_file(replaced.backup_path) == first
    assert registry.all() == (second,)
    assert PluginProfileResolver(registry.all()).resolve(observation).parameters[0].name == "My Input"


def test_profile_editor_starts_from_the_effective_suggested_values():
    observation = _observation(parameter_count=1)
    suggested_raw = build_user_profile(observation, _parameters(observation)).to_dict()
    suggested_raw["id"] = "community.test-compressor"
    suggested_raw["status"] = "community"
    suggested_raw["layer"] = "suggested"
    suggested = PluginProfile.from_dict(suggested_raw)

    resolved = PluginProfileResolver([suggested]).resolve(observation)
    editable = editable_parameters(resolved)

    assert editable[0].name == "Input"
    assert editable[0].importance == 90
    assert editable[0].kind == PluginParameterKind.CONTINUOUS


def test_profile_version_increments_only_for_the_same_exact_identity():
    observation = _observation()
    current = build_user_profile(
        observation,
        _parameters(observation),
        profile_version="2.4.9",
    )

    assert next_user_profile_version([current], observation) == "2.4.10"
    assert next_user_profile_version([current], _observation(stable_id="VST3-Other")) == "1.0.0"


def test_project_analysis_groups_instances_resolves_profiles_and_preserves_source(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.rack2"
    source.write_bytes(b"read-only-project-evidence")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    instances = (
        ProjectPlugin("Compressor", "VST3-Test-1234", 101, 3, "VST3-Test"),
        ProjectPlugin("Compressor", "VST3-Test-1234", 102, 3, "VST3-Test"),
        ProjectPlugin("Limiter", "VST3-Limiter-5678", 201, 2, "VST3-Limiter"),
    )
    monkeypatch.setattr(
        "silemio_control_hub.plugin_studio.inspect_plugins",
        lambda _path: instances,
    )
    observation = instances[0].observation
    user = build_user_profile(observation, _parameters(observation))

    analysis = analyze_plugin_project(source, [user])

    assert analysis.instance_count == 3
    assert len(analysis.plugin_types) == 2
    assert analysis.plugin_types[0].instance_uids == (101, 102)
    assert analysis.plugin_types[0].resolved.layer == PluginProfileLayer.USER
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_semantic_order_fills_only_free_controls_after_manual_and_preserved_mappings():
    plugin = ProjectPlugin("Compressor", "VST3-Test-1234", 101, 4, "VST3-Test")
    rotaries = []
    for number, control_id in enumerate((10, 11, 12, 13), start=1):
        control = ValueTree("HardwareControl", [], [])
        control.set("id", control_id)
        rotaries.append((number, control))

    assignments, mapped = _plugin_assignments(
        controller_uid=99,
        plugin=plugin,
        rotaries=rotaries,
        buttons=[],
        profile={10: 2},
        preserve_parameters=(1,),
        preferred_parameter_order=(3, 2, 1, 0),
    )

    by_control = {
        assignment.get("ControllerId"): assignment.get("ParameterId")
        for assignment in assignments
    }
    assert mapped == 4
    assert by_control == {10: 2, 11: 1, 12: 3, 13: 0}


def test_automap_allowed_parameters_excludes_unchecked_automatic_slots():
    plugin = ProjectPlugin("Compressor", "VST3-Test-1234", 101, 5, "VST3-Test")
    rotaries = []
    for number, control_id in enumerate((10, 11, 12, 13), start=1):
        control = ValueTree("HardwareControl", [], [])
        control.set("id", control_id)
        rotaries.append((number, control))

    assignments, mapped = _plugin_assignments(
        controller_uid=99,
        plugin=plugin,
        rotaries=rotaries,
        buttons=[],
        profile={},
        preferred_parameter_order=(4, 2, 0),
        allowed_parameters=(0, 2, 4),
    )

    assert mapped == 3
    assert [assignment.get("ParameterId") for assignment in assignments] == [4, 2, 0]


def test_liveprofessor_names_follow_saved_slot_mapping_not_parameter_order(
    tmp_path, monkeypatch
):
    observation = _observation()
    parameters = _parameters(observation)
    monkeypatch.setattr(
        "silemio_control_hub.plugin_studio.inspect_plugin_parameter_slots",
        lambda _path, plugin_uid: {0: 2, 1: 0},
    )

    updated, count = capture_liveprofessor_parameter_names(
        parameters,
        project=tmp_path / "project.rack2",
        plugin_uid=123,
        live_names=("Output Gain", "Input Gain"),
    )

    assert count == 2
    assert updated[0].name == "Input Gain"
    assert updated[0].short_label == "InputGai"
    assert updated[2].name == "Output Gain"
    assert updated[2].enabled is False


def test_companion_name_request_works_without_hardware_runtime(monkeypatch):
    state = {}

    class FakeServer:
        def __init__(self, host, port, callback, error_callback):
            state["callback"] = callback

        def start(self):
            state["started"] = True

        def stop(self):
            state["stopped"] = True

    class FakeClient:
        def __init__(self, host, port):
            state["target"] = (host, port)

        def send(self, address, *args):
            state.setdefault("requests", []).append(address)
            if address == "/refresh":
                state["callback"](
                    "/Companion/ControllerNames", ["Rotary3", "Output Gain"]
                )
                state["callback"](
                    "/Companion/ControllerNames", ["Rotary1", "Input Gain"]
                )
                state["callback"](
                    "/Companion/ControllerNames", ["Generic Button 1", "Bypass"]
                )

        def close(self):
            state["closed"] = True

    monkeypatch.setattr("silemio_control_hub.plugin_studio.OSCServer", FakeServer)
    monkeypatch.setattr("silemio_control_hub.plugin_studio.OSCClient", FakeClient)

    names = request_liveprofessor_companion_names(
        host="127.0.0.1",
        request_port=8010,
        feedback_host="127.0.0.1",
        feedback_port=8011,
        quiet_period=0,
    )

    assert names == ("Input Gain", "", "Output Gain")
    assert state["requests"] == ["/init", "/refresh", "/ViewSets/Refresh"]
    assert state["started"] and state["stopped"] and state["closed"]
