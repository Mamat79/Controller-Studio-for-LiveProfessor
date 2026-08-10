import hashlib
import json

import pytest

from silemio_control_hub.adapters.hosts.liveprofessor_automap import (
    AutoMapError,
    create_automapped_project,
    inspect_project,
)
from silemio_control_hub.adapters.hosts.liveprofessor_controller import (
    default_companion_template,
)
from silemio_control_hub.cli import main
from silemio_control_hub.formats.juce_value_tree import (
    ValueTree,
    normalize_rotary_controls,
    parse_tree,
    write_tree,
)
from silemio_control_hub.models import ControllerProfile
from silemio_control_hub.plugin_profiles import PluginParameterProfile
from silemio_control_hub.plugin_studio import build_user_profile
from silemio_control_hub.registry import ControllerRegistry
from silemio_control_hub.workflow import (
    LiveProfessorPreparationError,
    prepare_liveprofessor_project,
)


def _node(type_name: str, **properties: object) -> ValueTree:
    result = ValueTree(type_name, [], [])
    for key, value in properties.items():
        result.set(key, value)
    return result


def _walk(tree: ValueTree):
    yield tree
    for child in tree.children:
        yield from _walk(child)


def _controllerless_project(parameter_count: int = 12) -> ValueTree:
    project = _node(
        "LiveProfessorProjectFile",
        isTemplate=False,
        ProjectFileVersion=1,
        appVersion="2026.1.0",
    )
    chains = _node("Chains")
    chain = _node("Chain", ChainViewOrder=0)
    chain_plugins = _node("ChainPlugins")
    plugin = _node(
        "Plugin",
        pluginTypeId="VST3-Test Plugin-b86068d4-ca0ebedb",
        pluginTypeName="Test Plugin",
        pluginUid=7_956_475,
    )
    plugin_wrapper = _node("Plugin", useMinimalView=False)
    snapshot = _node(
        "PluginSnapshot",
        name="",
        uId=12_753_713,
        pluginTypeId="VST3-Test Plugin-b86068d4-ca0ebedb",
    )
    parameters = _node("parameters")
    for index in range(parameter_count):
        parameters.set(f"P{index}", 0.5)
    snapshot.children = [parameters]
    plugin_wrapper.children = [snapshot]
    plugin.children = [plugin_wrapper]
    chain_plugins.children = [plugin]
    chain.children = [chain_plugins]
    chains.children = [chain]

    hardware_root = _node("HardwareControllers", ActiveMap=0)
    hardware_root.children = [_node("HardwareControllers"), _node("HardwareCtrlMaps")]
    project.children = [chains, hardware_root]
    return project


def _project_with_existing_ec4(parameter_count: int = 12) -> ValueTree:
    project = _controllerless_project(parameter_count)
    controller = parse_tree(default_companion_template().read_bytes())
    controller.type_name = "HardwareController"
    controller.set("ControllerName", "EC4")
    controller.set("uID", 19_639_590)
    normalize_rotary_controls(controller, 16)
    hardware_root = next(
        child for child in project.children if child.type_name == "HardwareControllers"
    )
    controllers = next(
        child for child in hardware_root.children if child.type_name == "HardwareControllers"
    )
    controllers.children.append(controller)
    return project


def _project_with_three_plugin_instances(parameter_count: int = 12) -> ValueTree:
    project = _project_with_existing_ec4(parameter_count)
    chains = next(child for child in project.children if child.type_name == "Chains")
    original = chains.children[0]
    for uid in (7_956_476, 7_956_477):
        duplicate = parse_tree(write_tree(original))
        plugin_root = next(
            child for child in duplicate.children if child.type_name == "ChainPlugins"
        )
        plugin_root.children[0].set("pluginUid", uid)
        chains.children.append(duplicate)
    return project


