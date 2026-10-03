<#
    PreToolUse-Hook, registriert in .claude/settings.json (PLAT-3657, aus PLAT-3652). Er laeuft fuer alle Sitzungen und
    alle Rollen (kein Subagent-Freibrief) und trennt echte Umgebungsdateien von Platzhalter-Vorlagen:
      - abgelehnt: Dateinamen .env*, also .env, .env.local, .env.test, .env.*.local, .env.production, .envrc usw.
      - erlaubt:   Dateinamen .env*.example (z. B. .env.test.example), das sind Vorlagen mit Platzhalterwerten.
    Warum ein Hook: In Claude Code hebt allow ein deny nicht auf, und deny-Muster kennen keine Ausnahme (keine Negation).
    Ein Hook kann "alles .env* ausser *.example" fail-closed ausdruecken; die Rest-Sperren in permissions.deny bleiben als
    zweite Schicht (Grep ueber ein ganzes Verzeichnis kann der Hook nicht erfassen, das deny-Muster best effort schon).

    Erfasste Werkzeuge: Read, Edit, Write, NotebookEdit, MultiEdit (Feld file_path bzw. notebook_path) und Grep (Feld path
    sowie Feld glob: ein glob mit ".env", der nicht auf ".example" endet, wird abgelehnt). Glob liefert nur Namen, keine
    Inhalte, und wird nicht geprueft. Shell-Zugriffe (cat, Get-Content) erfasst dieser Hook nicht.

    Namensabgleich (nur der letzte Pfadteil, Gross/Klein egal): Alternate Data Streams (Teil ab ':') und Punkte/Leerzeichen
    am Ende werden entfernt, weil Windows sie ignoriert; 8.3-Kurznamen (ENV~1) gelten als .env-artig. Eine Vorlage, die
    ein Symlink oder eine Junction ist, wird abgelehnt (koennte auf eine echte Datei zeigen).

    Fail-closed: jeder interne Fehler (kein gueltiges JSON, falsche Feldtypen, Ausnahme) ergibt exit 2. Kein Protokoll,
    keine Inhalte im Ausgabetext (nur der gekuerzte Pfad). Der Hook oeffnet nie eine Datei, er liest nur Attribute.
#>
$ErrorActionPreference = 'Stop'
$PathTools = @('Read', 'Edit', 'Write', 'NotebookEdit', 'MultiEdit')

function Stop-Hook([string]$Code, [string]$Detail) {
    $msg = "[env-guard] Abgelehnt ($Code): $Detail " +
        "Regel: Echte Umgebungsdateien (.env, .env.local, .env.test, .env.*.local, .env.production usw.) werden nie gelesen oder geschrieben. " +
        "Richtiger Weg: Platzhalter-Vorlagen mit der Endung .example verwenden (z. B. .env.test.example, nur Platzhalterwerte, nie echte Werte); " +
        "diese duerfen gelesen und geschrieben werden. Echte Werte traegt Sascha lokal ein oder sie kommen aus dem Vault. " +
        "Muss eine echte Datei geaendert werden: stoppen und an Sascha melden."
    [Console]::Error.WriteLine($msg)
    exit 2
}

