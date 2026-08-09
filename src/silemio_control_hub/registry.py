from __future__ import annotations

import json
from pathlib import Path

from .library_remote import (
    LibraryRemoteError,
    cached_library_profiles,
    default_library_cache_dir,
)
from .models import ControllerProfile, ProfileError
from .platform_paths import legacy_control_hub_data_dir, product_data_dir


class ControllerRegistry:
    """Offline-first registry for built-in and user controller profiles."""

    def __init__(
        self,
        profile_directories: list[Path] | None = None,
        *,
        library_cache_root: Path | None = None,
    ) -> None:
        builtin = Path(__file__).with_name("controller_profiles")
        directories = profile_directories
        if directories is None:
            directories = [
                legacy_control_hub_data_dir() / "controller_profiles",
                default_user_profile_dir(),
            ]
        self.builtin_directory = builtin
        self.profile_directories = list(directories)
        self.library_cache_root = Path(
            library_cache_root or default_library_cache_dir()
        )
        self._profiles: dict[str, ControllerProfile] = {}
        self._sources: dict[str, Path] = {}

    def load(self) -> None:
        profiles: dict[str, ControllerProfile] = {}
        sources: dict[str, Path] = {}
        sources_to_load: list[Path] = []
        if self.builtin_directory.exists():
            sources_to_load.extend(sorted(self.builtin_directory.glob("*.json")))
        try:
            sources_to_load.extend(
                cached_library_profiles(self.library_cache_root).controllers
            )
        except LibraryRemoteError as exc:
            raise ProfileError(f"cache de bibliothèque invalide: {exc}") from exc
        for directory in self.profile_directories:
            if not directory.exists():
                continue
            sources_to_load.extend(sorted(directory.glob("*.json")))
        for path in sources_to_load:
            profile = self.load_file(path)
            profiles[profile.id] = profile
            sources[profile.id] = path
        self._profiles = profiles
        self._sources = sources

    @staticmethod
    def load_file(path: Path) -> ControllerProfile:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProfileError(f"profil illisible {path}: {exc}") from exc
        return ControllerProfile.from_dict(raw)

    def all(self) -> tuple[ControllerProfile, ...]:
        if not self._profiles:
            self.load()
        return tuple(sorted(self._profiles.values(), key=lambda item: item.display_name.casefold()))

    def get(self, profile_id: str) -> ControllerProfile:
        if not self._profiles:
            self.load()
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise KeyError(f"profil de contrôleur inconnu: {profile_id}") from exc

    def source(self, profile_id: str) -> Path:
        if not self._profiles:
            self.load()
        return self._sources[profile_id]


def default_user_profile_dir() -> Path:
    return product_data_dir() / "controller_profiles"
