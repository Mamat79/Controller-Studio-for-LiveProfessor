import unittest
from types import SimpleNamespace

from ec4lpbridge.bridge import EC4LiveProfessorBridge
from ec4lpbridge.config import BridgeConfig
from ec4lpbridge.ec4_protocol import EC4SetupState


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

    def test_simple_pushes_send_companion_button_press_and_release(self):
        bridge = self.make_bridge()
        bridge._on_midi(SimpleNamespace(type="note_on", channel=12, note=40, velocity=127))
        bridge._on_midi(SimpleNamespace(type="note_off", channel=12, note=40, velocity=0))
        self.assertEqual(
            bridge._osc_client.messages[-2:],
            [
                ("/Companion/GenericButtons/Button1", (1.0,)),
                ("/Companion/GenericButtons/Button1", (0.0,)),
            ],
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
        self.assertTrue(len(bridge._midi.sysex) > 0)
        banner_count = len(bridge._midi.sysex)
        bridge.show_startup_banner()
        self.assertEqual(len(bridge._midi.sysex), banner_count)


if __name__ == "__main__":
    unittest.main()
