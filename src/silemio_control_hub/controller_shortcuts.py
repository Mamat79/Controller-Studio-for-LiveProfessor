"""Controller-specific shortcut actions and safe persisted bindings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import ControllerProfile


@dataclass(frozen=True, slots=True)
class ShortcutAction:
    id: str
    label_fr: str
    label_en: str
    display_label: str

    def label(self, language: str) -> str:
        return self.label_en if language == "en" else self.label_fr


SHORTCUT_ACTIONS = (
    ShortcutAction("previous_bank", "Banque précédente", "Previous bank", "Bk-"),
    ShortcutAction("next_bank", "Banque suivante", "Next bank", "Bk+"),
    ShortcutAction("previous_view", "View Set précédent", "Previous View Set", "VS-"),
    ShortcutAction("next_view", "View Set suivant", "Next View Set", "VS+"),
    ShortcutAction("show_hide_plugin", "Afficher / masquer le plug-in", "Show / hide plug-in", "Show"),
    ShortcutAction("toggle_processing", "Activer / désactiver le plug-in", "Enable / disable plug-in", "OnOf"),
    ShortcutAction("previous_chain", "Chaîne précédente", "Previous chain", "ChUp"),
    ShortcutAction("next_chain", "Chaîne suivante", "Next chain", "ChDn"),
    ShortcutAction("previous_plugin", "Plug-in précédent", "Previous plug-in", "<Plg"),
    ShortcutAction("next_plugin", "Plug-in suivant", "Next plug-in", "Plg>"),
    ShortcutAction("previous_cue", "Cue précédent", "Previous cue", "Cue-"),
    ShortcutAction("next_cue", "Cue suivant", "Next cue", "Cue+"),
    ShortcutAction("previous_snapshot", "Snapshot précédent", "Previous snapshot", "Sn-"),
    ShortcutAction("next_snapshot", "Snapshot suivant", "Next snapshot", "Sn+"),
    ShortcutAction("tap_tempo", "Tap Tempo", "Tap Tempo", "Tap"),
)

SHORTCUT_ACTION_BY_ID = {action.id: action for action in SHORTCUT_ACTIONS}


EC4_DEFAULT_SHORTCUTS = {
    "shift+encoder_01": "previous_bank",
    "shift+encoder_02": "next_bank",
    "shift+encoder_03": "previous_view",
    "shift+encoder_04": "next_view",
    "shift+encoder_05": "show_hide_plugin",
    "shift+encoder_06": "previous_chain",
    "shift+encoder_07": "previous_plugin",
    "shift+encoder_08": "next_plugin",
    "shift+encoder_09": "toggle_processing",
    "shift+encoder_10": "next_chain",
    "shift+encoder_11": "previous_plugin",
    "shift+encoder_12": "next_plugin",
    "shift+encoder_13": "previous_cue",
    "shift+encoder_14": "next_cue",
    "shift+encoder_15": "previous_snapshot",
    "shift+encoder_16": "next_snapshot",
    "encoder_16": "tap_tempo",
}


def shortcut_binding_key(control_id: str, modifier_id: str | None = None) -> str:
    return f"{modifier_id}+{control_id}" if modifier_id else control_id


def configurable_shortcut_bindings(profile: ControllerProfile) -> tuple[str, ...]:
    """Return every button/push chord that can be configured for a profile."""

    controls = tuple(control for control in profile.controls if control.supports_press)
    direct = tuple(control.id for control in controls)
    modified = tuple(
        shortcut_binding_key(control.id, modifier.id)
        for modifier in profile.modifiers
        for control in controls
    )
    return direct + modified


def default_shortcuts(profile: ControllerProfile) -> dict[str, str]:
    if profile.id == "faderfox.ec4":
        return dict(EC4_DEFAULT_SHORTCUTS)
    return {}


def normalize_shortcuts_by_controller(value: object) -> dict[str, dict[str, str]]:
    """Drop malformed settings while preserving explicit empty assignments."""

    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, dict[str, str]] = {}
    for controller_id, bindings in value.items():
        if not isinstance(controller_id, str) or not controller_id.strip():
            continue
        if not isinstance(bindings, dict):
            continue
        controller_bindings: dict[str, str] = {}
        for binding, action_id in bindings.items():
            if not isinstance(binding, str) or not binding.strip():
                continue
            if action_id == "":
                controller_bindings[binding.strip()] = ""
            elif isinstance(action_id, str) and action_id in SHORTCUT_ACTION_BY_ID:
                controller_bindings[binding.strip()] = action_id
        cleaned[controller_id.strip()] = controller_bindings
    return cleaned


def effective_shortcuts(
    profile: ControllerProfile,
    shortcuts_by_controller: Mapping[str, Mapping[str, str]] | None,
) -> dict[str, str]:
    """Merge controller defaults with the user's complete per-controller choices."""

    result = default_shortcuts(profile)
    if shortcuts_by_controller and profile.id in shortcuts_by_controller:
        result.update(shortcuts_by_controller[profile.id])
    allowed = set(configurable_shortcut_bindings(profile))
    return {
        binding: action_id
        for binding, action_id in result.items()
        if binding in allowed and action_id in SHORTCUT_ACTION_BY_ID
    }

