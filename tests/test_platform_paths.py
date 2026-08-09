from pathlib import Path

import silemio_control_hub.platform_paths as platform_paths
from silemio_control_hub.platform_paths import local_app_data_dir, product_data_dir


def test_explicit_silemio_local_app_data_override_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("SILEMIO_LOCAL_APP_DATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "redirected"))

    assert local_app_data_dir() == tmp_path
    assert product_data_dir() == tmp_path / "Controller Studio for LiveProfessor"


def test_known_folder_path_wins_over_environment_fallbacks(tmp_path, monkeypatch):
    stable = tmp_path / "stable"
    redirected = tmp_path / "redirected"
    monkeypatch.delenv("SILEMIO_LOCAL_APP_DATA", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(redirected))
    monkeypatch.setattr(
        platform_paths,
        "_windows_unredirected_local_app_data",
        lambda: stable,
    )
    monkeypatch.setattr(
        platform_paths,
        "_registry_local_app_data",
        lambda: Path(redirected),
    )
    monkeypatch.setattr(
        platform_paths,
        "_windows_local_app_data",
        lambda: Path(redirected),
    )

    assert local_app_data_dir() == stable
