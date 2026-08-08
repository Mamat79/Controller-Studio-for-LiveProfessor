from __future__ import annotations

import re
from dataclasses import dataclass


MIDI_CHANNEL_13 = 12  # numerotation interne 0..15
MIDI_CHANNEL_14 = 13

MACRO_CONTROLS: dict[tuple[int, int], int] = {
    **{(MIDI_CHANNEL_13, 48 + index): index for index in range(8)},
    **{(MIDI_CHANNEL_14, 73 + index): 8 + index for index in range(8)},
}
PARAMETER_PUSHES = {(MIDI_CHANNEL_13, 40 + index): index for index in range(16)}

SETUP_REQUEST = bytes((0xF0, 0x00, 0x00, 0x00, 0x4E, 0x20, 0x10, 0xF7))
EC4_PREFIX = bytes((0xF0, 0x00, 0x00, 0x00, 0x4E, 0x2C, 0x1B))
BUTTON_PREFIX = EC4_PREFIX + bytes((0x4E,))
SUPPORTED_DISPLAY_SETUPS = {12, 13, 14, 15}
SUPPORTED_DISPLAY_GROUPS = {2, 3}

DISPLAY_ROW_SIZE = 20
DISPLAY_ROWS = 4
DISPLAY_TOTAL_LENGTH = DISPLAY_ROW_SIZE * DISPLAY_ROWS


_CHAR_TABLE = "".join(
    [
        "                ",
        "                ",
        " !\"# %&'()*+,-./",
        "0123456789:;<=>?",
        " ABCDEFGHIJKLMNO",
        "PQRSTUVWXYZÄÖ Ü§",
        " abcdefghijklmno",
        "pqrstuvwxyzäö üà",
        "  ²³            ",
        "          ()    ",
        "@               ",
        "                ",
        "    _           ",
        "                ",
        "                ",
        "          [\\]<|>",
    ]
)
_CHARS = {char: index for index, char in enumerate(_CHAR_TABLE)}
_CHARS[" "] = 0x20


@dataclass(frozen=True, slots=True)
class EC4ButtonEvent:
    kind: str
    index: int | None
    pressed: bool


@dataclass(frozen=True, slots=True)
class EC4SetupState:
    setup: int
    group: int


def translate_text(text: str | None) -> bytes:
    if not text:
        return b""
    return bytes(_CHARS.get(char, 0x1F) for char in str(text))


def _single_line(text: str | None) -> str:
    """Normalise le texte utilisateur avant le remplissage a largeur fixe."""

    return re.sub(r"\s+", " ", str(text or "")).strip()


def _nibble_encoded(data: bytes) -> bytes:
    output = bytearray()
    for value in data:
        output.extend((0x4D, 0x20 | (value >> 4), 0x10 | (value & 0x0F)))
    return bytes(output)


def main_display_message(labels: list[str]) -> bytes:
    """Construit la ligne principale de 16 segments de quatre caracteres."""

    cells = [_single_line(label)[:4].ljust(4) for label in labels[:16]]
    cells.extend(["    "] * (16 - len(cells)))
    content = translate_text("".join(cells))
    header = EC4_PREFIX + bytes((0x4E, 0x22, 0x10, 0x4A, 0x20, 0x10))
    return header + _nibble_encoded(content) + bytes((0xF7,))


def parameter_grid_message(labels: list[str]) -> bytes:
    """Affiche 16 libelles de quatre caracteres dans une grille 4 x 4 persistante."""

    cells = [_single_line(label)[:4].ljust(4) for label in labels[:16]]
    cells.extend(["    "] * (16 - len(cells)))
    rows = []
    for row in range(4):
        start = row * 4
        rows.append(" ".join(cells[start : start + 4]).ljust(DISPLAY_ROW_SIZE))
    content = translate_text("".join(rows))
    header = EC4_PREFIX + bytes((0x4E, 0x22, 0x13, 0x4A, 0x20, 0x10))
    return header + _nibble_encoded(content) + bytes((0x4E, 0x22, 0x14, 0xF7))


def total_display_message(
    lines: list[str], offset: int = 0, alignments: list[str] | None = None
) -> bytes:
    if alignments is None:
        alignments = ["center"] * DISPLAY_ROWS
    alignments = [str(a or "center").lower() for a in alignments]
    alignments.extend(["center"] * (DISPLAY_ROWS - len(alignments)))
    rows = []
    for line, align in zip(lines[:DISPLAY_ROWS], alignments):
        formatted = _single_line(line)[:DISPLAY_ROW_SIZE]
        if align == "left":
            rows.append(formatted.ljust(DISPLAY_ROW_SIZE))
        elif align == "right":
            rows.append(formatted.rjust(DISPLAY_ROW_SIZE))
        else:
            rows.append(formatted.center(DISPLAY_ROW_SIZE))
    rows.extend([" " * DISPLAY_ROW_SIZE] * (DISPLAY_ROWS - len(rows)))
    content = translate_text("".join(rows))
    header = EC4_PREFIX + bytes(
        (0x4E, 0x22, 0x13, 0x4A, 0x20 | ((offset >> 4) & 0x0F), 0x10 | (offset & 0x0F))
    )
    return header + _nibble_encoded(content) + bytes((0x4E, 0x22, 0x14, 0xF7))


def hide_total_display_message() -> bytes:
    blank = translate_text(" " * DISPLAY_TOTAL_LENGTH)
    header = EC4_PREFIX + bytes((0x4E, 0x22, 0x13, 0x4A, 0x20, 0x10))
    return header + _nibble_encoded(blank) + bytes((0x4E, 0x22, 0x15, 0xF7))


def parse_setup_response(data: bytes | tuple[int, ...]) -> EC4SetupState | None:
    raw = bytes(data)
    if (
        len(raw) == 14
        and raw.startswith(EC4_PREFIX)
        and raw[7:9] == bytes((0x4E, 0x28))
        and raw[10:12] == bytes((0x4E, 0x24))
        and raw[-1] == 0xF7
    ):
        return EC4SetupState(setup=raw[9] & 0x0F, group=raw[12] & 0x0F)
    return None


def parse_button_sysex(data: bytes | tuple[int, ...]) -> EC4ButtonEvent | None:
    raw = bytes(data)
    if len(raw) < 14 or not raw.startswith(BUTTON_PREFIX) or raw[-1] != 0xF7:
        return None
    body = raw[8:-1]
    if len(body) != 5 or body[2:4] != bytes((0x4E, 0x2E)):
        return None
    pressed = body[4] == 0x11
    if body[0] == 0x2A and 0x10 <= body[1] <= 0x1F:
        return EC4ButtonEvent("shift_push", body[1] - 0x10, pressed)
    if body[0] == 0x26 and body[1] == 0x11:
        return EC4ButtonEvent("shift", None, pressed)
    if body[0] == 0x26 and 0x12 <= body[1] <= 0x15:
        return EC4ButtonEvent("user", body[1] - 0x12, pressed)
    return None


def feedback_cc(physical_index: int, normalized: float) -> tuple[int, int, int]:
    value = max(0, min(127, round(float(normalized) * 127)))
    if not 0 <= physical_index < 16:
        raise IndexError("encodeur physique hors plage")
    if physical_index < 8:
        return MIDI_CHANNEL_13, 48 + physical_index, value
    return MIDI_CHANNEL_14, 73 + (physical_index - 8), value


def macro_index(channel: int, control: int) -> int | None:
    return MACRO_CONTROLS.get((channel, control))


def parameter_push_index(channel: int, note: int) -> int | None:
    return PARAMETER_PUSHES.get((channel, note))