# Letzter nicht leerer Pfadteil, normalisiert wie Windows ihn aufloest (klein, ohne Stream, ohne Punkt/Leerzeichen am Ende).
function Get-BaseName([string]$Raw) {
    $segs = @($Raw.Replace('\', '/').Split('/') | Where-Object { $_ -ne '' })
    if ($segs.Count -eq 0) { return '' }
    $n = $segs[$segs.Count - 1]
    $i = $n.IndexOf(':')
    if ($i -ge 0) { $n = $n.Substring(0, $i) }
    return $n.TrimEnd('.', ' ').ToLowerInvariant()
}

# Namen des Pfads roh und nach GetFullPath (loest "/." und "/sub/.." auf, PLAT-3657 SEC-2). Schlaegt GetFullPath fehl,
# zaehlt nur der rohe Name (der Hook lehnt dann nur ab, was schon roh .env-artig ist).
function Get-Names([string]$Raw) {
    $names = @(Get-BaseName $Raw)
    try { $names += Get-BaseName ([IO.Path]::GetFullPath($Raw)) } catch { }
    return $names
}

# 8.3-Kurzname (z. B. ENV~1.LOC, ENVIRO~1) gilt als .env-artig (SEC-3).
function Test-EnvLike([string]$Name) {
    return ($Name -match '^\.env') -or ($Name -match '^env[^.~]*~\d')
}

function Test-Template([string]$Name) {
    return $Name -match '^\.env.*\.example$'
}

function Test-ReparseFile([string]$Raw) {
    $native = $Raw.Replace('/', '\')
    if (-not (Test-Path -LiteralPath $native)) { return $false }
    $attr = [IO.File]::GetAttributes($native)
    return (($attr -band [IO.FileAttributes]::ReparsePoint) -ne 0)
}

function Get-Shown($Raw) {
    $s = if ($Raw -is [string]) { ($Raw -replace '[^\x20-\x7E]', '?') } else { '<kein Wert>' }
    if ($s.Length -gt 200) { $s = $s.Substring(0, 200) + '...' }
    return "Pfad: $s."
}

try {
    $stdin = New-Object System.IO.MemoryStream
    [Console]::OpenStandardInput().CopyTo($stdin)
    $text = (New-Object System.Text.UTF8Encoding($false, $true)).GetString($stdin.ToArray()).TrimStart([char]0xFEFF)
    $data = $text | ConvertFrom-Json
    if ($data -isnot [System.Management.Automation.PSCustomObject]) { throw 'Hook-Eingabe ist kein JSON-Objekt' }
    if ($data.tool_name -isnot [string] -or $data.tool_name -eq '') { throw 'tool_name fehlt oder ist kein String' }
    $tool = $data.tool_name
    $isGrep = ($tool -ceq 'Grep')
    if (-not $isGrep -and $PathTools -cnotcontains $tool) { exit 0 }
    if ($data.tool_input -isnot [System.Management.Automation.PSCustomObject]) { throw 'tool_input fehlt oder ist kein Objekt' }
    $props = @($data.tool_input.PSObject.Properties.Name)

    if ($isGrep) {
        # Grep: path (Datei oder Verzeichnis) und glob pruefen; fehlende Felder sind erlaubt (Standard: aktuelles Verzeichnis).
        if ($props -ccontains 'path') {
            $gp = $data.tool_input.path
            if ($gp -isnot [string] -and $null -ne $gp) { throw 'path ist kein String' }
            if ($gp -is [string]) {
                foreach ($n in (Get-Names $gp)) {
                    if ((Test-EnvLike $n) -and -not (Test-Template $n)) { Stop-Hook 'env-file' ("Grep auf eine echte Umgebungsdatei. " + (Get-Shown $gp)) }
                }
            }
        }
        if ($props -ccontains 'glob') {
            $gl = $data.tool_input.glob
            if ($gl -isnot [string] -and $null -ne $gl) { throw 'glob ist kein String' }
            if ($gl -is [string]) {
                # E1: glob in Einzelmuster zerlegen (Leerzeichen, Komma); jedes Muster mit .env muss auf .example enden.
                # Mit .env im Text sind Klammern {..} und fuehrendes ! (Negation) nicht sicher auswertbar: abgelehnt.
                $g = $gl.ToLowerInvariant()
                if ($g.Contains('.env')) {
                    $tokens = @($g -split '[\s,]+' | Where-Object { $_ -ne '' })
                    $unsafe = $g.Contains('{') -or $g.Contains('}') -or (@($tokens | Where-Object { $_.StartsWith('!') }).Count -gt 0)
                    $bad = @($tokens | Where-Object { $_.Contains('.env') -and -not $_.TrimEnd('.', ' ').EndsWith('.example') }).Count -gt 0
                    if ($unsafe -or $bad) { Stop-Hook 'env-glob' ("Grep-Filter zielt auf echte Umgebungsdateien. " + (Get-Shown $gl)) }
                }
            }
        }
        exit 0
    }

    $field = if ($tool -ceq 'NotebookEdit') { 'notebook_path' } else { 'file_path' }
    $raw = $null
    if ($props -ccontains $field) { $raw = $data.tool_input.$field }
    if ($raw -isnot [string] -or $raw.Length -eq 0) { throw "$field fehlt oder ist kein String" }
    $anyEnv = $false
    foreach ($name in (Get-Names $raw)) {
        if (Test-EnvLike $name) {
            $anyEnv = $true
            if (-not (Test-Template $name)) { Stop-Hook 'env-file' ("Echte Umgebungsdatei. " + (Get-Shown $raw)) }
        }
    }
    if (-not $anyEnv) { exit 0 }
    if (Test-ReparseFile $raw) { Stop-Hook 'reparse-point' ("Die Vorlage ist ein Symlink oder eine Junction. " + (Get-Shown $raw)) }
    exit 0
} catch {
    [Console]::Error.WriteLine('[env-guard] interner Fehler, fail-closed (exit 2): ' + ($_.Exception.Message -replace '[^\x20-\x7E]', '?'))
    exit 2
}
