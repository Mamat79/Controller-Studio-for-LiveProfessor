import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ec4lpbridge.automap import (
    AutoMapError,
    create_automapped_project,
    inspect_project,
    plugin_map_type_id,
)
from scripts.repair_ctrl2 import ValueTree, normalize_rotary_controls, parse_tree, write_tree


def node(type_name: str, **properties: object) -> ValueTree:
    result = ValueTree(type_name, [], [])
    for key, value in properties.items():
        result.set(key, value)
    return result


def controller_project(parameter_count: int = 30) -> ValueTree:
    project = node(
        "LiveProfessorProjectFile",
        isTemplate=False,
        ProjectFileVersion=1,
        appVersion="2026.1.0",
    )
    chains = node("Chains")
    chain = node("Chain", ChainViewOrder=0)
    chain_plugins = node("ChainPlugins")
    plugin = node(
        "Plugin",
        pluginTypeId="VST3-Avalon VT-747SP-b86068d4-ca0ebedb",
        pluginTypeName="Avalon VT-747SP",
        pluginUid=7956475,
    )
    plugin_wrapper = node("Plugin", useMinimalView=False)
    snapshot = node(
        "PluginSnapshot",
        name="",
        uId=12753713,
        pluginTypeId="VST3-Avalon VT-747SP-b86068d4-ca0ebedb",
    )
    parameters = node("parameters")
    for index in range(parameter_count):
        parameters.set(f"P{index}", 0.5)
    snapshot.children = [parameters]
    plugin_wrapper.children = [snapshot]
    plugin.children = [plugin_wrapper]
    chain_plugins.children = [plugin]
    chain.children = [chain_plugins]
    chains.children = [chain]

    hardware_root = node("HardwareControllers", ActiveMap=0)
    controllers = node("HardwareControllers")
    controller = node(
        "HardwareController",
        ControllerName="EC4",
        ControllerType="Companion",
        uID=12687768,
        OSCInPort=8010,
        OSCOutPort=8011,
        OSChostIp="127.0.0.1",
        PingAddress="",
    )
    controls = node("Controls")
    for number in range(1, 17):
        button = node(
            "HardwareControl",
            Name=f"Generic Button {number}",
            id=22_000_000 + number,
            ControlStyle=2,
            tag=f"GenericButton{number}",
            noFeedbackOnInput=False,
            OSCAddressPatern=f"/Companion/GenericButtons/Button{number}",
        )
        button.children = [node("ControlTransform", Toggle=True)]
        controls.children.append(button)
    for number in range(1, 17):
        rotary = node(
            "HardwareControl",
            Name=f"Rotary {number}",
            id=23_000_000 + number,
            ControlStyle=0,
            tag=f"Rotary{number}",
            noFeedbackOnInput=False,
            OSCAddressPatern=f"/Companion/Rotary{number}",
        )
        rotary.children = [node("ControlTransform", Toggle=False)]
        controls.children.append(rotary)
    controller.children = [controls, node("MapPresets", children=0), node("Pinger")]
    controller.children[1].children = [node("Presets")]
    controllers.children = [controller]
    hardware_root.children = [controllers, node("HardwareCtrlMaps")]
    project.children = [chains, hardware_root]
    return project


