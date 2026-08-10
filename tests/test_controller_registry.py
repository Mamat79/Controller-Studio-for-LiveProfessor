import json
import hashlib
from pathlib import PurePosixPath

import pytest

from silemio_control_hub.models import ProfileError
from silemio_control_hub.library import LibraryManifest
from silemio_control_hub.library_remote import update_library
from silemio_control_hub.registry import ControllerRegistry


def test_builtin_profiles_are_valid_and_distinct():
    registry = ControllerRegistry()
    profiles = registry.all()
    assert {profile.id for profile in profiles} == {
        "behringer.x-touch-compact.layer-a",
        "behringer.x-touch-mini.preset-a",
        "behringer.x-touch-one.midi",
        "dj-techtools.midi-fighter-twister.factory-banks-1-4",
        "faderfox.ec4",
        "faderfox.pc12.setup-1",
        "faderfox.pc4.setup-1",
        "faderfox.uc4.setup-1-group-1",
        "generic.midi.16",
        "novation.launch-control-xl3.mode-16",
    }
    ec4 = registry.get("faderfox.ec4")
    assert ec4.bank_size == 16
    assert len(ec4.controls) == 16
    assert all(control.supports_rotation for control in ec4.controls)
    assert all(control.supports_press for control in ec4.controls)

    compact = registry.get("behringer.x-touch-compact.layer-a")
    assert compact.bank_size == 25
    assert sum(control.supports_rotation for control in compact.controls) == 25
    assert sum(control.supports_press for control in compact.controls) == 16
    assert compact.status == "community"

    launch_control = registry.get("novation.launch-control-xl3.mode-16")
    assert launch_control.bank_size == 48
    assert sum(control.supports_rotation for control in launch_control.controls) == 32
    assert sum(control.supports_press for control in launch_control.controls) == 16

    pc4 = registry.get("faderfox.pc4.setup-1")
    assert pc4.bank_size == 24
    assert sum(control.supports_rotation for control in pc4.controls) == 24
    assert sum(control.supports_press for control in pc4.controls) == 0

    uc4 = registry.get("faderfox.uc4.setup-1-group-1")
    assert uc4.bank_size == 25
    assert sum(control.supports_rotation for control in uc4.controls) == 17
    assert sum(control.supports_press for control in uc4.controls) == 16

    pc12 = registry.get("faderfox.pc12.setup-1")
    assert pc12.bank_size == 85
    assert sum(control.supports_rotation for control in pc12.controls) == 73
    assert sum(control.supports_press for control in pc12.controls) == 13

    twister = registry.get("dj-techtools.midi-fighter-twister.factory-banks-1-4")
    assert twister.bank_size == 16
    assert twister.bank_count == 4
    assert len(twister.controls) == 64
    assert all(control.supports_rotation for control in twister.controls)
    assert all(control.supports_press for control in twister.controls)


def test_duplicate_control_ids_are_rejected(tmp_path):
    profile = {
        "schema_version": 1,
        "id": "test.duplicate",
        "manufacturer": "Test",
        "model": "Duplicate",
        "bank_size": 1,
        "controls": [
            {"id": "same", "kind": "button", "input": {"message": "note", "channel": 1, "number": 1}},
            {"id": "same", "kind": "button", "input": {"message": "note", "channel": 1, "number": 2}}
        ]
    }
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(ProfileError, match="uniques"):
        ControllerRegistry.load_file(path)


class _RemoteControllerLibrary:
    repository = "test/library"
    ref = "main"

    def __init__(self, profile):
        self.payload = json.dumps(profile, sort_keys=True).encode("utf-8")
        self.path = PurePosixPath(
            f"controllers/test/remote/{profile['profile_version']}/profile.json"
        )
        self.raw = {
            "manifest_version": 1,
            "generated_at": "2026-08-09T22:00:00Z",
            "profiles": [
                {
                    "id": profile["id"],
                    "version": profile["profile_version"],
                    "status": profile["status"],
                    "path": self.path.as_posix(),
                    "sha256": hashlib.sha256(self.payload).hexdigest(),
                }
            ],
            "plugin_profiles": [],
        }

    def fetch_manifest(self):
        return LibraryManifest.from_dict(self.raw), json.dumps(self.raw).encode("utf-8")

    def fetch_profile(self, path):
        assert path == self.path
        return self.payload


def _remote_controller(model="Remote Controller", version="1.0.0"):
    return {
        "schema_version": 1,
        "profile_version": version,
        "id": "test.remote-controller",
        "manufacturer": "Test",
        "model": model,
        "bank_size": 1,
        "status": "community",
        "capabilities": ["commands"],
        "controls": [
            {
                "id": "knob",
                "kind": "absolute_encoder",
                "input": {"message": "cc", "channel": 1, "number": 7},
            }
        ],
    }


def test_registry_automatically_uses_the_validated_cached_library(tmp_path):
    cache = tmp_path / "cache"
    update_library(
        _RemoteControllerLibrary(_remote_controller()),
        cache_root=cache,
        apply=True,
    )

    registry = ControllerRegistry(profile_directories=[], library_cache_root=cache)

    assert registry.get("test.remote-controller").model == "Remote Controller"
    assert "current" in registry.source("test.remote-controller").parts


def test_local_user_profile_overrides_the_cached_community_profile(tmp_path):
    cache = tmp_path / "cache"
    user = tmp_path / "user"
    user.mkdir()
    update_library(
        _RemoteControllerLibrary(_remote_controller()),
        cache_root=cache,
        apply=True,
    )
    local = _remote_controller(model="My Local Controller", version="1.1.0")
    (user / "local.json").write_text(json.dumps(local), encoding="utf-8")

    registry = ControllerRegistry(
        profile_directories=[user],
        library_cache_root=cache,
    )

    assert registry.get("test.remote-controller").model == "My Local Controller"
    assert registry.source("test.remote-controller") == user / "local.json"


def test_cache_environment_override_is_used_by_the_default_registry(tmp_path, monkeypatch):
    cache = tmp_path / "isolated-cache"
    update_library(
        _RemoteControllerLibrary(_remote_controller()),
        cache_root=cache,
        apply=True,
    )
    monkeypatch.setenv("SILEMIO_LIBRARY_CACHE", str(cache))

    registry = ControllerRegistry(profile_directories=[])

    assert registry.get("test.remote-controller").model == "Remote Controller"
