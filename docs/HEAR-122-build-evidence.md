# HEAR-122 — Quality-First Release Candidate Build Evidence

**Task:** HEAR-122 — Versioned quality-first release candidate build and evidence  
**Build Date:** 2026-04-19  
**Build Time:** ~16:22 – 17:10 UTC+2  
**DevOps Role:** AYEHEAR_DEVOPS  
**Branch:** feature/phase-1b-implementation-updates

---

## Build Summary

| Item | Value |
|------|-------|
| Product Version | 0.5.4 |
| Python | 3.12.10 |
| PyInstaller | 6.19.0 |
| Installer Tool | Inno Setup 6 |
| Platform | Windows 11 |
| ASR Model | Whisper small (Systran/faster-whisper-small) |
| Build Script | `tools/scripts/Build-WindowsPackage.ps1 -BuildInstaller -Clean` |
| Build Exit Code | 0 (success) |
| Build Log | `build/build-log-0.5.4.txt` |

---

## Version Bump

| File | Old Version | New Version |
|------|------------|-------------|
| `pyproject.toml` | 0.5.3 | 0.5.4 |
| `src/ayehear/__init__.py` | 0.5.3 | 0.5.4 |

Scope: Patch version bump — quality-first wave (HEAR-115..HEAR-118) packaged as new release candidate.

---

## Quality-First Wave Scope (HEAR-115..HEAR-118)

This release candidate packages the complete quality-first feature set:

| Task | Feature |
|------|---------|
| HEAR-115 | ASR Profile Tuning |
| HEAR-116 | Quality Engine Integration |
| HEAR-117 | Confidence Review Integration |
| HEAR-118 | Protocol Traceability Layer (evidence-linked, local-only) |

Test suite validated on branch before build: **219 tests passed**.

---

## Artifacts

| Artifact | Size | SHA256 |
|----------|------|--------|
| `dist\AyeHear-Setup-0.5.4.exe` | 1053.13 MB | `A7837B170CD066B42EBEE0C61A03B59F81A32C48DED7945A657F14093FFA71B6` |
| `dist\AyeHear\AyeHear.exe` | 17.59 MB | `0C74029E42FD6BD22D6A79D6AC29A39E0E7063ABCE5B1C5CF8B0C4EF12E339E7` |
| `dist\AyeHear\` (bundle total) | 1439.8 MB | — |

---

## Bundle Validation

- [x] `AyeHear.exe` vorhanden (`dist\AyeHear\AyeHear.exe`)
- [x] `aye_hear_version.txt` enthält `0.5.4`
- [x] Whisper `small/model.bin` im Bundle vorhanden (461.1 MB)
- [x] Inno Setup Installer erzeugt (`AyeHear-Setup-0.5.4.exe`)
- [x] Build-Exit-Code: 0 (kein Fehler)

---

## Whisper Model Staging

Whisper `small` Modell war zum Build-Zeitpunkt bereits vorgestaged (kein Re-Download erforderlich):

```
Staged: config\models\whisper\small\
  - config.json     (1.0 KB)
  - model.bin       (461.1 MB)  ← Systran/faster-whisper-small
  - tokenizer.json  (2.1 MB)
  - vocabulary.txt  (0.4 MB)
```

---

## Build-Warnungen (non-blocking)

Alle Warnungen sind identisch mit vorherigen Builds (HEAR-100, HEAR-104, HEAR-110) und bekannt als non-blocking:

- `psycopg_binary` collect_submodules Warning: erfordert `psycopg` Import vor `psycopg_binary` — bekanntes PyInstaller-Verhalten, runtime nicht betroffen
- `psycopg.types.text` / `psycopg.types.date` hidden import not found — psycopg runtime-Funktionalität unbeeinträchtigt
- `pysqlite2` / `MySQLdb` hidden imports not found — erwartet, da nur PostgreSQL+psycopg verwendet wird

---

## Predecessor Chain

| Version | Task | Notes |
|---------|------|-------|
| 0.5.1 | HEAR-100 | First installer build |
| 0.5.2 | HEAR-104 | Feature additions |
| 0.5.3 | HEAR-110 | Validation candidate (HEAR-112 readiness authority) |
| **0.5.4** | **HEAR-122** | **Quality-first wave candidate (this build)** |

---

## Next Step

HEAR-123 (AYEHEAR_QA): Installed-package E2E evidence for 0.5.4 quality-first candidate.

Evidence to be stored under `deployment-evidence/hear-122/`.
