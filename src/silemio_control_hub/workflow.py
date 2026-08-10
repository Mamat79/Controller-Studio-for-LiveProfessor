from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from collections.abc import Iterable
import tempfile

from .adapters.hosts import (
    LiveProfessorControllerExport,
    LiveProfessorHostAdapter,
    export_liveprofessor_controller,
)
from .adapters.hosts.liveprofessor_automap import AutoMapResult
from .models import ControllerProfile
from .plugin_profiles import PluginProfile


class LiveProfessorPreparationError(ValueError):
    """Raised when the safe profile-to-AutoMap workflow cannot proceed."""


@dataclass(frozen=True, slots=True)
class LiveProfessorPreparation:
    profile_id: str
    source_project: Path
    source_sha256: str
    controller: LiveProfessorControllerExport
    automap: AutoMapResult


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def prepare_liveprofessor_project(
    profile: ControllerProfile,
    source_project: Path,
    destination_project: Path,
    controller_destination: Path,
    *,
    plugin_uid: int | None = None,
    plugin_uids: Iterable[int] | None = None,
    project_controller_uid: int | None = None,
    embed_new_controller: bool = False,
    target_rotary_count: int | None = None,
    replace_controller: bool = False,
    replace_project: bool = False,
    controller_name: str | None = None,
    osc_in_port: int = 8010,
    osc_out_port: int = 8011,
    plugin_profiles: Iterable[PluginProfile] = (),
) -> LiveProfessorPreparation:
    """Generate a CTRL2 and an AutoMapped project copy from one profile."""

    source = Path(source_project).expanduser().resolve()
    destination = Path(destination_project).expanduser().resolve()
    controller_path = Path(controller_destination).expanduser().resolve()
    if not source.is_file():
        raise LiveProfessorPreparationError(f"projet source introuvable: {source}")
    if source.suffix.casefold() != ".rack2":
        raise LiveProfessorPreparationError("le projet source doit porter l'extension .rack2")
    if destination.suffix.casefold() != ".rack2":
        raise LiveProfessorPreparationError(
            "la copie AutoMap doit porter l'extension .rack2"
        )
    if source == destination:
        raise LiveProfessorPreparationError(
            "la destination AutoMap doit être différente du projet source"
        )
    if destination.exists() and not replace_project:
        raise LiveProfessorPreparationError(
            f"{destination} existe déjà; autorisez explicitement son remplacement"
        )

    source_hash = _sha256(source)
    if embed_new_controller and project_controller_uid is not None:
        raise LiveProfessorPreparationError(
            "choisissez soit un contrôleur existant, soit un nouveau contrôleur"
        )

    # Inspect with a disposable template first. This keeps the requested .ctrl2
    # destination untouched until every controller-selection check has passed.
    with tempfile.TemporaryDirectory(prefix="silemio-controller-probe-") as temporary:
        probe_path = Path(temporary) / "Controller-Probe.ctrl2"
        probe = export_liveprofessor_controller(
            profile,
            probe_path,
            controller_name=controller_name,
            osc_in_port=osc_in_port,
            osc_out_port=osc_out_port,
            rotary_count=target_rotary_count,
        )
        inventory = LiveProfessorHostAdapter(controller_template=probe.path).inspect(
            source
        )
    existing_controllers = tuple(
        item for item in inventory.controllers if not item.is_embedded
    )
    if embed_new_controller:
        selected_controller_uid = probe.controller_uid
    elif project_controller_uid is not None:
        selected = next(
            (
                item
                for item in existing_controllers
                if item.controller_uid == project_controller_uid
            ),
            None,
        )
        if selected is None:
            raise LiveProfessorPreparationError(
                "le contrôleur LiveProfessor choisi n'existe plus dans le projet source"
            )
        selected_controller_uid = selected.controller_uid
    elif len(existing_controllers) == 1:
        # Reusing the only Companion/OSC controller is critical. Embedding a
        # second controller with the same /Companion/RotaryN namespace makes
        # LiveProfessor send two competing label inventories to the hardware.
        selected_controller_uid = existing_controllers[0].controller_uid
    elif len(existing_controllers) > 1:
        raise LiveProfessorPreparationError(
            "plusieurs contrôleurs Companion/OSC sont présents; choisissez celui à auto-mapper"
        )
    else:
        selected_controller_uid = probe.controller_uid

    matching_existing = next(
        (
            item
            for item in existing_controllers
            if item.controller_uid == selected_controller_uid
        ),
        None,
    )
    controller = export_liveprofessor_controller(
        profile,
        controller_path,
        replace=replace_controller,
        controller_name=(
            controller_name
            or (matching_existing.name if matching_existing is not None else None)
        ),
        controller_uid=(
            matching_existing.controller_uid
            if matching_existing is not None
            else None
        ),
        osc_in_port=osc_in_port,
        osc_out_port=osc_out_port,
        rotary_count=target_rotary_count,
    )

    adapter = LiveProfessorHostAdapter(controller_template=controller.path)
    automap = adapter.create_automapped_copy(
        source,
        destination,
        controller_uid=selected_controller_uid,
        plugin_uid=plugin_uid,
        plugin_uids=plugin_uids,
        rotary_count=controller.rotary_count,
        plugin_profiles=plugin_profiles,
    )
    after_hash = _sha256(source)
    if after_hash != source_hash:
        raise LiveProfessorPreparationError(
            "le projet source a changé pendant la préparation; résultat non validé"
        )
    return LiveProfessorPreparation(
        profile_id=profile.id,
        source_project=source,
        source_sha256=source_hash,
        controller=controller,
        automap=automap,
    )
