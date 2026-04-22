#Requires -Version 5.1
<#!
.SYNOPSIS
    Executes the HEAR-137 seed-only ASR benchmark dry run.

.DESCRIPTION
    Runs the 4-candidate benchmark against the seeded HEAR-136 dataset manifest.
    This is an engineering smoke test only. It validates model IDs, local model
    resolution, transcript artifact naming, and JSON report generation.
    It is explicitly non-authoritative and must not be used to change the
    packaged default ASR model.

.PARAMETER Dataset
    Dataset manifest path. Defaults to the seeded HEAR-136 manifest.

.PARAMETER OutputDir
    Directory where benchmark artifacts and the JSON report are written.

.PARAMETER PythonExe
    Python interpreter to use. Defaults to .venv\Scripts\python.exe when present.

.PARAMETER ComputeType
    faster-whisper compute type. Defaults to int8.

.PARAMETER BeamSize
    Beam size used for all model runs. Defaults to 3.

.PARAMETER Language
    Language hint for Whisper. Defaults to de.

.EXAMPLE
    .\tools\scripts\Invoke-HEAR-137-ASRBenchmarkDryRun.ps1
#>
[CmdletBinding()]
param(
    [string]$Dataset = "benchmarks\asr-evaluation-dataset\manifest.json",
    [string]$OutputDir = "deployment-evidence\hear-137\seed-dry-run",
    [string]$PythonExe = ".venv\Scripts\python.exe",
    [string]$ComputeType = "int8",
    [int]$BeamSize = 3,
    [string]$Language = "de"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $RepoRoot

$datasetPath = Join-Path $RepoRoot $Dataset
if (-not (Test-Path $datasetPath)) {
    throw "Dataset manifest not found: $datasetPath"
}

$outputPath = Join-Path $RepoRoot $OutputDir
if (-not (Test-Path $outputPath)) {
    New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
}

$pythonPath = Join-Path $RepoRoot $PythonExe
if (-not (Test-Path $pythonPath)) {
    $pythonPath = $PythonExe
}

$manifest = Get-Content $datasetPath -Raw -Encoding UTF8 | ConvertFrom-Json
$sampleCount = @($manifest.samples).Count
$realSampleCount = @(
    @($manifest.samples) | Where-Object {
        $_.tags -and (@($_.tags) -contains 'real-meeting')
    }
).Count

Write-Host "[hear-137] HEAR-137 dry run starting ..."
Write-Host "[hear-137] Dataset: $datasetPath"
Write-Host "[hear-137] Samples: $sampleCount total / $realSampleCount tagged real-meeting"
Write-Warning "[hear-137] This run is NON-AUTHORITATIVE. Do not change packaged defaults based on seed-only results."

$benchmarkScript = Join-Path $RepoRoot 'tools\scripts\benchmark_whisper_models.py'
& $pythonPath $benchmarkScript `
    --dataset $datasetPath `
    --output-dir $outputPath `
    --model small `
    --model large-v3-turbo `
    --model TheChola/whisper-large-v3-turbo-german-faster-whisper `
    --model distil-whisper/distil-large-v3 `
    --compute-type $ComputeType `
    --beam-size $BeamSize `
    --language $Language

if ($LASTEXITCODE -ne 0) {
    throw "HEAR-137 dry run failed with exit code $LASTEXITCODE"
}

$notePath = Join-Path $outputPath 'dry-run-scope.txt'
@(
    'HEAR-137 seed dry run'
    'Scope: engineering smoke test only'
    'Authority: non-authoritative'
    'Rule: do not change packaged default based on this run alone'
    "Dataset=$Dataset"
    "SampleCount=$sampleCount"
    "RealMeetingSampleCount=$realSampleCount"
) | Set-Content -Path $notePath -Encoding UTF8

Write-Host "[hear-137] Dry run finished. Artifacts: $outputPath"
