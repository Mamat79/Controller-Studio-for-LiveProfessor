"""Optional GitHub synchronization for the declarative SiLeMI/O library."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid

from .library import (
    LibraryEntry,
    LibraryError,
    LibraryManifest,
    validate_library,
    validate_plugin_library,
)
from .platform_paths import product_data_dir


DEFAULT_LIBRARY_REPOSITORY = "Mamat79/Controller-Studio-for-LiveProfessor"
DEFAULT_LIBRARY_REF = "main"
DEFAULT_LIBRARY_ROOT = PurePosixPath("library")
MAX_MANIFEST_BYTES = 1_000_000
MAX_PROFILE_BYTES = 4_000_000
CONTENT_API_OVERHEAD_BYTES = 65_536
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
HUB_VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:[.-].*)?$")


class LibraryRemoteError(ValueError):
    """Raised when a remote update is unsafe, incomplete or ambiguous."""


class LibraryRemote(Protocol):
    repository: str
    ref: str

    def fetch_manifest(self) -> tuple[LibraryManifest, bytes]: ...

    def fetch_profile(self, path: PurePosixPath) -> bytes: ...


@dataclass(frozen=True, slots=True)
class LibraryChange:
    collection: str
    id: str
    kind: str
    current_version: str | None
    remote_version: str | None


@dataclass(frozen=True, slots=True)
class LibraryPreview:
    repository: str
    ref: str
    generated_at: str
    changes: tuple[LibraryChange, ...]

    @property
    def has_downgrades(self) -> bool:
        return any(change.kind == "downgrade" for change in self.changes)

    @property
    def has_removals(self) -> bool:
        return any(change.kind == "removed" for change in self.changes)


@dataclass(frozen=True, slots=True)
class LibraryUpdateResult:
    preview: LibraryPreview
    cache_root: Path
    applied: bool
    backup_path: Path | None = None


@dataclass(frozen=True, slots=True)
class CachedLibraryProfiles:
    controllers: tuple[Path, ...]
    plugins: tuple[Path, ...]


def default_library_cache_dir() -> Path:
    override = os.environ.get("SILEMIO_LIBRARY_CACHE")
    if override:
        return Path(override).expanduser()
    return product_data_dir() / "library"


def _decode_content_api(payload: bytes) -> bytes:
    """Accept both GitHub raw-media and ordinary JSON content responses."""

    stripped = payload.lstrip()
    if not stripped.startswith(b"{"):
        return payload
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return payload
    if not isinstance(raw, dict) or raw.get("encoding") != "base64":
        return payload
    content = raw.get("content")
    if not isinstance(content, str):
        raise LibraryRemoteError("réponse GitHub sans contenu de fichier")
    try:
        return base64.b64decode("".join(content.split()), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise LibraryRemoteError("contenu GitHub en base64 invalide") from exc


class GitHubLibraryClient:
    """Read only files exposed by the GitHub Contents API."""

    def __init__(
        self,
        repository: str = DEFAULT_LIBRARY_REPOSITORY,
        ref: str = DEFAULT_LIBRARY_REF,
        *,
        token: str | None = None,
        timeout: float = 15.0,
        root: str | PurePosixPath = DEFAULT_LIBRARY_ROOT,
        opener=urlopen,
    ) -> None:
        if not isinstance(repository, str) or not REPOSITORY.fullmatch(repository):
            raise LibraryRemoteError("repository doit respecter la forme propriétaire/dépôt")
        if not isinstance(ref, str) or not ref.strip() or any(c in ref for c in "\r\n\0"):
            raise LibraryRemoteError("ref GitHub est invalide")
        if timeout <= 0:
            raise LibraryRemoteError("timeout doit être positif")
        library_root = PurePosixPath(str(root))
        if library_root.is_absolute() or ".." in library_root.parts:
            raise LibraryRemoteError("root GitHub est invalide")
        self.repository = repository
        self.ref = ref.strip()
        self.root = library_root
        self.token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        self.timeout = float(timeout)
        self._opener = opener

    def _fetch(self, path: PurePosixPath, *, limit: int) -> bytes:
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise LibraryRemoteError("chemin GitHub non sûr")
        encoded_path = "/".join(quote(part, safe="") for part in path.parts)
        owner, repository_name = self.repository.split("/", 1)
        url = (
            "https://api.github.com/repos/"
            f"{quote(owner, safe='')}/{quote(repository_name, safe='')}/contents/"
            f"{encoded_path}?ref={quote(self.ref, safe='')}"
        )
        headers = {
            "Accept": "application/vnd.github.raw+json",
            "User-Agent": "Controller-Studio-for-LiveProfessor",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers, method="GET")
        encoded_limit = ((limit + 2) // 3) * 4 + CONTENT_API_OVERHEAD_BYTES
        try:
            with self._opener(request, timeout=self.timeout) as response:
                payload = response.read(encoded_limit + 1)
        except HTTPError as exc:
            if exc.code in {401, 403, 404}:
                raise LibraryRemoteError(
                    "bibliothèque GitHub inaccessible; vérifiez le dépôt, la connexion "
                    "et GH_TOKEN pour un dépôt privé"
                ) from exc
            raise LibraryRemoteError(f"GitHub a répondu HTTP {exc.code}") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise LibraryRemoteError(f"téléchargement GitHub impossible: {exc}") from exc
        payload = _decode_content_api(payload)
        if len(payload) > limit:
            raise LibraryRemoteError(f"fichier distant trop volumineux: {path}")
        return payload

    def fetch_manifest(self) -> tuple[LibraryManifest, bytes]:
        payload = self._fetch(
            self.root / "manifest-v1.json",
            limit=MAX_MANIFEST_BYTES,
        )
        try:
            raw = json.loads(payload.decode("utf-8"))
            manifest = LibraryManifest.from_dict(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, LibraryError) as exc:
            raise LibraryRemoteError(f"manifeste distant invalide: {exc}") from exc
        return manifest, payload

    def fetch_profile(self, path: PurePosixPath) -> bytes:
        return self._fetch(self.root / path, limit=MAX_PROFILE_BYTES)


def _entry_map(manifest: LibraryManifest | None) -> dict[tuple[str, str], LibraryEntry]:
    if manifest is None:
        return {}
    return {
        **{("controller", entry.id): entry for entry in manifest.profiles},
        **{("plugin", entry.id): entry for entry in manifest.plugin_profiles},
    }


def _version_key(value: str) -> tuple[int, int, int, int, str]:
    core, separator, prerelease = value.partition("-")
    major, minor, patch = (int(part) for part in core.split("."))
    return major, minor, patch, 0 if separator else 1, prerelease


def _hub_version_key(value: str) -> tuple[int, int, int]:
    match = HUB_VERSION.match(value)
    if match is None:
        raise LibraryRemoteError(f"version du Hub non comparable: {value}")
    return tuple(int(part or 0) for part in match.groups())


def _installed_hub_version() -> str:
    try:
        return package_version("silemio-control-hub")
    except PackageNotFoundError:
        return "2026.2.dev0"


def _check_hub_compatibility(manifest: LibraryManifest, hub_version: str) -> None:
    current = _hub_version_key(hub_version)
    incompatible = [
        f"{entry.id} exige Hub {entry.minimum_hub_version}"
        for entry in _all_entries(manifest)
        if entry.minimum_hub_version is not None
        and current < _hub_version_key(entry.minimum_hub_version)
    ]
    if incompatible:
        raise LibraryRemoteError(
            f"bibliothèque incompatible avec Hub {hub_version}: " + "; ".join(incompatible)
        )


def preview_library(
    remote: LibraryManifest,
    current: LibraryManifest | None,
    *,
    repository: str,
    ref: str,
) -> LibraryPreview:
    remote_entries = _entry_map(remote)
    current_entries = _entry_map(current)
    changes: list[LibraryChange] = []
    for key in sorted(set(remote_entries) | set(current_entries)):
        collection, profile_id = key
        remote_entry = remote_entries.get(key)
        current_entry = current_entries.get(key)
        if current_entry is None and remote_entry is not None:
            kind = "new"
        elif remote_entry is None and current_entry is not None:
            kind = "removed"
        elif current_entry is not None and remote_entry is not None:
            if current_entry.version == remote_entry.version:
                if (
                    current_entry.sha256 != remote_entry.sha256
                    or current_entry.path != remote_entry.path
                    or current_entry.status != remote_entry.status
                ):
                    raise LibraryRemoteError(
                        f"la version publiée {profile_id} {remote_entry.version} a été remplacée; "
                        "les versions de bibliothèque doivent être immuables"
                    )
                continue
            kind = (
                "update"
                if _version_key(remote_entry.version) > _version_key(current_entry.version)
                else "downgrade"
            )
        else:
            continue
        changes.append(
            LibraryChange(
                collection=collection,
                id=profile_id,
                kind=kind,
                current_version=current_entry.version if current_entry else None,
                remote_version=remote_entry.version if remote_entry else None,
            )
        )
    return LibraryPreview(repository, ref, remote.generated_at, tuple(changes))


def _load_manifest(path: Path) -> LibraryManifest | None:
    if not path.is_file():
        return None
    try:
        return LibraryManifest.load_file(path)
    except LibraryError as exc:
        raise LibraryRemoteError(f"cache local invalide {path}: {exc}") from exc


def _validate_cached(root: Path, manifest: LibraryManifest | None) -> None:
    if manifest is None:
        return
    try:
        validate_library(root, manifest)
        validate_plugin_library(root, manifest)
    except LibraryError as exc:
        raise LibraryRemoteError(f"bibliothèque locale invalide {root}: {exc}") from exc


def _all_entries(manifest: LibraryManifest) -> tuple[LibraryEntry, ...]:
    return (*manifest.profiles, *manifest.plugin_profiles)


def cached_library_profiles(
    cache_root: Path | None = None,
) -> CachedLibraryProfiles:
    """Return only manifest-referenced paths from a fully validated local cache."""

    cache = Path(cache_root or default_library_cache_dir()).expanduser().resolve()
    current = cache / "current"
    manifest = _load_manifest(current / "manifest-v1.json")
    if manifest is None:
        return CachedLibraryProfiles((), ())
    _validate_cached(current, manifest)
    controllers = tuple(
        current.joinpath(*entry.path.parts).resolve() for entry in manifest.profiles
    )
    plugins = tuple(
        current.joinpath(*entry.path.parts).resolve()
        for entry in manifest.plugin_profiles
    )
    return CachedLibraryProfiles(controllers, plugins)


def _write_payload(root: Path, path: PurePosixPath, payload: bytes) -> Path:
    target = root.joinpath(*path.parts).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise LibraryRemoteError(f"chemin de profil hors cache: {path}") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def _timestamp_name(prefix: str = "backup") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _safe_remove_staging(path: Path, cache_root: Path) -> None:
    try:
        relative = path.resolve().relative_to(cache_root.resolve())
    except ValueError:
        return
    if len(relative.parts) == 1 and relative.name.startswith(".staging-") and path.exists():
        shutil.rmtree(path)


def update_library(
    remote: LibraryRemote,
    *,
    cache_root: Path | None = None,
    apply: bool = False,
    allow_downgrade: bool = False,
    allow_removals: bool = False,
    hub_version: str | None = None,
) -> LibraryUpdateResult:
    cache = Path(cache_root or default_library_cache_dir()).expanduser().resolve()
    current_root = cache / "current"
    current_manifest = _load_manifest(current_root / "manifest-v1.json")
    _validate_cached(current_root, current_manifest)
    remote_manifest, manifest_payload = remote.fetch_manifest()
    _check_hub_compatibility(remote_manifest, hub_version or _installed_hub_version())
    preview = preview_library(
        remote_manifest,
        current_manifest,
        repository=remote.repository,
        ref=remote.ref,
    )
    if not apply:
        return LibraryUpdateResult(preview, cache, False)
    if preview.has_downgrades and not allow_downgrade:
        raise LibraryRemoteError(
            "la mise à jour contient un retour de version; utilisez le mécanisme de rollback "
            "ou autorisez explicitement le downgrade"
        )
    if preview.has_removals and not allow_removals:
        raise LibraryRemoteError(
            "la mise à jour retirerait des profils; autorisez explicitement les suppressions"
        )
    if not preview.changes:
        return LibraryUpdateResult(preview, cache, True)

    cache.mkdir(parents=True, exist_ok=True)
    staging = cache / f".staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=False, exist_ok=False)
    backup_path: Path | None = None
    try:
        for entry in _all_entries(remote_manifest):
            payload = remote.fetch_profile(entry.path)
            digest = hashlib.sha256(payload).hexdigest().upper()
            if digest != entry.sha256:
                raise LibraryRemoteError(
                    f"SHA-256 distant incorrect pour {entry.path}: "
                    f"attendu {entry.sha256}, obtenu {digest}"
                )
            _write_payload(staging, entry.path, payload)
        _write_payload(staging, PurePosixPath("manifest-v1.json"), manifest_payload)
        try:
            validate_library(staging, remote_manifest)
            validate_plugin_library(staging, remote_manifest)
        except LibraryError as exc:
            raise LibraryRemoteError(f"bibliothèque téléchargée invalide: {exc}") from exc

        if current_root.exists():
            backups = cache / "backups"
            backups.mkdir(parents=True, exist_ok=True)
            backup_path = backups / _timestamp_name()
            os.replace(current_root, backup_path)
        try:
            os.replace(staging, current_root)
        except OSError:
            if backup_path is not None and backup_path.exists() and not current_root.exists():
                os.replace(backup_path, current_root)
            raise
    finally:
        _safe_remove_staging(staging, cache)
    return LibraryUpdateResult(preview, cache, True, backup_path)


def list_library_backups(cache_root: Path | None = None) -> tuple[str, ...]:
    cache = Path(cache_root or default_library_cache_dir()).expanduser().resolve()
    backups = cache / "backups"
    if not backups.is_dir():
        return ()
    return tuple(
        sorted(
            path.name
            for path in backups.iterdir()
            if path.is_dir() and (path / "manifest-v1.json").is_file()
        )
    )


def rollback_library(
    backup_name: str,
    *,
    cache_root: Path | None = None,
    apply: bool = False,
) -> LibraryUpdateResult:
    if (
        not isinstance(backup_name, str)
        or not backup_name
        or backup_name != Path(backup_name).name
        or any(character in backup_name for character in "\\/\0")
    ):
        raise LibraryRemoteError("nom de sauvegarde invalide")
    cache = Path(cache_root or default_library_cache_dir()).expanduser().resolve()
    current_root = cache / "current"
    source = (cache / "backups" / backup_name).resolve()
    try:
        source.relative_to((cache / "backups").resolve())
    except ValueError as exc:
        raise LibraryRemoteError("sauvegarde hors du cache") from exc
    source_manifest = _load_manifest(source / "manifest-v1.json")
    if source_manifest is None:
        raise LibraryRemoteError(f"sauvegarde introuvable: {backup_name}")
    _validate_cached(source, source_manifest)
    current_manifest = _load_manifest(current_root / "manifest-v1.json")
    _validate_cached(current_root, current_manifest)
    preview = preview_library(
        source_manifest,
        current_manifest,
        repository="local-backup",
        ref=backup_name,
    )
    if not apply:
        return LibraryUpdateResult(preview, cache, False)

    staging = cache / f".staging-{uuid.uuid4().hex}"
    shutil.copytree(source, staging)
    try:
        validate_library(staging, source_manifest)
        validate_plugin_library(staging, source_manifest)
        backup_path: Path | None = None
        if current_root.exists():
            backups = cache / "backups"
            backups.mkdir(parents=True, exist_ok=True)
            backup_path = backups / _timestamp_name("pre-rollback")
            os.replace(current_root, backup_path)
        try:
            os.replace(staging, current_root)
        except OSError:
            if backup_path is not None and backup_path.exists() and not current_root.exists():
                os.replace(backup_path, current_root)
            raise
    finally:
        _safe_remove_staging(staging, cache)
    return LibraryUpdateResult(preview, cache, True, backup_path)
