"""Regenerate the deterministic profile entries of manifest-v1.json."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "manifest-v1.json"


def _entries(folder: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for source in sorted((ROOT / folder).glob("**/profile.json")):
        payload = source.read_bytes()
        raw = json.loads(payload.decode("utf-8"))
        entries.append(
            {
                "id": str(raw["id"]),
                "version": str(raw["profile_version"]),
                "status": str(raw["status"]),
                "path": source.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest().upper(),
                "minimum_hub_version": "0.1.0",
            }
        )
    return entries


def main() -> int:
    manifest = {
        "manifest_version": 1,
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "profiles": _entries("controllers"),
        "plugin_profiles": _entries("plugin-profiles"),
    }
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=ROOT,
        prefix=".manifest-v1-",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(payload)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, MANIFEST)
    print(f"ÉCRIT: {MANIFEST} | {len(manifest['profiles'])} contrôleurs | {len(manifest['plugin_profiles'])} plug-ins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
