---
owner: AYEHEAR_DEVOPS
status: active
updated: 2026-04-16
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

The Inno Setup and NSIS installers automate this entire lifecycle.
The Inno Setup `[Run]` section (and NSIS `ExecWait` calls) execute
`tools\scripts\Install-PostgresRuntime.ps1` automatically during installation.

**What the script does:**
1. Checks for existing binaries at `C:\AyeHear\pgsql`; installs EDB PostgreSQL 16 silently if absent.
2. Runs `initdb` on `C:\AyeHear\data\pg16` (UTF-8, C locale, md5 auth).
3. Enforces `listen_addresses = 'localhost'` in `postgresql.conf` (ADR-0006 loopback gate).
4. Registers the `AyeHearDB` Windows service with auto-start via `pg_ctl register`.
5. Starts the service and waits for readiness via `pg_isready`.
6. Generates a **per-installation random password** for the `ayehear` role.
7. Persists the DSN to `C:\AyeHear\runtime\pg.dsn` with ACL restricted to SYSTEM + Administrators.
8. Creates the `ayehear` database and applies schema migrations.

**Manual re-provisioning (e.g. after clean uninstall):**

```powershell
# Requires administrator privileges
.\tools\scripts\Install-PostgresRuntime.ps1
# Force re-init (DESTRUCTIVE — deletes existing data):
.\tools\scripts\Install-PostgresRuntime.ps1 -Force
```

**Offline / enterprise deployment (bundled installer):**

Place `postgresql-16.x-windows-x64.exe` in `build\installer\pg-installer\` before
building the installer, then uncomment the `[Files]` source line for the bundled installer
in `ayehear-installer.iss`. The provisioning script will prefer the bundled file over
downloading.

```powershell
# Pass the path explicitly:
.\tools\scripts\Install-PostgresRuntime.ps1 `
    -BundledPgInstaller "C:\Temp\postgresql-16.4-1-windows-x64.exe"
```

> **Security:** PostgreSQL binds `loopback only (127.0.0.1)` on port `5433`.
> Never expose or change the bind address. See ADR-0006.

### 2.1a Startup Health Check

A dedicated health-check script validates the runtime before the application is allowed to launch.
The installer runs it automatically as the final `[Run]` step.

```powershell
# Manual invocation (e.g. after service restart)
.\tools\scripts\Start-AyeHearRuntime.ps1

# Silent mode (exit code only — useful in CI / scripted environments)
.\tools\scripts\Start-AyeHearRuntime.ps1 -Silent
echo "Exit: $LASTEXITCODE"  # 0 = all checks passed
```

**Checks performed:**

| # | Check | Pass condition |
|---|-------|----------------|
| 1 | Windows service registered | `AyeHearDB` service present |
| 2 | Service running | Status = Running (auto-start attempted) |
| 3 | DSN file accessible | `C:\AyeHear\runtime\pg.dsn` readable |
| 4 | PostgreSQL accepts connections | `pg_isready -h 127.0.0.1 -p 5433` → exit 0 |
| 5 | loopback-only (ADR-0006) | `SHOW listen_addresses` ∈ {localhost, 127.0.0.1, ::1} |
| 6 | Schema baseline present | `meetings` table exists in `public` schema |

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

> **Status:** `tools\scripts\Start-AyeHearRuntime.ps1` — **IMPLEMENTED** (HEAR-049).
> See Section 2.1a for full documentation and check matrix.

The installer calls this script automatically as the final step. For manual
pre-launch verification:

```powershell
.\tools\scripts\Start-AyeHearRuntime.ps1
# Exit 0 = ready; Exit 1 = diagnostic output + remediation hints
```

---

## 5. NSIS Installer

### 5.1 Generate Installer (Inno Setup — primary)

```powershell
# Full build: PyInstaller bundle + Inno Setup installer
.\tools\scripts\Build-WindowsPackage.ps1 -BuildInstaller -Clean
# Output: dist\AyeHear-Setup-<version>.exe
```

The installer script bundles the provisioning scripts automatically from
`tools\scripts\`. No additional preparation is required unless you want an
offline/bundled PG installer (see Section 2.1 — Offline path).

### 5.2 Generate NSIS Installer (legacy baseline)

```powershell
makensis /V2 build\installer\ayehear-installer.nsi
# Output: dist\AyeHear-Setup-<version>.exe
```

Current repository baseline:

- `build\installer\ayehear-installer.iss` (Inno Setup 6, primary) packages the PyInstaller `dist\AyeHear\` bundle and **automates PostgreSQL 16 provisioning** via `Install-PostgresRuntime.ps1` and `Start-AyeHearRuntime.ps1`.
- `build\installer\ayehear-installer.nsi` (NSIS 3, legacy) provides the same provisioning automation via `ExecWait` calls.
- Both installer scripts copy `tools\scripts\Install-PostgresRuntime.ps1` and `tools\scripts\Start-AyeHearRuntime.ps1` to `%APPDATA%\AYE Hear\scripts\` for post-install use.

### 5.3 Installer Responsibilities (Updated — HEAR-049)

| Phase             | Action                                                      | Status    |
| ----------------- | ----------------------------------------------------------- | --------- |
| Pre-install check | Detect existing version; prompt for upgrade                 | Planned   |
| Install PG        | Silent PostgreSQL 16 install to `C:\AyeHear\pgsql`          | **Done**  |
| Init data dir     | Run `initdb` if data directory does not exist               | **Done**  |
| Register service  | Register `AyeHearDB` Windows service via `pg_ctl register`  | **Done**  |
| Copy app bundle   | Copy PyInstaller `onedir` output to `C:\AyeHear\app`        | **Done**  |
| Copy scripts      | Copy provisioning + health-check scripts to `%APPDATA%`     | **Done**  |
| Start service     | Start `AyeHearDB` service + wait for `pg_isready`           | **Done**  |
| Run migrations    | Launch once-off migration bootstrap via Python              | **Done**  |
| Health check      | Run `Start-AyeHearRuntime.ps1` post-install                 | **Done**  |
| Create shortcuts  | Desktop + Start Menu shortcuts                              | **Done**  |
| Uninstall         | Stop service, optionally preserve data dir (user choice)    | **Done**  |

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

- [ ] PostgreSQL initialization verified from zero-state (`Install-PostgresRuntime.ps1` completes without error)
- [ ] `Start-AyeHearRuntime.ps1` exits 0 on clean machine (all 6 checks PASS)
- [ ] Startup health check passes end-to-end
- [ ] Schema migrations apply cleanly on a fresh data directory
- [ ] **Clean-machine validation:** Run the full installer on a fresh Windows 11 VM and confirm application-ready state (documented in release evidence artifact)

**Clean-machine validation checklist (Windows 11 VM):**

```powershell
# 1. Run installer (no PostgreSQL pre-installed on the VM)
.\dist\AyeHear-Setup-<version>.exe

# 2. After install completes, verify health check passes
& "$env:APPDATA\AYE Hear\scripts\Start-AyeHearRuntime.ps1"
# Expected: "=== ALL CHECKS PASSED ==="

# 3. Confirm service
Get-Service AyeHearDB | Select-Object Name, Status, StartType
# Expected: AyeHearDB, Running, Automatic

# 4. Confirm DSN file exists with restricted ACL
Get-Acl "C:\AyeHear\runtime\pg.dsn" | Format-List
# Expected: only SYSTEM and Administrators have access

# 5. Launch AyeHear.exe and confirm meeting list loads without errors
```

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
**Task:** HEAR-017, HEAR-049
