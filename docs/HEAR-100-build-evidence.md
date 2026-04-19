# HEAR-100 — Release Build Evidence

**Task:** HEAR-100 — Installer rebuild and package validation after model updates  
**Build Date:** 2026-04-19  
**Build Time:** ~08:30 – 09:00 UTC+2  
**DevOps Role:** AYEHEAR_DEVOPS  
**Branch:** feature/phase-1b-implementation-updates

---

## Build Summary

| Item | Value |
|------|-------|
| Product Version | 0.5.2 |
| Python | 3.12.10 |
| PyInstaller | 6.19.0 |
| Installer Tool | Inno Setup 6.7.1 |
| Platform | Windows 11 |
| ASR Model | Whisper small (Systran/faster-whisper-small) |
| Build Script | `tools/scripts/Build-WindowsPackage.ps1 -BuildInstaller -Clean` |
| Build Exit Code | 0 (success) |

---

## Artifacts

| Artifact | Size | SHA256 |
|----------|------|--------|
| `dist\AyeHear-Setup-0.5.2.exe` | 1052.92 MB | `D2BECDE155F7F9CEB224F02E25A729DDDC391870412B154EDC005B085F987D0C` |
| `dist\AyeHear\AyeHear.exe` | 17.56 MB | `61BA6AC542E8105740A454D9AE29BCED3C5C5045290D5DBFCBA9461EE39C088D` |

---

## Bundle Validation

- [x] `AyeHear.exe` vorhanden (`dist\AyeHear\AyeHear.exe`)
- [x] `aye_hear_version.txt` enthält `0.5.2`
- [x] Whisper `small/model.bin` im Bundle vorhanden (461.15 MB)
- [x] Inno Setup Installer erzeugt (`AyeHear-Setup-0.5.2.exe`)
- [x] Build-Exit-Code: 0 (kein Fehler)
- [x] Installer-Zielverzeichnis: `C:\AyeHear\app` (per Inno Setup .iss)

---

## Model-Staging-Nachweis

Das Whisper `small` Modell war zum Build-Zeitpunkt bereits vorgestaged:

```
Staged: config\models\whisper\small\
  - config.json     (1.0 KB)
  - model.bin       (461.15 MB)  ← Systran/faster-whisper-small
  - tokenizer.json  (2.1 MB)
  - vocabulary.txt  (0.4 MB)
```

Bundle enthält zusätzlich `whisper/base/` (via `config/`-Verzeichnis-Kopie) als Fallback-Modell.

---

## Build-Warnungen (non-blocking, bekannt)

- `psycopg_binary` collect_submodules Warning — bekanntes PyInstaller-Verhalten, runtime nicht betroffen
- `pysqlite2` / `MySQLdb` hidden imports not found — erwartet, da nur PostgreSQL+psycopg3 verwendet wird
- `psycopg.types.text` / `psycopg.types.date` — Moduls umbenannt in psycopg3, nicht kritisch

Alle Warnungen identisch mit HEAR-104-Build (v0.4.3) — keine Regression.

---

## Test-Ergebnisse

| Test-Suite | Tests | Ergebnis |
|-----------|-------|---------|
| `test_hear_073_install_paths.py` | 9 | ✅ PASSED |
| `test_hear_077_pg_failfast.py` | 13 | ✅ PASSED |
| `test_hear_078_installer_sha256.py` | 23 | ✅ PASSED |
| **Gesamt** | **45** | **✅ 45/45 PASSED** |

---

## Startup Prerequisites

| Anforderung | Status |
|-------------|--------|
| Whisper small (offline ASR) | Im Bundle ✅ |
| PostgreSQL Runtime (pgsql/) | Auto-Init beim ersten Start |
| Fail-Fast bei DB-Fehler | Verifiziert ✅ (HEAR-077 Tests) |
| Install-Root-relative Pfade | Verifiziert ✅ (HEAR-073 Tests) |

---

## Checksums

Aktuelle Checksums in: `ops-release/v0.5.2/checksums-sha256.txt`

```
D2BECDE155F7F9CEB224F02E25A729DDDC391870412B154EDC005B085F987D0C  AyeHear-Setup-0.5.2.exe
61BA6AC542E8105740A454D9AE29BCED3C5C5045290D5DBFCBA9461EE39C088D  AyeHear/AyeHear.exe
```

---

**Erstellt von:** AYEHEAR_DEVOPS  
**Freigabe für:** Deployment / QA-Handoff
