<#
    PreToolUse-Hook (Bash, PowerShell): Weist task.ps1-Aufrufe ab, die sonst ein Berechtigungs-Popup
    ausloesen oder vom Wrapper abgelehnt wuerden, und zwar VOR dem Popup und mit Anleitung (PLAT-3446).
    Abgelehnt werden (nur wenn der Befehl ein task.ps1-Aufruf ist):
      - Pipe, Semikolon, &&, Zeilenumbruch, Skriptblock-Klammern (foreach) ausserhalb von Anfuehrungszeichen
      - Get-Task -Status mit Liste oder unzulaessigem Wert; Set-Task -Status ausserhalb des ValidateSet
      - override_reason / -OverrideReason irgendwo im Aufruf (PLAT-3738, Security S-3 Teil 1; menschlicher Weg des Services)
      - im PowerShell-Werkzeug: Gesamtbefehl ueber 1000 Byte (UTF-8, Umlaute zaehlen doppelt)
    Ersetzt nicht den Wrapper (Allowlist im Wrapper bleibt). Keine Treffer bei anderen Befehlen, auch wenn
    "task.ps1" nur als Text vorkommt. Bei jedem Fehler im Hook: durchlassen (exit 0).
    PLAT-3535: Mit -InputJson (vom powershell-ast-guard als zweite Stufe im selben Prozess aufgerufen) wird die
    Eingabe nicht von stdin gelesen. Ohne Parameter unveraendert.
