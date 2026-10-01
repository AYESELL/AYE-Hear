<#
    Stop-Hook (AYEChology): Wurden Dateien geaendert (ausser Rollen-Gedaechtnis),
    muss ein Task in der Task-CLI aktualisiert worden sein. Sonst wird das Beenden
    einmal blockiert. Heuristik: Textscan des Transkripts inkl. Subagenten.
#>
$ErrorActionPreference = 'SilentlyContinue'
$raw = [Console]::In.ReadToEnd()
try { $data = $raw | ConvertFrom-Json } catch { exit 0 }
if ($data.stop_hook_active) { exit 0 }

$transcript = $data.transcript_path
if (-not $transcript -or -not (Test-Path $transcript)) { exit 0 }

$files = @($transcript)
$subDir = Join-Path ([IO.Path]::ChangeExtension($transcript, $null).TrimEnd('.')) 'subagents'
if (Test-Path $subDir) { $files += (Get-ChildItem $subDir -Filter *.jsonl -Recurse | ForEach-Object FullName) }
$content = ($files | ForEach-Object { Get-Content $_ -Raw }) -join "`n"

# Aenderungen ausser am Rollen-Gedaechtnis
$edits = [regex]::Matches($content, '"name"\s*:\s*"(Edit|Write|MultiEdit|NotebookEdit)"[^\n]{0,600}?"file_path"\s*:\s*"([^"]+)"')
$changed = @($edits | ForEach-Object { $_.Groups[2].Value } | Where-Object { $_ -notmatch 'agent-memory' })
if ($changed.Count -eq 0) { exit 0 }

$taskUpd = $content -match 'task\.ps1[^\n]{0,400}(Start-Task|Set-Task|Complete-Task|New-Task|New-FollowUpTask)'
if (-not $taskUpd) {
    $reason = "Es wurden Dateien geaendert, aber kein Task in der Task-CLI aktualisiert. " +
              "Bitte per Wrapper nachtragen (Start-Task / Set-Task -ImplementationNotesFile <Datei> (haengt an) mit Pruefnachweis / Complete-Task) " +
              "oder kurz begruenden, warum diese Aenderung keinen Task braucht."
    @{ decision = 'block'; reason = $reason } | ConvertTo-Json -Compress | Write-Output
}
exit 0
