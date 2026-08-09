from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventContext:
    """Logical surface layer active when an event was emitted."""

    bank: int = 0
    page: int = 0
    modifiers: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class RotationEvent:
    control_id: str
    context: EventContext = EventContext()
    value: float | None = None
    delta: float | None = None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.delta is None):
            raise ValueError("un événement de rotation doit définir value ou delta, exclusivement")
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError("value doit être normalisée entre 0 et 1")


@dataclass(frozen=True, slots=True)
class PressEvent:
    control_id: str
    pressed: bool
    context: EventContext = EventContext()


@dataclass(frozen=True, slots=True)
class TouchEvent:
    control_id: str
    touched: bool
    context: EventContext = EventContext()


@dataclass(frozen=True, slots=True)
class ModifierEvent:
    modifier_id: str
    active: bool
    context: EventContext = EventContext()


@dataclass(frozen=True, slots=True)
class DeviceStateEvent:
    """Normalized device status that is not a user control gesture."""

    name: str
    value: object


@dataclass(frozen=True, slots=True)
class ControlFeedback:
    control_id: str
    value: float | None = None
    label: str | None = None
    led: bool | None = None
    color: str | None = None
    context: EventContext = EventContext()

    def __post_init__(self) -> None:
        if self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError("value doit être normalisée entre 0 et 1")


@dataclass(frozen=True, slots=True)
class DisplayFeedback:
    labels: tuple[str, ...]
    mode: str = "grid"


InputEvent = RotationEvent | PressEvent | TouchEvent | ModifierEvent | DeviceStateEvent
FeedbackEvent = ControlFeedback | DisplayFeedback
