#Requires -Version 5.1
<#!
.SYNOPSIS
    Executes the HEAR-113 Whisper small vs base benchmark on Windows.

.DESCRIPTION
    Generates a deterministic offline WAV sample from a reference transcript using
    Windows SpeechSynthesizer, then benchmarks Whisper small and base on CPU using
    the repo-local benchmark_whisper_models.py helper.

.PARAMETER ReferenceTranscript
    Path to the reference transcript used both as TTS source and WER baseline.

.PARAMETER OutputDir
    Directory where audio, transcripts and JSON results are written.

.PARAMETER VoiceName
    Optional installed Windows voice. Defaults to Microsoft Hedda Desktop when available.

.PARAMETER PythonExe
    Python interpreter to use. Defaults to .venv\Scripts\python.exe when present.

.EXAMPLE
    .\tools\scripts\Invoke-HEAR-113-ASRBenchmark.ps1
#>
[CmdletBinding()]
param(
    [string]$ReferenceTranscript = "exports\test-baseline-transcript-HEAR-103.txt",
    [string]$OutputDir = "deployment-evidence\hear-113\2026-04-19",
    [string]$VoiceName = "Microsoft Hedda Desktop",
    [string]$PythonExe = ".venv\Scripts\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $RepoRoot

$referencePath = Join-Path $RepoRoot $ReferenceTranscript
if (-not (Test-Path $referencePath)) {
    throw "Reference transcript not found: $referencePath"
}

$outputPath = Join-Path $RepoRoot $OutputDir
if (-not (Test-Path $outputPath)) {
    New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
}

$pythonPath = Join-Path $RepoRoot $PythonExe
if (-not (Test-Path $pythonPath)) {
    $pythonPath = $PythonExe
}

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $synth.GetInstalledVoices() |
    ForEach-Object { $_.VoiceInfo } |
    Where-Object { $_.Name -eq $VoiceName } |
    Select-Object -First 1
if (-not $voice) {
    $voice = $synth.GetInstalledVoices() |
        ForEach-Object { $_.VoiceInfo } |
        Where-Object { $_.Culture.Name -eq 'de-DE' } |
        Select-Object -First 1
}
if (-not $voice) {
    throw "No German TTS voice installed. Cannot create deterministic benchmark audio."
}

$synth.SelectVoice($voice.Name)
$synth.Rate = 0

$referenceText = Get-Content $referencePath -Raw -Encoding UTF8
$audioPath = Join-Path $outputPath 'hear-113-reference.wav'
$transcriptForSpeech = ($referenceText -split "`r?`n") -join '. '

Write-Host "[hear-113] Generating reference audio with voice '$($voice.Name)' ..."
$synth.SetOutputToWaveFile($audioPath)
$synth.Speak($transcriptForSpeech)
$synth.SetOutputToNull()

$hardwarePath = Join-Path $outputPath 'hardware-profile.txt'
Get-ComputerInfo |
    Select-Object CsName, WindowsVersion, OsName, OsVersion, CsProcessors, CsTotalPhysicalMemory |
    Format-List |
    Out-String |
    Set-Content -Path $hardwarePath -Encoding UTF8

$voicePath = Join-Path $outputPath 'tts-voice.txt'
@(
    "VoiceName=$($voice.Name)"
    "Culture=$($voice.Culture.Name)"
    "Gender=$($voice.Gender)"
    "Age=$($voice.Age)"
) | Set-Content -Path $voicePath -Encoding UTF8

$benchmarkScript = Join-Path $RepoRoot 'tools\scripts\benchmark_whisper_models.py'
Write-Host "[hear-113] Running Whisper benchmark via $pythonPath ..."
& $pythonPath $benchmarkScript `
    --audio $audioPath `
    --reference $referencePath `
    --output-dir $outputPath `
    --model small `
    --model base `
    --compute-type int8 `
    --beam-size 3 `
    --language de

if ($LASTEXITCODE -ne 0) {
    throw "Benchmark failed with exit code $LASTEXITCODE"
}

Write-Host "[hear-113] Benchmark finished. Artifacts: $outputPath"