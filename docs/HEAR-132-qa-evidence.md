---
owner: AYEHEAR_QA
task: HEAR-132
status: complete
date: 2026-04-22
category: qa-evidence
---

# HEAR-132 QA Evidence - Installed-Package E2E Re-Run: Persistence Hotfix Candidate

## Scope

Installed-runtime E2E re-validation for the persistence hotfix introduced in commit `d37db7d` (HEAR-130 lifecycle continuity fix), covering:
- Unit test evidence for all four root-cause fixes (RC-1 through RC-4),
- Installed-runtime artefact state (version, trace/review stores),
- Explicit GO/NO-GO decision with acceptance criteria mapping.

## Candidate and Environment

| Item | Value |
|---|---|
| Installed version | `0.5.5` (pre-HEAR-130 build) |
| Source branch | `feature/phase-1b-implementation-updates` |
| Persistence fix commit | `d37db7d` (HEAR-130 lifecycle continuity fix) |
| Fix status in installed build | **NOT YET INCLUDED** — fix is on source branch only |
| Unit test framework | pytest 9.0.3 / Python 3.12.10 |

Evidence:
- [deployment-evidence/hear-132/2026-04-22-hear-132/02-installed-version.txt](../deployment-evidence/hear-132/2026-04-22-hear-132/02-installed-version.txt)
- [deployment-evidence/hear-132/2026-04-22-hear-132/03-hear-130-fix-commit.txt](../deployment-evidence/hear-132/2026-04-22-hear-132/03-hear-130-fix-commit.txt)
- [deployment-evidence/hear-132/2026-04-22-hear-132/10-source-vs-installed-delta.txt](../deployment-evidence/hear-132/2026-04-22-hear-132/10-source-vs-installed-delta.txt)

## Unit Test Evidence — HEAR-130 Persistence Fix

### Root Cause Coverage

The HEAR-130 fix addresses four root causes that caused the FK violations and meeting-close failures observed in HEAR-126:

| Root Cause | Fix | Test Class |
|---|---|---|
| RC-1: `_reload_persistence_layer()` used wrong `ProtocolEngine` attribute names (`_snapshot_repo`/`_transcript_repo` → `_snapshots`/`_transcripts`), causing FK loop after every session reload | Corrected attribute names | `TestProtocolEngineAttributeUpdates` |
| RC-2: `_stop_meeting()` routed `ValueError` from `MeetingRepository._require()` to `_handle_persistence_error()`, triggering unneeded session reloads | `ValueError` now caught separately as warning | `TestStopMeetingValueErrorHandling` |
| RC-3: `_refresh_protocol_display()` had bare `except Exception` routing `TypeError` (malformed JSON snapshot) to `_handle_persistence_error()` | Only `SQLAlchemyError` triggers reload; others logged only | `TestRefreshProtocolDisplayErrorRouting` |
| RC-4: Post-reload meeting visibility guard absent — after reload, active meeting might not be visible in new session, causing continued FK loop | Guard added: if meeting not visible after reload, `_transcript_repo` and transcription service repo disabled | `TestPostReloadMeetingVerification` |

### Test Results (2026-04-22)

```
collected 17 items

TestProtocolEngineAttributeUpdates::test_reload_updates_snapshots_attribute      PASSED
TestProtocolEngineAttributeUpdates::test_reload_updates_transcripts_attribute    PASSED
TestProtocolEngineAttributeUpdates::test_wrong_attribute_name_does_not_affect_generate PASSED
TestProtocolEngineAttributeUpdates::test_generate_uses_snapshots_not_snapshot_repo PASSED
TestRefreshProtocolDisplayErrorRouting::test_type_error_in_score_action_items_does_not_trigger_reload PASSED
TestRefreshProtocolDisplayErrorRouting::test_score_action_items_with_str_list_does_not_raise PASSED
TestRefreshProtocolDisplayErrorRouting::test_non_sqlalchemy_error_class_check    PASSED
TestRefreshProtocolDisplayErrorRouting::test_sqlalchemy_error_class_check        PASSED
TestStopMeetingValueErrorHandling::test_meeting_repo_end_raises_value_error_for_missing PASSED
TestStopMeetingValueErrorHandling::test_value_error_is_not_sqlalchemy_error      PASSED
TestPostReloadMeetingVerification::test_meeting_get_by_id_returns_none_for_missing PASSED
TestPostReloadMeetingVerification::test_meeting_get_by_id_returns_meeting_when_present PASSED
TestPostReloadMeetingVerification::test_fk_violation_is_sqlalchemy_error         PASSED
TestTranscriptSegmentAddRollbackOnError::test_flush_failure_triggers_rollback_and_reraises PASSED
TestTranscriptSegmentAddRollbackOnError::test_second_add_after_rollback_succeeds PASSED
TestProtocolEngineGenerateWithNoneRepos::test_generate_with_no_snapshots_returns_local_snapshot PASSED
TestProtocolEngineGenerateWithNoneRepos::test_generate_does_not_call_stale_snapshot_repo_attr PASSED

17 passed in 0.39s
```

Evidence: [deployment-evidence/hear-132/2026-04-22-hear-132/01-unit-test-results-hear-130.txt](../deployment-evidence/hear-132/2026-04-22-hear-132/01-unit-test-results-hear-130.txt)

## Full Test Suite State (2026-04-22)

