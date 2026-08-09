from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import tempfile

from ...formats.juce_value_tree import (
    ValueTree,
    ValueTreeFormatError,
    parse_tree,
    write_tree,
)

from ...models import ControllerProfile


ROTARY_ADDRESS = re.compile(r"^/Companion/Rotary(\d+)$", re.IGNORECASE)
BUTTON_ADDRESS = re.compile(
    r"^/Companion/GenericButtons/Button(\d+)$",
    re.IGNORECASE,
)
MAX_COMPANION_ROTARIES = 99
MAX_COMPANION_BUTTONS = 16


class LiveProfessorControllerExportError(ValueError):
    """Raised when a controller profile cannot be exported safely to CTRL2."""


@dataclass(frozen=True, slots=True)
class LiveProfessorControllerExport:
    path: Path
    profile_id: str
    controller_name: str
    controller_uid: int
    rotary_count: int
    button_count: int
    sha256: str


def default_companion_template() -> Path:
    return Path(__file__).parents[2] / "resources" / "liveprofessor-companion-99.ctrl2"


def _child(tree: ValueTree, type_name: str) -> ValueTree:
    try:
        return next(child for child in tree.children if child.type_name == type_name)
    except StopIteration as exc:
        raise LiveProfessorControllerExportError(
            f"le modèle LiveProfessor ne contient pas le nœud {type_name}"
        ) from exc


def logical_rotary_count(profile: ControllerProfile) -> int:
    per_page = sum(
        sum(control.supports_rotation for control in profile.controls_for_bank(bank))
        for bank in range(profile.bank_count)
    )
    return per_page * profile.page_count


def bank_rotary_count(profile: ControllerProfile) -> int:
    """Return the physical rotary count exposed in one controller bank."""

    return sum(control.supports_rotation for control in profile.controls_for_bank(0))


def _physical_button_count(profile: ControllerProfile) -> int:
    return sum(control.supports_press for control in profile.controls[: profile.bank_size])


def _stable_controller_uid(profile_id: str) -> int:
    digest = hashlib.sha256(f"silemio-control-hub:{profile_id}".encode("utf-8")).digest()
    return 100_000_000 + int.from_bytes(digest[:4], "big") % 2_000_000_000


