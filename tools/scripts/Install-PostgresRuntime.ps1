#Requires -Version 5.1
#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Provisions the installer-managed local PostgreSQL 16 runtime for AYE Hear.

.DESCRIPTION
    Implements the full PostgreSQL lifecycle defined by ADR-0006:
      1. Check for an existing AyeHear PG installation; skip if already configured.
      2. Download (or use a bundled) PostgreSQL 16 EDB installer when binaries are absent.
      3. Silent install to C:\AyeHear\pgsql.
      4. Generate a per-installation application password and persist the DSN
         to C:\AyeHear\runtime\pg.dsn with ACL restricted to SYSTEM + Administrators.
      5. Run initdb on C:\AyeHear\data\pg16.
      6. Enforce loopback-only listen_addresses in postgresql.conf.
      7. Register the AyeHearDB Windows service via pg_ctl register.
      8. Start the service and wait for readiness.
      9. Create the ayehear database role and database.
     10. Apply schema migrations via ayehear.storage.database bootstrap.

.PARAMETER InstallDir
    Root install directory. Default: C:\AyeHear

.PARAMETER AppBinDir
    Path to the AYE Hear app bundle (contains the bundled Python runtime).
    Default: C:\AyeHear\app

.PARAMETER BundledPgInstaller
    Full path to a pre-downloaded postgresql-16.*-windows-x64.exe.
    When provided, the download step is skipped.
    Useful for offline/bundled deployments.

.PARAMETER Force
    Re-initialize even if a data directory already exists.
    WARNING: destroys existing database data when combined with an existing data dir.

.EXAMPLE
    # Standard installer-managed path (called from Inno Setup [Run] entry)
    .\Install-PostgresRuntime.ps1

    # Offline path — bundled installer alongside the setup exe
    .\Install-PostgresRuntime.ps1 -BundledPgInstaller "C:\AyeHear\pg-installer\postgresql-16.4-1-windows-x64.exe"

.NOTES
    ADR references: ADR-0006, ADR-0007, ADR-0009
    Task:           HEAR-049
    Owner:          AYEHEAR_DEVOPS
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$InstallDir      = 'C:\AyeHear',
    [string]$AppBinDir       = 'C:\AyeHear\app',
    [string]$BundledPgInstaller = '',
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ─── Constants ────────────────────────────────────────────────────────────────

$PG_VERSION       = '16'
$PG_PORT          = 5433
$PG_SERVICE_NAME  = 'AyeHearDB'
$PG_APP_USER      = 'ayehear'
$PG_APP_DB        = 'ayehear'

$PG_BIN_DIR       = Join-Path $InstallDir 'pgsql\bin'
$PG_DATA_DIR      = Join-Path $InstallDir "data\pg$PG_VERSION"
$RUNTIME_DIR      = Join-Path $InstallDir 'runtime'
$LOG_DIR          = Join-Path $InstallDir 'logs'
$DSN_FILE         = Join-Path $RUNTIME_DIR 'pg.dsn'
$LOG_FILE         = Join-Path $LOG_DIR 'pg-install.log'

# PostgreSQL 16 EDB download URL (official, checksum-verifiable)
$PG_DOWNLOAD_URL  = 'https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64.exe'
$PG_INSTALLER_SHA256 = 'DB5E9D3E4AD65D29E0AD2B6E90B0A36A9D1CB3C47CDA9A6BBAF1CF7F8D8E9C0A'  # placeholder: validate in CI

# ─── Helpers ──────────────────────────────────────────────────────────────────

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $ts  = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null }
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8
}

function Invoke-Pg {
    param([string]$Tool, [string[]]$Arguments)
    $exe = Join-Path $PG_BIN_DIR "$Tool.exe"
    if (-not (Test-Path $exe)) {
        throw "PostgreSQL binary not found: $exe"
    }
    Write-Log "  -> $Tool $($Arguments -join ' ')"
    $result = & $exe @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$Tool failed (exit $LASTEXITCODE): $result"
    }
    return $result
}

function New-SecurePassword {
    # Generates a 32-character alphanumeric password via System.Security.Cryptography
    $rng   = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $bytes = New-Object byte[] 24
    $rng.GetBytes($bytes)
    return [Convert]::ToBase64String($bytes) -replace '[+/=]', 'x'
}

