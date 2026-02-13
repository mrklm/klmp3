<# 
Build Windows — KLMP3
- PyInstaller (onedir) + ZIP + SHA256
- Embarque uniquement tools\windows-*
Usage:
  powershell -ExecutionPolicy Bypass -File .\build-windows.ps1
  powershell -ExecutionPolicy Bypass -File .\build-windows.ps1 -Version 2.10.0
  powershell -ExecutionPolicy Bypass -File .\build-windows.ps1 -Arch windows-x86_64
  powershell -ExecutionPolicy Bypass -File .\build-windows.ps1 -Keep
#>

[CmdletBinding()]
param(
  [string]$Version = "",
  [string]$Arch = "windows-x86_64",
  [switch]$Keep
)

$ErrorActionPreference = "Stop"

# Toujours travailler depuis le dossier du script (racine du repo)
Set-Location -Path $PSScriptRoot
Write-Host "📁 Repo : $PSScriptRoot"

function Die($msg) {
  Write-Host "❌ $msg"
  exit 1
}

# ---------- Constantes ----------
$AppName    = "KLMP3"
$EntryPy    = ".\klmp3.py"
$AssetsDir  = ".\assets"
$ToolsDir   = ".\tools\$Arch"
$DistDir    = ".\dist"
$BuildDir   = ".\build"
$ReleasesDir = ".\releases"

# ---------- Sanity checks ----------
if (-not (Test-Path $EntryPy))   { Die "Fichier introuvable : $EntryPy" }
if (-not (Test-Path $AssetsDir)) { Die "Dossier introuvable : $AssetsDir" }
if (-not (Test-Path $ToolsDir))  { Die "Dossier tools introuvable : $ToolsDir (embarquement Windows uniquement)" }

# ---------- Version (si non fournie, on tente de la lire dans klmp3.py) ----------
if ([string]::IsNullOrWhiteSpace($Version)) {
  try {
    $line = Select-String -Path $EntryPy -Pattern '^\s*APP_VERSION\s*=\s*"(.*)"\s*$' -List
    if ($line) {
      $Version = $line.Matches[0].Groups[1].Value
      Write-Host "🔎 Version détectée depuis APP_VERSION : $Version"
    }
  } catch { }
}

if ([string]::IsNullOrWhiteSpace($Version)) {
  Die "Version non fournie et APP_VERSION introuvable. Lancez avec -Version x.y.z"
}

# ---------- Nettoyage ----------
if (-not $Keep) {
  Write-Host "🧹 Nettoyage build/ dist/ + *.spec…"
  Remove-Item -Recurse -Force $BuildDir, $DistDir -ErrorAction SilentlyContinue
  Remove-Item -Force .\*.spec -ErrorAction SilentlyContinue
} else {
  Write-Host "♻️ Keep activé : pas de nettoyage build/dist/spec"
}

# ---------- Prépare releases/ ----------
New-Item -ItemType Directory -Force -Path $ReleasesDir | Out-Null

# ---------- PyInstaller args ----------
$pyiArgs = @(
  "--noconfirm",
  "--clean",
  "--windowed",
  "--name", $AppName,
  "--add-data", "assets;assets",
  # IMPORTANT: n'embarque que tools\windows-*
  "--add-data", ("tools\$Arch;tools\$Arch")
)

# Icône si présente
if (Test-Path ".\assets\ar.ico") {
  $pyiArgs += @("--icon", ".\assets\ar.ico")
}

# Lancement PyInstaller
Write-Host "🧱 PyInstaller (onedir)…"
python -m PyInstaller @pyiArgs $EntryPy
if ($LASTEXITCODE -ne 0) { Die "PyInstaller a échoué (code=$LASTEXITCODE)" }

# ---------- Artefacts ----------
$OutDir = Join-Path $DistDir $AppName
if (-not (Test-Path $OutDir)) { Die "Dossier onedir introuvable : $OutDir" }

$ZipName = "$AppName-windows-$Arch-v$Version.zip"
$ZipPath = Join-Path $ReleasesDir $ZipName

# ZIP (force écrasement)
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Write-Host "📦 ZIP : $ZipName"
Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $ZipPath -Force

# SHA256
$ShaFile = "SHA256SUMS-$AppName-v$Version.txt"
$ShaPath = Join-Path $ReleasesDir $ShaFile

Write-Host "🔐 SHA256 : $ShaFile"
$hash = (Get-FileHash -Algorithm SHA256 $ZipPath).Hash.ToLower()
"$hash  $ZipName" | Out-File -FilePath $ShaPath -Encoding ascii

Write-Host ""
Write-Host "✅ Build terminé."
Write-Host "   - $ZipPath"
Write-Host "   - $ShaPath"
