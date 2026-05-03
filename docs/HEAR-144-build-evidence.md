# HEAR-144 Build Evidence — Release 0.6.1

**Date:** 2026-04-22
**Role:** AYEHEAR_DEVOPS
**Task:** HEAR-144
**Version:** 0.6.1
**Status:** BUILD COMPLETE ✅

---

## Summary

HEAR-144 delivers the AYE Hear installer v0.6.1 after successful integration of HEAR-141
(AdaptiveTranscriptionQueue + WAV persistence privacy config) and HEAR-142 (security review).
Blockers from previous run (HEAR-145 speaker defaults, HEAR-146 async queue wiring,
HEAR-147 protocol no-DB behavior, HEAR-148 action-item extraction) were resolved in
prior tasks (HEAR-145–HEAR-148 all COMPLETED).

This build also resolves three new regressions found during quality gate validation:

1. **test_116/117/118 CPU-defer flakiness**: `_get_cpu_pct()` ≥ 80% during full suite
   caused `ProtocolEngine.generate()` to return deferred snapshots without `trace_store`,
   `review_queue`, or `action_item_quality`. Fixed by `monkeypatch` autouse fixture in
   `TestGenerateQualityIntegration`, `TestGenerateReviewQueueIntegration`,
   `TestGenerateTraceStoreIntegration`.

2. **test_085 AC1/AC3/AC5 vs. HEAR-147 conflict**: `_update_protocol_live` had been
   changed by HEAR-147 to append transcript lines into the protocol panel (no-DB path),
   which violates HEAR-085 AC1/AC3/AC5. Reverted to always delegate to
   `_refresh_protocol_display()` — which correctly shows `[DEGRADED]` without DB.

3. **test_075 stale assertions**: `TestUpdateProtocolLive` and
   `TestAppendTranscriptLineIntegration` were asserting the old append-to-protocol
   behaviour. Updated to assert the HEAR-085-compliant `[DEGRADED]` output.

---

## Version Changes

| File | Before | After |
|------|--------|-------|
| `pyproject.toml` | `0.6.0` | `0.6.1` |
| `src/ayehear/__init__.py` | `0.5.5` | `0.6.1` |

---

## Bug Fixes Applied in This Build

| File | Fix |
|------|-----|
| `src/ayehear/app/window.py` | `_update_protocol_live` reverted to always call `_refresh_protocol_display()` (HEAR-085 AC1/AC3/AC5 compliance) |
| `tests/test_hear_116_quality_engine_integration.py` | `TestGenerateQualityIntegration`: autouse `_no_cpu_defer` fixture |
| `tests/test_hear_117_confidence_review_integration.py` | `TestGenerateReviewQueueIntegration`: autouse `_no_cpu_defer` fixture |
| `tests/test_hear_118_protocol_traceability_integration.py` | `TestGenerateTraceStoreIntegration`: autouse `_no_cpu_defer` fixture |
| `tests/test_hear_075_protocol_export.py` | `TestUpdateProtocolLive` + `TestAppendTranscriptLineIntegration`: assertions updated to HEAR-085 contract |

---

## Test Results

**Run date:** 2026-04-22
**Scope:** Full pytest suite (excluding DB-dependent tests)
**Command:** `pytest -q --ignore=tests/test_database.py --ignore=tests/test_hear_049_installer_postgres.py --ignore=tests/test_hear_077_pg_failfast.py --ignore=tests/test_hear_081_listen_addresses.py --ignore=tests/test_hear_111_db_shutdown.py --ignore=tests/test_hear_068_enrollment_real.py`

| Result | Count |
|--------|-------|
| PASSED | 730 |
| FAILED | 2 (pre-existing) |
| Duration | ~6:32 min |

**Pre-existing failures (not caused by HEAR-144):**
- `test_hear_074_enrollment_workflow.py::TestParseSpeakerRaw::test_two_fields`
- `test_hear_074_enrollment_workflow.py::TestParseSpeakerRaw::test_single_field`

Both are tracked in the backlog and unchanged since HEAR-139.

---

## Build Artifacts

| Artifact | Path | Size |
|---------|------|------|
| Installer | `dist\AyeHear-Setup-0.6.1.exe` | 1150.7 MB |
| Installer SHA256 | `A3380673052B83D490D69BEFF4B1D50B3294CE0B2DCE4CF053B0843E14EDE0D2` | — |
| Bundle dir | `dist\AyeHear\` | — |
| Bundled model.bin | `dist\AyeHear\_internal\models\whisper\TheChola\whisper-large-v3-turbo-german-faster-whisper\model.bin` | 1542.9 MB |
| Version file | `dist\AyeHear\aye_hear_version.txt` | `0.6.1` |
| Build log | `build\build-log-0.6.1.txt` | — |
| Build date | 2026-04-22 22:07 | — |
| PyInstaller | 6.19.0 | — |
| Python (build) | 3.12.10 | — |
| Inno Setup | 6.x | — |
| Compression | lzma2/ultra64 + SolidCompression | — |

**Note on installer size:** 1150.7 MB — lzma2/ultra64 solid compression applied to the
1542.9 MB int8 model.bin plus all application binaries. SHA256 verified post-build.

---

## ASR Model

| Property | Value |
|----------|-------|
| HuggingFace ID | `TheChola/whisper-large-v3-turbo-german-faster-whisper` |
| Architecture | Whisper Large v3 Turbo (CTranslate2 / faster-whisper) |
| model.bin size | 1542.9 MB |
| Access | Gated — HF account + ToS required |
| Offline-first | ✅ local_files_only, no runtime downloads |

---

## Offline-First Verification

- Model loaded from `dist\AyeHear\_internal\models\whisper\...` (bundled)
- No HuggingFace network calls at runtime
- PostgreSQL bundled locally (runtime install)
- No telemetry, no cloud audio transmission
