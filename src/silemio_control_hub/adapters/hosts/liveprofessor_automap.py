from __future__ import annotations

import copy
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ...formats.juce_value_tree import (
    ValueTree,
    ValueTreeFormatError,
    normalize_rotary_controls,
    parse_tree,
    write_tree,
)
from ...plugin_profiles import PluginObservation, PluginProfile, PluginProfileResolver


ROTARY_ADDRESS = re.compile(r"^/Companion/Rotary(\d+)$", re.IGNORECASE)
BUTTON_ADDRESS = re.compile(
    r"^/Companion/GenericButtons/Button(\d+)$", re.IGNORECASE
)
PARAMETER_PROPERTY = re.compile(r"^P(\d+)$")
# JUCE writes hexadecimal hashes without left-padding. Most VST3 identifiers end
# in eight digits, but valid values such as CEDAR StageVox's 0x050070f0 are
# serialized by LiveProfessor as ``50070f0``.
PLUGIN_TYPE_SUFFIX = re.compile(r"-([0-9a-fA-F]{1,8})$")
AUTOMAP_PREFIX = "SiLeMI/O AutoMap -"
LEGACY_AUTOMAP_PREFIX = "EC4 AutoMap -"
DYNAMIC_AUTOMAP_NAME = f"{AUTOMAP_PREFIX} Dynamic"
LEGACY_DYNAMIC_AUTOMAP_NAME = f"{LEGACY_AUTOMAP_PREFIX} Dynamic"


@dataclass(frozen=True, slots=True)
class ProjectPlugin:
    name: str
    plugin_type_id: str
    plugin_uid: int
    parameter_count: int
    map_type_id: str

    @property
    def display_name(self) -> str:
        return f"{self.name} — {self.parameter_count} paramètres"

    @property
    def observation(self) -> PluginObservation:
        plugin_format, _separator, _remainder = self.plugin_type_id.partition("-")
        return PluginObservation.from_parameter_count(
            plugin_format=plugin_format or "LiveProfessor",
            stable_id=self.plugin_type_id,
            name=self.name,
            parameter_count=self.parameter_count,
        )


@dataclass(frozen=True, slots=True)
class ProjectController:
    name: str
    controller_uid: int
    rotary_count: int
    button_count: int
    is_embedded: bool = False

    @property
    def display_name(self) -> str:
        return f"{self.name} — {self.rotary_count} rotatifs"


@dataclass(frozen=True, slots=True)
class ProjectInventory:
    path: Path
    plugins: tuple[ProjectPlugin, ...]
    controllers: tuple[ProjectController, ...]
    skipped_plugins: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AutoMapResult:
    output_path: Path
    backup_path: Path | None
    plugin_name: str
    controller_name: str
    mapped_rotaries: int
    available_parameters: int
    controller_rotaries: int
    map_type_id: str
    mapped_plugins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepairMapResult:
    output_path: Path
    backup_path: Path | None
    controller_name: str
    restored_assignments: int
    synchronized_presets: int
    migrated_presets: int
    conflicts_preserved: int


class AutoMapError(ValueError):
    pass


def _child(tree: ValueTree, type_name: str) -> ValueTree:
    for child in tree.children:
        if child.type_name == type_name:
            return child
    raise AutoMapError(f"noeud LiveProfessor absent : {type_name}")


def _walk(tree: ValueTree):
    yield tree
    for child in tree.children:
        yield from _walk(child)


def _new_node(type_name: str, **properties: object) -> ValueTree:
    node = ValueTree(type_name, [], [])
    for key, value in properties.items():
        node.set(key, value)
    return node


def plugin_map_type_id(plugin_type_id: str) -> str:
    """Convert LiveProfessor's hexadecimal plugin suffix to Controller Map TypeId.

    LiveProfessor serializes the JUCE plugin UID as the absolute decimal value of
    the signed 32-bit hexadecimal suffix stored in ``pluginTypeId``.
    """

    match = PLUGIN_TYPE_SUFFIX.search(plugin_type_id)
    if not match:
        raise AutoMapError(f"identifiant de plugin non pris en charge : {plugin_type_id}")
    unsigned = int(match.group(1), 16)
    signed = unsigned if unsigned < 0x80000000 else unsigned - 0x100000000
    return f"plugin-UID-{abs(signed)}"


def _parameter_count(plugin_node: ValueTree) -> int:
    indices: list[int] = []
    for node in _walk(plugin_node):
        if node.type_name != "parameters":
            continue
        for key, _variant in node.properties:
            match = PARAMETER_PROPERTY.fullmatch(key)
            if match:
                indices.append(int(match.group(1)))
        if indices:
            break
    return max(indices, default=-1) + 1


def _rotary_controls(controller: ValueTree) -> list[tuple[int, ValueTree]]:
    controls = _child(controller, "Controls")
    result: list[tuple[int, ValueTree]] = []
    for control in controls.children:
        if control.type_name != "HardwareControl" or control.get("ControlStyle") != 0:
            continue
        match = ROTARY_ADDRESS.fullmatch(str(control.get("OSCAddressPatern", "")))
        if match:
            result.append((int(match.group(1)), control))
    result.sort(key=lambda item: item[0])
    return result


def _button_count(controller: ValueTree) -> int:
    controls = _child(controller, "Controls")
    return sum(
        1
        for control in controls.children
        if control.type_name == "HardwareControl" and control.get("ControlStyle") == 2
    )


def _button_controls(controller: ValueTree) -> list[tuple[int, ValueTree]]:
    controls = _child(controller, "Controls")
    result: list[tuple[int, ValueTree]] = []
    for control in controls.children:
        if control.type_name != "HardwareControl" or control.get("ControlStyle") != 2:
            continue
        match = BUTTON_ADDRESS.fullmatch(str(control.get("OSCAddressPatern", "")))
        if match:
            result.append((int(match.group(1)), control))
    result.sort(key=lambda item: item[0])
    return result


def _project_plugins(
    tree: ValueTree,
) -> tuple[list[tuple[ProjectPlugin, ValueTree]], list[str]]:
    chains = _child(tree, "Chains")
    result: list[tuple[ProjectPlugin, ValueTree]] = []
    skipped: list[str] = []
    for chain in chains.children:
        chain_plugins = next(
            (child for child in chain.children if child.type_name == "ChainPlugins"),
            None,
        )
        if chain_plugins is None:
            continue
        for plugin_node in chain_plugins.children:
            plugin_type_id = str(plugin_node.get("pluginTypeId", ""))
            plugin_uid = plugin_node.get("pluginUid")
            if not plugin_type_id or plugin_uid is None:
                continue
            parameter_count = _parameter_count(plugin_node)
            if parameter_count <= 0:
                continue
            plugin_name = str(plugin_node.get("pluginTypeName", "Plugin"))
            try:
                map_type_id = plugin_map_type_id(plugin_type_id)
            except AutoMapError as exc:
                skipped.append(f"{plugin_name} ({plugin_type_id}) : {exc}")
                continue
            plugin = ProjectPlugin(
                name=plugin_name,
                plugin_type_id=plugin_type_id,
                plugin_uid=int(plugin_uid),
                parameter_count=parameter_count,
                map_type_id=map_type_id,
            )
            result.append((plugin, plugin_node))
    return result, skipped


