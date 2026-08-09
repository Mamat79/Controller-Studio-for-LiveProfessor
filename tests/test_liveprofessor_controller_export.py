import hashlib

import pytest

from silemio_control_hub.adapters.hosts import (
    LiveProfessorControllerExportError,
    export_liveprofessor_controller,
)
from silemio_control_hub.formats.juce_value_tree import parse_tree
from silemio_control_hub.adapters.hosts.liveprofessor_controller import (
    BUTTON_ADDRESS,
    ROTARY_ADDRESS,
    default_companion_template,
)
from silemio_control_hub.registry import ControllerRegistry


def _controls(tree):
    return next(child for child in tree.children if child.type_name == "Controls").children


def _counts(tree):
    controls = _controls(tree)
    rotaries = sum(bool(ROTARY_ADDRESS.fullmatch(str(item.get("OSCAddressPatern", "")))) for item in controls)
    buttons = sum(bool(BUTTON_ADDRESS.fullmatch(str(item.get("OSCAddressPatern", "")))) for item in controls)
    return rotaries, buttons


def test_ec4_profile_exports_a_neutral_99_control_companion_file(tmp_path):
    source = default_companion_template()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "Faderfox-EC4.ctrl2"

    result = export_liveprofessor_controller(
        ControllerRegistry().get("faderfox.ec4"),
        destination,
    )

    assert destination.is_file()
    assert result.rotary_count == 99
    assert result.button_count == 16
    assert result.sha256 == hashlib.sha256(destination.read_bytes()).hexdigest().upper()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before

    tree = parse_tree(destination.read_bytes())
    assert tree.type_name == "LPController"
    assert tree.get("ControllerType") == "Companion"
    assert tree.get("ControllerName") == "SiLeMI/O - Faderfox EC4"
    assert tree.get("OSCInPort") == 8010
    assert tree.get("OSCOutPort") == 8011
    assert _counts(tree) == (99, 16)
    presets = next(child for child in tree.children if child.type_name == "MapPresets")
    assert presets.children == []


def test_generic_profile_export_contains_only_its_sixteen_rotaries(tmp_path):
    destination = tmp_path / "Generic.ctrl2"
    result = export_liveprofessor_controller(
        ControllerRegistry().get("generic.midi.16"),
        destination,
        controller_name="My Generic Controller",
        osc_in_port=9010,
        osc_out_port=9011,
    )
    tree = parse_tree(destination.read_bytes())
    assert result.controller_name == "My Generic Controller"
    assert _counts(tree) == (16, 0)
    assert tree.get("OSCInPort") == 9010
    assert tree.get("OSCOutPort") == 9011


def test_ec4_profile_can_export_the_recommended_sixteen_rotary_unibank(tmp_path):
    destination = tmp_path / "Faderfox-EC4-UniBank.ctrl2"

    result = export_liveprofessor_controller(
        ControllerRegistry().get("faderfox.ec4"),
        destination,
        rotary_count=16,
    )

    assert result.rotary_count == 16
    assert _counts(parse_tree(destination.read_bytes())) == (16, 16)


def test_export_can_keep_the_uid_of_an_existing_liveprofessor_controller(tmp_path):
    destination = tmp_path / "Existing-EC4.ctrl2"

    result = export_liveprofessor_controller(
        ControllerRegistry().get("faderfox.ec4"),
        destination,
        controller_name="EC4",
        controller_uid=19_639_590,
        rotary_count=16,
    )

    tree = parse_tree(destination.read_bytes())
    assert result.controller_uid == 19_639_590
    assert tree.get("uID") == 19_639_590
    assert tree.get("ControllerName") == "EC4"


def test_export_refuses_overwrite_without_explicit_replace(tmp_path):
    destination = tmp_path / "Controller.ctrl2"
    destination.write_bytes(b"personal file")
    profile = ControllerRegistry().get("generic.midi.16")
    with pytest.raises(LiveProfessorControllerExportError, match="existe déjà"):
        export_liveprofessor_controller(profile, destination)
    assert destination.read_bytes() == b"personal file"

    result = export_liveprofessor_controller(profile, destination, replace=True)
    assert parse_tree(result.path.read_bytes()).type_name == "LPController"


def test_export_requires_ctrl2_extension_and_valid_ports(tmp_path):
    profile = ControllerRegistry().get("generic.midi.16")
    with pytest.raises(LiveProfessorControllerExportError, match="extension .ctrl2"):
        export_liveprofessor_controller(profile, tmp_path / "Controller.bin")
    with pytest.raises(LiveProfessorControllerExportError, match="osc_in_port"):
        export_liveprofessor_controller(profile, tmp_path / "Controller.ctrl2", osc_in_port=0)
