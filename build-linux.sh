#!/usr/bin/env bash
set -euo pipefail

############################################
# KLMP3 build-linux.sh v3 (hybride propre)
############################################

APP_NAME="KLMP3"
MAIN_PY="klmp3.py"
ICON_PATH="assets/KLMP3.png"
KEEP_BUILD_DIRS="0"

############################################
# Options
############################################

while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep) KEEP_BUILD_DIRS="1"; shift ;;
    -h|--help)
      echo "Usage: ./build-linux.sh [--keep]"
      exit 0
      ;;
    *)
      echo "Option inconnue: $1"
      exit 1
      ;;
  esac
done

############################################
# Helpers
############################################

need_file() {
  [[ -f "$1" ]] || { echo "❌ Fichier manquant: $1"; exit 1; }
}

need_dir() {
  [[ -d "$1" ]] || { echo "❌ Dossier manquant: $1"; exit 1; }
}

say() { printf "%s\n" "$*"; }

detect_arch() {
  local m
  m="$(uname -m || true)"
  case "$m" in
    x86_64|amd64) echo "x86_64" ;;
    aarch64|arm64) echo "arm64" ;;
    *) echo "$m" ;;
  esac
}

############################################
# Préflight
############################################

say "🧪 Préflight…"

need_file "$MAIN_PY"
need_file "requirements.txt"
need_file "build-requirements.txt"
need_dir  "assets"
need_file "$ICON_PATH"
need_dir  "tools"

ARCH="$(detect_arch)"
TOOLS_DIR="tools/linux-${ARCH}"

need_dir "$TOOLS_DIR"
need_file "$TOOLS_DIR/ffmpeg"
need_file "$TOOLS_DIR/ffprobe"
need_file "$TOOLS_DIR/appimagetool.AppImage"
# Assurer les droits d'exécution (souvent perdus après zip/copie)
chmod +x "$TOOLS_DIR/ffmpeg" "$TOOLS_DIR/ffprobe" "$TOOLS_DIR/appimagetool.AppImage" 2>/dev/null || true
if [[ -f "$TOOLS_DIR/deno" ]]; then
  chmod +x "$TOOLS_DIR/deno" 2>/dev/null || true
fi

if [[ ! -f "$TOOLS_DIR/deno" ]]; then
  say "⚠️  Deno absent (non bloquant)"
fi

############################################
# Lecture version automatique
############################################

# Lecture __version__ si format direct
VERSION=$(grep -Po '(?<=__version__ = ")[^"]+' "$MAIN_PY" || true)

# Sinon lecture APP_VERSION
if [[ -z "$VERSION" ]]; then
  VERSION=$(grep -Po '(?<=APP_VERSION = ")[^"]+' "$MAIN_PY" || true)
fi

if [[ -z "$VERSION" ]]; then
  echo "❌ Impossible de lire version dans $MAIN_PY"
  exit 1
fi


say "📦 Version détectée : $VERSION"
say "🏗️  Architecture : linux-${ARCH}"

############################################
# Venv
############################################

say "🐍 Préparation venv…"

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -U pip wheel >/dev/null
pip install -r requirements.txt
pip install -r build-requirements.txt

############################################
# Nettoyage précédent
############################################

say "🧹 Nettoyage ancien build…"
rm -rf build dist *.spec "${APP_NAME}.AppDir" releases
mkdir -p releases

############################################
# Build PyInstaller
############################################

say "🏗️  Build PyInstaller…"

python -m PyInstaller \
  --name "$APP_NAME" \
  --noconfirm \
  --clean \
  --windowed \
  --icon "$ICON_PATH" \
  --add-data "assets:assets" \
  --add-data "tools:tools" \
  --collect-all PIL \
  --collect-all yt_dlp \
  --collect-submodules yt_dlp \
  --collect-all certifi \
  "$MAIN_PY"

[[ -f "dist/$APP_NAME/$APP_NAME" ]] || {
  echo "❌ PyInstaller a échoué"
  exit 1
}

############################################
# Création AppDir
############################################

say "📦 Préparation AppImage…"

mkdir -p "${APP_NAME}.AppDir/usr/bin"
cp -a "dist/$APP_NAME/." "${APP_NAME}.AppDir/usr/bin/"

cat > "${APP_NAME}.AppDir/AppRun" <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/bin/$APP_NAME" "\$@"
EOF

chmod +x "${APP_NAME}.AppDir/AppRun"

cat > "${APP_NAME}.AppDir/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Exec=$APP_NAME
Icon=$APP_NAME
Categories=AudioVideo;
Terminal=false
EOF

cp -a "$ICON_PATH" "${APP_NAME}.AppDir/${APP_NAME}.png"

############################################
# Génération AppImage
############################################

APPIMAGE_NAME="${APP_NAME}-${VERSION}-linux-${ARCH}.AppImage"
TAR_NAME="${APP_NAME}-${VERSION}-linux-${ARCH}.tar.gz"

"$TOOLS_DIR/appimagetool.AppImage" \
  "${APP_NAME}.AppDir" \
  "releases/${APPIMAGE_NAME}"

chmod +x "releases/${APPIMAGE_NAME}"

(
  cd releases
  sha256sum "${APPIMAGE_NAME}" > "${APPIMAGE_NAME}.sha256"
)

############################################
# Génération tar.gz
############################################

tar -czf "releases/${TAR_NAME}" -C dist "$APP_NAME"

(
  cd releases
  sha256sum "${TAR_NAME}" > "${TAR_NAME}.sha256"
)

############################################
# Clean final
############################################

if [[ "$KEEP_BUILD_DIRS" == "1" ]]; then
  say "🧾 --keep activé : build conservé"
else
  say "🧹 Clean final…"
  rm -rf build *.spec "${APP_NAME}.AppDir"
  find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
fi

say ""
say "🎉 Build terminé : ${APP_NAME} ${VERSION} (linux-${ARCH})"
say "📦 Artefacts disponibles dans releases/"
