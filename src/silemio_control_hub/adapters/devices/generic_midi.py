from __future__ import annotations

from ...models import ControllerProfile
from ...registry import ControllerRegistry
from ...state import ControllerState
from .profile_midi import ProfileMidiDeviceAdapter


class GenericMidiDeviceAdapter(ProfileMidiDeviceAdapter):
    """Baseline profile-driven adapter for standard MIDI controllers."""

    profile_id = "generic.midi.16"

    def __init__(
        self,
        profile: ControllerProfile | None = None,
        state: ControllerState | None = None,
    ) -> None:
        super().__init__(profile or ControllerRegistry().get(self.profile_id), state)
