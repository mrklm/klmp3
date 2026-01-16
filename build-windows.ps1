<# 
build-windows.ps1 — KLMP3 Windows portable (ZIP + SHA256)

Usage:
  powershell -ExecutionPolicy Bypass -File .\build-windows.ps1 -Version 1.6
  powershell -ExecutionPolicy Bypass -File .\build-windows.ps1 -Version 1.6 -Keep
  powershell -ExecutionPolicy Bypass -File .\build-windows.ps1 -Version 1.6 -NoVenv

Attendu à la racine du repo:
  - klmp3.py
  - assets\ (avec KLMP3.ico)
  - tools\ (avec tools\windows-x86_64\yt-dlp.exe, ffmpeg.exe, ffprobe.exe, deno.exe, etc.)
Sorties:
  - dist\KLMP3\...
  - releases\KLMP3-v<Version>-windows-x86_64.zip
  - releases\KLMP3-v<Version>-windows-x86_64.zip.sha256
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory = $false)]
  [string]$Version = "1.6",

  [Parameter(Mandatory = $false)]
  [string]$Arch = "windows-x86_64",

  [Parameter(Mandatory = $false)]
  [switch]$Keep,

  [Parameter(Mandatory = $false)]
  [switch]$NoVenv
)

$ErrorActionPreference = "Stop"

function Die($msg) {
  Write-Host "❌ $msg" -ForegroundColor Red
  exit 1
}

# --- Basic sanity ---
if (-not (Test-Path ".\klmp3.py")) { Die "klmp3.py introuvable (lance ce script à la racine du repo)." }
if (-not (Test-Path ".\assets"))   { Die "Dossier assets/ introuvable." }
if (-not (Test-Path ".\tools"))    { Die "Dossier tools/ introuvable." }

$iconPath = ".\assets\KLMP3.ico"
if (-not (Test-Path $iconPath)) {
  Write-Host "⚠️ Icône Windows absente : $iconPath (build OK, mais icône par défaut)." -ForegroundColor Yellow
  $iconPath = $null
}

# --- Activate venv if present and allowed ---
if (-not $NoVenv) {
  $venvActivate = ".\.venv\Scripts\Activate.ps1"
  if (Test-Path $venvActivate) {
    Write-Host "🐍 Activation venv : .venv" 
    . $venvActivate
  } else {
    Write-Host "⚠️ Pas de venv détecté (.venv). On continue avec le Python courant." -ForegroundColor Yellow
  }
} else {
  Write-Host "🧪 Option -NoVenv : venv non activé." -ForegroundColor Yellow
}

# --- Show python ---
try {
  $py = (Get-Command python).Source
  Write-Host "🐍 Python : $py"
} catch {
  Die "Python introuvable dans PATH. Installe Python ou active ton venv."
}

# --- Ensure build deps ---
Write-Host "📦 Mise à jour pip / installation PyInstaller + yt-dlp (pip)…"
python -m pip install --upgrade pip | Out-Host
python -m pip install --upgrade pyinstaller yt-dlp | Out-Host

# --- Clean build dirs ---
if (-not $Keep) {
  Write-Host "🧹 Nettoyage build/ dist/…"
  Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue
} else {
  Write-Host "🧷 Option -Keep : on conserve build/ dist/." -ForegroundColor Yellow
}

# --- Build PyInstaller ---
Write-Host "🏗️  PyInstaller — build KLMP3.exe"
$pyiArgs = @(
  "--noconfirm",
  "--clean",
  "--windowed",
  "--name", "KLMP3",
  "--add-data", "assets;assets",
  "--add-data", "tools;tools"
)

if ($iconPath) {
  $pyiArgs += @("--icon", $iconPath)
}

$pyiArgs += "klmp3.py"

& pyinstaller @pyiArgs | Out-Host

# --- Verify output ---
$exePath = ".\dist\KLMP3\KLMP3.exe"
if (-not (Test-Path $exePath)) {
  Die "Build terminé mais EXE introuvable : $exePath"
}

# --- Release packaging ---
$releasesDir = ".\releases"
New-Item -ItemType Directory -Force -Path $releasesDir | Out-Null

$zipName = "KLMP3-v$Version-$Arch.zip"
$zipPath = Join-Path $releasesDir $zipName
$shaPath = "$zipPath.sha256"

Write-Host "📦 ZIP : $zipName"
Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
Remove-Item -Force $shaPath -ErrorAction SilentlyContinue

Compress-Archive -Path ".\dist\KLMP3\*" -DestinationPath $zipPath -Force

# --- SHA256 ---
$hash = (Get-FileHash -Algorithm SHA256 $zipPath).Hash.ToLower()
"$hash  $zipName" | Set-Content -Encoding ASCII $shaPath

# --- Done ---
Write-Host ""
Write-Host "✅ EXE : $exePath" -ForegroundColor Green
Write-Host "✅ ZIP : $zipPath" -ForegroundColor Green
Write-Host "✅ SHA : $shaPath" -ForegroundColor Green
Write-Host ""
Write-Host "Astuce test: dézippe dans un dossier temporaire puis lance KLMP3.exe" -ForegroundColor Cyan
