from silemio_control_hub.mapping import (
    ControlAction,
    MappingAssignment,
    MappingPlanner,
    ParameterDefinition,
    ParameterKind,
)
from silemio_control_hub.registry import ControllerRegistry


def _ec4():
    return ControllerRegistry().get("faderfox.ec4")


def test_manual_mapping_wins_and_parameter_is_not_duplicated():
    planner = MappingPlanner()
    parameters = [
        ParameterDefinition("mix", "Mix", priority=10),
        ParameterDefinition("gain", "Output", priority=5, preferred_role="output"),
    ]
    manual = [MappingAssignment("mix", "encoder_04", ControlAction.ROTATE, manual=True)]
    plan = planner.plan(_ec4(), parameters, manual)
    mix = [item for item in plan.assignments if item.parameter_id == "mix"]
    gain = [item for item in plan.assignments if item.parameter_id == "gain"]
    assert len(mix) == 1
    assert mix[0].control_id == "encoder_04"
    assert mix[0].manual
    assert len(gain) == 1
    assert gain[0].control_id == "encoder_16"


def test_buttons_use_push_and_labels_remain_available():
    parameters = [ParameterDefinition("bypass", "Bypass", ParameterKind.TOGGLE)]
    plan = MappingPlanner().plan(_ec4(), parameters)
    assert plan.assignments[0].action == ControlAction.PRESS
    assert plan.label_parameter_for(plan.assignments[0].control_id) == "bypass"


def test_rotation_label_has_priority_over_push_label_on_same_encoder():
    parameters = [
        ParameterDefinition("frequency", "Frequency"),
        ParameterDefinition("reset", "Reset", ParameterKind.MOMENTARY),
    ]
    plan = MappingPlanner().plan(_ec4(), parameters)
    first = plan.assignments[0].control_id
    assert first == plan.assignments[1].control_id
    assert plan.label_parameter_for(first) == "frequency"


def test_automatic_mapping_uses_later_banks_without_parameter_duplicates():
    parameters = [ParameterDefinition(f"parameter-{index}", f"Parameter {index}") for index in range(17)]
    plan = MappingPlanner().plan(_ec4(), parameters)
    assert not plan.unmapped_parameters
    assert len({assignment.parameter_id for assignment in plan.assignments}) == 17
    assert plan.assignments[15].control_id == "encoder_16"
    assert plan.assignments[15].bank == 0
    assert plan.assignments[16].control_id == "encoder_01"
    assert plan.assignments[16].bank == 1
    assert plan.label_parameter_for("encoder_01", bank=1) == "parameter-16"


def test_manual_mapping_context_is_preserved_and_audited():
    manual = [
        MappingAssignment(
            "mix",
            "encoder_04",
            ControlAction.ROTATE,
            manual=True,
            bank=2,
            modifiers=frozenset({"shift"}),
        )
    ]
    plan = MappingPlanner().plan(_ec4(), [ParameterDefinition("mix", "Mix")], manual)
    assert plan.assignments == (
        MappingAssignment(
            "mix",
            "encoder_04",
            ControlAction.ROTATE,
            manual=True,
            reason="manual-preserved",
            bank=2,
            modifiers=frozenset({"shift"}),
        ),
    )
    assert not plan.conflicts


def test_partial_last_ec4_bank_caps_automatic_mapping_at_99_parameters():
    parameters = [ParameterDefinition(f"p{index}", f"P{index}") for index in range(100)]
    plan = MappingPlanner().plan(_ec4(), parameters)
    assert len(plan.assignments) == 99
    assert plan.unmapped_parameters == ("p99",)
