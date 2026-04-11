---
owner: AYEHEAR_DEVOPS
status: active
updated: 2026-04-09
category: operational-runbook
---

# AYE Hear – Windows Packaging & Runtime Operations Runbook

**Scope:** Local PostgreSQL lifecycle, PyInstaller packaging, NSIS installer generation,
startup health checks and release readiness baseline.

**Related ADRs:** ADR-0002 (Stack), ADR-0006 (PostgreSQL local deployment), ADR-0008 (Hardware profiles)

---

## 1. Prerequisites

| Requirement               | Version | Notes                                                               |
| ------------------------- | ------- | ------------------------------------------------------------------- |
| Windows 10/11             | 22H2+   | 64-bit mandatory                                                    |
| Python                    | 3.12    | Exact minor for V1 packaging and release validation                 |
| PostgreSQL                | 16.x    | Lock per ADR-0006; local installer-managed instance                 |
| PyInstaller               | ≥ 6.9   | `pip install pyinstaller` in CI/build venv                          |
| NSIS                      | 3.x     | [nsis.sourceforge.io](https://nsis.sourceforge.io) — PATH-available |
| Visual Studio Build Tools | 2022    | Required for `psycopg[binary]` and `sounddevice` wheels             |
| Git                       | 2.40+   | For CI and version tagging                                          |

---

## 2. Local PostgreSQL Lifecycle (Production Runtime)

### 2.1 Install (Installer-managed — end-user path)

The NSIS installer handles this automatically. Manual steps for reference:

```powershell
# Download PostgreSQL 16 Windows installer
# https://www.enterprisedb.com/downloads/postgres-postgresql-downloads

# Silent install to known local path
postgresql-16.x-windows-x64.exe --mode unattended `
  --prefix "C:\AyeHear\pgsql" `
  --datadir "C:\AyeHear\data\pg16" `
  --serverport 5433 `
  --superpassword "" `  # Set via NSIS-generated local secret
  --servicename "AyeHearDB"
```

> **Security:** PostgreSQL binds `loopback only (127.0.0.1)` on port `5433`.
> Never expose or change the bind address. See ADR-0006.

### 2.2 Initialize Data Directory (First Run)

The application startup performs this check automatically (see Section 4).
For manual operations:

```powershell
# Check if DB is initialized
$pgData = "C:\AyeHear\data\pg16"
if (-not (Test-Path "$pgData\PG_VERSION")) {
    & "C:\AyeHear\pgsql\bin\initdb.exe" -D $pgData `
        -U ayehear `
        --encoding UTF8 `
        --lc-collate C `
        --locale-provider libc
}
```

### 2.3 Start / Stop Service

```powershell
# Start
Start-Service -Name "AyeHearDB"
# or via pg_ctl:
& "C:\AyeHear\pgsql\bin\pg_ctl.exe" start -D "C:\AyeHear\data\pg16" -l "C:\AyeHear\logs\pg.log"

# Stop
Stop-Service -Name "AyeHearDB"
& "C:\AyeHear\pgsql\bin\pg_ctl.exe" stop -D "C:\AyeHear\data\pg16" -m fast
```

### 2.4 Apply Schema Migrations (First Launch and Upgrades)

Migrations live in `src/ayehear/storage/migrations/`.
The application bootstrap applies pending migrations automatically on startup.

Manual trigger:

```powershell
.\.venv\Scripts\Activate.ps1
python -m ayehear.storage.migrate --apply
```

### 2.5 Startup Health Check

On every application launch the runtime verifies:

1. PostgreSQL service is running
2. DSN connection is established (< 5 s timeout)
3. Schema version matches the bundled migration baseline
4. Hardware profile is detected and an appropriate runtime tier is selected (ADR-0008)

If any check fails, the application shows a diagnostic dialog and blocks the main window until the issue is resolved.

---

## 3. PyInstaller Build

### 3.1 Build Steps (Local Machine)

```powershell
# 1. Activate clean build venv
python -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller>=6.9

# 2. Run PyInstaller with the project spec
pyinstaller build\aye-hear.spec --noconfirm --clean

# Output: dist\AyeHear\AyeHear.exe  (onedir mode)
```

### 3.2 PyInstaller Spec Template

The spec is maintained at `build/aye-hear.spec`. Key decisions:

| Option            | Value                                             | Reason                                           |
| ----------------- | ------------------------------------------------- | ------------------------------------------------ |
| `onedir`          | yes                                               | Allows PG binaries to co-exist alongside the app |
| `console=False`   | yes                                               | Hides console window in production               |
| `uac_admin=False` | yes                                               | No admin rights required for runtime             |
| Hidden imports    | `ayehear.storage`, `psycopg`, `PySide6.QtWidgets` | Avoid dynamic-import misses                      |
| Data includes     | `config/`, `src/ayehear/storage/migrations/`      | Bundled at runtime path                          |

### 3.3 Version Injection

The build pipeline injects the version from `pyproject.toml` into the bundled binary:

```powershell
$version = (python -c "import tomllib; f=open('pyproject.toml','rb'); d=tomllib.load(f); print(d['project']['version'])")
pyinstaller build\aye-hear.spec --noconfirm --clean
```

The version string is embedded in `aye_hear_version.txt` inside the bundle and displayed in the About dialog.

---

## 4. Startup Health Check Script

> **Status:** `tools\scripts\Start-AyeHearRuntime.ps1` is planned for a future DevOps task.
> Until it is implemented, use the manual sequence below.

Manual pre-launch check (PowerShell):

```powershell
# Ensure PG service is up
$svc = Get-Service -Name "AyeHearDB" -ErrorAction SilentlyContinue
if (-not $svc -or $svc.Status -ne 'Running') {
    Write-Warning "PostgreSQL service not running — attempting start"
    Start-Service -Name "AyeHearDB"
    Start-Sleep -Seconds 3
}

# Verify connection via DatabaseBootstrap
$env:AYEHEAR_DB_DSN = "postgresql://ayehear:@127.0.0.1:5433/ayehear"
python -c "
from ayehear.storage import DatabaseBootstrap, DatabaseConfig
cfg = DatabaseConfig(dsn='postgresql://ayehear:@127.0.0.1:5433/ayehear')
db  = DatabaseBootstrap(cfg)
db.bootstrap()
print('DB check passed')
"
if ($LASTEXITCODE -ne 0) {
    [System.Windows.Forms.MessageBox]::Show(
        'Cannot connect to local database. Please check the AyeHearDB service.',
        'AYE Hear – Database Error',
        'OK',
        'Error')
    exit 1
}
```

---

## 5. NSIS Installer

### 5.1 Generate Installer

```powershell
makensis /V2 build\installer\ayehear-installer.nsi
# Output: dist\AyeHear-Setup-<version>.exe
```

Current repository baseline:

- `build\installer\ayehear-installer.nsi` packages the PyInstaller `dist\AyeHear\` onedir bundle into a Windows installer.
- The installer copies the app to `C:\AyeHear\app`, creates desktop and Start Menu shortcuts, and registers an uninstaller.
- PostgreSQL provisioning, service registration and migration bootstrap remain release-readiness checks and are not yet automated by this NSIS baseline.

### 5.2 Installer Responsibilities

| Phase             | Action                                                     |
| ----------------- | ---------------------------------------------------------- |
| Pre-install check | Detect existing version; prompt for upgrade                |
| Install PG        | Silent PostgreSQL 16 install to `C:\AyeHear\pgsql`         |
| Init data dir     | Run `initdb` if data directory does not exist              |
| Register service  | Register `AyeHearDB` Windows service via `pg_ctl register` |
| Copy app bundle   | Copy PyInstaller `onedir` output to `C:\AyeHear\app`       |
| Start service     | Start `AyeHearDB` service                                  |
| Run migrations    | Launch once-off migration bootstrap                        |
| Create shortcuts  | Desktop + Start Menu shortcuts                             |
| Uninstall         | Stop service, optionally preserve data dir (user choice)   |

---

## 6. Release Checklist

Before cutting a release:

### 6.1 Security Pre-Flight (MUST complete before any other step)

Run the BitLocker evidence script on the **target deployment machine** and
attach the output file to the release ticket (QA-DP-01):

```powershell
# Captures manage-bde -status evidence and exits 0 on Pass
.\tools\scripts\Invoke-BitLockerPreFlight.ps1
```

- [ ] **QA-DP-01 — BitLocker pre-flight passed** (`[PASS]` in evidence file)
  — evidence file attached to release ticket.
  _If failed: obtain AYEHEAR_SECURITY written waiver before proceeding._
  Script: `tools\scripts\Invoke-BitLockerPreFlight.ps1` | ADR: ADR-0009 | Task: HEAR-035

### 6.2 Build & Test

- [ ] All HEAR Phase-1B developer tasks are DONE
- [ ] `pytest tests -q` passes fully (≥ 75 % coverage)
- [ ] PyInstaller build succeeds locally on both CPU-only and CUDA-capable hardware
- [ ] NSIS installer tested on a clean Windows 11 VM

### 6.3 Deployment Validation

- [ ] PostgreSQL initialization verified from zero-state
- [ ] Startup health check passes end-to-end
- [ ] Schema migrations apply cleanly on a fresh data directory

### 6.4 Artifacts & Tagging

- [ ] `dist\AyeHear-Setup-<version>.exe` uploaded to release artifacts
- [ ] BitLocker evidence file archived with release artifacts
- [ ] `CHANGELOG.md` updated
- [ ] Git tag created: `release/v<version>`

---

## 7. Known Operational Risks

| Risk                                            | Mitigation                                                     |
| ----------------------------------------------- | -------------------------------------------------------------- |
| PostgreSQL service fails to start               | Startup dialog blocks launch; user guided to restart service   |
| Corrupt data directory after power loss         | PG WAL protects most cases; manual recovery guide TBD (V2)     |
| DLL conflicts in onedir bundle                  | Lock PySide6 and psycopg wheel versions in `requirements.txt`  |
| GPU detection causes crash on CPU-only machines | ADR-0008: always fall back to CPU tier; never hard-require GPU |
| Schema version mismatch after partial upgrade   | Migration bootstrap is idempotent; re-running is safe          |

---

## 8. Development vs. Production Runtime

| Aspect            | Development                                 | Production                       |
| ----------------- | ------------------------------------------- | -------------------------------- |
| PostgreSQL source | Docker Compose (`infra/docker-compose.yml`) | Installer-managed local service  |
| Bind address      | `127.0.0.1:5432`                            | `127.0.0.1:5433`                 |
| Service name      | n/a (container)                             | `AyeHearDB`                      |
| App launch        | `python -m ayehear.app`                     | `AyeHear.exe` from onedir bundle |
| Migrations        | `python -m ayehear.storage.migrate`         | Automatic on app startup         |

---

**Maintained by:** AYEHEAR_DEVOPS  
**ADR references:** ADR-0002, ADR-0006, ADR-0008  
**Task:** HEAR-017
