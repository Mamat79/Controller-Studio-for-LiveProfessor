from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ...plugin_profiles import PluginProfile

from .liveprofessor_automap import (
    AutoMapResult,
    ProjectInventory,
    create_automapped_project,
    inspect_project,
)

from ..base import HostAdapter, HostCapabilities


class LiveProfessorHostAdapter(HostAdapter):
    """Première intégration hôte complète du noyau indépendant SiLeMI/O."""

    name = "LiveProfessor"
    capabilities = HostCapabilities(
        discovers_plugins=True,
        discovers_parameters=True,
        writes_mappings=True,
        receives_values=True,
        receives_labels=True,
    )

    def __init__(self, controller_template: Path | None = None) -> None:
        self.controller_template = controller_template

    def inspect(self, project: Path) -> ProjectInventory:
        return inspect_project(project, controller_template=self.controller_template)

    def create_automapped_copy(
        self,
        source: Path,
        destination: Path,
        *,
        controller_uid: int,
        plugin_uid: int | None = None,
        plugin_uids: Iterable[int] | None = None,
        fullbank: bool = False,
        rotary_count: int | None = None,
        plugin_profiles: Iterable[PluginProfile] = (),
    ) -> AutoMapResult:
        return create_automapped_project(
            source,
            destination,
            plugin_uid=plugin_uid,
            plugin_uids=plugin_uids,
            controller_uid=controller_uid,
            expand_to_fullbank=fullbank,
            controller_template=self.controller_template,
            target_rotary_count=rotary_count,
            plugin_profiles=plugin_profiles,
        )