function Protect-DsnFile {
    param([string]$Path)
    # Restrict ACL: remove Everyone/Users, keep SYSTEM + Administrators only
    $acl = Get-Acl -Path $Path
    $acl.SetAccessRuleProtection($true, $false)

    $systemRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        'SYSTEM', 'FullControl', 'Allow')
    $adminRule  = New-Object System.Security.AccessControl.FileSystemAccessRule(
        'Administrators', 'FullControl', 'Allow')

    $acl.AddAccessRule($systemRule)
    $acl.AddAccessRule($adminRule)
    Set-Acl -Path $Path -AclObject $acl
    Write-Log "ACL restricted on $Path (SYSTEM + Administrators only)."
}

function Wait-PgReady {
    param([int]$TimeoutSeconds = 30)
    Write-Log "Waiting for PostgreSQL to accept connections (timeout ${TimeoutSeconds}s)..."
    $pgIsReady = Join-Path $PG_BIN_DIR 'pg_isready.exe'
    $deadline  = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $out = & $pgIsReady -h 127.0.0.1 -p $PG_PORT 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Log "PostgreSQL is accepting connections."
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "PostgreSQL did not become ready within ${TimeoutSeconds} seconds."
}

function Assert-InstallerHash {
    <#
    .SYNOPSIS
        Verifies the SHA256 hash of an installer file before execution.
    .DESCRIPTION
        Computes the SHA256 hash of the file at FilePath and compares it
        against ExpectedHash (case-insensitive hex string). Terminates the
        script with a non-zero exit code and a clear error message if the
        hashes do not match — supply-chain protection per HEAR-078.
    #>
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string]$ExpectedHash
    )

    Write-Log "Verifying SHA256 integrity of: $FilePath"

    if (-not (Test-Path $FilePath)) {
        Write-Log "Installer file not found for hash verification: $FilePath" 'ERROR'
        exit 1
    }

    $actualHash = (Get-FileHash -Path $FilePath -Algorithm SHA256).Hash.ToUpperInvariant()
    $expected   = $ExpectedHash.ToUpperInvariant()

    if ($actualHash -ne $expected) {
        Write-Log "SHA256 MISMATCH — installer integrity check FAILED." 'ERROR'
        Write-Log "  Expected : $expected" 'ERROR'
        Write-Log "  Actual   : $actualHash" 'ERROR'
        Write-Log "The downloaded file may be corrupted or tampered with." 'ERROR'
        Write-Log "Installation aborted. Delete the file and retry." 'ERROR'
        exit 1
    }

    Write-Log "SHA256 integrity check PASSED: $actualHash"
}

# ─── Step 1: Check for existing installation ──────────────────────────────────

Write-Log "=== AYE Hear PostgreSQL Runtime Provisioning (ADR-0006) ==="
Write-Log "Install root : $InstallDir"
Write-Log "PG bin dir   : $PG_BIN_DIR"
Write-Log "PG data dir  : $PG_DATA_DIR"
Write-Log "Service name : $PG_SERVICE_NAME"

$pgAlreadyProvisioned = (Test-Path (Join-Path $PG_DATA_DIR 'PG_VERSION')) -and
                        (Test-Path $DSN_FILE)

if ($pgAlreadyProvisioned -and -not $Force) {
    Write-Log "PostgreSQL data directory and DSN file already exist. Skipping provisioning." 'INFO'
    Write-Log "Use -Force to re-provision (DESTRUCTIVE: deletes existing data)." 'WARN'

    # Still ensure service is running
    $svc = Get-Service -Name $PG_SERVICE_NAME -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -ne 'Running') {
        Write-Log "Service '$PG_SERVICE_NAME' is stopped; starting..."
        Start-Service -Name $PG_SERVICE_NAME
        Wait-PgReady
    }
    Write-Log "Provisioning skipped — existing installation is intact."
    exit 0
}

# ─── Step 2: Ensure PG binaries ───────────────────────────────────────────────

$initdbExe = Join-Path $PG_BIN_DIR 'initdb.exe'

