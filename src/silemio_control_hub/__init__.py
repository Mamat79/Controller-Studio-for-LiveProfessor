"""SiLeMI/O Controller Studio core package."""

from .events import ControlFeedback, EventContext, PressEvent, RotationEvent, TouchEvent
from .identity import BRAND_NAME, FULL_PRODUCT_NAME, HOST_EDITION, PRODUCT_NAME
from .mapping import MappingAssignment, MappingPlan, MappingPlanner, ParameterDefinition
from .library_remote import GitHubLibraryClient, update_library
from .models import ControllerProfile, ControlDefinition, MidiBinding
from .plugin_profiles import (
    PluginObservation,
    PluginProfile,
    PluginProfileResolver,
    ResolvedPluginProfile,
)
from .plugin_registry import PluginProfileRegistry
from .registry import ControllerRegistry
from .simulator import ControllerSimulator
from .state import ControllerState
from .workflow import LiveProfessorPreparation, prepare_liveprofessor_project

__all__ = [
    "ControlFeedback",
    "BRAND_NAME",
    "ControllerProfile",
    "ControllerRegistry",
    "ControllerSimulator",
    "ControllerState",
    "ControlDefinition",
    "EventContext",
    "FULL_PRODUCT_NAME",
    "GitHubLibraryClient",
    "MappingAssignment",
    "MappingPlan",
    "MappingPlanner",
    "MidiBinding",
    "LiveProfessorPreparation",
    "HOST_EDITION",
    "ParameterDefinition",
    "PluginObservation",
    "PluginProfile",
    "PluginProfileResolver",
    "PluginProfileRegistry",
    "PressEvent",
    "PRODUCT_NAME",
    "RotationEvent",
    "ResolvedPluginProfile",
    "TouchEvent",
    "update_library",
    "prepare_liveprofessor_project",
]

__version__ = "2026.2"
