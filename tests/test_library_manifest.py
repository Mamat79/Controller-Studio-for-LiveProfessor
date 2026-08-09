import hashlib
import json

import pytest

from silemio_control_hub.library import (
    LibraryError,
    LibraryManifest,
    validate_library,
    validate_plugin_library,
)
from silemio_control_hub.cli import main
from silemio_control_hub.plugin_profiles import PluginObservation


def _profile():
    return {
        "schema_version": 1,
        "profile_version": "1.2.0",
        "id": "community.test-controller",
        "manufacturer": "Community",
        "model": "Test Controller",
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
    }


def _library(tmp_path, *, mutate_manifest=None, mutate_profile=None):
    root = tmp_path / "library"
    source = root / "controllers" / "community" / "test" / "1.2.0" / "profile.json"
    source.parent.mkdir(parents=True)
    profile = _profile()
    if mutate_profile:
        mutate_profile(profile)
    payload = json.dumps(profile, ensure_ascii=False, indent=2).encode("utf-8")
    source.write_bytes(payload)
    entry = {
        "id": "community.test-controller",
        "version": "1.2.0",
        "status": "community",
        "path": "controllers/community/test/1.2.0/profile.json",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "minimum_hub_version": "0.1.0",
    }
    manifest = {
        "manifest_version": 1,
        "generated_at": "2026-08-09T18:00:00Z",
        "profiles": [entry],
    }
    if mutate_manifest:
        mutate_manifest(manifest)
    manifest_path = root / "manifest-v1.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return root, manifest_path


def _plugin_library(tmp_path, *, mutate_manifest=None, mutate_profile=None):
    root = tmp_path / "library"
    source = root / "plugin-profiles" / "test" / "compressor" / "1.0.0" / "profile.json"
    source.parent.mkdir(parents=True)
    observation = PluginObservation.from_parameter_count(
        plugin_format="VST3",
        stable_id="VST3-Test Compressor-b86068d4-ca0ebedb",
        name="Test Compressor",
        parameter_count=2,
    )
    profile = {
        "schema_version": 1,
        "profile_version": "1.0.0",
        "id": "test.compressor",
        "status": "community",
        "layer": "suggested",
        "plugin_name": "Test Compressor",
        "manufacturer": "Test",
        "identity": {
            "format": "VST3",
            "stable_id": observation.stable_id,
            "parameter_fingerprint": observation.parameter_fingerprint,
        },
        "parameters": [
            {
                "stable_id": "index:0",
                "name": "Input",
                "short_label": "IN",
                "role": "input_gain",
                "importance": 90,
            }
        ],
    }
    if mutate_profile:
        mutate_profile(profile)
    payload = json.dumps(profile, ensure_ascii=False, indent=2).encode("utf-8")
    source.write_bytes(payload)
    manifest = {
        "manifest_version": 1,
        "generated_at": "2026-08-09T19:00:00Z",
        "profiles": [],
        "plugin_profiles": [
            {
                "id": "test.compressor",
                "version": "1.0.0",
                "status": "community",
                "path": "plugin-profiles/test/compressor/1.0.0/profile.json",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "minimum_hub_version": "0.1.0",
            }
        ],
    }
    if mutate_manifest:
        mutate_manifest(manifest)
    manifest_path = root / "manifest-v1.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return root, manifest_path


def test_library_manifest_validates_hash_profile_and_metadata(tmp_path):
    root, manifest_path = _library(tmp_path)
    manifest = LibraryManifest.load_file(manifest_path)
    validated = validate_library(root, manifest)
    assert len(validated) == 1
    assert validated[0].profile.id == "community.test-controller"
    assert validated[0].profile.profile_version == "1.2.0"


def test_library_manifest_rejects_path_traversal(tmp_path):
    root, manifest_path = _library(
        tmp_path,
        mutate_manifest=lambda manifest: manifest["profiles"][0].update(
            {"path": "../outside.json"}
        ),
    )
    with pytest.raises(LibraryError, match="relatif au dépôt"):
        LibraryManifest.load_file(manifest_path)


def test_library_validation_rejects_hash_mismatch(tmp_path):
    root, manifest_path = _library(
        tmp_path,
        mutate_manifest=lambda manifest: manifest["profiles"][0].update(
            {"sha256": "0" * 64}
        ),
    )
    manifest = LibraryManifest.load_file(manifest_path)
    with pytest.raises(LibraryError, match="SHA-256 incorrect"):
        validate_library(root, manifest)


def test_library_validation_rejects_executable_or_unknown_profile_fields(tmp_path):
    root, manifest_path = _library(
        tmp_path,
        mutate_profile=lambda profile: profile.update({"executable": "payload.py"}),
    )
    manifest = LibraryManifest.load_file(manifest_path)
    with pytest.raises(LibraryError, match="champs inconnus: executable"):
        validate_library(root, manifest)


def test_library_validation_rejects_manifest_profile_version_mismatch(tmp_path):
    root, manifest_path = _library(
        tmp_path,
        mutate_manifest=lambda manifest: manifest["profiles"][0].update(
            {"version": "2.0.0"}
        ),
    )
    manifest = LibraryManifest.load_file(manifest_path)
    with pytest.raises(LibraryError, match="version incohérente"):
        validate_library(root, manifest)


def test_library_manifest_validates_shared_suggested_plugin_profiles(tmp_path):
    root, manifest_path = _plugin_library(tmp_path)
    manifest = LibraryManifest.load_file(manifest_path)

    validated = validate_plugin_library(root, manifest)

    assert len(validated) == 1
    assert validated[0].profile.id == "test.compressor"
    assert validated[0].profile.layer.value == "suggested"


def test_shared_library_rejects_user_plugin_profiles(tmp_path):
    root, manifest_path = _plugin_library(
        tmp_path,
        mutate_profile=lambda profile: profile.update({"layer": "user"}),
    )
    manifest = LibraryManifest.load_file(manifest_path)

    with pytest.raises(LibraryError, match="profil de plug-in invalide"):
        validate_plugin_library(root, manifest)


def test_manifest_rejects_duplicate_paths_across_controller_and_plugin_profiles(tmp_path):
    root, manifest_path = _plugin_library(
        tmp_path,
        mutate_manifest=lambda manifest: manifest["profiles"].append(
            dict(manifest["plugin_profiles"][0])
        ),
    )

    with pytest.raises(LibraryError, match="chemins dupliqués"):
        LibraryManifest.load_file(manifest_path)


def test_validate_library_cli_reports_controller_and_plugin_counts(tmp_path, capsys):
    root, _manifest_path = _plugin_library(tmp_path)

    exit_code = main(["validate-library", str(root)])

    assert exit_code == 0
    assert "0 contrôleur(s), 1 plug-in(s)" in capsys.readouterr().out
