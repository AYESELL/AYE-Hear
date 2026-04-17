#Requires -Version 5.1
<#
.SYNOPSIS
    Local Windows packaging script for AYE Hear.

.DESCRIPTION
    Builds the PyInstaller onedir bundle and (optionally) the NSIS installer.
    Intended for local developer packaging and release validation.
    The CI pipeline uses windows-build.yml instead.

.PARAMETER BuildInstaller
    Also build the NSIS installer after the PyInstaller bundle.

.PARAMETER Clean
    Remove dist/ and build/__pycache__ before building.

.EXAMPLE
    .\tools\scripts\Build-WindowsPackage.ps1
    .\tools\scripts\Build-WindowsPackage.ps1 -BuildInstaller -Clean

.NOTES
    Prerequisites: Python 3.12, PyInstaller >= 6.9, NSIS 3.x (if -BuildInstaller)
    ADR references: ADR-0002, ADR-0006
    Task: HEAR-017
#>
[CmdletBinding()]
param(
    [switch]$BuildInstaller,
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $RepoRoot
Write-Host "Working directory: $RepoRoot"

# ─── Clean ─────────────────────────────────────────────────────────────────────
if ($Clean) {
    Write-Host "[clean] Removing dist/ and build/__pycache__..."
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    Get-ChildItem "build" -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force
    Write-Host "[clean] Done"
}

# ─── Checks ────────────────────────────────────────────────────────────────────
Write-Host "[check] Python version..."
$pythonOut = python --version 2>&1
if ($pythonOut -notmatch '3\.12') {
    Write-Error "Python 3.12.x required (found: $pythonOut). Aborting."
}
Write-Host "        $pythonOut  OK"

Write-Host "[check] PyInstaller..."
$piOut = pyinstaller --version 2>&1
if (-not $piOut) {
    Write-Error "PyInstaller not found. Run: pip install 'pyinstaller>=6.9'"
}
Write-Host "        pyinstaller $piOut  OK"

# ─── Version ───────────────────────────────────────────────────────────────────
$version = python -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d['project']['version'])"
Write-Host "[version] $version"

# ─── Whisper model staging (HEAR-062 / HEAR-094) ─────────────────────────────
# Stage the faster-whisper 'small' model from the HuggingFace cache into
# config/models/whisper/small/ so PyInstaller can bundle it for offline use.
# On CI / build agents the model must be pre-downloaded before running this script.
# HEAR-094: upgraded from 'base' (~74MB) to 'small' (~244MB) for improved German ASR quality.
$WhisperModelName   = 'small'
$WhisperStagingDir  = 'config\models\whisper\small'
$HfCacheRoot        = "$env:USERPROFILE\.cache\huggingface\hub"
$HfModelDir         = Join-Path $HfCacheRoot 'models--Systran--faster-whisper-small'