class AutoMapTests(unittest.TestCase):
    def test_plugin_uid_conversion_matches_liveprofessor_serialization(self):
        self.assertEqual(
            plugin_map_type_id("VST3-Avalon VT-747SP-b86068d4-ca0ebedb"),
            "plugin-UID-905003301",
        )
        with self.assertRaises(AutoMapError):
            plugin_map_type_id("unsupported")

    def test_project_inventory_finds_plugin_and_companion_controller(self):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "test.rack2"
            source.write_bytes(write_tree(controller_project()))

            inventory = inspect_project(source)

            self.assertEqual(len(inventory.plugins), 1)
            self.assertEqual(inventory.plugins[0].parameter_count, 30)
            self.assertEqual(inventory.plugins[0].map_type_id, "plugin-UID-905003301")
            self.assertEqual(len(inventory.controllers), 1)
            self.assertEqual(inventory.controllers[0].rotary_count, 16)
            self.assertEqual(inventory.controllers[0].button_count, 16)

    def test_automap_creates_valid_fullbank_copy_and_preserves_source(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "test.rack2"
            destination = root / "test-EC4-AutoMap.rack2"
            source.write_bytes(write_tree(controller_project()))
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            result = create_automapped_project(
                source,
                destination,
                plugin_uid=7956475,
                controller_uid=12687768,
                expand_to_fullbank=True,
            )

            self.assertEqual(result.mapped_rotaries, 30)
            self.assertEqual(result.controller_rotaries, 99)
            self.assertEqual(result.mapped_plugins, ("Avalon VT-747SP",))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
            generated = parse_tree(destination.read_bytes())
            self.assertEqual(write_tree(generated), destination.read_bytes())
            hardware_root = next(
                child for child in generated.children if child.type_name == "HardwareControllers"
            )
            controller_root = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            controller = controller_root.children[0]
            controls = next(child for child in controller.children if child.type_name == "Controls")
            rotaries = [
                child
                for child in controls.children
                if child.type_name == "HardwareControl" and child.get("ControlStyle") == 0
            ]
            self.assertEqual(len(rotaries), 99)
            presets = next(child for child in controller.children if child.type_name == "MapPresets")
            preset = presets.children[0].children[0]
            self.assertEqual(preset.get("TypeId"), "plugin-UID-905003301")
            map_node = preset.children[0]
            self.assertTrue(map_node.get("SelectMode"))
            self.assertEqual(len(map_node.children), 2)
            self.assertEqual(len(map_node.children[0].children), 30)
            self.assertEqual(map_node.children[0].children[-1].get("ParameterId"), 29)

    def test_source_cannot_be_overwritten(self):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "test.rack2"
            source.write_bytes(write_tree(controller_project()))
            with self.assertRaises(AutoMapError):
                create_automapped_project(
                    source,
                    source,
                    plugin_uid=7956475,
                    controller_uid=12687768,
                )

    def test_unibank_mode_reduces_a_fullbank_controller_to_sixteen(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "full.rack2"
            destination = root / "uni.rack2"
            project = controller_project(parameter_count=30)
            hardware_root = next(
                child for child in project.children if child.type_name == "HardwareControllers"
            )
            controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            normalize_rotary_controls(controllers.children[0], 99)
            source.write_bytes(write_tree(project))

            result = create_automapped_project(
                source,
                destination,
                plugin_uid=7956475,
                controller_uid=12687768,
                expand_to_fullbank=False,
            )

            self.assertEqual(result.controller_rotaries, 16)
            self.assertEqual(result.mapped_rotaries, 16)
            generated = parse_tree(destination.read_bytes())
            hardware_root = next(
                child for child in generated.children if child.type_name == "HardwareControllers"
            )
            controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            controls = next(
                child for child in controllers.children[0].children if child.type_name == "Controls"
            )
            self.assertEqual(
                sum(
                    child.type_name == "HardwareControl" and child.get("ControlStyle") == 0
                    for child in controls.children
                ),
                16,
            )

    def test_existing_manual_map_is_preserved(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "test.rack2"
            destination = root / "mapped.rack2"
            project = controller_project()
            hardware_root = next(
                child for child in project.children if child.type_name == "HardwareControllers"
            )
            controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            presets_root = next(
                child for child in controllers.children[0].children if child.type_name == "MapPresets"
            )
            presets = next(child for child in presets_root.children if child.type_name == "Presets")
            manual_preset = node(
                "MapPreset",
                Name="Mon mapping manuel",
                TypeId="plugin-UID-905003301",
                ControllerId=12687768,
            )
            manual_map = node(
                "ControllerMapPreset",
                Name="Mon mapping manuel",
                TypeId="plugin-UID-905003301",
                ControllerId=12687768,
                SelectMode=True,
                mapId=1234567,
            )
            manual_map.children = [node("Assignments"), node("Assignments")]
            manual_preset.children = [manual_map]
            presets.children.append(manual_preset)
            source.write_bytes(write_tree(project))

            create_automapped_project(
                source,
                destination,
                plugin_uid=7956475,
                controller_uid=12687768,
            )

            generated = parse_tree(destination.read_bytes())
            hardware_root = next(
                child for child in generated.children if child.type_name == "HardwareControllers"
            )
            controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            presets_root = next(
                child for child in controllers.children[0].children if child.type_name == "MapPresets"
            )
            presets = next(child for child in presets_root.children if child.type_name == "Presets")
            self.assertEqual(
                {preset.get("Name") for preset in presets.children},
                {"Mon mapping manuel", "EC4 AutoMap - Avalon VT-747SP"},
            )
            self.assertEqual(
                next(p for p in presets.children if p.get("Name") == "Mon mapping manuel")
                .children[0]
                .get("mapId"),
                1234567,
            )

    def test_none_plugin_uid_maps_every_plugin_type(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "test.rack2"
            destination = root / "all.rack2"
            project = controller_project(parameter_count=30)
            chains = next(child for child in project.children if child.type_name == "Chains")
            existing = chains.children[0].children[0].children[0]
            duplicate = parse_tree(write_tree(existing))
            duplicate.set("pluginUid", 8888888)
            chains.children[0].children[0].children.append(duplicate)
            source.write_bytes(write_tree(project))

            result = create_automapped_project(
                source,
                destination,
                plugin_uid=None,
                controller_uid=12687768,
            )

            self.assertEqual(result.mapped_plugins, ("Avalon VT-747SP",))
            self.assertEqual(result.mapped_rotaries, 60)
            generated = parse_tree(destination.read_bytes())
            hardware_root = next(
                child for child in generated.children if child.type_name == "HardwareControllers"
            )
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            active_map = next(
                child
                for child in hardware_maps.children
                if child.get("mapId") == hardware_root.get("ActiveMap")
            )
            self.assertEqual(active_map.get("Name"), "EC4 AutoMap - Dynamic")
            assignments = active_map.children[0].children
            self.assertEqual(len(assignments), 60)
            self.assertEqual(
                {assignment.get("ControllableId") for assignment in assignments},
                {"Processor7956475", "Processor8888888"},
            )
            self.assertTrue(all(assignment.get("selectMode") for assignment in assignments))

    def test_dynamic_map_combines_distinct_plugin_types(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "test.rack2"
            destination = root / "all.rack2"
            project = controller_project(parameter_count=30)
            chains = next(child for child in project.children if child.type_name == "Chains")
            existing = chains.children[0].children[0].children[0]
            second = parse_tree(write_tree(existing))
            second.set("pluginTypeId", "VST3-ValhallaPlate-example-0000002a")
            second.set("pluginTypeName", "ValhallaPlate")
            second.set("pluginUid", 9999999)
            second.children[0].children[0].set(
                "pluginTypeId", "VST3-ValhallaPlate-example-0000002a"
            )
            chains.children[0].children[0].children.append(second)
            source.write_bytes(write_tree(project))

            result = create_automapped_project(
                source,
                destination,
                plugin_uid=None,
                controller_uid=12687768,
            )

            self.assertEqual(result.mapped_plugins, ("Avalon VT-747SP", "ValhallaPlate"))
            self.assertEqual(result.mapped_rotaries, 60)
            generated = parse_tree(destination.read_bytes())
            hardware_root = next(
                child for child in generated.children if child.type_name == "HardwareControllers"
            )
            controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            presets_root = next(
                child for child in controllers.children[0].children if child.type_name == "MapPresets"
            )
            presets = next(child for child in presets_root.children if child.type_name == "Presets")
            self.assertEqual(len(presets.children), 2)
            self.assertEqual(presets.children[0].get("Name"), "EC4 AutoMap - Dynamic")
            self.assertEqual(
                len(presets.children[0].children[0].children[0].children),
                60,
            )
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            self.assertEqual(
                {hardware_map.get("Name") for hardware_map in hardware_maps.children},
                {"EC4 AutoMap - Dynamic", "EC4 AutoMap - ValhallaPlate"},
            )

    def test_snapshot_recalled_runtime_map_receives_combined_assignments(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "test.rack2"
            destination = root / "mapped.rack2"
            project = controller_project(parameter_count=30)
            chains = next(child for child in project.children if child.type_name == "Chains")
            existing = chains.children[0].children[0].children[0]
            second = parse_tree(write_tree(existing))
            second.set("pluginTypeId", "VST3-ValhallaPlate-example-0000002a")
            second.set("pluginTypeName", "ValhallaPlate")
            second.set("pluginUid", 9999999)
            second.children[0].children[0].set(
                "pluginTypeId", "VST3-ValhallaPlate-example-0000002a"
            )
            chains.children[0].children[0].children.append(second)

            hardware_root = next(
                child for child in project.children if child.type_name == "HardwareControllers"
            )
            hardware_root.set("ActiveMap", 7_777_777)
            project.children.append(node("GlobalSnapshot", ControllerMapId=7_777_777))
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            runtime_map = node("HardwareCtrlMap", Name="Default Controller Map", mapId=7_777_777)
            runtime_assignments = node("Assignments")
            old_rotary = node(
                "Assignment",
                ParentControllerId=12687768,
                ControllerId=23_000_001,
                ControllableId="Processor7956475",
                ParameterId=29,
                selectMode=True,
            )
            preserved_button = node(
                "Assignment",
                ParentControllerId=12687768,
                ControllerId=22_000_001,
                ControllableId="PluginWindow",
                ParameterId=0,
                selectMode=True,
            )
            runtime_assignments.children = [old_rotary, preserved_button]
            runtime_map.children = [runtime_assignments]
            hardware_maps.children.append(runtime_map)
            source.write_bytes(write_tree(project))

            create_automapped_project(
                source,
                destination,
                plugin_uid=None,
                controller_uid=12687768,
                expand_to_fullbank=True,
            )

            generated = parse_tree(destination.read_bytes())
            hardware_root = next(
                child for child in generated.children if child.type_name == "HardwareControllers"
            )
            self.assertEqual(hardware_root.get("ActiveMap"), 7_777_777)
            snapshot = next(
                child for child in generated.children if child.type_name == "GlobalSnapshot"
            )
            self.assertEqual(snapshot.get("ControllerMapId"), 7_777_777)
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            runtime_map = next(
                child for child in hardware_maps.children if child.get("mapId") == 7_777_777
            )
            assignments = runtime_map.children[0].children
            self.assertEqual(runtime_map.get("Name"), "EC4 AutoMap - Dynamic")
            self.assertEqual(len(assignments), 61)
            self.assertEqual(
                sum(assignment.get("ControllableId") == "PluginWindow" for assignment in assignments),
                1,
            )
            self.assertNotIn(
                ("Processor7956475", 29),
                {
                    (assignment.get("ControllableId"), assignment.get("ParameterId"))
                    for assignment in assignments
                    if assignment.get("ControllerId") == 23_000_001
                },
            )


if __name__ == "__main__":
    unittest.main()
