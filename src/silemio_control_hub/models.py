from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any


class ProfileError(ValueError):
    """Raised when a controller profile is invalid."""


PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PROFILE_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
KNOWN_CAPABILITIES = frozenset(
    {
        "commands",
        "push",
        "touch",
        "led",
        "labels",
        "values",
        "colors",
        "display",
        "high_resolution",
        "motorized",
        "sysex",
        "banks",
        "pages",
        "modifiers",
    }
)
RELATIVE_MODES = frozenset(
    {"twos_complement", "binary_offset", "signed_bit", "increment_decrement"}
)


def _reject_unknown(raw: dict[str, Any], allowed: set[str], *, location: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        fields = ", ".join(unknown)
        raise ProfileError(f"{location} contient des champs inconnus: {fields}")


class ControlKind(StrEnum):
    RELATIVE_ENCODER = "relative_encoder"
    ABSOLUTE_ENCODER = "absolute_encoder"
    FADER = "fader"
    BUTTON = "button"
    PAD = "pad"


class MessageKind(StrEnum):
    CC = "cc"
    NOTE = "note"
    NRPN = "nrpn"
    PITCH_BEND = "pitch_bend"
    SYSEX = "sysex"


class ModifierBehavior(StrEnum):
    MOMENTARY = "momentary"
    TOGGLE = "toggle"


@dataclass(frozen=True, slots=True)
class MidiBinding:
    message: MessageKind
    channel: int | None = None
    number: int | None = None
    mode: str | None = None

    @property
    def identity(self) -> tuple[MessageKind, int | None, int | None, str | None]:
        mode = self.mode if self.message == MessageKind.SYSEX else None
        return self.message, self.channel, self.number, mode

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, location: str) -> "MidiBinding":
        if not isinstance(raw, dict):
            raise ProfileError(f"{location} doit être un objet")
        _reject_unknown(raw, {"message", "channel", "number", "mode"}, location=location)
        try:
            message = MessageKind(str(raw["message"]))
        except (KeyError, ValueError) as exc:
            raise ProfileError(f"{location}.message est absent ou inconnu") from exc
        channel = raw.get("channel")
        number = raw.get("number")
        mode = raw.get("mode")
        if mode is not None and (not isinstance(mode, str) or not mode.strip()):
            raise ProfileError(f"{location}.mode doit être un texte non vide")
        if message == MessageKind.SYSEX:
            if channel is not None or number is not None:
                raise ProfileError(f"{location} SysEx ne doit pas définir channel ou number")
            if mode is None:
                raise ProfileError(f"{location}.mode est requis pour identifier un message SysEx")
        else:
            if not isinstance(channel, int) or not 1 <= channel <= 16:
                raise ProfileError(f"{location}.channel doit être compris entre 1 et 16")
        if message in {MessageKind.CC, MessageKind.NOTE, MessageKind.NRPN}:
            if not isinstance(number, int) or not 0 <= number <= 16383:
                raise ProfileError(f"{location}.number est invalide")
            if message in {MessageKind.CC, MessageKind.NOTE} and number > 127:
                raise ProfileError(f"{location}.number doit être compris entre 0 et 127")
        elif number is not None:
            raise ProfileError(f"{location}.number n'est pas accepté pour {message.value}")
        return cls(message=message, channel=channel, number=number, mode=mode)


@dataclass(frozen=True, slots=True)
class MidiIdentity:
    input_name_patterns: tuple[str, ...] = ()
    output_name_patterns: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MidiIdentity":
        location = "midi_identity"
        if not isinstance(raw, dict):
            raise ProfileError(f"{location} doit être un objet")
        _reject_unknown(raw, {"input_name_patterns", "output_name_patterns"}, location=location)

        def patterns(field: str) -> tuple[str, ...]:
            value = raw.get(field, [])
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise ProfileError(f"{location}.{field} doit être une liste de textes non vides")
            cleaned = tuple(item.strip() for item in value)
            if len(cleaned) != len(set(cleaned)):
                raise ProfileError(f"{location}.{field} contient des doublons")
            return cleaned

        return cls(patterns("input_name_patterns"), patterns("output_name_patterns"))


