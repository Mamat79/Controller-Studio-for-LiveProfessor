"""Validate paths, hashes, metadata and declarative-only library boundaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re


ROOT = Path(__file__).parents[1].resolve()
MANIFEST = ROOT / "manifest-v1.json"
PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
VERSION = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
SHA256 = re.compile(r"^[0-9A-Fa-f]{64}$")
ALLOWED_STATUS = {"builtin", "verified", "community"}
ENTRY_KEYS = {"id", "version", "status", "path", "sha256", "minimum_hub_version"}
MANIFEST_KEYS = {"manifest_version", "generated_at", "profiles", "plugin_profiles"}
FORBIDDEN_PROFILE_KEYS = {
    "code",
    "command",
    "executable",
    "host_name",
    "license_key",
    "machine_id",
    "network",
    "rack2",
    "script",
}


class ValidationError(ValueError):
    pass


def _reject_forbidden(value: object, *, location: str) -> None:
    if isinstance(value, dict):
        forbidden = sorted(set(value) & FORBIDDEN_PROFILE_KEYS)
        if forbidden:
            raise ValidationError(
                f"{location} contient des champs sensibles ou exécutables: {', '.join(forbidden)}"
            )
        for key, item in value.items():
            _reject_forbidden(item, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden(item, location=f"{location}[{index}]")


def _entry(raw: object, *, collection: str, index: int) -> tuple[str, PurePosixPath]:
    location = f"{collection}[{index}]"
    if not isinstance(raw, dict) or set(raw) - ENTRY_KEYS:
        raise ValidationError(f"{location} contient une structure inconnue")
    profile_id = raw.get("id")
    version = raw.get("version")
    status = raw.get("status")
    digest = raw.get("sha256")
    minimum = raw.get("minimum_hub_version")
    if not isinstance(profile_id, str) or not PROFILE_ID.fullmatch(profile_id):
        raise ValidationError(f"{location}.id est invalide")
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValidationError(f"{location}.version est invalide")
    if status not in ALLOWED_STATUS:
        raise ValidationError(f"{location}.status est invalide")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValidationError(f"{location}.sha256 est invalide")
    if minimum is not None and (
        not isinstance(minimum, str) or not VERSION.fullmatch(minimum)
    ):
        raise ValidationError(f"{location}.minimum_hub_version est invalide")
    path_raw = raw.get("path")
    if not isinstance(path_raw, str) or "\\" in path_raw:
        raise ValidationError(f"{location}.path est invalide")
    path = PurePosixPath(path_raw)
    expected_root = "controllers" if collection == "profiles" else "plugin-profiles"
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != expected_root:
        raise ValidationError(f"{location}.path sort de {expected_root}")
    source = ROOT.joinpath(*path.parts).resolve()
    try:
        source.relative_to(ROOT)
    except ValueError as exc:
        raise ValidationError(f"{location}.path sort de la bibliothèque") from exc
    if not source.is_file():
        raise ValidationError(f"{location}.path est introuvable: {path}")
    payload = source.read_bytes()
    actual = hashlib.sha256(payload).hexdigest().upper()
    if actual != digest.upper():
        raise ValidationError(f"{location}.sha256 ne correspond pas à {path}")
    profile = json.loads(payload.decode("utf-8"))
    if not isinstance(profile, dict):
        raise ValidationError(f"{path} n'est pas un objet JSON")
    _reject_forbidden(profile, location=str(path))
    if profile.get("schema_version") != 1:
        raise ValidationError(f"{path}.schema_version doit valoir 1")
    if profile.get("id") != profile_id or profile.get("profile_version") != version:
        raise ValidationError(f"{path} ne correspond pas aux métadonnées du manifeste")
    if profile.get("status") != status:
        raise ValidationError(f"{path}.status ne correspond pas au manifeste")
    if collection == "plugin_profiles" and profile.get("layer") != "suggested":
        raise ValidationError(f"{path}.layer doit valoir suggested")
    return profile_id, path


def main() -> int:
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != MANIFEST_KEYS:
        raise ValidationError("manifest-v1.json contient une structure inconnue")
    if raw.get("manifest_version") != 1:
        raise ValidationError("manifest_version doit valoir 1")
    if not isinstance(raw.get("generated_at"), str) or not raw["generated_at"].strip():
        raise ValidationError("generated_at est absent")
    all_paths: list[PurePosixPath] = []
    for collection in ("profiles", "plugin_profiles"):
        entries = raw.get(collection)
        if not isinstance(entries, list):
            raise ValidationError(f"{collection} doit être une liste")
        ids: list[str] = []
        for index, item in enumerate(entries):
            profile_id, path = _entry(item, collection=collection, index=index)
            ids.append(profile_id)
            all_paths.append(path)
        if len(ids) != len(set(ids)):
            raise ValidationError(f"{collection} contient plusieurs versions actives du même id")
    if len(all_paths) != len(set(all_paths)):
        raise ValidationError("le manifeste contient des chemins dupliqués")
    discovered = {
        source.relative_to(ROOT).as_posix()
        for folder in ("controllers", "plugin-profiles")
        for source in (ROOT / folder).glob("**/profile.json")
    }
    referenced = {path.as_posix() for path in all_paths}
    if discovered != referenced:
        missing = sorted(discovered - referenced)
        stale = sorted(referenced - discovered)
        raise ValidationError(f"écart manifeste: non référencés={missing}, absents={stale}")
    print(
        f"OK: {len(raw['profiles'])} contrôleur(s), "
        f"{len(raw['plugin_profiles'])} profil(s) de plug-in"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
