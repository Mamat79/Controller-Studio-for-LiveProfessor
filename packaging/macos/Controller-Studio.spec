from pathlib import Path
import os


project_root = Path(SPECPATH).parents[1]
package_root = project_root / "src" / "silemio_control_hub"
target_arch = os.environ.get("SILEMIO_TARGET_ARCH", "arm64")
version = os.environ.get("SILEMIO_VERSION", "2026.6")
icon_path = Path(
    os.environ.get(
        "SILEMIO_MACOS_ICON",
        project_root / "build" / "controller-studio.icns",
    )
)

a = Analysis(
    [str(project_root / "packaging" / "macos" / "gui_entry.py")],
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
    [],
    exclude_binaries=True,
    name="Controller-Studio-for-LiveProfessor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=target_arch,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Controller Studio for LiveProfessor",
)
app = BUNDLE(
    coll,
    name="Controller Studio for LiveProfessor.app",
    icon=str(icon_path),
    bundle_identifier="io.silemio.controller-studio-liveprofessor",
    version=version,
    info_plist={
        "CFBundleDisplayName": "Controller Studio for LiveProfessor",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    },
)
