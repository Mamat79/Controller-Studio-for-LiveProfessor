from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any


class OSCError(ValueError):
    pass


def _pad4(data: bytes) -> bytes:
    return data + (b"\0" * ((-len(data)) % 4))


def _osc_string(value: str) -> bytes:
    if "\0" in value:
        raise OSCError("une chaine OSC ne peut pas contenir NUL")
    return _pad4(value.encode("utf-8") + b"\0")


def encode_message(address: str, args: Iterable[Any] = ()) -> bytes:
    if not address.startswith("/"):
        raise OSCError("une adresse OSC doit commencer par '/'")
    tags: list[str] = []
    payload: list[bytes] = []
    for value in args:
        if isinstance(value, bool):
            tags.append("T" if value else "F")
        elif value is None:
            tags.append("N")
        elif isinstance(value, int):
            tags.append("i")
            payload.append(struct.pack(">i", value))
        elif isinstance(value, float):
            tags.append("f")
            payload.append(struct.pack(">f", value))
        elif isinstance(value, str):
            tags.append("s")
            payload.append(_osc_string(value))
        elif isinstance(value, (bytes, bytearray)):
            blob = bytes(value)
            tags.append("b")
            payload.append(struct.pack(">i", len(blob)) + _pad4(blob))
        else:
            raise OSCError(f"type OSC non pris en charge: {type(value).__name__}")
    return _osc_string(address) + _osc_string("," + "".join(tags)) + b"".join(payload)


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    try:
        end = data.index(0, offset)
    except ValueError as exc:
        raise OSCError("chaine OSC sans terminateur") from exc
    value = data[offset:end].decode("utf-8", errors="replace")
    return value, (end + 4) & ~3


def decode_message(data: bytes) -> tuple[str, list[Any]]:
    address, offset = _read_string(data, 0)
    if address == "#bundle":
        raise OSCError("les bundles OSC ne sont pas utilises par ce pont")
    if not address.startswith("/"):
        raise OSCError("adresse OSC invalide")
    tags, offset = _read_string(data, offset)
    if not tags.startswith(","):
        raise OSCError("liste de types OSC absente")
    values: list[Any] = []
    for tag in tags[1:]:
        if tag == "i":
            values.append(struct.unpack_from(">i", data, offset)[0])
            offset += 4
        elif tag == "f":
            values.append(struct.unpack_from(">f", data, offset)[0])
            offset += 4
        elif tag == "d":
            values.append(struct.unpack_from(">d", data, offset)[0])
            offset += 8
        elif tag == "s":
            value, offset = _read_string(data, offset)
            values.append(value)
        elif tag == "b":
            length = struct.unpack_from(">i", data, offset)[0]
            offset += 4
            values.append(data[offset : offset + length])
            offset = (offset + length + 3) & ~3
        elif tag == "T":
            values.append(True)
        elif tag == "F":
            values.append(False)
        elif tag == "N":
            values.append(None)
        else:
            raise OSCError(f"type OSC inconnu: {tag}")
    return address, values


@dataclass(slots=True)
class OSCClient:
    host: str
    port: int

    def send(self, address: str, *args: Any) -> None:
        packet = encode_message(address, args)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet, (self.host, self.port))


class OSCServer:
    def __init__(
        self,
        host: str,
        port: int,
        callback: Callable[[str, list[Any]], None],
        error_callback: Callable[[Exception], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.callback = callback
        self.error_callback = error_callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.settimeout(0.25)
        except Exception:
            sock.close()
            raise
        self._socket = sock
        self._thread = threading.Thread(target=self._run, name="osc-feedback", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        assert self._socket is not None
        while not self._stop.is_set():
            try:
                data, _peer = self._socket.recvfrom(65535)
            except TimeoutError:
                continue
            except OSError as exc:
                if not self._stop.is_set() and self.error_callback:
                    self.error_callback(exc)
                break
            try:
                address, args = decode_message(data)
                self.callback(address, args)
            except Exception as exc:  # le serveur doit survivre a un paquet invalide
                if self.error_callback:
                    self.error_callback(exc)

    def stop(self) -> None:
        self._stop.set()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._socket = None
