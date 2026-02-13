[CmdletBinding()]
param(
  [string]$Version = "",
  [string]$Arch = "windows-x86_64",
  [switch]$Keep
)

$ErrorActionPreference = "Stop"

function Die([string]$msg) {
  Write-Host "ERROR: $msg"
  exit 1
}

Set-Location -Path $PSScriptRoot
Write-Host "Repo: $PSScriptRoot"

# ---------- Constantes ----------
$AppName      = "KLMP3"
$EntryPy      = Join-Path $PSScriptRoot "klmp3.py"
$AssetsDir    = Join-Path $PSScriptRoot "assets"
$ToolsDir     = Join-Path $PSScriptRoot ("tools\" + $Arch)
$DistDir      = Join-Path $PSScriptRoot "dist"
$BuildDir     = Join-Path $PSScriptRoot "build"
$ReleasesDir  = Join-Path $PSScriptRoot "releases"
$VenvDir      = Join-Path $PSScriptRoot ".venv-build"
$VenvPython   = Join-Path $VenvDir "Scripts\python.exe"
$ReqFile      = Join-Path $PSScriptRoot "requirements.txt"
$IconPath     = Join-Path $AssetsDir "KLMP3.ico"

# ---------- Sanity checks ----------
if (-not (Test-Path $EntryPy))   { Die "Missing file: $EntryPy" }
if (-not (Test-Path $AssetsDir)) { Die "Missing folder: $AssetsDir" }
if (-not (Test-Path $ToolsDir))  { Die "Missing tools folder: $ToolsDir" }

# Icon is required for Windows
if (-not (Test-Path $IconPath))  { Die "Missing icon: $IconPath" }

# ---------- Version (detect from klmp3.py if not provided) ----------
if ([string]::IsNullOrWhiteSpace($Version)) {
  $line = Get-Content $EntryPy | Where-Object { $_ -match "APP_VERSION" } | Select-Object -First 1
  if ($line) {
    $parts = $line.Split('"')
    if ($parts.Count -ge 2) {
      $Version = $parts[1]
      Write-Host "Detected version: $Version"
    }
  }
}
if ([string]::IsNullOrWhiteSpace($Version)) {
  Die "Version not provided and APP_VERSION not found."
}

# ---------- TRUE CLEAN ----------
if (-not $Keep) {
  Write-Host "Full clean: build/, dist/, releases/, *.spec, .venv-build/"
  Remove-Item -Recurse -Force $BuildDir, $DistDir, $ReleasesDir -ErrorAction SilentlyContinue
  Remove-Item -Force (Join-Path $PSScriptRoot "*.spec") -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
} else {
  Write-Host "Keep enabled: no cleaning (build/dist/releases/spec/venv preserved)"
}

# ---------- Create build venv ----------
Write-Host "Creating build venv: $VenvDir"
python -m venv $VenvDir
if (-not (Test-Path $VenvPython)) { Die "Failed to create venv at $VenvDir" }

# ---------- Install build tools ----------
Write-Host "Preparing build venv..."
& $VenvPython -m pip install --upgrade pip setuptools wheel | Out-Host
& $VenvPython -m pip install --upgrade pyinstaller | Out-Host

if (Test-Path $ReqFile) {
  Write-Host "Installing requirements.txt..."
  & $VenvPython -m pip install -r $ReqFile | Out-Host
}

# ---------- Prepare releases ----------
New-Item -ItemType Directory -Force -Path $ReleasesDir | Out-Null

# ---------- PyInstaller args ----------
$pyiArgs = @()
$pyiArgs += "--noconfirm"
$pyiArgs += "--clean"
$pyiArgs += "--windowed"
$pyiArgs += "--name"
$pyiArgs += $AppName
$pyiArgs += "--icon"
$pyiArgs += $IconPath
$pyiArgs += "--add-data"
$pyiArgs += "assets;assets"
$pyiArgs += "--add-data"
$pyiArgs += "tools\$Arch;tools\$Arch"

Write-Host "Running PyInstaller..."
& $VenvPython -m PyInstaller @pyiArgs $EntryPy
if ($LASTEXITCODE -ne 0) { Die "PyInstaller failed." }

# ---------- Zip + SHA ----------
$OutDir = Join-Path $DistDir $AppName
if (-not (Test-Path $OutDir)) { Die "Output folder missing: $OutDir" }

$ZipName = "$AppName-windows-$Arch-v$Version.zip"
$ZipPath = Join-Path $ReleasesDir $ZipName
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

Write-Host "Creating ZIP..."
Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $ZipPath -Force

$ShaFile = "SHA256SUMS-$AppName-v$Version.txt"
$ShaPath = Join-Path $ReleasesDir $ShaFile
$hash = (Get-FileHash -Algorithm SHA256 $ZipPath).Hash.ToLower()
"$hash  $ZipName" | Out-File -FilePath $ShaPath -Encoding ascii

# ---------- Final clean after success (keep releases/) ----------
if (-not $Keep) {
  Write-Host "Final clean: .venv-build/, build/, dist/, *.spec, __pycache__/ and PyInstaller cache"

  # Repo artifacts
  Remove-Item -Recurse -Force $VenvDir, $BuildDir, $DistDir -ErrorAction SilentlyContinue
  Remove-Item -Force (Join-Path $PSScriptRoot "*.spec") -ErrorAction SilentlyContinue

  # Python caches in repo
  Get-ChildItem -Path $PSScriptRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }

  Get-ChildItem -Path $PSScriptRoot -Recurse -File -Include "*.pyc","*.pyo" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -Force $_.FullName -ErrorAction SilentlyContinue }

  # PyInstaller caches (user profile)
  $PyInstallerCache1 = Join-Path $env:LOCALAPPDATA "pyinstaller"
  $PyInstallerCache2 = Join-Path $env:APPDATA "pyinstaller"
  if (Test-Path $PyInstallerCache1) { Remove-Item -Recurse -Force $PyInstallerCache1 -ErrorAction SilentlyContinue }
  if (Test-Path $PyInstallerCache2) { Remove-Item -Recurse -Force $PyInstallerCache2 -ErrorAction SilentlyContinue }
} else {
  Write-Host "Keep enabled: no final cleaning (venv/build/dist/spec/caches preserved)"
}

Write-Host ""
Write-Host "Build complete."
Write-Host "ZIP: $ZipPath"
Write-Host "SHA: $ShaPath"
