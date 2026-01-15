#!/usr/bin/env bash
set -euo pipefail

# build-macos.sh — KLMP3 macOS (Intel)
# Build: PyInstaller -> .app -> DMG -> sha256
#
# Usage:
#   ./build-macos.sh
#   ./build-macos.sh -v 1.0.0
#   ./build-macos.sh -v 1.0.0 --keep
#   ./build-macos.sh --zip
#
# Assumptions:
# - venv at .venv/
# - assets/KLMP3.icns exists
# - tools/macos-x86_64/ffmpeg and ffprobe exist
# - yt-dlp uses Python module yt_dlp (collected by PyInstaller)

APP_NAME="KLMP3"
VERSION="0.0.0"
KEEP="0"
MAKE_ZIP="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--version) VERSION="${2:-}"; shift 2 ;;
    --keep) KEEP="1"; shift ;;
    --zip) MAKE_ZIP="1"; shift ;;
    -h|--help)
      sed -n '1,120p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ----- Checks -----
if [[ ! -d ".venv" ]]; then
  echo "❌ Missing .venv/ (create venv first)"
  exit 1
fi

if [[ ! -f "klmp3.py" ]]; then
  echo "❌ Missing klmp3.py (run this script at repo root)"
  exit 1
fi

if [[ ! -f "assets/${APP_NAME}.icns" ]]; then
  echo "❌ Missing assets/${APP_NAME}.icns"
  exit 1
fi

if [[ ! -f "tools/macos-x86_64/ffmpeg" ]]; then
  echo "❌ Missing tools/macos-x86_64/ffmpeg"
  exit 1
fi

if [[ ! -f "tools/macos-x86_64/ffprobe" ]]; then
  echo "❌ Missing tools/macos-x86_64/ffprobe"
  exit 1
fi

# ----- Activate venv -----
# shellcheck disable=SC1091
source ".venv/bin/activate"

python -V
python -c "import yt_dlp; print('yt_dlp OK', yt_dlp.version.__version__)" >/dev/null
python -c "import certifi; print('certifi OK', certifi.where())" >/dev/null

python -m pip install -U pip wheel setuptools >/dev/null
python -m pip install -U pyinstaller yt-dlp certifi >/dev/null

# ----- Clean -----
rm -rf build dist "${APP_NAME}.spec"
rm -rf "$HOME/Library/Application Support/pyinstaller" || true

# ----- Build .app -----
pyinstaller \
  --name "${APP_NAME}" \
  --windowed \
  --noconfirm \
  --clean \
  --icon "assets/${APP_NAME}.icns" \
  --add-data "assets:assets" \
  --add-binary "tools/macos-x86_64/ffmpeg:tools/macos-x86_64" \
  --add-binary "tools/macos-x86_64/ffprobe:tools/macos-x86_64" \
  --collect-all yt_dlp \
  --collect-submodules yt_dlp \
  --collect-all certifi \
  klmp3.py

APP_PATH="dist/${APP_NAME}.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "❌ Build failed: ${APP_PATH} not found"
  exit 1
fi

# ----- Prepare staging -----
STAGING_DIR="dist_dmg_staging"
DMG_NAME="${APP_NAME}-${VERSION}-macOS-x86_64"
DMG_PATH="releases/${DMG_NAME}.dmg"
ZIP_PATH="releases/${DMG_NAME}.zip"

mkdir -p releases
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

# Copy app into staging
cp -R "$APP_PATH" "$STAGING_DIR/"

# Add Applications symlink for drag & drop install
ln -s /Applications "$STAGING_DIR/Applications"

# Optional: remove quarantine attributes on the built app (best effort)
# Big Sur doesn't support xattr -r, so use find.
find "$STAGING_DIR/${APP_NAME}.app" -exec xattr -d com.apple.quarantine {} \; 2>/dev/null || true

# ----- Create DMG -----
rm -f "$DMG_PATH"

hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH" >/dev/null

# ----- Optional ZIP of .app (sometimes useful for GitHub Releases) -----
if [[ "$MAKE_ZIP" == "1" ]]; then
  rm -f "$ZIP_PATH"
  ditto -c -k --sequesterRsrc --keepParent "dist/${APP_NAME}.app" "$ZIP_PATH"
fi

# ----- SHA-256 -----
rm -f "${DMG_PATH}.sha256"
( cd releases && shasum -a 256 "$(basename "$DMG_PATH")" > "$(basename "$DMG_PATH").sha256" )

if [[ "$MAKE_ZIP" == "1" ]]; then
  rm -f "${ZIP_PATH}.sha256"
  ( cd releases && shasum -a 256 "$(basename "$ZIP_PATH")" > "$(basename "$ZIP_PATH").sha256" )
fi

# ----- Done -----
echo
echo "✅ Done:"
echo "   - App:  dist/${APP_NAME}.app"
echo "   - DMG:  ${DMG_PATH}"
echo "   - SHA:  ${DMG_PATH}.sha256"
if [[ "$MAKE_ZIP" == "1" ]]; then
  echo "   - ZIP:  ${ZIP_PATH}"
  echo "   - SHA:  ${ZIP_PATH}.sha256"
fi

if [[ "$KEEP" != "1" ]]; then
  rm -rf "$STAGING_DIR"
fi
