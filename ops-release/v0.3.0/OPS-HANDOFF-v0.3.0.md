# AYE Hear v0.3.0 — Operations Handoff Summary

**Date:** 2026-04-16
**From:** AYEHEAR_DEVOPS
**To:** Operations / Field Deployment Team
**Architect Gate:** HEAR-065 — PASS
**Security Gate:** HEAR-051 / HEAR-056 — APPROVED WITH CONDITIONS (BitLocker waiver HEAR-055)

---

## Release Decision

AYE Hear v0.3.0 is **APPROVED FOR DEPLOYMENT** to internal target machines.

All mandatory quality gates are green. The one approved residual risk (BitLocker on dev
workstation, not on GA target) is covered by signed waiver `deployment-evidence/bitlocker-waiver-20260416.md`.

---

## What Operations Receives

| Artifact | Location | Size |
|---|---|---|
| Windows Installer | `dist/AyeHear-Setup-0.3.0.exe` | 341.5 MB |
| PyInstaller Bundle | `dist/AyeHear/` | 643.9 MB (1073 files) |
| Release Notes | `ops-release/v0.3.0/RELEASE-NOTES-v0.3.0.md` | — |
| Deployment Checklist | `ops-release/v0.3.0/DEPLOYMENT-CHECKLIST-v0.3.0.md` | — |
| SHA256 Checksums | `ops-release/v0.3.0/checksums-sha256.txt` | — |
| Build Warn Log | `ops-release/v0.3.0/warn-aye-hear.txt` | — |

---

## Key Facts for Operations

### Install Path
- Application: `C:\AyeHear\app\`
- Database data: `C:\AyeHear\data\`
- Log file: `C:\AyeHear\logs\ayehear.log` ← **first place to look on failure**

### Runtime Requirements
- Windows 10/11 64-bit, admin rights for install
- PostgreSQL 16 (installed automatically by installer)
- Microphone (WASAPI-compatible, any Windows default device)
- BitLocker on target drive (ADR-0009) — or approved waiver

### No Internet Required
The installer is self-contained. Whisper `base` model (138 MB) is bundled.
No outbound calls at any time (offline-first per ADR-0001).

### Code Signing
Installer is **not code-signed** in this release. Windows SmartScreen will show a warning.
Workaround: "More info" → "Run anyway". This is accepted for internal deployment.
GA signing is planned for a future release.

---

## Quality Gate Summary

| Gate | Status | Evidence |
|---|---|---|
| Unit tests (178/178) | ✅ PASS | `test_run_full.txt` |
| Speaker edit/enrollment fixes | ✅ PASS | HEAR-059, HEAR-060 |
| ASR diagnostics | ✅ PASS | HEAR-061, `test_transcription.py` 14/14 |
| Regression validation | ✅ PASS | HEAR-063, 82/82 targeted tests |
| Architect design gate | ✅ PASS | HEAR-065 |
| Security review | ✅ APPROVED | HEAR-051, HEAR-056 |
| BitLocker evidence | ✅ WAIVER | HEAR-055, `bitlocker-waiver-20260416.md` |
| Version consistency | ✅ PASS | `pyproject.toml`, `__init__.py`, installer all = 0.3.0 |
| ASR bundle completeness | ✅ PASS | `model.bin` 138.5 MB in bundle |
| Application logging | ✅ PASS | `C:\AyeHear\logs\ayehear.log` |

---

## Open Residuals (Non-blocking)

| ID | Description | Risk | Next Step |
|---|---|---|---|
| HEAR-062-R3 | End-to-end packaged EXE smoke test on real hardware | Medium | Phase 2 |
| HEAR-063-R1 | Live mic + real Whisper on target hardware | Medium | Phase 2 |
| HEAR-066-R1 | Code signing of installer | Low | GA milestone |

---

## Handoff Sign-Off

- **AYEHEAR_DEVOPS:** Prepared 2026-04-16 ✅
- **AYEHEAR_ARCHITECT:** Gate HEAR-065 PASS ✅
- **AYEHEAR_SECURITY:** HEAR-056 APPROVED ✅
- **AYEHEAR_QA:** HEAR-063 PASS ✅

Operations may proceed with deployment to target machines.
