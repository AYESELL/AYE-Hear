#Requires -Version 5.1
<#
.SYNOPSIS
    AYE Hear runtime startup health check - validates local PostgreSQL before app launch.

.DESCRIPTION
    Implements the startup validation required by ADR-0006:
      1. Verify AyeHearDB Windows service is running; attempt auto-start if stopped.
      2. Read the installer-provisioned DSN from C:\AyeHear\runtime\pg.dsn.
      3. Confirm PostgreSQL is reachable and accepting connections on loopback.
      4. Validate that listen_addresses is loopback-only (security gate, ADR-0006).
      5. Confirm schema migration baseline is present (meetings table exists).

    Exit codes:
    0 - all checks passed; application may launch.
    1 - one or more checks failed; caller should display diagnostic.

.PARAMETER InstallDir
    AYE Hear install root. Default: C:\AyeHear

.PARAMETER Silent
    Suppress human-readable output; only emit exit code.

.EXAMPLE
    # Pre-launch check (called from AyeHear.exe launcher or shortcut wrapper)
    .\Start-AyeHearRuntime.ps1
    if ($LASTEXITCODE -ne 0) { Write-Error "Database not ready." }

.NOTES
    ADR references: ADR-0006, ADR-0007
    Task:           HEAR-049
    Owner:          AYEHEAR_DEVOPS
#>
[CmdletBinding()]
param(
    [string]$InstallDir = 'C:\AyeHear',
    [switch]$Silent
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'   # Non-fatal: each check produces its own result

$PG_SERVICE_NAME = 'AyeHearDB'
$PG_PORT         = 5433
$DSN_FILE        = Join-Path $InstallDir 'runtime\pg.dsn'
$PG_BIN_DIR      = Join-Path $InstallDir 'pgsql\bin'

# Helper: resolve a pg binary, preferring the bundled path then falling back to PATH.
function Resolve-PgBin {
    param([string]$ExeName)
    $bundled = Join-Path $PG_BIN_DIR $ExeName
    if (Test-Path $bundled) { return $bundled }
    $inPath = Get-Command $ExeName -ErrorAction SilentlyContinue
    if ($inPath) { return $inPath.Source }
    return $null
}

$script:AllPassed = $true
$script:Results   = [System.Collections.Generic.List[hashtable]]::new()

function Write-Check {
    param([string]$Name, [bool]$Passed, [string]$Detail = '')
    $status = if ($Passed) { 'PASS' } else { 'FAIL' }
    $script:Results.Add(@{ Check = $Name; Status = $status; Detail = $Detail })
    if (-not $Passed) { $script:AllPassed = $false }
    if (-not $Silent) {
        $color        = if ($Passed) { 'Green' } else { 'Red' }
        $detailSuffix = if ($Detail) { " - $Detail" } else { '' }
        Write-Host ("  [{0}] {1}{2}" -f $status, $Name, $detailSuffix) -ForegroundColor $color
    }
}

if (-not $Silent) {
    Write-Host ''
    Write-Host '=== AYE Hear Runtime Health Check ===' -ForegroundColor Cyan
}

# --- Check 1: Windows service ------------------------------------------------

$svc = Get-Service -Name $PG_SERVICE_NAME -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Check 'PostgreSQL service registered' $false "Service '$PG_SERVICE_NAME' not found on this machine"
} elseif ($svc.Status -ne 'Running') {
    if (-not $Silent) { Write-Host "  [INFO] Service '$PG_SERVICE_NAME' is $($svc.Status) - attempting start..." }
    try {
        Start-Service -Name $PG_SERVICE_NAME -ErrorAction Stop
        Start-Sleep -Seconds 3
        $svc.Refresh()
    } catch {
        # ignore start errors - pg_isready will catch the failure below
    }
    $svc.Refresh()
    $running = $svc.Status -eq 'Running'
    Write-Check 'PostgreSQL service running' $running "Status after start attempt: $($svc.Status)"
} else {
    Write-Check 'PostgreSQL service running' $true "Status: Running"
}

# --- Check 2: DSN file accessible --------------------------------------------

$dsnExists = Test-Path $DSN_FILE
Write-Check 'Installer DSN file present' $dsnExists $DSN_FILE

$dsn = ''
if ($dsnExists) {
    try {
        $dsn = (Get-Content $DSN_FILE -Raw -ErrorAction Stop).Trim()
        $hasContent = $dsn.Length -gt 10
        $dsnDetail = if ($hasContent) { 'DSN loaded' } else { 'File is empty or too short' }
        Write-Check 'DSN file readable' $hasContent $dsnDetail
    } catch {
        Write-Check 'DSN file readable' $false $_.Exception.Message
    }
}

# --- Check 3: pg_isready -----------------------------------------------------