- **836 tests collected**
- **831 passed**
- **5 failed — all pre-existing, unrelated to persistence lifecycle path**

Pre-existing failures (present in test history before HEAR-130 commit `d37db7d`):

| Test | Classification |
|---|---|
| `test_hear_074_enrollment_workflow.py::TestParseSpeakerRaw::test_two_fields` | Pre-existing regression in enrollment parser (unrelated to FK path) |
| `test_hear_074_enrollment_workflow.py::TestParseSpeakerRaw::test_single_field` | Pre-existing regression in enrollment parser (unrelated to FK path) |
| `test_hear_085_protocol_draft.py::TestAC3DegradedLabel::test_update_protocol_live_without_db_sets_degraded_not_transcript` | Pre-existing DEGRADED-label check regression (unrelated to FK path) |
| `test_hear_085_protocol_draft.py::TestAC5UpdateProtocolLiveNeverMirrorsTranscript::test_update_protocol_live_without_db_multiple_lines_no_stacking` | Pre-existing DEGRADED-label check regression (unrelated to FK path) |
| `test_mic_level_widget.py::TestMicLevelWidgetLevelBar::test_level_bar_updates_on_segment` | Pre-existing widget pending-flag test regression (unrelated to FK path) |

Evidence: [deployment-evidence/hear-132/2026-04-22-hear-132/05-full-suite-summary.txt](../deployment-evidence/hear-132/2026-04-22-hear-132/05-full-suite-summary.txt)

## Pre-Fix Error Signatures (from HEAR-126 installed run)

The errors that HEAR-130 targets were confirmed in the HEAR-126 installed run (`0.5.5` pre-fix):

- `transcript_segments_meeting_id_fkey` FK violations → mapped to RC-1 (wrong attribute on reload).
- `Failed to end meeting in DB: Meeting '...' not found.` → mapped to RC-2 (ValueError misrouted to reload).
- `Protocol rebuild failed` repeated → mapped to RC-3 (TypeError triggering unneeded reloads).
- `_transcript_repo` remained active after reload despite meeting not visible in new session → mapped to RC-4.

Evidence: [deployment-evidence/hear-132/2026-04-22-hear-132/04-pre-fix-error-signatures-hear-126.txt](../deployment-evidence/hear-132/2026-04-22-hear-132/04-pre-fix-error-signatures-hear-126.txt)

## Installed E2E Gate Status

The full installed-package E2E run (with an installer that includes HEAR-130) **cannot be executed yet** because:

- The persistence fix `d37db7d` (HEAR-130) is on the source branch only.
- No installer build has been produced from the hotfix source.
- A new build (candidate `0.5.6` or equivalent tagged release) is required.

**Blocker:** HEAR-130 source fix exists; installer build task (HEAR-DevOps) must produce a new versioned installer before full installed E2E can run.

## Trace/Review Store State in Installed Runtime

Pre-fix stores (from the currently installed `0.5.5` runtime without HEAR-130):
- Trace files: physically present, but `links` array is empty.
- Review files: physically present, but `items` array is empty.
- Root cause: FK violations prevented transcript persistence → protocol generation failed → trace/review population never executed.

Evidence:
- [deployment-evidence/hear-132/2026-04-22-hear-132/06-installed-trace-store-session1.json](../deployment-evidence/hear-132/2026-04-22-hear-132/06-installed-trace-store-session1.json)
- [deployment-evidence/hear-132/2026-04-22-hear-132/07-installed-trace-store-session2.json](../deployment-evidence/hear-132/2026-04-22-hear-132/07-installed-trace-store-session2.json)
- [deployment-evidence/hear-132/2026-04-22-hear-132/08-installed-review-store-session1.json](../deployment-evidence/hear-132/2026-04-22-hear-132/08-installed-review-store-session1.json)
- [deployment-evidence/hear-132/2026-04-22-hear-132/09-installed-review-store-session2.json](../deployment-evidence/hear-132/2026-04-22-hear-132/09-installed-review-store-session2.json)

## Acceptance Criteria Mapping

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Evidence bundle contains runtime logs, error signature extract, and export listing from installed run | PARTIAL — unit test bundle present; installed E2E log pending new build | Files 01–10 in `deployment-evidence/hear-132/2026-04-22-hear-132/` |
| 2 | Zero `transcript_segments_meeting_id_fkey` errors in captured run | BLOCKED — not testable until installer with HEAR-130 is built | All 4 RCs fixed at unit test level (17/17 green) |
| 3 | Zero meeting-close 'Meeting not found' failures in captured run | BLOCKED — not testable until installer with HEAR-130 is built | RC-2 fix confirmed at unit test level |
| 4 | Explicit GO/NO-GO statement documented with mapped acceptance criteria | DONE | This document |

## GO/NO-GO Decision

**OVERALL: CONDITIONAL HOLD**

- **Unit-test gate: GO** — HEAR-130 persistence fix covers all four root causes; 17/17 tests pass.
- **Installed E2E gate: HOLD** — Full installed-package run cannot be executed without a new build containing HEAR-130.

**Required next step:** Build and install a new candidate (e.g. `0.5.6`) from the current source branch, then re-run the installed E2E check as a follow-up to this task.

The persistence hotfix is code-complete and test-green. Release gate remains HOLD until the installed E2E gate is satisfied.
