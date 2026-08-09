import unittest

from silemio_control_hub.runtime.plugin_labels import (
    ParameterProfile,
    PluginProfile,
    profile_names,
    short_label,
)


class ProfileTests(unittest.TestCase):
    def test_profile_is_padded_for_plugin_with_fewer_than_16_parameters(self):
        profile = PluginProfile(parameters=[ParameterProfile(name="Gain")])
        names, shorts = profile_names(profile, 16)
        self.assertEqual(len(names), 16)
        self.assertEqual((names[0], shorts[0], names[15]), ("Gain", "Gain", "Parametre 16"))

    def test_long_and_punctuated_names_get_four_character_label(self):
        self.assertEqual(short_label("Fréquence (Hz)"), "Fréq")
        self.assertEqual(short_label("---", 4), "P005")


if __name__ == "__main__":
    unittest.main()
