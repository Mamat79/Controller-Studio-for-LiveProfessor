from silemio_control_hub.adapters.devices import EC4DeviceAdapter
from silemio_control_hub.adapters.hosts import LiveProfessorHostAdapter


def test_ec4_adapter_emits_display_sysex():
    messages = EC4DeviceAdapter().encode_feedback({"labels": ["Gain"], "mode": "grid"})
    assert len(messages) == 1
    assert messages[0].startswith(bytes((0xF0,)))
    assert messages[0].endswith(bytes((0xF7,)))


def test_liveprofessor_declares_full_initial_capabilities():
    capabilities = LiveProfessorHostAdapter.capabilities
    assert capabilities.discovers_plugins
    assert capabilities.discovers_parameters
    assert capabilities.writes_mappings
    assert capabilities.receives_values
    assert capabilities.receives_labels
