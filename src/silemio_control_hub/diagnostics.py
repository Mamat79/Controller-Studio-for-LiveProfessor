"""Non-mutating diagnostics shared by the desktop UI and packaged smoke test."""

from __future__ import annotations

from typing import Any

from .adapters.devices.ec4_protocol import (
    main_display_message,
    parameter_grid_message,
    total_display_message,
)
from .identity import FULL_PRODUCT_NAME
from .runtime.config import BridgeConfig
from .transports.midi import input_names, output_names
from .transports.osc import decode_message, encode_message


def run_product_diagnostics() -> dict[str, Any]:
    """Exercise config, OSC, EC4 SysEx and the actual packaged MIDI backend."""

    BridgeConfig().validate()
    packet = encode_message("/silemio/diagnostic", [1, "ok"])
    if decode_message(packet) != ("/silemio/diagnostic", [1, "ok"]):
        raise RuntimeError("OSC round-trip mismatch")
    if len(main_display_message([f"P{i + 1}" for i in range(16)])) != 206:
        raise RuntimeError("EC4 main display message mismatch")
    if len(parameter_grid_message([f"P{i + 1}" for i in range(16)])) != 257:
        raise RuntimeError("EC4 grid message mismatch")
    if len(total_display_message(["SiLeMI/O", "Controller Studio"])) != 257:
        raise RuntimeError("EC4 total display message mismatch")
    midi_inputs = input_names()
    midi_outputs = output_names()
    return {
        "product": FULL_PRODUCT_NAME,
        "config": "ok",
        "osc": "ok",
        "ec4_sysex": "ok",
        "midi_backend": "ok",
        "midi_inputs": len(midi_inputs),
        "midi_outputs": len(midi_outputs),
    }
