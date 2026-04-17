# AYE Hear v0.3.0 — Release Notes

**Release Date:** 2026-04-16
**Build:** SAM_ULTRA · Python 3.12.10 · PyInstaller 6.19.0 · Inno Setup 6.7.1
**Installer:** `AyeHear-Setup-0.3.0.exe` (341.5 MB)
**Architect Gate:** HEAR-065 PASS
**Quality Gates:** All green (178/178 tests passing)

---

## What's New in v0.3.0

### Speaker Edit & Enrollment Fixes (HEAR-059 / HEAR-060)

**HEAR-059 — Speaker Name Parsing Fixed**
- `_parse_speaker_raw()` now correctly strips status tokens (`| pending enrollment`, `| enrolled`)
  before saving participant names to the database.
- Previously, status suffixes were accidentally persisted as part of the name.
- All existing `NameCorrectionAudit` entries for affected meetings are self-healing on next
  transcription cycle.

**HEAR-060 — Enrollment Flow Corrected**
- Removed `_name_to_stub_audio()` stub that silently reported "enrolled" without capturing audio.
- Enrollment items correctly remain in `pending enrollment` state until real voice capture is
  implemented in Phase 2.
- No false-positive enrollment confirmations will appear to users.

### ASR Diagnostics System (HEAR-061)

A new structured diagnostics layer for the ASR (Automatic Speech Recognition) pipeline:

| Diagnostic Code | Meaning | UI Action |
|---|---|---|
| `not_installed` | faster-whisper package absent | Warning shown once per session |
| `model_load_error` | Model files could not be loaded | Warning with path hint |
| `inference_error` | Runtime error during transcription | Warning with restart advice |
| `empty_result` | Whisper returned no text | Silent (may be silence) |

- New `AsrUnavailableError` exception — distinct from generic `RuntimeError`.
- `TranscriptResult.asr_diagnostic` field carries the code for downstream logging.
- Each warning type is shown **at most once per session** to avoid UI spam.

### Application Logging (HEAR-066)

- Persistent log file at `C:\AyeHear\logs\ayehear.log` (created at first launch).
- `RotatingFileHandler`: 5 MB per file, 3 backups retained (`ayehear.log`, `.1`, `.2`, `.3`).
- All subsystem loggers (ASR, database, speaker manager, protocol engine) write to this file.
- Fallback: if `C:\AyeHear\logs\` is not writable, logs go to `.\logs\ayehear.log` (dev/CI).
- First log entry records the resolved log path and `frozen` (packaged) status.

### Offline ASR Bundle Fix (HEAR-062)

- Whisper `base` model (138.5 MB) is now **bundled inside the installer**.
- No internet connection required at first launch — fully offline per ADR-0001.
- Bundle path detection: `sys._MEIPASS/models/whisper/base/model.bin` (packaged) with
  fallback to HuggingFace Hub cache (dev machines).

---

## Version History

| Version | Date | Key Changes |
|---|---|---|
| 0.1.0 | 2026-04-08 | Initial scaffold — PySide6 shell, PostgreSQL integration, speaker enrollment |
| 0.2.0 | 2026-04-16 | MicLevelWidget, installer PostgreSQL setup, security gate PASS, BitLocker waiver |
| **0.3.0** | **2026-04-16** | Speaker edit/enrollment fixes, ASR diagnostics, application logging, ASR bundle fix |

---

## Known Limitations

- **Live mic + real Whisper model**: Validated in unit tests; end-to-end hardware acceptance
  on target device is deferred (HEAR-063-R1).
- **Code signing**: Installer is unsigned. Windows SmartScreen prompt will appear on first
  run. Click "More info → Run anyway" (acceptable for internal deployment per security policy).
- **Uninstaller RunOnceId**: Cosmetic Inno Setup warning — non-functional impact.

---

## Files in This Release

| File | SHA256 | Size |
|---|---|---|
| `AyeHear-Setup-0.3.0.exe` | `8C4CBED9...` | 341.5 MB |
| `AyeHear.exe` (bundle) | `A5FBB787...` | 15.8 MB |
| `models/whisper/base/model.bin` | `D01C3014...` | 138.5 MB |

Full checksums: `ops-release/v0.3.0/checksums-sha256.txt`
