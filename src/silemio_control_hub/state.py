from __future__ import annotations

from dataclasses import dataclass, field

from .events import EventContext
from .models import ControllerProfile, ModifierBehavior


@dataclass(slots=True)
class ControllerState:
    """Mutable navigation state shared by device adapters and the simulator."""

    profile: ControllerProfile
    bank: int = 0
    page: int = 0
    _modifiers: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self.set_bank(self.bank)
        self.set_page(self.page)

    @property
    def modifiers(self) -> frozenset[str]:
        return frozenset(self._modifiers)

    @property
    def context(self) -> EventContext:
        return EventContext(self.bank, self.page, self.modifiers)

    def set_bank(self, bank: int) -> int:
        if not isinstance(bank, int):
            raise TypeError("bank doit être un entier")
        self.bank = max(0, min(bank, self.profile.bank_count - 1))
        return self.bank

    def step_bank(self, delta: int) -> int:
        return self.set_bank(self.bank + delta)

    def set_page(self, page: int) -> int:
        if not isinstance(page, int):
            raise TypeError("page doit être un entier")
        self.page = max(0, min(page, self.profile.page_count - 1))
        return self.page

    def step_page(self, delta: int) -> int:
        return self.set_page(self.page + delta)

    def set_modifier(self, modifier_id: str, active: bool) -> bool:
        modifier = next(
            (item for item in self.profile.modifiers if item.id == modifier_id),
            None,
        )
        if modifier is None:
            raise KeyError(f"modificateur inconnu: {modifier_id}")
        if modifier.behavior == ModifierBehavior.TOGGLE and active:
            active = modifier_id not in self._modifiers
        elif modifier.behavior == ModifierBehavior.TOGGLE and not active:
            return modifier_id in self._modifiers
        if active:
            self._modifiers.add(modifier_id)
        else:
            self._modifiers.discard(modifier_id)
        return modifier_id in self._modifiers
