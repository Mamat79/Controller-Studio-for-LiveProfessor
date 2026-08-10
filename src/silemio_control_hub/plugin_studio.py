"""Application services for the offline plug-in profile studio."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
import time
import unicodedata

from .adapters.hosts.liveprofessor_automap import (
    ProjectPlugin,
    inspect_plugin_parameter_slots,
    inspect_plugins,
)
from .plugin_profiles import (
    PluginObservation,
    PluginParameterKind,
    PluginParameterProfile,
    PluginProfile,
    PluginProfileError,
    PluginProfileLayer,
    PluginProfileResolver,
    ResolvedPluginProfile,
    compact_label,
)
from .plugin_registry import default_user_plugin_profile_dir
from .transports.osc import OSCClient, OSCServer
from .vst3_scanner import VST3ScanResult, scan_installed_vst3


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


def request_liveprofessor_companion_names(
    *,
    host: str,
    request_port: int,
    feedback_host: str,
    feedback_port: int,
    max_controls: int = 512,
    timeout: float = 30.0,
    quiet_period: float = 0.35,
    retry_interval: float = 2.0,
) -> tuple[str, ...]:
    """Request Companion labels without starting a hardware controller runtime.

    LiveProfessor sends one ``/Companion/ControllerNames`` message per mapped
    rotary.  Depending on the active Controller Map, that inventory can arrive
    several seconds after a refresh request.  Requests are therefore retried
    until the first label arrives, then collection stops shortly after the last
    label so larger Controller Maps are accepted without a fixed short delay.
    """

    if not 1 <= int(request_port) <= 65535 or not 1 <= int(feedback_port) <= 65535:
        raise PluginProfileError("les ports OSC doivent être compris entre 1 et 65535")
    if max_controls < 1:
        raise PluginProfileError("max_controls doit être supérieur à zéro")

    names = [""] * max_controls
    first_name = threading.Event()
    lock = threading.Lock()
    last_update = [0.0]
    errors: list[Exception] = []

    def receive(address: str, args: list[object]) -> None:
        if not address.casefold().endswith("/controllernames") or len(args) < 2:
            return
        match = re.search(
            r"(?:Rotary|Encoder)\s*(\d+)",
            str(args[0]),
            flags=re.IGNORECASE,
        )
        if match is None:
            return
        index = int(match.group(1)) - 1
        if not 0 <= index < max_controls:
            return
        name = str(args[1] or "").strip()
        if not name:
            return
        with lock:
            names[index] = name
            last_update[0] = time.monotonic()
        first_name.set()

    server = OSCServer(feedback_host, int(feedback_port), receive, errors.append)
    client = OSCClient(host, int(request_port))
    started = False
    try:
        try:
            server.start()
            started = True
        except OSError as exc:
            raise PluginProfileError(
                f"le port de retour OSC {feedback_host}:{feedback_port} est indisponible: {exc}"
            ) from exc
        deadline = time.monotonic() + max(0.05, timeout)
        next_request = 0.0
        retry_after = max(0.05, retry_interval)
        settle_after = max(0.0, quiet_period)
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_request:
                client.send("/init")
                client.send("/refresh")
                client.send("/ViewSets/Refresh")
                next_request = now + retry_after
            if first_name.is_set():
                with lock:
                    quiet_for = time.monotonic() - last_update[0]
                if quiet_for >= settle_after:
                    break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.02, max(0.001, remaining)))
    except OSError as exc:
        raise PluginProfileError(f"communication OSC impossible: {exc}") from exc
    finally:
        client.close()
        if started:
            server.stop()

    highest = max((index for index, name in enumerate(names) if name), default=-1)
    if highest < 0 and errors:
        raise PluginProfileError(f"retour OSC impossible: {errors[0]}")
    return tuple(names[: highest + 1])


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
            enabled=parameter.enabled,
        )
        for parameter in resolved.parameters
    )


def retrieve_installed_parameter_names(
    summary: PluginTypeSummary,
    *,
    database: Path | None = None,
    timeout: float = 20.0,
) -> VST3ScanResult:
    """Read the exact parameter inventory exported by an installed plug-in.

    The scanner itself runs out of process.  Its result is accepted only when
    the exported parameter count exactly matches the LiveProfessor project.
    """

    return scan_installed_vst3(
        summary.observation.name,
        expected_parameter_count=len(summary.observation.parameters),
        plugin_format=summary.observation.plugin_format,
        database=database,
        timeout=timeout,
    )


def merge_scanned_parameter_names(
    parameters: Sequence[PluginParameterProfile],
    scan: VST3ScanResult,
) -> tuple[PluginParameterProfile, ...]:
    """Merge a verified VST3 inventory without losing the user's choices."""

    if len(parameters) != len(scan.parameters):
        raise PluginProfileError(
            f"inventaire incompatible : {len(scan.parameters)} noms pour "
            f"{len(parameters)} paramètres LiveProfessor"
        )
    updated: list[PluginParameterProfile] = []
    for index, (current, scanned) in enumerate(zip(parameters, scan.parameters)):
        if scanned.index != index:
            raise PluginProfileError("l'ordre du scanner de plug-ins est invalide")
        kind = current.kind
        if scanned.step_count == 1:
            kind = PluginParameterKind.TOGGLE
        elif scanned.step_count > 1:
            kind = PluginParameterKind.ENUM
        updated.append(
            replace(
                current,
                name=scanned.name,
                short_label=compact_label(scanned.name, fallback_index=index),
                unit=scanned.unit or current.unit,
                kind=kind,
            )
        )
    return tuple(updated)


def capture_liveprofessor_parameter_names(
    parameters: Sequence[PluginParameterProfile],
    *,
    project: Path,
    plugin_uid: int,
    live_names: Sequence[str],
) -> tuple[tuple[PluginParameterProfile, ...], int]:
    """Merge real names reported by LiveProfessor into an editable profile.

    The saved Controller Map supplies the slot-to-parameter relationship, so a
    semantic or manually reordered map cannot shift labels onto the wrong IDs.
    """

    slots = inspect_plugin_parameter_slots(project, plugin_uid=plugin_uid)
    if not slots:
        raise PluginProfileError(
            "aucune Controller Map enregistrée ne relie ce plug-in aux rotatifs"
        )
    updated = list(parameters)
    captured = 0
    for slot, parameter_id in slots.items():
        if not 0 <= slot < len(live_names) or not 0 <= parameter_id < len(updated):
            continue
        name = str(live_names[slot] or "").strip()
        if not name:
            continue
        current = updated[parameter_id]
        captured += 1
        if current.name != name:
            updated[parameter_id] = replace(
                current,
                name=name,
                short_label=compact_label(name, fallback_index=parameter_id),
            )
    return tuple(updated), captured


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
