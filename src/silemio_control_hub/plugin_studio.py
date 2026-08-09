"""Application services for the offline plug-in profile studio."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata

from .adapters.hosts.liveprofessor_automap import ProjectPlugin, inspect_plugins
from .plugin_profiles import (
    PluginObservation,
    PluginParameterProfile,
    PluginProfile,
    PluginProfileError,
    PluginProfileLayer,
    PluginProfileResolver,
    ResolvedPluginProfile,
)
from .plugin_registry import default_user_plugin_profile_dir


@dataclass(frozen=True, slots=True)
class PluginTypeSummary:
    observation: PluginObservation
    instances: tuple[ProjectPlugin, ...]
    resolved: ResolvedPluginProfile

    @property
    def instance_uids(self) -> tuple[int, ...]:
        return tuple(instance.plugin_uid for instance in self.instances)


@dataclass(frozen=True, slots=True)
class PluginProjectAnalysis:
    path: Path
    source_sha256: str
    plugin_types: tuple[PluginTypeSummary, ...]

    @property
    def instance_count(self) -> int:
        return sum(len(item.instances) for item in self.plugin_types)


@dataclass(frozen=True, slots=True)
class UserProfileSaveResult:
    profile: PluginProfile
    path: Path
    backup_path: Path | None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower()
    return cleaned or "plugin"


def default_user_profile_id(observation: PluginObservation) -> str:
    canonical = "\0".join(
        (
            observation.plugin_format.casefold(),
            observation.stable_id,
            observation.parameter_fingerprint,
            observation.version or "",
        )
    ).encode("utf-8")
    identity_hash = hashlib.sha256(canonical).hexdigest()[:10]
    return f"local.{_slug(observation.name)}.{identity_hash}"


def _version_key(value: str) -> tuple[int, int, int, int, str]:
    core, separator, prerelease = value.partition("-")
    major, minor, patch = (int(part) for part in core.split("."))
    return major, minor, patch, 0 if separator else 1, prerelease


def compatible_user_profile(
    profiles: Iterable[PluginProfile],
    observation: PluginObservation,
) -> PluginProfile | None:
    compatible = [
        profile
        for profile in profiles
        if profile.layer == PluginProfileLayer.USER
        and profile.identity.matches(observation)
    ]
    if not compatible:
        return None
    newest_key = max(_version_key(profile.profile_version) for profile in compatible)
    newest = [
        profile
        for profile in compatible
        if _version_key(profile.profile_version) == newest_key
    ]
    if len(newest) > 1:
        ids = ", ".join(sorted(profile.id for profile in newest))
        raise PluginProfileError(
            f"plusieurs profils user ont la même version compatible: {ids}"
        )
    return newest[0]


def next_user_profile_version(
    profiles: Iterable[PluginProfile],
    observation: PluginObservation,
) -> str:
    current = compatible_user_profile(profiles, observation)
    if current is None:
        return "1.0.0"
    major, minor, patch, _stable, _prerelease = _version_key(
        current.profile_version
    )
    return f"{major}.{minor}.{patch + 1}"


def editable_parameters(
    resolved: ResolvedPluginProfile,
) -> tuple[PluginParameterProfile, ...]:
    return tuple(
        PluginParameterProfile(
            stable_id=parameter.stable_id,
            name=parameter.name,
            short_label=parameter.short_label,
            unit=parameter.unit,
            role=parameter.role,
            kind=parameter.kind,
            importance=parameter.importance,
        )
        for parameter in resolved.parameters
    )


def build_user_profile(
    observation: PluginObservation,
    parameters: Sequence[PluginParameterProfile],
    *,
    profile_id: str | None = None,
    profile_version: str = "1.0.0",
) -> PluginProfile:
    return PluginProfile.from_dict(
        {
            "schema_version": 1,
            "profile_version": profile_version,
            "id": profile_id or default_user_profile_id(observation),
            "status": "local",
            "layer": "user",
            "plugin_name": observation.name,
            "manufacturer": observation.manufacturer,
            "identity": observation.identity.to_dict(),
            "parameters": [parameter.to_dict() for parameter in parameters],
        }
    )


def analyze_plugin_project(
    project: Path,
    profiles: Iterable[PluginProfile] = (),
) -> PluginProjectAnalysis:
    source = Path(project).expanduser().resolve()
    source_hash = _sha256(source)
    instances = inspect_plugins(source)
    after_hash = _sha256(source)
    if after_hash != source_hash:
        raise PluginProfileError(
            "le projet LiveProfessor a changé pendant son analyse"
        )

    grouped: dict[tuple[str, str], list[ProjectPlugin]] = {}
    for instance in instances:
        observation = instance.observation
        key = (observation.stable_id, observation.parameter_fingerprint)
        grouped.setdefault(key, []).append(instance)

    resolver = PluginProfileResolver(profiles)
    summaries = tuple(
        PluginTypeSummary(
            observation=group[0].observation,
            instances=tuple(group),
            resolved=resolver.resolve(group[0].observation),
        )
        for group in grouped.values()
    )
    return PluginProjectAnalysis(source, source_hash, summaries)


def save_user_profile(
    profile: PluginProfile,
    *,
    directory: Path | None = None,
    replace: bool = False,
) -> UserProfileSaveResult:
    if profile.layer != PluginProfileLayer.USER or profile.status != "local":
        raise PluginProfileError("seul un profil user local peut être enregistré")
    root = Path(directory or default_user_plugin_profile_dir()).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{profile.id}.json"
    backup_path: Path | None = None
    if destination.exists():
        if not replace:
            raise PluginProfileError(
                f"{destination} existe déjà; autorisez explicitement son remplacement"
            )
        previous = PluginProfile.load_file(destination)
        if previous.layer != PluginProfileLayer.USER:
            raise PluginProfileError("le profil existant n'appartient pas à la couche user")
        backup_root = root / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = backup_root / f"{previous.id}-{previous.profile_version}-{stamp}.json"
        shutil.copy2(destination, backup_path)

    payload = json.dumps(
        profile.to_dict(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=root,
            prefix=f".{profile.id}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    reloaded = PluginProfile.load_file(destination)
    if reloaded != profile:
        raise PluginProfileError("le profil relu ne correspond pas au profil enregistré")
    return UserProfileSaveResult(profile, destination, backup_path)
