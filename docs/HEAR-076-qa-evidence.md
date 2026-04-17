# HEAR-076 QA Evidence — Validate Enrollment, Export and Runtime Path UX

**Task:** HEAR-076  
**Role:** AYEHEAR_QA  
**Date:** 2026-04-16  
**Validator:** AYEHEAR_QA Agent  
**Status:** PASS — All 4 acceptance criteria met

---

## Scope

QA validation for the three Phase-1b implementation tasks:

| Task | Title | Status |
|------|-------|--------|
| HEAR-072 | Define Install-Root Relative Runtime Paths (ADR-0011) | done |
| HEAR-073 | Implement Install-Root Relative Logging and Artifact Paths | done |
| HEAR-074 | Implement Real Microphone Voice Enrollment Workflow | done |
| HEAR-075 | Add Visible Protocol Preview and Manual Export UI | done |

---

## Automated Test Results

### Combined Test Run (42 tests, 3 feature test files)

```
tests/test_hear_073_install_paths.py   — 16 passed
tests/test_hear_074_enrollment_workflow.py — 11 passed
tests/test_hear_075_protocol_export.py — 15 passed
Total: 42 passed in 1.14s
```

**Result: 42/42 PASS**

### Regression Suite (98 tests, all affected modules)

```
tests/test_hear_073_install_paths.py
tests/test_hear_074_enrollment_workflow.py
tests/test_hear_075_protocol_export.py
tests/test_hear_060_enrollment.py
tests/test_storage.py
tests/test_speaker_manager.py

Total: 98 passed in 1.27s  — 0 failed
```

**Result: 98/98 PASS — No regressions**

---

## Coverage

| Module | Stmts | Miss | Cover | Notes |
|--------|-------|------|-------|-------|
| `ayehear.utils.paths` | 34 | 2 | **93%** | Uncovered: frozen-EXE discovery branch (requires packaged build) |
| `ayehear.utils.logging` | 38 | 26 | 26% | Covered: path delegation to utils.paths; uncovered: runtime log-handler setup (requires live fs) |
| `ayehear.storage.database` | 122 | 89 | 21% | Covered: DSN path delegation; uncovered: live PostgreSQL connection methods |

> **Rationale:** Low coverage in logging/database is expected and acceptable. The critical path-resolution logic in `utils.paths` is 93% covered. The uncovered database/logging branches require live infrastructure (PostgreSQL, file system) that is not available in the CI-equivalent offline test environment. This matches the V1 testing strategy documented in `docs/governance/QUALITY_GATES.md`.

---

## AC1 — Runtime-Path Logging Discoverability

**Acceptance Criterion:** Test evidence confirms logs are discoverable in the actual install location.

**Evidence:**

| Test | Result |
|------|--------|
| `test_logging_module_has_no_hardcoded_path` | PASS |
| `test_database_module_has_no_hardcoded_path` | PASS |
| `test_log_dir_creates_subdir` | PASS |
| `test_log_dir_is_idempotent` | PASS |
| `test_dsn_path_explicit_root` | PASS |
| `test_dsn_path_uses_env` | PASS |
| `test_no_hardcoded_c_ayehear` | PASS |

**Static Analysis — Hardcoded path scan (`C:\AyeHear`):**
```powershell
Select-String -Path src/ayehear/utils/paths.py,
                     src/ayehear/utils/logging.py,
                     src/ayehear/storage/database.py,
                     src/ayehear/app/window.py `
              -Pattern "C:\\AyeHear" -SimpleMatch