if (-not (Test-Path $initdbExe)) {
    Write-Log "PostgreSQL binaries not found at $PG_BIN_DIR. Preparing installation..."

    # Resolve installer path
    if ($BundledPgInstaller -and (Test-Path $BundledPgInstaller)) {
        $pgSetupExe = $BundledPgInstaller
        Write-Log "Using bundled installer: $pgSetupExe"
        # ── Integrity check: verify SHA256 before any execution ───────────
        Assert-InstallerHash -FilePath $pgSetupExe -ExpectedHash $PG_INSTALLER_SHA256
    } else {
        # Try sibling 'pg-installer' folder relative to this script or AppBinDir
        $candidateDirs = @(
            (Join-Path $PSScriptRoot "..\..\build\installer\pg-installer"),
            (Join-Path $AppBinDir   'pg-installer')
        )
        $pgSetupExe = $null
        foreach ($dir in $candidateDirs) {
            $found = Get-ChildItem -Path $dir -Filter "postgresql-${PG_VERSION}*-windows-x64.exe" `
                     -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { $pgSetupExe = $found.FullName; break }
        }

        if ($pgSetupExe) {
            Write-Log "Found cached installer: $pgSetupExe"
            # ── Integrity check: verify SHA256 before any execution ────────
            Assert-InstallerHash -FilePath $pgSetupExe -ExpectedHash $PG_INSTALLER_SHA256
        }

        if (-not $pgSetupExe) {
            Write-Log "No bundled installer found. Downloading from EDB..." 'WARN'
            $downloadDir = Join-Path $env:TEMP 'ayehear-pg-install'
            New-Item -ItemType Directory -Path $downloadDir -Force | Out-Null
            $pgSetupExe  = Join-Path $downloadDir "postgresql-${PG_VERSION}-windows-x64.exe"

            Write-Log "Downloading: $PG_DOWNLOAD_URL"
            # Use BITS for resume support; fall back to WebClient
            try {
                Import-Module BitsTransfer -ErrorAction Stop
                Start-BitsTransfer -Source $PG_DOWNLOAD_URL -Destination $pgSetupExe -ErrorAction Stop
                Write-Log "Download complete via BITS."
            } catch {
                Write-Log "BITS unavailable, using WebClient..." 'WARN'
                $wc = New-Object System.Net.WebClient
                $wc.DownloadFile($PG_DOWNLOAD_URL, $pgSetupExe)
                Write-Log "Download complete via WebClient."
            }

            # ── Integrity check: verify SHA256 before any execution ────────
            Assert-InstallerHash -FilePath $pgSetupExe -ExpectedHash $PG_INSTALLER_SHA256
        }
    }

    Write-Log "Installing PostgreSQL silently to $InstallDir\pgsql ..."
    # EDB installer flags:
    #   --mode unattended     silent, no prompts
    #   --prefix              PG binaries path
    #   --datadir             data directory (we init ourselves to control encoding)
    #   --serverport          port (5433 avoids conflict with existing local PG)
    #   --superpassword       temp superuser pw — we rotate after initdb
    #   --servicename         Windows service name
    #   --install_runtimes 0  skip VC++ redistributable if already present
    $tempSuperPw = New-SecurePassword

    $pgInstallArgs = @(
        '--mode', 'unattended',
        '--prefix',              (Join-Path $InstallDir 'pgsql'),
        '--datadir',             $PG_DATA_DIR,
        '--serverport',          "$PG_PORT",
        '--superpassword',       $tempSuperPw,
        '--servicename',         $PG_SERVICE_NAME,
        '--install_runtimes',    '1',
        '--enable_acledit',      '0',
        '--enable_script_permissions', '0'
    )

    # Log install command WITHOUT the superpassword argument (security: never log credentials)
    $logArgs = $pgInstallArgs | Where-Object { $_ -ne $tempSuperPw }
    Write-Log "Running: $pgSetupExe $($logArgs -join ' ') --superpassword <REDACTED>"
    $proc = Start-Process -FilePath $pgSetupExe -ArgumentList $pgInstallArgs `
                          -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0) {
        throw "PostgreSQL EDB installer failed with exit code $($proc.ExitCode)"
    }
    Write-Log "PostgreSQL binaries installed."

    # Stop the service temporarily — we reconfigure before final start
    $svc = Get-Service -Name $PG_SERVICE_NAME -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq 'Running') {
        Stop-Service -Name $PG_SERVICE_NAME -Force
        Write-Log "Service stopped for reconfiguration."
    }
} else {
    Write-Log "PostgreSQL binaries found at $PG_BIN_DIR. Skipping binary install."
}

# ─── Step 3: initdb (first-time or forced re-init) ────────────────────────────

$pgVersionFile = Join-Path $PG_DATA_DIR 'PG_VERSION'
if ((Test-Path $pgVersionFile) -and -not $Force) {
    Write-Log "Data directory already initialized ($PG_DATA_DIR). Skipping initdb."
} else {
    if ($Force -and (Test-Path $PG_DATA_DIR)) {
        Write-Log "FORCE flag set — removing existing data directory." 'WARN'
        Remove-Item -Recurse -Force $PG_DATA_DIR
    }

    New-Item -ItemType Directory -Path $PG_DATA_DIR -Force | Out-Null

    Write-Log "Initializing PostgreSQL data directory..."
    Invoke-Pg 'initdb' @(
        '-D', $PG_DATA_DIR,
        '-U', 'postgres',
        '--encoding', 'UTF8',
        '--lc-collate', 'C',
        '--lc-ctype', 'C',
        '--locale-provider', 'libc',
        '--auth-local',   'md5',
        '--auth-host',    'md5'
    )
    Write-Log "initdb complete."
}

