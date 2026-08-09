from __future__ import annotations

from dataclasses import dataclass, field

from .events import (
    ControlFeedback,
    FeedbackEvent,
    ModifierEvent,
    PressEvent,
    RotationEvent,
    TouchEvent,
)
from .models import ControlKind, ControllerProfile
from .state import ControllerState


@dataclass(slots=True)
class ControllerSimulator:
    """Hardware-free source of normalized controller events for tests and tooling."""

    profile: ControllerProfile
    state: ControllerState = field(init=False)
    feedback_history: list[FeedbackEvent] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.state = ControllerState(self.profile)

    def rotate(self, control_id: str, amount: float) -> RotationEvent:
        control = self.profile.control(control_id)
        if not control.supports_rotation:
            raise ValueError(f"{control_id} ne prend pas en charge la rotation")
        if control.kind == ControlKind.RELATIVE_ENCODER:
            return RotationEvent(control_id, self.state.context, delta=float(amount))
        return RotationEvent(control_id, self.state.context, value=float(amount))

    def press(self, control_id: str, pressed: bool = True) -> PressEvent:
        control = self.profile.control(control_id)
        if not control.supports_press:
            raise ValueError(f"{control_id} ne prend pas en charge la pression")
        return PressEvent(control_id, bool(pressed), self.state.context)

    def touch(self, control_id: str, touched: bool = True) -> TouchEvent:
        control = self.profile.control(control_id)
        if not control.supports_touch:
            raise ValueError(f"{control_id} ne prend pas en charge le toucher")
        return TouchEvent(control_id, bool(touched), self.state.context)

    def modifier(self, modifier_id: str, active: bool = True) -> ModifierEvent:
        effective = self.state.set_modifier(modifier_id, active)
        return ModifierEvent(modifier_id, effective, self.state.context)

    def set_bank(self, bank: int) -> int:
        return self.state.set_bank(bank)

    def set_page(self, page: int) -> int:
        return self.state.set_page(page)

    def receive_feedback(self, feedback: FeedbackEvent) -> None:
        if isinstance(feedback, ControlFeedback):
            self.profile.control(feedback.control_id)
        self.feedback_history.append(feedback)
