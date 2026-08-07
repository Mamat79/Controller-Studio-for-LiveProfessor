import tempfile
import unittest
from pathlib import Path

from ec4lpbridge.config import BridgeConfig, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_configuration_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            original = BridgeConfig(
                mode="generic",
                max_controls=32,
                plugin_label="Test",
                target_setup=9,
                target_group=13,
                encoder_mappings={
                    "9:13": [
                        {
                            "channel": 3,
                            "control": 40 + index,
                            "push_channel": 4,
                            "push_note": 70 + index,
                        }
                        for index in range(16)
                    ]
                },
            )
            save_config(original, path)
            restored = load_config(path)
            self.assertEqual(
                (
                    restored.mode,
                    restored.max_controls,
                    restored.plugin_label,
                    restored.target_setup,
                    restored.target_group,
                    len(restored.encoder_mappings["9:13"]),
                ),
                ("generic", 32, "Test", 9, 13, 16),
            )

    def test_unknown_fields_survive_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text('{"mode":"companion","future_option":42}', encoding="utf-8")
            config = load_config(path)
            save_config(config, path)
            self.assertEqual(load_config(path).extra["future_option"], 42)


if __name__ == "__main__":
    unittest.main()
