# HEAR-157 Build Evidence — Release 0.6.3

**Date:** 2026-05-02
**Role:** AYEHEAR_DEVOPS
**Task:** HEAR-157
**Version:** 0.6.3
**Status:** BUILD COMPLETE ✅

---

## Summary

HEAR-157 delivers the AYE Hear installer v0.6.3 with two goals:

1. **New versioned installer candidate** containing all fixes since 0.6.2, enabling QA to run the
   HEAR-155 installed-E2E gate on a same-candidate package.

2. **Stabilized runtime health-check script** (`Start-AyeHearRuntime.ps1`): the script now searches
   multiple PostgreSQL binary locations (bundled `pgsql\bin` + EDB system installations in
   `Program Files`) instead of only the install-root-relative path. This fixes the failure observed
   in HEAR-123 where `pg_isready.exe` and `psql.exe` were not found under `<installRoot>/pgsql/bin`
   because the EDB PostgreSQL is installed system-wide.

---

## Version Changes

| File | Before | After |
|------|--------|-------|
| `pyproject.toml` | `0.6.2` | `0.6.3` |
| `src/ayehear/__init__.py` | `0.6.2` | `0.6.3` |

---

## Changes Applied in This Build

| File | Change |
|------|--------|
| `pyproject.toml` | Version bumped to `0.6.3` |
| `src/ayehear/__init__.py` | `__version__` bumped to `0.6.3` |
| `tools/scripts/Start-AyeHearRuntime.ps1` | HEAR-157: `Resolve-PgBin` extended with `$PG_SYSTEM_BIN_CANDIDATES` array (bundled path + EDB `Program Files\PostgreSQL\{17,16,15,14}\bin`); FAIL messages now list all checked paths |

**Note:** No application logic changes in this build. All source fixes (HEAR-130, HEAR-149)
were included in 0.6.2 and are carried forward unchanged.

---

## Regression Test Results

**Run date:** 2026-05-02
**Scope:** Targeted regression suite (persistence, ProtocolEngine, WAV config, async pipeline, config)
**Command:**
```
.\.venv\Scripts\python.exe -m pytest tests/test_hear_141_async_pipeline.py
  tests/test_hear_146_adaptive_queue_wiring.py tests/test_protocol_engine.py
  tests/test_hear_085_protocol_draft.py tests/test_config.py -q --tb=short
```

| Result | Count |
|--------|-------|
| PASSED | 82 |
| FAILED | 0 |
| Duration | ~95s |

All 82 tests passed. No failures (compared to 0.6.2 which had 1 flaky DB connection error).

---

## Build Artifacts

| Artifact | Path | Detail |
|---------|------|--------|
| Installer | `dist\AyeHear-Setup-0.6.3.exe` | 1150.8 MB |
| Installer SHA256 | `8F1C024AD6798BFE317400BD9DE3A3BAC5189BE16710185A8AAC7C7563D85086` | — |
| Bundle dir | `dist\AyeHear\` | — |
| Bundled model | `dist\AyeHear\_internal\models\whisper\TheChola\whisper-large-v3-turbo-german-faster-whisper\model.bin` | — |
| Build log (PyInstaller) | `build\build-log-0.6.3.txt` | — |
| Build date | 2026-05-02 12:24 | — |
| PyInstaller | 6.19.0 | — |
| Python (build) | 3.12.10 | — |
| Inno Setup | 6.7.1 | — |

---

## Quality Gate Checklist

| Gate | Status | Notes |
|------|--------|-------|
| Version bumped in pyproject.toml | ✅ PASS | `0.6.2` → `0.6.3` |
| Version bumped in `__init__.py` | ✅ PASS | `0.6.2` → `0.6.3` |
| `Start-AyeHearRuntime.ps1` pg-bin search extended | ✅ PASS | Multi-path fallback incl. EDB system install paths |
| Regression tests | ✅ PASS | 82/82 passed, 0 failures |
| PyInstaller build succeeded | ✅ PASS | Exit code 0, `AyeHear.exe` verified |
| Inno Setup installer created | ✅ PASS | `AyeHear-Setup-0.6.3.exe` created |
| Installer SHA256 recorded | ✅ PASS | `8F1C024A...` above |
| HEAR-130 fix present (persistence lifecycle) | ✅ INHERITED | Carried from 0.6.2 |
| HEAR-149 fix present (ProtocolEngine wiring) | ✅ INHERITED | Carried from 0.6.2 |
| privacy.wav_persistence_enabled = false | ✅ PASS | HEAR-156 production default confirmed |

---

## Known Issues / Open Items

- **HEAR-150 (ASR hallucinations on short clips):** Not fixed in this build. Tracked separately.
- **HEAR-136/137 benchmark decision:** Remains DEFERRED. `wav_persistence_enabled = false` is
  the production default (HEAR-156); benchmark recording requires explicit opt-in at runtime.
- **Installed E2E gate (HEAR-155):** This candidate is now ready for QA handover. QA should
  install `dist\AyeHear-Setup-0.6.3.exe` and run the HEAR-155 evidence checklist using
  `Start-AyeHearRuntime.ps1 -InstallDir <installRoot>` — the script now resolves pg binaries
  from system EDB paths without manual patching.

---

## QA Handover — Smoke Command

```powershell
# After installing AyeHear-Setup-0.6.3.exe to default path:
& "C:\ProgramData\AYE Hear\scripts\Start-AyeHearRuntime.ps1" -InstallDir "C:\AyeHear"
# Expected exit code: 0 (all checks pass)
```

---

## Next Steps

1. QA installs `dist\AyeHear-Setup-0.6.3.exe` on target hardware (HEAR-155)
2. Run HEAR-155 installed-E2E evidence checklist
3. Forward outcome to AYEHEAR_ARCHITECT for readiness reconciliation