def _prepare_tree(
    profile: ControllerProfile,
    template: Path,
    *,
    controller_name: str | None,
    osc_in_port: int,
    osc_out_port: int,
    rotary_count: int | None = None,
    controller_uid: int | None = None,
) -> tuple[ValueTree, int, int]:
    try:
        tree = parse_tree(template.read_bytes())
    except (OSError, ValueTreeFormatError) as exc:
        raise LiveProfessorControllerExportError(
            f"modèle LiveProfessor illisible {template}: {exc}"
        ) from exc
    if tree.type_name != "LPController":
        raise LiveProfessorControllerExportError(
            "le modèle fourni n'est pas un contrôleur LiveProfessor .ctrl2"
        )
    if str(tree.get("ControllerType", "")).casefold() != "companion":
        raise LiveProfessorControllerExportError(
            "le modèle fourni n'est pas un contrôleur Companion"
        )
    for label, port in (("osc_in_port", osc_in_port), ("osc_out_port", osc_out_port)):
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise LiveProfessorControllerExportError(f"{label} doit être compris entre 1 et 65535")

    logical_count = logical_rotary_count(profile)
    rotary_count = logical_count if rotary_count is None else rotary_count
    if not isinstance(rotary_count, int) or rotary_count < 1:
        raise LiveProfessorControllerExportError(
            "rotary_count doit être un entier positif"
        )
    if rotary_count > logical_count:
        raise LiveProfessorControllerExportError(
            f"{rotary_count} contrôles demandés, mais le profil {profile.display_name} "
            f"n'en expose que {logical_count}"
        )
    if not 1 <= rotary_count <= MAX_COMPANION_ROTARIES:
        raise LiveProfessorControllerExportError(
            f"{rotary_count} contrôles rotatifs logiques demandés; "
            f"l'export Companion v1 en accepte de 1 à {MAX_COMPANION_ROTARIES}"
        )
    button_count = _physical_button_count(profile)
    if button_count > MAX_COMPANION_BUTTONS:
        raise LiveProfessorControllerExportError(
            f"{button_count} boutons physiques demandés; "
            f"l'export Companion v1 en accepte au plus {MAX_COMPANION_BUTTONS}"
        )

    name = (controller_name or f"SiLeMI/O - {profile.display_name}").strip()
    if not name:
        raise LiveProfessorControllerExportError("le nom du contrôleur est vide")
    if controller_uid is not None and (
        not isinstance(controller_uid, int) or not 1 <= controller_uid <= 2_147_483_647
    ):
        raise LiveProfessorControllerExportError(
            "controller_uid doit être un entier compris entre 1 et 2147483647"
        )
    tree.set("ControllerName", name)
    tree.set(
        "uID",
        controller_uid if controller_uid is not None else _stable_controller_uid(profile.id),
    )
    tree.set("OSCInPort", osc_in_port)
    tree.set("OSCOutPort", osc_out_port)
    tree.set("OSChostIp", "127.0.0.1")

    controls = _child(tree, "Controls")
    kept: list[ValueTree] = []
    seen_rotaries: set[int] = set()
    seen_buttons: set[int] = set()
    for control in controls.children:
        address = str(control.get("OSCAddressPatern", ""))
        rotary_match = ROTARY_ADDRESS.fullmatch(address)
        button_match = BUTTON_ADDRESS.fullmatch(address)
        if rotary_match:
            number = int(rotary_match.group(1))
            if number <= rotary_count:
                if number in seen_rotaries:
                    raise LiveProfessorControllerExportError(
                        f"le modèle contient plusieurs Rotary {number}"
                    )
                seen_rotaries.add(number)
                kept.append(control)
            continue
        if button_match:
            number = int(button_match.group(1))
            if number <= button_count:
                if number in seen_buttons:
                    raise LiveProfessorControllerExportError(
                        f"le modèle contient plusieurs Generic Button {number}"
                    )
                seen_buttons.add(number)
                kept.append(control)
            continue
        kept.append(control)
    expected_rotaries = set(range(1, rotary_count + 1))
    expected_buttons = set(range(1, button_count + 1))
    if seen_rotaries != expected_rotaries or seen_buttons != expected_buttons:
        raise LiveProfessorControllerExportError(
            "le modèle Companion ne contient pas tous les contrôles demandés"
        )
    controls.children = kept

    map_presets = _child(tree, "MapPresets")
    map_presets.children = []
    return tree, rotary_count, button_count


def export_liveprofessor_controller(
    profile: ControllerProfile,
    destination: Path,
    *,
    replace: bool = False,
    controller_name: str | None = None,
    osc_in_port: int = 8010,
    osc_out_port: int = 8011,
    rotary_count: int | None = None,
    controller_uid: int | None = None,
    template: Path | None = None,
) -> LiveProfessorControllerExport:
    """Create a neutral Companion CTRL2 without touching LiveProfessor projects."""

    destination = Path(destination).expanduser().resolve()
    if destination.suffix.casefold() != ".ctrl2":
        raise LiveProfessorControllerExportError("la destination doit porter l'extension .ctrl2")
    if destination.exists() and not replace:
        raise LiveProfessorControllerExportError(
            f"{destination} existe déjà; utilisez --replace pour le remplacer"
        )
    source = Path(template or default_companion_template()).expanduser().resolve()
    tree, rotary_count, button_count = _prepare_tree(
        profile,
        source,
        controller_name=controller_name,
        osc_in_port=osc_in_port,
        osc_out_port=osc_out_port,
        rotary_count=rotary_count,
        controller_uid=controller_uid,
    )
    payload = write_tree(tree)
    try:
        verified = parse_tree(payload)
    except ValueTreeFormatError as exc:
        raise LiveProfessorControllerExportError(
            f"le fichier généré ne repasse pas la validation ValueTree: {exc}"
        ) from exc
    if verified.type_name != "LPController":
        raise LiveProfessorControllerExportError("le fichier généré a une racine invalide")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.stem}-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return LiveProfessorControllerExport(
        path=destination,
        profile_id=profile.id,
        controller_name=str(tree.get("ControllerName")),
        controller_uid=int(tree.get("uID")),
        rotary_count=rotary_count,
        button_count=button_count,
        sha256=hashlib.sha256(payload).hexdigest().upper(),
    )
