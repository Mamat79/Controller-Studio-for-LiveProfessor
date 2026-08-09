import hashlib
import json
from pathlib import PurePosixPath

import pytest

from silemio_control_hub.library import LibraryManifest
from silemio_control_hub.library_remote import update_library
from silemio_control_hub.plugin_profiles import (
    PluginObservation,
    PluginProfileError,
    PluginProfileLayer,
    PluginProfileResolver,
)
from silemio_control_hub.plugin_registry import PluginProfileRegistry


def _observation():
    return PluginObservation.from_parameter_count(
        plugin_format="VST3",
        stable_id="VST3-Test-b86068d4-ca0ebedb",
        name="Test Plugin",
        parameter_count=2,
    )


def _profile(observation, *, layer="suggested", name="Shared Input"):
    return {
        "schema_version": 1,
        "profile_version": "1.0.0",
        "id": "test.plugin" if layer == "suggested" else "local.test-plugin",
        "status": "community" if layer == "suggested" else "local",
        "layer": layer,
        "plugin_name": observation.name,
        "identity": {
            "format": observation.plugin_format,
            "stable_id": observation.stable_id,
            "parameter_fingerprint": observation.parameter_fingerprint,
        },
        "parameters": [
            {
                "stable_id": "index:0",
                "name": name,
                "short_label": "INPUT",
                "importance": 90,
            }
        ],
    }


class _RemotePluginLibrary:
    repository = "test/library"
    ref = "main"

    def __init__(self, profile):
        self.payload = json.dumps(profile, sort_keys=True).encode("utf-8")
        self.path = PurePosixPath("plugin-profiles/test/plugin/1.0.0/profile.json")
        self.raw = {
            "manifest_version": 1,
            "generated_at": "2026-08-09T22:00:00Z",
            "profiles": [],
            "plugin_profiles": [
                {
                    "id": profile["id"],
                    "version": profile["profile_version"],
                    "status": profile["status"],
                    "path": self.path.as_posix(),
                    "sha256": hashlib.sha256(self.payload).hexdigest(),
                }
            ],
        }

    def fetch_manifest(self):
        return LibraryManifest.from_dict(self.raw), json.dumps(self.raw).encode("utf-8")

    def fetch_profile(self, path):
        assert path == self.path
        return self.payload


def test_plugin_registry_loads_cached_suggestions_for_offline_resolution(tmp_path):
    observation = _observation()
    cache = tmp_path / "cache"
    update_library(
        _RemotePluginLibrary(_profile(observation)),
        cache_root=cache,
        apply=True,
    )

    registry = PluginProfileRegistry(profile_directories=[], library_cache_root=cache)
    resolved = PluginProfileResolver(registry.all()).resolve(observation)

    assert len(registry.all()) == 1
    assert resolved.layer == PluginProfileLayer.SUGGESTED
    assert resolved.parameters[0].name == "Shared Input"


def test_local_user_plugin_profile_remains_higher_priority_than_cached_suggestion(tmp_path):
    observation = _observation()
    cache = tmp_path / "cache"
    user = tmp_path / "user"
    user.mkdir()
    update_library(
        _RemotePluginLibrary(_profile(observation)),
        cache_root=cache,
        apply=True,
    )
    local_path = user / "test-plugin.json"
    local_path.write_text(
        json.dumps(_profile(observation, layer="user", name="My Input")),
        encoding="utf-8",
    )

    registry = PluginProfileRegistry(
        profile_directories=[user],
        library_cache_root=cache,
    )
    profiles = registry.all()
    resolved = PluginProfileResolver(profiles).resolve(observation)

    assert len(profiles) == 2
    assert resolved.layer == PluginProfileLayer.USER
    assert resolved.parameters[0].name == "My Input"
    local_profile = next(
        profile for profile in profiles if profile.layer == PluginProfileLayer.USER
    )
    assert registry.source(local_profile) == local_path


def test_local_plugin_directory_rejects_a_shared_suggested_layer(tmp_path):
    observation = _observation()
    user = tmp_path / "user"
    user.mkdir()
    (user / "wrong-layer.json").write_text(
        json.dumps(_profile(observation, layer="suggested")),
        encoding="utf-8",
    )

    registry = PluginProfileRegistry(
        profile_directories=[user],
        library_cache_root=tmp_path / "cache",
    )

    with pytest.raises(PluginProfileError, match="profil local.*couche user"):
        registry.all()
