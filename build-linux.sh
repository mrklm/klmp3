#!/usr/bin/env bash
set -euo pipefail

# build-linux.sh — KLMP3 (Linux) — binaire + tar.gz + sha256 + clean
# Usage:
#   ./build-linux.sh
#   ./build-linux.sh -v 2.6.2
#   ./build-linux.sh -v 2.6.2 --keep
#
# À lancer à la racine du repo (là où sont klmp3.py, assets/, tools/, etc.)

VERSION="2.6.2"
KEEP_BUILD_DIRS="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--version) VERSION="${2:-}"; shift 2 ;;
    --keep) KEEP_BUILD_DIRS="1"; shift ;;
    -h|--help)
      sed -n '1,120p' "$0"
      exit 0
      ;;
    *)
      echo "Option inconnue: $1"
      exit 1
      ;;
  esac
done

# -------- Helpers --------
need_file() {
  if [[ ! -f "$1" ]]; then
    echo "❌ Fichier manquant: $1"
    exit 1
  fi
}

need_dir() {
  if [[ ! -d "$1" ]]; then
    echo "❌ Dossier manquant: $1"
    exit 1
  fi
}

detect_arch() {
  local m
  m="$(uname -m || true)"
  case "$m" in
    x86_64|amd64) echo "x86_64" ;;
    aarch64|arm64) echo "arm64" ;;
    *) echo "$m" ;;
  esac
}

say() { printf "%s\n" "$*"; }

# -------- Preflight --------
say "🧪 Préflight…"
need_file "klmp3.py"
need_file "requirements.txt"
need_file "build-requirements.txt"
need_dir  "assets"
need_file "assets/logo.png"
need_dir  "tools"

ARCH="$(detect_arch)"
TOOLS_DIR="tools/linux-${ARCH}"

need_dir "$TOOLS_DIR"
need_file "$TOOLS_DIR/ffmpeg"
need_file "$TOOLS_DIR/ffprobe"
# deno : recommandé mais pas strictement obligatoire pour build ; on prévient seulement
if [[ ! -f "$TOOLS_DIR/deno" ]]; then
  say "⚠️  Deno absent dans $TOOLS_DIR (YouTube JS challenge peut être dégradé)"
fi

# -------- Venv --------
say "🐍 Création/activation venv…"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -U pip wheel >/dev/null
say "📦 Installation dépendances…"
pip install -r requirements.txt
pip install -r build-requirements.txt

# -------- Clean old build artifacts --------
say "🧹 Nettoyage anciens artefacts…"
rm -rf build dist *.spec __pycache__ || true

# -------- Build PyInstaller --------
say "🏗️  Build PyInstaller (Linux ${ARCH})…"
python -m PyInstaller \
  --name KLMP3 \
  --noconfirm \
  --clean \
  --windowed \
  --icon assets/logo.png \
  --add-data "assets:assets" \
  --add-data "tools:tools" \
  --collect-all PIL \
  klmp3.py

# -------- Release artifacts --------
say "📦 Préparation release…"
cd dist

OUT_DIR="KLMP3-${VERSION}-linux-${ARCH}"
if [[ -d "$OUT_DIR" ]]; then
  rm -rf "$OUT_DIR"
fi

mv "KLMP3" "$OUT_DIR"

TAR_NAME="${OUT_DIR}.tar.gz"
SHA_NAME="${TAR_NAME}.sha256"

say "🗜️  Création: ${TAR_NAME}"
tar -czf "$TAR_NAME" "$OUT_DIR"

say "🔒 SHA-256: ${SHA_NAME}"
sha256sum "$TAR_NAME" > "$SHA_NAME"

say "✅ Artefacts générés dans dist/:"
ls -la "$OUT_DIR" "$TAR_NAME" "$SHA_NAME" | sed 's/^/  /'

# -------- Optional quick run note --------
say ""
say "🧪 Test rapide (optionnel) :"
say "  ./dist/${OUT_DIR}/KLMP3"

cd ..

# -------- Clean build temp --------
if [[ "$KEEP_BUILD_DIRS" == "1" ]]; then
  say "🧾 --keep activé : on conserve build/ et *.spec"
else
  say "🧹 Clean (build/ *.spec __pycache__)…"
  rm -rf build *.spec __pycache__ || true
  find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
fi

say "🎉 Build terminé : ${VERSION} (linux-${ARCH})"