<#
    PreToolUse-Hook (Matcher PowerShell, PLAT-3535, Plan 2.1, Security S-12/S-16):
    Ein PowerShell-Aufruf ist EIN einfacher Befehl. Der Befehl wird mit dem PowerShell-Parser (ParseInput) geprueft;
    abgelehnt werden (jede Ablehnung nennt Regel-ID, Regel und den richtigen Weg):
      PSG-0 Parse-Fehler            PSG-1 mehr als ein Statement (Semikolon, Zeilenumbruch)
      PSG-2 Pipeline (|)            PSG-3 && / || (und Hintergrund-&)
      PSG-4 Skriptblock { }         PSG-5 Umleitung (>, >>, 2>&1)
      PSG-6 Unterausdruck $(...) oder (...) mit Befehl darin
      PSG-7 Kontrollfluss oder Zuweisung statt eines Befehls (foreach, if, $x = ...)
    Text in Anfuehrungszeichen (auch mehrzeilig, z. B. git commit -m) ist ein Argument und bleibt erlaubt.

    Zweite Stufe im selben Prozess: besteht der Befehl die Pruefung, laeuft task-call-guard.ps1 (Task-CLI-Aufrufe,
    1000-Byte-Grenze) mit derselben Eingabe (-InputJson); dessen Ausgabe wird unveraendert weitergereicht.
    Der DB-Guard ist ein eigener Hook-Eintrag und damit ein eigener Prozess; dieser Hook schreibt die Eingabe nie
    um (keine Aenderung des Werkzeugaufrufs, S-12).

    Fail-closed: interner Fehler (kein JSON, Parser fehlt, Ausnahme) = exit 2 mit kurzer Meldung auf stderr.
    Kein Protokoll, der Rohbefehl steht nie im Ausgabetext (S-16).
