from ec4lpbridge.bridge import EC4LiveProfessorBridge as LegacyBridge
from ec4lpbridge.config import BridgeConfig as LegacyConfig
from ec4lpbridge.midi_backend import MidiConnection as LegacyMidiConnection
from ec4lpbridge.osc_codec import OSCClient as LegacyOSCClient
from ec4lpbridge.profiles import short_label as legacy_short_label

from silemio_control_hub.runtime.config import BridgeConfig
from silemio_control_hub.runtime.ec4_liveprofessor import EC4LiveProfessorRuntime
from silemio_control_hub.runtime.plugin_labels import short_label
from silemio_control_hub.transports.midi import MidiConnection
from silemio_control_hub.transports.osc import OSCClient


def test_historical_modules_are_compatibility_aliases_to_silemio_runtime():
    assert LegacyBridge is EC4LiveProfessorRuntime
    assert LegacyConfig is BridgeConfig
    assert LegacyMidiConnection is MidiConnection
    assert LegacyOSCClient is OSCClient
    assert legacy_short_label is short_label