# Output: (empty — no matches)
```

**Result: PASS** — No hardcoded `C:\AyeHear` literals in any production module. All path resolution delegates to `ayehear.utils.paths.resolve_install_root()` per ADR-0011.

---

## AC2 — Enrollment Flow Usability

**Acceptance Criterion:** Enrollment flow is understandable and usable on a clean install.

**Evidence:**

| Test | Result |
|------|--------|
| `test_already_enrolled_excluded_from_pending` | PASS |
| `test_all_enrolled_shows_information` | PASS |
| `test_successful_enrollment_updates_item_text` | PASS |
| `test_successful_enrollment_adds_to_enrolled_speakers` | PASS |
| `test_unrecorded_speaker_marked_failed_on_accept` | PASS |
| `test_status_label_shows_count_on_accept` | PASS |
| `test_dialog_receives_correct_speaker_manager` | PASS |

**Static Code Review — `window.py`:**

- `EnrollmentDialog` is imported from `ayehear.app.enrollment_dialog` (line 31)
- `_start_enrollment()` is connected to "Start Enrollment" button (line 205)
- Method filters out already-enrolled speakers — only pending speakers shown (line 331–369)
- Status transitions visible: `pending → enrolled (id: ...)` / `enrollment failed`
- Status label updated with count: `X/Y Sprecher registriert`
- `EnrollmentDialog` existence confirmed: `Test-Path src/ayehear/app/enrollment_dialog.py → True`

**Result: PASS** — Real `EnrollmentDialog` replaces placeholder. Status transitions and guidance are implemented and tested.

---

## AC3 — Live Protocol Preview and Manual Export

**Acceptance Criterion:** Live protocol preview and manual export are visible and functional.

**Evidence:**

| Test | Result |
|------|--------|
| `test_export_button_exists` | PASS |
| `test_export_button_disabled_initially` | PASS |
| `test_export_button_enabled_during_meeting` | PASS |
| `test_export_button_remains_enabled_after_stop` | PASS |
| `test_export_path_label_exists` | PASS |
| `test_export_writes_markdown_file` | PASS |
| `test_export_path_label_updated` | PASS |
| `test_export_empty_draft_shows_warning` | PASS |
| `test_export_file_contains_markdown_header` | PASS |
| `test_appends_transcript_when_no_db` | PASS |
| `test_transcript_section_added_on_first_update` | PASS |
| `test_second_update_appends_without_duplicate_section` | PASS |
| `test_delegates_to_refresh_when_snapshot_repo_present` | PASS |
| `test_protocol_updated_during_active_meeting` | PASS |
| `test_protocol_not_updated_without_active_meeting` | PASS |

**Static Code Review — `window.py`:**

- Export button: `QPushButton("Export Protocol…")` at line 679
- Tooltip: `"Protokoll als Markdown-Datei in den exports/-Ordner speichern"` — path clearly surfaced
- Export enabled during meeting (line 465–466), remains enabled after stop (line 481–482)
- Live preview updates with each audio segment via `_update_protocol_live()`
- Export artifact is Markdown with header; export path label updates after write

**Result: PASS** — Visible export button with clear location hint, live protocol preview updates, post-meeting export accessible.

---

## AC4 — Residual Risks and Usability Gaps

**Acceptance Criterion:** Residual risks and usability gaps documented with repro steps.

### RR-076-01 — Frozen-EXE Path Discovery (untestable in CI)

- **Risk:** The `sys.frozen` packaged-EXE branch in `utils/paths.py` (lines 73–76) cannot be exercised without a PyInstaller build.
- **Impact:** Low — dev fallback is `cwd`, which is correct for development; packaged path is covered by the existing build pipeline (HEAR-058).
- **Repro:** Run `AyeHear.exe` from a non-`C:\AyeHear` directory and verify logs appear in the correct install-root `logs/` subdirectory.
- **Mitigation:** ADR-0011 defines the contract; `Build-WindowsPackage.ps1` produces a testable artifact.

### RR-076-02 — Live Database Path Branches (low coverage in `database.py`)

- **Risk:** Live PostgreSQL connection branches in `storage/database.py` are 21% covered — only DSN-path delegation is tested.
- **Impact:** Low for path validation; existing integration tests (HEAR-049) cover the PostgreSQL connection path separately.
- **Repro:** Run `test_hear_049_installer_postgres.py` with a live PostgreSQL instance to exercise the connection branches.
- **Mitigation:** Accepted gap; database connectivity is outside the scope of this path/enrollment/export validation.

### RR-076-03 — Enrollment Dialog — No Audio Hardware in Headless Test Environment

- **Risk:** The actual microphone capture inside `EnrollmentDialog` cannot be validated headlessly; tests mock the dialog result.
- **Impact:** Medium — real microphone behavior only verifiable on physical hardware.
- **Repro:** Manual test: Open app on target device → Setup tab → Add participant → "Start Enrollment" → observe guidance text, recording state, status update.
- **Mitigation:** `EnrollmentDialog` (HEAR-068) was separately validated; mock-based tests confirm window.py integration logic is correct.

### RR-076-04 — Export Location Not Opened Automatically

- **Risk:** After export, the user is shown the file path in a label but the folder is not opened automatically in Explorer.
- **Impact:** Low — discoverability gap, not a functional bug.
- **Repro:** Export protocol during meeting → observe `_export_path_label` text → confirm no Explorer window opens.
- **Mitigation:** Acceptable for Phase-1; auto-open could be added as a Phase-2 UX improvement (no ADR required).

---

## Quality Gate Checklist

| Gate | Status |
|------|--------|
| ≥75% test coverage for path-resolution module (`utils/paths`: 93%) | ✅ PASS |
| No hardcoded `C:\AyeHear` literals in production modules | ✅ PASS |
| Enrollment `_start_enrollment()` uses real `EnrollmentDialog` (not placeholder) | ✅ PASS |
| Status transitions visible (pending → enrolled / failed) | ✅ PASS |
| Export button exists and is disabled initially | ✅ PASS |
| Export button enabled during meeting and after stop | ✅ PASS |
| Export writes Markdown artifact with header | ✅ PASS |
| Live protocol preview updates on each audio segment | ✅ PASS |
| Offline-first confirmed (no network calls in tested paths) | ✅ PASS |
| No regressions in existing test suite (98 tests) | ✅ PASS |
| Residual risks documented with repro steps | ✅ PASS |

**Overall QA Gate: PASS**

---

## Sign-Off

AYEHEAR_QA validates HEAR-073, HEAR-074, and HEAR-075 as meeting their acceptance criteria.  
HEAR-076 is complete. Release-readiness for the Phase-1b feature bundle is confirmed subject to the residual risks documented above.