#>
$ErrorActionPreference = 'Stop'
try {
    $stdin = New-Object System.IO.MemoryStream
    [Console]::OpenStandardInput().CopyTo($stdin)
    $raw = (New-Object System.Text.UTF8Encoding($false, $true)).GetString($stdin.ToArray()).TrimStart([char]0xFEFF)
    $data = $raw | ConvertFrom-Json
    if ($data -isnot [System.Management.Automation.PSCustomObject]) { throw 'Hook-Eingabe ist kein JSON-Objekt' }
    if ($data.tool_name -isnot [string]) { throw 'tool_name fehlt' }
    if ($data.tool_name -cne 'PowerShell') { exit 0 }
    if ($data.tool_input -isnot [System.Management.Automation.PSCustomObject]) { throw 'tool_input fehlt' }
    $cmd = $data.tool_input.command
    if ($cmd -isnot [string]) { throw 'command fehlt oder ist kein String' }

    $tokens = $null
    $errs = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($cmd, [ref]$tokens, [ref]$errs)
    if ($null -eq $ast) { throw 'Parser lieferte keinen Syntaxbaum' }

    $hits = [ordered]@{}
    function Add-Hit([string]$Id, [string]$Text) { if (-not $hits.Contains($Id)) { $hits[$Id] = $Text } }
    function Find-All($Node, [Type]$Type) {
        return @($Node.FindAll([Func[System.Management.Automation.Language.Ast, bool]] { param($a) $Type.IsInstanceOfType($a) }, $true))
    }

    if ($errs -and $errs.Count -gt 0) {
        Add-Hit 'PSG-0' 'Parse-Fehler: der Befehl ist kein gueltiges PowerShell (z. B. ungeschlossene Anfuehrungszeichen, Klammern oder Here-String). Typische Ursache: ein Apostroph in einem einfach quotierten Text; dann den Text in doppelte Anfuehrungszeichen setzen oder den Apostroph vermeiden.'
    } else {
        $statements = New-Object System.Collections.Generic.List[object]
        foreach ($blk in @($ast.BeginBlock, $ast.ProcessBlock, $ast.EndBlock, $ast.DynamicParamBlock)) {
            if ($blk) { foreach ($s in $blk.Statements) { $statements.Add($s) } }
        }
        if ($ast.ParamBlock) { Add-Hit 'PSG-7' 'param-Block statt eines Befehls' }
        if ($statements.Count -gt 1) { Add-Hit 'PSG-1' 'mehr als ein Statement (Semikolon oder Zeilenumbruch zwischen Befehlen)' }
        foreach ($s in $statements) {
            if ($s -is [System.Management.Automation.Language.PipelineChainAst]) { continue }
            if ($s -isnot [System.Management.Automation.Language.PipelineAst]) {
                Add-Hit 'PSG-7' 'Kontrollfluss oder Zuweisung (foreach, if, while, $x = ...) statt eines einzelnen Befehls'
            }
        }
        foreach ($p in (Find-All $ast ([System.Management.Automation.Language.PipelineAst]))) {
            if ($p.PipelineElements.Count -gt 1) { Add-Hit 'PSG-2' 'Pipeline mit mehr als einem Element (|)' }
            if ($p.Background) { Add-Hit 'PSG-3' 'Hintergrundstart mit &' }
        }
        if ((Find-All $ast ([System.Management.Automation.Language.PipelineChainAst])).Count -gt 0) {
            Add-Hit 'PSG-3' 'Verkettung mit && oder ||'
        }
        if ((Find-All $ast ([System.Management.Automation.Language.ScriptBlockExpressionAst])).Count -gt 0) {
            Add-Hit 'PSG-4' 'Skriptblock { } (z. B. ForEach-Object, Where-Object, & { })'
        }
        if ((Find-All $ast ([System.Management.Automation.Language.RedirectionAst])).Count -gt 0) {
            Add-Hit 'PSG-5' 'Umleitung (>, >>, 2>&1)'
        }
        $nested = @(Find-All $ast ([System.Management.Automation.Language.SubExpressionAst])) +
                  @(Find-All $ast ([System.Management.Automation.Language.ParenExpressionAst]))
        foreach ($n in $nested) {
            if ((Find-All $n ([System.Management.Automation.Language.CommandAst])).Count -gt 0) {
                Add-Hit 'PSG-6' 'Befehl innerhalb von $(...) oder (...) (verschachtelter Aufruf)'
                break
            }
        }
    }

    if ($hits.Count -gt 0) {
        $list = ($hits.Keys | ForEach-Object { "$_ ($($hits[$_]))" }) -join '; '
        $reason = "[powershell-ast-guard] Abgelehnt: $list. " +
            "Regel: Ein PowerShell-Aufruf ist ein einfacher Befehl (ein Statement, keine Pipeline, kein && oder ||, kein Skriptblock, keine Umleitung). " +
            "Richtiger Weg: ein einfacher Befehl pro Aufruf; bei mehreren Schritten mehrere Aufrufe nacheinander, Ausgaben direkt lesen " +
            "(Dateien mit Read, Grep, Glob statt Pipe-Filtern). Mehrzeiliger Text als Argument in Anfuehrungszeichen ist erlaubt (z. B. git commit -m). " +
            "Regeln: Skill Abschnitt 1a (Werkzeuge und Befehle)."
        @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } } |
            ConvertTo-Json -Compress -Depth 4 | Write-Output
        exit 0
    }

    # Zweite Stufe im selben Prozess: bestehende task-call-guard-Pruefungen
    $stage2 = Join-Path $PSScriptRoot 'task-call-guard.ps1'
    if (-not (Test-Path -LiteralPath $stage2)) { throw 'task-call-guard.ps1 fehlt neben dem Hook' }
    $out = & $stage2 -InputJson $raw
    if ($out) { $out | Write-Output }
    exit 0
} catch {
    [Console]::Error.WriteLine('[powershell-ast-guard] interner Fehler, fail-closed (exit 2): ' + ($_.Exception.Message -replace '[^\x20-\x7E]', '?'))
    exit 2
}
