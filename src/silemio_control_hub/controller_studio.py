"""Safe helpers used by the in-app controller profile editor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from typing import Any

from .models import ControllerProfile, ProfileError
from .registry import default_user_profile_dir


_SAFE_ID_PART = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class ControllerProfileSave:
    profile: ControllerProfile
    path: Path
    backup_path: Path | None


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    return _SAFE_ID_PART.sub("-", ascii_value).strip("-")


def suggest_controller_profile_id(manufacturer: str, model: str) -> str:
    """Return a stable, schema-compatible identifier suggested from visible fields."""

    maker = _slug(manufacturer) or "custom"
    product = _slug(model) or "controller"
    return f"{maker}.{product}"


def _binding_payload(binding) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": binding.message.value}
    if binding.channel is not None:
        payload["channel"] = binding.channel
    if binding.number is not None:
        payload["number"] = binding.number
    if binding.mode is not None:
        payload["mode"] = binding.mode
    return payload


def controller_profile_payload(profile: ControllerProfile) -> dict[str, Any]:
    """Serialize a validated profile without relying on dataclass implementation details."""

    controls: list[dict[str, Any]] = []
    for control in profile.controls:
        item: dict[str, Any] = {
            "id": control.id,
            "kind": control.kind.value,
            "input": _binding_payload(control.input),
        }
        if control.push is not None:
            item["push"] = _binding_payload(control.push)
        if control.touch is not None:
            item["touch"] = _binding_payload(control.touch)
        if control.feedback is not None:
            feedback: dict[str, Any] = {}
            for field in ("value", "led", "color"):
                binding = getattr(control.feedback, field)
                if binding is not None:
                    feedback[field] = _binding_payload(binding)
            if control.feedback.supported_colors:
                feedback["supported_colors"] = list(control.feedback.supported_colors)
            item["feedback"] = feedback
        if control.display_cell is not None:
            item["display_cell"] = control.display_cell
        if control.roles:
            item["roles"] = list(control.roles)
        controls.append(item)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "profile_version": profile.profile_version,
        "id": profile.id,
        "manufacturer": profile.manufacturer,
        "model": profile.model,
        "midi_identity": {
            "input_name_patterns": list(profile.midi_identity.input_name_patterns),
            "output_name_patterns": list(profile.midi_identity.output_name_patterns),
        },
        "bank_size": profile.bank_size,
        "bank_count": profile.bank_count,
        "page_count": profile.page_count,
        "status": "community",
        "capabilities": list(profile.capabilities),
        "controls": controls,
    }
    if profile.firmware is not None:
        payload["firmware"] = profile.firmware
    if profile.last_bank_size is not None:
        payload["last_bank_size"] = profile.last_bank_size
    if profile.modifiers:
        payload["modifiers"] = [
            {
                "id": modifier.id,
                "input": _binding_payload(modifier.input),
                "behavior": modifier.behavior.value,
            }
            for modifier in profile.modifiers
        ]
    return payload


def editable_controller_payload(profile: ControllerProfile, *, duplicate: bool) -> dict[str, Any]:
    """Create a safe editor draft, optionally as a new personal derivative."""

    payload = controller_profile_payload(profile)
    payload["status"] = "community"
    if duplicate:
        payload["id"] = f"{profile.id}.custom"
        payload["model"] = f"{profile.model} Custom"
        payload["profile_version"] = "1.0.0"
    return payload


def default_controller_payload() -> dict[str, Any]:
    """Return an immediately editable eight-encoder starter profile."""

    controls = [
        {
            "id": f"encoder_{index:02d}",
            "kind": "absolute_encoder",
            "input": {"message": "cc", "channel": 1, "number": index - 1},
        }
        for index in range(1, 9)
    ]
    return {
        "schema_version": 1,
        "profile_version": "1.0.0",
        "id": "custom.controller",
        "manufacturer": "Custom",
        "model": "MIDI Controller",
        "midi_identity": {"input_name_patterns": [], "output_name_patterns": []},
        "bank_size": 8,
        "bank_count": 1,
        "page_count": 1,
        "status": "community",
        "capabilities": ["commands"],
        "controls": controls,
    }


def derived_capabilities(payload: dict[str, Any]) -> list[str]:
    """Keep declared hardware capabilities and add every capability required by the draft."""

    capabilities = {
        item for item in payload.get("capabilities", []) if isinstance(item, str)
    }
    capabilities.add("commands")
    controls = payload.get("controls", [])
    if any(item.get("push") is not None for item in controls):
        capabilities.add("push")
    if any(item.get("touch") is not None for item in controls):
        capabilities.add("touch")
    if any(item.get("display_cell") is not None for item in controls):
        capabilities.add("display")
    for item in controls:
        feedback = item.get("feedback") or {}
        if feedback.get("value") is not None:
            capabilities.add("values")
        if feedback.get("led") is not None:
            capabilities.add("led")
        if feedback.get("color") is not None:
            capabilities.add("colors")
        bindings = [item.get("input"), item.get("push"), item.get("touch")]
        if any(binding and binding.get("message") == "nrpn" for binding in bindings):
            capabilities.add("high_resolution")
        if any(binding and binding.get("message") == "sysex" for binding in bindings):
            capabilities.add("sysex")
    if int(payload.get("bank_count", 1)) > 1:
        capabilities.add("banks")
    if int(payload.get("page_count", 1)) > 1:
        capabilities.add("pages")
    if payload.get("modifiers"):
        capabilities.add("modifiers")
    return sorted(capabilities)


def validate_controller_draft(payload: dict[str, Any]) -> tuple[ControllerProfile, dict[str, Any]]:
    """Normalize editor data and run the same strict model used by the library."""

    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["schema_version"] = 1
    normalized["status"] = "community"
    normalized["capabilities"] = derived_capabilities(normalized)
    midi_identity = normalized.setdefault("midi_identity", {})
    midi_identity.setdefault("input_name_patterns", [])
    midi_identity.setdefault("output_name_patterns", [])
    profile = ControllerProfile.from_dict(normalized)
    return profile, normalized


def save_user_controller_profile(
    payload: dict[str, Any],
    *,
    directory: Path | None = None,
    replace: bool = False,
) -> ControllerProfileSave:
    """Validate and atomically save a declarative user profile, with rollback backup."""

    profile, normalized = validate_controller_draft(payload)
    root = Path(directory or default_user_profile_dir()).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{profile.id}.json"
    if destination.exists() and not replace:
        raise ProfileError(f"{destination.name} existe déjà")

    current = destination.read_text(encoding="utf-8") if destination.exists() else None
    if current is not None:
        try:
            current_payload = json.loads(current)
            current_profile = ControllerProfile.from_dict(current_payload)
        except (json.JSONDecodeError, ProfileError) as exc:
            raise ProfileError(f"profil personnel existant illisible {destination}: {exc}") from exc
        if current_payload != normalized:
            current_version = tuple(
                int(part) for part in current_profile.profile_version.split("-", 1)[0].split(".")
            )
            proposed_version = tuple(
                int(part) for part in profile.profile_version.split("-", 1)[0].split(".")
            )
            if proposed_version <= current_version:
                normalized["profile_version"] = (
                    f"{current_version[0]}.{current_version[1]}.{current_version[2] + 1}"
                )
                profile = ControllerProfile.from_dict(normalized)

    serialized = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    backup_path: Path | None = None
    temporary_path: Path | None = None
    try:
        if destination.exists():
            assert current is not None
            if current != serialized:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                backup_root = root / "backups"
                backup_root.mkdir(parents=True, exist_ok=True)
                backup_path = backup_root / f"{profile.id}-{stamp}.json"
                backup_path.write_text(current, encoding="utf-8")
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=root,
            prefix=f".{profile.id}-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return ControllerProfileSave(profile, destination, backup_path)


def midi_binding_from_message(message: Any) -> dict[str, Any] | None:
    """Convert one common mido input message into a declarative profile binding."""

    message_type = str(getattr(message, "type", ""))
    channel = getattr(message, "channel", None)
    if message_type == "control_change":
        return {
            "message": "cc",
            "channel": int(channel) + 1,
            "number": int(message.control),
        }
    if message_type in {"note_on", "note_off"}:
        if message_type == "note_on" and int(getattr(message, "velocity", 0)) == 0:
            return None
        return {
            "message": "note",
            "channel": int(channel) + 1,
            "number": int(message.note),
        }
    if message_type == "pitchwheel":
        return {"message": "pitch_bend", "channel": int(channel) + 1}
    return None
