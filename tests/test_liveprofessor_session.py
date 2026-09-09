from pathlib import Path

from silemio_control_hub.liveprofessor_session import (
    _default_settings_dirs,
    _liveprofessor_is_running_macos,
    detect_liveprofessor_session,
)


def write_recent_projects(settings_dir: Path, *projects: Path) -> None:
    settings_dir.mkdir(parents=True)
    rows = "\n".join(f'  <ProjectFile file="{project}"/>' for project in projects)
    (settings_dir / "RecentProjects.xml").write_text(
        f"<?xml version=\"1.0\"?><RecentProjectsTree>\n{rows}\n</RecentProjectsTree>",
        encoding="utf-8",
    )


def test_detection_requires_a_running_liveprofessor(tmp_path):
    project = tmp_path / "show.rack2"
    project.write_bytes(b"project")
    settings = tmp_path / "settings"
    write_recent_projects(settings, project)

    session = detect_liveprofessor_session(
        settings_dirs=(settings,), process_running=False
    )

    assert session.running is False
    assert session.project_path is None


def test_detection_uses_first_recent_project(tmp_path):
    current = tmp_path / "current.rack2"
    older = tmp_path / "older.rack2"
    current.write_bytes(b"current")
    older.write_bytes(b"older")
    settings = tmp_path / "settings"
    write_recent_projects(settings, current, older)

    session = detect_liveprofessor_session(
        settings_dirs=(settings,), process_running=True
    )

    assert session.running is True
    assert session.project_path == current.resolve()
    assert session.source == "recent_projects"


def test_detection_never_falls_back_to_an_older_recent_project(tmp_path):
    missing = tmp_path / "missing.rack2"
    older = tmp_path / "older.rack2"
    older.write_bytes(b"older")
    settings = tmp_path / "settings"
    write_recent_projects(settings, missing, older)

    session = detect_liveprofessor_session(
        settings_dirs=(settings,), process_running=True
    )

    assert session.project_path is None


def test_detection_reports_running_without_a_saved_project(tmp_path):
    settings = tmp_path / "settings"
    settings.mkdir()

    session = detect_liveprofessor_session(
        settings_dirs=(settings,), process_running=True
    )

    assert session.running is True
    assert session.project_path is None


def test_macos_process_detection_uses_exact_process_name(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr("silemio_control_hub.liveprofessor_session.sys.platform", "darwin")
    monkeypatch.setattr("silemio_control_hub.liveprofessor_session.subprocess.run", fake_run)

    assert _liveprofessor_is_running_macos() is True
    assert calls[0][0] == ["pgrep", "-x", "LiveProfessor"]


def test_macos_settings_directory_uses_application_support(monkeypatch, tmp_path):
    vendor = tmp_path / "Library" / "Application Support" / "Audiostrom"
    settings = vendor / "LiveProfessor 2"
    settings.mkdir(parents=True)
    monkeypatch.setattr("silemio_control_hub.liveprofessor_session.sys.platform", "darwin")
    monkeypatch.setattr("silemio_control_hub.liveprofessor_session.Path.home", lambda: tmp_path)

    assert _default_settings_dirs() == (settings,)
