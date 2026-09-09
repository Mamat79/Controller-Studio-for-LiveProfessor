#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "The macOS package must be built on macOS." >&2
  exit 2
fi

target_arch="${1:-arm64}"
case "$target_arch" in
  arm64) release_arch="Apple-Silicon" ;;
  x86_64) release_arch="Intel" ;;
  *) echo "Unsupported architecture: $target_arch" >&2; exit 2 ;;
esac

project_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
cd "$project_root"
python_base="${SILEMIO_MACOS_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12}"
if [[ ! -x "$python_base" ]]; then
  echo "Pinned universal2 Python 3.12 is unavailable: $python_base" >&2
  exit 2
fi

version="$(arch -"$target_arch" "$python_base" -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
venv="$project_root/.venv-macos-$target_arch"
build_root="$project_root/build/macos-$target_arch"
dist_root="$project_root/artifacts/macos/$target_arch"
release_root="$project_root/artifacts/release"
qa_root="$project_root/artifacts/qa/$target_arch"
rm -rf "$venv" "$build_root" "$dist_root" "$qa_root"
mkdir -p "$release_root" "$qa_root"

arch -"$target_arch" "$python_base" -m venv "$venv"
arch -"$target_arch" "$venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip
arch -"$target_arch" "$venv/bin/python" -m pip install --disable-pip-version-check -r requirements-build.txt
arch -"$target_arch" "$venv/bin/python" -c 'import tkinter, mido, rtmidi; print(tkinter.TkVersion, mido.__version__ if hasattr(mido, "__version__") else "mido", rtmidi.get_compiled_api())'

iconset="$project_root/build/controller-studio.iconset"
rm -rf "$iconset"
mkdir -p "$iconset"
source_icon="$project_root/src/silemio_control_hub/assets/controller-studio.png"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$source_icon" --out "$iconset/icon_${size}x${size}.png" >/dev/null
  doubled=$((size * 2))
  sips -z "$doubled" "$doubled" "$source_icon" --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
icon_file="$project_root/build/controller-studio.icns"
iconutil -c icns "$iconset" -o "$icon_file"

SILEMIO_TARGET_ARCH="$target_arch" SILEMIO_VERSION="$version" SILEMIO_MACOS_ICON="$icon_file" \
  arch -"$target_arch" "$venv/bin/python" -m PyInstaller \
    --noconfirm --clean \
    --distpath "$dist_root" \
    --workpath "$build_root" \
    "$project_root/packaging/macos/Controller-Studio.spec"

app="$dist_root/Controller Studio for LiveProfessor.app"
binary="$app/Contents/MacOS/Controller-Studio-for-LiveProfessor"
test -x "$binary"
lipo "$binary" -verify_arch "$target_arch"
codesign --force --deep --sign - "$app"
codesign --verify --deep --strict "$app"
plutil -lint "$app/Contents/Info.plist"

staging="$project_root/build/dmg-$target_arch"
rm -rf "$staging"
mkdir -p "$staging"
cp -R "$app" "$staging/"
ln -s /Applications "$staging/Applications"
dmg="$release_root/Controller-Studio-for-LiveProfessor-macOS-${release_arch}-v${version}.dmg"
rm -f "$dmg" "$dmg.sha256"
hdiutil create -quiet -volname "Controller Studio ${version}" -srcfolder "$staging" -ov -format UDZO "$dmg"

mount_root="$(mktemp -d "${TMPDIR%/}/controller-studio-${target_arch}.XXXXXX")"
cleanup() {
  if mount | grep -Fq " on $mount_root "; then hdiutil detach "$mount_root" >/dev/null || true; fi
  rmdir "$mount_root" 2>/dev/null || true
}
trap cleanup EXIT
hdiutil attach "$dmg" -readonly -nobrowse -mountpoint "$mount_root" >/dev/null
mounted_app="$mount_root/Controller Studio for LiveProfessor.app"
mounted_binary="$mounted_app/Contents/MacOS/Controller-Studio-for-LiveProfessor"
codesign --verify --deep --strict "$mounted_app"
lipo "$mounted_binary" -verify_arch "$target_arch"
SILEMIO_LOCAL_APP_DATA="$qa_root/data" SILEMIO_SMOKE_RESULT="$qa_root/smoke.json" \
  arch -"$target_arch" "$mounted_binary" --smoke-test
python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); assert data.get("status")=="ok", data' "$qa_root/smoke.json"
file "$mounted_binary" > "$qa_root/binary-architecture.txt"
hdiutil detach "$mount_root" >/dev/null
trap - EXIT
rmdir "$mount_root"

(
  cd "$release_root"
  shasum -a 256 "$(basename "$dmg")" > "$(basename "$dmg").sha256"
  shasum -a 256 -c "$(basename "$dmg").sha256"
)

echo "Built and verified $dmg"
