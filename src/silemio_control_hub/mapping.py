from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import ControllerProfile


class ParameterKind(StrEnum):
    CONTINUOUS = "continuous"
    ENUM = "enum"
    TOGGLE = "toggle"
    MOMENTARY = "momentary"


class ControlAction(StrEnum):
    ROTATE = "rotate"
    PRESS = "press"


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    id: str
    name: str
    kind: ParameterKind = ParameterKind.CONTINUOUS
    priority: int = 0
    preferred_role: str | None = None
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class MappingAssignment:
    parameter_id: str
    control_id: str
    action: ControlAction
    manual: bool = False
    reason: str = "automatic"
    bank: int = 0
    page: int = 0
    modifiers: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class MappingPlan:
    assignments: tuple[MappingAssignment, ...]
    unmapped_parameters: tuple[str, ...]
    conflicts: tuple[str, ...]

    def label_parameter_for(
        self,
        control_id: str,
        *,
        bank: int = 0,
        page: int = 0,
        modifiers: frozenset[str] = frozenset(),
    ) -> str | None:
        candidates = [
            item
            for item in self.assignments
            if item.control_id == control_id
            and item.bank == bank
            and item.page == page
            and item.modifiers == modifiers
        ]
        rotation = next((item for item in candidates if item.action == ControlAction.ROTATE), None)
        if rotation is not None:
            return rotation.parameter_id
        press = next((item for item in candidates if item.action == ControlAction.PRESS), None)
        return press.parameter_id if press is not None else None


class MappingPlanner:
    """Capability-based first mapping planner.

    It deliberately avoids plugin-specific guesses. Semantic plugin profiles will
    enrich priorities and preferred roles in a later phase.
    """

    def plan(
        self,
        profile: ControllerProfile,
        parameters: list[ParameterDefinition],
        manual_assignments: list[MappingAssignment] | None = None,
    ) -> MappingPlan:
        controls = {control.id: control for control in profile.controls}
        assignments: list[MappingAssignment] = []
        conflicts: list[str] = []
        mapped_parameters: set[str] = set()
        occupied_actions: set[
            tuple[str, ControlAction, int, int, frozenset[str]]
        ] = set()

        for item in manual_assignments or []:
            if item.control_id not in controls:
                conflicts.append(f"mapping manuel conservé mais contrôle inconnu: {item.control_id}")
            action_key = (
                item.control_id,
                item.action,
                item.bank,
                item.page,
                item.modifiers,
            )
            if not 0 <= item.bank < profile.bank_count:
                conflicts.append(f"mapping manuel conservé mais banque inconnue: {item.bank}")
            if not 0 <= item.page < profile.page_count:
                conflicts.append(f"mapping manuel conservé mais page inconnue: {item.page}")
            known_modifiers = {modifier.id for modifier in profile.modifiers}
            unknown_modifiers = sorted(set(item.modifiers) - known_modifiers)
            if unknown_modifiers:
                conflicts.append(
                    "mapping manuel conservé mais modificateur inconnu: "
                    + ", ".join(unknown_modifiers)
                )
            if item.parameter_id in mapped_parameters:
                conflicts.append(f"paramètre manuel dupliqué ignoré: {item.parameter_id}")
                continue
            if action_key in occupied_actions:
                conflicts.append(
                    f"emplacement manuel déjà occupé: {item.control_id}/{item.action.value}"
                )
                continue
            preserved = MappingAssignment(
                item.parameter_id,
                item.control_id,
                item.action,
                manual=True,
                reason="manual-preserved",
                bank=item.bank,
                page=item.page,
                modifiers=item.modifiers,
            )
            assignments.append(preserved)
            mapped_parameters.add(item.parameter_id)
            occupied_actions.add(action_key)

        ordered = sorted(
            enumerate(parameters),
            key=lambda item: (-item[1].priority, item[0]),
        )
        for _index, parameter in ordered:
            if parameter.id in mapped_parameters:
                continue
            action = (
                ControlAction.PRESS
                if parameter.kind in {ParameterKind.TOGGLE, ParameterKind.MOMENTARY}
                else ControlAction.ROTATE
            )
            candidates = [
                (control, bank, page)
                for page in range(profile.page_count)
                for bank in range(profile.bank_count)
                for control in profile.controls_for_bank(bank)
                if (control.supports_press if action == ControlAction.PRESS else control.supports_rotation)
                and (control.id, action, bank, page, frozenset()) not in occupied_actions
            ]
            if parameter.preferred_role:
                preferred = [
                    slot for slot in candidates if parameter.preferred_role in slot[0].roles
                ]
                if preferred:
                    candidates = preferred
            if not candidates:
                continue
            control, bank, page = candidates[0]
            assignments.append(
                MappingAssignment(
                    parameter.id,
                    control.id,
                    action,
                    reason="capability-match",
                    bank=bank,
                    page=page,
                )
            )
            mapped_parameters.add(parameter.id)
            occupied_actions.add((control.id, action, bank, page, frozenset()))

        unmapped = tuple(parameter.id for parameter in parameters if parameter.id not in mapped_parameters)
        return MappingPlan(tuple(assignments), unmapped, tuple(conflicts))
