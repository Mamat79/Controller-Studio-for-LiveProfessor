"""Validate every manifest payload against the published JSON Schemas."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    manifest_schema = _load(ROOT / "schemas" / "library-manifest-schema-v1.json")
    controller_schema = _load(ROOT / "schemas" / "controller-profile-schema-v1.json")
    plugin_schema = _load(ROOT / "schemas" / "plugin-profile-schema-v1.json")
    for schema in (manifest_schema, controller_schema, plugin_schema):
        Draft202012Validator.check_schema(schema)
    manifest = _load(ROOT / "manifest-v1.json")
    Draft202012Validator(manifest_schema).validate(manifest)
    for entry in manifest["profiles"]:
        Draft202012Validator(controller_schema).validate(_load(ROOT / entry["path"]))
    for entry in manifest.get("plugin_profiles", []):
        Draft202012Validator(plugin_schema).validate(_load(ROOT / entry["path"]))
    print("OK: manifeste et profils conformes aux schémas JSON v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
