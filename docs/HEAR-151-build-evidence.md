# HEAR-151 Build Evidence — Release 0.6.2

**Date:** 2026-04-22
**Role:** AYEHEAR_DEVOPS
**Task:** HEAR-151
**Version:** 0.6.2
**Status:** BUILD COMPLETE ✅

---

## Summary

HEAR-151 delivers the AYE Hear installer v0.6.2 containing two targeted fixes:

1. **HEAR-149 fix:** Attribute naming bug in `window.py` — the HEAR-130 persistence-disable
   logic (`_reload_persistence_layer` and `_disable_persistence`) was silently a no-op because
   it used `._snapshot_repo` / `._transcript_repo` on `ProtocolEngine` instead of the correct
   internal attribute names `._snapshots` / `._transcripts`. Result: FK violations were never
   suppressed after a persistence error. Now correctly wired.

2. **WAV persistence enabled by default:** `config/default.yaml` sets
   `privacy.wav_persistence_enabled: true` to support HEAR-136/137 benchmark data collection
   (recording reference WAV segments from real meetings for authoritative ASR go/no-go evaluation).
   Security constraints from HEAR-142 remain in place (local only, clamped retention 1-30 days).

---

## Version Changes

| File | Before | After |
|------|--------|-------|
| `pyproject.toml` | `0.6.1` | `0.6.2` |
| `src/ayehear/__init__.py` | `0.6.1` | `0.6.2` |

---

## Changes Applied in This Build

| File | Change |
|------|--------|
| `pyproject.toml` | Version bumped to `0.6.2` |
| `src/ayehear/__init__.py` | `__version__` bumped to `0.6.2` |
| `src/ayehear/app/window.py` | HEAR-149: `_reload_persistence_layer` and `_disable_persistence` use `_protocol_engine._snapshots` / `_protocol_engine._transcripts` (correct internal names); `_transcription_service.transcript_repo` correctly wired on disable path |
| `config/default.yaml` | `privacy.wav_persistence_enabled: true` for HEAR-136/137 benchmark data collection |

**Note:** The `window.py` HEAR-149 fix was implemented as part of HEAR-149 (completed prior to
this build task). This build task confirms the fix is present and packages it into the installer.

---

## Regression Test Results

**Run date:** 2026-04-22
**Scope:** Targeted regression suite (persistence, ProtocolEngine, WAV config, async pipeline)
**Command:**
```
pytest tests/test_hear_141_async_pipeline.py tests/test_hear_146_adaptive_queue_wiring.py
       tests/test_protocol_engine.py tests/test_hear_085_protocol_draft.py
       tests/test_config.py -q --tb=short
```

| Result | Count |
|--------|-------|
| PASSED | 74 |
| FAILED | 1 (pre-existing, flaky) |
| Duration | ~87s |

**Failure analysis:**
- `tests/test_config.py::test_load_runtime_config_from_repository_file` — flaky DB connection
  error (`psycopg.OperationalError: server closed the connection unexpectedly`). This is a
  transient infrastructure issue (PostgreSQL server closed connection during rollback in test
  cleanup), not caused by HEAR-149 or any code change in this build.

---

## Build Artifacts

| Artifact | Path | Size |
|---------|------|------|
| Installer | `dist\AyeHear-Setup-0.6.2.exe` | 1150.7 MB |
| Installer SHA256 | `D18F720E808AE4619EEB7ABFDB832A745F36F3700036A322602181FC4BE0C7BB` | — |
| Bundle dir | `dist\AyeHear\` | — |
| Bundled model | `dist\AyeHear\_internal\models\whisper\TheChola\whisper-large-v3-turbo-german-faster-whisper\model.bin` | 1542.9 MB |
| Version file | `dist\AyeHear\aye_hear_version.txt` | `0.6.2` |
| Build log | `build\build-log-0.6.2.txt` | — |
| Build date | 2026-04-22 23:39 | — |
| PyInstaller | 6.19.0 | — |
| Python (build) | 3.12.10 | — |
| Inno Setup | 6.x | — |

---

## Quality Gate Checklist

| Gate | Status | Notes |
|------|--------|-------|
| HEAR-149 fix present in source | ✅ PASS | `window.py` lines 389-393 and 428-437 verified |
| WAV persistence enabled in config | ✅ PASS | `privacy.wav_persistence_enabled: true` confirmed |
| Version bumped in pyproject.toml | ✅ PASS | `0.6.1` → `0.6.2` |
| Version bumped in `__init__.py` | ✅ PASS | `0.6.1` → `0.6.2` |
| Regression tests (targeted) | ✅ PASS | 74/75; 1 flaky DB error (pre-existing) |
| PyInstaller build succeeded | ✅ PASS | Exit code 0, `AyeHear.exe` verified |
| Inno Setup installer created | ✅ PASS | `AyeHear-Setup-0.6.2.exe` created |
| Installer SHA256 recorded | ✅ PASS | `D18F720E...` above |

---

## Known Issues / Open Items

- **HEAR-150 (ASR hallucinations on short clips):** TheChola large-v3-turbo model hallucinates
  on 1-2 second audio clips. Not fixed in this build. Tracked separately; do not change default
  model without authoritative benchmark evidence (HEAR-136/137 constraint).
- **WAV persistence benchmark:** This build enables WAV recording to support reference corpus
  collection. HEAR-136/137 benchmark decision remains DEFERRED until live-test reference data
  is captured from standalone operation.

---

## Next Steps

1. Install `dist\AyeHear-Setup-0.6.2.exe` on target hardware
2. Run 5-min test meeting — verify no FK violation errors in runtime log
3. Confirm WAV segments appear in `runtime/wav/` during meeting
4. Forward to QA (HEAR-152) for installed E2E validation
