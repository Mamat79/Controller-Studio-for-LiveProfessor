import unittest

from ec4lpbridge.osc_codec import OSCError, decode_message, encode_message


class OSCCodecTests(unittest.TestCase):
    def test_round_trip_supported_types(self):
        packet = encode_message("/test", [42, 0.5, "texte", True, False, None, b"abc"])
        address, values = decode_message(packet)
        self.assertEqual(address, "/test")
        self.assertEqual(values[0], 42)
        self.assertAlmostEqual(values[1], 0.5)
        self.assertEqual(values[2:], ["texte", True, False, None, b"abc"])

    def test_address_is_required(self):
        with self.assertRaises(OSCError):
            encode_message("test")


if __name__ == "__main__":
    unittest.main()
