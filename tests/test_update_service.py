import json
import unittest
from unittest.mock import patch

from ec4lpbridge.update_service import (
    fetch_latest_release,
    is_newer_version,
    parse_release,
    version_tuple,
)


class UpdateServiceTests(unittest.TestCase):
    def release(self, **changes):
        payload = {
            "tag_name": "v0.5.0",
            "name": "EC4 Bridge 0.5.0",
            "body": "Corrections",
            "html_url": (
                "https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/tag/v0.5.0"
            ),
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": "EC4-LiveProfessor-Bridge-Setup-v0.5.0.exe",
                    "browser_download_url": (
                        "https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/download/"
                        "v0.5.0/EC4-LiveProfessor-Bridge-Setup-v0.5.0.exe"
                    ),
                    "size": 42,
                }
            ],
        }
        payload.update(changes)
        return payload

    def test_version_comparison(self):
        self.assertEqual(version_tuple("v1.2"), (1, 2, 0, 0))
        self.assertTrue(is_newer_version("0.5.0", "0.4.1"))
        self.assertFalse(is_newer_version("v0.5.0", "0.5.0"))

    def test_parse_release_prefers_setup(self):
        release = parse_release(self.release())
        self.assertEqual(release.version, "0.5.0")
        self.assertTrue(release.asset_name.endswith(".exe"))

    def test_prerelease_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_release(self.release(prerelease=True))

    def test_network_failure_is_reported_without_real_internet(self):
        with patch("ec4lpbridge.update_service.urlopen", side_effect=OSError("offline")):
            with self.assertRaisesRegex(OSError, "offline"):
                fetch_latest_release()

    def test_fetch_uses_mocked_github_response(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps(self_payload).encode("utf-8")

        self_payload = self.release()
        with patch("ec4lpbridge.update_service.urlopen", return_value=FakeResponse()):
            self.assertEqual(fetch_latest_release().version, "0.5.0")


if __name__ == "__main__":
    unittest.main()
