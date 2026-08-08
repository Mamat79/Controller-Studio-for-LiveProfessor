"""Repair a LiveProfessor Companion controller exported as a ``.ctrl2`` file.

LiveProfessor stores controller definitions as a JUCE ValueTree binary stream.
By default this utility keeps the original tree (including controller maps) and
only cleans the hardware-control definitions required by EC4 LiveProfessor
Bridge. The optional ``--clean-map-presets`` switch creates a neutral controller
template by removing plugin-specific map presets from the exported file.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
from pathlib import Path
import re
import struct
from typing import Any


MARKER_INT = 1
MARKER_BOOL_TRUE = 2
MARKER_BOOL_FALSE = 3
MARKER_DOUBLE = 4
MARKER_STRING = 5
MARKER_INT64 = 6
MARKER_ARRAY = 7
MARKER_BINARY = 8
MARKER_UNDEFINED = 9


@dataclass
class Variant:
    marker: int | None
    value: Any = None


@dataclass
class ValueTree:
    type_name: str
    properties: list[tuple[str, Variant]]
    children: list["ValueTree"]

    def get(self, name: str, default: Any = None) -> Any:
        for key, variant in self.properties:
            if key == name:
                return variant.value
        return default

    def set(self, name: str, value: Any) -> None:
        for index, (key, variant) in enumerate(self.properties):
            if key == name:
                self.properties[index] = (key, _variant_for(value, variant.marker))
                return
        self.properties.append((name, _variant_for(value)))


class ValueTreeFormatError(ValueError):
    pass


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    def read(self, size: int) -> bytes:
        end = self.position + size
        if end > len(self.data):
            raise ValueTreeFormatError("fin de fichier inattendue")
        chunk = self.data[self.position:end]
        self.position = end
        return chunk

    def read_string(self) -> str:
        try:
            end = self.data.index(0, self.position)
        except ValueError as exc:
            raise ValueTreeFormatError("chaine JUCE non terminee") from exc
        raw = self.data[self.position:end]
        self.position = end + 1
        return raw.decode("utf-8")

    def read_compressed_int(self) -> int:
        size_byte = self.read(1)[0]
        if size_byte == 0:
            return 0
        size = size_byte & 0x7F
        if size > 4:
            raise ValueTreeFormatError("entier compresse JUCE invalide")
        value = int.from_bytes(self.read(size), "little", signed=False)
        return -value if size_byte & 0x80 else value

    def read_variant(self) -> Variant:
        size = self.read_compressed_int()
        if size == 0:
            return Variant(None, None)
        if size < 0:
            raise ValueTreeFormatError("taille de variante negative")

        end = self.position + size
        marker = self.read(1)[0]
        if marker == MARKER_INT:
            value = struct.unpack("<i", self.read(4))[0]
        elif marker == MARKER_BOOL_TRUE:
            value = True
        elif marker == MARKER_BOOL_FALSE:
            value = False
        elif marker == MARKER_DOUBLE:
            value = struct.unpack("<d", self.read(8))[0]
        elif marker == MARKER_STRING:
            value = self.read(size - 1).split(b"\0", 1)[0].decode("utf-8")
        elif marker == MARKER_INT64:
            value = struct.unpack("<q", self.read(8))[0]
        elif marker == MARKER_ARRAY:
            count = self.read_compressed_int()
            value = [self.read_variant() for _ in range(count)]
        elif marker == MARKER_BINARY:
            value = self.read(size - 1)
        elif marker == MARKER_UNDEFINED:
            value = None
        else:
            value = self.read(size - 1)

        if self.position != end:
            raise ValueTreeFormatError(
                f"taille de variante incoherente (marqueur {marker})"
            )
        return Variant(marker, value)

    def read_tree(self) -> ValueTree:
        type_name = self.read_string()
        if not type_name:
            raise ValueTreeFormatError("ValueTree sans type")
        property_count = self.read_compressed_int()
        if property_count < 0:
            raise ValueTreeFormatError("nombre de proprietes negatif")
        properties = []
        for _ in range(property_count):
            properties.append((self.read_string(), self.read_variant()))
        child_count = self.read_compressed_int()
        if child_count < 0:
            raise ValueTreeFormatError("nombre d'enfants negatif")
        children = [self.read_tree() for _ in range(child_count)]
        return ValueTree(type_name, properties, children)


def _compressed_int(value: int) -> bytes:
    negative = value < 0
    unsigned = -value if negative else value
    payload = bytearray()
    while unsigned:
        payload.append(unsigned & 0xFF)
        unsigned >>= 8
    size = len(payload) | (0x80 if negative else 0)
    return bytes((size,)) + bytes(payload)


def _string(value: str) -> bytes:
    return value.encode("utf-8") + b"\0"


def _variant_for(value: Any, preferred_marker: int | None = None) -> Variant:
    if isinstance(value, bool):
        return Variant(MARKER_BOOL_TRUE if value else MARKER_BOOL_FALSE, value)
    if isinstance(value, int):
        marker = preferred_marker if preferred_marker in {MARKER_INT, MARKER_INT64} else MARKER_INT
        return Variant(marker, value)
    if isinstance(value, float):
        return Variant(MARKER_DOUBLE, value)
    if isinstance(value, str):
        return Variant(MARKER_STRING, value)
    if value is None:
        return Variant(None, None)
    raise TypeError(f"type de variante non pris en charge: {type(value).__name__}")


def _write_variant(variant: Variant) -> bytes:
    marker = variant.marker
    value = variant.value
    if marker is None:
        return _compressed_int(0)
    if marker == MARKER_INT:
        payload = bytes((marker,)) + struct.pack("<i", int(value))
    elif marker == MARKER_BOOL_TRUE:
        payload = bytes((marker,))
    elif marker == MARKER_BOOL_FALSE:
        payload = bytes((marker,))
    elif marker == MARKER_DOUBLE:
        payload = bytes((marker,)) + struct.pack("<d", float(value))
    elif marker == MARKER_STRING:
        payload = bytes((marker,)) + _string(str(value))
    elif marker == MARKER_INT64:
        payload = bytes((marker,)) + struct.pack("<q", int(value))
    elif marker == MARKER_ARRAY:
        values = value or []
        payload = bytes((marker,)) + _compressed_int(len(values))
        payload += b"".join(_write_variant(item) for item in values)
    elif marker == MARKER_BINARY:
        payload = bytes((marker,)) + bytes(value)
    elif marker == MARKER_UNDEFINED:
        payload = bytes((marker,))
    else:
        payload = bytes((marker,)) + bytes(value)
    return _compressed_int(len(payload)) + payload


def write_tree(tree: ValueTree) -> bytes:
    output = bytearray(_string(tree.type_name))
    output += _compressed_int(len(tree.properties))
    for name, variant in tree.properties:
        output += _string(name)
        output += _write_variant(variant)
    output += _compressed_int(len(tree.children))
    for child in tree.children:
        output += write_tree(child)
    return bytes(output)


def parse_tree(data: bytes) -> ValueTree:
    reader = Reader(data)
    tree = reader.read_tree()
    if reader.position != len(data):
        raise ValueTreeFormatError(
            f"donnees restantes apres le ValueTree: {len(data) - reader.position} octets"
        )
    return tree


def _child(tree: ValueTree, type_name: str) -> ValueTree:
    for child in tree.children:
        if child.type_name == type_name:
            return child
    raise ValueTreeFormatError(f"noeud {type_name!r} introuvable")


def _walk(tree: ValueTree):
    yield tree
    for child in tree.children:
        yield from _walk(child)


def normalize_rotary_controls(tree: ValueTree, rotary_count: int) -> dict[str, int]:
    """Resize the Companion rotary list while preserving the controller structure."""

    if not 16 <= rotary_count <= 99:
        raise ValueTreeFormatError("le nombre de rotatifs doit etre compris entre 16 et 99")
    controls_node = _child(tree, "Controls")
    controls = [child for child in controls_node.children if child.type_name == "HardwareControl"]
    rotary_pattern = re.compile(r"^/Companion/Rotary(\d+)$", re.IGNORECASE)
    rotaries: dict[int, ValueTree] = {}
    for control in controls:
        match = rotary_pattern.match(str(control.get("OSCAddressPatern", "")))
        if not match or control.get("ControlStyle") != 0:
            continue
        number = int(match.group(1))
        if number in rotaries:
            raise ValueTreeFormatError(f"rotatif {number} defini plusieurs fois")
        rotaries[number] = control

    missing_base = sorted(set(range(1, 17)) - set(rotaries))
    if missing_base:
        raise ValueTreeFormatError(f"rotatifs de base absents: {missing_base}")

    removed_ids: set[int] = set()
    kept_children = []
    removed = 0
    for child in controls_node.children:
        match = rotary_pattern.match(str(child.get("OSCAddressPatern", "")))
        if (
            child.type_name == "HardwareControl"
            and child.get("ControlStyle") == 0
            and match
            and int(match.group(1)) > rotary_count
        ):
            removed += 1
            removed_ids.add(int(child.get("id")))
            continue
        kept_children.append(child)
    controls_node.children = kept_children

    if removed_ids:
        for node in _walk(tree):
            if node.type_name != "Assignments":
                continue
            node.children = [
                assignment
                for assignment in node.children
                if assignment.get("ControllerId") not in removed_ids
            ]

    used_ids = {
        int(control.get("id"))
        for control in controls_node.children
        if control.type_name == "HardwareControl" and control.get("id") is not None
    }
    next_id = max(used_ids, default=22_000_000) + 1
    template = rotaries[16]
    added = 0
    for number in range(17, rotary_count + 1):
        if number in rotaries and number <= rotary_count:
            continue
        while next_id in used_ids:
            next_id += 1
        control = copy.deepcopy(template)
        control.set("id", next_id)
        control.set("Name", f"Rotary {number}")
        control.set("tag", f"Rotary{number}")
        control.set("OSCAddressPatern", f"/Companion/Rotary{number}")
        controls_node.children.append(control)
        used_ids.add(next_id)
        next_id += 1
        added += 1

    return {"rotaries_added": added, "rotaries_removed": removed}


def repair_controller(
    tree: ValueTree,
    *,
    clean_map_presets: bool = False,
    expected_rotaries: int = 16,
) -> dict[str, int]:
    if tree.type_name != "LPController":
        raise ValueTreeFormatError("le fichier n'est pas un controleur LiveProfessor")

    controls_node = _child(tree, "Controls")
    controls = [child for child in controls_node.children if child.type_name == "HardwareControl"]
    if len(controls) < 32:
        raise ValueTreeFormatError(
            f"32 controles attendus (16 boutons + 16 rotatifs), {len(controls)} trouves"
        )

    button_ids: set[int] = set()
    for number, control in enumerate(controls[:16], start=1):
        expected_tag = f"GenericButton{number}"
        if control.get("ControlStyle") != 2 or control.get("tag") != expected_tag:
            raise ValueTreeFormatError(
                f"le controle {number} n'est pas le bouton Companion {expected_tag}"
            )
        control.set("Name", f"Generic Button {number}")
        control.set("OSCAddressPatern", f"/Companion/GenericButtons/Button{number}")
        button_ids.add(int(control.get("id")))

    rotaries: dict[int, ValueTree] = {}
    rotary_pattern = re.compile(r"^/Companion/Rotary(\d+)$", re.IGNORECASE)
    for control in controls:
        match = rotary_pattern.match(str(control.get("OSCAddressPatern", "")))
        if match and control.get("ControlStyle") == 0:
            number = int(match.group(1))
            if number in rotaries:
                raise ValueTreeFormatError(f"rotatif {number} defini plusieurs fois")
            rotaries[number] = control

    expected_rotary_numbers = set(range(1, expected_rotaries + 1))
    if set(rotaries) != expected_rotary_numbers:
        missing = sorted(expected_rotary_numbers - set(rotaries))
        extra = sorted(set(rotaries) - expected_rotary_numbers)
        raise ValueTreeFormatError(f"rotatifs invalides; absents={missing}, en trop={extra}")

    for number, control in rotaries.items():
        control.set("Name", f"Rotary {number}")
        # LiveProfessor uses this Companion tag in ControllerNames and
        # ControllerValues feedback. Controls added manually have an empty tag,
        # which is why only the four factory rotaries expose their labels.
        control.set("tag", f"Rotary{number}")
        control.set("OSCAddressPatern", f"/Companion/Rotary{number}")

    assignments_removed = 0
    for node in _walk(tree):
        if node.type_name != "Assignments":
            continue
        kept = []
        for assignment in node.children:
            if assignment.type_name == "Assignment" and assignment.get("ControllerId") in button_ids:
                assignments_removed += 1
            else:
                kept.append(assignment)
        node.children = kept

    map_presets_removed = 0
    if clean_map_presets:
        for node in _walk(tree):
            if node.type_name != "MapPresets":
                continue
            map_presets_removed += len(node.children)
            node.children = []

    addresses: dict[str, str] = {}
    duplicates = []
    for control in controls:
        address = str(control.get("OSCAddressPatern", ""))
        if not address:
            continue
        if address in addresses:
            duplicates.append(address)
        addresses[address] = str(control.get("Name", ""))
    if duplicates:
        raise ValueTreeFormatError(
            "adresses OSC encore dupliquees: " + ", ".join(sorted(set(duplicates)))
        )

    return {
        "controls": len(controls),
        "buttons": 16,
        "rotaries": expected_rotaries,
        "assignments_removed": assignments_removed,
        "map_presets_removed": map_presets_removed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--clean-map-presets",
        action="store_true",
        help="supprime les presets de mapping lies a des plugins ou projets",
    )
    parser.add_argument(
        "--rotaries",
        type=int,
        choices=(16, 99),
        default=16,
        help="cree un controleur UniBank (16) ou FullBank (99)",
    )
    args = parser.parse_args()

    original = args.source.read_bytes()
    original_tree = parse_tree(original)
    if write_tree(original_tree) != original:
        raise ValueTreeFormatError("le test de reecriture identique a echoue")

    resize_stats = normalize_rotary_controls(original_tree, args.rotaries)
    stats = repair_controller(
        original_tree,
        clean_map_presets=args.clean_map_presets,
        expected_rotaries=args.rotaries,
    )
    stats.update(resize_stats)
    repaired = write_tree(original_tree)
    reparsed = parse_tree(repaired)
    if write_tree(reparsed) != repaired:
        raise ValueTreeFormatError("la validation du fichier repare a echoue")

    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_bytes(repaired)
    print(
        f"Controleur repare: {args.destination} | "
        f"{stats['rotaries']} rotatifs uniques | "
        f"{stats['assignments_removed']} assignation(s) parasite(s) supprimee(s) | "
        f"{stats['map_presets_removed']} preset(s) de mapping supprime(s) | "
        f"{stats['rotaries_added']} ajoute(s), {stats['rotaries_removed']} retire(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