def _project_controllers(tree: ValueTree) -> list[tuple[ProjectController, ValueTree]]:
    hardware_root = _child(tree, "HardwareControllers")
    controllers_root = _child(hardware_root, "HardwareControllers")
    result: list[tuple[ProjectController, ValueTree]] = []
    for controller_node in controllers_root.children:
        if controller_node.type_name != "HardwareController":
            continue
        if str(controller_node.get("ControllerType", "")).lower() not in {"companion", "osc"}:
            continue
        uid = controller_node.get("uID")
        if uid is None:
            continue
        rotaries = _rotary_controls(controller_node)
        if not rotaries:
            continue
        controller = ProjectController(
            name=str(controller_node.get("ControllerName", "Controller")),
            controller_uid=int(uid),
            rotary_count=len(rotaries),
            button_count=_button_count(controller_node),
        )
        result.append((controller, controller_node))
    return result


def _controller_from_template(
    project_tree: ValueTree,
    template_path: Path,
) -> tuple[ProjectController, ValueTree]:
    """Load the neutral bundled CTRL2 as an embeddable project controller."""

    path = Path(template_path).expanduser().resolve()
    if not path.is_file():
        raise AutoMapError(f"modèle de contrôleur introuvable : {path}")
    try:
        template = parse_tree(path.read_bytes())
    except (OSError, ValueTreeFormatError) as exc:
        raise AutoMapError(f"modèle de contrôleur illisible : {exc}") from exc
    if template.type_name != "LPController":
        raise AutoMapError("le modèle intégré n'est pas un contrôleur LiveProfessor .ctrl2")
    if str(template.get("ControllerType", "")).lower() not in {"companion", "osc"}:
        raise AutoMapError("le modèle intégré n'est pas un contrôleur Companion/OSC")

    controller_node = copy.deepcopy(template)
    controller_node.type_name = "HardwareController"
    uid = controller_node.get("uID")
    if uid is None:
        raise AutoMapError("le modèle intégré ne contient pas d'identifiant de contrôleur")

    # A project may contain a non-Companion controller with the same saved UID.
    # In that case, use a deterministic free UID so analysis and generation agree.
    used_controller_uids = {
        int(node.get("uID"))
        for node in _walk(project_tree)
        if node.type_name == "HardwareController" and node.get("uID") is not None
    }
    controller_uid = int(uid)
    if controller_uid in used_controller_uids:
        controller_uid = max(used_controller_uids | {controller_uid}) + 1
        controller_node.set("uID", controller_uid)

    rotaries = _rotary_controls(controller_node)
    if not rotaries:
        raise AutoMapError("le modèle intégré ne contient aucun rotatif")
    controller = ProjectController(
        name=str(controller_node.get("ControllerName", "SiLeMI/O Controller")),
        controller_uid=controller_uid,
        rotary_count=len(rotaries),
        button_count=_button_count(controller_node),
        is_embedded=True,
    )
    return controller, controller_node


def _load_project(path: Path) -> ValueTree:
    project_path = Path(path).expanduser().resolve()
    if not project_path.is_file():
        raise AutoMapError(f"projet LiveProfessor introuvable : {project_path}")
    try:
        tree = parse_tree(project_path.read_bytes())
    except (OSError, ValueTreeFormatError) as exc:
        raise AutoMapError(f"projet LiveProfessor illisible : {exc}") from exc
    if tree.type_name != "LiveProfessorProjectFile":
        raise AutoMapError("le fichier sélectionné n'est pas un projet LiveProfessor .rack2")
    return tree


def inspect_project(
    path: Path,
    *,
    controller_template: Path | None = None,
) -> ProjectInventory:
    project_path = Path(path).expanduser().resolve()
    tree = _load_project(project_path)
    plugin_pairs, skipped_plugins = _project_plugins(tree)
    plugins = tuple(item[0] for item in plugin_pairs)
    controller_pairs = _project_controllers(tree)
    if not controller_pairs and controller_template is not None:
        controller_pairs = [_controller_from_template(tree, controller_template)]
    controllers = tuple(item[0] for item in controller_pairs)
    if not plugins:
        details = f"\n\nPlugins ignorés :\n" + "\n".join(skipped_plugins) if skipped_plugins else ""
        raise AutoMapError(
            "aucun plugin pris en charge avec paramètres automatisables n'a été trouvé"
            + details
        )
    if not controllers:
        raise AutoMapError("aucun contrôleur Companion/OSC avec rotatifs n'a été trouvé")
    return ProjectInventory(project_path, plugins, controllers, tuple(skipped_plugins))


def inspect_plugins(path: Path) -> tuple[ProjectPlugin, ...]:
    """Inspect plug-ins without requiring a configured hardware controller."""

    tree = _load_project(Path(path).expanduser().resolve())
    plugin_pairs, skipped_plugins = _project_plugins(tree)
    plugins = tuple(item[0] for item in plugin_pairs)
    if not plugins:
        details = (
            "\n\nPlugins ignorés :\n" + "\n".join(skipped_plugins)
            if skipped_plugins
            else ""
        )
        raise AutoMapError(
            "aucun plugin pris en charge avec paramètres automatisables n'a été trouvé"
            + details
        )
    return plugins


def _assignment(
    controller_uid: int,
    control_uid: int,
    plugin_uid: int,
    parameter_id: int,
) -> ValueTree:
    assignment = _new_node(
        "Assignment",
        ParentControllerId=controller_uid,
        ControllerId=control_uid,
        ControllableId=f"Processor{plugin_uid}",
        ParameterId=parameter_id,
        selectMode=True,
    )
    assignment.children.append(
        _new_node(
            "Transform",
            Reverse=False,
            Toggle=False,
            Relative=False,
            expCurve=False,
            MaxOpValue=1.0,
            MinOpValue=0.0,
            MaxInpValue=1.0,
            MinInpValue=0.0,
            selectMode=True,
            relativeInputMode=0,
        )
    )
    return assignment


def _next_map_id(tree: ValueTree) -> int:
    used: set[int] = set()
    for node in _walk(tree):
        for key, variant in node.properties:
            normalized_key = key.casefold()
            if (
                normalized_key in {"id", "uid", "mapid", "activemap", "controllermapid"}
                or normalized_key.endswith("mapid")
            ) and isinstance(variant.value, int):
                used.add(variant.value)
    candidate = max(used, default=5_000_000) + 1
    while candidate in used:
        candidate += 1
    return candidate


def _is_automap_preset(preset: ValueTree) -> bool:
    prefixes = (AUTOMAP_PREFIX, LEGACY_AUTOMAP_PREFIX)
    if str(preset.get("Name", "")).startswith(prefixes):
        return True
    return any(
        child.type_name == "ControllerMapPreset"
        and str(child.get("Name", "")).startswith(prefixes)
        for child in preset.children
    )


