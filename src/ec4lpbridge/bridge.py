from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import BridgeConfig
from .ec4_protocol import (
    MIDI_CHANNEL_13,
    MIDI_CHANNEL_14,
    SETUP_REQUEST,
    SUPPORTED_DISPLAY_GROUPS,
    SUPPORTED_DISPLAY_SETUPS,
    EC4SetupState,
    feedback_cc,
    hide_total_display_message,
    macro_index,
    main_display_message,
    parameter_grid_message,
    parameter_push_index,
    parse_button_sysex,
    parse_setup_response,
    total_display_message,
)
from .midi_backend import MidiBackendError, MidiConnection
from .osc_codec import OSCClient, OSCServer
from .profiles import load_profile, profile_names, short_label


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class BridgeSnapshot:
    running: bool
    midi_connected: bool
    active_bank: int
    bank_count: int
    setup: int | None
    group: int | None
    status: str


StatusCallback = Callable[[BridgeSnapshot], None]
LogCallback = Callable[[str], None]
MidiLearnCallback = Callable[[str, int, int, int], bool]


class EC4LiveProfessorBridge:
    def __init__(
        self,
        config: BridgeConfig,
        status_callback: StatusCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.status_callback = status_callback
        self.log_callback = log_callback
        self.profile = load_profile(config.profile_file)
        self.names, self.short_names = profile_names(self.profile, config.max_controls)
        self.display_values = ["-"] * config.max_controls
        self.values = [0.0] * config.max_controls
        self.active_bank = min(config.start_bank, self.bank_count - 1)
        self.setup_state: EC4SetupState | None = None
        self.status = "Arrete"
        self._running = False
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._midi = MidiConnection(self._on_midi)
        self._osc_client = OSCClient(config.liveprofessor_host, config.liveprofessor_port)
        self._osc_server = OSCServer(
            config.feedback_host,
            config.feedback_port,
            self._on_osc,
            self._on_osc_error,
        )
        self._reconnect_thread: threading.Thread | None = None
        self._overlay_timer: threading.Timer | None = None
        self._last_feedback: dict[int, tuple[int, float]] = {}
        self._midi_learn_callback: MidiLearnCallback | None = None
        self._received_companion_names = False

    @property
    def bank_count(self) -> int:
        return max(1, math.ceil(self.config.max_controls / self.config.bank_size))

    @property
    def running(self) -> bool:
        return self._running

    def snapshot(self) -> BridgeSnapshot:
        state = self.setup_state
        return BridgeSnapshot(
            running=self._running,
            midi_connected=self._midi.is_open,
            active_bank=self.active_bank,
            bank_count=self.bank_count,
            setup=state.setup if state else None,
            group=state.group if state else None,
            status=self.status,
        )

    def _notify(self) -> None:
        if self.status_callback:
            try:
                self.status_callback(self.snapshot())
            except Exception:
                LOGGER.exception("erreur du callback d'etat")

    def _log(self, message: str, level: int = logging.INFO) -> None:
        LOGGER.log(level, message)
        if self.log_callback:
            try:
                self.log_callback(message)
            except Exception:
                LOGGER.exception("erreur du callback de journal")

    def start(self) -> None:
        if self._running:
            return
        self._stop.clear()
        self._running = True
        try:
            self._osc_server.start()
            self._log(
                f"OSC feedback en ecoute sur {self.config.feedback_host}:{self.config.feedback_port}"
            )
        except OSError as exc:
            self._running = False
            self.status = f"Port OSC indisponible: {exc}"
            self._notify()
            raise
        self.status = "Recherche du Faderfox EC4"
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop, name="midi-reconnect", daemon=True
        )
        self._reconnect_thread.start()
        if self.config.mode == "companion":
            self.refresh_companion()
        self._notify()

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        if self._overlay_timer:
            self._overlay_timer.cancel()
            self._overlay_timer = None
        self._osc_server.stop()
        self._midi.close()
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=2.0)
        self._reconnect_thread = None
        self.status = "Arrete"
        self._notify()

    def _reconnect_loop(self) -> None:
        last_error = ""
        next_companion_refresh = time.monotonic() + 10.0
        while not self._stop.is_set():
            if self._midi.is_open and not self._midi.ports_still_available():
                self._log("Faderfox EC4 deconnecte; attente de sa reconnexion", logging.WARNING)
                self._midi.close()
                self.status = "EC4 deconnecte - nouvelle tentative automatique"
                self._notify()
            if not self._midi.is_open:
                try:
                    input_name, output_name = self._midi.open(
                        self.config.midi_input, self.config.midi_output
                    )
                    self.status = "Connecte"
                    self._log(f"MIDI connecte: entree={input_name!r}, sortie={output_name!r}")
                    if self.config.setup_request_on_connect:
                        self._midi.send_sysex(SETUP_REQUEST)
                        self._log("Requete du setup/groupe EC4 envoyee")
                    last_error = ""
                    self._notify()
                except Exception as exc:
                    error = str(exc)
                    self.status = "EC4 deconnecte - nouvelle tentative automatique"
                    if error != last_error:
                        self._log(error, logging.WARNING)
                        last_error = error
                    self._notify()
            if (
                self.config.mode == "companion"
                and not self._received_companion_names
                and time.monotonic() >= next_companion_refresh
            ):
                self.refresh_companion(log_request=False)
                next_companion_refresh = time.monotonic() + 10.0
            self._stop.wait(self.config.reconnect_interval_s)

    def _on_osc_error(self, exc: Exception) -> None:
        self._log(f"Paquet OSC ignore: {exc}", logging.WARNING)

    def _send_osc(self, address: str, *args: Any) -> None:
        try:
            self._osc_client.send(address, *args)
            LOGGER.debug("OSC -> %s %r", address, args)
        except OSError as exc:
            self._log(f"Envoi OSC impossible vers {address}: {exc}", logging.WARNING)

    def refresh_companion(self, log_request: bool = True) -> None:
        if self.config.mode != "companion":
            return
        self._send_osc("/init")
        self._send_osc("/refresh")
        if log_request:
            self._log("Demande des noms et valeurs Companion envoyee")

    def _rotary_address(self, global_index: int) -> str:
        number = global_index + 1
        if self.config.mode == "companion":
            return f"/Companion/Rotary{number}"
        return f"{self.config.generic_prefix}{number}"

    def _send_parameter(self, global_index: int, normalized: float) -> None:
        normalized = max(0.0, min(1.0, normalized))
        self.values[global_index] = normalized
        self.display_values[global_index] = f"{normalized * 100:.1f}%"
        self._send_osc(self._rotary_address(global_index), normalized)

    def _global_index(self, physical_index: int) -> int | None:
        index = self.active_bank * self.config.bank_size + physical_index
        return index if index < self.config.max_controls else None

    def _target_active(self) -> bool:
        state = self.setup_state
        if not state:
            return False
        return (
            state.setup + 1 == self.config.target_setup
            and state.group + 1 == self.config.target_group
        )

    def set_target(self, setup: int, group: int) -> None:
        if not 1 <= int(setup) <= 16 or not 1 <= int(group) <= 16:
            raise ValueError("le setup et le groupe EC4 doivent etre compris entre 1 et 16")
        self.config.target_setup = int(setup)
        self.config.target_group = int(group)
        self._log(f"Zone EC4 dediee: setup {setup}, groupe {group}")
        if self._target_active():
            self._send_current_bank_feedback()
            self._refresh_main_display()
        self._notify()

    def set_midi_learn_callback(self, callback: MidiLearnCallback | None) -> None:
        self._midi_learn_callback = callback

    def _mapping_key(self) -> str:
        return f"{self.config.target_setup}:{self.config.target_group}"

    def _configured_encoder_mapping(self) -> list[dict[str, int]] | None:
        mapping = self.config.encoder_mappings.get(self._mapping_key())
        if isinstance(mapping, list) and len(mapping) == self.config.bank_size:
            return mapping
        return None

    def _physical_index(self, channel: int, control: int) -> int | None:
        mapping = self._configured_encoder_mapping()
        if mapping:
            for index, item in enumerate(mapping):
                if int(item["channel"]) == channel and int(item["control"]) == control:
                    return index
            return None
        return macro_index(channel, control)

    def _feedback_address(self, physical_index: int, normalized: float) -> tuple[int, int, int]:
        mapping = self._configured_encoder_mapping()
        if mapping:
            value = max(0, min(127, round(float(normalized) * 127)))
            item = mapping[physical_index]
            return int(item["channel"]), int(item["control"]), value
        return feedback_cc(physical_index, normalized)

    def _push_index(self, channel: int, note: int) -> int | None:
        mapping = self._configured_encoder_mapping()
        if mapping and all("push_channel" in item and "push_note" in item for item in mapping):
            for index, item in enumerate(mapping):
                if int(item["push_channel"]) == channel and int(item["push_note"]) == note:
                    return index
            return None
        return parameter_push_index(channel, note)

    def refresh_target(self) -> None:
        if self._target_active():
            self._send_current_bank_feedback()
            self._refresh_main_display()

    def _is_echo(self, physical_index: int, value: int) -> bool:
        previous = self._last_feedback.get(physical_index)
        if not previous:
            return False
        previous_value, sent_at = previous
        age_ms = (time.monotonic() - sent_at) * 1000.0
        return previous_value == value and age_ms <= self.config.echo_guard_ms

    def _on_midi(self, message: Any) -> None:
        try:
            if message.type != "sysex" and self.config.restrict_to_target and not self._target_active():
                return
            if message.type == "control_change":
                if self._midi_learn_callback and self._midi_learn_callback(
                    "cc", message.channel, message.control, message.value
                ):
                    return
                physical = self._physical_index(message.channel, message.control)
                if physical is None or self._is_echo(physical, message.value):
                    return
                global_index = self._global_index(physical)
                if global_index is None:
                    return
                normalized = message.value / 127.0
                self._send_parameter(global_index, normalized)
                self._show_parameter(global_index)
                return

            if message.type in {"note_on", "note_off"}:
                pressed = message.type == "note_on" and message.velocity > 0
                if self._midi_learn_callback:
                    if pressed:
                        self._midi_learn_callback(
                            "note", message.channel, message.note, message.velocity
                        )
                    return
                if not pressed:
                    return
                parameter = self._push_index(message.channel, message.note)
                if parameter is not None:
                    self._handle_parameter_push(parameter)
                    return
                self._handle_note(message.channel, message.note)
                return

            if message.type == "sysex":
                raw = bytes((0xF0, *message.data, 0xF7))
                state = parse_setup_response(raw)
                if state:
                    self.setup_state = state
                    self._log(
                        f"EC4 detecte: setup interne {state.setup} (affiche {state.setup + 1}), "
                        f"groupe interne {state.group} (affiche {state.group + 1})"
                    )
                    if self._target_active():
                        self._send_current_bank_feedback()
                        self._refresh_main_display()
                    self._notify()
                    return
                button = parse_button_sysex(raw)
                if (
                    button
                    and button.pressed
                    and (not self.config.restrict_to_target or self._target_active())
                ):
                    self._handle_sysex_button(button.kind, button.index)
        except Exception as exc:
            self._log(f"Erreur de traitement MIDI: {exc}", logging.ERROR)

    def _handle_note(self, channel: int, note: int) -> None:
        if channel == MIDI_CHANNEL_14 and note == 112:
            self.change_bank(-1)
        elif channel == MIDI_CHANNEL_14 and note == 113:
            self.change_bank(1)
        elif channel == MIDI_CHANNEL_13 and note == 114:
            self._command("/Command/PluginWindows/SelectPreviousPlugin", "Plugin precedent")
        elif channel == MIDI_CHANNEL_13 and note == 115:
            self._command("/Command/PluginWindows/SelectNextPlugin", "Plugin suivant")
        elif channel == MIDI_CHANNEL_13 and note == 112:
            self._command("/Command/PluginWindows/ShowHideselectedplugin", "Afficher/masquer plugin")
        elif channel == MIDI_CHANNEL_13 and note == 113:
            self._command(
                "/Command/SelectedPlugin/EnableProcessingonselectedplugin",
                "Traitement plugin active/desactive",
            )
        elif channel == MIDI_CHANNEL_13 and note == 116:
            self._command("/Command/PluginWindows/ShowHideselectedplugin", "Afficher/masquer plugin")
        elif channel == MIDI_CHANNEL_13 and note == 117:
            self._show_overlay(["Verrouillage plugin", "non expose par", "l'API LiveProfessor"])
        elif channel == MIDI_CHANNEL_13 and note == 118:
            self._command("/Command/PluginWindows/SelectPreviousChain", "Chaine precedente")
        elif channel == MIDI_CHANNEL_13 and note == 119:
            self._command("/Command/PluginWindows/SelectNextChain", "Chaine suivante")

    def _handle_parameter_push(self, physical_index: int) -> None:
        if physical_index == 15:
            self._command("/Command/Transport&Tempo/TempoTap", "Tap tempo")
            return
        global_index = self._global_index(physical_index)
        if global_index is not None:
            self._show_parameter(global_index)

    def _handle_sysex_button(self, kind: str, index: int | None) -> None:
        if kind != "shift_push" or index is None:
            return
        commands = {
            1: (
                "/Command/GlobalSnapshots/RecallPreviousGlobalSnapshot",
                "Snapshot precedent",
            ),
            2: (
                "/Command/GlobalSnapshots/RecallNextGlobalSnapshot",
                "Snapshot suivant",
            ),
            5: ("/Command/PluginWindows/SelectPreviousPlugin", "Plugin precedent"),
            6: ("/Command/PluginWindows/SelectNextPlugin", "Plugin suivant"),
            12: (
                "/Command/SelectedPlugin/EnableProcessingonselectedplugin",
                "Traitement plugin active/desactive",
            ),
            15: ("/Command/PluginWindows/ShowHideselectedplugin", "Afficher/masquer plugin"),
        }
        if index == 8:
            self.set_bank(0)
        elif index == 9:
            self.change_bank(-1)
        elif index == 10:
            self.change_bank(1)
        elif index == 11:
            self.set_bank(self.bank_count - 1)
        elif index == 13:
            self.change_bank(-1)
        elif index == 14:
            self.change_bank(1)
        elif index in commands:
            address, label = commands[index]
            self._command(address, label)
        elif index in {0, 3, 4, 7}:
            self._show_overlay(["Navigation", "Premier/dernier", "non expose par", "l'API LiveProfessor"])

    def _command(self, address: str, label: str) -> None:
        self._send_osc(address, 1.0)
        self._show_overlay([label, self.profile.plugin_label, f"Banque {self.active_bank + 1}/{self.bank_count}"])

    def change_bank(self, delta: int) -> None:
        self.set_bank(self.active_bank + delta)

    def set_bank(self, bank: int) -> None:
        bank = max(0, min(self.bank_count - 1, int(bank)))
        if bank == self.active_bank:
            self._show_bank_overlay()
            return
        self.active_bank = bank
        self._log(f"Banque active: {bank + 1}/{self.bank_count}")
        self._send_current_bank_feedback()
        self._refresh_main_display()
        self._show_bank_overlay()
        self._notify()

    def _send_current_bank_feedback(self) -> None:
        if not self._midi.is_open:
            return
        if self.config.restrict_to_target and not self._target_active():
            return
        for physical in range(self.config.bank_size):
            global_index = self._global_index(physical)
            normalized = self.values[global_index] if global_index is not None else 0.0
            channel, control, value = self._feedback_address(physical, normalized)
            try:
                self._midi.send_cc(channel, control, value)
                self._last_feedback[physical] = (value, time.monotonic())
            except MidiBackendError as exc:
                self._log(str(exc), logging.WARNING)
                break

    def _display_allowed(self) -> bool:
        if not self.config.display_enabled or not self._midi.is_open:
            return False
        if self.config.restrict_to_target:
            return self._target_active()
        if not self.config.display_only_supported_setups:
            return True
        return bool(
            self.setup_state
            and self.setup_state.setup in SUPPORTED_DISPLAY_SETUPS
            and self.setup_state.group in SUPPORTED_DISPLAY_GROUPS
        )

    def _refresh_main_display(self) -> None:
        if not self._display_allowed():
            return
        start = self.active_bank * self.config.bank_size
        labels = self.short_names[start : start + self.config.bank_size]
        try:
            self._midi.send_sysex(main_display_message(labels))
            if self.config.persistent_parameter_display and self._overlay_timer is None:
                self._midi.send_sysex(parameter_grid_message(labels))
        except MidiBackendError as exc:
            self._log(str(exc), logging.WARNING)

    def _show_parameter(self, global_index: int) -> None:
        name = self.names[global_index]
        value = self.display_values[global_index]
        bank = global_index // self.config.bank_size + 1
        slot = global_index % self.config.bank_size + 1
        self._show_overlay([name, value, f"Banque {bank}/{self.bank_count}", f"Encodeur {slot}"])

    def _show_bank_overlay(self) -> None:
        start = self.active_bank * self.config.bank_size
        end = min(start + self.config.bank_size, self.config.max_controls)
        self._show_overlay(
            [
                self.profile.plugin_label or self.config.plugin_label,
                f"Banque {self.active_bank + 1}/{self.bank_count}",
                f"Parametres {start + 1}-{end}",
                "EC4 <-> LiveProf",
            ]
        )

    def _show_overlay(self, lines: list[str], duration: float = 1.2) -> None:
        if not self._display_allowed():
            return
        if self._overlay_timer:
            self._overlay_timer.cancel()
        try:
            self._midi.send_sysex(total_display_message(lines))
        except MidiBackendError as exc:
            self._log(str(exc), logging.WARNING)
            return
        self._overlay_timer = threading.Timer(duration, self._hide_overlay)
        self._overlay_timer.daemon = True
        self._overlay_timer.start()

    def _hide_overlay(self) -> None:
        self._overlay_timer = None
        if not self._display_allowed():
            return
        try:
            if self.config.persistent_parameter_display:
                start = self.active_bank * self.config.bank_size
                labels = self.short_names[start : start + self.config.bank_size]
                self._midi.send_sysex(parameter_grid_message(labels))
            else:
                self._midi.send_sysex(hide_total_display_message())
        except MidiBackendError:
            pass

    @staticmethod
    def _control_number(value: Any) -> int | None:
        match = re.search(r"(?:Rotary|Encoder)\s*(\d+)", str(value), flags=re.IGNORECASE)
        if not match:
            return None
        number = int(match.group(1))
        return number if number >= 1 else None

    def _on_osc(self, address: str, args: list[Any]) -> None:
        try:
            LOGGER.debug("OSC <- %s %r", address, args)
            if self.config.mode == "companion":
                self._on_companion_feedback(address, args)
            else:
                self._on_generic_feedback(address, args)
        except Exception as exc:
            self._log(f"Retour OSC ignore ({address}): {exc}", logging.WARNING)

    def _on_companion_feedback(self, address: str, args: list[Any]) -> None:
        match = re.fullmatch(r"/Companion/Rotary(\d+)", address, flags=re.IGNORECASE)
        if match and args:
            index = int(match.group(1)) - 1
            self._update_value(index, float(args[0]))
            return
        if address.casefold().endswith("/controllernames") and len(args) >= 2:
            number = self._control_number(args[0])
            if number:
                self._received_companion_names = True
                self._update_name(number - 1, str(args[1]))
            return
        if address.casefold().endswith("/controllervalues") and len(args) >= 2:
            number = self._control_number(args[0])
            if number and number <= self.config.max_controls:
                self.display_values[number - 1] = str(args[1])
            return
        if address.casefold().endswith("/touchandturnchange") and args:
            self._show_overlay(["Touch & Turn", str(args[0]), self.profile.plugin_label])

    def _on_generic_feedback(self, address: str, args: list[Any]) -> None:
        pattern = re.escape(self.config.generic_prefix) + r"(\d+)"
        match = re.fullmatch(pattern, address, flags=re.IGNORECASE)
        if match and args:
            self._update_value(int(match.group(1)) - 1, float(args[0]))

    def _update_name(self, index: int, name: str) -> None:
        if not 0 <= index < self.config.max_controls:
            return
        name = name.strip() or f"Parametre {index + 1}"
        changed = name != self.names[index]
        self.names[index] = name
        self.short_names[index] = short_label(name, index)
        if changed and index // self.config.bank_size == self.active_bank:
            self._refresh_main_display()

    def _update_value(self, index: int, normalized: float) -> None:
        if not 0 <= index < self.config.max_controls:
            return
        normalized = max(0.0, min(1.0, normalized))
        self.values[index] = normalized
        if self.display_values[index] in {"", "-"} or self.display_values[index].endswith("%"):
            self.display_values[index] = f"{normalized * 100:.1f}%"
        if index // self.config.bank_size != self.active_bank:
            return
        if self.config.restrict_to_target and not self._target_active():
            return
        physical = index % self.config.bank_size
        if not self._midi.is_open:
            return
        channel, control, value = self._feedback_address(physical, normalized)
        self._midi.send_cc(channel, control, value)
        self._last_feedback[physical] = (value, time.monotonic())

    def demo_display(self) -> None:
        self._refresh_main_display()
        self._show_overlay(
            ["Test affichage EC4", "Pont LiveProfessor", f"Banque {self.active_bank + 1}", "Aucun audio touche"],
            duration=2.0,
        )