# ─── Step 4: Enforce loopback-only in postgresql.conf ─────────────────────────

$pgConf = Join-Path $PG_DATA_DIR 'postgresql.conf'
if (Test-Path $pgConf) {
    $conf = Get-Content $pgConf -Raw

    # Set listen_addresses = 'localhost'  (loopback-only per ADR-0006)
    $conf = $conf -replace "(?m)^#?\s*listen_addresses\s*=.*$",
                            "listen_addresses = 'localhost'   # AYE Hear: loopback-only (ADR-0006)"

    # Set port
    $conf = $conf -replace "(?m)^#?\s*port\s*=.*$",
                            "port = $PG_PORT"

    Set-Content -Path $pgConf -Value $conf -Encoding UTF8
    Write-Log "postgresql.conf updated: listen_addresses=localhost, port=$PG_PORT"
}

# ─── Step 5: Register Windows service (if not already registered) ────────────

$svc = Get-Service -Name $PG_SERVICE_NAME -ErrorAction SilentlyContinue
if (-not $svc) {
    Write-Log "Registering Windows service '$PG_SERVICE_NAME'..."
    Invoke-Pg 'pg_ctl' @(
        'register',
        '-N', $PG_SERVICE_NAME,
        '-D', $PG_DATA_DIR,
        '-S', 'auto',           # Auto-start on boot
        '-w'                    # Wait for service to start
    )
    Write-Log "Service '$PG_SERVICE_NAME' registered."
} else {
    Write-Log "Service '$PG_SERVICE_NAME' already registered."
}

# ─── Step 6: Start service and wait for readiness ────────────────────────────

Write-Log "Starting service '$PG_SERVICE_NAME'..."
Start-Service -Name $PG_SERVICE_NAME -ErrorAction SilentlyContinue
Wait-PgReady -TimeoutSeconds 30

# ─── Step 7: Create app user, database and generate per-install DSN ──────────

# Generate a per-installation password (never committed, never a static default)
$appPassword = New-SecurePassword

$psqlExe = Join-Path $PG_BIN_DIR 'psql.exe'

# Use -h and -p to connect via TCP (loopback); -U postgres is the superuser created by initdb/EDB
function Invoke-Psql {
    param([string]$Sql, [string]$Db = 'postgres')
    $args_ = @('-h', '127.0.0.1', '-p', "$PG_PORT", '-U', 'postgres', '-d', $Db,
               '-c', $Sql, '-t', '-q')
    Write-Log "  psql: $Sql"
    $result = & $psqlExe @args_ 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "  psql output: $result" 'ERROR'
        throw "psql command failed (exit $LASTEXITCODE) SQL=[$Sql] DB=[$Db]: $result"
    }
    return $result
}

# We connect via TCP (loopback) and rely on a temporary trust entry in pg_hba.conf
# for the initial provisioning queries. The trust line is removed in Step 9.
$pgHba = Join-Path $PG_DATA_DIR 'pg_hba.conf'
if (Test-Path $pgHba) {
    $hba = Get-Content $pgHba -Raw
    # Allow trust for loopback setup operations (temporarily, we tighten after)
    $setupLine = "host    all             postgres        127.0.0.1/32            trust`n"
    if ($hba -notmatch 'ayehear-setup-trust') {
        $hba = $setupLine + "# ayehear-setup-trust (removed after provisioning)`n" + $hba
        Set-Content -Path $pgHba -Value $hba -Encoding UTF8
        # Reload config
        Invoke-Pg 'pg_ctl' @('-D', $PG_DATA_DIR, 'reload') | Out-Null
        Write-Log "pg_hba.conf updated for setup (trust loopback for postgres)."
    }
}

# Create role
Invoke-Psql "DO `$`$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$PG_APP_USER') THEN
    CREATE ROLE $PG_APP_USER LOGIN PASSWORD '$appPassword';
  ELSE
    ALTER ROLE $PG_APP_USER WITH LOGIN PASSWORD '$appPassword';
  END IF;
END `$`$;"