def _existing_automap_id(controller_node: ValueTree, map_type_id: str) -> int | None:
    try:
        presets = _child(_child(controller_node, "MapPresets"), "Presets")
    except AutoMapError:
        return None
    for preset in presets.children:
        if (
            preset.type_name != "MapPreset"
            or preset.get("TypeId") != map_type_id
            or not _is_automap_preset(preset)
        ):
            continue
        for child in preset.children:
            if child.type_name == "ControllerMapPreset" and child.get("mapId") is not None:
                return int(child.get("mapId"))
    return None


def _ensure_presets(controller_node: ValueTree) -> ValueTree:
    map_presets = next(
        (child for child in controller_node.children if child.type_name == "MapPresets"),
        None,
    )
    if map_presets is None:
        map_presets = _new_node("MapPresets")
        controller_node.children.append(map_presets)
    presets = next(
        (child for child in map_presets.children if child.type_name == "Presets"),
        None,
    )
    if presets is None:
        presets = _new_node("Presets")
        map_presets.children.append(presets)
    return presets


def _install_plugin_preset(
    tree: ValueTree,
    controller_node: ValueTree,
    plugin: ProjectPlugin,
    assignments: list[ValueTree],
    forbidden_map_ids: set[int] | None = None,
) -> tuple[int, ValueTree, ValueTree]:
    controller_uid = int(controller_node.get("uID"))
    forbidden = forbidden_map_ids or set()
    existing_map_id = _existing_automap_id(controller_node, plugin.map_type_id)
    map_id = (
        existing_map_id
        if existing_map_id is not None and existing_map_id not in forbidden
        else _next_map_id(tree)
    )
    presets = _ensure_presets(controller_node)
    presets.children = [
        preset
        for preset in presets.children
        if not (
            preset.type_name == "MapPreset"
            and preset.get("TypeId") == plugin.map_type_id
            and int(preset.get("ControllerId", -1)) == controller_uid
            and _is_automap_preset(preset)
        )
    ]

    preset = _new_node(
        "MapPreset",
        Name=f"{AUTOMAP_PREFIX} {plugin.name}",
        TypeId=plugin.map_type_id,
        ControllerId=controller_uid,
    )
    controller_map = _new_node(
        "ControllerMapPreset",
        TypeId=plugin.map_type_id,
        ControllerId=controller_uid,
        Name=f"{AUTOMAP_PREFIX} {plugin.name}",
        SelectMode=True,
        mapId=map_id,
    )
    first_assignments = _new_node("Assignments")
    first_assignments.children = copy.deepcopy(assignments)
    second_assignments = _new_node("Assignments")
    second_assignments.children = copy.deepcopy(assignments)
    controller_map.children = [first_assignments, second_assignments]
    preset.children = [controller_map]
    presets.children.append(preset)

    return map_id, preset, controller_map


def _set_controller_map_assignments(
    controller_map: ValueTree,
    assignments: list[ValueTree],
) -> None:
    first_assignments = _new_node("Assignments")
    first_assignments.children = copy.deepcopy(assignments)
    second_assignments = _new_node("Assignments")
    second_assignments.children = copy.deepcopy(assignments)
    controller_map.children = [first_assignments, second_assignments]


def _assignment_key(assignment: ValueTree) -> tuple[object, object, object] | None:
    if assignment.type_name != "Assignment":
        return None
    return (
        assignment.get("ParentControllerId"),
        assignment.get("ControllerId"),
        assignment.get("ControllableId"),
    )


def _merge_assignments(
    fallback: list[ValueTree],
    preferred: list[ValueTree],
) -> list[ValueTree]:
    """Merge assignments without duplicating a controller/control/target tuple."""

    merged = copy.deepcopy(fallback)
    positions = {
        key: index
        for index, assignment in enumerate(merged)
        if (key := _assignment_key(assignment)) is not None
    }
    for assignment in preferred:
        cloned = copy.deepcopy(assignment)
        key = _assignment_key(cloned)
        if key is None or key not in positions:
            if key is not None:
                positions[key] = len(merged)
            merged.append(cloned)
        else:
            merged[positions[key]] = cloned
    return merged


def _assignment_groups(controller_map: ValueTree) -> list[ValueTree]:
    return [child for child in controller_map.children if child.type_name == "Assignments"]


def _replace_plugin_control_assignments(
    container: ValueTree,
    *,
    controller_uid: int,
    control_ids: set[int],
    assignments: list[ValueTree],
) -> None:
    """Replace only plugin assignments owned by one hardware controller."""

    def is_target(assignment: ValueTree) -> bool:
        controllable = assignment.get("ControllableId")
        return (
            assignment.type_name == "Assignment"
            and assignment.get("ParentControllerId") == controller_uid
            and assignment.get("ControllerId") in control_ids
            and isinstance(controllable, str)
            and controllable.startswith("Processor")
        )

    groups = _assignment_groups(container)
    if not groups:
        groups = [_new_node("Assignments")]
        container.children.append(groups[0])
    for group in groups:
        preserved = [copy.deepcopy(item) for item in group.children if not is_target(item)]
        group.children = preserved + copy.deepcopy(assignments)


def _synchronize_dynamic_presets(
    tree: ValueTree,
    *,
    map_id: int,
    controller_uid: int,
    control_ids: set[int],
    assignments: list[ValueTree],
) -> int:
    synchronized = 0
    for node in _walk(tree):
        if (
            node.type_name == "ControllerMapPreset"
            and node.get("mapId") == map_id
            and node.get("ControllerId") == controller_uid
            and str(node.get("Name", ""))
            in {DYNAMIC_AUTOMAP_NAME, LEGACY_DYNAMIC_AUTOMAP_NAME}
        ):
            _replace_plugin_control_assignments(
                node,
                controller_uid=controller_uid,
                control_ids=control_ids,
                assignments=assignments,
            )
            synchronized += 1
    return synchronized


def _normalized_map_type_id(value: object) -> str:
    match = re.fullmatch(r"plugin-UID-?(\d+)", str(value), re.IGNORECASE)
    return f"plugin-UID-{match.group(1)}" if match else str(value)


