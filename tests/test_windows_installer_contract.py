from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packaging" / "windows" / "SiLeMIO-Controller-Studio.iss"


def test_setup_is_user_scoped_and_uses_the_updater_product_name():
    content = INSTALLER.read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in content
    assert "DefaultDirName={localappdata}\\Programs\\Controller Studio for LiveProfessor" in content
    assert (
        "OutputBaseFilename=Controller-Studio-for-LiveProfessor-Setup-v{#MyAppVersion}"
        in content
    )
    assert "controller-studio.ico" in content
    assert "desktopicon" in content
    assert "Controller-Studio-for-LiveProfessor.exe" in content