if (-not (Test-Path (Join-Path $WhisperStagingDir 'model.bin'))) {
    if (Test-Path $HfModelDir) {
        # Find the latest snapshot hash directory
        $snapshotRoot = Join-Path $HfModelDir 'snapshots'
        $snapshots = Get-ChildItem $snapshotRoot -Directory -ErrorAction SilentlyContinue
        if ($snapshots) {
            $latestSnap = ($snapshots | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
            Write-Host "[model] Staging Whisper '$WhisperModelName' from $latestSnap ..."
            if (-not (Test-Path $WhisperStagingDir)) {
                New-Item -ItemType Directory -Path $WhisperStagingDir -Force | Out-Null
            }
            # Copy required CTranslate2 model files, resolving symlinks to actual blobs
            foreach ($fname in @('config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt')) {
                $src = Join-Path $latestSnap $fname
                $dst = Join-Path $WhisperStagingDir $fname
                if (Test-Path $src) {
                    $resolved = (Get-Item $src -Force).Target
                    if ($resolved) {
                        # Symlink → resolve to blob
                        $blobPath = Join-Path (Join-Path $HfModelDir 'blobs') (Split-Path $resolved -Leaf)
                        if (-not (Test-Path $blobPath)) { $blobPath = $resolved }
                        Copy-Item -Path $blobPath -Destination $dst -Force
                    } else {
                        Copy-Item -Path $src -Destination $dst -Force
                    }
                    $sizeMB = [math]::Round((Get-Item $dst).Length / 1MB, 1)
                    Write-Host "        $fname  ($sizeMB MB)"
                } else {
                    Write-Warning "        $fname not found in snapshot — skipping"
                }
            }
            Write-Host "[model] Whisper model staged to $WhisperStagingDir  OK"
        } else {
            Write-Warning "[model] No snapshot found in $snapshotRoot — Whisper model will not be bundled."
            Write-Warning "        Run: python -c 'from faster_whisper import WhisperModel; WhisperModel(\"small\")' to pre-download."
        }
    } else {
        Write-Warning "[model] HuggingFace cache not found at $HfModelDir — Whisper model will not be bundled."
        Write-Warning "        Run: python -c 'from faster_whisper import WhisperModel; WhisperModel(\"small\")' to pre-download."
    }
} else {
    $modelSize = [math]::Round((Get-Item (Join-Path $WhisperStagingDir 'model.bin')).Length / 1MB, 1)
    Write-Host "[model] Whisper '$WhisperModelName' already staged ($modelSize MB)  OK"
}

# ─── PyInstaller spec ─────────────────────────────────────────────────────────
if (-not (Test-Path "build")) { New-Item -ItemType Directory -Path "build" | Out-Null }
$specPath = "build\aye-hear.spec"

if (-not (Test-Path $specPath)) {
    Write-Host "[spec] Generating $specPath ..."
    $spec = @"
# -*- mode: python ; coding: utf-8 -*-
import os as _os
block_cipher = None
_whisper_model_dir = _os.path.join(_os.path.dirname(_os.path.abspath(SPEC)), '..', 'config', 'models', 'whisper', 'base')
_whisper_datas = [(_whisper_model_dir, 'models/whisper/base')] if _os.path.isfile(_os.path.join(_whisper_model_dir, 'model.bin')) else []
a = Analysis(
    ['../src/ayehear/__main__.py'],
    pathex=['../src'],
    binaries=[],
    datas=[
        ('../config/', 'config'),
        ('../src/ayehear/storage/migrations/', 'ayehear/storage/migrations'),
    ] + _whisper_datas,
    # NOTE: faster_whisper Python code is auto-detected via PYZ.
    # ctranslate2 DLLs and tokenizers are included via their PyInstaller hooks.
    # Whisper model files are staged via Build-WindowsPackage.ps1 (HEAR-062).
    hiddenimports=[
        'ayehear.storage',
        'ayehear.storage.orm',
        'ayehear.storage.migrations',
        'psycopg',
        'psycopg.adapt',
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pyannote.audio', 'silero_vad', 'ollama'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='AyeHear',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    uac_admin=False,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AyeHear',
)
"@
    Set-Content -Path $specPath -Value $spec -Encoding UTF8
    Write-Host "[spec] Written to $specPath"
}
else {
    Write-Host "[spec] Using existing $specPath"
}

# ─── Build ─────────────────────────────────────────────────────────────────────
Write-Host "[build] Running PyInstaller..."
pyinstaller $specPath --noconfirm --clean
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
}

# Write version file into bundle
Set-Content -Path "dist\AyeHear\aye_hear_version.txt" -Value $version -Encoding UTF8
Write-Host "[build] Version $version written to bundle"

# ─── Verify bundle ─────────────────────────────────────────────────────────────
$exePath = "dist\AyeHear\AyeHear.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "Expected $exePath not found — PyInstaller output missing"
}
Write-Host "[verify] $exePath  OK"

# ─── Inno Setup installer ──────────────────────────────────────────────────────
if ($BuildInstaller) {
    $issScript = "build\installer\ayehear-installer.iss"
    if (-not (Test-Path $issScript)) {
        Write-Error "[inno] Required installer script missing: $issScript"
    }
    else {
        # Locate iscc.exe: PATH → standard install locations
        $iscc = Get-Command iscc -ErrorAction SilentlyContinue
        if (-not $iscc) {
            $candidates = @(
                "C:\Program Files (x86)\Inno Setup 6\iscc.exe",
                "C:\Program Files\Inno Setup 6\iscc.exe",
                "$env:LOCALAPPDATA\Programs\Inno Setup 6\iscc.exe"
            )
            foreach ($c in $candidates) {
                if (Test-Path $c) { $iscc = [PSCustomObject]@{ Source = $c }; break }
            }
        }
        if (-not $iscc) {
            Write-Error "[inno] iscc.exe not found. Install Inno Setup 6: winget install JRSoftware.InnoSetup"
        }

        $bundleDir = (Resolve-Path "dist\AyeHear").Path
        $issScriptPath = (Resolve-Path $issScript).Path
        Write-Host "[inno] Building installer with Inno Setup 6..."
        & $iscc.Source `
            "/DProductVersion=$version" `
            "/DDistDir=$bundleDir" `
            $issScriptPath
        if ($LASTEXITCODE -ne 0) {
            Write-Error "[inno] Inno Setup failed with exit code $LASTEXITCODE"
        }
        $installerPath = "dist\AyeHear-Setup-$version.exe"
        if (Test-Path $installerPath) {
            Write-Host "[inno] Installer created: $installerPath"
        }
        else {
            Write-Warning "[inno] Expected installer not found at $installerPath"
        }
    }
}

Write-Host ""
Write-Host "=========================================="
Write-Host " AYE Hear Windows Package  v$version"
Write-Host " Bundle: dist\AyeHear\"
if ($BuildInstaller) {
    Write-Host " Installer: dist\AyeHear-Setup-$version.exe"
}
Write-Host "=========================================="
