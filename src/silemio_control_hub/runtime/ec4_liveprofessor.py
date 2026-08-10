"""Proven EC4-to-LiveProfessor runtime hosted by SiLeMI/O Controller Studio."""

from __future__ import annotations

import logging
import math
import unicodedata
import re
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .config import BridgeConfig
from ..adapters.devices.ec4_protocol import (
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
from ..transports.midi import MidiBackendError, MidiConnection
from ..transports.osc import OSCClient, OSCServer
from .plugin_labels import load_profile, profile_names, short_label


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
    _SHIFT_SHORTCUT_LABELS = (
        "Bk-",
        "Bk+",
        "VS-",
        "VS+",
        "Show",
        "ChUp",
        "<Plg",
        "Plg>",
        "OnOf",
        "ChDn",
        "<Plg",
        "Plg>",
        "Cue-",
        "Cue+",
        "Sn-",
        "Sn+",
    )

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
        if self.config.mode == "companion":
            self.names, self.short_names = self._sanitize_profile_labels(self.names)
        self.display_values = ["-"] * config.max_controls
        self.button_names = [""] * config.bank_size
        self.button_short_names = [""] * config.bank_size
        self.button_display_values = ["-"] * config.bank_size
        self.values = [0.0] * config.max_controls
        self.active_bank = min(config.start_bank, self.bank_count - 1)
        self.setup_state: EC4SetupState | None = None
        self.status = "Arrete"
        self._running = False
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._last_companion_name_update = 0.0
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
        self._shift_held: bool = False
        self._last_feedback: dict[int, tuple[int, float]] = {}
        self._motion_log_times: dict[int, float] = {}
        self._feedback_timers: dict[int, threading.Timer] = {}
        self._pending_feedback: dict[int, int] = {}
        self._feedback_sequence = 0
        self._received_control_numbers: set[int] = set()
        self._name_inventory_timer: threading.Timer | None = None
        self._companion_refresh_timer: threading.Timer | None = None
        self._name_refresh_timer: threading.Timer | None = None
        self._parameter_overlay_timer: threading.Timer | None = None
        self._pending_overlay_index: int | None = None
        self._last_parameter_overlay_update: float = 0.0
        self._min_parameter_overlay_interval_s: float = max(
            0.001, self.config.parameter_overlay_interval_ms / 1000.0
        )
        self._midi_learn_callback: MidiLearnCallback | None = None
        self._received_companion_names = False
        self._companion_inventory_retries = 0
        self._overlay_parameter_index: int | None = None
        self._active_viewset_index: int | None = None
        self._viewset_count: int | None = None
        self._viewset_indices: set[int] = set()
        self._startup_banner_shown: bool = False

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
            self._schedule_companion_refresh(
                max(0.25, self.config.companion_refresh_delay_ms / 1000.0)
            )
        self._notify()

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        self._shift_held = False
        if self._overlay_timer:
            self._overlay_timer.cancel()
            self._overlay_timer = None
        for timer in self._feedback_timers.values():
            timer.cancel()
        self._feedback_timers.clear()
        self._pending_feedback.clear()
        if self._name_inventory_timer:
            self._name_inventory_timer.cancel()
            self._name_inventory_timer = None
        if self._companion_refresh_timer:
            self._companion_refresh_timer.cancel()
            self._companion_refresh_timer = None
        if self._name_refresh_timer:
            self._name_refresh_timer.cancel()
            self._name_refresh_timer = None
        if self._parameter_overlay_timer:
            self._parameter_overlay_timer.cancel()
            self._parameter_overlay_timer = None
            self._pending_overlay_index = None
        if hasattr(self._osc_client, "close"):
            try:
                self._osc_client.close()
            except Exception:
                pass
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
                    # A reconnect is a new user-visible connection event. Keep the
                    # one-shot guard inside one connection, but show the banner again.
                    self._startup_banner_shown = False
                    self.show_startup_banner()
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
        self._send_osc("/ViewSets/Refresh")
        if log_request:
            self._log("Demande des noms et valeurs Companion envoyee")

    def clear_companion_names(self) -> None:
        """Clear cached labels before a plug-in-specific Companion refresh."""

        with self._lock:
            self.names[:] = [""] * len(self.names)
            self.short_names[:] = [""] * len(self.short_names)
            self._received_control_numbers.clear()
            self._received_companion_names = False

    def companion_names_snapshot(self) -> tuple[str, ...]:
        """Return the latest labels intercepted from LiveProfessor."""

        with self._lock:
            return tuple(self.names)

    def capture_companion_names(
        self,
        *,
        required_indices: Iterable[int] = (),
        timeout: float = 30.0,
        quiet_period: float = 0.35,
        retry_interval: float = 2.0,
    ) -> tuple[str, ...]:
        """Capture labels for Plugin Studio without discarding live feedback.

        Controller-name feedback is continuously received by the running
        bridge.  When the selected plug-in already appears on the hardware,
        the cached labels are the most reliable and fastest source.  If no
        useful mapped label is cached, refresh requests are retried while the
        existing OSC listener keeps collecting the replies.
        """

        required = tuple(
            sorted(
                {
                    int(index)
                    for index in required_indices
                    if 0 <= int(index) < len(self.names)
                }
            )
        )

        def useful_count(snapshot: tuple[str, ...]) -> int:
            indices = required or tuple(range(len(snapshot)))
            return sum(bool(snapshot[index].strip()) for index in indices)

        retry_after = max(0.05, retry_interval)
        settle_after = max(0.0, quiet_period)
        snapshot = self.companion_names_snapshot()
        with self._lock:
            cached_quiet_for = time.monotonic() - self._last_companion_name_update
        if useful_count(snapshot) and cached_quiet_for >= settle_after:
            self._log("Noms Companion deja recus: capture directe du controleur actif")
            return snapshot

        deadline = time.monotonic() + max(0.05, timeout)
        next_request = 0.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_request:
                self.refresh_companion(log_request=next_request == 0.0)
                next_request = now + retry_after

            snapshot = self.companion_names_snapshot()
            if useful_count(snapshot):
                with self._lock:
                    quiet_for = time.monotonic() - self._last_companion_name_update
                if quiet_for >= settle_after:
                    return snapshot

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.02, max(0.001, remaining)))

        return self.companion_names_snapshot()

    def _schedule_companion_refresh(self, delay: float | None = None) -> None:
        if self.config.mode != "companion":
            return
        if delay is None:
            delay = self.config.companion_refresh_delay_ms / 1000.0
        if self._companion_refresh_timer:
            self._companion_refresh_timer.cancel()
        timer = threading.Timer(delay, self._perform_companion_refresh)
        timer.daemon = True
        self._companion_refresh_timer = timer
        timer.start()

    def _perform_companion_refresh(self) -> None:
        if self.config.mode != "companion":
            self._companion_refresh_timer = None
            return
        self._companion_refresh_timer = None
        self.refresh_companion(log_request=False)

    def _schedule_name_refresh(self, delay: float | None = None) -> None:
        if delay is None:
            delay = self.config.name_refresh_delay_ms / 1000.0
        if self._name_refresh_timer:
            self._name_refresh_timer.cancel()
        timer = threading.Timer(delay, self._flush_name_refresh)
        timer.daemon = True
        self._name_refresh_timer = timer
        timer.start()

    def _flush_name_refresh(self) -> None:
        self._name_refresh_timer = None
        self._refresh_main_display()

    def _rotary_address(self, global_index: int) -> str:
        number = global_index + 1
        if self.config.mode == "companion":
            return f"/Companion/Rotary{number}"
        return f"{self.config.generic_prefix}{number}"

    def _send_parameter(
        self,
        global_index: int,
        normalized: float,
        *,
        physical_index: int | None = None,
        midi_control: int | None = None,
        midi_value: int | None = None,
    ) -> None:
        normalized = max(0.0, min(1.0, normalized))
        self.values[global_index] = normalized
        if self.config.mode != "companion":
            self.display_values[global_index] = f"{normalized * 100:.1f}%"
        else:
            self.display_values[global_index] = "-"
        address = self._rotary_address(global_index)
        self._send_osc(address, normalized)
        if physical_index is not None:
            now = time.monotonic()
            last_log = self._motion_log_times.get(physical_index, 0.0)
            if now - last_log >= 0.25:
                midi_details = ""
                if midi_control is not None and midi_value is not None:
                    midi_details = f" CC{midi_control}={midi_value}"
                self._log(
                    f"EC4 encodeur {physical_index + 1}:{midi_details} -> "
                    f"{address} = {normalized * 100:.1f}%"
                )
                self._motion_log_times[physical_index] = now
        if self.config.mode == "companion":
            self._expect_parameter_feedback(global_index)

    def _expect_parameter_feedback(self, global_index: int) -> None:
        previous = self._feedback_timers.pop(global_index, None)
        if previous:
            previous.cancel()
        self._feedback_sequence += 1
        sequence = self._feedback_sequence
        self._pending_feedback[global_index] = sequence
        timer = threading.Timer(
            max(0.1, self.config.feedback_confirm_timeout_ms / 1000.0),
            self._parameter_feedback_timeout,
            args=(global_index, sequence),
        )
        timer.daemon = True
        self._feedback_timers[global_index] = timer
        timer.start()

    def _parameter_feedback_timeout(self, global_index: int, sequence: int) -> None:
        with self._lock:
            if self._pending_feedback.get(global_index) != sequence:
                return
            self._pending_feedback.pop(global_index, None)
            self._feedback_timers.pop(global_index, None)
        number = global_index + 1
        self._log(
            f"Aucun retour LiveProfessor pour Rotary{number}. Le mouvement EC4 est bien recu; "
            f"verifiez le port d'entree du Companion Controller ({self.config.liveprofessor_port}) "
            "et l'affectation dans le Controller Map actif.",
            logging.WARNING,
        )

    def _confirm_parameter_feedback(self, global_index: int) -> None:
        with self._lock:
            sequence = self._pending_feedback.pop(global_index, None)
            timer = self._feedback_timers.pop(global_index, None)
        if timer:
            timer.cancel()
        if sequence is not None:
            self._log(f"LiveProfessor confirme Rotary{global_index + 1}")

    def _schedule_companion_inventory_report(self) -> None:
        if self._name_inventory_timer:
            self._name_inventory_timer.cancel()
        timer = threading.Timer(
            max(0.1, self.config.feedback_confirm_timeout_ms / 1000.0),
            self._report_companion_inventory,
        )
        timer.daemon = True
        self._name_inventory_timer = timer
        timer.start()

    def _report_companion_inventory(self) -> None:
        self._name_inventory_timer = None
        expected = min(self.config.bank_size, self.config.max_controls)
        available = len({number for number in self._received_control_numbers if number <= expected})
        if available < expected:
            missing = [
                str(number)
                for number in range(1, expected + 1)
                if number not in self._received_control_numbers
            ]
            self._log(
                f"Companion n'a renvoye que {available}/{expected} rotatifs pour la premiere banque. "
                f"Definissez et mappez les Rotary manquants dans LiveProfessor: {', '.join(missing)}.",
                logging.WARNING,
            )
            if self._running and self._companion_inventory_retries < 2:
                self._companion_inventory_retries += 1
                self._schedule_companion_refresh(0.5)
        else:
            self._companion_inventory_retries = 0
            self._log(f"Companion confirme les {expected} rotatifs de la premiere banque")

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

    def reconnect_midi(self) -> None:
        self._midi.close()
        self.status = "Reconnexion EC4 demandee"
        self._log("Reconnexion MIDI EC4 demandee")
        self._notify()

    def request_setup_state(self) -> None:
        if not self._midi.is_open:
            self._log("Requete setup/groupe impossible: EC4 absent", logging.WARNING)
            return
        self._midi.send_sysex(SETUP_REQUEST)
        self._log("Requete du setup/groupe EC4 envoyee")

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
                self._send_parameter(
                    global_index,
                    normalized,
                    physical_index=physical,
                    midi_control=message.control,
                    midi_value=message.value,
                )
                self._schedule_parameter_overlay(global_index)
                return

            if message.type in {"note_on", "note_off"}:
                pressed = message.type == "note_on" and message.velocity > 0
                if self._midi_learn_callback:
                    if pressed:
                        self._midi_learn_callback(
                            "note", message.channel, message.note, message.velocity
                        )
                    return
                parameter = self._push_index(message.channel, message.note)
                if parameter is not None:
                    self._handle_parameter_push(parameter, pressed=pressed)
                    return
                if not pressed:
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
                if button:
                    target_allowed = not self.config.restrict_to_target or self._target_active()
                    if button.kind == "shift":
                        # Toujours accepter le relachement d'un Shift deja pris en compte,
                        # meme si l'utilisateur change de groupe entre-temps.
                        if target_allowed or self._shift_held:
                            self._handle_sysex_button(
                                button.kind,
                                button.index,
                                pressed=button.pressed,
                            )
                    elif button.pressed and target_allowed:
                        self._handle_sysex_button(
                            button.kind,
                            button.index,
                            pressed=True,
                        )
        except Exception as exc:
            self._log(f"Erreur de traitement MIDI: {exc}", logging.ERROR)

    def _handle_note(self, channel: int, note: int) -> None:
        if channel == MIDI_CHANNEL_14 and note == 112:
            self.change_bank(-1)
        elif channel == MIDI_CHANNEL_14 and note == 113:
            self.change_bank(1)
        elif channel == MIDI_CHANNEL_13 and note == 114:
            self._command(
                "/Command/PluginWindows/SelectPreviousPlugin",
                "Plugin precedent",
                refresh_companion=True,
            )
        elif channel == MIDI_CHANNEL_13 and note == 115:
            self._command(
                "/Command/PluginWindows/SelectNextPlugin",
                "Plugin suivant",
                refresh_companion=True,
            )
        elif channel == MIDI_CHANNEL_13 and note == 112:
            self._command(self.config.show_hide_command, "Afficher/masquer plugin")
        elif channel == MIDI_CHANNEL_13 and note == 113:
            self._command(
                self.config.enable_processing_command,
                "Traitement plugin active/desactive",
            )
        elif channel == MIDI_CHANNEL_13 and note == 116:
            self._command(self.config.show_hide_command, "Afficher/masquer plugin")
        elif channel == MIDI_CHANNEL_13 and note == 117:
            self._show_overlay(["Verrouillage plugin", "non expose par", "l'API LiveProfessor"])
        elif channel == MIDI_CHANNEL_13 and note == 118:
            self._command(
                "/Command/PluginWindows/SelectPreviousChain",
                "Chaine precedente",
                refresh_companion=True,
            )
        elif channel == MIDI_CHANNEL_13 and note == 119:
            self._command(
                "/Command/PluginWindows/SelectNextChain",
                "Chaine suivante",
                refresh_companion=True,
            )

    def _handle_parameter_push(self, physical_index: int, *, pressed: bool = True) -> None:
        if physical_index == 15:
            if pressed:
                self._command("/Command/Transport&Tempo/TempoTap", "Tap tempo")
            return
        if self.config.mode == "companion":
            self._send_osc(
                f"/Companion/GenericButtons/Button{physical_index + 1}",
                1.0 if pressed else 0.0,
            )
        if not pressed:
            return
        button_name = self._button_display_name(physical_index)
        if button_name:
            button_value = self._normalize_companion_value(
                self.button_display_values[physical_index]
            )
            lines = [button_name]
            if button_value not in {"", "-"}:
                lines.append(button_value)
            lines.append(self.profile.plugin_label)
            self._show_overlay(lines)
            return
        global_index = self._global_index(physical_index)
        if global_index is not None:
            self._show_parameter(global_index)

    def _navigate_viewset(self, step: int) -> None:
        if step == 0:
            return
        if self._active_viewset_index is None:
            self._send_osc("/ViewSets/Refresh")
            if not self._viewset_count:
                self._show_overlay(["View Set", "synchronisation...", "en cours"])
                return
            self._active_viewset_index = 0 if step > 0 else self._viewset_count - 1
            next_index = self._active_viewset_index
        else:
            next_index = self._active_viewset_index + step
        if self._viewset_count is not None:
            if self._viewset_count <= 0:
                self._show_overlay(["View Set", "aucun", "View Set"])
                return
            next_index %= self._viewset_count
        elif next_index < 0:
            self._show_overlay(["View Set", "premier", "déja atteint"])
            return
        if self._viewset_count is not None and next_index < 0:
            next_index %= self._viewset_count
        self._active_viewset_index = next_index
        self._send_osc("/ViewSets/Recall", next_index)
        self._show_overlay(
            ["View Set", f"{next_index + 1}"]
        )
        self._schedule_companion_refresh()

    def _handle_sysex_button(
        self,
        kind: str,
        index: int | None,
        *,
        pressed: bool = True,
    ) -> None:
        if kind == "shift":
            if pressed:
                self._show_shift_shortcuts()
            else:
                self._hide_shift_shortcuts()
            return
        if kind != "shift_push" or index is None or not pressed:
            return
        if index == 0:
            self.change_bank(-1)
            return
        if index == 1:
            self.change_bank(1)
            return
        if index == 2:
            self._navigate_viewset(-1)
            return
        if index == 3:
            self._navigate_viewset(1)
            return
        if index == 4:
            self._command(self.config.show_hide_command, "Afficher/masquer plugin")
            return
        if index == 5:
            self._command(
                "/Command/PluginWindows/SelectPreviousChain",
                "Chaine precedente",
                refresh_companion=True,
            )
            return
        if index == 6:
            self._command(
                "/Command/PluginWindows/SelectPreviousPlugin",
                "Plugin precedent",
                refresh_companion=True,
            )
            return
        if index == 7:
            self._command(
                "/Command/PluginWindows/SelectNextPlugin",
                "Plugin suivant",
                refresh_companion=True,
            )
            return
        if index == 8:
            self._command(
                self.config.enable_processing_command,
                "Traitement plugin active/desactive",
            )
            return
        if index == 9:
            self._command(
                "/Command/PluginWindows/SelectNextChain",
                "Chaine suivante",
                refresh_companion=True,
            )
            return
        if index == 10:
            self._command(
                "/Command/PluginWindows/SelectPreviousPlugin",
                "Plugin precedent",
                refresh_companion=True,
            )
            return
        if index == 11:
            self._command(
                "/Command/PluginWindows/SelectNextPlugin",
                "Plugin suivant",
                refresh_companion=True,
            )
            return
        if index == 12:
            self._command(self.config.cue_previous_command, "Cue precedent")
            return
        if index == 13:
            self._command(self.config.cue_next_command, "Cue suivant")
            return
        if index == 14:
            self._command(self.config.snapshot_previous_command, "Snapshot precedent")
            return
        if index == 15:
            self._command(self.config.snapshot_next_command, "Snapshot suivant")
            return

    def _command(
        self,
        address: str,
        label: str,
        *,
        refresh_companion: bool = False,
    ) -> None:
        command_address = self._command_fallbacks(address)[0]
        if command_address in self._COMMAND_ADDRESSES_WITHOUT_VALUE:
            self._send_osc(command_address)
        else:
            self._send_osc(command_address, 1.0)
        self._show_overlay([label, self.profile.plugin_label, f"Banque {self.active_bank + 1}/{self.bank_count}"])
        if refresh_companion:
            self._schedule_companion_refresh()

    @staticmethod
    def _command_fallbacks(address: str) -> tuple[str, ...]:
        official_aliases = {
            "/Command/PluginWindows/ShowHideSelectedPlugin": (
                "/Command/PluginWindows/ShowHideselectedplugin"
            ),
            "/Command/SelectedPlugin/ShowHideSelectedPlugin": (
                "/Command/PluginWindows/ShowHideselectedplugin"
            ),
            "/Command/SelectedPlugin/EnableProcessingOnSelectedPlugin": (
                "/Command/SelectedPlugin/EnableProcessingonselectedplugin"
            ),
            "/Command/CueList/RecallPreviousCue": "/Command/CueLists/FirePreviousCue",
            "/Command/CueList/RecallNextCue": "/Command/CueLists/FireNextCue",
            "/Command/GlobalSnapshots/RecallPrevious": (
                "/Command/GlobalSnapshots/RecallPreviousGlobalSnapshot"
            ),
            "/Command/GlobalSnapshots/RecallNext": (
                "/Command/GlobalSnapshots/RecallNextGlobalSnapshot"
            ),
        }
        return (official_aliases.get(address, address),)

    @staticmethod
    def _coerce_viewset_count_argument(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return int(value)
        if isinstance(value, (bytes, bytearray)):
            try:
                value = bytes(value).decode("utf-8", errors="replace")
            except Exception:
                return None
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if "," in text or ";" in text or "|" in text or "\n" in text or "\r" in text:
            tokens = [chunk.strip() for chunk in re.split(r"[;,|\n\r]+", text) if chunk.strip()]
            if len(tokens) > 1:
                return len(tokens)
        try:
            return int(float(text))
        except ValueError:
            return None

    _COMMAND_ADDRESSES_WITHOUT_VALUE = frozenset(
        {
            "/Command/PluginWindows/ShowHideselectedplugin",
            "/Command/PluginWindows/ShowHideSelectedPlugin",
            "/Command/PluginWindows/TogglePluginWindows",
            "/Command/SelectedPlugin/ShowHideSelectedPlugin",
            "/Command/SelectedPlugin/EnableProcessingOnSelectedPlugin",
            "/Command/SelectedPlugin/EnableProcessingonselectedplugin",
            "/Command/SelectedPlugin/EnableBypassonselectedplugin",
            "/Command/CueList/RecallPreviousCue",
            "/Command/CueLists/FirePreviousCue",
            "/Command/CueList/RecallNextCue",
            "/Command/CueLists/FireNextCue",
            "/Command/CueList/FirePreviousCue",
            "/Command/CueList/FireNextCue",
            "/Command/CueList/StepUp",
            "/Command/CueLists/StepUp",
            "/Command/CueList/StepDown",
            "/Command/CueLists/StepDown",
            "/Command/CueList/GoToTop",
            "/Command/CueLists/GoToTop",
            "/Command/GlobalSnapshots/RecallPreviousGlobalSnapshot",
            "/Command/GlobalSnapshots/RecallPrevious",
            "/Command/Snapshots/RecallPrevious",
            "/Command/GlobalSnapshots/RecallNextGlobalSnapshot",
            "/Command/GlobalSnapshots/RecallNext",
            "/Command/Snapshots/RecallNext",
            "/Command/PluginWindows/SelectNextChain",
            "/Command/PluginWindows/SelectPreviousChain",
            "/Command/PluginWindows/SelectNextPlugin",
            "/Command/PluginWindows/SelectPreviousPlugin",
            "/Command/SelectedPlugin/CreateNewPluginSnapshot",
            "/Command/Transport&Tempo/TempoTap",
        }
    )

    @staticmethod
    def _coerce_viewset_feedback_index(value: Any) -> int | None:
        return EC4LiveProfessorBridge._coerce_viewset_count_argument(value)

    @classmethod
    def _viewset_index_from_arguments(cls, args: list[Any] | tuple[Any, ...]) -> int | None:
        """Extract the zero-based index from LiveProfessor's name/index feedback."""

        for value in reversed(args):
            index = cls._coerce_viewset_feedback_index(value)
            if index is not None and index >= 0:
                return index
        return None

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
        if self._shift_held:
            return
        start = self.active_bank * self.config.bank_size
        labels = self.short_names[start : start + self.config.bank_size]
        labels = [
            self._display_short_label(start + offset, label)
            for offset, label in enumerate(labels)
        ]
        try:
            self._midi.send_sysex(main_display_message(labels))
            if self.config.persistent_parameter_display and self._overlay_timer is None:
                self._midi.send_sysex(parameter_grid_message(labels))
        except MidiBackendError as exc:
            self._log(str(exc), logging.WARNING)

    def _cancel_display_timers(self) -> None:
        if self._overlay_timer:
            self._overlay_timer.cancel()
            self._overlay_timer = None
        if self._parameter_overlay_timer:
            self._parameter_overlay_timer.cancel()
            self._parameter_overlay_timer = None
        self._pending_overlay_index = None
        self._overlay_parameter_index = None

    def _send_shift_shortcuts(self) -> None:
        labels = list(self._SHIFT_SHORTCUT_LABELS)
        try:
            self._midi.send_sysex(main_display_message(labels))
            self._midi.send_sysex(parameter_grid_message(labels))
        except MidiBackendError as exc:
            self._log(str(exc), logging.WARNING)

    def _show_shift_shortcuts(self) -> None:
        if not self._display_allowed():
            return
        self._shift_held = True
        self._cancel_display_timers()
        self._send_shift_shortcuts()

    def _hide_shift_shortcuts(self) -> None:
        if not self._shift_held:
            return
        self._shift_held = False
        self._cancel_display_timers()
        self._refresh_main_display()

    def _show_parameter(self, global_index: int) -> None:
        self._overlay_parameter_index = global_index
        name = self._display_name(global_index)
        value = self._format_companion_value_for_display(global_index)
        bank = global_index // self.config.bank_size + 1
        slot = global_index % self.config.bank_size + 1
        self._show_overlay(
            [name, value, f"Banque {bank}/{self.bank_count}", f"Encodeur {slot}"],
            parameter_index=global_index,
        )

    def _schedule_parameter_overlay(self, global_index: int) -> None:
        if self.config.mode != "companion":
            return

        now = time.monotonic()
        if self._overlay_parameter_index != global_index:
            self._show_parameter(global_index)
            self._last_parameter_overlay_update = now
            return

        elapsed = now - self._last_parameter_overlay_update
        if elapsed >= self._min_parameter_overlay_interval_s:
            self._show_parameter(global_index)
            self._last_parameter_overlay_update = now
            return

        if self._parameter_overlay_timer:
            self._parameter_overlay_timer.cancel()
        self._pending_overlay_index = global_index
        timer = threading.Timer(
            self._min_parameter_overlay_interval_s - elapsed,
            self._flush_parameter_overlay,
        )
        timer.daemon = True
        self._parameter_overlay_timer = timer
        timer.start()

    def _flush_parameter_overlay(self) -> None:
        self._parameter_overlay_timer = None
        if not self._display_allowed():
            return
        global_index = self._pending_overlay_index
        self._pending_overlay_index = None
        if global_index is None:
            return
        if self._overlay_parameter_index != global_index:
            return
        self._show_parameter(global_index)
        self._last_parameter_overlay_update = time.monotonic()

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

    def show_startup_banner(self) -> None:
        if self._startup_banner_shown:
            return
        if self.config.display_enabled is False:
            return
        if not self._midi.is_open:
            return
        self._startup_banner_shown = True
        status_line = "Connection OK" if self.config.ui_language == "en" else "Connexion OK"
        self._overlay_parameter_index = None
        if self._overlay_timer:
            self._overlay_timer.cancel()
        try:
            self._midi.send_sysex(
                total_display_message(
                    [status_line, "SiLeMI/O CtrlStudio", "By Mamat", "-----[]---"],
                    alignments=["center", "center", "right", "right"],
                )
            )
        except MidiBackendError as exc:
            self._log(str(exc), logging.WARNING)
            return
        self._overlay_timer = threading.Timer(2.0, lambda: self._hide_overlay(force=True))
        self._overlay_timer.daemon = True
        self._overlay_timer.start()

    def _show_overlay(
        self,
        lines: list[str],
        duration: float | None = None,
        parameter_index: int | None = None,
    ) -> None:
        if not self._display_allowed():
            return
        if duration is None:
            duration = max(0.2, self.config.overlay_display_duration_ms / 1000.0)
        self._overlay_parameter_index = parameter_index
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

    def _hide_overlay(self, force: bool = False) -> None:
        self._overlay_timer = None
        self._overlay_parameter_index = None
        if not force and not self._display_allowed():
            return
        if self._shift_held:
            self._send_shift_shortcuts()
            return
        try:
            if self.config.persistent_parameter_display:
                start = self.active_bank * self.config.bank_size
                labels = self.short_names[start : start + self.config.bank_size]
                labels = [
                    self._display_short_label(start + offset, label)
                    for offset, label in enumerate(labels)
                ]
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

    @staticmethod
    def _button_number(value: Any) -> int | None:
        match = re.search(
            r"(?:Generic\s*Button|GenericButton|Button)\s*(\d+)",
            str(value),
            flags=re.IGNORECASE,
        )
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
                self._received_control_numbers.add(number)
                self._update_name(number - 1, str(args[1]))
                self._schedule_companion_inventory_report()
            else:
                button_number = self._button_number(args[0])
                if button_number:
                    self._update_button_name(button_number - 1, str(args[1]))
            return
        if address.casefold().endswith("/controllervalues") and len(args) >= 2:
            number = self._control_number(args[0])
            if number and number <= self.config.max_controls:
                self.display_values[number - 1] = self._normalize_companion_value(args[1])
                if self._overlay_parameter_index == number - 1:
                    self._schedule_parameter_overlay(number - 1)
            else:
                button_number = self._button_number(args[0])
                if button_number and button_number <= len(self.button_display_values):
                    self.button_display_values[button_number - 1] = self._normalize_companion_value(
                        args[1]
                    )
            return
        if address.casefold().endswith("/viewsets/recall") and args:
            value = self._viewset_index_from_arguments(args)
            if value is not None:
                self._active_viewset_index = value
            return
        if address.casefold().endswith("/viewsets/update"):
            if not args:
                return
            index = self._viewset_index_from_arguments(args)
            if index is not None and index >= 0:
                self._viewset_indices.add(index)
                self._viewset_count = max(self._viewset_indices) + 1
            elif all(not isinstance(arg, (int, float)) for arg in args):
                self._viewset_count = max(1, (self._viewset_count or 0) + 1)
            return
        if address.casefold().endswith("/viewsets/changed"):
            self._viewset_indices.clear()
            self._viewset_count = None
            self._send_osc("/ViewSets/Refresh")
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
        name = self._coerce_companion_name(index, name)
        with self._lock:
            changed = name != self.names[index]
            self.names[index] = name
            self.short_names[index] = "" if not name else short_label(name, index)
            self._last_companion_name_update = time.monotonic()
        if changed and index // self.config.bank_size == self.active_bank:
            self._schedule_name_refresh()

    def _update_button_name(self, index: int, name: str) -> None:
        if not 0 <= index < len(self.button_names):
            return
        name = self._coerce_companion_name(index, name)
        self.button_names[index] = name
        self.button_short_names[index] = "" if not name else short_label(name, index)

    def _button_display_name(self, index: int) -> str:
        if not 0 <= index < len(self.button_names):
            return ""
        name = self.button_names[index].strip()
        return "" if self._is_default_label(name) else name

    def _display_name(self, index: int) -> str:
        name = self.names[index]
        if self.config.mode == "companion" and self._is_default_label(name):
            return ""
        return name

    def _display_short_label(self, index: int, label: str) -> str:
        if self.config.mode != "companion":
            return label
        if self._is_control_mapped(index):
            return label
        # A push-only mapping still deserves a permanent label. Reuse the
        # otherwise empty encoder cell without creating a fake rotary mapping.
        physical_index = index % self.config.bank_size
        if 0 <= physical_index < len(self.button_short_names):
            return self.button_short_names[physical_index]
        return ""

    @staticmethod
    def _normalize_default_token(name: str) -> str:
        value = unicodedata.normalize("NFD", (name or "").strip().lower())
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        value = re.sub(r"[^0-9a-zà-ÿ]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    @classmethod
    def _is_default_label(cls, name: str) -> bool:
        value = cls._normalize_default_token(name)
        if not value:
            return True
        if re.fullmatch(r"parametre\s*[:#-]?\s*\d+", value):
            return True
        if re.fullmatch(r"parameter\s*[:#-]?\s*\d+", value):
            return True
        if re.fullmatch(r"rotary\s*[:#-]?\s*\d+", value):
            return True
        if re.fullmatch(r"encoder\s*[:#-]?\s*\d+", value):
            return True
        return False

    def _is_control_mapped(self, index: int) -> bool:
        if self.config.mode != "companion":
            return True
        if not (0 <= index < len(self.names)):
            return False
        name = self.names[index].strip()
        return bool(name) and not self._is_default_label(name)

    def _format_companion_value_for_display(self, index: int) -> str:
        value = self.display_values[index]
        if self.config.mode == "companion":
            return self._normalize_companion_value(value)
        return value

    @staticmethod
    def _normalize_companion_value(value: Any) -> str:
        text = str(value).strip()
        if not text:
            return text
        match = re.fullmatch(r"([-+]?\d+[.,]?\d*)\s*%", text)
        if match:
            return match.group(1).replace(",", ".")
        return text

    @staticmethod
    def _coerce_companion_name(index: int, name: str) -> str:
        value = (name or "").strip()
        return "" if value and EC4LiveProfessorBridge._is_default_label(value) else value

    @staticmethod
    def _sanitize_profile_label(index: int, name: str) -> str:
        value = (name or "").strip()
        if not value:
            return ""
        return "" if EC4LiveProfessorBridge._is_default_label(value) else value

    def _sanitize_profile_labels(
        self,
        names: list[str],
    ) -> tuple[list[str], list[str]]:
        clean_names: list[str] = []
        clean_shorts: list[str] = []
        for index, name in enumerate(names):
            name = self._sanitize_profile_label(index, name)
            clean_names.append(name)
            clean_shorts.append("" if not name else short_label(name, index))
        return clean_names, clean_shorts

    def _update_value(self, index: int, normalized: float) -> None:
        if not 0 <= index < self.config.max_controls:
            return
        self._confirm_parameter_feedback(index)
        normalized = max(0.0, min(1.0, normalized))
        self.values[index] = normalized
        if self.config.mode != "companion":
            if (
                self.display_values[index] in {"", "-"}
                or self.display_values[index].endswith("%")
            ):
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
            [
                "Test affichage EC4",
                "Controller Studio",
                f"Banque {self.active_bank + 1}",
                "Aucun audio touche",
            ],
            duration=2.0,
        )


EC4LiveProfessorRuntime = EC4LiveProfessorBridge
