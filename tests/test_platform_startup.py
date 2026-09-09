import plistlib

from silemio_control_hub.platform_startup import (
    MACOS_LAUNCH_AGENT_ID,
    macos_launch_agent_path,
    set_start_with_system,
    starts_with_system,
)


def test_macos_launch_agent_round_trip(tmp_path):
    command = ("/Applications/Controller Studio.app/Contents/MacOS/Controller Studio", "--minimized")

    assert not starts_with_system(
        command,
        platform_name="darwin",
        launch_agents_dir=tmp_path,
    )
    set_start_with_system(
        True,
        command,
        platform_name="darwin",
        launch_agents_dir=tmp_path,
    )

    launch_agent = macos_launch_agent_path(tmp_path)
    payload = plistlib.loads(launch_agent.read_bytes())
    assert payload["Label"] == MACOS_LAUNCH_AGENT_ID
    assert payload["ProgramArguments"] == list(command)
    assert payload["RunAtLoad"] is True
    assert starts_with_system(
        command,
        platform_name="darwin",
        launch_agents_dir=tmp_path,
    )

    set_start_with_system(
        False,
        command,
        platform_name="darwin",
        launch_agents_dir=tmp_path,
    )
    assert not launch_agent.exists()


def test_macos_disabling_absent_launch_agent_is_idempotent(tmp_path):
    set_start_with_system(
        False,
        ("/Applications/Controller Studio.app/Contents/MacOS/Controller Studio",),
        platform_name="darwin",
        launch_agents_dir=tmp_path,
    )