$pgIsReady = Resolve-PgBin 'pg_isready.exe'
if ($pgIsReady) {
    $out = & $pgIsReady -h 127.0.0.1 -p $PG_PORT 2>&1
    $ready = $LASTEXITCODE -eq 0
    Write-Check 'PostgreSQL accepting connections' $ready ($out -join ' ')
} else {
    Write-Check 'PostgreSQL accepting connections' $false "pg_isready.exe not found (checked: $(Join-Path $PG_BIN_DIR 'pg_isready.exe') and PATH)"
}

# --- Check 4: Loopback-only listen_addresses ---------------------------------

if ($dsn -and ($dsn -match 'postgresql://')) {
    $psqlExe = Resolve-PgBin 'psql.exe'
    if ($psqlExe) {
        try {
            $env:PGPASSWORD = ''   # DSN carries password via URI
            $listenAddrs = & $psqlExe $dsn -c 'SHOW listen_addresses;' -t -q 2>&1 |
                           Where-Object { $_.Trim() -ne '' } | Select-Object -First 1
            Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
            $listenTrimmed = ($listenAddrs -join '').Trim()
            # Split on commas to handle multi-value configurations (e.g. "localhost,127.0.0.1")
            # Strip surrounding quotes from each token (PostgreSQL may return quoted values)
            $addrTokens = $listenTrimmed -split ',' |
                          ForEach-Object { $_.Trim().Trim("'").Trim('"').ToLower() } |
                          Where-Object { $_ -ne '' }
            # Loopback-safe: every address token must be localhost, ::1, or 127.x.x.x
            # An empty token list (empty setting) means no network exposure - also safe.
            # Consistent with DatabaseBootstrap._is_loopback_address() (ADR-0006)
            $nonLoopback = $addrTokens | Where-Object {
                $_ -ne 'localhost' -and $_ -ne '::1' -and $_ -notmatch '^127\.'
            }
            $loopbackSafe = ($addrTokens.Count -eq 0) -or (-not $nonLoopback)
            Write-Check 'listen_addresses loopback-only (ADR-0006)' $loopbackSafe "listen_addresses=$listenTrimmed"
        } catch {
            Write-Check 'listen_addresses loopback-only (ADR-0006)' $false $_.Exception.Message
        }
    } else {
        Write-Check 'listen_addresses loopback-only (ADR-0006)' $false "psql.exe not found (checked: $(Join-Path $PG_BIN_DIR 'psql.exe') and PATH)"
    }
} else {
    Write-Check 'listen_addresses loopback-only (ADR-0006)' $false 'No usable DSN for query'
}

# --- Check 5: Schema baseline - meetings table -------------------------------

if ($dsn -and ($dsn -match 'postgresql://')) {
    $psqlExe = Resolve-PgBin 'psql.exe'
    if ($psqlExe) {
        try {
            $tableCheck = & $psqlExe $dsn -c @"
SELECT 1
FROM   information_schema.tables
WHERE  table_schema = 'public'
  AND  table_name   = 'meetings';
"@ -t -q 2>&1
            $tableExists = ($tableCheck -join '').Trim() -eq '1'
            $schemaDetail = if ($tableExists) { 'Table exists' } else { 'Table not found - migrations may not have run' }
            Write-Check 'Schema baseline (meetings table)' $tableExists $schemaDetail
        } catch {
            Write-Check 'Schema baseline (meetings table)' $false $_.Exception.Message
        }
    } else {
        Write-Check 'Schema baseline (meetings table)' $false "psql.exe not found (checked: $(Join-Path $PG_BIN_DIR 'psql.exe') and PATH)"
    }
}

# --- Summary -----------------------------------------------------------------

if (-not $Silent) {
    Write-Host ''
    if ($script:AllPassed) {
        Write-Host '=== ALL CHECKS PASSED - AYE Hear is ready to launch ===' -ForegroundColor Green
    } else {
        Write-Host '=== HEALTH CHECK FAILED ===' -ForegroundColor Red
        Write-Host ''
        Write-Host 'Failed checks:' -ForegroundColor Yellow
        $script:Results | Where-Object { $_.Status -eq 'FAIL' } | ForEach-Object {
            Write-Host ("  - {0}: {1}" -f $_.Check, $_.Detail) -ForegroundColor Yellow
        }
        Write-Host ''
        Write-Host 'Troubleshooting:' -ForegroundColor Cyan
        Write-Host '  1. Ensure AyeHearDB service is running: Start-Service AyeHearDB'
        Write-Host '  2. Re-run provisioning: .\Install-PostgresRuntime.ps1'
        Write-Host '  3. Check logs: C:\AyeHear\logs\pg-install.log'
        Write-Host '  4. Consult runbook: docs\quick-refs\WINDOWS_PACKAGING_RUNBOOK.md'
    }
    Write-Host ''
}

exit $(if ($script:AllPassed) { 0 } else { 1 })
