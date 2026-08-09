"""Offline-first registry for cached Suggested and local User plug-in profiles."""

from __future__ import annotations

from pathlib import Path

from .library_remote import (
    LibraryRemoteError,
    cached_library_profiles,
    default_library_cache_dir,
)
from .plugin_profiles import PluginProfile, PluginProfileError, PluginProfileLayer
from .platform_paths import legacy_control_hub_data_dir, product_data_dir


def default_user_plugin_profile_dir() -> Path:
    return product_data_dir() / "plugin_profiles"


class PluginProfileRegistry:
    """Load validated remote suggestions, then higher-priority local profiles."""

    def __init__(
        self,
        profile_directories: list[Path] | None = None,
        *,
        library_cache_root: Path | None = None,
    ) -> None:
        self.profile_directories = list(
            profile_directories
            if profile_directories is not None
            else [
                legacy_control_hub_data_dir() / "plugin_profiles",
                default_user_plugin_profile_dir(),
            ]
        )
        self.library_cache_root = Path(
            library_cache_root or default_library_cache_dir()
        )
        self._profiles: tuple[PluginProfile, ...] | None = None
        self._sources: dict[tuple[str, str, str], Path] = {}

    def load(self) -> None:
        try:
            remote_paths = cached_library_profiles(self.library_cache_root).plugins
        except LibraryRemoteError as exc:
            raise PluginProfileError(f"cache de bibliothèque invalide: {exc}") from exc
        paths: list[Path] = list(remote_paths)
        for directory in self.profile_directories:
            if directory.exists():
                paths.extend(sorted(directory.glob("*.json")))
        profiles: list[PluginProfile] = []
        sources: dict[tuple[str, str, str], Path] = {}
        for path in paths:
            profile = PluginProfile.load_file(path)
            if path in remote_paths and profile.layer != PluginProfileLayer.SUGGESTED:
                raise PluginProfileError(
                    f"le cache distant contient une couche interdite: {profile.layer.value}"
                )
            if path not in remote_paths and profile.layer != PluginProfileLayer.USER:
                raise PluginProfileError(
                    f"un profil local doit utiliser la couche user: {profile.layer.value}"
                )
            profiles.append(profile)
            sources[(profile.layer.value, profile.id, profile.profile_version)] = path
        self._profiles = tuple(profiles)
        self._sources = sources

    def all(self) -> tuple[PluginProfile, ...]:
        if self._profiles is None:
            self.load()
        return tuple(
            sorted(
                self._profiles or (),
                key=lambda item: (item.plugin_name.casefold(), item.layer.value, item.id),
            )
        )

    def source(self, profile: PluginProfile) -> Path:
        if self._profiles is None:
            self.load()
        return self._sources[
            (profile.layer.value, profile.id, profile.profile_version)
        ]
