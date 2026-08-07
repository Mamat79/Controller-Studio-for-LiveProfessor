from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class ParameterProfile:
    name: str
    short: str = ""
    unit: str = ""
    stable_id: str = ""
    minimum: float | None = None
    maximum: float | None = None


@dataclass(slots=True)
class PluginProfile:
    plugin_label: str = "LiveProfessor"
    manufacturer: str = ""
    plugin_format: str = ""
    plugin_id: str = ""
    parameters: list[ParameterProfile] = field(default_factory=list)


def short_label(name: str, fallback_index: int | None = None) -> str:
    clean = re.sub(r"[^0-9A-Za-zÀ-ÿ]+", "", name or "")
    if clean:
        return clean[:4]
    if fallback_index is None:
        return "----"
    return f"P{fallback_index + 1:03d}"[-4:]


def load_profile(path: str | Path | None) -> PluginProfile:
    if not path:
        return PluginProfile()
    file_path = Path(path)
    raw = json.loads(file_path.read_text(encoding="utf-8-sig"))
    parameters = []
    for item in raw.get("parameters", []):
        if isinstance(item, str):
            parameters.append(ParameterProfile(name=item))
        else:
            parameters.append(
                ParameterProfile(
                    name=str(item.get("name", "")),
                    short=str(item.get("short", "")),
                    unit=str(item.get("unit", "")),
                    stable_id=str(item.get("stable_id", "")),
                    minimum=item.get("minimum"),
                    maximum=item.get("maximum"),
                )
            )
    return PluginProfile(
        plugin_label=str(raw.get("plugin_label", "LiveProfessor")),
        manufacturer=str(raw.get("manufacturer", "")),
        plugin_format=str(raw.get("plugin_format", "")),
        plugin_id=str(raw.get("plugin_id", "")),
        parameters=parameters,
    )


def profile_names(profile: PluginProfile, count: int) -> tuple[list[str], list[str]]:
    names: list[str] = []
    shorts: list[str] = []
    for index in range(count):
        if index < len(profile.parameters):
            parameter = profile.parameters[index]
            name = parameter.name or f"Parametre {index + 1}"
            short = parameter.short or short_label(name, index)
        else:
            name = f"Parametre {index + 1}"
            short = short_label("", index)
        names.append(name)
        shorts.append(short[:4])
    return names, shorts
