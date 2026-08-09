from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from .models import ControllerProfile, PROFILE_ID, PROFILE_VERSION, ProfileError
from .plugin_profiles import PluginProfile, PluginProfileError, PluginProfileLayer


SHA256 = re.compile(r"^[0-9A-Fa-f]{64}$")


class LibraryError(ValueError):
    """Raised when a controller-library manifest or payload is unsafe."""


def _reject_unknown(raw: dict[str, Any], allowed: set[str], *, location: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise LibraryError(f"{location} contient des champs inconnus: {', '.join(unknown)}")


@dataclass(frozen=True, slots=True)
class LibraryEntry:
    id: str
    version: str
    status: str
    path: PurePosixPath
    sha256: str
    minimum_hub_version: str | None = None

    @classmethod
    def from_dict(
        cls,
        raw: dict[str, Any],
        *,
        index: int,
        collection: str = "profiles",
    ) -> "LibraryEntry":
        location = f"{collection}[{index}]"
        if not isinstance(raw, dict):
            raise LibraryError(f"{location} doit être un objet")
        _reject_unknown(
            raw,
            {"id", "version", "status", "path", "sha256", "minimum_hub_version"},
            location=location,
        )
        profile_id = raw.get("id")
        if not isinstance(profile_id, str) or not PROFILE_ID.fullmatch(profile_id):
            raise LibraryError(f"{location}.id est invalide")
        version = raw.get("version")
        if not isinstance(version, str) or not PROFILE_VERSION.fullmatch(version):
            raise LibraryError(f"{location}.version doit respecter la forme 1.2.3")
        minimum = raw.get("minimum_hub_version")
        if minimum is not None and (
            not isinstance(minimum, str) or not PROFILE_VERSION.fullmatch(minimum)
        ):
            raise LibraryError(
                f"{location}.minimum_hub_version doit respecter la forme 1.2.3"
            )
        status = raw.get("status")
        if status not in {"builtin", "verified", "community"}:
            raise LibraryError(f"{location}.status est inconnu")
        path_raw = raw.get("path")
        if not isinstance(path_raw, str) or not path_raw:
            raise LibraryError(f"{location}.path est absent")
        path = PurePosixPath(path_raw)
        if path.is_absolute() or ".." in path.parts or "\\" in path_raw:
            raise LibraryError(f"{location}.path doit rester relatif au dépôt")
        if path.suffix.casefold() != ".json":
            raise LibraryError(f"{location}.path doit désigner un fichier JSON")
        digest = raw.get("sha256")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise LibraryError(f"{location}.sha256 est invalide")
        return cls(profile_id, version, status, path, digest.upper(), minimum)


@dataclass(frozen=True, slots=True)
class LibraryManifest:
    manifest_version: int
    generated_at: str
    profiles: tuple[LibraryEntry, ...]
    plugin_profiles: tuple[LibraryEntry, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "LibraryManifest":
        if not isinstance(raw, dict):
            raise LibraryError("le manifeste doit être un objet JSON")
        _reject_unknown(
            raw,
            {"manifest_version", "generated_at", "profiles", "plugin_profiles"},
            location="manifest",
        )
        if raw.get("manifest_version") != 1:
            raise LibraryError("manifest_version doit valoir 1")
        generated_at = raw.get("generated_at")
        if not isinstance(generated_at, str) or not generated_at.strip():
            raise LibraryError("generated_at est absent")
        profiles_raw = raw.get("profiles")
        if not isinstance(profiles_raw, list):
            raise LibraryError("profiles doit être une liste")
        profiles = tuple(
            LibraryEntry.from_dict(item, index=index)
            for index, item in enumerate(profiles_raw)
        )
        plugin_profiles_raw = raw.get("plugin_profiles", [])
        if not isinstance(plugin_profiles_raw, list):
            raise LibraryError("plugin_profiles doit être une liste")
        plugin_profiles = tuple(
            LibraryEntry.from_dict(item, index=index, collection="plugin_profiles")
            for index, item in enumerate(plugin_profiles_raw)
        )
        ids = [entry.id for entry in profiles]
        if len(ids) != len(set(ids)):
            raise LibraryError("le manifeste contient plusieurs versions actives du même profil")
        plugin_ids = [entry.id for entry in plugin_profiles]
        if len(plugin_ids) != len(set(plugin_ids)):
            raise LibraryError(
                "le manifeste contient plusieurs versions actives du même profil de plug-in"
            )
        paths = [entry.path for entry in (*profiles, *plugin_profiles)]
        if len(paths) != len(set(paths)):
            raise LibraryError("le manifeste contient des chemins dupliqués")
        return cls(1, generated_at.strip(), profiles, plugin_profiles)

    @classmethod
    def load_file(cls, path: Path) -> "LibraryManifest":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LibraryError(f"manifeste illisible {path}: {exc}") from exc
        return cls.from_dict(raw)


@dataclass(frozen=True, slots=True)
class ValidatedLibraryProfile:
    entry: LibraryEntry
    profile: ControllerProfile
    source: Path


@dataclass(frozen=True, slots=True)
class ValidatedLibraryPluginProfile:
    entry: LibraryEntry
    profile: PluginProfile
    source: Path


def _read_entry(root: Path, entry: LibraryEntry, *, kind: str) -> tuple[Path, bytes]:
    source = root.joinpath(*entry.path.parts).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise LibraryError(f"le {kind} sort de la racine de bibliothèque: {entry.path}") from exc
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise LibraryError(f"{kind} de bibliothèque illisible {entry.path}: {exc}") from exc
    digest = hashlib.sha256(payload).hexdigest().upper()
    if digest != entry.sha256:
        raise LibraryError(
            f"SHA-256 incorrect pour {entry.path}: attendu {entry.sha256}, obtenu {digest}"
        )
    return source, payload


def validate_library(
    root: Path,
    manifest: LibraryManifest,
) -> tuple[ValidatedLibraryProfile, ...]:
    root = Path(root).expanduser().resolve()
    validated: list[ValidatedLibraryProfile] = []
    for entry in manifest.profiles:
        source, payload = _read_entry(root, entry, kind="profil")
        try:
            raw = json.loads(payload.decode("utf-8"))
            profile = ControllerProfile.from_dict(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, ProfileError) as exc:
            raise LibraryError(f"profil invalide {entry.path}: {exc}") from exc
        if profile.id != entry.id:
            raise LibraryError(
                f"id incohérent pour {entry.path}: {entry.id} != {profile.id}"
            )
        if profile.profile_version != entry.version:
            raise LibraryError(
                f"version incohérente pour {entry.path}: "
                f"{entry.version} != {profile.profile_version}"
            )
        if profile.status != entry.status:
            raise LibraryError(
                f"statut incohérent pour {entry.path}: {entry.status} != {profile.status}"
            )
        validated.append(ValidatedLibraryProfile(entry, profile, source))
    return tuple(validated)


def validate_plugin_library(
    root: Path,
    manifest: LibraryManifest,
) -> tuple[ValidatedLibraryPluginProfile, ...]:
    root = Path(root).expanduser().resolve()
    validated: list[ValidatedLibraryPluginProfile] = []
    for entry in manifest.plugin_profiles:
        source, payload = _read_entry(root, entry, kind="profil de plug-in")
        try:
            raw = json.loads(payload.decode("utf-8"))
            profile = PluginProfile.from_dict(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, PluginProfileError) as exc:
            raise LibraryError(f"profil de plug-in invalide {entry.path}: {exc}") from exc
        if profile.id != entry.id:
            raise LibraryError(
                f"id de plug-in incohérent pour {entry.path}: {entry.id} != {profile.id}"
            )
        if profile.profile_version != entry.version:
            raise LibraryError(
                f"version de plug-in incohérente pour {entry.path}: "
                f"{entry.version} != {profile.profile_version}"
            )
        if profile.status != entry.status:
            raise LibraryError(
                f"statut de plug-in incohérent pour {entry.path}: "
                f"{entry.status} != {profile.status}"
            )
        if profile.layer != PluginProfileLayer.SUGGESTED:
            raise LibraryError(
                f"la bibliothèque partagée refuse la couche {profile.layer.value}: {entry.path}"
            )
        validated.append(ValidatedLibraryPluginProfile(entry, profile, source))
    return tuple(validated)
