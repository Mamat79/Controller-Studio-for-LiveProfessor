"""Identité et résolution déterministes des profils de plug-ins SiLeMI/O."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable

from .models import PROFILE_ID, PROFILE_VERSION


FINGERPRINT = re.compile(r"^[0-9A-Fa-f]{64}$")


class PluginProfileError(ValueError):
    """Raised when a plug-in observation or profile is unsafe or ambiguous."""


def _reject_unknown(raw: dict[str, Any], allowed: set[str], *, location: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise PluginProfileError(
            f"{location} contient des champs inconnus: {', '.join(unknown)}"
        )


def _required_text(value: object, *, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PluginProfileError(f"{location} doit être un texte non vide")
    cleaned = value.strip()
    if any(character in cleaned for character in "\r\n\0"):
        raise PluginProfileError(f"{location} contient un caractère interdit")
    return cleaned


def compact_label(name: str, fallback_index: int | None = None, maximum: int = 8) -> str:
    """Create a display-safe label without assuming an EC4 four-character cell."""

    if not 1 <= maximum <= 16:
        raise PluginProfileError("maximum doit être compris entre 1 et 16")
    normalized = unicodedata.normalize("NFKC", str(name or ""))
    compact = "".join(character for character in normalized if character.isalnum())
    if compact:
        return compact[:maximum]
    if fallback_index is None:
        return "-" * min(4, maximum)
    fallback = f"P{fallback_index + 1:03d}"
    return fallback[-maximum:]


@dataclass(frozen=True, slots=True)
class ObservedParameter:
    position: int
    stable_id: str
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.position, int) or self.position < 0:
            raise PluginProfileError("la position de paramètre doit être positive ou nulle")
        object.__setattr__(
            self,
            "stable_id",
            _required_text(self.stable_id, location="parameter.stable_id"),
        )
        if self.name is not None:
            object.__setattr__(
                self,
                "name",
                _required_text(self.name, location="parameter.name"),
            )


@dataclass(frozen=True, slots=True)
class PluginIdentity:
    plugin_format: str
    stable_id: str
    parameter_fingerprint: str
    version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "plugin_format",
            _required_text(self.plugin_format, location="identity.format"),
        )
        object.__setattr__(
            self,
            "stable_id",
            _required_text(self.stable_id, location="identity.stable_id"),
        )
        if not isinstance(self.parameter_fingerprint, str) or not FINGERPRINT.fullmatch(
            self.parameter_fingerprint
        ):
            raise PluginProfileError("identity.parameter_fingerprint est invalide")
        object.__setattr__(
            self,
            "parameter_fingerprint",
            self.parameter_fingerprint.upper(),
        )
        if self.version is not None:
            object.__setattr__(
                self,
                "version",
                _required_text(self.version, location="identity.version"),
            )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PluginIdentity":
        if not isinstance(raw, dict):
            raise PluginProfileError("identity doit être un objet")
        _reject_unknown(
            raw,
            {"format", "stable_id", "parameter_fingerprint", "version"},
            location="identity",
        )
        return cls(
            plugin_format=_required_text(raw.get("format"), location="identity.format"),
            stable_id=_required_text(raw.get("stable_id"), location="identity.stable_id"),
            parameter_fingerprint=str(raw.get("parameter_fingerprint", "")).upper(),
            version=(
                _required_text(raw["version"], location="identity.version")
                if raw.get("version") is not None
                else None
            ),
        )

    def matches(self, observation: "PluginObservation") -> bool:
        other = observation.identity
        if self.plugin_format.casefold() != other.plugin_format.casefold():
            return False
        if self.stable_id != other.stable_id:
            return False
        if self.parameter_fingerprint.upper() != other.parameter_fingerprint.upper():
            return False
        if self.version is not None:
            return other.version is not None and self.version == other.version
        return True

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "format": self.plugin_format,
            "stable_id": self.stable_id,
            "parameter_fingerprint": self.parameter_fingerprint,
        }
        if self.version is not None:
            payload["version"] = self.version
        return payload


@dataclass(frozen=True, slots=True)
class PluginObservation:
    plugin_format: str
    stable_id: str
    name: str
    parameters: tuple[ObservedParameter, ...]
    manufacturer: str = ""
    version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "plugin_format",
            _required_text(self.plugin_format, location="observation.format"),
        )
        object.__setattr__(
            self,
            "stable_id",
            _required_text(self.stable_id, location="observation.stable_id"),
        )
        object.__setattr__(
            self,
            "name",
            _required_text(self.name, location="observation.name"),
        )
        if self.manufacturer:
            object.__setattr__(
                self,
                "manufacturer",
                _required_text(self.manufacturer, location="observation.manufacturer"),
            )
        if self.version is not None:
            object.__setattr__(
                self,
                "version",
                _required_text(self.version, location="observation.version"),
            )
        positions = [parameter.position for parameter in self.parameters]
        stable_ids = [parameter.stable_id for parameter in self.parameters]
        if positions != list(range(len(self.parameters))):
            raise PluginProfileError(
                "les paramètres observés doivent être ordonnés sans trou à partir de zéro"
            )
        if len(stable_ids) != len(set(stable_ids)):
            raise PluginProfileError("les paramètres observés contiennent des identifiants dupliqués")

    @classmethod
    def from_parameter_count(
        cls,
        *,
        plugin_format: str,
        stable_id: str,
        name: str,
        parameter_count: int,
        manufacturer: str = "",
        version: str | None = None,
    ) -> "PluginObservation":
        if not isinstance(parameter_count, int) or parameter_count < 0:
            raise PluginProfileError("parameter_count doit être positif ou nul")
        return cls(
            plugin_format=plugin_format,
            stable_id=stable_id,
            name=name,
            manufacturer=manufacturer,
            version=version,
            parameters=tuple(
                ObservedParameter(index, f"index:{index}")
                for index in range(parameter_count)
            ),
        )

    @property
    def parameter_fingerprint(self) -> str:
        canonical = json.dumps(
            [parameter.stable_id for parameter in self.parameters],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest().upper()

    @property
    def identity(self) -> PluginIdentity:
        return PluginIdentity(
            plugin_format=self.plugin_format,
            stable_id=self.stable_id,
            parameter_fingerprint=self.parameter_fingerprint,
            version=self.version,
        )


class PluginProfileLayer(StrEnum):
    RAW = "raw"
    SUGGESTED = "suggested"
    USER = "user"


class PluginParameterKind(StrEnum):
    CONTINUOUS = "continuous"
    TOGGLE = "toggle"
    ENUM = "enum"
    METER = "meter"


@dataclass(frozen=True, slots=True)
class PluginParameterProfile:
    stable_id: str
    name: str
    short_label: str
    unit: str = ""
    role: str | None = None
    kind: PluginParameterKind = PluginParameterKind.CONTINUOUS
    importance: int = 50

    @classmethod
    def from_dict(
        cls,
        raw: dict[str, Any],
        *,
        index: int,
    ) -> "PluginParameterProfile":
        location = f"parameters[{index}]"
        if not isinstance(raw, dict):
            raise PluginProfileError(f"{location} doit être un objet")
        _reject_unknown(
            raw,
            {"stable_id", "name", "short_label", "unit", "role", "kind", "importance"},
            location=location,
        )
        stable_id = _required_text(raw.get("stable_id"), location=f"{location}.stable_id")
        name = _required_text(raw.get("name"), location=f"{location}.name")
        short = raw.get("short_label")
        short_label = (
            _required_text(short, location=f"{location}.short_label")
            if short is not None
            else compact_label(name)
        )
        if len(short_label) > 16:
            raise PluginProfileError(f"{location}.short_label dépasse 16 caractères")
        unit_raw = raw.get("unit", "")
        if not isinstance(unit_raw, str) or any(c in unit_raw for c in "\r\n\0"):
            raise PluginProfileError(f"{location}.unit est invalide")
        role_raw = raw.get("role")
        role = None
        if role_raw is not None:
            role = _required_text(role_raw, location=f"{location}.role")
            if not PROFILE_ID.fullmatch(role):
                raise PluginProfileError(f"{location}.role est invalide")
        try:
            kind = PluginParameterKind(str(raw.get("kind", "continuous")))
        except ValueError as exc:
            raise PluginProfileError(f"{location}.kind est inconnu") from exc
        importance = raw.get("importance", 50)
        if not isinstance(importance, int) or not 0 <= importance <= 100:
            raise PluginProfileError(f"{location}.importance doit être comprise entre 0 et 100")
        return cls(stable_id, name, short_label, unit_raw, role, kind, importance)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "stable_id": self.stable_id,
            "name": self.name,
            "short_label": self.short_label,
            "unit": self.unit,
            "kind": self.kind.value,
            "importance": self.importance,
        }
        if self.role is not None:
            payload["role"] = self.role
        return payload


@dataclass(frozen=True, slots=True)
class PluginProfile:
    schema_version: int
    profile_version: str
    id: str
    status: str
    layer: PluginProfileLayer
    plugin_name: str
    manufacturer: str
    identity: PluginIdentity
    parameters: tuple[PluginParameterProfile, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PluginProfile":
        if not isinstance(raw, dict):
            raise PluginProfileError("le profil de plug-in doit être un objet")
        _reject_unknown(
            raw,
            {
                "schema_version",
                "profile_version",
                "id",
                "status",
                "layer",
                "plugin_name",
                "manufacturer",
                "identity",
                "parameters",
            },
            location="profile",
        )
        if raw.get("schema_version") != 1:
            raise PluginProfileError("schema_version doit valoir 1")
        profile_version = _required_text(
            raw.get("profile_version"), location="profile_version"
        )
        if not PROFILE_VERSION.fullmatch(profile_version):
            raise PluginProfileError("profile_version doit respecter la forme 1.2.3")
        profile_id = _required_text(raw.get("id"), location="id")
        if not PROFILE_ID.fullmatch(profile_id):
            raise PluginProfileError("id est invalide")
        status = raw.get("status")
        if status not in {"builtin", "verified", "community", "local"}:
            raise PluginProfileError("status est inconnu")
        try:
            layer = PluginProfileLayer(str(raw.get("layer")))
        except ValueError as exc:
            raise PluginProfileError("layer doit valoir suggested ou user") from exc
        if layer == PluginProfileLayer.RAW:
            raise PluginProfileError("la couche raw est générée par le Hub et ne se charge pas")
        if layer == PluginProfileLayer.USER and status != "local":
            raise PluginProfileError("un profil user doit avoir le statut local")
        if layer == PluginProfileLayer.SUGGESTED and status == "local":
            raise PluginProfileError("un profil suggested ne peut pas avoir le statut local")
        plugin_name = _required_text(raw.get("plugin_name"), location="plugin_name")
        manufacturer_raw = raw.get("manufacturer", "")
        if not isinstance(manufacturer_raw, str) or any(
            character in manufacturer_raw for character in "\r\n\0"
        ):
            raise PluginProfileError("manufacturer est invalide")
        parameters_raw = raw.get("parameters")
        if not isinstance(parameters_raw, list) or not parameters_raw:
            raise PluginProfileError("parameters doit être une liste non vide")
        parameters = tuple(
            PluginParameterProfile.from_dict(item, index=index)
            for index, item in enumerate(parameters_raw)
        )
        stable_ids = [parameter.stable_id for parameter in parameters]
        if len(stable_ids) != len(set(stable_ids)):
            raise PluginProfileError("parameters contient des stable_id dupliqués")
        return cls(
            schema_version=1,
            profile_version=profile_version,
            id=profile_id,
            status=str(status),
            layer=layer,
            plugin_name=plugin_name,
            manufacturer=manufacturer_raw.strip(),
            identity=PluginIdentity.from_dict(raw.get("identity")),
            parameters=parameters,
        )

    @classmethod
    def load_file(cls, path: Path) -> "PluginProfile":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PluginProfileError(f"profil de plug-in illisible {path}: {exc}") from exc
        return cls.from_dict(raw)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile_version": self.profile_version,
            "id": self.id,
            "status": self.status,
            "layer": self.layer.value,
            "plugin_name": self.plugin_name,
            "manufacturer": self.manufacturer,
            "identity": self.identity.to_dict(),
            "parameters": [parameter.to_dict() for parameter in self.parameters],
        }


@dataclass(frozen=True, slots=True)
class EffectivePluginParameter:
    position: int
    stable_id: str
    name: str
    short_label: str
    unit: str
    role: str | None
    kind: PluginParameterKind
    importance: int
    source_layer: PluginProfileLayer


@dataclass(frozen=True, slots=True)
class ResolvedPluginProfile:
    observation: PluginObservation
    parameters: tuple[EffectivePluginParameter, ...]
    layer: PluginProfileLayer
    applied_profile_ids: tuple[str, ...]


def _version_key(value: str) -> tuple[int, int, int, int, str]:
    core, separator, prerelease = value.partition("-")
    major, minor, patch = (int(part) for part in core.split("."))
    return major, minor, patch, 0 if separator else 1, prerelease


class PluginProfileResolver:
    """Resolve exact profiles with the fixed precedence User > Suggested > Raw."""

    def __init__(self, profiles: Iterable[PluginProfile] = ()) -> None:
        self.profiles = tuple(profiles)

    def _select(
        self,
        observation: PluginObservation,
        layer: PluginProfileLayer,
    ) -> PluginProfile | None:
        compatible = [
            profile
            for profile in self.profiles
            if profile.layer == layer and profile.identity.matches(observation)
        ]
        if not compatible:
            return None
        newest_version = max(_version_key(profile.profile_version) for profile in compatible)
        newest = [
            profile
            for profile in compatible
            if _version_key(profile.profile_version) == newest_version
        ]
        if len(newest) > 1:
            ids = ", ".join(sorted(profile.id for profile in newest))
            raise PluginProfileError(
                f"plusieurs profils {layer.value} ont la même version compatible: {ids}"
            )
        return newest[0]

    def resolve(self, observation: PluginObservation) -> ResolvedPluginProfile:
        effective = {
            parameter.stable_id: EffectivePluginParameter(
                position=parameter.position,
                stable_id=parameter.stable_id,
                name=parameter.name or f"Paramètre {parameter.position + 1}",
                short_label=compact_label(
                    parameter.name or "", fallback_index=parameter.position
                ),
                unit="",
                role=None,
                kind=PluginParameterKind.CONTINUOUS,
                importance=50,
                source_layer=PluginProfileLayer.RAW,
            )
            for parameter in observation.parameters
        }
        applied: list[str] = []
        selected_layer = PluginProfileLayer.RAW
        for layer in (PluginProfileLayer.SUGGESTED, PluginProfileLayer.USER):
            profile = self._select(observation, layer)
            if profile is None:
                continue
            unknown = sorted(
                parameter.stable_id
                for parameter in profile.parameters
                if parameter.stable_id not in effective
            )
            if unknown:
                raise PluginProfileError(
                    f"{profile.id} référence des paramètres absents: {', '.join(unknown)}"
                )
            for parameter in profile.parameters:
                position = effective[parameter.stable_id].position
                effective[parameter.stable_id] = EffectivePluginParameter(
                    position=position,
                    stable_id=parameter.stable_id,
                    name=parameter.name,
                    short_label=parameter.short_label,
                    unit=parameter.unit,
                    role=parameter.role,
                    kind=parameter.kind,
                    importance=parameter.importance,
                    source_layer=layer,
                )
            applied.append(profile.id)
            selected_layer = layer
        return ResolvedPluginProfile(
            observation=observation,
            parameters=tuple(
                sorted(effective.values(), key=lambda parameter: parameter.position)
            ),
            layer=selected_layer,
            applied_profile_ids=tuple(applied),
        )
