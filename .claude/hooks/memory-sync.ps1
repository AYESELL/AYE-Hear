<#
    SubagentStop hook (PLAT-3752): secures role memory of an isolated agent worktree in the main folder
    BEFORE Claude Code can auto-clean the worktree (WorktreeRemove only fires for hook-based worktrees,
    so SubagentStop is the usable event; worktree path is derived, see below).

    Rules (docs/runbooks/WORKTREE_CLEANUP.md, "Agent memory handling"):
    - Reads ONLY <worktree>/.claude/agent-memory/<agent_type>/** (the folder of the role that stopped; no
      agent_type or an invalid one -> nothing is copied) and writes ONLY the same relative path below
      <main>/.claude/agent-memory/. No other paths. Never deletes, never overwrites.
    - New file            -> copied.
    - Identical file      -> skipped.
    - Differing file      -> saved as <name>.from-worktree<ext>; a second different version as
                             <name>.from-worktree-<worktree folder><ext>; a third is reported, not written.
    - MEMORY.md is never overwritten (differing index is saved as MEMORY.from-worktree.md).
    - Target side: if .claude, agent-memory, any existing folder on the target path or an existing target file
      is a reparse point (junction/symlink), the file is skipped and reported (SEC-1).
    - Limits per run: more than 200 files or more than 5 MB in total -> nothing is copied, reported (SEC-5).
    - Fail-safe: any error -> nothing more is done, message on stderr, exit 0 (never blocks the agent stop).
    - Main folder comes from git (common git dir), not from a hard-coded path.
    Worktree path: (a) top level of cwd if it is a linked worktree, else
    (b) <main>/.claude/worktrees/agent-<agent_id>. In BOTH cases the folder must be listed by
    `git worktree list --porcelain` of the main folder, otherwise nothing is copied (SEC-2).
#>
$ErrorActionPreference = 'Stop'
$MaxBytes = 1MB
$MaxFiles = 200
$MaxTotal = 5MB

function Out-Msg([string]$m) { [Console]::Error.WriteLine("memory-sync: $m") }
function Norm([string]$p) { [IO.Path]::GetFullPath($p).TrimEnd('\', '/') }
function Same([string]$a, [string]$b) { [string]::Equals((Norm $a), (Norm $b), [StringComparison]::OrdinalIgnoreCase) }
function FileHashOf([string]$p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }
function Test-Link([string]$p) {
    if (-not (Test-Path -LiteralPath $p)) { return $false }
    return [bool]((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)
}

# SEC-1: no reparse point on the target path (.claude, agent-memory, existing folders below it, the file itself)
function Test-DestSafe([string]$main, [string]$dstRoot, [string]$dst) {
    foreach ($p in @((Join-Path $main '.claude'), $dstRoot)) { if (Test-Link $p) { return $false } }
    $rel = (Norm $dst).Substring((Norm $dstRoot).Length).TrimStart('\', '/')
    $cur = $dstRoot
    foreach ($seg in ($rel -split '[\\/]')) {
        if (-not $seg) { continue }
        $cur = Join-Path $cur $seg
        if (Test-Link $cur) { return $false }
    }
    return $true
}

function Copy-NoOverwrite([string]$src, [string]$dst) {
    $dir = Split-Path -Parent $dst
    if (-not (Test-Path -LiteralPath $dir)) { [void][IO.Directory]::CreateDirectory($dir) }
    [IO.File]::Copy($src, $dst, $false)   # throws if the target exists: never overwrites
}

function Sync-File([string]$src, [string]$dst, [string]$wtName, [string]$main, [string]$dstRoot) {
    if (-not (Test-DestSafe $main $dstRoot $dst)) { return 'target-link-skipped' }
    if (-not (Test-Path -LiteralPath $dst)) { Copy-NoOverwrite $src $dst; return 'copied' }
    $h = FileHashOf $src
    if ((FileHashOf $dst) -eq $h) { return 'identical' }
    $dir = Split-Path -Parent $dst
    $base = [IO.Path]::GetFileNameWithoutExtension($dst)
    $ext = [IO.Path]::GetExtension($dst)
    foreach ($suffix in @('.from-worktree', ".from-worktree-$wtName")) {
        $alt = Join-Path $dir ($base + $suffix + $ext)
        if (Test-Link $alt) { return 'target-link-skipped' }
        if (-not (Test-Path -LiteralPath $alt)) { Copy-NoOverwrite $src $alt; return 'saved-as-variant' }
        if ((FileHashOf $alt) -eq $h) { return 'identical-variant' }
    }
    return 'conflict-kept'
}

function Sync-Worktree([string]$wt, [string]$main, [string]$role) {
    $srcRoot = Join-Path $wt ".claude/agent-memory/$role"
    if (-not (Test-Path -LiteralPath $srcRoot -PathType Container)) { return }
    foreach ($p in @((Join-Path $wt '.claude/agent-memory'), $srcRoot)) {
        if (Test-Link $p) { Out-Msg "skip $p (link)"; return }
    }
    $dstRoot = Join-Path $main '.claude/agent-memory'
    $srcFull = Norm $srcRoot
    $wtName = Split-Path -Leaf (Norm $wt)

    $files = @(Get-ChildItem -LiteralPath $srcRoot -Recurse -File -Force | Where-Object { -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) })
    $total = ($files | Measure-Object -Property Length -Sum).Sum
    if ($files.Count -gt $MaxFiles -or $total -gt $MaxTotal) {
        Out-Msg "abort $wtName/$role : $($files.Count) files, $total bytes exceed the limit ($MaxFiles files, $MaxTotal bytes); nothing copied"
        return
    }

    $counts = @{}
    foreach ($f in $files) {
        try {
            $full = Norm $f.FullName
            if (-not $full.StartsWith($srcFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { continue }
            if ($f.Length -gt $MaxBytes) { Out-Msg "skip $full (larger than 1 MB)"; continue }
            $rel = $full.Substring($srcFull.Length + 1)
            if ($rel -match '(^|[\\/])\.\.([\\/]|$)') { continue }
            $dst = Join-Path (Join-Path $dstRoot $role) $rel
            if (-not (Norm $dst).StartsWith((Norm $dstRoot) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { continue }
            $r = Sync-File $full $dst $wtName $main $dstRoot
            $counts[$r] = 1 + [int]$counts[$r]
            if ($r -eq 'conflict-kept') { Out-Msg "conflict, not written: $rel (variants already exist with other content)" }
            if ($r -eq 'target-link-skipped') { Out-Msg "skip $rel (reparse point on the target path)" }
        } catch {
            Out-Msg "file skipped: $($f.Name): $($_.Exception.Message)"
        }
    }
    if ($counts.Count -gt 0) {
        Out-Msg ("worktree {0}: {1}" -f $wtName, (($counts.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ', '))
    }
}

try {
    $raw = [Console]::In.ReadToEnd()
    $data = $raw | ConvertFrom-Json
    $cwd = [string]$data.cwd
    if (-not $cwd -or -not (Test-Path -LiteralPath $cwd)) { exit 0 }

    # SEC-3: only the folder of the role that stopped
    $role = [string]$data.agent_type
    if ($role -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$') { exit 0 }

    $g = @(& git -C $cwd rev-parse --path-format=absolute --show-toplevel --git-dir --git-common-dir 2>$null)
    if ($LASTEXITCODE -ne 0 -or $g.Count -lt 3) { exit 0 }
    $top = $g[0]; $gitDir = $g[1]; $common = $g[2]
    if ((Split-Path -Leaf (Norm $common)) -ne '.git') { exit 0 }
    $main = Split-Path -Parent (Norm $common)

    # SEC-2: every candidate must be registered in the worktree list of the main folder
    $listed = @(& git -C $main worktree list --porcelain 2>$null | Where-Object { $_ -like 'worktree *' } | ForEach-Object { $_.Substring(9) })
    if ($LASTEXITCODE -ne 0 -or $listed.Count -eq 0) { exit 0 }
    $cands = New-Object System.Collections.Generic.List[string]
    function Add-Cand([string]$p) {
        if (Same $p $main) { return }
        if (-not ($listed | Where-Object { Same $_ $p })) { Out-Msg "skip $p (not in git worktree list)"; return }
        if (-not ($cands | Where-Object { Same $_ $p })) { $cands.Add((Norm $p)) }
    }
    if (-not (Same $gitDir $common) -and -not (Same $top $main)) { Add-Cand $top }

    $aid = [string]$data.agent_id
    if ($aid -match '^[A-Za-z0-9]{4,64}$') {
        $guess = Join-Path $main ".claude/worktrees/agent-$aid"
        if (Test-Path -LiteralPath $guess -PathType Container) { Add-Cand $guess }
    }
    foreach ($wt in $cands) { Sync-Worktree $wt $main $role }
} catch {
    Out-Msg "failed, nothing done: $($_.Exception.Message)"
}
exit 0
