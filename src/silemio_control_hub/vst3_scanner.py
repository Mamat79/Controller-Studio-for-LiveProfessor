"""Isolated, read-only inspection of parameters exposed by installed VST3 plug-ins.

The worker implements only the small, stable subset of the VST3 ABI needed to
instantiate an edit controller and read ``ParameterInfo`` records.  It never
loads a plug-in in the Controller Studio GUI process: a crash or a hang remains
confined to the disposable worker process.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ET


class VST3ScanError(RuntimeError):
    """Raised when an installed plug-in cannot be inspected safely."""


def _debug(message: str) -> None:
    if os.environ.get("SILEMIO_VST3_DEBUG") == "1":
        print(f"VST3 scanner: {message}", file=sys.stderr, flush=True)


@dataclass(frozen=True, slots=True)
class ScannedParameter:
    index: int
    parameter_id: int
    name: str
    short_name: str
    unit: str
    step_count: int
    flags: int

    @classmethod
    def from_dict(cls, raw: object, *, index: int) -> "ScannedParameter":
        if not isinstance(raw, dict):
            raise VST3ScanError("réponse de paramètre invalide")
        try:
            actual_index = int(raw["index"])
            parameter_id = int(raw["parameter_id"])
            name = str(raw["name"]).strip()
            short_name = str(raw.get("short_name", "")).strip()
            unit = str(raw.get("unit", "")).strip()
            step_count = int(raw.get("step_count", 0))
            flags = int(raw.get("flags", 0))
        except (KeyError, TypeError, ValueError) as exc:
            raise VST3ScanError("réponse de paramètre invalide") from exc
        if actual_index != index or not name or step_count < 0:
            raise VST3ScanError("ordre ou nom de paramètre invalide")
        return cls(
            index=actual_index,
            parameter_id=parameter_id,
            name=name,
            short_name=short_name,
            unit=unit,
            step_count=step_count,
            flags=flags,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "parameter_id": self.parameter_id,
            "name": self.name,
            "short_name": self.short_name,
            "unit": self.unit,
            "step_count": self.step_count,
            "flags": self.flags,
        }


@dataclass(frozen=True, slots=True)
class VST3ScanResult:
    plugin_name: str
    class_name: str
    module_path: Path
    parameters: tuple[ScannedParameter, ...]

    @classmethod
    def from_dict(cls, raw: object) -> "VST3ScanResult":
        if not isinstance(raw, dict):
            raise VST3ScanError("réponse du scanner invalide")
        try:
            plugin_name = str(raw["plugin_name"]).strip()
            class_name = str(raw["class_name"]).strip()
            module_path = Path(str(raw["module_path"])).expanduser().resolve()
            raw_parameters = raw["parameters"]
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise VST3ScanError("réponse du scanner invalide") from exc
        if not plugin_name or not class_name or not isinstance(raw_parameters, list):
            raise VST3ScanError("réponse du scanner incomplète")
        parameters = tuple(
            ScannedParameter.from_dict(parameter, index=index)
            for index, parameter in enumerate(raw_parameters)
        )
        return cls(plugin_name, class_name, module_path, parameters)

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_name": self.plugin_name,
            "class_name": self.class_name,
            "module_path": str(self.module_path),
            "parameters": [parameter.to_dict() for parameter in self.parameters],
        }


def default_liveprofessor_plugin_database() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / "audiostrom" / "LiveProfessor 2" / "PluginsX64.xml"


def installed_plugin_paths(
    plugin_name: str,
    *,
    plugin_format: str = "VST3",
    database: Path | None = None,
) -> tuple[Path, ...]:
    """Resolve exact LiveProfessor database entries for one plug-in name."""

    requested_name = str(plugin_name).strip().casefold()
    requested_format = str(plugin_format).strip().casefold()
    source = Path(database or default_liveprofessor_plugin_database())
    if not source.is_file():
        raise VST3ScanError(f"base des plug-ins LiveProfessor introuvable : {source}")
    try:
        root = ET.parse(source).getroot()
    except (ET.ParseError, OSError) as exc:
        raise VST3ScanError(f"base des plug-ins LiveProfessor illisible : {exc}") from exc

    matches: list[Path] = []
    seen: set[str] = set()
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].casefold() != "plugin":
            continue
        if str(element.get("name", "")).strip().casefold() != requested_name:
            continue
        entry_format = str(element.get("format", "")).strip().casefold()
        if requested_format and entry_format != requested_format:
            continue
        raw_path = str(element.get("file", "")).strip()
        if not raw_path:
            continue
        candidate = Path(raw_path).expanduser()
        if not candidate.exists():
            continue
        resolved = candidate.resolve()
        key = str(resolved).casefold()
        if key not in seen:
            seen.add(key)
            matches.append(resolved)
    if not matches:
        raise VST3ScanError(
            f"« {plugin_name} » est absent de la base VST3 de LiveProfessor"
        )
    return tuple(matches)


def _worker_command(module_path: Path, expected_name: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [
            sys.executable,
            "--vst3-scan-worker",
            str(module_path),
            expected_name,
        ]
    return [
        sys.executable,
        "-m",
        "silemio_control_hub.vst3_scanner",
        "--worker",
        str(module_path),
        expected_name,
    ]


def scan_vst3_module(
    module_path: Path,
    *,
    expected_name: str,
    timeout: float = 20.0,
) -> VST3ScanResult:
    """Inspect a VST3 module in a disposable subprocess."""

    source = Path(module_path).expanduser().resolve()
    if not source.exists():
        raise VST3ScanError(f"module de plug-in introuvable : {source}")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        completed = subprocess.run(
            _worker_command(source, expected_name),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1.0, float(timeout)),
            creationflags=creationflags,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VST3ScanError(
            f"« {expected_name} » ne répond pas après {timeout:g} secondes"
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        if len(detail) > 500:
            detail = detail[-500:]
        raise VST3ScanError(
            f"échec du scanner pour « {expected_name} »"
            + (f" : {detail}" if detail else "")
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise VST3ScanError(f"aucune réponse du scanner pour « {expected_name} »")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise VST3ScanError(f"réponse illisible pour « {expected_name} »") from exc
    result = VST3ScanResult.from_dict(payload)
    if result.module_path != source:
        raise VST3ScanError("le scanner a répondu pour un autre module")
    return result


def scan_installed_vst3(
    plugin_name: str,
    *,
    expected_parameter_count: int,
    plugin_format: str = "VST3",
    database: Path | None = None,
    timeout: float = 20.0,
) -> VST3ScanResult:
    """Resolve and scan an installed plug-in, accepting only an exact count."""

    if str(plugin_format).strip().casefold() != "vst3":
        raise VST3ScanError(
            f"le format {plugin_format} ne permet pas encore la lecture directe"
        )
    errors: list[str] = []
    for path in installed_plugin_paths(
        plugin_name,
        plugin_format=plugin_format,
        database=database,
    ):
        try:
            result = scan_vst3_module(
                path,
                expected_name=plugin_name,
                timeout=timeout,
            )
        except VST3ScanError as exc:
            errors.append(str(exc))
            continue
        actual_count = len(result.parameters)
        if actual_count != expected_parameter_count:
            errors.append(
                f"« {plugin_name} » expose {actual_count} paramètres, "
                f"mais le projet LiveProfessor en contient {expected_parameter_count}"
            )
            continue
        return result
    raise VST3ScanError(" ; ".join(errors) or f"« {plugin_name} » est introuvable")


def _decode_c_string(value: Any) -> str:
    return bytes(value).split(b"\0", 1)[0].decode("utf-8", errors="replace").strip()


def _decode_string128(value: Any) -> str:
    raw = ctypes.string_at(ctypes.addressof(value), ctypes.sizeof(value))
    return raw.decode("utf-16-le", errors="replace").split("\0", 1)[0].strip()


def _iid(l1: int, l2: int, l3: int, l4: int) -> bytes:
    # VST3 uses the COM-compatible byte order for TUID values on Windows.
    return (
        struct.pack("<I", l1)
        + bytes(((l2 >> 16) & 0xFF, (l2 >> 24) & 0xFF, l2 & 0xFF, (l2 >> 8) & 0xFF))
        + struct.pack(">II", l3, l4)
    )


_IID_COMPONENT = _iid(0xE831FF31, 0xF2D54301, 0x928EBBEE, 0x25697802)
_IID_EDIT_CONTROLLER = _iid(0xDCD7BBE3, 0x7742448D, 0xA874AACC, 0x979C759E)
_IID_CONNECTION_POINT = _iid(0x70A4156F, 0x6E6E4026, 0x989148BF, 0xAA60D8D1)
_IID_FUNKNOWN = _iid(0x00000000, 0x00000000, 0xC0000000, 0x00000046)
_IID_HOST_APPLICATION = _iid(0x58E595CC, 0xDB2D4969, 0x8B6AAF8C, 0x36A664E5)
_IID_COMPONENT_HANDLER = _iid(0x93A0BEA3, 0x0BD045DB, 0x8E890B0C, 0xC1E46AC6)
_IID_STREAM = _iid(0xC3BF6EA2, 0x30994752, 0x9B6BF990, 0x1EE33E9B)


class _PClassInfo(ctypes.Structure):
    _fields_ = [
        ("cid", ctypes.c_ubyte * 16),
        ("cardinality", ctypes.c_int32),
        ("category", ctypes.c_char * 32),
        ("name", ctypes.c_char * 64),
    ]


class _ParameterInfo(ctypes.Structure):
    _fields_ = [
        ("parameter_id", ctypes.c_uint32),
        ("title", ctypes.c_uint16 * 128),
        ("short_title", ctypes.c_uint16 * 128),
        ("units", ctypes.c_uint16 * 128),
        ("step_count", ctypes.c_int32),
        ("default_normalized_value", ctypes.c_double),
        ("unit_id", ctypes.c_int32),
        ("flags", ctypes.c_int32),
    ]


_CALL = ctypes.WINFUNCTYPE if os.name == "nt" else ctypes.CFUNCTYPE


class _HostApplication(ctypes.Structure):
    _fields_ = [
        ("vtable", ctypes.POINTER(ctypes.c_void_p)),
        ("reference_count", ctypes.c_uint32),
    ]


class _HostContext:
    """Minimal mandatory IHostApplication passed during plug-in initialize."""

    def __init__(self) -> None:
        query_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_void_p),
        )
        ref_type = _CALL(ctypes.c_uint32, ctypes.c_void_p)
        name_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint16),
        )
        create_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_void_p),
        )

        def query(this, iid_pointer, output) -> int:
            requested = ctypes.string_at(iid_pointer, 16)
            if requested not in {_IID_FUNKNOWN, _IID_HOST_APPLICATION}:
                output[0] = None
                return -1
            output[0] = this
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            instance.reference_count += 1
            return 0

        def add_ref(this) -> int:
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            instance.reference_count += 1
            return instance.reference_count

        def release(this) -> int:
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            if instance.reference_count:
                instance.reference_count -= 1
            return instance.reference_count

        def get_name(_this, destination) -> int:
            encoded = "Controller Studio".encode("utf-16-le") + b"\0\0"
            ctypes.memmove(destination, encoded, min(len(encoded), 128 * 2))
            return 0

        def create_instance(_this, _class_id, _interface_id, output) -> int:
            output[0] = None
            return -1

        self.callbacks = (
            query_type(query),
            ref_type(add_ref),
            ref_type(release),
            name_type(get_name),
            create_type(create_instance),
        )
        self.vtable = (ctypes.c_void_p * len(self.callbacks))(
            *(ctypes.cast(callback, ctypes.c_void_p).value for callback in self.callbacks)
        )
        self.instance = _HostApplication(
            ctypes.cast(self.vtable, ctypes.POINTER(ctypes.c_void_p)),
            1,
        )

    @property
    def pointer(self) -> ctypes.c_void_p:
        return ctypes.cast(ctypes.pointer(self.instance), ctypes.c_void_p)


class _ComponentHandlerContext:
    """Minimal mandatory IComponentHandler used during controller inspection."""

    def __init__(self) -> None:
        query_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_void_p),
        )
        ref_type = _CALL(ctypes.c_uint32, ctypes.c_void_p)
        edit_type = _CALL(ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32)
        perform_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_double,
        )
        restart_type = _CALL(ctypes.c_int32, ctypes.c_void_p, ctypes.c_int32)

        def query(this, iid_pointer, output) -> int:
            requested = ctypes.string_at(iid_pointer, 16)
            if requested not in {_IID_FUNKNOWN, _IID_COMPONENT_HANDLER}:
                output[0] = None
                return -1
            output[0] = this
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            instance.reference_count += 1
            return 0

        def add_ref(this) -> int:
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            instance.reference_count += 1
            return instance.reference_count

        def release(this) -> int:
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            if instance.reference_count:
                instance.reference_count -= 1
            return instance.reference_count

        def edit(_this, _parameter_id) -> int:
            return 0

        def perform(_this, _parameter_id, _value) -> int:
            return 0

        def restart(_this, flags) -> int:
            _debug(f"component requested restart flags={flags}")
            return 0

        self.callbacks = (
            query_type(query),
            ref_type(add_ref),
            ref_type(release),
            edit_type(edit),
            perform_type(perform),
            edit_type(edit),
            restart_type(restart),
        )
        self.vtable = (ctypes.c_void_p * len(self.callbacks))(
            *(ctypes.cast(callback, ctypes.c_void_p).value for callback in self.callbacks)
        )
        self.instance = _HostApplication(
            ctypes.cast(self.vtable, ctypes.POINTER(ctypes.c_void_p)),
            1,
        )

    @property
    def pointer(self) -> ctypes.c_void_p:
        return ctypes.cast(ctypes.pointer(self.instance), ctypes.c_void_p)


class _MemoryStreamContext:
    """Small in-memory IBStream for component-to-controller state transfer."""

    def __init__(self) -> None:
        self.data = bytearray()
        self.position = 0
        query_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ctypes.c_void_p),
        )
        ref_type = _CALL(ctypes.c_uint32, ctypes.c_void_p)
        io_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int32),
        )
        seek_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.c_int64,
            ctypes.c_int32,
            ctypes.POINTER(ctypes.c_int64),
        )
        tell_type = _CALL(
            ctypes.c_int32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int64),
        )

        def query(this, iid_pointer, output) -> int:
            requested = ctypes.string_at(iid_pointer, 16)
            if requested not in {_IID_FUNKNOWN, _IID_STREAM}:
                output[0] = None
                return -1
            output[0] = this
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            instance.reference_count += 1
            return 0

        def add_ref(this) -> int:
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            instance.reference_count += 1
            return instance.reference_count

        def release(this) -> int:
            instance = ctypes.cast(this, ctypes.POINTER(_HostApplication)).contents
            if instance.reference_count:
                instance.reference_count -= 1
            return instance.reference_count

        def read(_this, buffer, count, actual) -> int:
            amount = min(max(0, count), max(0, len(self.data) - self.position))
            if amount:
                chunk = bytes(self.data[self.position : self.position + amount])
                ctypes.memmove(buffer, chunk, amount)
                self.position += amount
            if actual:
                actual[0] = amount
            return 0 if amount == count else 1

        def write(_this, buffer, count, actual) -> int:
            amount = max(0, count)
            chunk = ctypes.string_at(buffer, amount) if amount else b""
            end = self.position + amount
            if end > len(self.data):
                self.data.extend(b"\0" * (end - len(self.data)))
            self.data[self.position : end] = chunk
            self.position = end
            if actual:
                actual[0] = amount
            return 0

        def seek(_this, offset, mode, result) -> int:
            if mode == 0:
                target = offset
            elif mode == 1:
                target = self.position + offset
            elif mode == 2:
                target = len(self.data) + offset
            else:
                return 1
            if target < 0:
                return 1
            self.position = int(target)
            if result:
                result[0] = self.position
            return 0

        def tell(_this, result) -> int:
            if not result:
                return 1
            result[0] = self.position
            return 0

        self.callbacks = (
            query_type(query),
            ref_type(add_ref),
            ref_type(release),
            io_type(read),
            io_type(write),
            seek_type(seek),
            tell_type(tell),
        )
        self.vtable = (ctypes.c_void_p * len(self.callbacks))(
            *(ctypes.cast(callback, ctypes.c_void_p).value for callback in self.callbacks)
        )
        self.instance = _HostApplication(
            ctypes.cast(self.vtable, ctypes.POINTER(ctypes.c_void_p)),
            1,
        )

    @property
    def pointer(self) -> ctypes.c_void_p:
        return ctypes.cast(ctypes.pointer(self.instance), ctypes.c_void_p)


def _method(
    interface: ctypes.c_void_p,
    index: int,
    result_type: Any,
    *argument_types: Any,
):
    if not interface or not interface.value:
        raise VST3ScanError("interface VST3 nulle")
    vtable = ctypes.cast(
        interface,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
    ).contents
    address = vtable[index]
    return _CALL(result_type, ctypes.c_void_p, *argument_types)(address)


def _query_interface(interface: ctypes.c_void_p, iid: bytes) -> ctypes.c_void_p | None:
    output = ctypes.c_void_p()
    iid_buffer = (ctypes.c_ubyte * 16).from_buffer_copy(iid)
    result = _method(
        interface,
        0,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_void_p),
    )(interface, iid_buffer, ctypes.byref(output))
    return output if result == 0 and output.value else None


def _release(interface: ctypes.c_void_p | None) -> None:
    if interface and interface.value:
        _method(interface, 2, ctypes.c_uint32)(interface)


def _plugin_binary(path: Path) -> Path:
    if path.is_file():
        return path
    binary_root = path / "Contents" / "x86_64-win"
    candidates = sorted(binary_root.glob("*.vst3"))
    if not candidates:
        raise VST3ScanError(f"binaire VST3 x64 introuvable dans {path}")
    expected = binary_root / path.name
    return expected if expected in candidates else candidates[0]


def _select_class(factory: ctypes.c_void_p, expected_name: str) -> _PClassInfo:
    count = _method(factory, 4, ctypes.c_int32)(factory)
    classes: list[_PClassInfo] = []
    get_info = _method(factory, 5, ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(_PClassInfo))
    for index in range(max(0, count)):
        info = _PClassInfo()
        if get_info(factory, index, ctypes.byref(info)) != 0:
            continue
        if _decode_c_string(info.category).casefold() == "audio module class":
            classes.append(info)
    if not classes:
        raise VST3ScanError("aucune classe audio VST3 trouvée")
    requested = expected_name.strip().casefold()
    exact = [info for info in classes if _decode_c_string(info.name).casefold() == requested]
    if len(exact) == 1:
        return exact[0]
    if len(classes) == 1:
        return classes[0]
    partial = [
        info
        for info in classes
        if requested in _decode_c_string(info.name).casefold()
        or _decode_c_string(info.name).casefold() in requested
    ]
    if len(partial) == 1:
        return partial[0]
    available = ", ".join(_decode_c_string(info.name) for info in classes)
    raise VST3ScanError(
        f"classe « {expected_name} » ambiguë dans le module ({available})"
    )


def _create_instance(
    factory: ctypes.c_void_p,
    class_id: Any,
    interface_id: bytes,
) -> ctypes.c_void_p:
    output = ctypes.c_void_p()
    iid_buffer = (ctypes.c_ubyte * 16).from_buffer_copy(interface_id)
    create = _method(
        factory,
        6,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_ubyte),
        ctypes.POINTER(ctypes.c_void_p),
    )
    result = create(factory, class_id, iid_buffer, ctypes.byref(output))
    if result != 0 or not output.value:
        raise VST3ScanError("impossible d'instancier le contrôleur VST3")
    return output


def _scan_in_process(module_path: Path, expected_name: str) -> VST3ScanResult:
    source = Path(module_path).expanduser().resolve()
    binary = _plugin_binary(source)
    if os.name != "nt":
        raise VST3ScanError("la lecture directe VST3 est disponible sous Windows")
    try:
        library = ctypes.WinDLL(str(binary))
    except OSError as exc:
        raise VST3ScanError(f"chargement impossible : {exc}") from exc

    initialized_dll = False
    factory: ctypes.c_void_p | None = None
    component: ctypes.c_void_p | None = None
    controller: ctypes.c_void_p | None = None
    component_connection: ctypes.c_void_p | None = None
    controller_connection: ctypes.c_void_p | None = None
    component_initialized = False
    controller_initialized = False
    connected = False
    component_active = False
    host = _HostContext()
    component_handler = _ComponentHandlerContext()
    try:
        init_dll = getattr(library, "InitDll", None)
        if init_dll is not None:
            init_dll.restype = ctypes.c_bool
            if not init_dll():
                raise VST3ScanError("InitDll a refusé le chargement")
            initialized_dll = True
        get_factory = getattr(library, "GetPluginFactory", None)
        if get_factory is None:
            raise VST3ScanError("GetPluginFactory est absent du module")
        get_factory.restype = ctypes.c_void_p
        factory = ctypes.c_void_p(get_factory())
        if not factory.value:
            raise VST3ScanError("la fabrique VST3 est indisponible")
        class_info = _select_class(factory, expected_name)
        component = _create_instance(factory, class_info.cid, _IID_COMPONENT)
        initialize_component = _method(component, 3, ctypes.c_int32, ctypes.c_void_p)
        if initialize_component(component, host.pointer) != 0:
            raise VST3ScanError("initialisation du composant VST3 impossible")
        component_initialized = True

        controller = _query_interface(component, _IID_EDIT_CONTROLLER)
        _debug(f"single component/controller={controller is not None}")
        if controller is None:
            controller_class_id = (ctypes.c_ubyte * 16)()
            get_controller_class_id = _method(
                component,
                5,
                ctypes.c_int32,
                ctypes.POINTER(ctypes.c_ubyte),
            )
            if get_controller_class_id(component, controller_class_id) != 0:
                raise VST3ScanError("le composant n'expose pas de contrôleur d'édition")
            controller = _create_instance(
                factory,
                controller_class_id,
                _IID_EDIT_CONTROLLER,
            )
            initialize_controller = _method(controller, 3, ctypes.c_int32, ctypes.c_void_p)
            if initialize_controller(controller, host.pointer) != 0:
                raise VST3ScanError("initialisation du contrôleur VST3 impossible")
            controller_initialized = True
            _debug("separate controller initialized")

            component_connection = _query_interface(component, _IID_CONNECTION_POINT)
            controller_connection = _query_interface(controller, _IID_CONNECTION_POINT)
            if component_connection is not None and controller_connection is not None:
                connect_component = _method(
                    component_connection,
                    3,
                    ctypes.c_int32,
                    ctypes.c_void_p,
                )
                connect_controller = _method(
                    controller_connection,
                    3,
                    ctypes.c_int32,
                    ctypes.c_void_p,
                )
                first = connect_component(component_connection, controller_connection)
                second = connect_controller(controller_connection, component_connection)
                connected = first == 0 and second == 0
                _debug(f"connection results component={first} controller={second}")

        set_component_handler = _method(
            controller,
            16,
            ctypes.c_int32,
            ctypes.c_void_p,
        )
        handler_result = set_component_handler(controller, component_handler.pointer)
        _debug(f"setComponentHandler result={handler_result}")

        component_state = _MemoryStreamContext()
        get_component_state = _method(
            component,
            13,
            ctypes.c_int32,
            ctypes.c_void_p,
        )
        get_state_result = get_component_state(component, component_state.pointer)
        _debug(
            f"getState result={get_state_result} bytes={len(component_state.data)}"
        )
        if get_state_result == 0:
            component_state.position = 0
            set_component_state = _method(
                controller,
                5,
                ctypes.c_int32,
                ctypes.c_void_p,
            )
            state_result = set_component_state(controller, component_state.pointer)
            _debug(f"setComponentState result={state_result}")

        get_count = _method(controller, 8, ctypes.c_int32)
        count = get_count(controller)
        _debug(f"parameter count after initialize/connect={count}")
        if count == 0:
            # A small number of plug-ins populate their edit controller only
            # after the component has entered its active state.  No processing
            # bus is created and no audio is run; this only completes the host
            # side of their documented component lifecycle.
            try:
                set_active = _method(component, 11, ctypes.c_int32, ctypes.c_ubyte)
                active_result = set_active(component, 1)
                _debug(f"setActive result={active_result}")
                if active_result == 0:
                    component_active = True
                    count = get_count(controller)
                    _debug(f"parameter count after setActive={count}")
            except Exception:
                pass
        if count < 0 or count > 100_000:
            raise VST3ScanError(f"nombre de paramètres invalide : {count}")
        get_parameter_info = _method(
            controller,
            9,
            ctypes.c_int32,
            ctypes.c_int32,
            ctypes.POINTER(_ParameterInfo),
        )
        parameters: list[ScannedParameter] = []
        for index in range(count):
            info = _ParameterInfo()
            if get_parameter_info(controller, index, ctypes.byref(info)) != 0:
                raise VST3ScanError(f"lecture impossible du paramètre {index + 1}")
            name = _decode_string128(info.title)
            if not name:
                name = _decode_string128(info.short_title) or f"Parameter {index + 1}"
            parameters.append(
                ScannedParameter(
                    index=index,
                    parameter_id=int(info.parameter_id),
                    name=name,
                    short_name=_decode_string128(info.short_title),
                    unit=_decode_string128(info.units),
                    step_count=int(info.step_count),
                    flags=int(info.flags),
                )
            )
        return VST3ScanResult(
            plugin_name=expected_name,
            class_name=_decode_c_string(class_info.name),
            module_path=source,
            parameters=tuple(parameters),
        )
    finally:
        if connected and component_connection and controller_connection:
            try:
                _method(component_connection, 4, ctypes.c_int32, ctypes.c_void_p)(
                    component_connection, controller_connection
                )
                _method(controller_connection, 4, ctypes.c_int32, ctypes.c_void_p)(
                    controller_connection, component_connection
                )
            except Exception:
                pass
        _release(controller_connection)
        _release(component_connection)
        if controller is not None:
            try:
                _method(controller, 16, ctypes.c_int32, ctypes.c_void_p)(
                    controller, None
                )
            except Exception:
                pass
            if controller_initialized:
                try:
                    _method(controller, 4, ctypes.c_int32)(controller)
                except Exception:
                    pass
            _release(controller)
        if component is not None:
            if component_active:
                try:
                    _method(component, 11, ctypes.c_int32, ctypes.c_ubyte)(component, 0)
                except Exception:
                    pass
            if component_initialized:
                try:
                    _method(component, 4, ctypes.c_int32)(component)
                except Exception:
                    pass
            _release(component)
        if factory is not None:
            _release(factory)
        if initialized_dll:
            exit_dll = getattr(library, "ExitDll", None)
            if exit_dll is not None:
                try:
                    exit_dll()
                except Exception:
                    pass


def worker_main(arguments: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    if len(args) == 3 and args[0] in {"--worker", "--vst3-scan-worker"}:
        args = args[1:]
    if len(args) != 2:
        print("usage: vst3_scanner --worker MODULE EXPECTED_NAME", file=sys.stderr)
        return 2
    try:
        result = _scan_in_process(Path(args[0]), args[1])
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(worker_main())