def _mapping_profile_details(
    assignments: list[ValueTree],
    *,
    controller_uid: int,
    plugin: ProjectPlugin,
    plugin_uids: set[int],
    preferred_keys: set[tuple[object, object, object]] | None = None,
) -> tuple[dict[int, int], dict[int, tuple[int, int, int]]]:
    """Build one deterministic control layout shared by identical plugins.

    A mapping that is already active wins over a recovered preset mapping. Then
    the most common value across all instances wins, so four copies of the same
    plugin cannot slowly acquire four different EC4 layouts.
    """

    preferred = preferred_keys or set()
    values: dict[int, list[tuple[int, bool, int]]] = {}
    for order, assignment in enumerate(assignments):
        if (
            assignment.type_name != "Assignment"
            or assignment.get("ParentControllerId") != controller_uid
        ):
            continue
        controllable = assignment.get("ControllableId")
        if not isinstance(controllable, str) or not controllable.startswith("Processor"):
            continue
        try:
            target_uid = int(controllable.removeprefix("Processor"))
            parameter_id = int(assignment.get("ParameterId"))
            control_id = int(assignment.get("ControllerId"))
        except (TypeError, ValueError):
            continue
        if target_uid not in plugin_uids or not 0 <= parameter_id < plugin.parameter_count:
            continue
        key = _assignment_key(assignment)
        values.setdefault(control_id, []).append(
            (parameter_id, key in preferred if key is not None else False, order)
        )

    profile: dict[int, int] = {}
    priorities: dict[int, tuple[int, int, int]] = {}
    for control_id, candidates in values.items():
        parameters = list(dict.fromkeys(item[0] for item in candidates))
        def score(parameter_id: int) -> tuple[int, int, int]:
            return (
                sum(
                    1
                    for value, is_preferred, _order in candidates
                    if value == parameter_id and is_preferred
                ),
                sum(
                    1
                    for value, _is_preferred, _order in candidates
                    if value == parameter_id
                ),
                max(
                    order
                    for value, _is_preferred, order in candidates
                    if value == parameter_id
                ),
            )

        parameter_id = max(parameters, key=score)
        profile[control_id] = parameter_id
        priorities[control_id] = score(parameter_id)
    return profile, priorities


