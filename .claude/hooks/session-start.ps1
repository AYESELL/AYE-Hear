<#
    SessionStart-Hook (AYE Hear): gibt Claude beim Start den Task-Kontext des
    Projekts `hear` mit. Faellt der Change Service aus, nur ein Hinweis.
#>
$ErrorActionPreference = 'SilentlyContinue'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$wrapper = Join-Path $repoRoot '.claude\tools\task.ps1'

Write-Output "## Task-CLI-Kontext (Projekt hear)"
Write-Output "Task-CLI ist fuehrend. Aufruf nur ueber den Wrapper:"
Write-Output '  pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File G:/Repo/aye-hear/.claude/tools/task.ps1 "<Befehl>"'
Write-Output "Gemeinsamer Ablauf: Skill ayehear-task-execution."
$status = Join-Path $repoRoot 'docs\STATUS.md'
if (Test-Path $status) { Write-Output ""; Get-Content $status -Raw -Encoding utf8 | Write-Output }

# Keine eigene URL-Annahme: die Task-CLI ermittelt den Change Service selbst
# (TASK_SERVICE_BASE_URL, platform-tools/.env oder ~/.task-cli/config.json).
$probe = & pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $wrapper "Get-Task -Project hear -Status IN_PROGRESS | Select-Object -First 1" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Output "WARNUNG: Task-CLI nicht erreichbar oder Fehler: $((($probe | Out-String).Trim() -split "`n")[0])"
    exit 0
}

foreach ($status in @('IN_PROGRESS', 'REVIEW', 'BLOCKED')) {
    $out = & pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $wrapper "Get-Task -Project hear -Status $status | Select-Object -First 15" 2>$null
    $text = ($out | Out-String).Trim()
    if ($text -and $text -notmatch '^\[task\.ps1\]') {
        Write-Output ""
        Write-Output "### Tasks mit Status $status"
        Write-Output $text
    }
}
exit 0
