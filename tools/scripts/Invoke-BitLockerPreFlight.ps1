<#
.SYNOPSIS
    AYE Hear BitLocker pre-flight check — captures manage-bde -status evidence for QA-DP-01.

.DESCRIPTION
    Runs manage-bde -status against the specified drive letter and writes a timestamped
    evidence file to <RepoRoot>\deployment-evidence\. Required before GA release (HEAR-035).

    The script exits with code 0 when BitLocker is Protection On for the target volume.
    Any other state (Protection Off, Not applicable, manage-bde not found) exits with code 1.

    Evidence is saved to:
        deployment-evidence\bitlocker-evidence-<YYYYMMDD-HHmmss>.txt

.PARAMETER Drive
    Drive letter to check (default: C). Do not include the colon.

.PARAMETER OutDir
    Directory to write the evidence file to (default: <script root>\..\..\deployment-evidence).

.EXAMPLE
    .\Invoke-BitLockerPreFlight.ps1

.EXAMPLE
    .\Invoke-BitLockerPreFlight.ps1 -Drive D -OutDir "C:\AYEHear\deployment-evidence"

.NOTES
    Owner:  AYEHEAR_DEVOPS
    Task:   HEAR-035
    ADR:    ADR-0009 (Data Protection & Encryption-at-Rest)
    QA gate: QA-DP-01
#>

[CmdletBinding()]
param (
    [string] $Drive  = "C",
    [string] $OutDir = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Resolve output directory
# ---------------------------------------------------------------------------
if (-not $OutDir) {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot ".." "..")).Path
    $OutDir   = Join-Path $repoRoot "deployment-evidence"
}

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$timestamp    = Get-Date -Format "yyyyMMdd-HHmmss"
$evidenceFile = Join-Path $OutDir "bitlocker-evidence-$timestamp.txt"
$drivePath    = "${Drive}:"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
$header = @"
===================================================================
AYE Hear — BitLocker Pre-Flight Evidence (QA-DP-01)
===================================================================
Date/Time  : $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Drive      : $drivePath
Host       : $env:COMPUTERNAME
User       : $env:USERNAME
ADR        : ADR-0009
Task       : HEAR-035
===================================================================

"@

Write-Host $header

# ---------------------------------------------------------------------------
# Run manage-bde -status
# ---------------------------------------------------------------------------
$manageBde = Get-Command "manage-bde.exe" -ErrorAction SilentlyContinue
if (-not $manageBde) {
    $msg = "[FAIL] manage-bde.exe not found. Windows Pro/Enterprise required for BitLocker."
    Write-Warning $msg
    "$header$msg`n" | Out-File -FilePath $evidenceFile -Encoding utf8
    Write-Host "Evidence written to: $evidenceFile"
    exit 1
}

Write-Host "Running: manage-bde -status $drivePath"
Write-Host ""

try {
    $bdeOutput = & manage-bde.exe -status $drivePath 2>&1
}
catch {
    $msg = "[FAIL] manage-bde -status failed: $_"
    Write-Warning $msg
    "$header$msg`n" | Out-File -FilePath $evidenceFile -Encoding utf8
    Write-Host "Evidence written to: $evidenceFile"
    exit 1
}

$bdeText = $bdeOutput -join "`n"

# ---------------------------------------------------------------------------
# Parse protection status
# ---------------------------------------------------------------------------
# manage-bde output contains a line like:
#   Protection Status:     Protection On
#   Protection Status:     Protection Off
$protectionLine  = $bdeOutput | Where-Object { $_ -match "Protection Status" } | Select-Object -First 1
$isProtected     = $false

if ($protectionLine -and $protectionLine -match "Protection On") {
    $isProtected = $true
}

# ---------------------------------------------------------------------------
# Build evidence document
# ---------------------------------------------------------------------------
$verdict = if ($isProtected) { "[PASS]" } else { "[FAIL]" }
$verdictLine = "$verdict  Drive $drivePath — BitLocker Protection: $(if ($isProtected) { 'On' } else { 'Off / Not configured' })"

$evidenceContent = @"
$header
-- manage-bde -status $drivePath --

$bdeText

-------------------------------------------------------------------
VERDICT: $verdictLine
-------------------------------------------------------------------
"@

$evidenceContent | Out-File -FilePath $evidenceFile -Encoding utf8

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
Write-Host $bdeText
Write-Host ""
Write-Host "-------------------------------------------------------------------"
Write-Host $verdictLine
Write-Host "-------------------------------------------------------------------"
Write-Host ""
Write-Host "Evidence written to : $evidenceFile"
Write-Host ""

if (-not $isProtected) {
    Write-Warning @"
BitLocker is NOT active on drive $drivePath.
Per ADR-0009 and QA-DP-01, BitLocker (or an approved equivalent) is required
before GA release.  Options:
  1. Enable BitLocker on this volume.
  2. Document an AYEHEAR_SECURITY-approved alternative encryption control.
"@
    exit 1
}

Write-Host "QA-DP-01: BitLocker evidence captured. Pre-flight PASSED." -ForegroundColor Green
exit 0
