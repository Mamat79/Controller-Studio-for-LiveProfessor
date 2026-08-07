import unittest

from ec4lpbridge.ec4_protocol import (
    SETUP_REQUEST,
    SUPPORTED_DISPLAY_GROUPS,
    SUPPORTED_DISPLAY_SETUPS,
    feedback_cc,
    macro_index,
    main_display_message,
    parameter_grid_message,
    parse_button_sysex,
    parse_setup_response,
    total_display_message,
)


class EC4ProtocolTests(unittest.TestCase):
    def test_setup_request(self):
        self.assertEqual(SETUP_REQUEST.hex(" "), "f0 00 00 00 4e 20 10 f7")

    def test_setup_response(self):
        raw = bytes.fromhex("f0 00 00 00 4e 2c 1b 4e 28 1e 4e 24 13 f7")
        state = parse_setup_response(raw)
        self.assertIsNotNone(state)
        self.assertEqual((state.setup, state.group), (14, 3))
        self.assertIn(state.setup, SUPPORTED_DISPLAY_SETUPS)
        self.assertIn(state.group, SUPPORTED_DISPLAY_GROUPS)

    def test_shift_push_button(self):
        raw = bytes.fromhex("f0 00 00 00 4e 2c 1b 4e 2a 19 4e 2e 11 f7")
        event = parse_button_sysex(raw)
        self.assertIsNotNone(event)
        self.assertEqual((event.kind, event.index, event.pressed), ("shift_push", 9, True))

    def test_macro_map_and_feedback(self):
        self.assertEqual(macro_index(12, 48), 0)
        self.assertEqual(macro_index(13, 80), 15)
        self.assertEqual(feedback_cc(15, 1.0), (13, 80, 127))

    def test_display_messages_are_framed_and_expected_length(self):
        main = main_display_message([f"P{i + 1}" for i in range(16)])
        total = total_display_message(["Plugin", "Parametre", "Valeur", "Banque"])
        grid = parameter_grid_message([f"P{i + 1}" for i in range(16)])
        self.assertEqual((main[0], main[-1], len(main)), (0xF0, 0xF7, 206))
        self.assertEqual((total[0], total[-1], len(total)), (0xF0, 0xF7, 257))
        self.assertEqual((grid[0], grid[-1], len(grid)), (0xF0, 0xF7, 257))


if __name__ == "__main__":
    unittest.main()