@dataclass(frozen=True, slots=True)
class FeedbackDefinition:
    value: MidiBinding | None = None
    led: MidiBinding | None = None
    color: MidiBinding | None = None
    supported_colors: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, location: str) -> "FeedbackDefinition":
        if not isinstance(raw, dict):
            raise ProfileError(f"{location} doit être un objet")
        _reject_unknown(
            raw,
            {"value", "led", "color", "supported_colors"},
            location=location,
        )

        def binding(field: str) -> MidiBinding | None:
            value = raw.get(field)
            return (
                MidiBinding.from_dict(value, location=f"{location}.{field}")
                if value is not None
                else None
            )

        colors = raw.get("supported_colors", [])
        if not isinstance(colors, list) or not all(
            isinstance(item, str) and item.strip() for item in colors
        ):
            raise ProfileError(f"{location}.supported_colors doit être une liste de textes")
        cleaned_colors = tuple(item.strip() for item in colors)
        if len(cleaned_colors) != len(set(cleaned_colors)):
            raise ProfileError(f"{location}.supported_colors contient des doublons")
        return cls(binding("value"), binding("led"), binding("color"), cleaned_colors)


@dataclass(frozen=True, slots=True)
class ControlDefinition:
    id: str
    kind: ControlKind
    input: MidiBinding
    push: MidiBinding | None = None
    touch: MidiBinding | None = None
    feedback: FeedbackDefinition | None = None
    display_cell: int | None = None
    roles: tuple[str, ...] = ()

    @property
    def supports_rotation(self) -> bool:
        return self.kind in {
            ControlKind.RELATIVE_ENCODER,
            ControlKind.ABSOLUTE_ENCODER,
            ControlKind.FADER,
        }

    @property
    def supports_press(self) -> bool:
        return self.push is not None or self.kind in {ControlKind.BUTTON, ControlKind.PAD}

    @property
    def supports_touch(self) -> bool:
        return self.touch is not None

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, index: int) -> "ControlDefinition":
        location = f"controls[{index}]"
        if not isinstance(raw, dict):
            raise ProfileError(f"{location} doit être un objet")
        _reject_unknown(
            raw,
            {"id", "kind", "input", "push", "touch", "feedback", "display_cell", "roles"},
            location=location,
        )
        try:
            control_id = str(raw["id"]).strip()
            kind = ControlKind(str(raw["kind"]))
            input_binding = MidiBinding.from_dict(raw["input"], location=f"{location}.input")
        except KeyError as exc:
            raise ProfileError(f"{location}.{exc.args[0]} est absent") from exc
        except ValueError as exc:
            if isinstance(exc, ProfileError):
                raise
            raise ProfileError(f"{location}.kind est inconnu") from exc
        if not control_id or not PROFILE_ID.fullmatch(control_id):
            raise ProfileError(f"{location}.id est vide ou contient des caractères interdits")
        if kind == ControlKind.RELATIVE_ENCODER and input_binding.mode not in RELATIVE_MODES:
            raise ProfileError(
                f"{location}.input.mode doit décrire un mode relatif pris en charge"
            )
        push_raw = raw.get("push")
        push = (
            MidiBinding.from_dict(push_raw, location=f"{location}.push")
            if push_raw is not None
            else None
        )
        touch_raw = raw.get("touch")
        touch = (
            MidiBinding.from_dict(touch_raw, location=f"{location}.touch")
            if touch_raw is not None
            else None
        )
        feedback_raw = raw.get("feedback")
        feedback = (
            FeedbackDefinition.from_dict(feedback_raw, location=f"{location}.feedback")
            if feedback_raw is not None
            else None
        )
        display_cell = raw.get("display_cell")
        if display_cell is not None and (not isinstance(display_cell, int) or display_cell < 1):
            raise ProfileError(f"{location}.display_cell doit être un entier positif")
        roles_raw = raw.get("roles", [])
        if not isinstance(roles_raw, list) or not all(
            isinstance(item, str) and item.strip() for item in roles_raw
        ):
            raise ProfileError(f"{location}.roles doit être une liste de textes")
        roles = tuple(item.strip() for item in roles_raw)
        if len(roles) != len(set(roles)):
            raise ProfileError(f"{location}.roles contient des doublons")
        return cls(control_id, kind, input_binding, push, touch, feedback, display_cell, roles)


