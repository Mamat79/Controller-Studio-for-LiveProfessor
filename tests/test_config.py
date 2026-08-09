import tempfile
import unittest
from pathlib import Path

import silemio_control_hub.runtime.config as runtime_config
from silemio_control_hub.runtime.config import (
    BridgeConfig,
    default_data_dir,
    load_config,
    save_config,
)


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
                parameter_overlay_interval_ms=150,
                companion_refresh_delay_ms=300,
                name_refresh_delay_ms=90,
                feedback_confirm_timeout_ms=1200,
                overlay_display_duration_ms=900,
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
            self.assertFalse(list(Path(folder).glob(".*.tmp")))
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
            self.assertEqual(
                (
                    restored.parameter_overlay_interval_ms,
                    restored.companion_refresh_delay_ms,
                    restored.name_refresh_delay_ms,
                    restored.feedback_confirm_timeout_ms,
                    restored.overlay_display_duration_ms,
                ),
                (150, 300, 90, 1200, 900),
            )

    def test_unknown_fields_survive_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text('{"mode":"companion","future_option":42}', encoding="utf-8")
            config = load_config(path)
            save_config(config, path)
            self.assertEqual(load_config(path).extra["future_option"], 42)

    def test_legacy_cue_commands_are_migrated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(
                "{"
                "\"mode\":\"companion\","
                "\"cue_previous_command\":\"/Command/CueList/RecallPreviousCue\","
                "\"cue_next_command\":\"/Command/CueList/RecallNextCue\""
                "}",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(
                (
                    config.cue_previous_command,
                    config.cue_next_command,
                ),
                (
                    "/Command/CueLists/FirePreviousCue",
                    "/Command/CueLists/FireNextCue",
                ),
            )

    def test_legacy_show_hide_and_enable_paths_are_migrated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(
                "{"
                "\"mode\":\"companion\","
                "\"show_hide_command\":\"/Command/PluginWindows/ShowHideSelectedPlugin\","
                "\"enable_processing_command\":\"/Command/SelectedPlugin/EnableProcessingOnSelectedPlugin\""
                "}",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.show_hide_command, "/Command/PluginWindows/ShowHideselectedplugin")
            self.assertEqual(
                config.enable_processing_command,
                "/Command/SelectedPlugin/EnableProcessingonselectedplugin",
            )

    def test_product_data_directory_uses_controller_studio_name(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = runtime_config.os.environ.get("SILEMIO_LOCAL_APP_DATA")
            runtime_config.os.environ["SILEMIO_LOCAL_APP_DATA"] = folder
            try:
                self.assertEqual(
                    default_data_dir(),
                    Path(folder) / "Controller Studio for LiveProfessor",
                )
            finally:
                if previous is None:
                    runtime_config.os.environ.pop("SILEMIO_LOCAL_APP_DATA", None)
                else:
                    runtime_config.os.environ["SILEMIO_LOCAL_APP_DATA"] = previous

    def test_legacy_bridge_config_is_read_only_migration_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            product = root / "runtime-config.json"
            legacy = root / "legacy-config.json"
            original = '{"target_setup":9,"target_group":13}\n'
            legacy.write_text(original, encoding="utf-8")
            previous_default = runtime_config.default_config_path
            previous_product = runtime_config.previous_product_config_path
            previous_legacy = runtime_config.legacy_config_path
            runtime_config.default_config_path = lambda: product
            runtime_config.previous_product_config_path = lambda: root / "missing.json"
            runtime_config.legacy_config_path = lambda: legacy
            try:
                config = load_config()
                save_config(config)
            finally:
                runtime_config.default_config_path = previous_default
                runtime_config.previous_product_config_path = previous_product
                runtime_config.legacy_config_path = previous_legacy
            self.assertEqual((config.target_setup, config.target_group), (9, 13))
            self.assertEqual(legacy.read_text(encoding="utf-8"), original)
            self.assertTrue(product.is_file())


if __name__ == "__main__":
    unittest.main()
