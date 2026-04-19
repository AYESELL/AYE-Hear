# HEAR-110 — Validation Package Build Evidence

**Task:** HEAR-110 — Version bump and validation package build  
**Build Date:** 2026-04-19  
**Build Time:** ~13:00 – 13:20 UTC+2  
**DevOps Role:** AYEHEAR_DEVOPS  
**Branch:** feature/phase-1b-implementation-updates

---

## Build Summary

| Item | Value |
|------|-------|
| Product Version | 0.5.3 |
| Python | 3.12.10 |
| PyInstaller | 6.19.0 |
| Installer Tool | Inno Setup 6 |
| Platform | Windows 11 |
| ASR Model | Whisper small (Systran/faster-whisper-small) |
| Build Script | `tools/scripts/Build-WindowsPackage.ps1 -BuildInstaller -Clean` |
| Build Exit Code | 0 (success) |

---

## Version Bump

| File | Old Version | New Version |
|------|------------|-------------|
| `pyproject.toml` | 0.5.2 | 0.5.3 |
| `src/ayehear/__init__.py` | 0.5.2 | 0.5.3 |

Scope: Patch version bump only — no feature changes, no dependency updates, no scope expansion.

---

## Artifacts

| Artifact | Size | SHA256 |
|----------|------|--------|
| `dist\AyeHear-Setup-0.5.3.exe` | 1053.02 MB | `C2963D6153AF709694940442B115BEF5ED6423961E0BAB1D994D2BBD490CE287` |
| `dist\AyeHear\AyeHear.exe` | 17.56 MB | `CFD7B2CA44916E5F211F2854E45F617E84F67D32B4DA1161BD7A5B28C24F6854` |
| `dist\AyeHear\` (bundle total) | 1439.8 MB | — |

---

## Bundle Validation

- [x] `AyeHear.exe` vorhanden (`dist\AyeHear\AyeHear.exe`)
- [x] `aye_hear_version.txt` enthält `0.5.3`
- [x] Whisper `small/model.bin` im Bundle vorhanden (461.15 MB)
- [x] Inno Setup Installer erzeugt (`AyeHear-Setup-0.5.3.exe`)
- [x] Build-Exit-Code: 0 (kein Fehler)

---

## Whisper Model Staging

Whisper `small` Modell war zum Build-Zeitpunkt bereits vorgestaged (kein Re-Download erforderlich):

```
Staged: config\models\whisper\small\
  - config.json     (1.0 KB)
  - model.bin       (461.15 MB)  ← Systran/faster-whisper-small
  - tokenizer.json  (2.1 MB)
  - vocabulary.txt  (0.4 MB)
```

---

## Build-Warnungen (non-blocking)

Alle Warnungen sind identisch mit vorherigen Builds (HEAR-100, HEAR-104) und bekannt als non-blocking:

- `psycopg_binary` collect_submodules Warning: erfordert `psycopg` Import vor `psycopg_binary` — bekanntes PyInstaller-Verhalten, runtime nicht betroffen
- `psycopg.types.text` / `psycopg.types.date` hidden import not found — psycopg runtime-Funktionalität unbeeinträchtigt
- `pysqlite2` / `MySQLdb` hidden imports not found — erwartet, da nur PostgreSQL+psycopg verwendet wird

---

## Next Steps

Dieses Build ist der Validierungskandidat für:

- **HEAR-111:** Installed packaged E2E validation (AYEHEAR_QA)
- **HEAR-112:** Final readiness reconciliation (AYEHEAR_ARCHITECT)
