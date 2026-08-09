from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class HostCapabilities:
    discovers_plugins: bool = False
    discovers_parameters: bool = False
    writes_mappings: bool = False
    receives_values: bool = False
    receives_labels: bool = False


class DeviceAdapter(ABC):
    profile_id: str

    @abstractmethod
    def decode(self, message: Any) -> tuple[object, ...]:
        """Convert a hardware message into normalized events."""

    @abstractmethod
    def encode_feedback(self, feedback: Any) -> tuple[bytes, ...]:
        """Convert normalized feedback into hardware messages."""


class HostAdapter(ABC):
    name: str
    capabilities: HostCapabilities

    @abstractmethod
    def inspect(self, project: Path) -> object:
        """Return the host-specific project inventory."""
