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
PARAMETER_PROPERTY = re.compile(r"^P(\d+)$")
PLUGIN_TYPE_SUFFIX = re.compile(r"-([0-9a-fA-F]{8})$")


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

    @property
    def display_name(self) -> str:
        return f"{self.name} — {self.rotary_count} rotatifs"


@dataclass(frozen=True, slots=True)
class ProjectInventory:
    path: Path
    plugins: tuple[ProjectPlugin, ...]
    controllers: tuple[ProjectController, ...]


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


def _project_plugins(tree: ValueTree) -> list[tuple[ProjectPlugin, ValueTree]]:
    chains = _child(tree, "Chains")
    result: list[tuple[ProjectPlugin, ValueTree]] = []
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
            plugin = ProjectPlugin(
                name=str(plugin_node.get("pluginTypeName", "Plugin")),
                plugin_type_id=plugin_type_id,
                plugin_uid=int(plugin_uid),
                parameter_count=parameter_count,
                map_type_id=plugin_map_type_id(plugin_type_id),
            )
            result.append((plugin, plugin_node))
    return result


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


def inspect_project(path: Path) -> ProjectInventory:
    project_path = Path(path).expanduser().resolve()
    tree = _load_project(project_path)
    plugins = tuple(item[0] for item in _project_plugins(tree))
    controllers = tuple(item[0] for item in _project_controllers(tree))
    if not plugins:
        raise AutoMapError("aucun plugin avec paramètres automatisables n'a été trouvé")
    if not controllers:
        raise AutoMapError("aucun contrôleur Companion/OSC avec rotatifs n'a été trouvé")
    return ProjectInventory(project_path, plugins, controllers)


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
            if key.lower() in {"id", "uid", "mapid"} and isinstance(variant.value, int):
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
) -> tuple[int, ValueTree, ValueTree]:
    controller_uid = int(controller_node.get("uID"))
    map_id = _existing_automap_id(controller_node, plugin.map_type_id) or _next_map_id(tree)
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
    combined = copy.deepcopy(preserved_assignments)
    combined.extend(copy.deepcopy(assignments))
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
) -> AutoMapResult:
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    if source_path == destination_path:
        raise AutoMapError("l'auto-mapping crée une copie : choisissez un autre nom de fichier")
    tree = _load_project(source_path)

    plugins = _project_plugins(tree)
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
    if controller_pair is None:
        raise AutoMapError("le contrôleur choisi n'existe plus dans ce projet")
    controller, controller_node = controller_pair

    target_rotaries = 99 if expand_to_fullbank else 16
    if controller.rotary_count != target_rotaries:
        normalize_rotary_controls(controller_node, target_rotaries)
    rotaries = _rotary_controls(controller_node)
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
    for plugin, _plugin_node in selected_plugins:
        mapped_count = min(plugin.parameter_count, len(rotaries), 99)
        if mapped_count <= 0:
            continue
        assignments = [
            _assignment(
                controller_uid,
                int(control.get("id")),
                plugin.plugin_uid,
                parameter_id,
            )
            for parameter_id, (_number, control) in enumerate(rotaries[:mapped_count])
        ]
        combined_assignments.extend(copy.deepcopy(assignments))
        if plugin.plugin_type_id not in installed_types:
            map_id, preset, controller_map = _install_plugin_preset(
                tree,
                controller_node,
                plugin,
                assignments,
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
            _install_runtime_dynamic_map(
                tree,
                map_id=runtime_map_id,
                assignments=combined_assignments,
                preserved_assignments=preserved_runtime_assignments.get(runtime_map_id, []),
                activate=index == 0,
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
