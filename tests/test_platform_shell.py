from pathlib import Path

from silemio_control_hub.platform_shell import open_path


def test_macos_opens_existing_path_with_open(tmp_path):
    document = tmp_path / "manual.pdf"
    document.write_bytes(b"pdf")
    commands = []

    result = open_path(document, platform_name="darwin", launcher=commands.append)

    assert result == document.resolve()
    assert commands == [["open", str(document.resolve())]]


def test_open_path_rejects_missing_paths(tmp_path):
    missing = tmp_path / "missing"
    try:
        open_path(missing, platform_name="darwin", launcher=lambda _command: None)
    except FileNotFoundError as exc:
        assert Path(exc.filename or exc.args[0]) == missing
    else:
        raise AssertionError("missing path was accepted")
