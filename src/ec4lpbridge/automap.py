from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .value_tree import (
    ValueTree,
    ValueTreeFormatError,
    normalize_rotary_controls,
    parse_tree,
    write_tree,
)


ROTARY_ADDRESS = re.compile(r"^/Companion/Rotary(\d+)$", re.IGNORECASE)
BUTTON_ADDRESS = re.compile(
    r"^/Companion/GenericButtons/Button(\d+)$", re.IGNORECASE
)
PARAMETER_PROPERTY = re.compile(r"^P(\d+)$")
# JUCE writes hexadecimal hashes without left-padding. Most VST3 identifiers end
# in eight digits, but valid values such as CEDAR StageVox's 0x050070f0 are
# serialized by LiveProfessor as ``50070f0``.
PLUGIN_TYPE_SUFFIX = re.compile(r"-([0-9a-fA-F]{1,8})$")


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
        raise AutoMapError(f"modèle de contrôleur EC4 introuvable : {path}")
    try:
        template = parse_tree(path.read_bytes())
    except (OSError, ValueTreeFormatError) as exc:
        raise AutoMapError(f"modèle de contrôleur EC4 illisible : {exc}") from exc
    if template.type_name != "LPController":
        raise AutoMapError("le modèle EC4 intégré n'est pas un contrôleur LiveProfessor .ctrl2")
    if str(template.get("ControllerType", "")).lower() not in {"companion", "osc"}:
        raise AutoMapError("le modèle EC4 intégré n'est pas un contrôleur Companion/OSC")

    controller_node = copy.deepcopy(template)
    controller_node.type_name = "HardwareController"
    uid = controller_node.get("uID")
    if uid is None:
        raise AutoMapError("le modèle EC4 intégré ne contient pas d'identifiant de contrôleur")

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
        raise AutoMapError("le modèle EC4 intégré ne contient aucun rotatif")
    controller = ProjectController(
        name=str(controller_node.get("ControllerName", "EC4")),
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
    if str(preset.get("Name", "")).startswith("EC4 AutoMap -"):
        return True
    return any(
        child.type_name == "ControllerMapPreset"
        and str(child.get("Name", "")).startswith("EC4 AutoMap -")
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
        Name=f"EC4 AutoMap - {plugin.name}",
        TypeId=plugin.map_type_id,
        ControllerId=controller_uid,
    )
    controller_map = _new_node(
        "ControllerMapPreset",
        TypeId=plugin.map_type_id,
        ControllerId=controller_uid,
        Name=f"EC4 AutoMap - {plugin.name}",
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
            and str(node.get("Name", "")) == "EC4 AutoMap - Dynamic"
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


def _existing_mapping_profile(
    tree: ValueTree,
    controller_node: ValueTree,
    *,
    plugin: ProjectPlugin,
    plugin_uids: set[int],
) -> dict[int, int]:
    """Return the best user-defined control-to-parameter layout for a plugin type."""

    controller_uid = int(controller_node.get("uID"))
    profile: dict[int, int] = {}

    def merge_group(group: ValueTree) -> None:
        values: dict[int, list[int]] = {}
        for assignment in group.children:
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
            values.setdefault(control_id, []).append(parameter_id)
        for control_id, parameters in values.items():
            if control_id in profile:
                continue
            # Repeated instances normally agree. If they do not, keep the most
            # common value, then the latest one as a deterministic tie-breaker.
            profile[control_id] = max(
                dict.fromkeys(parameters),
                key=lambda value: (parameters.count(value), parameters[::-1].index(value) * -1),
            )

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
        return profile
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
    return profile


def _plugin_assignments(
    *,
    controller_uid: int,
    plugin: ProjectPlugin,
    rotaries: list[tuple[int, ValueTree]],
    buttons: list[tuple[int, ValueTree]],
    profile: dict[int, int],
) -> tuple[list[ValueTree], int]:
    """Build a profile-aware layout and keep paired rotary labels for buttons."""

    rotary_by_number = {number: control for number, control in rotaries}
    button_by_number = {number: control for number, control in buttons}
    rotary_parameters: dict[int, int] = {}
    button_parameters: dict[int, int] = {}
    for number, control in rotaries:
        control_id = int(control.get("id"))
        parameter_id = profile.get(control_id)
        if parameter_id is not None and 0 <= parameter_id < plugin.parameter_count:
            rotary_parameters[number] = parameter_id
    for number, control in buttons:
        control_id = int(control.get("id"))
        parameter_id = profile.get(control_id)
        if parameter_id is not None and 0 <= parameter_id < plugin.parameter_count:
            button_parameters[number] = parameter_id
            # EC4 labels are driven by the rotary feedback. If a learned button
            # has no deliberately assigned rotary, mirror it at the same position.
            if number in rotary_by_number and number not in rotary_parameters:
                rotary_parameters[number] = parameter_id

    used_parameters = set(rotary_parameters.values())
    remaining_parameters = iter(
        parameter_id
        for parameter_id in range(plugin.parameter_count)
        if parameter_id not in used_parameters
    )
    for number, _control in rotaries:
        if number in rotary_parameters:
            continue
        try:
            rotary_parameters[number] = next(remaining_parameters)
        except StopIteration:
            break

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
        name="EC4 AutoMap - Dynamic",
        assignments=combined,
        activate=activate,
    )


def create_automapped_project(
    source: Path,
    destination: Path,
    *,
    plugin_uid: int | None,
    controller_uid: int,
    expand_to_fullbank: bool = True,
    controller_template: Path | None = None,
) -> AutoMapResult:
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise AutoMapError("l'auto-mapping crée une copie : choisissez un autre nom de fichier")
    tree = _load_project(source_path)

    plugins, _skipped_plugins = _project_plugins(tree)
    if plugin_uid is None:
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

    target_rotaries = 99 if expand_to_fullbank else 16
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
    type_profiles: dict[str, dict[int, int]] = {}
    for project_plugin, _node in selected_plugins:
        if project_plugin.map_type_id in type_profiles:
            continue
        type_profiles[project_plugin.map_type_id] = _existing_mapping_profile(
            tree,
            controller_node,
            plugin=project_plugin,
            plugin_uids=all_plugins_by_map_type.get(project_plugin.map_type_id, set()),
        )
    profiles: dict[int, dict[int, int]] = {}
    for project_plugin, _node in selected_plugins:
        instance_profile = _existing_mapping_profile(
            tree,
            controller_node,
            plugin=project_plugin,
            plugin_uids={project_plugin.plugin_uid},
        )
        merged_profile = dict(type_profiles.get(project_plugin.map_type_id, {}))
        merged_profile.update(instance_profile)
        profiles[project_plugin.plugin_uid] = merged_profile
    for plugin, _plugin_node in selected_plugins:
        assignments, mapped_count = _plugin_assignments(
            controller_uid=controller_uid,
            plugin=plugin,
            rotaries=rotaries,
            buttons=buttons,
            profile=profiles.get(plugin.plugin_uid, {}),
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
                name=f"EC4 AutoMap - {plugin.name}",
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
        active_name = "EC4 AutoMap - Dynamic"
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
        active_name = f"EC4 AutoMap - {selected_plugins[0][0].name}"
    else:
        active_name = "EC4 AutoMap - Dynamic"
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
    """Consolidate stale shared EC4 maps without replacing manual assignments.

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
        consolidated = list(selected.values())
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
            if not map_name.startswith("EC4 AutoMap -") or map_name == "EC4 AutoMap - Dynamic":
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