def _eight_rotary_profile() -> ControllerProfile:
    return ControllerProfile.from_dict(
        {
            "schema_version": 1,
            "profile_version": "1.0.0",
            "id": "test.eight-rotaries",
            "manufacturer": "Test",
            "model": "Eight Rotaries",
            "bank_size": 8,
            "status": "community",
            "capabilities": ["commands"],
            "controls": [
                {
                    "id": f"rotary_{number:02d}",
                    "kind": "absolute_encoder",
                    "input": {"message": "cc", "channel": 1, "number": number - 1},
                }
                for number in range(1, 9)
            ],
        }
    )


def test_prepare_workflow_creates_ctrl2_and_automapped_copy_without_touching_source(
    tmp_path,
):
    source = tmp_path / "source.rack2"
    destination = tmp_path / "source-automap.rack2"
    controller = tmp_path / "Generic-MIDI-16.ctrl2"
    source.write_bytes(write_tree(_controllerless_project()))
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest().upper()

    result = prepare_liveprofessor_project(
        ControllerRegistry().get("generic.midi.16"),
        source,
        destination,
        controller,
    )

    assert result.source_sha256 == source_hash
    assert hashlib.sha256(source.read_bytes()).hexdigest().upper() == source_hash
    assert controller.is_file()
    assert destination.is_file()
    assert result.automap.mapped_rotaries == 12
    assert result.automap.available_parameters == 12
    assert result.automap.controller_rotaries == 16
    inventory = inspect_project(destination)
    assert len(inventory.plugins) == 1
    assert len(inventory.controllers) == 1
    assert inventory.controllers[0].name == "SiLeMI/O - Generic MIDI 16 controls"
    generated_tree = parse_tree(destination.read_bytes())
    generated_names = {str(node.get("Name", "")) for node in _walk(generated_tree)}
    assert any(name.startswith("SiLeMI/O AutoMap -") for name in generated_names)
    assert all(not name.startswith("EC4 AutoMap -") for name in generated_names)


def test_prepare_workflow_can_explicitly_embed_a_new_controller(tmp_path):
    source = tmp_path / "source.rack2"
    destination = tmp_path / "source-new-controller.rack2"
    controller = tmp_path / "Faderfox-EC4.ctrl2"
    source.write_bytes(write_tree(_controllerless_project()))
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest().upper()

    result = prepare_liveprofessor_project(
        ControllerRegistry().get("faderfox.ec4"),
        source,
        destination,
        controller,
        embed_new_controller=True,
        target_rotary_count=16,
    )

    assert hashlib.sha256(source.read_bytes()).hexdigest().upper() == source_hash
    inventory = inspect_project(destination)
    assert len(inventory.controllers) == 1
    assert inventory.controllers[0].controller_uid == result.controller.controller_uid
    assert inventory.controllers[0].rotary_count == 16


def test_prepare_workflow_supports_profiles_smaller_than_sixteen_rotaries(tmp_path):
    source = tmp_path / "source.rack2"
    destination = tmp_path / "mapped.rack2"
    controller = tmp_path / "Eight.ctrl2"
    source.write_bytes(write_tree(_controllerless_project(parameter_count=12)))

    result = prepare_liveprofessor_project(
        _eight_rotary_profile(),
        source,
        destination,
        controller,
    )

    assert result.controller.rotary_count == 8
    assert result.automap.controller_rotaries == 8
    assert result.automap.mapped_rotaries == 8


def test_prepare_workflow_reuses_the_only_existing_controller_to_keep_labels_aligned(
    tmp_path,
):
    source = tmp_path / "source-with-ec4.rack2"
    destination = tmp_path / "mapped.rack2"
    controller = tmp_path / "Controller-Studio-EC4.ctrl2"
    source.write_bytes(write_tree(_project_with_existing_ec4()))
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest().upper()

    result = prepare_liveprofessor_project(
        ControllerRegistry().get("faderfox.ec4"),
        source,
        destination,
        controller,
        target_rotary_count=16,
    )

    assert hashlib.sha256(source.read_bytes()).hexdigest().upper() == source_hash
    inventory = inspect_project(destination)
    assert [(item.controller_uid, item.name) for item in inventory.controllers] == [
        (19_639_590, "EC4")
    ]
    assert result.automap.controller_name == "EC4"
    assert result.controller.controller_uid == 19_639_590
    exported_controller = parse_tree(controller.read_bytes())
    assert exported_controller.get("uID") == 19_639_590
    assert exported_controller.get("ControllerName") == "EC4"
    generated = parse_tree(destination.read_bytes())
    hardware_root = next(
        child for child in generated.children if child.type_name == "HardwareControllers"
    )
    maps = next(
        child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
    )
    active_map = next(
        child for child in maps.children if child.get("mapId") == hardware_root.get("ActiveMap")
    )
    assignments = next(
        child for child in active_map.children if child.type_name == "Assignments"
    )
    assert {item.get("ParentControllerId") for item in assignments.children} == {
        19_639_590
    }


