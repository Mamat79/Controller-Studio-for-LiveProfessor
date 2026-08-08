import unittest

from ec4lpbridge.app import tray_action_for_event


class AppHelperTests(unittest.TestCase):
    def test_tray_clicks_never_map_to_quit(self):
        self.assertEqual(tray_action_for_event(0x0202), "open")
        self.assertEqual(tray_action_for_event(0x0203), "open")
        self.assertEqual(tray_action_for_event(0x0205), "menu")
        self.assertIsNone(tray_action_for_event(0x0201))


if __name__ == "__main__":
    unittest.main()
