# HEAR-129 — Patch Release Candidate Build Evidence

**Task:** HEAR-129 — Build patch release candidate 0.5.5 after HEAR-124/125 fixes  
**Build Date:** 2026-04-19  
**DevOps Role:** AYEHEAR_DEVOPS  
**Branch:** feature/phase-1b-implementation-updates

---

## Build Summary

| Item | Value |
|------|-------|
| Product Version | 0.5.5 |
| Python | 3.12.10 |
| PyInstaller | 6.19.0 |
| Installer Tool | Inno Setup 6 |
| Platform | Windows 11 |
| ASR Model | Whisper small (Systran/faster-whisper-small) |
| Build Script | `tools/scripts/Build-WindowsPackage.ps1 -BuildInstaller -Clean` |
| Build Exit Code | 0 (success) |
| Build Log | `build/build-log-0.5.5.txt` |

---

## Version Bump

| File | Old Version | New Version |
|------|------------|-------------|
| `pyproject.toml` | 0.5.4 | 0.5.5 |
| `src/ayehear/__init__.py` | 0.5.4 | 0.5.5 |

**Scope:** Patch version bump — persistence lifecycle hotfix (HEAR-124) and Start-AyeHearRuntime script repair (HEAR-125) on top of quality-first wave (HEAR-115..HEAR-118).

---

## Included Fixes (0.5.4 → 0.5.5)

| Task | Fix |
|------|-----|
| HEAR-124 | Meeting lifecycle FK persistence defect — soft-fallback to local-only on DB commit failure |
| HEAR-125 | Start-AyeHearRuntime.ps1 — inline-if syntax error repair and pg-binary discovery fix |

**Prior quality-first wave (already in 0.5.4):**

| Task | Feature |
|------|---------|
| HEAR-115 | ASR Profile Tuning |
| HEAR-116 | Quality Engine Integration |
| HEAR-117 | Confidence Review Integration |
| HEAR-118 | Protocol Traceability Layer (evidence-linked, local-only) |

---

## Artifacts

| Artifact | Size | SHA256 |
|----------|------|--------|
| `dist\AyeHear-Setup-0.5.5.exe` | 1053.14 MB | `4EF5311DE8C9EFC77CF6EFBBA3527AB16D2077D990D192FA9EC9BCDD2ED08D6D` |
| `dist\AyeHear\AyeHear.exe` | 17.59 MB | `4EB22618CA6868CE526D7F279036CAAF1E60799BD5F4CB200C22930C67C0DE8F` |
| `dist\AyeHear\` (bundle total) | 1439.8 MB | — |

---

## Bundle Validation

- [x] `AyeHear.exe` vorhanden (`dist\AyeHear\AyeHear.exe`)
- [x] `aye_hear_version.txt` enthält `0.5.5`
- [x] Whisper `small/model.bin` im Bundle vorhanden (461.1 MB)
- [x] Inno Setup Installer erzeugt (`AyeHear-Setup-0.5.5.exe`)
- [x] Build-Exit-Code: 0 (kein Fehler)
- [x] `Build-WindowsPackage.ps1 -Clean` ausgeführt (frischer Build)

---

## Whisper Model Staging

Whisper `small` Modell war zum Build-Zeitpunkt bereits vorgestaged (kein Re-Download erforderlich):

```
Staged: config\models\whisper\small\
  - model.bin (461.1 MB)  ← Systran/faster-whisper-small
```

---

## Test Suite Validation

Die Test-Suite wurde auf dem Branch vor dem Build validiert:

```
.venv\Scripts\python.exe -m pytest tests/ -q
```

Relevant für 0.5.5:
- `tests/test_hear_124_meeting_lifecycle_fk.py` — Regression-Coverage für FK-Persistence-Fallback (HEAR-124)
- Gesamte Quality-First-Suite (test_hear_107, test_hear_108, test_hear_115..test_hear_118) grün

---

## Predecessor Comparison

| Item | 0.5.4 (HEAR-122) | 0.5.5 (HEAR-129) |
|------|-----------------|-----------------|
| Installer SHA256 | `A7837B170CD066B42...` | `4EF5311DE8C9EFC77...` |
| EXE SHA256 | `0C74029E42FD6BD22D6A...` | `4EB22618CA6868CE52...` |
| Installer Size | 1053.13 MB | 1053.14 MB |
| Bundle Size | 1439.8 MB | 1439.8 MB |
| HEAR-124 Fix | ❌ | ✅ |
| HEAR-125 Fix | ❌ | ✅ |

---

## Readiness for Downstream Tasks

| Task | Status |
|------|--------|
| HEAR-126 — QA Re-run installed E2E | ✅ Baseline bereit |
| HEAR-127 — Security Recheck | ✅ Baseline bereit |
| HEAR-128 — Architect Readiness Reconciliation | Wartet auf HEAR-126 + HEAR-127 |

---

**Conclusion:** Build 0.5.5 ist erfolgreich abgeschlossen. Installer und Bundle-Artefakte sind bereit für die QA-installed-E2E-Validierung (HEAR-126).
