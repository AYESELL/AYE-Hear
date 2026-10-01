<#
    PreToolUse-Hook, registriert in .claude/settings.json (PLAT-3554; zuvor Frontmatter der Lead-Vorlage, PLAT-3536,
    Plan 3.2, Security S-01/S-02). Er laeuft fuer alle Sitzungen und schraenkt nur die Lead-Hauptsession ein:
    Die Projektleitung (Hauptsession) schreibt keinen Code. Edit/Write/NotebookEdit/MultiEdit sind nur erlaubt fuer
      - <repo>/docs/STATUS.md und <repo>/docs/BACKLOG.md
      - das Scratchpad: <Temp>/claude/<Projekt>/<Sitzung>/scratchpad/**
      - das Lead-Gedaechtnis: <repo>/.claude/agent-memory/ayehear-lead/**
    Alles andere wird mit exit 2 und Regeltext (stderr) abgelehnt. .claude/worktrees ist immer gesperrt.

    Identitaet (Probe PLAT-3534, Claude Code 2.1.285): Die Hauptsession hat NIE den Schluessel agent_id, Subagenten haben
    ihn immer. Wer den Schluessel agent_id hat (auch leer oder null), wird nie abgelehnt. Ohne agent_id wird nur
    abgelehnt, wenn agent_type fehlt (bzw. leer/kein String ist) oder "ayehear-lead" ist; eine Hauptsession mit
    einem anderen Agenten (anderer agent_type) wird nicht eingeschraenkt (exit 0).

    Pfade: nur absolute Laufwerkspfade, normalisiert und ordinal ohne Gross/Klein verglichen; abgelehnt werden UNC- und
    Geraetepfade, relative Pfade, "..", ".", leere Segmente, Steuerzeichen, Sonderzeichen, Alternate Data Streams,
    Segmente mit Punkt oder Leerzeichen am Ende, 8.3-Kurznamen und alle Pfade, bei denen unterhalb des Ankers
    (Repo bzw. Temp/claude) ein Symlink oder eine Junction liegt.

    Fail-closed: jeder interne Fehler (kein gueltiges JSON, falsche Feldtypen, Ausnahme) ergibt exit 2.
    Kein Protokoll, kein Umschreiben der Eingabe, keine Inhalte im Ausgabetext (nur der gekuerzte Pfad).
    Schreiben ueber die Shell (Umleitung, Cmdlets) erfasst dieser Hook nicht (Best Effort ausserhalb des Hooks).
#>
$ErrorActionPreference = 'Stop'
$RepoRoot = 'G:/Repo/aye-hear'
$LeadName = 'ayehear-lead'
$WriteTools = @('Edit', 'Write', 'NotebookEdit', 'MultiEdit')

function Stop-Hook([string]$Code, [string]$Detail) {
    $msg = "[lead-write-guard] Abgelehnt ($Code): $Detail " +
        "Regel: Die Projektleitung schreibt keinen Code; Edit/Write sind nur fuer docs/STATUS.md, docs/BACKLOG.md, das Scratchpad " +
        "und das Lead-Gedaechtnis (.claude/agent-memory/$LeadName/) erlaubt. " +
        "Richtiger Weg: einen Task fuer die zustaendige Rolle anlegen (New-Task) und diese Rolle als Subagent mit dem Agent-Werkzeug beauftragen; " +
        "das Ergebnis kommt als Bericht zurueck."
    [Console]::Error.WriteLine($msg)
    exit 2
}

function Test-Segment([string]$Seg) {
    # $null = ok, sonst Ablehnungsgrund
    if ($Seg -eq '') { return 'empty-segment' }
    if ($Seg -eq '.' -or $Seg -eq '..') { return 'dot-segment' }
    if ($Seg.EndsWith('.') -or $Seg.EndsWith(' ')) { return 'trailing-dot-or-space' }
    if ($Seg.IndexOf(':') -ge 0) { return 'colon-or-stream' }
    if ($Seg -match '~\d') { return 'short-name' }
    return $null
}

# Liefert @{ Ok; Reason; Norm } mit Norm = absolute Pfadform mit '/' ohne abschliessenden '/'.
function ConvertTo-GuardPath($Raw, [bool]$Strict) {
    if ($Raw -isnot [string] -or $Raw.Length -eq 0) { return @{ Ok = $false; Reason = 'path-missing' } }
    if ($Raw.Length -gt 1024) { return @{ Ok = $false; Reason = 'path-too-long' } }
    foreach ($ch in $Raw.ToCharArray()) {
        $c = [int]$ch
        if ($c -lt 32 -or $c -eq 127 -or '<>"|?*'.IndexOf($ch) -ge 0) { return @{ Ok = $false; Reason = 'illegal-character' } }
    }
    if ($Raw -match '^[\\/]{2}') { return @{ Ok = $false; Reason = 'unc-or-device-path' } }
    if ($Raw -notmatch '^[A-Za-z]:[\\/]') { return @{ Ok = $false; Reason = 'not-absolute-drive-path' } }
    $parts = $Raw.Substring(3).Replace('\', '/').Split('/')
    if ($parts.Count -gt 0 -and $parts[$parts.Count - 1] -eq '' -and -not $Strict) { $parts = $parts[0..($parts.Count - 2)] }
    foreach ($p in $parts) {
        if ($Strict) {
            $r = Test-Segment $p
            if ($r) { return @{ Ok = $false; Reason = $r } }
        } elseif ($p -eq '' -or $p -eq '.' -or $p -eq '..') {
            return @{ Ok = $false; Reason = 'dot-segment' }
        }
    }
    return @{ Ok = $true; Norm = ($Raw.Substring(0, 2) + '/' + ($parts -join '/')).TrimEnd('/'); Segs = $parts }
}

function Test-Under([string]$Norm, [string]$Base) {
    return $Norm.StartsWith($Base + '/', [StringComparison]::OrdinalIgnoreCase)
}

# True, wenn unterhalb von $Anchor (exklusive) bis zum Ziel ein bestehender Pfadteil ein Reparse-Point ist.
function Test-ReparseBelow([string]$Anchor, [string]$Norm) {
    $rel = $Norm.Substring($Anchor.Length + 1).Split('/')
    $cur = $Anchor
    foreach ($seg in $rel) {
        $cur = $cur + '/' + $seg
        $native = $cur.Replace('/', '\')
        if (-not (Test-Path -LiteralPath $native)) { return $false }
        $attr = [IO.File]::GetAttributes($native)
        if (($attr -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return $true }
    }
    return $false
}

try {
    $stdin = New-Object System.IO.MemoryStream
    [Console]::OpenStandardInput().CopyTo($stdin)
    $text = (New-Object System.Text.UTF8Encoding($false, $true)).GetString($stdin.ToArray()).TrimStart([char]0xFEFF)
    $data = $text | ConvertFrom-Json
    if ($data -isnot [System.Management.Automation.PSCustomObject]) { throw 'Hook-Eingabe ist kein JSON-Objekt' }
    $keys = @($data.PSObject.Properties.Name)

    # Subagent: Schluessel agent_id vorhanden (auch leer/null) -> nie ablehnen.
    if ($keys -ccontains 'agent_id') { exit 0 }

    # Hauptsession mit einem anderen Agenten (agent_type gesetzt, nicht Lead): nicht einschraenken.
    # Fehlt agent_type oder ist er leer/kein String, gilt die Sitzung als Lead (fail-closed).
    if ($keys -ccontains 'agent_type') {
        $at = $data.agent_type
        if ($at -is [string] -and $at.Trim() -ne '' -and $at -ine $LeadName) { exit 0 }
    }

    if ($data.tool_name -isnot [string] -or $data.tool_name -eq '') { throw 'tool_name fehlt oder ist kein String' }
    if ($WriteTools -cnotcontains $data.tool_name) { exit 0 }
    if ($data.tool_input -isnot [System.Management.Automation.PSCustomObject]) { throw 'tool_input fehlt oder ist kein Objekt' }

    $field = if ($data.tool_name -ceq 'NotebookEdit') { 'notebook_path' } else { 'file_path' }
    $raw = $null
    if (@($data.tool_input.PSObject.Properties.Name) -ccontains $field) { $raw = $data.tool_input.$field }
    $shown = if ($raw -is [string]) { ($raw -replace '[^\x20-\x7E]', '?'); } else { '<kein Pfad>' }
    if ($shown.Length -gt 200) { $shown = $shown.Substring(0, 200) + '...' }
    $shown = "Pfad: $shown."

    $path = ConvertTo-GuardPath $raw $true
    if (-not $path.Ok) { Stop-Hook $path.Reason "Der Pfad ist nicht zulaessig (absolut mit Laufwerk, normalisiert, ohne Tricks). $shown" }
    $norm = $path.Norm
    $segsLower = @($path.Segs | ForEach-Object { $_.ToLowerInvariant() })
    for ($i = 0; $i -lt $segsLower.Count - 1; $i++) {
        if ($segsLower[$i] -eq '.claude' -and $segsLower[$i + 1] -eq 'worktrees') { Stop-Hook 'worktrees-blocked' ".claude/worktrees ist gesperrt. $shown" }
    }

    $rootP = ConvertTo-GuardPath $RepoRoot $false
    if (-not $rootP.Ok) { throw 'repo_path in der Hook-Vorlage ist nicht normalisierbar' }
    $root = $rootP.Norm
    $tempP = ConvertTo-GuardPath ([IO.Path]::GetTempPath()) $false
    if (-not $tempP.Ok) { throw 'Temp-Verzeichnis nicht normalisierbar' }
    $claudeTemp = $tempP.Norm + '/claude'

    $anchor = $null
    foreach ($f in @('docs/STATUS.md', 'docs/BACKLOG.md')) {
        if ($norm.Equals($root + '/' + $f, [StringComparison]::OrdinalIgnoreCase)) { $anchor = $root }
    }
    if (-not $anchor -and (Test-Under $norm ($root + '/.claude/agent-memory/' + $LeadName))) { $anchor = $root }
    if (-not $anchor -and (Test-Under $norm $claudeTemp)) {
        $rel = $norm.Substring($claudeTemp.Length + 1).Split('/')
        if ($rel.Count -ge 4 -and $rel[2] -ieq 'scratchpad') { $anchor = $claudeTemp }
    }
    if (-not $anchor) { Stop-Hook 'path-not-allowed' "Dieser Pfad gehoert nicht zur Allowlist der Projektleitung. $shown" }

    if (Test-ReparseBelow $anchor $norm) { Stop-Hook 'reparse-point' "Der Pfad fuehrt ueber einen Symlink oder eine Junction. $shown" }
    exit 0
} catch {
    [Console]::Error.WriteLine('[lead-write-guard] interner Fehler, fail-closed (exit 2): ' + ($_.Exception.Message -replace '[^\x20-\x7E]', '?'))
    exit 2
}
