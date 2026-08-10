"""Safe hand-off of declarative controller profiles to GitHub."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote, urlencode

from .models import ControllerProfile, ProfileError


DEFAULT_CONTRIBUTION_REPOSITORY = "Mamat79/Controller-Studio-for-LiveProfessor"
CONTROLLER_ISSUE_TEMPLATE = "controller-profile.md"


def validated_controller_payload(
    source: Path,
    *,
    expected_profile_id: str | None = None,
) -> tuple[ControllerProfile, str]:
    """Return canonical JSON only after parsing it with the product model."""

    path = Path(source).expanduser().resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"profil de contribution illisible {path}: {exc}") from exc
    profile = ControllerProfile.from_dict(raw)
    if expected_profile_id is not None and profile.id != expected_profile_id:
        raise ProfileError(
            f"le profil lu ({profile.id}) ne correspond pas à la sélection "
            f"({expected_profile_id})"
        )
    raw["status"] = "community"
    community_profile = ControllerProfile.from_dict(raw)
    payload = json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
    return community_profile, payload


def controller_submission_url(
    profile: ControllerProfile,
    *,
    repository: str = DEFAULT_CONTRIBUTION_REPOSITORY,
    payload: str | None = None,
) -> str:
    """Build a pre-filled public contribution form URL.

    GitHub still performs the final authenticated confirmation in the browser;
    the application never embeds or collects a user access token.
    """

    if repository.count("/") != 1 or any(character in repository for character in "\r\n?#"):
        raise ValueError("repository doit respecter la forme propriétaire/dépôt")
    title = f"Controller profile: {profile.manufacturer} {profile.model}"
    query_fields = {
        "template": CONTROLLER_ISSUE_TEMPLATE,
        "title": title,
    }
    if payload is not None:
        compact_payload = json.dumps(
            json.loads(payload), ensure_ascii=False, separators=(",", ":")
        )
        query_fields["body"] = controller_submission_body(profile, compact_payload)
    query = urlencode(query_fields, quote_via=quote)
    return f"https://github.com/{repository}/issues/new?{query}"


def controller_submission_body(profile: ControllerProfile, payload: str) -> str:
    """Return a complete bilingual issue body with no personal machine data."""

    return f"""## Contrôleur / Controller

{profile.manufacturer} {profile.model}

## Profil JSON / JSON profile

```json
{payload.strip()}
```

## Source MIDI et test matériel / MIDI source and hardware test

- Documentation:
- Firmware: {profile.firmware or '—'}
- Testé sur le matériel / Tested on hardware: oui / yes — non / no
- Entrée MIDI / MIDI input:
- Retour MIDI / MIDI feedback:
- Remarques / Notes:

## Validation

- [ ] Le profil ne contient aucun code exécutable. / The profile contains no executable code.
- [ ] J’autorise sa publication sous la licence du dépôt. / I agree to its publication under the repository license.
"""
