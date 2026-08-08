#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(python - <<'PY'
import re
from pathlib import Path

text = Path("pyproject.toml").read_text(encoding="utf-8")
match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
if not match:
    raise SystemExit("Version absente de pyproject.toml")
print(match.group(1))
PY
)"

ARCH="$(uname -m)"
case "$ARCH" in
  arm64) PACKAGE_ARCH="arm64" ;;
  x86_64) PACKAGE_ARCH="x86_64" ;;
  *) echo "Architecture macOS non prise en charge : $ARCH" >&2; exit 1 ;;
esac

for required in \
  "Ec4-UniBank.ctrl2" \
  "Ec4-FullBank.ctrl2" \
  "docs/NOTICE_EC4_BRIDGE_FR.pdf" \
  "docs/en/EC4_BRIDGE_USER_GUIDE_EN.pdf"; do
  test -f "$required" || { echo "Fichier requis absent : $required" >&2; exit 1; }
done

export PYTHONPATH="$ROOT/src"
python -m unittest discover -s tests -v

MAC_OUTPUT="$ROOT/output/macos/$PACKAGE_ARCH"
WORK_PATH="$ROOT/build/pyinstaller-macos-$PACKAGE_ARCH"
SPEC_PATH="$ROOT/build/spec-macos-$PACKAGE_ARCH"
mkdir -p "$MAC_OUTPUT" "$WORK_PATH" "$SPEC_PATH"

python -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --windowed \
  --icon "$ROOT/src/ec4lpbridge/assets/ec4lp.ico" \
  --add-data "$ROOT/src/ec4lpbridge/assets/ec4lp.ico:ec4lpbridge/assets" \
  --add-data "$ROOT/Ec4-UniBank.ctrl2:." \
  --add-data "$ROOT/Ec4-FullBank.ctrl2:." \
  --add-data "$ROOT/docs/NOTICE_EC4_BRIDGE_FR.pdf:docs" \
  --add-data "$ROOT/docs/en/EC4_BRIDGE_USER_GUIDE_EN.pdf:docs/en" \
  --name "EC4-LiveProfessor-Bridge" \
  --paths "$ROOT/src" \
  --collect-submodules "mido.backends" \
  --hidden-import "mido.backends.rtmidi" \
  --distpath "$MAC_OUTPUT" \
  --workpath "$WORK_PATH" \
  --specpath "$SPEC_PATH" \
  "$ROOT/launcher.py"

APP_PATH="$MAC_OUTPUT/EC4-LiveProfessor-Bridge.app"
test -d "$APP_PATH" || { echo "Application macOS absente : $APP_PATH" >&2; exit 1; }

PACKAGE_NAME="EC4-LiveProfessor-Bridge-v${VERSION}-macos-${PACKAGE_ARCH}"
PACKAGE_ROOT="$ROOT/output/distribution"
PACKAGE_DIR="$PACKAGE_ROOT/$PACKAGE_NAME"
ZIP_PATH="$PACKAGE_ROOT/$PACKAGE_NAME.zip"
mkdir -p "$PACKAGE_ROOT"
rm -rf "$PACKAGE_DIR"
rm -f "$ZIP_PATH"
mkdir -p "$PACKAGE_DIR/docs/en"

ditto "$APP_PATH" "$PACKAGE_DIR/EC4-LiveProfessor-Bridge.app"
cp "Ec4-UniBank.ctrl2" "Ec4-FullBank.ctrl2" "$PACKAGE_DIR/"
cp "README.md" "CHANGELOG.md" "$PACKAGE_DIR/"
cp "docs/NOTICE_EC4_BRIDGE_FR.pdf" "$PACKAGE_DIR/docs/"
cp "docs/en/EC4_BRIDGE_USER_GUIDE_EN.pdf" "$PACKAGE_DIR/docs/en/"

ditto -c -k --sequesterRsrc --keepParent "$PACKAGE_DIR" "$ZIP_PATH"
echo "Package macOS prêt : $ZIP_PATH"
