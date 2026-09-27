<#
.SYNOPSIS
    Claude-Code-Wrapper fuer Task-CLI und agent-memory (platform-tools).

.DESCRIPTION
    Claude Code startet fuer jeden Befehl eine neue Shell. Dieser Wrapper laedt
    task-cli und agent-memory, prueft, dass nur Befehle dieser beiden Module
    aufgerufen werden, und fuehrt den Befehl nicht-interaktiv aus.

.EXAMPLE
    pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File G:/Repo/aye-hear/.claude/tools/task.ps1 "Get-Task -Project hear -Status OPEN"

.NOTES
    Pfad zu platform-tools: $env:PLATFORM_TOOLS_ROOT, sonst ../platform-tools neben dem Repo.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Command
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$platformRoot = if ($env:PLATFORM_TOOLS_ROOT) { $env:PLATFORM_TOOLS_ROOT } else { Join-Path (Split-Path $repoRoot -Parent) 'platform-tools' }

$taskCli   = Join-Path $platformRoot 'tools\task-cli\task-cli.psd1'
$agentMem  = Join-Path $platformRoot 'tools\agent-memory\agent-memory.psd1'

foreach ($m in @($taskCli, $agentMem)) {
    if (-not (Test-Path $m)) {
        Write-Output "[task.ps1] FEHLER: Modul nicht gefunden: $m (PLATFORM_TOOLS_ROOT setzen?)"
        exit 2
    }
}

Import-Module $taskCli -Force -WarningAction SilentlyContinue
Import-Module $agentMem -Force -WarningAction SilentlyContinue

# Nur exportierte Befehle der beiden Module zulassen (erstes Token jeder Pipeline-Stufe/Anweisung)
$allowed = @()
$allowed += (Get-Module task-cli).ExportedCommands.Keys
$allowed += (Get-Module agent-memory).ExportedCommands.Keys
# PLAT-3277: ForEach-Object entfernt - erlaubt "-MemberName"/positional Member-Aufruf
# (z. B. "$x | ForEach-Object InvokeScript") ohne dass dabei ein InvokeMemberExpressionAst
# entsteht (der Aufruf laeuft ueber Reflection im Cmdlet, nicht im Parser sichtbar).
$allowedHelpers = @('Select-Object','Where-Object','Sort-Object','Format-Table','Format-List','ConvertTo-Json','Measure-Object','Out-String')

$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput($Command, [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {
    Write-Output "[task.ps1] FEHLER: Befehl nicht parsebar: $($errors[0].Message)"
    exit 2
}
$cmds = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
foreach ($c in $cmds) {
    $name = $c.GetCommandName()
    if (-not $name -or (($allowed -notcontains $name) -and ($allowedHelpers -notcontains $name))) {
        Write-Output "[task.ps1] ABGELEHNT: '$name' ist kein Task-CLI/agent-memory-Befehl."
        Write-Output "Erlaubt: $((($allowed | Sort-Object) -join ', '))"
        exit 2
    }
}

# PLAT-3277 (NO-GO-Nacharbeit zu PLAT-3273): Eine Deny-Liste gefaehrlicher
# Knotentypen bleibt bei PowerShell strukturell unvollstaendig - das Security-Review
# zu PLAT-3273 fand zwei weitere, real ausnutzbare Vektoren, die keinen der damals
# verbotenen Knoten erzeugen: "$obj | ForEach-Object -MemberName Foo" ruft eine
# Methode ueber einen String-Parameter des Cmdlets auf (kein InvokeMemberExpressionAst -
# deshalb zusaetzlich oben ForEach-Object aus $allowedHelpers entfernt), und
# "using module <Pfad>"/"using namespace <NS>" fuehrt Modulcode beim Import aus, ohne
# ueberhaupt einen CommandAst oder einen der bisherigen Deny-Knoten zu sein.
#
# Architekturwechsel: statt neuer Deny-Eintraege wird jetzt der GESAMTE Ast-Baum
# (jedes Argument, jeder Scriptblock, jedes Statement) gegen eine Allow-Liste
# harmloser Knotentypen geprueft; jeder Knoten, dessen Typ nicht in dieser Liste
# steht, fuehrt zur Ablehnung. Das schliesst automatisch auch Konstrukte wie
# UsingStatementAst, TypeDefinitionAst, FunctionDefinitionAst, FileRedirectionAst,
# PipelineChainAst und AssignmentStatementAst mit ein, ohne dass sie einzeln
# benannt werden muessen - neue PowerShell-Sprachkonstrukte sind damit standardmaessig
# verboten statt standardmaessig erlaubt.
#
# Erlaubt bleiben nur: der aeussere Skript-/Pipeline-/Kommando-Aufbau, Konstanten
# (Strings, Zahlen - keine interpolierten Strings), Variablen ($_ etc.), ein
# Scriptblock-Argument (fuer Where-Object/ForEach-Filter), ein Vergleichsoperator
# (-eq, -and, ...) und einfacher, nicht-aufrufender Property-Zugriff wie
# "$_.status" (MemberExpressionAst, exakter Typ - die Subklasse
# InvokeMemberExpressionAst fuer Methodenaufrufe bleibt dadurch verboten).
$allowedNodeTypes = @(
    [System.Management.Automation.Language.ScriptBlockAst]
    [System.Management.Automation.Language.NamedBlockAst]
    [System.Management.Automation.Language.PipelineAst]
    [System.Management.Automation.Language.CommandAst]
    [System.Management.Automation.Language.CommandParameterAst]
    [System.Management.Automation.Language.CommandExpressionAst]
    [System.Management.Automation.Language.ConstantExpressionAst]  # deckt StringConstantExpressionAst (Subklasse) mit ab
    [System.Management.Automation.Language.VariableExpressionAst]
    [System.Management.Automation.Language.ScriptBlockExpressionAst]
    [System.Management.Automation.Language.BinaryExpressionAst]
)
foreach ($node in $ast.FindAll({ $true }, $true)) {
    $isAllowed = $false
    foreach ($t in $allowedNodeTypes) {
        if ($node -is $t) { $isAllowed = $true; break }
    }
    if (-not $isAllowed -and $node.GetType() -eq [System.Management.Automation.Language.MemberExpressionAst]) {
        $isAllowed = $true
    }
    if (-not $isAllowed) {
        Write-Output "[task.ps1] ABGELEHNT: Ausdruck '$($node.Extent.Text)' ($($node.GetType().Name)) ist nicht erlaubt."
        Write-Output "Erlaubt sind nur Task-CLI/agent-memory-Aufrufe mit Konstanten, Variablen und einfachen Property-Zugriffen (z. B. `$_.status)."
        exit 2
    }
}

try {
    $result = Invoke-Expression $Command
    if ($null -ne $result) { $result | Out-String -Width 240 | Write-Output }
    exit 0
}
catch {
    Write-Output "[task.ps1] FEHLER: $($_.Exception.Message)"
    if ($_.Exception.Message -match 'Read-Host|NonInteractive|interactive') {
        Write-Output "Hinweis: Befehl wollte interaktiv nachfragen. -Force verwenden bzw. -InteractiveApms weglassen."
    }
    exit 1
}
