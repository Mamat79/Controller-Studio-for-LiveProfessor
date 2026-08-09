"""GitHub Release updater with strict product and SHA-256 validation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .platform_paths import product_data_dir


# Keep the already-distributed public EC4 Bridge repository URL stable. Once
# Controller Studio is explicitly accepted, that repository can be replaced by
# this independent product and future releases will be discovered here without
# asking existing users to change links.
LATEST_RELEASE_API_URL = (
    "https://api.github.com/repos/Mamat79/EC4-LiveProfessor-Bridge/releases/latest"
)
GITHUB_API_VERSION = "2022-11-28"
MAXIMUM_INSTALLER_BYTES = 512 * 1024 * 1024
INSTALLER_NAME = re.compile(
    r"^(?:Controller-Studio-for-LiveProfessor|"
    r"SiLeMIO-Controller-Studio(?:-for-LiveProfessor)?)-Setup"
    r"(?:-v?\d+(?:\.\d+){1,3})?\.exe$",
    re.IGNORECASE,
)
SHA256_VALUE = re.compile(r"^[0-9a-fA-F]{64}$")
TRUSTED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


class ApplicationUpdateError(RuntimeError):
    pass


class NoCompatibleRelease(ApplicationUpdateError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    name: str
    size: int
    download_url: str
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ApplicationRelease:
    version: str
    title: str
    notes: str
    page_url: str
    installer: ReleaseAsset
    checksum: ReleaseAsset | None


@dataclass(frozen=True, slots=True)
class UpdateDownload:
    release: ApplicationRelease
    path: Path
    sha256: str


def _version_key(value: str) -> tuple[int, int, int, int, int]:
    match = re.fullmatch(
        r"v?(\d+(?:\.\d+){1,3})(?:(?:[.-])(dev|a|alpha|b|beta|rc)(\d*)?)?",
        str(value).strip(),
        re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"version invalide: {value!r}")
    parts = [int(item) for item in match.group(1).split(".")]
    parts.extend([0] * (4 - len(parts)))
    qualifier = (match.group(2) or "").casefold()
    stage = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2, "rc": 3}.get(
        qualifier,
        4,
    )
    return (*parts[:4], stage)


def is_newer_version(candidate: str, current: str) -> bool:
    return _version_key(candidate) > _version_key(current)


def _trusted_url(
    value: str,
    *,
    hosts: set[str],
    path_prefix: str | None = None,
) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in hosts
        and not parsed.username
        and not parsed.password
        and port in {None, 443}
        and (path_prefix is None or parsed.path.startswith(path_prefix))
    )


def _parse_asset(raw: dict[str, Any]) -> ReleaseAsset | None:
    name = str(raw.get("name", "")).strip()
    url = str(raw.get("browser_download_url", "")).strip()
    size = raw.get("size")
    if (
        not name
        or not isinstance(size, int)
        or size <= 0
        or size > MAXIMUM_INSTALLER_BYTES
        or not _trusted_url(
            url,
            hosts={"github.com"},
            path_prefix="/Mamat79/EC4-LiveProfessor-Bridge/releases/download/",
        )
    ):
        return None
    digest = str(raw.get("digest", "")).strip()
    sha256 = None
    if digest.casefold().startswith("sha256:"):
        candidate = digest.split(":", 1)[1]
        if SHA256_VALUE.fullmatch(candidate):
            sha256 = candidate.upper()
    return ReleaseAsset(name, size, url, sha256)


def parse_release(payload: dict[str, Any]) -> ApplicationRelease:
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        raise ApplicationUpdateError("la réponse GitHub n'est pas une version stable")
    version_match = re.fullmatch(
        r"v?(\d+(?:\.\d+){1,3})", str(payload.get("tag_name", "")).strip()
    )
    if version_match is None:
        raise ApplicationUpdateError("la version GitHub est invalide")
    page_url = str(payload.get("html_url", "")).strip()
    if not _trusted_url(
        page_url,
        hosts={"github.com"},
        path_prefix="/Mamat79/EC4-LiveProfessor-Bridge/releases/",
    ):
        raise ApplicationUpdateError("la page de version GitHub n'est pas fiable")
    raw_assets = payload.get("assets", [])
    if not isinstance(raw_assets, list):
        raise ApplicationUpdateError("la liste des fichiers GitHub est invalide")
    assets = [
        asset
        for raw in raw_assets
        if isinstance(raw, dict) and (asset := _parse_asset(raw)) is not None
    ]
    installer = next((item for item in assets if INSTALLER_NAME.fullmatch(item.name)), None)
    if installer is None:
        raise NoCompatibleRelease(
            "aucun installateur Controller Studio compatible n'est publié"
        )
    checksum = next(
        (
            item
            for item in assets
            if item.name.casefold() == f"{installer.name}.sha256".casefold()
        ),
        None,
    )
    if installer.sha256 is None and checksum is None:
        raise ApplicationUpdateError(
            f"l'empreinte SHA-256 de {installer.name} est absente"
        )
    return ApplicationRelease(
        version=version_match.group(1),
        title=str(payload.get("name") or payload.get("tag_name") or "Controller Studio"),
        notes=str(payload.get("body") or ""),
        page_url=page_url,
        installer=installer,
        checksum=checksum,
    )


def _request(url: str, accept: str = "application/vnd.github+json") -> Request:
    return Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "Controller-Studio-for-LiveProfessor",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )


def fetch_latest_release(
    *,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 12.0,
) -> ApplicationRelease:
    if not _trusted_url(
        LATEST_RELEASE_API_URL,
        hosts={"api.github.com"},
        path_prefix="/repos/Mamat79/EC4-LiveProfessor-Bridge/releases/latest",
    ):
        raise ApplicationUpdateError("l'adresse de mise à jour n'est pas fiable")
    try:
        with opener(_request(LATEST_RELEASE_API_URL), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except NoCompatibleRelease:
        raise
    except Exception as exc:
        raise ApplicationUpdateError(f"GitHub est inaccessible : {exc}") from exc
    return parse_release(payload)


def _response_url(response: Any, fallback: str) -> str:
    getter = getattr(response, "geturl", None)
    return str(getter() if callable(getter) else fallback)


def _read_checksum(
    asset: ReleaseAsset,
    *,
    opener: Callable[..., Any],
    timeout: float,
) -> str:
    with opener(_request(asset.download_url, "application/octet-stream"), timeout=timeout) as response:
        final_url = _response_url(response, asset.download_url)
        if not _trusted_url(final_url, hosts=TRUSTED_DOWNLOAD_HOSTS):
            raise ApplicationUpdateError("redirection GitHub non fiable")
        content = response.read(4096).decode("ascii", errors="strict").strip()
    candidate = content.split()[0] if content else ""
    if not SHA256_VALUE.fullmatch(candidate):
        raise ApplicationUpdateError("le fichier SHA-256 de la version est invalide")
    return candidate.upper()


def download_update(
    release: ApplicationRelease,
    destination_directory: Path | None = None,
    *,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 30.0,
    progress: Callable[[int, int], None] | None = None,
) -> UpdateDownload:
    installer = release.installer
    expected_hash = installer.sha256
    if expected_hash is None:
        if release.checksum is None:
            raise ApplicationUpdateError("empreinte SHA-256 absente")
        expected_hash = _read_checksum(
            release.checksum,
            opener=opener,
            timeout=timeout,
        )
    destination_root = Path(destination_directory or (product_data_dir() / "updates"))
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / installer.name
    partial = destination.with_name(f".{destination.name}.partial")
    hasher = hashlib.sha256()
    total = 0
    try:
        with opener(
            _request(installer.download_url, "application/octet-stream"),
            timeout=timeout,
        ) as response, partial.open("wb") as output:
            final_url = _response_url(response, installer.download_url)
            if not _trusted_url(final_url, hosts=TRUSTED_DOWNLOAD_HOSTS):
                raise ApplicationUpdateError("redirection GitHub non fiable")
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAXIMUM_INSTALLER_BYTES or total > installer.size:
                    raise ApplicationUpdateError("l'installateur dépasse la taille annoncée")
                hasher.update(block)
                output.write(block)
                if progress is not None:
                    progress(total, installer.size)
        if total != installer.size:
            raise ApplicationUpdateError(
                f"téléchargement incomplet : {total}/{installer.size} octets"
            )
        actual_hash = hasher.hexdigest().upper()
        if actual_hash != expected_hash:
            raise ApplicationUpdateError(
                "l'installateur téléchargé ne correspond pas à son empreinte SHA-256"
            )
        os.replace(partial, destination)
        return UpdateDownload(release, destination, actual_hash)
    finally:
        if partial.exists():
            partial.unlink()


def launch_installer(
    path: Path,
    launcher: Callable[[str], object] | None = None,
) -> None:
    installer = Path(path).expanduser().resolve()
    if not installer.is_file() or not INSTALLER_NAME.fullmatch(installer.name):
        raise ApplicationUpdateError("installateur Controller Studio invalide")
    if launcher is not None:
        launcher(str(installer))
    elif sys.platform == "win32":
        os.startfile(str(installer))
    else:
        subprocess.Popen([str(installer)], close_fds=True)