#>
param([string]$InputJson)
$ErrorActionPreference = 'Stop'
try {
    if ($PSBoundParameters.ContainsKey('InputJson')) {
        $raw = $InputJson
    } else {
        [Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
        $raw = [Console]::In.ReadToEnd()
    }
    $data = $raw | ConvertFrom-Json
    $tool = [string]$data.tool_name
    if ($tool -ne 'Bash' -and $tool -ne 'PowerShell') { exit 0 }
    $cmd = ([string]$data.tool_input.command).Trim()
    if (-not $cmd -or $cmd -notmatch '(?i)task\.ps1') { exit 0 }

    # Anfuehrungszeichen-bewusst in Segmente zerlegen; Trenner (Pipe usw.) nur ausserhalb von Quotes.
    $esc = if ($tool -eq 'Bash') { '\' } else { '`' }
    $segs = New-Object System.Collections.Generic.List[string]
    $seps = New-Object System.Collections.Generic.List[string]
    $sb = New-Object System.Text.StringBuilder
    $q = $null
    $i = 0
    while ($i -lt $cmd.Length) {
        $c = [string]$cmd[$i]
        $next = if ($i + 1 -lt $cmd.Length) { [string]$cmd[$i + 1] } else { '' }
        if ($q) {
            [void]$sb.Append($c)
            if ($q -eq '"' -and $c -eq $esc -and $next) { $i++; [void]$sb.Append($next) }
            elseif ($c -eq $q) { $q = $null }
            $i++; continue
        }
        if ($c -eq "'" -or $c -eq '"') { $q = $c; [void]$sb.Append($c); $i++; continue }
        $sep = $null
        if ($c -eq '|') { $sep = 'pipe'; if ($next -eq '|') { $i++ } }
        elseif ($c -eq '&' -and $next -eq '&') { $sep = 'chain'; $i++ }
        elseif ($c -eq ';' -or $c -eq "`n" -or $c -eq "`r") { $sep = 'chain' }
        elseif ($c -eq '{' -or $c -eq '}') { $sep = 'block' }
        if ($sep) {
            $segs.Add($sb.ToString()); [void]$sb.Clear()
            if ($sep -ne 'chain' -or -not $seps.Contains('chain')) { if (-not $seps.Contains($sep)) { $seps.Add($sep) } }
        } else { [void]$sb.Append($c) }
        $i++
    }
    $segs.Add($sb.ToString())

    $callRx = '(?is)^\s*(?:&\s*)?(?:(?:pwsh|powershell)(?:\.exe)?\s+(?:-\w+\s+(?:(?![-"''])\S+\s+)?)*?-File\s+)?["'']?[^\s"'']*task\.ps1["'']?(?:\s+(.*))?$'
    $call = $null
    foreach ($s in $segs) {
        $m = [regex]::Match($s, $callRx)
        if ($m.Success) { $call = $m; break }
    }
    if (-not $call) { exit 0 }

    $problems = New-Object System.Collections.Generic.List[string]

    if ($seps.Count -gt 0) {
        $problems.Add("Der task.ps1-Aufruf ist mit Pipe, Semikolon, &&, Zeilenumbruch oder foreach/Skriptblock verkettet. " +
            "Das loest ein Berechtigungs-Popup aus oder wird vom Wrapper abgelehnt. " +
            "Stattdessen: genau ein einfacher Aufruf pro Schritt, ohne Filter (Where-Object, Select-Object, Format-Table, Out-String) " +
            "und ohne Schleife; bei mehreren Status je einen eigenen Get-Task-Aufruf absetzen und die Ausgabe direkt lesen.")
    }

    # Argument des Wrappers (erstes Argument nach dem Pfad) auswerten
    $arg = if ($call.Groups[1].Success) { $call.Groups[1].Value.Trim() } else { '' }
    $inner = $arg
    if ($arg.Length -ge 2 -and ($arg[0] -eq '"' -or $arg[0] -eq "'")) {
        $qc = $arg[0]; $end = 1
        while ($end -lt $arg.Length) {
            if ($qc -eq '"' -and [string]$arg[$end] -eq $esc -and $end + 1 -lt $arg.Length) { $end += 2; continue }
            if ($arg[$end] -eq $qc) { break }
            $end++
        }
        $inner = $arg.Substring(1, [Math]::Min($end, $arg.Length) - 1)
    }
    $verbM = [regex]::Match($inner, '^\s*([A-Za-z]+-[A-Za-z]+)')
    $verb = if ($verbM.Success) { $verbM.Groups[1].Value } else { '' }
    if ($verb -ieq 'Get-Task' -or $verb -ieq 'Set-Task') {
        $lits = New-Object System.Collections.Generic.List[string]
        $masked = [regex]::Replace($inner, "'([^']*)'|`"([^`"]*)`"", {
            param($mm)
            $lits.Add($(if ($mm.Groups[1].Success) { $mm.Groups[1].Value } else { $mm.Groups[2].Value }))
            'Q' + ($lits.Count - 1) + 'Q'
        })
        $allowed = if ($verb -ieq 'Get-Task') { @('OPEN','IN_PROGRESS','REVIEW','BLOCKED','DONE') }
                   else { @('DRAFT','OPEN','IN_PROGRESS','BLOCKED','REVIEW','DONE','CANCELLED') }
        foreach ($sm in [regex]::Matches($masked, '(?i)(?<![\w-])-Status(?:\s+|:)(\S+)')) {
            $val = $sm.Groups[1].Value
            $lit = [regex]::Match($val, '^Q(\d+)Q$')
            if ($lit.Success) { $val = $lits[[int]$lit.Groups[1].Value] }
            if ($val -match '[,\s]' -or $val.StartsWith('@') -or $val -match 'Q\d+Q') {
                $problems.Add("Statusliste '$val' bei $verb -Status ist nicht zulaessig. Immer genau ein Status pro Aufruf: ein eigener Get-Task-Aufruf je Status (erlaubt: " + ($allowed -join ', ') + ").")
            } elseif ($allowed -notcontains $val.ToUpperInvariant()) {
                $hint = if ($verb -ieq 'Get-Task') { "Erlaubte Statuswerte bei Get-Task: OPEN, IN_PROGRESS, REVIEW, BLOCKED, DONE." }
                        else { "Set-Task -Status nur aus: DRAFT, OPEN, IN_PROGRESS, BLOCKED, REVIEW, DONE, CANCELLED." }
                $problems.Add("Unzulaessiger Statuswert '$val' bei $verb -Status (Variablen sind nicht erlaubt, Werte wie 'Complete' gibt es nicht). $hint")
            }
        }
    }

    # PLAT-3738 (Security S-3 part 1, ADR-0112): override_reason / -OverrideReason is the human path of the Change Service
    # (stored and counted). An agent call through the wrapper never carries it. Deliberately strict: the word anywhere in
    # a task.ps1 call is rejected, also inside a quoted note (write such a note with -ImplementationNotesFile / -NoteFile).
    if ($cmd -match '(?i)override[_-]?reason') {
        $problems.Add("Der Aufruf enthaelt override_reason (-OverrideReason). Das ist der Weg fuer Menschen (Sascha) und kommt in keinem Agent-Aufruf vor, " +
            "auch nicht als Text in einer Note. Stattdessen den Fehlertext des Services befolgen und den richtigen Weg gehen; " +
            "braucht es wirklich eine Ausnahme, im Bericht an Sascha melden. Notes, die das Wort nennen, ueber -ImplementationNotesFile bzw. -NoteFile schreiben.")
    }

    if ($tool -eq 'PowerShell') {
        $bytes = [Text.Encoding]::UTF8.GetByteCount($cmd)
        if ($bytes -gt 1000) {
            $problems.Add("Der Befehl hat $bytes Byte (Umlaute zaehlen doppelt); im PowerShell-Werkzeug ist mehr als etwa 1000 Byte ein Popup-Risiko. " +
                "Lange Argumente (z. B. -ImplementationNotes, -Description, lange -Note) ueber das Bash-Werkzeug uebergeben (pwsh -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <Repo>/.claude/tools/task.ps1 `"<Befehl>`") oder kuerzen.")
        }
    }

    if ($problems.Count -eq 0) { exit 0 }
    $reason = "[task-call-guard] Aufruf abgelehnt, bevor ein Berechtigungs-Popup erscheint. " + ($problems -join ' ') +
        " Regeln: Skill Abschnitt 1a (Werkzeuge und Befehle)."
    @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } } |
        ConvertTo-Json -Compress -Depth 4 | Write-Output
    exit 0
} catch {
    exit 0
}
