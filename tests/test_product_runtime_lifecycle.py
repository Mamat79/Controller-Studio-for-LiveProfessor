import time

from silemio_control_hub.adapters.devices.ec4_protocol import SETUP_REQUEST
from silemio_control_hub.runtime.config import BridgeConfig
import silemio_control_hub.runtime.ec4_liveprofessor as runtime_module


class FakeMidiConnection:
    instances = []

    def __init__(self, callback):
        self.callback = callback
        self.is_open = False
        self.available = True
        self.open_count = 0
        self.sysex = []
        self.cc = []
        self.__class__.instances.append(self)

    def open(self, requested_input, requested_output):
        self.is_open = True
        self.available = True
        self.open_count += 1
        return requested_input, requested_output

    def close(self):
        self.is_open = False

    def ports_still_available(self):
        return self.available

    def send_sysex(self, data):
        self.sysex.append(bytes(data))

    def send_cc(self, channel, control, value):
        self.cc.append((channel, control, value))


class FakeOSCClient:
    def __init__(self, *_args):
        self.messages = []

    def send(self, address, *args):
        self.messages.append((address, args))

    def close(self):
        pass


class FakeOSCServer:
    def __init__(self, *_args):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False


def wait_until(predicate, timeout=1.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached before timeout")


def test_runtime_connects_reconnects_and_repeats_the_product_banner(monkeypatch):
    FakeMidiConnection.instances.clear()
    monkeypatch.setattr(runtime_module, "MidiConnection", FakeMidiConnection)
    monkeypatch.setattr(runtime_module, "OSCClient", FakeOSCClient)
    monkeypatch.setattr(runtime_module, "OSCServer", FakeOSCServer)
    snapshots = []
    runtime = runtime_module.EC4LiveProfessorRuntime(
        BridgeConfig(
            display_enabled=True,
            restrict_to_target=False,
            reconnect_interval_s=0.2,
        ),
        status_callback=snapshots.append,
    )
    midi = FakeMidiConnection.instances[-1]

    runtime.start()
    wait_until(lambda: midi.open_count == 1)
    first_banner = midi.sysex[0]
    assert midi.sysex[-1] == SETUP_REQUEST
    assert runtime.snapshot().midi_connected is True

    midi.available = False
    wait_until(lambda: midi.open_count == 2)
    runtime.stop()

    assert midi.sysex.count(first_banner) == 2
    assert snapshots[-1].running is False
    assert runtime.snapshot().midi_connected is False
