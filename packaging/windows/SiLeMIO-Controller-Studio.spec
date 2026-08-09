from pathlib import Path


project_root = Path(SPECPATH).parents[1]
package_root = project_root / "src" / "silemio_control_hub"

a = Analysis(
    [str(project_root / "packaging" / "windows" / "gui_entry.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(package_root / "controller_profiles"), "silemio_control_hub/controller_profiles"),
        (str(package_root / "resources"), "silemio_control_hub/resources"),
        (str(package_root / "assets"), "silemio_control_hub/assets"),
        (str(package_root / "manuals"), "silemio_control_hub/manuals"),
    ],
    hiddenimports=[
        "mido.backends.rtmidi",
        "rtmidi",
        "rtmidi._rtmidi",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["ec4lpbridge"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Controller-Studio-for-LiveProfessor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(package_root / "assets" / "controller-studio.ico"),
    codesign_identity=None,
    entitlements_file=None,
)