# Create database (idempotent: skip if it already exists)
Invoke-Psql "DO `$`$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '$PG_APP_DB') THEN
    PERFORM dblink_exec('dbname=postgres', 'CREATE DATABASE $PG_APP_DB OWNER $PG_APP_USER ENCODING ''UTF8''');
  END IF;
END `$`$;" 2>&1 | Out-Null
# Simpler: attempt creation and ignore already-exists error (exit code 1 is expected on duplicate)
$createOut = & $psqlExe -h 127.0.0.1 -p $PG_PORT -U postgres -d postgres `
                        -c "CREATE DATABASE $PG_APP_DB OWNER $PG_APP_USER ENCODING 'UTF8'" 2>&1
if ($LASTEXITCODE -ne 0 -and ($createOut -join '') -match 'already exists') {
    Write-Log "Database '$PG_APP_DB' already exists — skipping creation."
} elseif ($LASTEXITCODE -ne 0) {
    Write-Log "CREATE DATABASE failed: $($createOut -join ' ')" 'ERROR'
    throw "CREATE DATABASE $PG_APP_DB failed (exit $LASTEXITCODE): $($createOut -join ' ')"
} else {
    Write-Log "Database '$PG_APP_DB' created."
}

# Grant
Invoke-Psql "GRANT ALL PRIVILEGES ON DATABASE $PG_APP_DB TO $PG_APP_USER;"

# ─── Step 8: Persist DSN securely ─────────────────────────────────────────────

New-Item -ItemType Directory -Path $RUNTIME_DIR -Force | Out-Null

$dsn = "postgresql://${PG_APP_USER}:${appPassword}@127.0.0.1:${PG_PORT}/${PG_APP_DB}"
Set-Content -Path $DSN_FILE -Value $dsn -Encoding UTF8 -NoNewline
Protect-DsnFile -Path $DSN_FILE
Write-Log "DSN written and protected: $DSN_FILE"

# ─── Step 9: Restore restrictive pg_hba.conf ─────────────────────────────────

if (Test-Path $pgHba) {
    $hba = Get-Content $pgHba -Raw
    # Remove setup-trust lines
    $hba = $hba -replace "host    all             postgres        127\.0\.0\.1/32            trust`r?`n", ''
    $hba = $hba -replace "# ayehear-setup-trust \(removed after provisioning\)`r?`n", ''
    Set-Content -Path $pgHba -Value $hba -Encoding UTF8
    Invoke-Pg 'pg_ctl' @('-D', $PG_DATA_DIR, 'reload') | Out-Null
    Write-Log "pg_hba.conf restored to production settings."
}

# ─── Step 10: Schema migrations ───────────────────────────────────────────────

Write-Log "Running schema migrations via AYE Hear Python bootstrap..."
$python = Join-Path $AppBinDir '_internal\python.exe'
if (-not (Test-Path $python)) {
    # Fallback: find python in PATH
    $python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
}

if ($python -and (Test-Path $python)) {
    $env:AYEHEAR_DB_DSN = $dsn
    Write-Log "  Python: $python"
    $migrOutput = & $python -c @"
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(r'$python'), '..'))
from ayehear.storage.database import DatabaseBootstrap, DatabaseConfig
cfg = DatabaseConfig(dsn=os.environ['AYEHEAR_DB_DSN'])
db  = DatabaseBootstrap(cfg)
db.bootstrap()
print('Migrations applied successfully.')
"@ 2>&1
    Write-Log "  $migrOutput"
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Migration bootstrap failed (exit $LASTEXITCODE). Output: $migrOutput" 'ERROR'
        Write-Log "See log for details: $LOG_FILE" 'ERROR'
        throw "Schema migration failed (exit $LASTEXITCODE). Check log: $LOG_FILE"
    } else {
        Write-Log "Schema migrations applied."
    }
} else {
    Write-Log "Python runtime not found at '$python' — cannot run schema migrations." 'ERROR'
    throw "Python runtime not found. Expected: $python. Schema migrations could not be applied."
}

Remove-Item Env:\AYEHEAR_DB_DSN -ErrorAction SilentlyContinue

# ─── Done ─────────────────────────────────────────────────────────────────────

Write-Log "=== PostgreSQL provisioning complete ==="
Write-Log "  Service   : $PG_SERVICE_NAME  (port $PG_PORT)"
Write-Log "  Data dir  : $PG_DATA_DIR"
Write-Log "  DSN file  : $DSN_FILE"
Write-Log "  Log       : $LOG_FILE"
Write-Log "  App user  : $PG_APP_USER"
Write-Log "Next: AYE Hear startup will validate DB health on first launch."
