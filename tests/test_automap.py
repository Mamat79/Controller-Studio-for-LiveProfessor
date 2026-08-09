import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ec4lpbridge.automap import (
    AutoMapError,
    create_automapped_project,
    inspect_project,
    plugin_map_type_id,
    repair_automapped_project,
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


def controller_template(project: ValueTree) -> ValueTree:
    hardware_root = next(
        child for child in project.children if child.type_name == "HardwareControllers"
    )
    controllers = next(
        child for child in hardware_root.children if child.type_name == "HardwareControllers"
    )
    template = parse_tree(write_tree(controllers.children[0]))
    template.type_name = "LPController"
    return template


class AutoMapTests(unittest.TestCase):
    def test_plugin_uid_conversion_matches_liveprofessor_serialization(self):
        self.assertEqual(
            plugin_map_type_id("VST3-Avalon VT-747SP-b86068d4-ca0ebedb"),
            "plugin-UID-905003301",
        )
        self.assertEqual(
            plugin_map_type_id("VST3-CEDAR StageVox-b91618f4-50070f0"),
            "plugin-UID-83914992",
        )
        with self.assertRaises(AutoMapError):
            plugin_map_type_id("unsupported")

    def test_inventory_skips_unsupported_plugin_and_keeps_supported_ones(self):
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "test.rack2"
            project = controller_project()
            chains = next(child for child in project.children if child.type_name == "Chains")
            supported_chain = chains.children[0]
            unsupported_chain = parse_tree(write_tree(supported_chain))
            unsupported_plugin = next(
                child
                for child in unsupported_chain.children
                if child.type_name == "ChainPlugins"
            ).children[0]
            unsupported_plugin.set("pluginTypeName", "Unsupported Test")
            unsupported_plugin.set("pluginTypeId", "unsupported")
            unsupported_plugin.set("pluginUid", 9_999_999)
            chains.children.append(unsupported_chain)
            source.write_bytes(write_tree(project))

            inventory = inspect_project(source)

            self.assertEqual(len(inventory.plugins), 1)
            self.assertEqual(len(inventory.skipped_plugins), 1)
            self.assertIn("Unsupported Test", inventory.skipped_plugins[0])

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

    def test_controllerless_project_uses_embedded_template(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "controllerless.rack2"
            template_path = root / "Ec4-UniBank.ctrl2"
            destination = root / "mapped.rack2"
            project = controller_project(parameter_count=30)
            template_path.write_bytes(write_tree(controller_template(project)))
            hardware_root = next(
                child for child in project.children if child.type_name == "HardwareControllers"
            )
            controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            controllers.children.clear()
            source.write_bytes(write_tree(project))
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            inventory = inspect_project(source, controller_template=template_path)

            self.assertEqual(len(inventory.controllers), 1)
            self.assertTrue(inventory.controllers[0].is_embedded)
            self.assertEqual(inventory.controllers[0].rotary_count, 16)

            result = create_automapped_project(
                source,
                destination,
                plugin_uid=None,
                controller_uid=inventory.controllers[0].controller_uid,
                expand_to_fullbank=False,
                controller_template=template_path,
            )

            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
            self.assertEqual(result.controller_rotaries, 16)
            generated = parse_tree(destination.read_bytes())
            hardware_root = next(
                child for child in generated.children if child.type_name == "HardwareControllers"
            )
            controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            self.assertEqual(len(controllers.children), 1)
            self.assertEqual(controllers.children[0].type_name, "HardwareController")
            self.assertEqual(controllers.children[0].get("ControllerType"), "Companion")
            active_map_id = hardware_root.get("ActiveMap")
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            active_map = next(
                child for child in hardware_maps.children if child.get("mapId") == active_map_id
            )
            self.assertEqual(len(active_map.children[0].children), 16)

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
                {"Mon mapping manuel", "SiLeMI/O AutoMap - Avalon VT-747SP"},
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
            self.assertEqual(active_map.get("Name"), "SiLeMI/O AutoMap - Dynamic")
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
            self.assertEqual(presets.children[0].get("Name"), "SiLeMI/O AutoMap - Dynamic")
            self.assertEqual(
                len(presets.children[0].children[0].children[0].children),
                60,
            )
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            self.assertEqual(
                {hardware_map.get("Name") for hardware_map in hardware_maps.children},
                {"SiLeMI/O AutoMap - Dynamic", "SiLeMI/O AutoMap - ValhallaPlate"},
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
            self.assertEqual(runtime_map.get("Name"), "SiLeMI/O AutoMap - Dynamic")
            self.assertEqual(len(assignments), 61)
            self.assertEqual(
                sum(assignment.get("ControllableId") == "PluginWindow" for assignment in assignments),
                1,
            )
            self.assertIn(
                ("Processor7956475", 29),
                {
                    (assignment.get("ControllableId"), assignment.get("ParameterId"))
                    for assignment in assignments
                    if assignment.get("ControllerId") == 23_000_001
                },
            )

    def test_snapshot_map_id_is_reserved_for_runtime_and_never_reused_by_a_preset(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.rack2"
            destination = root / "mapped.rack2"
            project = controller_project()
            hardware_root = next(
                child for child in project.children if child.type_name == "HardwareControllers"
            )
            runtime_map_id = 30_000_050
            hardware_root.set("ActiveMap", runtime_map_id)
            project.children.append(node("GlobalSnapshot", ControllerMapId=runtime_map_id))
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            runtime_map = node("HardwareCtrlMap", Name="Default", mapId=runtime_map_id)
            runtime_map.children = [node("Assignments")]
            hardware_maps.children.append(runtime_map)
            source.write_bytes(write_tree(project))

            create_automapped_project(
                source,
                destination,
                plugin_uid=None,
                controller_uid=12687768,
                expand_to_fullbank=False,
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
            generated_preset = next(
                preset
                for preset in presets.children
                if preset.get("Name") == "SiLeMI/O AutoMap - Avalon VT-747SP"
            )
            self.assertNotEqual(generated_preset.children[0].get("mapId"), runtime_map_id)
            self.assertEqual(hardware_root.get("ActiveMap"), runtime_map_id)

    def test_existing_manual_profile_keeps_only_matched_button_label_pair(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.rack2"
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
                Name="Mon ordre essentiel",
                TypeId="plugin-UID-905003301",
                ControllerId=12687768,
            )
            manual_map = node(
                "ControllerMapPreset",
                Name="Mon ordre essentiel",
                TypeId="plugin-UID-905003301",
                ControllerId=12687768,
                SelectMode=True,
                mapId=7654321,
            )
            learned = node("Assignments")
            learned.children = [
                node(
                    "Assignment",
                    ParentControllerId=12687768,
                    ControllerId=23_000_001,
                    ControllableId="Processor7956475",
                    ParameterId=8,
                    selectMode=True,
                ),
                node(
                    "Assignment",
                    ParentControllerId=12687768,
                    ControllerId=23_000_016,
                    ControllableId="Processor7956475",
                    ParameterId=9,
                    selectMode=True,
                ),
                node(
                    "Assignment",
                    ParentControllerId=12687768,
                    ControllerId=23_000_003,
                    ControllableId="Processor7956475",
                    ParameterId=8,
                    selectMode=True,
                ),
                node(
                    "Assignment",
                    ParentControllerId=12687768,
                    ControllerId=22_000_002,
                    ControllableId="Processor7956475",
                    ParameterId=5,
                    selectMode=True,
                ),
            ]
            manual_map.children = [learned, parse_tree(write_tree(learned))]
            manual_preset.children = [manual_map]
            presets.children.append(manual_preset)
            source.write_bytes(write_tree(project))

            create_automapped_project(
                source,
                destination,
                plugin_uid=None,
                controller_uid=12687768,
                expand_to_fullbank=False,
            )

            generated = parse_tree(destination.read_bytes())
            hardware_root = next(
                child for child in generated.children if child.type_name == "HardwareControllers"
            )
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            active_map = next(
                item for item in hardware_maps.children if item.get("mapId") == hardware_root.get("ActiveMap")
            )
            mapped = {
                assignment.get("ControllerId"): assignment.get("ParameterId")
                for assignment in active_map.children[0].children
                if assignment.get("ControllableId") == "Processor7956475"
            }
            self.assertEqual(mapped[23_000_002], 5)
            self.assertEqual(mapped[23_000_016], 9)
            self.assertEqual(mapped[22_000_002], 5)
            rotary_values = [
                parameter_id
                for control_id, parameter_id in mapped.items()
                if 23_000_001 <= control_id <= 23_000_016
            ]
            self.assertEqual(rotary_values.count(8), 1)
            self.assertEqual(len(rotary_values), len(set(rotary_values)))
            duplicate_places = {
                parameter_id: sorted(control_id for control_id, value in mapped.items() if value == parameter_id)
                for parameter_id in set(mapped.values())
                if list(mapped.values()).count(parameter_id) > 1
            }
            self.assertEqual(duplicate_places, {5: [22_000_002, 23_000_002]})

    def test_automap_keeps_complementary_manual_parameters_once(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "manual.rack2"
            mapped = root / "mapped.rack2"
            project = controller_project(parameter_count=30)
            chains = next(child for child in project.children if child.type_name == "Chains")
            plugins = next(
                child
                for child in chains.children[0].children
                if child.type_name == "ChainPlugins"
            )
            second = parse_tree(write_tree(plugins.children[0]))
            second.set("pluginUid", 8_888_888)
            plugins.children.append(second)

            hardware_root = next(
                child for child in project.children if child.type_name == "HardwareControllers"
            )
            runtime_map_id = 30_000_050
            hardware_root.set("ActiveMap", runtime_map_id)
            project.children.append(node("GlobalSnapshot", ControllerMapId=runtime_map_id))
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            assignments = node("Assignments")
            for plugin_uid, values in (
                (7_956_475, (0, 1, 2)),
                (8_888_888, (0, 28)),
            ):
                for number, parameter_id in enumerate(values, 1):
                    assignments.children.append(
                        node(
                            "Assignment",
                            ParentControllerId=12_687_768,
                            ControllerId=23_000_000 + number,
                            ControllableId=f"Processor{plugin_uid}",
                            ParameterId=parameter_id,
                        )
                    )
            runtime_map = node("HardwareCtrlMap", Name="Dynamic", mapId=runtime_map_id)
            runtime_map.children = [assignments, parse_tree(write_tree(assignments))]
            hardware_maps.children.append(runtime_map)
            source.write_bytes(write_tree(project))

            create_automapped_project(
                source,
                mapped,
                plugin_uid=None,
                controller_uid=12_687_768,
                expand_to_fullbank=False,
            )

            generated = parse_tree(mapped.read_bytes())
            generated_hardware = next(
                child
                for child in generated.children
                if child.type_name == "HardwareControllers"
            )
            generated_maps = next(
                child
                for child in generated_hardware.children
                if child.type_name == "HardwareCtrlMaps"
            )
            generated_map = next(
                item for item in generated_maps.children if item.get("mapId") == runtime_map_id
            )
            layouts = {}
            for plugin_uid in (7_956_475, 8_888_888):
                layouts[plugin_uid] = {
                    assignment.get("ControllerId"): assignment.get("ParameterId")
                    for assignment in generated_map.children[0].children
                    if assignment.get("ControllableId") == f"Processor{plugin_uid}"
                }
            self.assertEqual(layouts[7_956_475], layouts[8_888_888])
            self.assertIn(1, layouts[7_956_475].values())
            self.assertIn(28, layouts[7_956_475].values())
            self.assertEqual(
                len(layouts[7_956_475].values()),
                len(set(layouts[7_956_475].values())),
            )

    def test_repair_merges_stale_dynamic_presets_and_preserves_active_changes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.rack2"
            mapped = root / "mapped.rack2"
            corrupted = root / "corrupted.rack2"
            repaired = root / "repaired.rack2"
            project = controller_project()
            chains = next(child for child in project.children if child.type_name == "Chains")
            first = chains.children[0].children[0].children[0]
            second = parse_tree(write_tree(first))
            second.set("pluginUid", 8_888_888)
            chains.children[0].children[0].children.append(second)
            hardware_root = next(
                child for child in project.children if child.type_name == "HardwareControllers"
            )
            runtime_map_id = 30_000_050
            hardware_root.set("ActiveMap", runtime_map_id)
            project.children.append(node("GlobalSnapshot", ControllerMapId=runtime_map_id))
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            runtime_map = node("HardwareCtrlMap", Name="Default", mapId=runtime_map_id)
            runtime_map.children = [node("Assignments")]
            hardware_maps.children.append(runtime_map)
            source.write_bytes(write_tree(project))
            create_automapped_project(
                source,
                mapped,
                plugin_uid=None,
                controller_uid=12687768,
                expand_to_fullbank=False,
            )

            damaged = parse_tree(mapped.read_bytes())
            hardware_root = next(
                child for child in damaged.children if child.type_name == "HardwareControllers"
            )
            controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            active_map = next(
                item for item in hardware_maps.children if item.get("mapId") == runtime_map_id
            )
            original_assignments = parse_tree(write_tree(active_map.children[0]))
            manual_preset = node(
                "MapPreset",
                Name="Mapping manuel tardif",
                TypeId="plugin-UID-905003301",
                ControllerId=12687768,
            )
            manual_map = node(
                "ControllerMapPreset",
                Name="EC4 AutoMap - Dynamic",
                TypeId="plugin-UID-905003301",
                ControllerId=12687768,
                SelectMode=True,
                mapId=runtime_map_id,
            )
            manual_map.children = [
                parse_tree(write_tree(original_assignments)),
                parse_tree(write_tree(original_assignments)),
            ]
            manual_preset.children = [manual_map]
            presets_root = next(
                child for child in controllers.children[0].children if child.type_name == "MapPresets"
            )
            presets = next(child for child in presets_root.children if child.type_name == "Presets")
            presets.children.append(manual_preset)
            active_map.children[0].children = [
                assignment
                for assignment in active_map.children[0].children
                if assignment.get("ControllableId") == "Processor8888888"
            ]
            changed = next(
                assignment
                for assignment in active_map.children[0].children
                if assignment.get("ControllerId") == 23_000_001
            )
            changed.set("ParameterId", 7)
            corrupted.write_bytes(write_tree(damaged))
            source_hash = hashlib.sha256(corrupted.read_bytes()).hexdigest()

            result = repair_automapped_project(
                corrupted,
                repaired,
                controller_uid=12687768,
            )

            self.assertEqual(hashlib.sha256(corrupted.read_bytes()).hexdigest(), source_hash)
            self.assertGreaterEqual(result.restored_assignments, 16)
            self.assertGreaterEqual(result.conflicts_preserved, 1)
            self.assertGreaterEqual(result.synchronized_presets, 1)
            fixed = parse_tree(repaired.read_bytes())
            hardware_root = next(
                child for child in fixed.children if child.type_name == "HardwareControllers"
            )
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            active_map = next(
                item for item in hardware_maps.children if item.get("mapId") == runtime_map_id
            )
            active = {
                (assignment.get("ControllableId"), assignment.get("ControllerId")): assignment.get(
                    "ParameterId"
                )
                for assignment in active_map.children[0].children
            }
            self.assertEqual(active[("Processor8888888", 23_000_001)], 7)
            self.assertIn(("Processor7956475", 23_000_001), active)
            first_layout = {
                control_id: parameter_id
                for (processor, control_id), parameter_id in active.items()
                if processor == "Processor7956475"
            }
            second_layout = {
                control_id: parameter_id
                for (processor, control_id), parameter_id in active.items()
                if processor == "Processor8888888"
            }
            self.assertEqual(first_layout, second_layout)
            self.assertEqual(len(first_layout.values()), len(set(first_layout.values())))
            fixed_controllers = next(
                child for child in hardware_root.children if child.type_name == "HardwareControllers"
            )
            fixed_presets_root = next(
                child
                for child in fixed_controllers.children[0].children
                if child.type_name == "MapPresets"
            )
            fixed_presets = next(
                child for child in fixed_presets_root.children if child.type_name == "Presets"
            )
            dynamic_map = next(
                child
                for preset in fixed_presets.children
                for child in preset.children
                if child.type_name == "ControllerMapPreset"
                and child.get("Name") == "EC4 AutoMap - Dynamic"
            )
            dynamic_values = {
                (assignment.get("ControllableId"), assignment.get("ControllerId")): assignment.get(
                    "ParameterId"
                )
                for assignment in dynamic_map.children[0].children
            }
            self.assertEqual(dynamic_values[("Processor8888888", 23_000_001)], 7)
            self.assertIn(("Processor7956475", 23_000_001), dynamic_values)

    def test_repair_unifies_instances_without_losing_unique_manual_parameters(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "manual.rack2"
            repaired = root / "repaired.rack2"
            project = controller_project(parameter_count=30)
            chains = next(child for child in project.children if child.type_name == "Chains")
            plugins = next(
                child
                for child in chains.children[0].children
                if child.type_name == "ChainPlugins"
            )
            second = parse_tree(write_tree(plugins.children[0]))
            second.set("pluginUid", 8_888_888)
            plugins.children.append(second)

            hardware_root = next(
                child for child in project.children if child.type_name == "HardwareControllers"
            )
            runtime_map_id = 30_000_050
            hardware_root.set("ActiveMap", runtime_map_id)
            project.children.append(node("GlobalSnapshot", ControllerMapId=runtime_map_id))
            hardware_maps = next(
                child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"
            )
            assignments = node("Assignments")
            for plugin_uid, values in (
                (7_956_475, (0, 1, 2)),
                (8_888_888, (0, 3)),
            ):
                for number, parameter_id in enumerate(values, 1):
                    assignments.children.append(
                        node(
                            "Assignment",
                            ParentControllerId=12_687_768,
                            ControllerId=23_000_000 + number,
                            ControllableId=f"Processor{plugin_uid}",
                            ParameterId=parameter_id,
                        )
                    )
            runtime_map = node("HardwareCtrlMap", Name="Dynamic", mapId=runtime_map_id)
            runtime_map.children = [assignments, parse_tree(write_tree(assignments))]
            hardware_maps.children.append(runtime_map)
            source.write_bytes(write_tree(project))

            repair_automapped_project(source, repaired, controller_uid=12_687_768)

            fixed = parse_tree(repaired.read_bytes())
            fixed_hardware = next(
                child for child in fixed.children if child.type_name == "HardwareControllers"
            )
            fixed_maps = next(
                child
                for child in fixed_hardware.children
                if child.type_name == "HardwareCtrlMaps"
            )
            fixed_map = next(
                item for item in fixed_maps.children if item.get("mapId") == runtime_map_id
            )
            layouts = {}
            for plugin_uid in (7_956_475, 8_888_888):
                layouts[plugin_uid] = {
                    assignment.get("ControllerId"): assignment.get("ParameterId")
                    for assignment in fixed_map.children[0].children
                    if assignment.get("ControllableId") == f"Processor{plugin_uid}"
                }
            self.assertEqual(layouts[7_956_475], layouts[8_888_888])
            self.assertEqual(set(layouts[7_956_475].values()), {0, 1, 2, 3})
            self.assertEqual(
                len(layouts[7_956_475].values()),
                len(set(layouts[7_956_475].values())),
            )


if __name__ == "__main__":
    unittest.main()
