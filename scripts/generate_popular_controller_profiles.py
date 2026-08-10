"""Generate the popular-controller profiles shipped with Controller Studio.

The generated JSON is intentionally committed twice: once as an application
resource and once in the public, remotely updatable library.  Keeping the
definitions here makes the two copies deterministic and reviewable.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "silemio_control_hub" / "controller_profiles"
LIBRARY = ROOT / "library" / "controllers"
sys.path.insert(0, str(ROOT / "src"))

from silemio_control_hub.models import ControllerProfile  # noqa: E402


def midi(message: str, channel: int, number: int | None = None, mode: str | None = None) -> dict[str, Any]:
    binding: dict[str, Any] = {"message": message, "channel": channel}
    if number is not None:
        binding["number"] = number
    if mode is not None:
        binding["mode"] = mode
    return binding


def rotary(
    control_id: str,
    cc: int,
    *,
    channel: int = 1,
    relative: str | None = None,
    push: tuple[str, int, int] | None = None,
    value_feedback: bool = False,
) -> dict[str, Any]:
    binding = midi("cc", channel, cc, relative)
    control: dict[str, Any] = {
        "id": control_id,
        "kind": "relative_encoder" if relative else "absolute_encoder",
        "input": binding,
    }
    if push is not None:
        control["push"] = midi(push[0], push[1], push[2])
    if value_feedback:
        control["feedback"] = {"value": binding}
    return control


def fader(
    control_id: str,
    number: int | None = None,
    *,
    channel: int = 1,
    pitch_bend: bool = False,
    touch_note: int | None = None,
    value_feedback: bool = False,
) -> dict[str, Any]:
    binding = midi("pitch_bend", channel) if pitch_bend else midi("cc", channel, number)
    control: dict[str, Any] = {"id": control_id, "kind": "fader", "input": binding}
    if touch_note is not None:
        control["touch"] = midi("note", 1, touch_note)
    if value_feedback:
        control["feedback"] = {"value": binding}
    return control


def switch(
    control_id: str,
    number: int,
    *,
    channel: int = 1,
    message: str = "note",
    pad: bool = False,
    led_feedback: bool = False,
) -> dict[str, Any]:
    binding = midi(message, channel, number)
    control: dict[str, Any] = {
        "id": control_id,
        "kind": "pad" if pad else "button",
        "input": binding,
    }
    if led_feedback:
        control["feedback"] = {"led": binding}
    return control


def profile(
    profile_id: str,
    manufacturer: str,
    model: str,
    controls: Iterable[dict[str, Any]],
    *,
    input_patterns: Iterable[str],
    output_patterns: Iterable[str] | None = None,
    bank_size: int | None = None,
    page_count: int = 1,
    capabilities: Iterable[str] = ("commands",),
    firmware: str | None = None,
) -> dict[str, Any]:
    control_list = list(controls)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "profile_version": "1.0.0",
        "id": profile_id,
        "manufacturer": manufacturer,
        "model": model,
        "midi_identity": {
            "input_name_patterns": list(input_patterns),
            "output_name_patterns": list(output_patterns or input_patterns),
        },
        "bank_size": bank_size or len(control_list),
        "page_count": page_count,
        "status": "community",
        "capabilities": list(capabilities),
        "controls": control_list,
    }
    if firmware is not None:
        payload["firmware"] = firmware
    return payload


def numbered_rotaries(count: int, first_cc: int, *, prefix: str = "encoder", channel: int = 1) -> list[dict[str, Any]]:
    return [rotary(f"{prefix}_{index:02d}", first_cc + index - 1, channel=channel) for index in range(1, count + 1)]


def numbered_faders(count: int, first_cc: int, *, channel: int = 1) -> list[dict[str, Any]]:
    return [fader(f"fader_{index:02d}", first_cc + index - 1, channel=channel) for index in range(1, count + 1)]


def numbered_pads(count: int, first_note: int, *, channel: int = 10, prefix: str = "pad") -> list[dict[str, Any]]:
    return [switch(f"{prefix}_{index:02d}", first_note + index - 1, channel=channel, pad=True) for index in range(1, count + 1)]


def mcu_controls(channels: int) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    for index in range(channels):
        controls.append(
            fader(
                f"channel_{index + 1:02d}_fader",
                channel=index + 1,
                pitch_bend=True,
                touch_note=104 + index,
                value_feedback=True,
            )
        )
    for index in range(channels):
        controls.append(
            rotary(
                f"channel_{index + 1:02d}_vpot",
                16 + index,
                relative="signed_bit",
                push=("note", 1, 32 + index),
                value_feedback=True,
            )
        )
    return controls


def mcu_profile(
    profile_id: str,
    manufacturer: str,
    model: str,
    *,
    channels: int,
    patterns: Iterable[str],
    page_count: int = 1,
    firmware: str | None = None,
) -> dict[str, Any]:
    capabilities = ["commands", "push", "touch", "led", "values", "motorized", "high_resolution"]
    if page_count > 1:
        capabilities.append("pages")
    return profile(
        profile_id,
        manufacturer,
        model,
        mcu_controls(channels),
        input_patterns=patterns,
        bank_size=channels * 2,
        page_count=page_count,
        capabilities=capabilities,
        firmware=firmware,
    )


def _midimix() -> dict[str, Any]:
    row_ccs = (
        (16, 20, 24, 28, 46, 50, 54, 58),
        (17, 21, 25, 29, 47, 51, 55, 59),
        (18, 22, 26, 30, 48, 52, 56, 60),
    )
    controls = [
        rotary(f"knob_r{row}_c{column}", cc)
        for row, ccs in enumerate(row_ccs, start=1)
        for column, cc in enumerate(ccs, start=1)
    ]
    controls += [
        fader(f"channel_{index:02d}_fader", cc)
        for index, cc in enumerate((19, 23, 27, 31, 49, 53, 57, 61), start=1)
    ]
    controls.append(fader("master_fader", 62))
    controls += [
        switch(f"mute_{index:02d}", note)
        for index, note in enumerate((1, 4, 7, 10, 13, 16, 19, 22), start=1)
    ]
    controls += [
        switch(f"rec_arm_{index:02d}", note)
        for index, note in enumerate((3, 6, 9, 12, 15, 18, 21, 24), start=1)
    ]
    return profile(
        "akai.midimix.factory",
        "Akai Professional",
        "MIDImix — Factory Layout",
        controls,
        input_patterns=("MIDI Mix", "MIDImix"),
        capabilities=("commands", "led"),
    )


def _minilab3() -> dict[str, Any]:
    controls = [
        rotary("main_encoder", 114, relative="increment_decrement", push=("cc", 1, 115)),
    ]
    controls += [rotary(f"encoder_{index:02d}", cc) for index, cc in enumerate((74, 71, 76, 77, 93, 18, 19, 16), 1)]
    controls += [fader(f"fader_{index:02d}", cc) for index, cc in enumerate((82, 83, 85, 17), 1)]
    controls += [switch(f"pad_{index:02d}", cc, message="cc", pad=True) for index, cc in enumerate(range(102, 110), 1)]
    return profile(
        "arturia.minilab-3.user",
        "Arturia",
        "MiniLab 3 — User Program",
        controls,
        input_patterns=("MiniLab 3 MIDI", "MiniLab 3"),
        capabilities=("commands", "push", "display"),
    )


def _mpk(profile_id: str, model: str, patterns: tuple[str, ...]) -> dict[str, Any]:
    controls = numbered_rotaries(8, 70) + numbered_pads(8, 36)
    return profile(
        profile_id,
        "Akai Professional",
        model,
        controls,
        input_patterns=patterns,
        capabilities=("commands", "banks"),
    )


def _launchkey(profile_id: str, model: str, patterns: tuple[str, ...], *, full_size: bool) -> dict[str, Any]:
    controls = numbered_rotaries(8, 21)
    if full_size:
        controls += numbered_faders(9, 41)
        controls += [switch(f"fader_button_{index:02d}", 51 + index - 1, message="cc") for index in range(1, 10)]
    else:
        controls += numbered_pads(16, 36)
    return profile(
        profile_id,
        "Novation",
        model,
        controls,
        input_patterns=patterns,
        page_count=4,
        capabilities=("commands", "led", "pages"),
    )


def _keylab_essential_mk3() -> dict[str, Any]:
    controls = numbered_rotaries(9, 74) + numbered_faders(9, 83) + numbered_pads(8, 36)
    return profile(
        "arturia.keylab-essential-mk3.user-program",
        "Arturia",
        "KeyLab Essential MK3 — User Program",
        controls,
        input_patterns=("KeyLab Essential 49 mk3 MIDI", "KeyLab Essential 61 mk3 MIDI", "KeyLab Essential mk3"),
        capabilities=("commands", "led"),
    )


def _beatstep() -> dict[str, Any]:
    controls = numbered_rotaries(16, 20) + numbered_pads(16, 36, channel=1)
    return profile(
        "arturia.beatstep.user-preset",
        "Arturia",
        "BeatStep — User Preset",
        controls,
        input_patterns=("Arturia BeatStep", "BeatStep"),
        capabilities=("commands", "led", "banks"),
    )


def _launch_control_xl2() -> dict[str, Any]:
    controls = numbered_rotaries(24, 13) + numbered_faders(8, 5)
    controls += [switch(f"button_{index:02d}", 37 + index - 1, message="cc") for index in range(1, 17)]
    return profile(
        "novation.launch-control-xl2.user-template",
        "Novation",
        "Launch Control XL MK2 — User Template",
        controls,
        input_patterns=("Launch Control XL",),
        capabilities=("commands", "led", "colors"),
    )


def _apc_mini_mk2() -> dict[str, Any]:
    controls = numbered_faders(9, 48)
    controls += [switch(f"track_button_{index:02d}", 99 + index, led_feedback=True) for index in range(1, 9)]
    controls += [switch(f"scene_button_{index:02d}", 111 + index, led_feedback=True) for index in range(1, 9)]
    controls += [switch(f"grid_pad_{index:02d}", index - 1, pad=True, led_feedback=True) for index in range(1, 65)]
    return profile(
        "akai.apc-mini-mk2.port-0",
        "Akai Professional",
        "APC Mini MK2 — Port 0",
        controls,
        input_patterns=("APC mini mk2 0", "APC mini mk2"),
        bank_size=25,
        capabilities=("commands", "led", "colors"),
    )


def _launchpad(profile_id: str, model: str, patterns: tuple[str, ...]) -> dict[str, Any]:
    controls = numbered_faders(8, 21)
    controls += [switch(f"switch_{index:02d}", 35 + index, pad=True, led_feedback=True) for index in range(1, 9)]
    return profile(
        profile_id,
        "Novation",
        model,
        controls,
        input_patterns=patterns,
        capabilities=("commands", "led", "colors"),
    )


PROFILES: tuple[tuple[str, str, str, dict[str, Any]], ...] = (
    ("akai-midimix-factory.json", "akai", "midimix-factory", _midimix()),
    ("arturia-minilab-3-user.json", "arturia", "minilab-3-user", _minilab3()),
    ("akai-mpk-mini-mk3-program-1.json", "akai", "mpk-mini-mk3-program-1", _mpk("akai.mpk-mini-mk3.program-1", "MPK Mini MK3 — Program 1", ("MPK mini 3", "MPK mini mk3"))),
    ("akai-mpk-mini-iv-user-program.json", "akai", "mpk-mini-iv-user-program", _mpk("akai.mpk-mini-iv.user-program", "MPK Mini IV — User Program", ("MPK mini IV", "MPK mini 4"))),
    ("akai-mpk-mini-plus-program-1.json", "akai", "mpk-mini-plus-program-1", _mpk("akai.mpk-mini-plus.program-1", "MPK Mini Plus — Program 1", ("MPK mini Plus",))),
    ("novation-launchkey-mk3-compact-custom.json", "novation", "launchkey-mk3-compact-custom", _launchkey("novation.launchkey-mk3.compact-custom", "Launchkey Mini MK3 — Custom Modes", ("Launchkey Mini MK3 MIDI", "Launchkey Mini MK3"), full_size=False)),
    ("novation-launchkey-mk3-full-custom.json", "novation", "launchkey-mk3-full-custom", _launchkey("novation.launchkey-mk3.49-61-88-custom", "Launchkey MK3 49/61/88 — Custom Modes", ("Launchkey MK3 MIDI", "Launchkey MK3"), full_size=True)),
    ("novation-launchkey-mk4-compact-custom.json", "novation", "launchkey-mk4-compact-custom", _launchkey("novation.launchkey-mk4.compact-custom", "Launchkey Mini 25/37 MK4 — Custom Modes", ("Launchkey Mini MK4 MIDI", "Launchkey MK4 MIDI"), full_size=False)),
    ("novation-launchkey-mk4-full-custom.json", "novation", "launchkey-mk4-full-custom", _launchkey("novation.launchkey-mk4.49-61-88-custom", "Launchkey MK4 49/61/88 — Custom Modes", ("Launchkey MK4 MIDI", "Launchkey MK4"), full_size=True)),
    ("arturia-keylab-essential-mk3-user-program.json", "arturia", "keylab-essential-mk3-user-program", _keylab_essential_mk3()),
    ("arturia-beatstep-user-preset.json", "arturia", "beatstep-user-preset", _beatstep()),
    ("novation-launch-control-xl2-user-template.json", "novation", "launch-control-xl2-user-template", _launch_control_xl2()),
    ("akai-apc-mini-mk2-port-0.json", "akai", "apc-mini-mk2-port-0", _apc_mini_mk2()),
    ("novation-launchpad-x-custom-faders.json", "novation", "launchpad-x-custom-faders", _launchpad("novation.launchpad-x.custom-faders", "Launchpad X — Custom Faders", ("Launchpad X MIDI", "Launchpad X"))),
    ("novation-launchpad-mini-mk3-custom-faders.json", "novation", "launchpad-mini-mk3-custom-faders", _launchpad("novation.launchpad-mini-mk3.custom-faders", "Launchpad Mini MK3 — Custom Faders", ("Launchpad Mini MK3 MIDI", "Launchpad Mini MK3"))),
    ("presonus-faderport-v2-mcu.json", "presonus", "faderport-v2-mcu", mcu_profile("presonus.faderport-v2.mcu", "PreSonus", "FaderPort V2 — MCU", channels=1, patterns=("PreSonus FP2", "FaderPort"))),
    ("presonus-faderport-8-mcu.json", "presonus", "faderport-8-mcu", mcu_profile("presonus.faderport-8.mcu", "PreSonus", "FaderPort 8 — MCU", channels=8, patterns=("PreSonus FP8", "FaderPort 8"))),
    ("presonus-faderport-16-mcu.json", "presonus", "faderport-16-mcu", mcu_profile("presonus.faderport-16.mcu", "PreSonus", "FaderPort 16 — MCU Base + Extender", channels=8, page_count=2, patterns=("PreSonus FP16", "FaderPort 16"))),
    ("behringer-x-touch-mcu.json", "behringer", "x-touch-mcu", mcu_profile("behringer.x-touch.mcu", "Behringer", "X-Touch — MC/MCU", channels=8, patterns=("X-TOUCH", "X-Touch"))),
    ("ssl-uf1-mcu.json", "ssl", "uf1-mcu", mcu_profile("ssl.uf1.mcu", "Solid State Logic", "UF1 — MCU", channels=1, patterns=("SSL UF1", "UF1"))),
    ("ssl-uf8-mcu.json", "ssl", "uf8-mcu", mcu_profile("ssl.uf8.mcu", "Solid State Logic", "UF8 — MCU", channels=8, patterns=("SSL UF8", "UF8"))),
)


def main() -> int:
    SOURCE.mkdir(parents=True, exist_ok=True)
    for filename, vendor, slug, payload in PROFILES:
        ControllerProfile.from_dict(payload)
        serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        source_path = SOURCE / filename
        library_path = LIBRARY / vendor / slug / "1.0.0" / "profile.json"
        library_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(serialized, encoding="utf-8", newline="\n")
        library_path.write_text(serialized, encoding="utf-8", newline="\n")
        print(f"ÉCRIT: {payload['id']}")
    print(f"{len(PROFILES)} profils populaires générés")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