def test_fullbank_extends_the_existing_controller_without_adding_a_second_one(
    tmp_path,
):
    source = tmp_path / "source-with-ec4.rack2"
    destination = tmp_path / "mapped-fullbank.rack2"
    controller = tmp_path / "Controller-Studio-EC4-FullBank.ctrl2"
    source.write_bytes(write_tree(_project_with_existing_ec4()))

    result = prepare_liveprofessor_project(
        ControllerRegistry().get("faderfox.ec4"),
        source,
        destination,
        controller,
        target_rotary_count=99,
    )

    inventory = inspect_project(destination)
    assert [item.controller_uid for item in inventory.controllers] == [19_639_590]
    assert inventory.controllers[0].rotary_count == 99
    assert result.automap.controller_rotaries == 99
    exported = parse_tree(controller.read_bytes())
    assert exported.get("uID") == 19_639_590
    controls = next(child for child in exported.children if child.type_name == "Controls")
    assert sum(
        str(child.get("OSCAddressPatern", "")).startswith("/Companion/Rotary")
        for child in controls.children
    ) == 99


def test_automap_accepts_an_explicit_multi_plugin_checkbox_selection(tmp_path):
    source = tmp_path / "three-plugins.rack2"
    destination = tmp_path / "selected-plugins.rack2"
    source.write_bytes(write_tree(_project_with_three_plugin_instances()))

    result = create_automapped_project(
        source,
        destination,
        plugin_uids=(7_956_475, 7_956_477),
        controller_uid=19_639_590,
        target_rotary_count=16,
    )

    generated = parse_tree(destination.read_bytes())
    hardware_root = next(
        child for child in generated.children if child.type_name == "HardwareControllers"
    )
    maps = next(
        child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
    )
    active_map = next(
        child for child in maps.children if child.get("mapId") == hardware_root.get("ActiveMap")
    )
    assignments = next(
        child for child in active_map.children if child.type_name == "Assignments"
    )
    processors = {
        item.get("ControllableId")
        for item in assignments.children
        if str(item.get("ControllableId", "")).startswith("Processor")
    }
    assert processors == {"Processor7956475", "Processor7956477"}
    assert result.mapped_rotaries == 24


def test_automap_uses_exact_local_profile_priority_for_free_rotaries(tmp_path):
    source = tmp_path / "profiled.rack2"
    destination = tmp_path / "profiled-automap.rack2"
    source.write_bytes(write_tree(_project_with_existing_ec4(parameter_count=4)))
    observation = inspect_project(source).plugins[0].observation
    parameters = tuple(
        PluginParameterProfile(
            stable_id=parameter.stable_id,
            name=f"Parameter {parameter.position + 1}",
            short_label=f"P{parameter.position + 1}",
            importance=100 if parameter.position == 3 else 50,
        )
        for parameter in observation.parameters
    )
    local_profile = build_user_profile(observation, parameters)

    create_automapped_project(
        source,
        destination,
        controller_uid=19_639_590,
        target_rotary_count=16,
        plugin_profiles=[local_profile],
    )

    generated = parse_tree(destination.read_bytes())
    hardware_root = next(
        child for child in generated.children if child.type_name == "HardwareControllers"
    )
    controller_root = next(
        child for child in hardware_root.children if child.type_name == "HardwareControllers"
    )
    controller = controller_root.children[0]
    controls = next(child for child in controller.children if child.type_name == "Controls")
    rotary_ids = {
        int(str(control.get("OSCAddressPatern")).removeprefix("/Companion/Rotary")):
        control.get("id")
        for control in controls.children
        if str(control.get("OSCAddressPatern", "")).startswith("/Companion/Rotary")
    }
    maps = next(
        child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
    )
    active_map = next(
        child for child in maps.children if child.get("mapId") == hardware_root.get("ActiveMap")
    )
    assignments = next(
        child for child in active_map.children if child.type_name == "Assignments"
    )
    parameters_by_control = {
        assignment.get("ControllerId"): assignment.get("ParameterId")
        for assignment in assignments.children
        if assignment.get("ControllableId") == "Processor7956475"
    }

    assert [parameters_by_control[rotary_ids[number]] for number in range(1, 5)] == [
        3,
        0,
        1,
        2,
    ]


