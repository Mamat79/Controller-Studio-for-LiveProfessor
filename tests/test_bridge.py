import unittest
from types import SimpleNamespace

from silemio_control_hub.runtime.config import BridgeConfig
from silemio_control_hub.runtime.ec4_liveprofessor import (
    EC4LiveProfessorRuntime as EC4LiveProfessorBridge,
)
from silemio_control_hub.adapters.devices.ec4_protocol import (
    EC4SetupState,
    main_display_message,
    parameter_grid_message,
    total_display_message,
)


class FakeMidi:
    def __init__(self):
        self.is_open = True
        self.cc = []
        self.sysex = []

    def send_cc(self, channel, control, value):
        self.cc.append((channel, control, value))

    def send_sysex(self, data):
        self.sysex.append(bytes(data))

    def close(self):
        self.is_open = False


class FakeOSC:
    def __init__(self):
        self.messages = []

    def send(self, address, *args):
        self.messages.append((address, args))


class BridgeTests(unittest.TestCase):
    def make_bridge(self, **changes):
        changes.setdefault("display_enabled", False)
        changes.setdefault("restrict_to_target", False)
        config = BridgeConfig(**changes)
        bridge = EC4LiveProfessorBridge(config)
        bridge._midi.close()
        bridge._osc_client.close()
        bridge._midi = FakeMidi()
        bridge._osc_client = FakeOSC()
        return bridge

    def test_encoder_sends_current_bank_parameter(self):
        bridge = self.make_bridge(max_controls=33)
        bridge.set_bank(1)
        bridge._on_midi(
            SimpleNamespace(type="control_change", channel=12, control=48, value=64)
        )
        self.assertEqual(bridge._osc_client.messages[-1][0], "/Companion/Rotary17")
        self.assertAlmostEqual(bridge._osc_client.messages[-1][1][0], 64 / 127)

    def test_feedback_updates_physical_encoder(self):
        bridge = self.make_bridge()
        bridge._on_osc("/Companion/Rotary1", [0.5])
        self.assertEqual(bridge._midi.cc[-1], (12, 48, 64))

    def test_identical_midi_echo_is_ignored(self):
        bridge = self.make_bridge()
        bridge._on_osc("/Companion/Rotary1", [0.5])
        bridge._on_midi(
            SimpleNamespace(type="control_change", channel=12, control=48, value=64)
        )
        self.assertFalse(bridge._osc_client.messages)

    def test_companion_name_and_display_value_feedback(self):
        bridge = self.make_bridge()
        bridge._on_osc("/Companion/ControllerNames", ["Rotary1", "Threshold"])
        bridge._on_osc("/Companion/ControllerValues", ["Rotary1", "-12.0 dB"])
        self.assertEqual((bridge.names[0], bridge.display_values[0]), ("Threshold", "-12.0 dB"))

    def test_push_name_is_visible_without_overriding_a_rotary_label(self):
        bridge = self.make_bridge()
        bridge._on_osc("/Companion/ControllerNames", ["Generic Button 1", "Bypass"])
        bridge._on_osc("/Companion/ControllerValues", ["Generic Button 1", "On"])
        self.assertEqual((bridge.button_names[0], bridge.button_display_values[0]), ("Bypass", "On"))
        self.assertEqual(bridge._display_short_label(0, ""), "Bypa")

        bridge._on_osc("/Companion/ControllerNames", ["Rotary1", "Threshold"])
        self.assertEqual(bridge._display_short_label(0, bridge.short_names[0]), "Thre")

        overlays = []
        bridge._show_overlay = overlays.append
        bridge._handle_parameter_push(0)
        self.assertEqual(overlays[-1][:2], ["Bypass", "On"])

    def test_companion_reports_missing_first_bank_rotaries(self):
        logs = []
        bridge = EC4LiveProfessorBridge(
            BridgeConfig(display_enabled=False, restrict_to_target=False),
            log_callback=logs.append,
        )
        self.addCleanup(bridge._osc_client.close)
        bridge._on_osc("/Companion/ControllerNames", ["Rotary1", "Threshold"])
        bridge._name_inventory_timer.cancel()
        bridge._name_inventory_timer = None
        bridge._report_companion_inventory()
        self.assertIn("1/16 rotatifs", logs[-1])
        self.assertIn("2, 3, 4", logs[-1])

    def test_navigation_uses_liveprofessor_compatible_command(self):
        bridge = self.make_bridge()
        bridge._handle_note(12, 113)
        self.assertEqual(
            bridge._osc_client.messages[-1][0],
            "/Command/SelectedPlugin/EnableProcessingonselectedplugin",
        )

    def test_plugin_and_chain_navigation_commands(self):
        bridge = self.make_bridge()
        bridge._handle_note(12, 115)
        bridge._handle_note(12, 119)
        self.assertEqual(
            [message[0] for message in bridge._osc_client.messages],
            [
                "/Command/PluginWindows/SelectNextPlugin",
                "/Command/PluginWindows/SelectNextChain",
            ],
        )

    def test_partial_last_bank_is_clamped(self):
        bridge = self.make_bridge(max_controls=33)
        bridge.set_bank(99)
        self.assertEqual((bridge.active_bank, bridge.bank_count), (2, 3))
        bridge._on_midi(
            SimpleNamespace(type="control_change", channel=13, control=80, value=127)
        )
        self.assertFalse(bridge._osc_client.messages)

    def test_display_is_limited_to_device_setup_and_group(self):
        bridge = EC4LiveProfessorBridge(
            BridgeConfig(display_enabled=True, target_setup=13, target_group=3)
        )
        self.addCleanup(bridge._osc_client.close)
        bridge._midi = FakeMidi()
        bridge.setup_state = EC4SetupState(setup=12, group=1)
        self.assertFalse(bridge._display_allowed())
        bridge.setup_state = EC4SetupState(setup=12, group=2)
        self.assertTrue(bridge._display_allowed())

    def test_persistent_parameter_grid_is_sent_on_active_target(self):
        bridge = EC4LiveProfessorBridge(
            BridgeConfig(
                display_enabled=True,
                persistent_parameter_display=True,
                target_setup=5,
                target_group=7,
            )
        )
        self.addCleanup(bridge._osc_client.close)
        bridge._midi = FakeMidi()
        bridge.setup_state = EC4SetupState(setup=4, group=6)
        bridge._refresh_main_display()
        self.assertEqual([len(message) for message in bridge._midi.sysex[-2:]], [206, 257])

    def test_controls_are_ignored_outside_dedicated_group(self):
        bridge = EC4LiveProfessorBridge(
            BridgeConfig(display_enabled=False, target_setup=9, target_group=13)
        )
        bridge._osc_client.close()
        bridge._midi = FakeMidi()
        bridge._osc_client = FakeOSC()
        bridge.setup_state = EC4SetupState(setup=8, group=0)
        message = SimpleNamespace(type="control_change", channel=12, control=48, value=64)
        bridge._on_midi(message)
        self.assertFalse(bridge._osc_client.messages)
        bridge.setup_state = EC4SetupState(setup=8, group=12)
        bridge._on_midi(message)
        self.assertEqual(bridge._osc_client.messages[-1][0], "/Companion/Rotary1")

    def test_learned_mapping_replaces_ableton_cc_and_drives_feedback(self):
        mapping = [
            {
                "channel": 2,
                "control": 20 + index,
                "push_channel": 3,
                "push_note": 60 + index,
            }
            for index in range(16)
        ]
        bridge = EC4LiveProfessorBridge(
            BridgeConfig(
                display_enabled=False,
                target_setup=5,
                target_group=7,
                encoder_mappings={"5:7": mapping},
            )
        )
        bridge._osc_client.close()
        bridge._midi = FakeMidi()
        bridge._osc_client = FakeOSC()
        bridge.setup_state = EC4SetupState(setup=4, group=6)
        bridge._on_midi(
            SimpleNamespace(type="control_change", channel=2, control=20, value=127)
        )
        self.assertEqual(bridge._osc_client.messages[-1][0], "/Companion/Rotary1")
        bridge._on_osc("/Companion/Rotary1", [0.25])
        self.assertEqual(bridge._midi.cc[-1], (2, 20, 32))
        self.assertEqual(bridge._push_index(3, 60), 0)

    def test_shift_pushes_control_banks_snapshots_navigation_and_tap_tempo(self):
        bridge = self.make_bridge()
        bridge._osc_client.messages.clear()
        bridge.set_bank(1)
        bridge._handle_sysex_button("shift_push", 1)
        self.assertEqual(bridge.active_bank, 2)
        bridge._handle_sysex_button("shift_push", 0)
        self.assertEqual(bridge.active_bank, 1)
        bridge._handle_sysex_button("shift_push", 4)
        self.assertEqual(
            bridge._osc_client.messages[-1][0], "/Command/PluginWindows/ShowHideselectedplugin"
        )
        bridge._handle_sysex_button("shift_push", 8)
        self.assertEqual(
            bridge._osc_client.messages[-1],
            ("/Command/SelectedPlugin/EnableProcessingonselectedplugin", ()),
        )
        bridge._handle_sysex_button("shift_push", 5)
        self.assertEqual(
            bridge._osc_client.messages[-1][0], "/Command/PluginWindows/SelectPreviousChain"
        )
        bridge._handle_sysex_button("shift_push", 6)
        self.assertEqual(
            bridge._osc_client.messages[-1][0], "/Command/PluginWindows/SelectPreviousPlugin"
        )
        bridge._handle_sysex_button("shift_push", 7)
        self.assertEqual(
            bridge._osc_client.messages[-1][0], "/Command/PluginWindows/SelectNextPlugin"
        )
        bridge._handle_sysex_button("shift_push", 9)
        self.assertEqual(
            bridge._osc_client.messages[-1][0], "/Command/PluginWindows/SelectNextChain"
        )
        bridge._handle_sysex_button("shift_push", 10)
        self.assertEqual(
            bridge._osc_client.messages[-1][0], "/Command/PluginWindows/SelectPreviousPlugin"
        )
        bridge._handle_sysex_button("shift_push", 11)
        self.assertEqual(
            bridge._osc_client.messages[-1][0], "/Command/PluginWindows/SelectNextPlugin"
        )
        bridge._handle_sysex_button("shift_push", 12)
        self.assertEqual(bridge._osc_client.messages[-1][0], "/Command/CueLists/FirePreviousCue")
        bridge._handle_sysex_button("shift_push", 13)
        self.assertEqual(bridge._osc_client.messages[-1][0], "/Command/CueLists/FireNextCue")
        bridge._handle_sysex_button("shift_push", 14)
        self.assertEqual(
            bridge._osc_client.messages[-1][0],
            "/Command/GlobalSnapshots/RecallPreviousGlobalSnapshot",
        )
        bridge._handle_sysex_button("shift_push", 15)
        self.assertEqual(
            bridge._osc_client.messages[-1][0],
            "/Command/GlobalSnapshots/RecallNextGlobalSnapshot",
        )
        bridge._active_viewset_index = 1
        bridge._viewset_count = 3
        bridge._handle_sysex_button("shift_push", 2)
        bridge._handle_sysex_button("shift_push", 3)
        self.assertEqual(
            [message for message in bridge._osc_client.messages[-2:]],
            [
                ("/ViewSets/Recall", (0,)),
                ("/ViewSets/Recall", (1,)),
            ],
        )
        bridge._handle_parameter_push(15)
        self.assertEqual(
            bridge._osc_client.messages[-1][0], "/Command/Transport&Tempo/TempoTap"
        )

    def test_shift_push_11_12_map_same_as_7_8_plugins(self):
        bridge = self.make_bridge()
        bridge._osc_client.messages.clear()
        bridge._handle_sysex_button("shift_push", 6)
        self.assertEqual(
            bridge._osc_client.messages[-1][0],
            "/Command/PluginWindows/SelectPreviousPlugin",
        )
        bridge._handle_sysex_button("shift_push", 7)
        self.assertEqual(
            bridge._osc_client.messages[-1][0],
            "/Command/PluginWindows/SelectNextPlugin",
        )

    def test_holding_shift_displays_shortcuts_then_restores_parameters(self):
        bridge = self.make_bridge(
            display_enabled=True,
            persistent_parameter_display=True,
            restrict_to_target=False,
            display_only_supported_setups=False,
        )
        labels = list(EC4LiveProfessorBridge._SHIFT_SHORTCUT_LABELS)
        bridge._midi.sysex.clear()

        bridge._handle_sysex_button("shift", None, pressed=True)

        self.assertTrue(bridge._shift_held)
        self.assertEqual(
            bridge._midi.sysex[-2:],
            [main_display_message(labels), parameter_grid_message(labels)],
        )
        self.assertFalse(bridge._osc_client.messages)

        bridge._handle_sysex_button("shift", None, pressed=False)

        self.assertFalse(bridge._shift_held)
        self.assertEqual([len(message) for message in bridge._midi.sysex[-2:]], [206, 257])
        self.assertNotEqual(bridge._midi.sysex[-1], parameter_grid_message(labels))

    def test_shift_sysex_press_and_release_drive_the_shortcut_display(self):
        bridge = self.make_bridge(
            display_enabled=True,
            persistent_parameter_display=True,
            restrict_to_target=False,
            display_only_supported_setups=False,
        )
        press = bytes.fromhex("f0 00 00 00 4e 2c 1b 4e 26 11 4e 2e 11 f7")
        release = bytes.fromhex("f0 00 00 00 4e 2c 1b 4e 26 11 4e 2e 10 f7")

        bridge._on_midi(SimpleNamespace(type="sysex", data=tuple(press[1:-1])))
        self.assertTrue(bridge._shift_held)

        bridge._on_midi(SimpleNamespace(type="sysex", data=tuple(release[1:-1])))
        self.assertFalse(bridge._shift_held)

    def test_shift_release_after_shortcut_cancels_overlay_and_restores_grid(self):
        bridge = self.make_bridge(
            display_enabled=True,
            persistent_parameter_display=True,
            restrict_to_target=False,
            display_only_supported_setups=False,
        )
        bridge._handle_sysex_button("shift", None, pressed=True)
        bridge._handle_sysex_button("shift_push", 6)
        self.assertIsNotNone(bridge._overlay_timer)

        bridge._handle_sysex_button("shift", None, pressed=False)

        self.assertIsNone(bridge._overlay_timer)
        self.assertFalse(bridge._shift_held)
        self.assertEqual(len(bridge._midi.sysex[-1]), 257)

    def test_released_shift_push_does_not_repeat_command(self):
        bridge = self.make_bridge()
        bridge._handle_sysex_button("shift_push", 6, pressed=False)
        self.assertFalse(bridge._osc_client.messages)
        bridge._handle_sysex_button("shift_push", 10)
        self.assertEqual(
            bridge._osc_client.messages[-1][0],
            "/Command/PluginWindows/SelectPreviousPlugin",
        )
        bridge._handle_sysex_button("shift_push", 11)
        self.assertEqual(
            bridge._osc_client.messages[-1][0],
            "/Command/PluginWindows/SelectNextPlugin",
        )

    def test_command_aliases_resolve_to_one_compatible_address(self):
        self.assertEqual(
            EC4LiveProfessorBridge._command_fallbacks("/Command/CueList/RecallPreviousCue"),
            ("/Command/CueLists/FirePreviousCue",),
        )
        self.assertEqual(
            EC4LiveProfessorBridge._command_fallbacks(
                "/Command/PluginWindows/ShowHideSelectedPlugin"
            ),
            ("/Command/PluginWindows/ShowHideselectedplugin",),
        )
        self.assertEqual(
            EC4LiveProfessorBridge._command_fallbacks(
                "/Command/SelectedPlugin/EnableProcessingOnSelectedPlugin"
            ),
            ("/Command/SelectedPlugin/EnableProcessingonselectedplugin",),
        )

    def test_viewset_inventory_uses_feedback_index_not_argument_count(self):
        bridge = self.make_bridge()
        for index in range(5):
            bridge._on_osc("/ViewSets/Update", [f"View Set {index + 1}", index])
        bridge._on_osc("/ViewSets/Recall", ["View Set 3", 2])
        self.assertEqual((bridge._viewset_count, bridge._active_viewset_index), (5, 2))
        bridge._handle_sysex_button("shift_push", 3)
        self.assertEqual(bridge._osc_client.messages[-1], ("/ViewSets/Recall", (3,)))

    def test_all_fifteen_plugin_pushes_send_press_and_release(self):
        bridge = self.make_bridge()
        for index in range(15):
            note = 40 + index
            bridge._on_midi(
                SimpleNamespace(type="note_on", channel=12, note=note, velocity=127)
            )
            bridge._on_midi(
                SimpleNamespace(type="note_off", channel=12, note=note, velocity=0)
            )
        self.assertEqual(len(bridge._osc_client.messages), 30)
        for index in range(15):
            address = f"/Companion/GenericButtons/Button{index + 1}"
            self.assertEqual(
                bridge._osc_client.messages[index * 2 : index * 2 + 2],
                [(address, (1.0,)), (address, (0.0,))],
            )

    def test_sixteenth_simple_push_remains_reserved_for_tap_tempo(self):
        bridge = self.make_bridge()
        bridge._on_midi(SimpleNamespace(type="note_on", channel=12, note=55, velocity=127))
        bridge._on_midi(SimpleNamespace(type="note_off", channel=12, note=55, velocity=0))
        self.assertEqual(
            bridge._osc_client.messages,
            [("/Command/Transport&Tempo/TempoTap", ())],
        )

    def test_parameter_motion_is_confirmed_by_liveprofessor_feedback(self):
        bridge = self.make_bridge()
        bridge._on_midi(
            SimpleNamespace(type="control_change", channel=12, control=48, value=64)
        )
        self.assertIn(0, bridge._pending_feedback)
        bridge._on_osc("/Companion/Rotary1", [64 / 127])
        self.assertNotIn(0, bridge._pending_feedback)
        self.assertNotIn(0, bridge._feedback_timers)

    def test_startup_banner_shown_on_connect(self):
        bridge = self.make_bridge(display_enabled=True, restrict_to_target=False, ui_language="fr")
        bridge._midi.sysex.clear()
        bridge._startup_banner_shown = False
        bridge.show_startup_banner()
        self.assertTrue(bridge._startup_banner_shown)
        self.assertEqual(
            bridge._midi.sysex[-1],
            total_display_message(
                [
                    "Connexion OK",
                    "SiLeMI/O CtrlStudio",
                    "By Mamat",
                    "-----[]---",
                ],
                alignments=["center", "center", "right", "right"],
            ),
        )
        banner_count = len(bridge._midi.sysex)
        bridge.show_startup_banner()
        self.assertEqual(len(bridge._midi.sysex), banner_count)


if __name__ == "__main__":
    unittest.main()
