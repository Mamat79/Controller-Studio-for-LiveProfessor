import unittest

from scripts.repair_ctrl2 import (
    ValueTree,
    Variant,
    MARKER_INT,
    MARKER_STRING,
    parse_tree,
    repair_controller,
    write_tree,
)


def prop(name, value):
    marker = MARKER_INT if isinstance(value, int) else MARKER_STRING
    return name, Variant(marker, value)


def hardware_control(control_id, style, tag, name, address):
    return ValueTree(
        "HardwareControl",
        [
            prop("id", control_id),
            prop("ControlStyle", style),
            prop("tag", tag),
            prop("Name", name),
            prop("OSCAddressPatern", address),
        ],
        [],
    )


class RepairControllerTests(unittest.TestCase):
    def make_controller(self):
        buttons = []
        for number in range(1, 17):
            address = (
                f"/Companion/Rotary{number}"
                if number <= 2
                else f"/Companion/GenericButtons/Button{number}"
            )
            buttons.append(
                hardware_control(
                    number,
                    2,
                    f"GenericButton{number}",
                    f"Rotary{number}" if number <= 2 else f"Generic Button {number}",
                    address,
                )
            )

        rotaries = [
            hardware_control(
                100 + number,
                0,
                f"Rotary{number}" if number <= 4 else "",
                f"Rotary {number}",
                f"/Companion/Rotary{number}",
            )
            for number in range(1, 17)
        ]
        assignments = ValueTree(
            "Assignments",
            [],
            [
                ValueTree("Assignment", [prop("ControllerId", 1)], []),
                ValueTree("Assignment", [prop("ControllerId", 101)], []),
                ValueTree("Assignment", [prop("ControllerId", 2)], []),
            ],
        )
        return ValueTree(
            "LPController",
            [],
            [
                ValueTree("Controls", [], buttons + rotaries),
                assignments,
                ValueTree(
                    "MapPresets",
                    [],
                    [ValueTree("Presets", [prop("Name", "Ancien plugin")], [])],
                ),
            ],
        )

    def test_repair_restores_unique_buttons_rotaries_and_all_sixteen_tags(self):
        controller = self.make_controller()

        stats = repair_controller(controller)

        controls = controller.children[0].children
        self.assertEqual(stats["assignments_removed"], 2)
        self.assertEqual(len(controller.children[1].children), 1)
        self.assertEqual(controller.children[1].children[0].get("ControllerId"), 101)
        for number, control in enumerate(controls[:16], start=1):
            self.assertEqual(control.get("Name"), f"Generic Button {number}")
            self.assertEqual(
                control.get("OSCAddressPatern"),
                f"/Companion/GenericButtons/Button{number}",
            )
        for number, control in enumerate(controls[16:], start=1):
            self.assertEqual(control.get("tag"), f"Rotary{number}")
            self.assertEqual(control.get("OSCAddressPatern"), f"/Companion/Rotary{number}")

        encoded = write_tree(controller)
        self.assertEqual(write_tree(parse_tree(encoded)), encoded)

    def test_clean_map_presets_creates_neutral_controller(self):
        controller = self.make_controller()

        stats = repair_controller(controller, clean_map_presets=True)

        map_presets = next(
            child for child in controller.children if child.type_name == "MapPresets"
        )
        self.assertEqual(map_presets.children, [])
        self.assertEqual(stats["map_presets_removed"], 1)


if __name__ == "__main__":
    unittest.main()
