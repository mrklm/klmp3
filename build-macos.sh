#!/usr/bin/env bash
set -euo pipefail

# build-macos.sh — KLMP3 macOS (Intel/Apple Silicon)
# Build: PyInstaller -> .app -> (optional) ZIP -> DMG -> sha256
#
# Usage:
#   ./build-macos.sh
#   ./build-macos.sh -v 2.4.1
#   ./build-macos.sh -v 2.4.1 --zip
#   ./build-macos.sh -v 2.4.1 --keep
#   ./build-macos.sh -v 2.4.1 --arch x86_64
#   ./build-macos.sh -v 2.4.1 --arch arm64
#
# Assumptions:
# - Run at repo root (contains klmp3.py, assets/, tools/, .venv/)
# - assets/KLMP3.icns exists
# - tools/macos-<arch>/ffmpeg, ffprobe, deno exist (executable)
# - yt-dlp is used as Python module (yt_dlp) + certifi collected by PyInstaller

APP_NAME="KLMP3"
VERSION="2.4.1"
KEEP="0"
MAKE_ZIP="0"
ARCH=""   # "x86_64" | "arm64" | auto

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--version) VERSION="${2:-}"; shift 2 ;;
    --keep) KEEP="1"; shift ;;
    --zip) MAKE_ZIP="1"; shift ;;
    --arch) ARCH="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '1,200p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# --- Detect arch if not provided ---
if [[ -z "$ARCH" ]]; then
  MACHINE="$(uname -m)"
  if [[ "$MACHINE" == "arm64" ]]; then
    ARCH="arm64"
  else
    ARCH="x86_64"
  fi
fi

if [[ "$ARCH" != "x86_64" && "$ARCH" != "arm64" ]]; then
  echo "❌ Invalid --arch. Use x86_64 or arm64."
  exit 1
fi

TOOLS_DIR="tools/macos-${ARCH}"
ICON_PATH="assets/${APP_NAME}.icns"
PY_FILE="klmp3.py"

# --- Checks ---
[[ -d ".venv" ]] || { echo "❌ Missing .venv/ (create venv first)"; exit 1; }
[[ -f "$PY_FILE" ]] || { echo "❌ Missing ${PY_FILE} (run this script at repo root)"; exit 1; }
[[ -f "$ICON_PATH" ]] || { echo "❌ Missing ${ICON_PATH}"; exit 1; }

for bin in ffmpeg ffprobe deno; do
  [[ -f "${TOOLS_DIR}/${bin}" ]] || { echo "❌ Missing ${TOOLS_DIR}/${bin}"; exit 1; }
done

# Ensure tools are executable (best effort)
chmod +x "${TOOLS_DIR}/ffmpeg" "${TOOLS_DIR}/ffprobe" "${TOOLS_DIR}/deno" 2>/dev/null || true

echo "== KLMP3 macOS build =="
echo " - Version: ${VERSION}"
echo " - Arch:    ${ARCH}"
echo " - Tools:   ${TOOLS_DIR}"

# --- Activate venv ---
# shellcheck disable=SC1091
source ".venv/bin/activate"

python -V
python -m pip install -U pip wheel setuptools >/dev/null
python -m pip install -U pyinstaller yt-dlp certifi >/dev/null

# Quick imports (fail fast)
python -c "import yt_dlp; print('yt_dlp OK', yt_dlp.version.__version__)" >/dev/null
python -c "import certifi; print('certifi OK', certifi.where())" >/dev/null

# --- Clean ---
rm -rf build dist "${APP_NAME}.spec"
rm -rf "$HOME/Library/Application Support/pyinstaller" || true

# --- Build .app ---
pyinstaller \
  --name "${APP_NAME}" \
  --windowed \
  --noconfirm \
  --clean \
  --icon "${ICON_PATH}" \
  --add-data "assets:assets" \
  --add-binary "${TOOLS_DIR}/ffmpeg:${TOOLS_DIR}" \
  --add-binary "${TOOLS_DIR}/ffprobe:${TOOLS_DIR}" \
  --add-binary "${TOOLS_DIR}/deno:${TOOLS_DIR}" \
  --collect-all yt_dlp \
  --collect-submodules yt_dlp \
  --collect-all certifi \
  "${PY_FILE}"

APP_PATH="dist/${APP_NAME}.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "❌ Build failed: ${APP_PATH} not found"
  exit 1
fi

# --- Sanity checks inside bundle ---
BUNDLE_TOOLS="dist/${APP_NAME}.app/Contents/Frameworks/${TOOLS_DIR}"
echo "== Sanity checks =="
for bin in ffmpeg ffprobe deno; do
  if [[ ! -f "${BUNDLE_TOOLS}/${bin}" ]]; then
    echo "❌ Missing in bundle: ${BUNDLE_TOOLS}/${bin}"
    exit 1
  fi
done
echo "✅ Tools embedded: ffmpeg, ffprobe, deno"

# --- Release artifacts ---
mkdir -p releases

BASE_NAME="${APP_NAME}-${VERSION}-macOS-${ARCH}"
DMG_PATH="releases/${BASE_NAME}.dmg"
ZIP_PATH="releases/${BASE_NAME}.zip"

# --- Optional ZIP of .app ---
if [[ "$MAKE_ZIP" == "1" ]]; then
  rm -f "$ZIP_PATH"
  # keepParent => includes KLMP3.app folder
  ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
  ( cd releases && shasum -a 256 "$(basename "$ZIP_PATH")" > "$(basename "$ZIP_PATH").sha256" )
  echo "✅ ZIP: ${ZIP_PATH}"
  echo "✅ SHA: ${ZIP_PATH}.sha256"
fi

# --- Prepare DMG staging ---
STAGING_DIR="dist_dmg_staging"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

# Best effort: remove quarantine attrs from built app inside staging (Big Sur friendly)
find "$STAGING_DIR/${APP_NAME}.app" -exec xattr -d com.apple.quarantine {} \; 2>/dev/null || true

# --- Create DMG ---
rm -f "$DMG_PATH"
hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH" >/dev/null

# --- SHA-256 for DMG ---
rm -f "${DMG_PATH}.sha256"
( cd releases && shasum -a 256 "$(basename "$DMG_PATH")" > "$(basename "$DMG_PATH").sha256" )

echo
echo "✅ Done:"
echo " - App: dist/${APP_NAME}.app"
echo " - DMG: ${DMG_PATH}"
echo " - SHA: ${DMG_PATH}.sha256"
if [[ "$MAKE_ZIP" == "1" ]]; then
  echo " - ZIP: ${ZIP_PATH}"
  echo " - SHA: ${ZIP_PATH}.sha256"
fi

if [[ "$KEEP" != "1" ]]; then
  rm -rf "$STAGING_DIR"
else
  echo "ℹ️ Kept staging dir: ${STAGING_DIR}"
fi
