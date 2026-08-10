from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from silemio_control_hub.controller_contribution import (
    controller_submission_body,
    controller_submission_url,
    validated_controller_payload,
)
from silemio_control_hub.models import ProfileError


def _profile(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profile_version": "1.0.0",
                "id": "acme.knob",
                "manufacturer": "ACME & Sons",
                "model": "Knob / One",
                "bank_size": 1,
                "status": "verified",
                "capabilities": ["commands"],
                "controls": [
                    {
                        "id": "encoder_01",
                        "kind": "absolute_encoder",
                        "input": {"message": "cc", "channel": 1, "number": 10},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_contribution_payload_is_validated_canonical_and_community(tmp_path: Path):
    profile, payload = validated_controller_payload(_profile(tmp_path / "profile.json"))

    assert profile.id == "acme.knob"
    assert profile.status == "community"
    assert json.loads(payload)["status"] == "community"
    assert payload.endswith("\n")


def test_contribution_payload_rejects_a_mismatched_selection(tmp_path: Path):
    with pytest.raises(ProfileError, match="ne correspond pas"):
        validated_controller_payload(
            _profile(tmp_path / "profile.json"), expected_profile_id="other.controller"
        )


def test_submission_url_targets_the_product_repository_and_template(tmp_path: Path):
    profile, _payload = validated_controller_payload(_profile(tmp_path / "profile.json"))
    url = controller_submission_url(profile)
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)

    assert parsed.netloc == "github.com"
    assert parsed.path == "/Mamat79/Controller-Studio-for-LiveProfessor/issues/new"
    assert query["template"] == ["controller-profile.md"]
    assert query["title"] == ["Controller profile: ACME & Sons Knob / One"]


def test_submission_url_can_prefill_the_complete_validated_profile(tmp_path: Path):
    profile, payload = validated_controller_payload(_profile(tmp_path / "profile.json"))
    url = controller_submission_url(profile, payload=payload)
    body = parse_qs(urlsplit(url).query)["body"][0]

    assert "ACME & Sons Knob / One" in body
    assert '"id":"acme.knob"' in body
    assert "```json" in body
    assert controller_submission_body(profile, "{}").startswith("## Contrôleur")
