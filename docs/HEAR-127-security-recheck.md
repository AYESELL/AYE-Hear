---
owner: AYEHEAR_SECURITY
task: HEAR-127
status: APPROVED
date: 2026-04-19
category: security-review
---

# HEAR-127: Security Recheck – Persistence-Path Hotfix

## Scope

Phase-5 focused security recheck for the meeting lifecycle persistence hotfix
introduced in commit `0474297` (`fix(window): soft-fallback to local-only on
meeting-start commit failure`).

Review covers:
- absence of any new outbound path in the hotfix code,
- local-only boundary preservation after the soft-fallback path is taken,
- no leakage of review/trace state into export artifacts.

Reference evidence:
- [docs/HEAR-123-qa-evidence.md](HEAR-123-qa-evidence.md) – blocker description
- [docs/HEAR-126-qa-evidence.md](HEAR-126-qa-evidence.md) – NO-GO evidence that triggered this task
- [docs/HEAR-119-security-review.md](HEAR-119-security-review.md) – prior approved baseline

---

## Executive Decision

**APPROVED**

The persistence-path hotfix is strictly scoped to the error-recovery branch of
`window.py#_start_meeting()`. No new network imports, external service calls, or
outbound transports were added. The soft-fallback path closes and nulls out the
DB session via the existing `_disable_persistence()` facility and continues the
session in memory. The LLM loopback guard in `ProtocolEngine` is unaffected. The
export pipeline does not include internal review or trace JSON. The prior
security baseline established by HEAR-109 and HEAR-119 remains intact.

---

## Security Checklist

| Check | Result | Evidence |
|---|---|---|
| No new outbound path introduced by hotfix | PASS | Hotfix confined to `window.py` error branch; no new network import or remote client added; `urllib` / `socket` usage unchanged and pre-existing |
| Local-only boundary preserved after fallback | PASS | `_disable_persistence()` closes DB session and nulls all repo references (meeting, participant, transcript, snapshot); protocol engine repos also cleared |
| LLM (Ollama) loopback enforcement unaffected | PASS | `ProtocolEngine._validate_loopback_url()` and `_start_meeting()` flow diverge; hotfix does not touch protocol engine initialisation |
| No review/trace state exported to `exports/` | PASS | `_export_meeting_artifacts()` writes only UI text views (protocol + transcript); `_save_review_queue()` and `_save_trace_store()` target `runtime/reviews` and `runtime/traces` respectively; paths unchanged |
| Participant data cleared on fallback | PASS | `self._participant_id_map = {}` explicit clear after `_disable_persistence()` call; no partial participant state leaks to transcript or export pipeline |
| Rollback attempted before entering fallback | PASS | `self._db_session.rollback()` attempted in guarded `try/except`; failure logged as warning, does not suppress the subsequent `_disable_persistence()` call |
| Regression test coverage for fallback path | PASS | `test_commit_failure_switches_to_local_only_soft_fallback` in `tests/test_hear_124_meeting_lifecycle_fk.py` verifies `_disable_persistence` is called and local meeting ID is retained |
| Offline-first contract preserved | PASS | Fallback is fully local-only; no retry against remote endpoint is attempted |

---

## Files Reviewed

- `src/ayehear/app/window.py` (diff commit `0474297` + current state of
  `_disable_persistence`, `_save_review_queue`, `_save_trace_store`,
  `_export_meeting_artifacts`)
- `tests/test_hear_124_meeting_lifecycle_fk.py` (new regression test)
- `src/ayehear/services/protocol_engine.py` (loopback guard unchanged)
- `src/ayehear/services/confidence_review.py` (persistence boundary unchanged)
- `src/ayehear/services/protocol_traceability.py` (persistence boundary unchanged)

---

## Findings

### F1 – Soft-Fallback Does Not Introduce Outbound Transport

The hotfix inserts a `try/except` block after the existing `session.commit()`
call. On `Exception`, the block attempts a rollback, calls
`_disable_persistence()`, and sets `meeting_persisted = False`. No new import,
socket, HTTP client, or background thread is introduced. The change is
exclusively within the local application boundary.

**Severity:** None. No action required.

### F2 – `_disable_persistence()` Nulls All DB-Facing References

`_disable_persistence()` closes the session, sets `_db_session`, `_meeting_repo`,
`_participant_repo`, `_transcript_repo`, and `_snapshot_repo` to `None`, and
also clears the transcript service and protocol engine repo references. After
this call the application cannot issue any further DB query regardless of
subsequent code paths.

**Severity:** None. Behaviour is correct and tightly scoped.

### F3 – Review/Trace State Correctly Isolated From Export Path

`_export_meeting_artifacts()` reads only `_protocol_view.toPlainText()` and
`_transcript_view.toPlainText()`. Neither `_review_queue` nor `_trace_store`
instances are referenced in the export method. Saving of review/trace state
(via `_save_review_queue()` / `_save_trace_store()`) writes to
`runtime/reviews/` and `runtime/traces/` only. These paths are separate from
the `exports/` boundary and the boundary enforcement is unchanged from the
HEAR-109/HEAR-119 approved baseline.

In the fallback scenario, trace/review stores may remain empty (no DB-backed
meeting ID to associate content with). This is an expected and safe consequence:
the local-only session produces no recoverable DB artefacts and the empty stores
do not expose sensitive state.

**Severity:** None. No action required.

### F4 – Participant Map Cleared on Fallback (No Partial Leak)

`self._participant_id_map = {}` is explicitly set after `_disable_persistence()`
is called. This prevents stale participant DB IDs from being used in enrollment
reconciliation later in `_start_meeting()`, where they would reference rows that
were never committed.

**Severity:** None. Behaviour is correct.

---

## Release Recommendation

The persistence-path hotfix (commit `0474297`) passes all security checks.
No new security controls are required before the next release reconciliation
review. The prior approved security posture (HEAR-109, HEAR-119) remains valid
and is not regressed by this change.