@dataclass(frozen=True, slots=True)
class ModifierDefinition:
    id: str
    input: MidiBinding
    behavior: ModifierBehavior = ModifierBehavior.MOMENTARY

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, index: int) -> "ModifierDefinition":
        location = f"modifiers[{index}]"
        if not isinstance(raw, dict):
            raise ProfileError(f"{location} doit être un objet")
        _reject_unknown(raw, {"id", "input", "behavior"}, location=location)
        try:
            modifier_id = str(raw["id"]).strip()
            binding = MidiBinding.from_dict(raw["input"], location=f"{location}.input")
            behavior = ModifierBehavior(str(raw.get("behavior", "momentary")))
        except KeyError as exc:
            raise ProfileError(f"{location}.{exc.args[0]} est absent") from exc
        except ValueError as exc:
            if isinstance(exc, ProfileError):
                raise
            raise ProfileError(f"{location}.behavior est inconnu") from exc
        if not modifier_id or not PROFILE_ID.fullmatch(modifier_id):
            raise ProfileError(f"{location}.id est vide ou contient des caractères interdits")
        return cls(modifier_id, binding, behavior)


@dataclass(frozen=True, slots=True)
class ControllerProfile:
    schema_version: int
    id: str
    manufacturer: str
    model: str
    bank_size: int
    controls: tuple[ControlDefinition, ...]
    capabilities: tuple[str, ...]
    profile_version: str = "1.0.0"
    firmware: str | None = None
    status: str = "community"
    midi_identity: MidiIdentity = MidiIdentity()
    bank_count: int = 1
    last_bank_size: int | None = None
    page_count: int = 1
    modifiers: tuple[ModifierDefinition, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ControllerProfile":
        if not isinstance(raw, dict):
            raise ProfileError("le profil doit être un objet JSON")
        _reject_unknown(
            raw,
            {
                "schema_version",
                "profile_version",
                "id",
                "manufacturer",
                "model",
                "firmware",
                "midi_identity",
                "bank_size",
                "bank_count",
                "last_bank_size",
                "page_count",
                "status",
                "capabilities",
                "controls",
                "modifiers",
            },
            location="profil",
        )
        if raw.get("schema_version") != 1:
            raise ProfileError("schema_version doit valoir 1")
        profile_version = raw.get("profile_version", "1.0.0")
        if not isinstance(profile_version, str) or not PROFILE_VERSION.fullmatch(profile_version):
            raise ProfileError("profile_version doit respecter la forme 1.2.3")
        required_text = ("id", "manufacturer", "model")
        for field_name in required_text:
            if not isinstance(raw.get(field_name), str) or not raw[field_name].strip():
                raise ProfileError(f"{field_name} est absent ou vide")
        if not PROFILE_ID.fullmatch(raw["id"].strip()):
            raise ProfileError("id contient des caractères interdits")
        firmware = raw.get("firmware")
        if firmware is not None and (not isinstance(firmware, str) or not firmware.strip()):
            raise ProfileError("firmware doit être un texte non vide")
        bank_size = raw.get("bank_size")
        if not isinstance(bank_size, int) or bank_size < 1:
            raise ProfileError("bank_size doit être un entier positif")
        bank_count = raw.get("bank_count", 1)
        if not isinstance(bank_count, int) or bank_count < 1:
            raise ProfileError("bank_count doit être un entier positif")
        last_bank_size = raw.get("last_bank_size")
        if last_bank_size is not None and (
            not isinstance(last_bank_size, int) or not 1 <= last_bank_size <= bank_size
        ):
            raise ProfileError("last_bank_size doit être compris entre 1 et bank_size")
        page_count = raw.get("page_count", 1)
        if not isinstance(page_count, int) or page_count < 1:
            raise ProfileError("page_count doit être un entier positif")
        controls_raw = raw.get("controls")
        if not isinstance(controls_raw, list) or not controls_raw:
            raise ProfileError("controls doit contenir au moins un contrôle")
        controls = tuple(
            ControlDefinition.from_dict(item, index=index)
            for index, item in enumerate(controls_raw)
        )
        control_ids = [control.id for control in controls]
        if len(control_ids) != len(set(control_ids)):
            raise ProfileError("les identifiants de contrôles doivent être uniques")
        if bank_size > len(controls):
            raise ProfileError("bank_size ne peut pas dépasser le nombre de contrôles")
        capabilities = raw.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(
            isinstance(item, str) and item.strip() for item in capabilities
        ):
            raise ProfileError("capabilities doit être une liste de textes")
        normalized_capabilities = tuple(item.strip() for item in capabilities)
        if len(normalized_capabilities) != len(set(normalized_capabilities)):
            raise ProfileError("capabilities contient des doublons")
        unknown_capabilities = sorted(set(normalized_capabilities) - KNOWN_CAPABILITIES)
        if unknown_capabilities:
            raise ProfileError(
                "capabilities contient des valeurs inconnues: " + ", ".join(unknown_capabilities)
            )
        status = str(raw.get("status", "community"))
        if status not in {"builtin", "verified", "community"}:
            raise ProfileError("status doit valoir builtin, verified ou community")
        midi_raw = raw.get("midi_identity", {})
        midi_identity = MidiIdentity.from_dict(midi_raw)
        modifiers_raw = raw.get("modifiers", [])
        if not isinstance(modifiers_raw, list):
            raise ProfileError("modifiers doit être une liste")
        modifiers = tuple(
            ModifierDefinition.from_dict(item, index=index)
            for index, item in enumerate(modifiers_raw)
        )
        modifier_ids = [modifier.id for modifier in modifiers]
        if len(modifier_ids) != len(set(modifier_ids)):
            raise ProfileError("les identifiants de modificateurs doivent être uniques")
        if set(control_ids) & set(modifier_ids):
            raise ProfileError("un contrôle et un modificateur ne peuvent pas partager le même id")

        if bank_count > 1 and "banks" not in normalized_capabilities:
            raise ProfileError("la capacité banks est requise lorsque bank_count dépasse 1")
        if page_count > 1 and "pages" not in normalized_capabilities:
            raise ProfileError("la capacité pages est requise lorsque page_count dépasse 1")
        if modifiers and "modifiers" not in normalized_capabilities:
            raise ProfileError("la capacité modifiers est requise lorsqu'un modificateur est déclaré")
        if any(control.supports_touch for control in controls) and "touch" not in normalized_capabilities:
            raise ProfileError("la capacité touch est requise lorsqu'un toucher est déclaré")

        input_bindings: dict[tuple[MessageKind, int | None, int | None, str | None], str] = {}
        for control in controls:
            for binding, label in (
                (control.input, f"{control.id}.input"),
                (control.push, f"{control.id}.push"),
                (control.touch, f"{control.id}.touch"),
            ):
                if binding is None:
                    continue
                previous = input_bindings.get(binding.identity)
                if previous is not None:
                    raise ProfileError(f"liaison MIDI dupliquée entre {previous} et {label}")
                input_bindings[binding.identity] = label
        for modifier in modifiers:
            previous = input_bindings.get(modifier.input.identity)
            if previous is not None:
                raise ProfileError(
                    f"liaison MIDI dupliquée entre {previous} et {modifier.id}.modifier"
                )
            input_bindings[modifier.input.identity] = f"{modifier.id}.modifier"

        return cls(
            schema_version=1,
            id=raw["id"].strip(),
            manufacturer=raw["manufacturer"].strip(),
            model=raw["model"].strip(),
            bank_size=bank_size,
            controls=controls,
            capabilities=normalized_capabilities,
            profile_version=profile_version,
            firmware=firmware.strip() if firmware is not None else None,
            status=status,
            midi_identity=midi_identity,
            bank_count=bank_count,
            last_bank_size=last_bank_size,
            page_count=page_count,
            modifiers=modifiers,
        )

    @property
    def display_name(self) -> str:
        return f"{self.manufacturer} {self.model}"

    def control(self, control_id: str) -> ControlDefinition:
        try:
            return next(item for item in self.controls if item.id == control_id)
        except StopIteration as exc:
            raise KeyError(f"contrôle inconnu: {control_id}") from exc

    def controls_for_bank(self, bank: int) -> tuple[ControlDefinition, ...]:
        if not 0 <= bank < self.bank_count:
            raise IndexError(f"banque hors plage: {bank}")
        size = (
            self.last_bank_size
            if bank == self.bank_count - 1 and self.last_bank_size is not None
            else self.bank_size
        )
        return self.controls[:size]
