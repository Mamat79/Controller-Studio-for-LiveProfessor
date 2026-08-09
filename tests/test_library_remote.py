import base64
import hashlib
import json
from pathlib import PurePosixPath

import pytest

from silemio_control_hub.library import LibraryManifest
from silemio_control_hub.library_remote import (
    GitHubLibraryClient,
    LibraryRemoteError,
    list_library_backups,
    rollback_library,
    update_library,
)


def _controller_payload(version="1.0.0", *, model="Test Controller"):
    return (
        json.dumps(
            {
                "schema_version": 1,
                "profile_version": version,
                "id": "community.test-controller",
                "manufacturer": "Community",
                "model": model,
                "bank_size": 1,
                "status": "community",
                "capabilities": ["commands"],
                "controls": [
                    {
                        "id": "knob",
                        "kind": "absolute_encoder",
                        "input": {"message": "cc", "channel": 1, "number": 1},
                    }
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _remote(
    version="1.0.0",
    *,
    model="Test Controller",
    sha_override=None,
    minimum_hub_version="0.1.0",
):
    path = PurePosixPath(
        f"controllers/community/test-controller/{version}/profile.json"
    )
    payload = _controller_payload(version, model=model)
    manifest_raw = {
        "manifest_version": 1,
        "generated_at": "2026-08-09T20:00:00Z",
        "profiles": [
            {
                "id": "community.test-controller",
                "version": version,
                "status": "community",
                "path": path.as_posix(),
                "sha256": sha_override
                or hashlib.sha256(payload).hexdigest().upper(),
                "minimum_hub_version": minimum_hub_version,
            }
        ],
        "plugin_profiles": [],
    }
    return FakeRemote(manifest_raw, {path: payload})


class FakeRemote:
    repository = "example/library"
    ref = "main"

    def __init__(self, manifest_raw, files):
        self.manifest_raw = manifest_raw
        self.files = files

    def fetch_manifest(self):
        payload = json.dumps(self.manifest_raw).encode("utf-8")
        return LibraryManifest.from_dict(self.manifest_raw), payload

    def fetch_profile(self, path):
        return self.files[path]


def _empty_remote():
    return FakeRemote(
        {
            "manifest_version": 1,
            "generated_at": "2026-08-09T21:00:00Z",
            "profiles": [],
            "plugin_profiles": [],
        },
        {},
    )


def test_update_is_preview_only_by_default_and_does_not_create_cache(tmp_path):
    cache = tmp_path / "cache"

    result = update_library(_remote(), cache_root=cache)

    assert result.applied is False
    assert [(change.kind, change.id) for change in result.preview.changes] == [
        ("new", "community.test-controller")
    ]
    assert not cache.exists()


def test_apply_validates_downloads_and_installs_the_remote_library(tmp_path):
    cache = tmp_path / "cache"

    result = update_library(_remote(), cache_root=cache, apply=True)

    assert result.applied is True
    assert result.backup_path is None
    installed = LibraryManifest.load_file(cache / "current" / "manifest-v1.json")
    assert installed.profiles[0].version == "1.0.0"
    assert (
        cache
        / "current"
        / "controllers"
        / "community"
        / "test-controller"
        / "1.0.0"
        / "profile.json"
    ).is_file()


def test_update_creates_a_restorable_backup_and_rollback_preserves_both_states(tmp_path):
    cache = tmp_path / "cache"
    update_library(_remote("1.0.0"), cache_root=cache, apply=True)
    updated = update_library(_remote("2.0.0"), cache_root=cache, apply=True)

    assert updated.backup_path is not None
    backup_name = updated.backup_path.name
    assert backup_name in list_library_backups(cache)
    preview = rollback_library(backup_name, cache_root=cache)
    assert preview.applied is False
    assert any(change.kind == "downgrade" for change in preview.preview.changes)

    restored = rollback_library(backup_name, cache_root=cache, apply=True)

    assert restored.applied is True
    current = LibraryManifest.load_file(cache / "current" / "manifest-v1.json")
    assert current.profiles[0].version == "1.0.0"
    assert any(name.startswith("pre-rollback-") for name in list_library_backups(cache))


def test_same_version_with_changed_content_is_rejected_as_immutable(tmp_path):
    cache = tmp_path / "cache"
    update_library(_remote(), cache_root=cache, apply=True)

    with pytest.raises(LibraryRemoteError, match="versions de bibliothèque.*immuables"):
        update_library(
            _remote(model="Changed without version bump"),
            cache_root=cache,
        )

    current = LibraryManifest.load_file(cache / "current" / "manifest-v1.json")
    assert current.profiles[0].version == "1.0.0"


def test_hash_mismatch_never_installs_a_partial_library(tmp_path):
    cache = tmp_path / "cache"

    with pytest.raises(LibraryRemoteError, match="SHA-256 distant incorrect"):
        update_library(
            _remote(sha_override="0" * 64),
            cache_root=cache,
            apply=True,
        )

    assert not (cache / "current").exists()
    assert not list(cache.glob(".staging-*"))


def test_remote_removal_requires_a_second_explicit_authorization(tmp_path):
    cache = tmp_path / "cache"
    update_library(_remote(), cache_root=cache, apply=True)

    with pytest.raises(LibraryRemoteError, match="retirerait des profils"):
        update_library(_empty_remote(), cache_root=cache, apply=True)

    result = update_library(
        _empty_remote(),
        cache_root=cache,
        apply=True,
        allow_removals=True,
    )
    assert result.applied is True
    assert LibraryManifest.load_file(
        cache / "current" / "manifest-v1.json"
    ).profiles == ()


def test_update_rejects_profiles_that_require_a_newer_hub(tmp_path):
    cache = tmp_path / "cache"

    with pytest.raises(LibraryRemoteError, match="exige Hub 9.0.0"):
        update_library(
            _remote(minimum_hub_version="9.0.0"),
            cache_root=cache,
            apply=True,
            hub_version="0.1.0.dev0",
        )

    assert not cache.exists()


def test_corrupted_current_cache_is_rejected_before_network_changes_are_applied(tmp_path):
    cache = tmp_path / "cache"
    update_library(_remote(), cache_root=cache, apply=True)
    profile = next((cache / "current" / "controllers").glob("**/profile.json"))
    profile.write_bytes(b"corrupted")

    with pytest.raises(LibraryRemoteError, match="bibliothèque locale invalide"):
        update_library(_remote("2.0.0"), cache_root=cache, apply=True)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size):
        return self.payload[:_size]


def test_github_client_uses_token_header_and_decodes_content_api_base64():
    manifest = {
        "manifest_version": 1,
        "generated_at": "2026-08-09T20:00:00Z",
        "profiles": [],
        "plugin_profiles": [],
    }
    encoded = base64.b64encode(json.dumps(manifest).encode("utf-8")).decode("ascii")
    response = json.dumps({"encoding": "base64", "content": encoded}).encode("utf-8")
    requests = []

    def opener(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(response)

    client = GitHubLibraryClient(
        "owner/library",
        "main",
        token="secret-token",
        opener=opener,
    )

    parsed, _payload = client.fetch_manifest()

    assert parsed.profiles == ()
    assert requests[0][0].get_header("Authorization") == "Bearer secret-token"
    assert requests[0][1] == 15.0


def test_content_api_wrapper_can_be_larger_than_the_decoded_profile_limit():
    decoded = b"x" * 2_000
    encoded = base64.b64encode(decoded).decode("ascii")
    response = json.dumps({"encoding": "base64", "content": encoded}).encode("utf-8")

    client = GitHubLibraryClient(
        "owner/library",
        opener=lambda _request, timeout: FakeResponse(response),
    )

    assert client._fetch(PurePosixPath("profile.json"), limit=len(decoded)) == decoded
