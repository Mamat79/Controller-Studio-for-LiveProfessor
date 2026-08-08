import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ec4lpbridge.app import (
    controller_template_path,
    copy_controller_template,
    open_liveprofessor_project,
    tray_action_for_event,
)


class AppHelperTests(unittest.TestCase):
    def test_tray_clicks_never_map_to_quit(self):
        self.assertEqual(tray_action_for_event(0x0202), "open")
        self.assertEqual(tray_action_for_event(0x0203), "open")
        self.assertEqual(tray_action_for_event(0x0205), "menu")
        self.assertIsNone(tray_action_for_event(0x0201))

    def test_windows_packed_tray_events_are_decoded_from_low_word(self):
        icon_id = 1 << 16
        self.assertEqual(tray_action_for_event(icon_id | 0x0202), "open")
        self.assertEqual(tray_action_for_event(icon_id | 0x0203), "open")
        self.assertEqual(tray_action_for_event(icon_id | 0x0205), "menu")
        self.assertEqual(tray_action_for_event(icon_id | 0x007B), "menu")
        self.assertIsNone(tray_action_for_event(icon_id | 0x0201))
        self.assertIsNone(tray_action_for_event(3007))

    def test_controller_template_can_be_located_and_copied(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "bundled" / "Ec4-FullBank.ctrl2"
            source.parent.mkdir()
            source.write_bytes(b"neutral-controller")
            located = controller_template_path(
                "Ec4-FullBank.ctrl2",
                candidates=[root / "missing.ctrl2", source],
            )
            destination = root / "export"
            destination.mkdir()

            copied = copy_controller_template(destination, source=located)

            expected = destination / "Ec4-FullBank.ctrl2"
            self.assertEqual(copied, expected.resolve())
            self.assertEqual(expected.read_bytes(), b"neutral-controller")

    def test_unknown_controller_template_is_rejected(self):
        with self.assertRaises(ValueError):
            controller_template_path("Unknown.ctrl2", candidates=[])

    def test_generated_project_uses_registered_windows_launcher(self):
        with TemporaryDirectory() as temporary:
            project = Path(temporary) / "mapped.rack2"
            project.write_bytes(b"project")
            opened: list[str] = []

            result = open_liveprofessor_project(project, launcher=opened.append)

            self.assertEqual(result, project.resolve())
            self.assertEqual(opened, [str(project.resolve())])

    def test_missing_generated_project_is_not_launched(self):
        with TemporaryDirectory() as temporary:
            opened: list[str] = []
            with self.assertRaises(FileNotFoundError):
                open_liveprofessor_project(
                    Path(temporary) / "missing.rack2",
                    launcher=opened.append,
                )
            self.assertEqual(opened, [])


if __name__ == "__main__":
    unittest.main()
