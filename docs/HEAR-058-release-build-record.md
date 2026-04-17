---
owner: AYEHEAR_DEVOPS
status: complete
task: HEAR-058
version: 0.2.0
date: 2026-04-16
category: release-artifact
---

# HEAR-058 – Release Candidate Build Record: v0.2.0

## Build Summary

| Field | Value |
|-------|-------|
| Version | **0.2.0** |
| Build Date | 2026-04-16 |
| Build Host | SAM_ULTRA (Windows 11 10.0.26200) |
| Python | 3.12.10 |
| PyInstaller | 6.19.0 |
| Inno Setup | 6.7.1 (user install) |
| Branch | `feature/phase-1b-implementation-updates` |
| Task | HEAR-058 |

---

## Artifacts

| Artifact | Path | Size | Timestamp |
|----------|------|------|-----------|
| App Bundle (onedir) | `dist\AyeHear\` | 361.4 MB (1061 files) | 2026-04-16 14:39 |
| Executable | `dist\AyeHear\AyeHear.exe` | 15.6 MB | 2026-04-16 14:39:54 |
| Version marker | `dist\AyeHear\aye_hear_version.txt` | `0.2.0` | 2026-04-16 14:39 |
| **Windows Installer** | `dist\AyeHear-Setup-0.2.0.exe` | **94.6 MB** | 2026-04-16 14:41:34 |

---

## Build Steps Executed

1. **Clean** – `dist/` und `build/__pycache__` entfernt
2. **PyInstaller Bundle** – `Build-WindowsPackage.ps1 -Clean`
   - Spec: `build\aye-hear.spec` (existing, validated)
   - Output: `dist\AyeHear\AyeHear.exe` ✅
   - Version file written: `dist\AyeHear\aye_hear_version.txt` = `0.2.0` ✅
3. **Inno Setup Installer** – `Build-WindowsPackage.ps1 -BuildInstaller`
   - Script: `build\installer\ayehear-installer.iss`
   - Output: `dist\AyeHear-Setup-0.2.0.exe` ✅
   - Warning: `[UninstallRun]` entries without `RunOnceId` (non-blocking, cosmetic)

---

## Quality Checks at Build Time

| Check | Result |
|-------|--------|
| `pyproject.toml` version = `0.2.0` | ✅ |
| `AyeHear.exe` present in bundle | ✅ |
| `aye_hear_version.txt` = `0.2.0` | ✅ |
| Installer filename = `AyeHear-Setup-0.2.0.exe` | ✅ |
| No build errors (exit code 0) | ✅ |
| Inno compile warning (RunOnceId) | ⚠️ non-blocking |

---

## Security & Compliance Evidence References

| Document | Status |
|----------|--------|
| HEAR-051 Security Gate Review | docs/HEAR-051-security-gate-review.md |
| HEAR-055 BitLocker Waiver | deployment-evidence/bitlocker-waiver-20260416.md |
| HEAR-056 Security Recheck (HEAR-051-R1 CLOSED) | docs/HEAR-056-security-recheck.md |
| HEAR-052 Release Decision | docs/HEAR-052-release-decision.md |

---

## Operations Handoff Notes

**Installer for deployment testing:** `dist\AyeHear-Setup-0.2.0.exe` (94.6 MB)

**Prerequisites on target machine:**
- Windows 10/11 64-bit (22H2+)
- Administrator rights for installer execution
- Internet access for PostgreSQL 16 download (or bundled PG installer in `build\installer\pg-installer\`)

**Post-install validation:**
```powershell
# Health check (run as admin after install)
C:\AyeHear\tools\scripts\Start-AyeHearRuntime.ps1 -HealthCheckOnly
```

**Installer scope:**
- Installs app to `C:\AyeHear\app\`
- Installs and configures PostgreSQL 16 (loopback-only, per ADR-0006)
- Generates per-installation random DB password, ACL-restricted DSN at `C:\AyeHear\runtime\pg.dsn`
- BitLocker preflight validated via HEAR-055/056 (waiver on record for dev workstation)

---

## Known Residuals / Non-Blockers

| ID | Description | Severity |
|----|-------------|----------|
| INNO-WARN-001 | `[UninstallRun]` entries lack `RunOnceId` — Inno Setup cosmetic warning, no functional impact | Low |

---

**Signed off by:** AYEHEAR_DEVOPS  
**Date:** 2026-04-16
