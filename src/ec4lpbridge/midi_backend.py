from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class MidiBackendError(RuntimeError):
    pass


def _mido() -> Any:
    try:
        import mido
    except ImportError as exc:
        raise MidiBackendError(
            "Dependance MIDI absente. Installez mido et python-rtmidi, ou utilisez l'executable fourni."
        ) from exc
    return mido


def input_names() -> list[str]:
    return list(_mido().get_input_names())


def output_names() -> list[str]:
    return list(_mido().get_output_names())


def resolve_port(requested: str, candidates: list[str]) -> str:
    if not candidates:
        raise MidiBackendError("aucun port MIDI n'est disponible")
    requested = (requested or "").strip()
    if requested in candidates:
        return requested
    matches = [name for name in candidates if requested.casefold() in name.casefold()]
    if len(matches) == 1:
        return matches[0]
    if not requested and len(candidates) == 1:
        return candidates[0]
    if not matches:
        raise MidiBackendError(f"port MIDI introuvable: {requested!r}")
    raise MidiBackendError(f"nom de port MIDI ambigu: {requested!r} -> {matches}")


class MidiConnection:
    def __init__(self, callback: Callable[[Any], None]) -> None:
        self.callback = callback
        self.input_port: Any | None = None
        self.output_port: Any | None = None
        self.input_name = ""
        self.output_name = ""
        self._lock = threading.RLock()

    @property
    def is_open(self) -> bool:
        return bool(
            self.input_port
            and self.output_port
            and not self.input_port.closed
            and not self.output_port.closed
        )

    def ports_still_available(self) -> bool:
        """Verifie que les deux ports ouverts sont toujours publies par Windows."""

        if not self.is_open:
            return False
        try:
            mido = _mido()
            return (
                self.input_name in list(mido.get_input_names())
                and self.output_name in list(mido.get_output_names())
            )
        except Exception:
            # Une erreur d'inventaire ponctuelle ne doit pas couper une liaison saine.
            return True

    def open(self, requested_input: str, requested_output: str) -> tuple[str, str]:
        mido = _mido()
        with self._lock:
            self.close()
            self.input_name = resolve_port(requested_input, list(mido.get_input_names()))
            self.output_name = resolve_port(requested_output, list(mido.get_output_names()))
            try:
                self.output_port = mido.open_output(self.output_name)
                self.input_port = mido.open_input(self.input_name, callback=self.callback)
            except Exception as exc:
                self.close()
                raise MidiBackendError(f"ouverture MIDI impossible: {exc}") from exc
            return self.input_name, self.output_name

    def close(self) -> None:
        with self._lock:
            for port in (self.input_port, self.output_port):
                if port is not None:
                    try:
                        port.close()
                    except Exception:
                        pass
            self.input_port = None
            self.output_port = None

    def send_cc(self, channel: int, control: int, value: int) -> None:
        mido = _mido()
        self.send(mido.Message("control_change", channel=channel, control=control, value=value))

    def send_sysex(self, framed_data: bytes) -> None:
        mido = _mido()
        if not framed_data.startswith(b"\xF0") or not framed_data.endswith(b"\xF7"):
            raise MidiBackendError("message SysEx mal encadre")
        self.send(mido.Message("sysex", data=tuple(framed_data[1:-1])))

    def send(self, message: Any) -> None:
        with self._lock:
            if not self.output_port or self.output_port.closed:
                raise MidiBackendError("port MIDI de sortie ferme")
            try:
                self.output_port.send(message)
            except Exception as exc:
                self.close()
                raise MidiBackendError(f"envoi MIDI impossible: {exc}") from exc
