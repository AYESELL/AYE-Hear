# HEAR-104 — Release Candidate Build Evidence

**Task:** HEAR-104 — Release candidate installer build for model-comparison cycle  
**Build Date:** 2026-04-18  
**Build Time:** 11:12 – 11:24 UTC+2  
**DevOps Role:** AYEHEAR_DEVOPS  
**Branch:** feature/phase-1b-implementation-updates

---

## Build Summary

| Item | Value |
|------|-------|
| Product Version | 0.4.3 |
| Python | 3.12.10 |
| PyInstaller | 6.19.0 |
| Installer Tool | Inno Setup 6 |
| Platform | Windows 11 (10.0.26200) |
| ASR Model | Whisper small (Systran/faster-whisper-small) |
| Whisper Snapshot | 536b0662742c02347bc0e980a01041f333bce120 |

---

## Artifacts

| Artifact | Size | SHA256 |
|----------|------|--------|
| `dist\AyeHear-Setup-0.4.3.exe` | 1052.75 MB | `3558DF8E5139F668AD70D0CE41AFA63935F8A4ACEEF883D26BF159371105DCA6` |
| `dist\AyeHear\AyeHear.exe` | 17.48 MB | `E9CBDB371F719B0930550AAA5B30FB9396B833FAE3F433B8BF7AA9FE8680E63E` |
| `dist\AyeHear\` (bundle total) | 1439.7 MB | — |

---

## Bundle Validation

- [x] `AyeHear.exe` vorhanden (`dist\AyeHear\AyeHear.exe`)
- [x] `aye_hear_version.txt` enthält `0.4.3`
- [x] Whisper `small/model.bin` im Bundle vorhanden (461.1 MB)
- [x] Inno Setup Installer erzeugt (`AyeHear-Setup-0.4.3.exe`)
- [x] Build-Exit-Code: 0 (kein Fehler)

---

## Build-Warnungen (non-blocking)

- `psycopg_binary` collect_submodules Warning: benötigt `psycopg` Import vor `psycopg_binary` — bekanntes PyInstaller-Verhalten, runtime nicht betroffen (psycopg_binary DLLs sind korrekt gebündelt)
- `pysqlite2` / `MySQLdb` hidden imports not found — erwartet, da nur PostgreSQL+psycopg verwendet wird

---

## Whisper Model Staging

Das `small` Modell wurde zum Build-Zeitpunkt aus dem HuggingFace-Cache gestaged:

```
Source: C:\Users\sasch\.cache\huggingface\hub\models--Systran--faster-whisper-small\
        snapshots\536b0662742c02347bc0e980a01041f333bce120
Staged: config\models\whisper\small\ (463.6 MB total)
  - config.json     (0 MB)
  - model.bin       (461.1 MB)
  - tokenizer.json  (2.1 MB)
  - vocabulary.txt  (0.4 MB)
```

---

## Startup Prerequisites (für QA-Benchmark-Zyklus)

| Anforderung | Status |
|-------------|--------|
| PostgreSQL Runtime (pgsql/) | Muss bei erstem Start auto-installiert werden |
| Ollama + deepseek-r1:8b | Extern (nicht im Installer) |
| Ollama + qwen3.5:latest | Extern (nicht im Installer) |
| Ollama + mistral:7b | Extern (nicht im Installer) |
| Whisper small (offline) | Im Bundle ✅ |

---

## Übergabe an QA (HEAR-103)

Dieser Build ist bereit für den HEAR-103 QA-Benchmark-Lauf:

1. Installer `AyeHear-Setup-0.4.3.exe` auf Ziel-System installieren
2. Erstem Start PostgreSQL-Init abwarten
3. Test-Meeting aufzeichnen → Transcript-Baseline einfrieren
4. Automatisierten Multi-Model-Replay starten (HEAR-102 implementiert)
5. Vergleichs-Matrix: deepseek-r1 / qwen3.5 / mistral:7b

**Checksums-Datei:** `ops-release/v0.4.3/checksums-sha256.txt`