def _existing_mapping_profile(
    tree: ValueTree,
    controller_node: ValueTree,
    *,
    plugin: ProjectPlugin,
    plugin_uids: set[int],
) -> tuple[
    dict[int, int],
    dict[int, tuple[int, int, int]],
    tuple[int, ...],
]:
    """Return the best user-defined control-to-parameter layout for a plugin type."""

    controller_uid = int(controller_node.get("uID"))
    profile: dict[int, int] = {}
    priorities: dict[int, tuple[int, int, int]] = {}
    preserved_parameters: list[int] = []

    def merge_group(group: ValueTree) -> None:
        for assignment in group.children:
            controllable = assignment.get("ControllableId")
            if not isinstance(controllable, str) or not controllable.startswith(
                "Processor"
            ):
                continue
            try:
                target_uid = int(controllable.removeprefix("Processor"))
                parameter_id = int(assignment.get("ParameterId"))
            except (TypeError, ValueError):
                continue
            if (
                target_uid in plugin_uids
                and 0 <= parameter_id < plugin.parameter_count
                and parameter_id not in preserved_parameters
            ):
                preserved_parameters.append(parameter_id)
        candidate, candidate_priorities = _mapping_profile_details(
            group.children,
            controller_uid=controller_uid,
            plugin=plugin,
            plugin_uids=plugin_uids,
        )
        for control_id, parameter_id in candidate.items():
            if control_id not in profile:
                profile[control_id] = parameter_id
                priorities[control_id] = candidate_priorities[control_id]

    hardware_root = _child(tree, "HardwareControllers")
    active_map_id = hardware_root.get("ActiveMap")
    hardware_maps = next(
        (child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"),
        None,
    )
    if hardware_maps is not None:
        active_map = next(
            (
                item
                for item in hardware_maps.children
                if item.type_name == "HardwareCtrlMap" and item.get("mapId") == active_map_id
            ),
            None,
        )
        if active_map is not None:
            groups = _assignment_groups(active_map)
            if groups:
                merge_group(groups[0])

    try:
        presets = _child(_child(controller_node, "MapPresets"), "Presets")
    except AutoMapError:
        return profile, priorities, tuple(preserved_parameters)
    manual: list[ValueTree] = []
    generated: list[ValueTree] = []
    for preset in presets.children:
        if (
            preset.type_name != "MapPreset"
            or _normalized_map_type_id(preset.get("TypeId")) != plugin.map_type_id
            or int(preset.get("ControllerId", -1)) != controller_uid
        ):
            continue
        (generated if _is_automap_preset(preset) else manual).append(preset)

    # Prefer the newest manual preset. A modified generated preset remains a
    # useful fallback and is still safer than reverting to technical order.
    for preset in [*reversed(manual), *reversed(generated)]:
        controller_map = next(
            (child for child in preset.children if child.type_name == "ControllerMapPreset"),
            None,
        )
        if controller_map is None:
            continue
        groups = _assignment_groups(controller_map)
        if not groups:
            continue
        merge_group(groups[0])
    return profile, priorities, tuple(preserved_parameters)


def inspect_plugin_parameter_slots(
    path: Path,
    *,
    plugin_uid: int,
) -> dict[int, int]:
    """Return zero-based Companion rotary slots mapped to plug-in parameters.

    This is read-only and intentionally relies on LiveProfessor's saved
    Controller Map instead of assuming that slot N always means parameter N.
    """

    tree = _load_project(Path(path).expanduser().resolve())
    plugins, _skipped = _project_plugins(tree)
    target_pair = next(
        (pair for pair in plugins if pair[0].plugin_uid == int(plugin_uid)),
        None,
    )
    if target_pair is None:
        raise AutoMapError("le plugin choisi n'existe plus dans ce projet")
    controllers = _project_controllers(tree)
    if not controllers:
        return {}
    target, _target_node = target_pair
    same_type_uids = {
        plugin.plugin_uid
        for plugin, _node in plugins
        if plugin.map_type_id == target.map_type_id
    }
    best: dict[int, int] = {}
    for _controller, controller_node in controllers:
        profile, _priorities, _preserved = _existing_mapping_profile(
            tree,
            controller_node,
            plugin=target,
            plugin_uids=same_type_uids,
        )
        slots = {
            number - 1: profile[int(control.get("id"))]
            for number, control in _rotary_controls(controller_node)
            if int(control.get("id")) in profile
        }
        if len(slots) > len(best):
            best = slots
    return best


def _plugin_assignments(
    *,
    controller_uid: int,
    plugin: ProjectPlugin,
    rotaries: list[tuple[int, ValueTree]],
    buttons: list[tuple[int, ValueTree]],
    profile: dict[int, int],
    profile_priority: dict[int, tuple[int, int, int]] | None = None,
    preserve_parameters: list[int] | tuple[int, ...] = (),
    preferred_parameter_order: Iterable[int] = (),
    allowed_parameters: Iterable[int] | None = None,
    fill_unassigned: bool = True,
) -> tuple[list[ValueTree], int]:
    """Build one semantic hardware layout for a plugin instance.

    A parameter learned on a push button is considered discrete and reserves the
    rotary at the same physical position. This one matched button/rotary pair is
    intentional: LiveProfessor exposes labels through Rotary feedback, so the
    mirror keeps the push label permanently visible. All other
    duplicates (two rotaries, two buttons, or unmatched button/rotary positions)
    are removed.
    """

    rotary_by_number = {number: control for number, control in rotaries}
    button_by_number = {number: control for number, control in buttons}
    rotary_parameters: dict[int, int] = {}
    button_parameters: dict[int, int] = {}
    used_parameters: set[int] = set()
    priority = profile_priority or {}
    allowed = (
        set(range(plugin.parameter_count))
        if allowed_parameters is None
        else {
            int(parameter_id)
            for parameter_id in allowed_parameters
            if 0 <= int(parameter_id) < plugin.parameter_count
        }
    )

    def ranked_controls(
        controls: list[tuple[int, ValueTree]],
    ) -> list[tuple[int, ValueTree]]:
        return sorted(
            controls,
            key=lambda item: (
                priority.get(int(item[1].get("id")), (0, 0, -1)),
                -item[0],
            ),
            reverse=True,
        )

    # A learned button is the strongest type hint available in a rack2 file:
    # LiveProfessor stores parameter values, but not the VST3 step count/type.
    for number, control in ranked_controls(buttons):
        control_id = int(control.get("id"))
        parameter_id = profile.get(control_id)
        if (
            parameter_id is not None
            and 0 <= parameter_id < plugin.parameter_count
            and parameter_id not in used_parameters
        ):
            button_parameters[number] = parameter_id
            used_parameters.add(parameter_id)

    # Reserve the rotary directly under every learned button. Besides making
    # the function available through both gestures, this is what lets a display
    # show Reset/Bypass-like labels before the user presses the encoder.
    for number, parameter_id in button_parameters.items():
        if number in rotary_by_number:
            rotary_parameters[number] = parameter_id

    for number, control in ranked_controls(rotaries):
        if number in rotary_parameters:
            continue
        control_id = int(control.get("id"))
        parameter_id = profile.get(control_id)
        if (
            parameter_id is not None
            and 0 <= parameter_id < plugin.parameter_count
            and parameter_id not in used_parameters
        ):
            rotary_parameters[number] = parameter_id
            used_parameters.add(parameter_id)

    preserved = [
        parameter_id
        for parameter_id in dict.fromkeys(preserve_parameters)
        if 0 <= parameter_id < plugin.parameter_count
        and parameter_id not in used_parameters
    ]
    preferred = [
        parameter_id
        for parameter_id in dict.fromkeys(preferred_parameter_order)
        if 0 <= parameter_id < plugin.parameter_count
        and parameter_id in allowed
        and parameter_id not in used_parameters
        and parameter_id not in preserved
    ]
    if fill_unassigned:
        remaining_parameters = iter(
            [
                *preserved,
                *preferred,
                *(
                    parameter_id
                    for parameter_id in range(plugin.parameter_count)
                    if parameter_id in allowed
                    and parameter_id not in used_parameters
                    and parameter_id not in preserved
                    and parameter_id not in preferred
                ),
            ]
        )
    else:
        # When several instances of the same plugin contain complementary
        # manual mappings, keep their union. Conflicting controls still use the
        # shared majority profile above; minority parameters are moved to free
        # rotaries instead of being silently discarded.
        remaining_parameters = iter(preserved)
    for number, _control in rotaries:
        if number in rotary_parameters:
            continue
        try:
            parameter_id = next(remaining_parameters)
        except StopIteration:
            break
        rotary_parameters[number] = parameter_id
        used_parameters.add(parameter_id)

    assignments: list[ValueTree] = []
    for number, parameter_id in rotary_parameters.items():
        assignments.append(
            _assignment(
                controller_uid,
                int(rotary_by_number[number].get("id")),
                plugin.plugin_uid,
                parameter_id,
            )
        )
    for number, parameter_id in button_parameters.items():
        if number not in button_by_number:
            continue
        assignments.append(
            _assignment(
                controller_uid,
                int(button_by_number[number].get("id")),
                plugin.plugin_uid,
                parameter_id,
            )
        )
    return assignments, len(rotary_parameters)


def _install_hardware_map(
    tree: ValueTree,
    *,
    map_id: int,
    name: str,
    assignments: list[ValueTree],
    activate: bool,
) -> None:

    hardware_root = _child(tree, "HardwareControllers")
    hardware_maps = next(
        (child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"),
        None,
    )
    if hardware_maps is None:
        hardware_maps = _new_node("HardwareCtrlMaps")
        hardware_root.children.append(hardware_maps)
    hardware_maps.children = [
        item
        for item in hardware_maps.children
        if not (item.type_name == "HardwareCtrlMap" and item.get("mapId") == map_id)
    ]
    active_map = _new_node("HardwareCtrlMap", Name=name, mapId=map_id)
    active_assignments = _new_node("Assignments")
    active_assignments.children = copy.deepcopy(assignments)
    active_map.children = [active_assignments]
    hardware_maps.children.append(active_map)
    if activate:
        hardware_root.set("ActiveMap", map_id)


def _runtime_map_context(
    tree: ValueTree,
    *,
    controller_uid: int,
    preserved_control_ids: set[int],
) -> tuple[list[int], dict[int, list[ValueTree]]]:
    """Return maps recalled by the project and their non-rotary assignments.

    LiveProfessor snapshots can restore a Controller Map after project load. An
    auto-map must therefore populate those referenced runtime maps instead of
    merely selecting a newly created preset map.
    """

    hardware_root = _child(tree, "HardwareControllers")
    referenced: list[int] = []

    def add_map_id(value: object) -> None:
        if isinstance(value, int) and value > 0 and value not in referenced:
            referenced.append(value)

    add_map_id(hardware_root.get("ActiveMap"))
    for node in _walk(tree):
        add_map_id(node.get("ControllerMapId"))

    hardware_maps = next(
        (child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"),
        None,
    )
    preserved: dict[int, list[ValueTree]] = {map_id: [] for map_id in referenced}
    if hardware_maps is None:
        return referenced, preserved

    for hardware_map in hardware_maps.children:
        map_id = hardware_map.get("mapId")
        if map_id not in preserved:
            continue
        assignments_node = next(
            (child for child in hardware_map.children if child.type_name == "Assignments"),
            None,
        )
        if assignments_node is None:
            continue
        preserved[int(map_id)] = [
            copy.deepcopy(assignment)
            for assignment in assignments_node.children
            if not (
                assignment.type_name == "Assignment"
                and assignment.get("ParentControllerId") == controller_uid
                and assignment.get("ControllerId") not in preserved_control_ids
            )
        ]
    return referenced, preserved


def _install_runtime_dynamic_map(
    tree: ValueTree,
    *,
    map_id: int,
    assignments: list[ValueTree],
    preserved_assignments: list[ValueTree],
    activate: bool,
) -> None:
    combined = _merge_assignments(preserved_assignments, assignments)
    _install_hardware_map(
        tree,
        map_id=map_id,
        name=DYNAMIC_AUTOMAP_NAME,
        assignments=combined,
        activate=activate,
    )


def create_automapped_project(
    source: Path,
    destination: Path,
    *,
    plugin_uid: int | None = None,
    plugin_uids: Iterable[int] | None = None,
    controller_uid: int,
    expand_to_fullbank: bool = True,
    controller_template: Path | None = None,
    target_rotary_count: int | None = None,
    plugin_profiles: Iterable[PluginProfile] = (),
) -> AutoMapResult:
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise AutoMapError("l'auto-mapping crée une copie : choisissez un autre nom de fichier")
    tree = _load_project(source_path)

    plugins, _skipped_plugins = _project_plugins(tree)
    if plugin_uid is not None and plugin_uids is not None:
        raise AutoMapError("plugin_uid et plugin_uids ne peuvent pas être utilisés ensemble")
    if plugin_uids is not None:
        requested_uids = tuple(dict.fromkeys(int(value) for value in plugin_uids))
        if not requested_uids:
            raise AutoMapError("sélectionnez au moins un plugin à auto-mapper")
        requested_set = set(requested_uids)
        selected_plugins = [
            item for item in plugins if item[0].plugin_uid in requested_set
        ]
        found_uids = {item[0].plugin_uid for item in selected_plugins}
        missing_uids = [value for value in requested_uids if value not in found_uids]
        if missing_uids:
            missing = ", ".join(str(value) for value in missing_uids)
            raise AutoMapError(
                f"les plugins choisis n'existent plus dans ce projet : {missing}"
            )
    elif plugin_uid is None:
        selected_plugins = list(plugins)
    else:
        plugin_pair = next((item for item in plugins if item[0].plugin_uid == plugin_uid), None)
        if plugin_pair is None:
            raise AutoMapError("le plugin choisi n'existe plus dans ce projet")
        selected_plugins = [plugin_pair]

    controllers = _project_controllers(tree)
    controller_pair = next(
        (item for item in controllers if item[0].controller_uid == controller_uid),
        None,
    )
    if controller_pair is None and controller_template is not None:
        embedded_pair = _controller_from_template(tree, controller_template)
        if embedded_pair[0].controller_uid == controller_uid:
            hardware_root = _child(tree, "HardwareControllers")
            controllers_root = _child(hardware_root, "HardwareControllers")
            controllers_root.children.append(embedded_pair[1])
            controller_pair = embedded_pair
    if controller_pair is None:
        raise AutoMapError("le contrôleur choisi n'existe plus dans ce projet")
    controller, controller_node = controller_pair

    target_rotaries = (
        target_rotary_count
        if target_rotary_count is not None
        else (99 if expand_to_fullbank else 16)
    )
    if not 1 <= target_rotaries <= 99:
        raise AutoMapError("le nombre de rotatifs cible doit être compris entre 1 et 99")
    if controller.rotary_count != target_rotaries:
        normalize_rotary_controls(controller_node, target_rotaries)
    rotaries = _rotary_controls(controller_node)
    buttons = _button_controls(controller_node)
    rotary_control_ids = {int(control.get("id")) for _number, control in rotaries}
    controls_node = _child(controller_node, "Controls")
    controller_control_ids = {
        int(control.get("id"))
        for control in controls_node.children
        if control.type_name == "HardwareControl" and control.get("id") is not None
    }
    runtime_map_ids, preserved_runtime_assignments = _runtime_map_context(
        tree,
        controller_uid=controller_uid,
        preserved_control_ids=controller_control_ids - rotary_control_ids,
    )
    mapped_counts: list[int] = []
    combined_assignments: list[ValueTree] = []
    installed_types: set[str] = set()
    first_preset: ValueTree | None = None
    first_controller_map: ValueTree | None = None
    active_map_id: int | None = None
    all_plugins_by_map_type: dict[str, set[int]] = {}
    for project_plugin, _node in plugins:
        all_plugins_by_map_type.setdefault(project_plugin.map_type_id, set()).add(
            project_plugin.plugin_uid
        )
    type_profiles: dict[
        str,
        tuple[
            dict[int, int],
            dict[int, tuple[int, int, int]],
            tuple[int, ...],
        ],
    ] = {}
    semantic_resolver = PluginProfileResolver(plugin_profiles)
    semantic_orders: dict[str, tuple[int, ...]] = {}
    semantic_allowed: dict[str, frozenset[int]] = {}
    for project_plugin, _node in selected_plugins:
        if project_plugin.map_type_id in type_profiles:
            continue
        type_profiles[project_plugin.map_type_id] = _existing_mapping_profile(
            tree,
            controller_node,
            plugin=project_plugin,
            plugin_uids=all_plugins_by_map_type.get(project_plugin.map_type_id, set()),
        )
        resolved = semantic_resolver.resolve(project_plugin.observation)
        semantic_allowed[project_plugin.map_type_id] = frozenset(
            parameter.position
            for parameter in resolved.parameters
            if parameter.enabled
        )
        semantic_orders[project_plugin.map_type_id] = tuple(
            parameter.position
            for parameter in sorted(
                resolved.parameters,
                key=lambda parameter: (-parameter.importance, parameter.position),
            )
            if parameter.enabled
        )
    for plugin, _plugin_node in selected_plugins:
        type_profile, type_priority, preserved_parameters = type_profiles.get(
            plugin.map_type_id,
            ({}, {}, ()),
        )
        assignments, mapped_count = _plugin_assignments(
            controller_uid=controller_uid,
            plugin=plugin,
            rotaries=rotaries,
            buttons=buttons,
            # Every instance of one plugin type deliberately shares this exact
            # profile. Per-instance overrides caused tracks 25-28 to drift.
            profile=type_profile,
            profile_priority=type_priority,
            preserve_parameters=preserved_parameters,
            preferred_parameter_order=semantic_orders.get(plugin.map_type_id, ()),
            # Explicit exclusions apply to automatically filled slots. Existing
            # manual mappings remain authoritative and are preserved above.
            allowed_parameters=semantic_allowed.get(plugin.map_type_id),
        )
        if mapped_count <= 0:
            continue
        combined_assignments.extend(copy.deepcopy(assignments))
        if plugin.plugin_type_id not in installed_types:
            map_id, preset, controller_map = _install_plugin_preset(
                tree,
                controller_node,
                plugin,
                assignments,
                forbidden_map_ids=set(runtime_map_ids),
            )
            installed_types.add(plugin.plugin_type_id)
            _install_hardware_map(
                tree,
                map_id=map_id,
                name=f"{AUTOMAP_PREFIX} {plugin.name}",
                assignments=assignments,
                activate=False,
            )
            if active_map_id is None:
                active_map_id = map_id
                first_preset = preset
                first_controller_map = controller_map
        mapped_counts.append(mapped_count)
    if not mapped_counts:
        raise AutoMapError("aucun paramètre ne peut être affecté")
    if active_map_id is None or first_preset is None or first_controller_map is None:
        raise AutoMapError("aucune Controller Map n'a pu être créée")

    if runtime_map_ids:
        active_name = DYNAMIC_AUTOMAP_NAME
        for index, runtime_map_id in enumerate(runtime_map_ids):
            final_runtime_assignments = _merge_assignments(
                preserved_runtime_assignments.get(runtime_map_id, []),
                combined_assignments,
            )
            _install_runtime_dynamic_map(
                tree,
                map_id=runtime_map_id,
                assignments=combined_assignments,
                preserved_assignments=preserved_runtime_assignments.get(runtime_map_id, []),
                activate=index == 0,
            )
            _synchronize_dynamic_presets(
                tree,
                map_id=runtime_map_id,
                controller_uid=controller_uid,
                control_ids=controller_control_ids,
                assignments=[
                    item
                    for item in final_runtime_assignments
                    if isinstance(item.get("ControllableId"), str)
                    and str(item.get("ControllableId")).startswith("Processor")
                ],
            )
    elif len(selected_plugins) == 1:
        active_name = f"{AUTOMAP_PREFIX} {selected_plugins[0][0].name}"
    else:
        active_name = DYNAMIC_AUTOMAP_NAME
        first_preset.set("Name", active_name)
        first_controller_map.set("Name", active_name)
        _set_controller_map_assignments(first_controller_map, combined_assignments)
    if not runtime_map_ids:
        _install_hardware_map(
            tree,
            map_id=active_map_id,
            name=active_name,
            assignments=combined_assignments,
            activate=True,
        )

    encoded = write_tree(tree)
    reparsed = parse_tree(encoded)
    if write_tree(reparsed) != encoded:
        raise AutoMapError("la validation du projet généré a échoué")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if destination_path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = destination_path.with_name(
            f"{destination_path.stem}.backup-{stamp}{destination_path.suffix}"
        )
        backup_path.write_bytes(destination_path.read_bytes())
    temporary_path = destination_path.with_name(f".{destination_path.name}.tmp")
    temporary_path.write_bytes(encoded)
    os.replace(temporary_path, destination_path)

    return AutoMapResult(
        output_path=destination_path,
        backup_path=backup_path,
        plugin_name=(
            selected_plugins[0][0].name
            if len(selected_plugins) == 1
            else f"{len(selected_plugins)} plugins"
        ),
        controller_name=controller.name,
        mapped_rotaries=sum(mapped_counts),
        available_parameters=sum(item[0].parameter_count for item in selected_plugins),
        controller_rotaries=len(rotaries),
        map_type_id=(selected_plugins[0][0].map_type_id if len(selected_plugins) == 1 else ""),
        mapped_plugins=tuple(
            plugin.name
            for index, (plugin, _node) in enumerate(selected_plugins)
            if plugin.plugin_type_id
            not in {previous[0].plugin_type_id for previous in selected_plugins[:index]}
        ),
    )


def repair_automapped_project(
    source: Path,
    destination: Path,
    *,
    controller_uid: int,
) -> RepairMapResult:
    """Consolidate stale shared maps without replacing manual assignments.

    LiveProfessor controller-map presets store a complete map. Loading an older
    preset can therefore remove mappings learned later. The active map is the
    authority here: its assignments always win conflicts, while assignments
    absent from it are recovered from the saved presets that target the same
    runtime map.
    """

    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise AutoMapError("la réparation crée une copie : choisissez un autre nom de fichier")
    tree = _load_project(source_path)
    controller_pair = next(
        (item for item in _project_controllers(tree) if item[0].controller_uid == controller_uid),
        None,
    )
    if controller_pair is None:
        raise AutoMapError("le contrôleur choisi n'existe plus dans ce projet")
    controller, controller_node = controller_pair
    controls_node = _child(controller_node, "Controls")
    rotaries = _rotary_controls(controller_node)
    buttons = _button_controls(controller_node)
    control_ids = {
        int(control.get("id"))
        for control in controls_node.children
        if control.type_name == "HardwareControl" and control.get("id") is not None
    }

    hardware_root = _child(tree, "HardwareControllers")
    runtime_map_ids: list[int] = []

    def add_runtime_map(value: object) -> None:
        if isinstance(value, int) and value > 0 and value not in runtime_map_ids:
            runtime_map_ids.append(value)

    add_runtime_map(hardware_root.get("ActiveMap"))
    for node in _walk(tree):
        add_runtime_map(node.get("ControllerMapId"))
    if not runtime_map_ids:
        raise AutoMapError("aucune Controller Map active ou rappelée n'a été trouvée")

    hardware_maps = next(
        (child for child in hardware_root.children if child.type_name == "HardwareCtrlMaps"),
        None,
    )
    if hardware_maps is None:
        raise AutoMapError("aucune Controller Map enregistrée n'a été trouvée")
    presets = _ensure_presets(controller_node)
    plugin_pairs, _skipped_plugins = _project_plugins(tree)
    plugins_by_type: dict[str, list[ProjectPlugin]] = {}
    for plugin, _plugin_node in plugin_pairs:
        plugins_by_type.setdefault(plugin.map_type_id, []).append(plugin)
    known_plugin_uids = {plugin.plugin_uid for plugin, _plugin_node in plugin_pairs}
    current_plugin_uids = {
        int(node.get("pluginUid"))
        for node in _walk(tree)
        if node.get("pluginUid") is not None and node.get("pluginTypeName") is not None
    }
    rotary_number_by_id = {int(control.get("id")): number for number, control in rotaries}
    button_number_by_id = {int(control.get("id")): number for number, control in buttons}

    def is_plugin_control_assignment(assignment: ValueTree) -> bool:
        controllable = assignment.get("ControllableId")
        return (
            assignment.type_name == "Assignment"
            and assignment.get("ParentControllerId") == controller_uid
            and assignment.get("ControllerId") in control_ids
            and isinstance(controllable, str)
            and controllable.startswith("Processor")
        )

    restored_total = 0
    synchronized_total = 0
    migrated_total = 0
    conflict_keys: set[tuple[object, object, object]] = set()
    repaired_any_map = False

    for runtime_map_id in runtime_map_ids:
        runtime_map = next(
            (
                item
                for item in hardware_maps.children
                if item.type_name == "HardwareCtrlMap" and item.get("mapId") == runtime_map_id
            ),
            None,
        )
        if runtime_map is None:
            continue
        repaired_any_map = True
        runtime_groups = _assignment_groups(runtime_map)
        active_assignments = (
            [item for item in runtime_groups[0].children if is_plugin_control_assignment(item)]
            if runtime_groups
            else []
        )
        active_keys = {
            key
            for assignment in active_assignments
            if (key := _assignment_key(assignment)) is not None
        }

        preset_pairs: list[tuple[ValueTree, ValueTree]] = []
        for preset in presets.children:
            if preset.type_name != "MapPreset":
                continue
            for controller_map in preset.children:
                if (
                    controller_map.type_name == "ControllerMapPreset"
                    and controller_map.get("ControllerId") == controller_uid
                    and controller_map.get("mapId") == runtime_map_id
                ):
                    preset_pairs.append((preset, controller_map))

        candidates: list[ValueTree] = list(active_assignments)
        # The last preset is normally the most recently created one. It is only
        # used to fill a missing mapping; the active map above remains authoritative.
        for _preset, controller_map in reversed(preset_pairs):
            for group in _assignment_groups(controller_map):
                candidates.extend(
                    item for item in group.children if is_plugin_control_assignment(item)
                )

        selected: dict[tuple[object, object, object], ValueTree] = {}
        parameter_values: dict[tuple[object, object, object], set[object]] = {}
        for assignment in candidates:
            key = _assignment_key(assignment)
            if key is None:
                continue
            parameter_values.setdefault(key, set()).add(assignment.get("ParameterId"))
            if key not in selected:
                selected[key] = copy.deepcopy(assignment)
        conflict_keys.update(
            key for key, values in parameter_values.items() if len(values) > 1
        )
        raw_consolidated = list(selected.values())
        consolidated: list[ValueTree] = []

        # Drop stale Processor targets that no longer exist in the project.
        # Current but unsupported/opaque processors are kept with the same
        # duplicate rule as supported plugins.
        # Supported plugin instances are rebuilt from one shared type profile:
        # a button may share only its matching rotary for permanent labelling;
        # every other duplicate is removed.
        opaque_by_uid: dict[int, list[ValueTree]] = {}
        for assignment in raw_consolidated:
            controllable = str(assignment.get("ControllableId", ""))
            try:
                target_uid = int(controllable.removeprefix("Processor"))
            except (TypeError, ValueError):
                target_uid = -1
            if target_uid in current_plugin_uids and target_uid not in known_plugin_uids:
                opaque_by_uid.setdefault(target_uid, []).append(assignment)

        for opaque_assignments in opaque_by_uid.values():
            used_parameters: set[object] = set()
            kept_buttons: dict[int, ValueTree] = {}
            for assignment in sorted(
                opaque_assignments,
                key=lambda item: button_number_by_id.get(
                    int(item.get("ControllerId", -1)), 10_000
                ),
            ):
                control_id = int(assignment.get("ControllerId", -1))
                if control_id not in button_number_by_id:
                    continue
                parameter_id = assignment.get("ParameterId")
                if parameter_id in used_parameters:
                    continue
                kept_buttons[button_number_by_id[control_id]] = assignment
                used_parameters.add(parameter_id)
                consolidated.append(copy.deepcopy(assignment))
            for assignment in sorted(
                opaque_assignments,
                key=lambda item: rotary_number_by_id.get(
                    int(item.get("ControllerId", -1)), 10_000
                ),
            ):
                control_id = int(assignment.get("ControllerId", -1))
                if control_id not in rotary_number_by_id:
                    continue
                number = rotary_number_by_id[control_id]
                parameter_id = assignment.get("ParameterId")
                paired_button = kept_buttons.get(number)
                if parameter_id in used_parameters and (
                    paired_button is None or paired_button.get("ParameterId") != parameter_id
                ):
                    continue
                consolidated.append(copy.deepcopy(assignment))
                used_parameters.add(parameter_id)

        for same_type_plugins in plugins_by_type.values():
            reference = same_type_plugins[0]
            plugin_uids = {plugin.plugin_uid for plugin in same_type_plugins}
            preserved_parameters: list[int] = []
            for assignment in raw_consolidated:
                controllable = assignment.get("ControllableId")
                if not isinstance(controllable, str) or not controllable.startswith(
                    "Processor"
                ):
                    continue
                try:
                    target_uid = int(controllable.removeprefix("Processor"))
                    parameter_id = int(assignment.get("ParameterId"))
                except (TypeError, ValueError):
                    continue
                if (
                    target_uid in plugin_uids
                    and 0 <= parameter_id < reference.parameter_count
                    and parameter_id not in preserved_parameters
                ):
                    preserved_parameters.append(parameter_id)
            profile, profile_priority = _mapping_profile_details(
                raw_consolidated,
                controller_uid=controller_uid,
                plugin=reference,
                plugin_uids=plugin_uids,
                # A control changed in the active map compared with an older
                # preset is an explicit manual edit and must beat a technical
                # duplicate elsewhere in the layout.
                preferred_keys=active_keys & conflict_keys,
            )
            for plugin in same_type_plugins:
                normalized, _mapped_count = _plugin_assignments(
                    controller_uid=controller_uid,
                    plugin=plugin,
                    rotaries=rotaries,
                    buttons=buttons,
                    profile=profile,
                    profile_priority=profile_priority,
                    preserve_parameters=preserved_parameters,
                    fill_unassigned=False,
                )
                consolidated.extend(normalized)

        restored_total += sum(key not in active_keys for key in selected)

        _replace_plugin_control_assignments(
            runtime_map,
            controller_uid=controller_uid,
            control_ids=control_ids,
            assignments=consolidated,
        )

        # Version 2026.1 could allocate the first generated plugin preset on the
        # same ID as a snapshot-recalled dynamic map. Move that preset to a free
        # ID before synchronising the genuinely shared dynamic presets.
        for preset, controller_map in preset_pairs:
            map_name = str(controller_map.get("Name", ""))
            if not map_name.startswith((AUTOMAP_PREFIX, LEGACY_AUTOMAP_PREFIX)) or map_name in {
                DYNAMIC_AUTOMAP_NAME,
                LEGACY_DYNAMIC_AUTOMAP_NAME,
            }:
                continue
            groups = _assignment_groups(controller_map)
            migrated_assignments = list(groups[0].children) if groups else []
            new_map_id = _next_map_id(tree)
            controller_map.set("mapId", new_map_id)
            _install_hardware_map(
                tree,
                map_id=new_map_id,
                name=map_name,
                assignments=migrated_assignments,
                activate=False,
            )
            migrated_total += 1

        synchronized_total += _synchronize_dynamic_presets(
            tree,
            map_id=runtime_map_id,
            controller_uid=controller_uid,
            control_ids=control_ids,
            assignments=consolidated,
        )

    if not repaired_any_map:
        raise AutoMapError("aucune Controller Map rappelée ne peut être réparée")

    encoded = write_tree(tree)
    reparsed = parse_tree(encoded)
    if write_tree(reparsed) != encoded:
        raise AutoMapError("la validation du projet réparé a échoué")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if destination_path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = destination_path.with_name(
            f"{destination_path.stem}.backup-{stamp}{destination_path.suffix}"
        )
        backup_path.write_bytes(destination_path.read_bytes())
    temporary_path = destination_path.with_name(f".{destination_path.name}.tmp")
    temporary_path.write_bytes(encoded)
    os.replace(temporary_path, destination_path)

    return RepairMapResult(
        output_path=destination_path,
        backup_path=backup_path,
        controller_name=controller.name,
        restored_assignments=restored_total,
        synchronized_presets=synchronized_total,
        migrated_presets=migrated_total,
        conflicts_preserved=len(conflict_keys),
    )