def test_automap_refuses_an_empty_checkbox_selection(tmp_path):
    source = tmp_path / "three-plugins.rack2"
    source.write_bytes(write_tree(_project_with_three_plugin_instances()))

    with pytest.raises(AutoMapError, match="au moins un plugin"):
        create_automapped_project(
            source,
            tmp_path / "empty.rack2",
            plugin_uids=(),
            controller_uid=19_639_590,
            target_rotary_count=16,
        )


def test_prepare_workflow_refuses_existing_destination_before_writing_ctrl2(tmp_path):
    source = tmp_path / "source.rack2"
    destination = tmp_path / "mapped.rack2"
    controller = tmp_path / "Controller.ctrl2"
    source.write_bytes(write_tree(_controllerless_project()))
    destination.write_bytes(b"personal destination")

    with pytest.raises(LiveProfessorPreparationError, match="existe déjà"):
        prepare_liveprofessor_project(
            ControllerRegistry().get("generic.midi.16"),
            source,
            destination,
            controller,
        )

    assert destination.read_bytes() == b"personal destination"
    assert not controller.exists()


def test_value_tree_rotary_normalizer_handles_one_to_ninety_nine():
    tree = parse_tree(default_companion_template().read_bytes())
    reduced = normalize_rotary_controls(tree, 8)
    expanded = normalize_rotary_controls(tree, 12)
    controls = next(child for child in tree.children if child.type_name == "Controls")
    rotaries = [
        child
        for child in controls.children
        if str(child.get("OSCAddressPatern", "")).startswith("/Companion/Rotary")
    ]
    assert reduced["rotaries_removed"] == 91
    assert expanded["rotaries_added"] == 4
    assert len(rotaries) == 12


def test_prepare_liveprofessor_cli_reports_both_deliverables(tmp_path, capsys):
    source = tmp_path / "source.rack2"
    destination = tmp_path / "mapped.rack2"
    controller = tmp_path / "Controller.ctrl2"
    source.write_bytes(write_tree(_controllerless_project(parameter_count=4)))

    exit_code = main(
        [
            "prepare-liveprofessor",
            "generic.midi.16",
            str(source),
            str(destination),
            str(controller),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert f"CONTRÔLEUR: {controller}" in output
    assert f"AUTOMAP: {destination}" in output
    assert "4/4 paramètre(s)" in output


def test_plugin_inspection_cli_emits_stable_identity_without_a_controller(tmp_path, capsys):
    source = tmp_path / "controllerless.rack2"
    source.write_bytes(write_tree(_controllerless_project(parameter_count=4)))

    exit_code = main(["inspect-liveprofessor-plugins", str(source)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == [
        {
            "format": "VST3",
            "name": "Test Plugin",
            "parameter_count": 4,
            "parameter_fingerprint": payload[0]["parameter_fingerprint"],
            "stable_id": "VST3-Test Plugin-b86068d4-ca0ebedb",
            "uid": 7_956_475,
        }
    ]
    assert len(payload[0]["parameter_fingerprint"]) == 64
