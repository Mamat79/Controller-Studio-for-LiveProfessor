from __future__ import annotations

import hashlib
import io

import pytest

from silemio_control_hub.application_update import (
    ApplicationUpdateError,
    NoCompatibleRelease,
    download_update,
    is_newer_version,
    launch_installer,
    parse_release,
)


def _release_payload(*assets):
    return {
        "tag_name": "v0.3.0",
        "name": "Controller Studio 0.3.0",
        "body": "AutoMap improvements",
        "html_url": (
            "https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/tag/v0.3.0"
        ),
        "draft": False,
        "prerelease": False,
        "assets": list(assets),
    }


def _asset(name: str, data: bytes, *, digest: str | None = None):
    result = {
        "name": name,
        "browser_download_url": (
            "https://github.com/Mamat79/EC4-LiveProfessor-Bridge/releases/download/"
            f"v0.3.0/{name}"
        ),
        "size": len(data),
    }
    if digest is not None:
        result["digest"] = digest
    return result


class _Response(io.BytesIO):
    def __init__(self, data: bytes, url: str):
        super().__init__(data)
        self._url = url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False

    def geturl(self):
        return self._url


def test_version_comparison_treats_the_stable_build_as_newer_than_same_dev_build():
    assert is_newer_version("0.3.0", "0.3.0.dev0")
    assert is_newer_version("2026.1", "0.3.0")
    assert not is_newer_version("0.3.0", "0.3.0")


def test_release_parser_accepts_only_controller_studio_installer_with_sha256():
    data = b"verified installer"
    digest = hashlib.sha256(data).hexdigest()
    release = parse_release(
        _release_payload(
            _asset(
                "Controller-Studio-for-LiveProfessor-Setup-v0.3.0.exe",
                data,
                digest=f"sha256:{digest}",
            )
        )
    )

    assert release.version == "0.3.0"
    assert release.installer.sha256 == digest.upper()


def test_old_ec4_bridge_release_is_never_offered_as_controller_studio_update():
    with pytest.raises(NoCompatibleRelease):
        parse_release(
            _release_payload(
                _asset("EC4-LiveProfessor-Bridge-Setup-v2026.1.exe", b"legacy")
            )
        )


def test_download_is_published_only_after_size_and_hash_validation(tmp_path):
    data = b"verified installer payload"
    digest = hashlib.sha256(data).hexdigest()
    release = parse_release(
        _release_payload(
            _asset(
                "Controller-Studio-for-LiveProfessor-Setup-v0.3.0.exe",
                data,
                digest=f"sha256:{digest}",
            )
        )
    )

    def opener(request, **_kwargs):
        return _Response(data, request.full_url)

    result = download_update(release, tmp_path, opener=opener)

    assert result.path.read_bytes() == data
    assert result.sha256 == digest.upper()
    assert not list(tmp_path.glob("*.partial"))


def test_download_rejects_tampering_and_removes_partial_file(tmp_path):
    expected = b"expected installer"
    tampered = b"tampered installer"
    digest = hashlib.sha256(expected).hexdigest()
    raw = _asset(
        "Controller-Studio-for-LiveProfessor-Setup-v0.3.0.exe",
        tampered,
        digest=f"sha256:{digest}",
    )
    release = parse_release(_release_payload(raw))

    def opener(request, **_kwargs):
        return _Response(tampered, request.full_url)

    with pytest.raises(ApplicationUpdateError, match="empreinte SHA-256"):
        download_update(release, tmp_path, opener=opener)
    assert not list(tmp_path.iterdir())


def test_checksum_sidecar_is_used_when_github_digest_is_absent(tmp_path):
    data = b"installer verified by sidecar"
    digest = hashlib.sha256(data).hexdigest()
    installer_name = "Controller-Studio-for-LiveProfessor-Setup-v0.3.0.exe"
    release = parse_release(
        _release_payload(
            _asset(installer_name, data),
            _asset(f"{installer_name}.sha256", f"{digest}  {installer_name}\n".encode()),
        )
    )

    def opener(request, **_kwargs):
        if request.full_url.endswith(".sha256"):
            payload = f"{digest}  {installer_name}\n".encode()
        else:
            payload = data
        return _Response(payload, request.full_url)

    result = download_update(release, tmp_path, opener=opener)

    assert result.sha256 == digest.upper()


def test_release_parser_rejects_a_malformed_asset_collection():
    payload = _release_payload()
    payload["assets"] = None

    with pytest.raises(ApplicationUpdateError, match="liste des fichiers"):
        parse_release(payload)


def test_installer_launcher_rejects_unexpected_executable_name(tmp_path):
    executable = tmp_path / "random.exe"
    executable.write_bytes(b"not an installer")
    with pytest.raises(ApplicationUpdateError, match="invalide"):
        launch_installer(executable, lambda _path: None)
