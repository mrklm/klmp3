#!/usr/bin/env bash
set -euo pipefail

# build-macos-dmg.sh — KLMP3 macOS Intel x86_64 : .app + .dmg + .sha256
# Usage:
#   ./build-macos-dmg.sh            # version par défaut (1.6)
#   ./build-macos-dmg.sh -v 1.6
#   ./build-macos-dmg.sh -v 1.6 --keep

VERSION="1.6"
KEEP_BUILD_DIRS="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--version) VERSION="${2:-}"; shift 2 ;;
    --keep) KEEP_BUILD_DIRS="1"; shift ;;
    -h|--help)
      sed -n '1,120p' "$0"
      exit 0
      ;;
    *) echo "Option inconnue: $1" >&2; exit 1 ;;
  esac
done

APP_NAME="KLMP3"
DIST_APP="dist/${APP_NAME}.app"
RELEASES_DIR="releases"
DMG_NAME="${APP_NAME}-v${VERSION}-macOS-x86_64.dmg"
DMG_PATH="${RELEASES_DIR}/${DMG_NAME}"
SHA_PATH="${DMG_PATH}.sha256"

# Nettoyage
mkdir -p "${RELEASES_DIR}"
rm -f "${DMG_PATH}" "${SHA_PATH}"

if [[ "${KEEP_BUILD_DIRS}" != "1" ]]; then
  rm -rf build dist
fi

# (Optionnel) venv local
if [[ -d ".venv" ]]; then
  source ".venv/bin/activate"
fi

python3 -m pip install -U pip wheel >/dev/null
python3 -m pip install -U pyinstaller yt-dlp >/dev/null

# Build PyInstaller (.app)
# IMPORTANT: sur macOS, --add-data utilise "source:dest" (deux-points)
pyinstaller --noconfirm --clean --windowed --name "${APP_NAME}" \
  --icon "assets/KLMP3.icns" \
  --add-data "assets:assets" \
  --add-data "tools:tools" \
  klmp3.py

# Vérif
if [[ ! -d "${DIST_APP}" ]]; then
  echo "ERREUR: ${DIST_APP} introuvable (PyInstaller a échoué ?)" >&2
  exit 1
fi

# Création DMG simple (drag & drop)
# On fabrique un dossier "staging" avec l'app + lien Applications
STAGING="$(mktemp -d)"
cp -R "${DIST_APP}" "${STAGING}/"
ln -s /Applications "${STAGING}/Applications"

# Volume name
VOLNAME="${APP_NAME} v${VERSION}"

# DMG (compressé)
hdiutil create -volname "${VOLNAME}" \
  -srcfolder "${STAGING}" \
  -ov -format UDZO \
  "${DMG_PATH}"

rm -rf "${STAGING}"

# SHA-256
shasum -a 256 "${DMG_PATH}" > "${SHA_PATH}"

echo "✅ DMG : ${DMG_PATH}"
echo "✅ SHA : ${SHA_PATH}"
