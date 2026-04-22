---
owner: AYEHEAR_SECURITY
task: HEAR-134
status: APPROVED
date: 2026-04-22
category: security-review
---

# HEAR-134: Security Boundary Recheck – Persistence Lifecycle Hotfix (HEAR-130)

## Scope

Phase-5 security recheck for the persistence lifecycle continuity fix introduced
in commit `d37db7d` (`fix(persistence): HEAR-130 lifecycle continuity fix`).

Review covers four root-cause fixes (RC-1 through RC-4) applied to
`src/ayehear/app/window.py`:

| RC | Change |
|----|--------|
| RC-1 | `_reload_persistence_layer()`: corrected `ProtocolEngine` attribute names (`_snapshot_repo`/`_transcript_repo` → `_snapshots`/`_transcripts`) |
| RC-2 | `_stop_meeting()`: `ValueError` from `MeetingRepository._require()` now caught separately as warning, not routed to `_handle_persistence_error()` |
| RC-3 | `_refresh_protocol_display()`: only `SQLAlchemyError` triggers session reload; other exceptions are logged and swallowed |
| RC-4 | Post-reload meeting visibility guard: if active meeting is not visible in new session, `_transcript_repo` and transcription service repo are nulled to prevent FK loop |

Prior security baselines:
- HEAR-109 (initial security review)
- HEAR-119 (security recheck – whisper local-only enforcement)
- HEAR-127 (security recheck – soft-fallback hotfix, commit `0474297`)

---

## Executive Decision

**APPROVED**

The HEAR-130 fix is strictly scoped to session management and error-routing
logic within `window.py`. No new outbound path, no new network import, and no
new external service dependency was introduced. Local-only and offline-first
constraints remain intact. The export boundary is unchanged: `exports/` receives
only human-readable protocol and transcript text; `runtime/traces` and
`runtime/reviews` remain strictly local and are not included in user-facing
exports. The GDPR local-data pledge is unaffected. All four acceptance criteria
are met.

---

## Acceptance Criteria Assessment

| AC | Requirement | Result |
|----|-------------|--------|
| AC-1 | No new outbound/network path introduced by fix | **PASS** |
| AC-2 | Local-only fallback and DB/session cleanup behavior remain deterministic and scoped | **PASS** |
| AC-3 | Export artifacts still exclude internal trace/review JSON by default | **PASS** |
| AC-4 | Security recommendation explicitly states APPROVED or NO-GO | **PASS – APPROVED** |

---

## Security Checklist

| Check | Result | Evidence |
|-------|--------|----------|
| No new network import added by HEAR-130 hotfix | PASS | Module-level imports in `window.py` unchanged (stdlib + PySide6 + local `ayehear.*`); no `urllib`, `socket`, `requests`, `httpx`, or cloud SDK added |
| `_reload_persistence_layer()` uses only local DSN and local session factory | PASS | `load_runtime_dsn()` reads local pg.dsn file; `DatabaseBootstrap` binds to that local PostgreSQL endpoint only; no remote fallback path added |
| RC-1: attribute name correction does not expose data externally | PASS | Change is a pure in-process attribute re-assignment; corrects stale engine reference to use fresh local session; no I/O involved |
| RC-2: `ValueError` branch does not introduce alternative persistence or export path | PASS | New branch logs a warning and returns; does not invoke `_handle_persistence_error`, does not disable persistence, does not write any file |
| RC-3: SQLAlchemy-only routing does not change export pipeline | PASS | Non-DB exceptions are now logged via `logger.error` and swallowed; no export or trace write triggered; SQLAlchemy path already reviewed in HEAR-127 |
| RC-4: meeting-visibility guard nulls repos — does not transmit or cache data externally | PASS | On guard trigger: `_transcript_repo = None` and `_transcription_service._transcript_repo = None`; nulling prevents FK writes; no data is serialized or transmitted |
| RC-4: guard exception handler does not suppress critical failures silently | PASS | `except Exception as verify_exc` logs a warning with context (`logger.warning`); guard failure does NOT disable transcription — it only logs and continues, erring on the side of safety |
| `_disable_persistence()` cleanup unchanged and complete | PASS | All repo references nulled (`_meeting_repo`, `_participant_repo`, `_transcript_repo`, `_snapshot_repo`); `_transcription_service._transcript_repo` and both `_protocol_engine` attributes cleared; DB session closed |
| `_save_review_queue()` and `_save_trace_store()` still write only to local runtime/ dirs | PASS | Both methods resolve paths relative to local `runtime/reviews/` and `runtime/traces/`; neither path changed by HEAR-130 |
| `_export_meeting_artifacts()` still excludes trace/review JSON | PASS | Export function writes only `*-protocol.md`, `*-protocol.docx`, `*-protocol.pdf`, and `*-transcript.txt` to `exports/`; trace and review store files are never referenced here |
| Offline-first contract preserved | PASS | All session-reload paths use local DSN only; no retry against remote endpoint added; fallback remains fully local-only |
| GDPR data scope unchanged | PASS | Speaker profiles, participant data, and transcript content remain in local PostgreSQL or local runtime files; no external processor added |
| LLM loopback guard (Ollama → localhost) unaffected | PASS | HEAR-130 does not touch `ProtocolEngine.__init__` or `_validate_loopback_url()`; confirmed by diff scope (window.py error-routing changes only) |
| Unit-test coverage for all four root causes | PASS | 17 new tests in `tests/test_hear_130_persistence_lifecycle_continuity.py`, all green (evidence: HEAR-132 QA) |

---

## Files Reviewed

| File | Review Method |
|------|--------------|
| `src/ayehear/app/window.py` | Full diff `9a1f866..d37db7d`; module-level imports verified; `_reload_persistence_layer()`, `_stop_meeting()`, `_refresh_protocol_display()`, `_disable_persistence()`, `_save_review_queue()`, `_save_trace_store()`, `_export_meeting_artifacts()` read in full |
| `tests/test_hear_130_persistence_lifecycle_continuity.py` | Test class names and 17-test pass result verified via HEAR-132 evidence |
| `tools/scripts/benchmark_whisper_models.py` | Network-keyword search: no `urllib`, `requests`, `socket`, `http`, `download`, `huggingface_hub` found |
| `tests/test_hear_136_asr_dataset.py` | Network-keyword search: no outbound calls found |
| `docs/HEAR-127-security-recheck.md` | Prior baseline confirmed; HEAR-127 scope (commit `0474297`) is orthogonal and still valid |
| `docs/HEAR-132-qa-evidence.md` | RC-1..RC-4 mapping and 17-test evidence; 5 pre-existing failures confirmed unrelated to FK path |
| `docs/HEAR-133-qa-evidence.md` | Trace/review store artifact inventory; empty-store root cause confirmed as FK cascade (expected; fixed by HEAR-130) |

---

## Findings

### F1 – No New Outbound Path

The HEAR-130 diff adds zero new imports at module level. The `sqlalchemy.exc`
import in `_refresh_protocol_display()` is a local conditional import of an
already-bundled dependency; it does not introduce a new network surface.
No `urllib`, `socket`, `requests`, or cloud SDK call was introduced.

**Severity:** None. No action required.

---

### F2 – RC-4 Guard: Exception Handler Coverage

The meeting-visibility guard (`RC-4`) catches a broad `except Exception` when
calling `self._meeting_repo.get_by_id()`. On failure, it logs a warning and
continues without disabling transcript persistence. This is intentional (fail
open toward continued operation), but means that a corrupted meeting-repo state
could leave `_transcript_repo` active, potentially producing continued FK
violations in an unexpected edge case.

**Assessment:** Acceptable for this hotfix. The guard is a best-effort
defense-in-depth measure; the primary fix is RC-1 (correct attribute names).
The `logger.warning` call ensures the anomaly is traceable in logs. A stricter
guard (disabling on exception) could be introduced in a follow-up if FK violations
recur in practice.

**Severity:** Low / Informational. No blocking action required.

---

### F3 – `_disable_persistence()` Retains Legacy Attribute Names for ProtocolEngine

`_disable_persistence()` still clears `self._protocol_engine._snapshot_repo`
and `self._protocol_engine._transcript_repo` — the old (wrong) attribute names
fixed by RC-1. Because `ProtocolEngine` uses `_snapshots`/`_transcripts`
internally, these null-assignments in `_disable_persistence()` are no-ops (they
set attributes that the engine does not read).

**Assessment:** This is a latent inconsistency but NOT a security issue. The
engine falls back to no-op behavior when `_snapshots`/`_transcripts` are None
(verified in unit tests). The practical impact is that a full-disable path does
not need corrected attribute names to be safe — the engine simply has no repos.
A cleanup task (correct attribute names in `_disable_persistence()`) is
recommended as a follow-up to maintain code consistency.

**Severity:** Low / Informational. No security boundary impact.

---

## Security Recommendation

**APPROVED**

The persistence lifecycle continuity fix (HEAR-130, commit `d37db7d`) does not
regress offline-first or export-boundary security constraints. All four
acceptance criteria are satisfied. Two low/informational findings are noted for
tracking; neither is a blocker. The prior security baselines established by
HEAR-109, HEAR-119, and HEAR-127 remain intact.

A follow-up cleanup is recommended (non-blocking):
- Correct `_disable_persistence()` to null `_protocol_engine._snapshots` and
  `_protocol_engine._transcripts` (instead of the legacy `_snapshot_repo`/
  `_transcript_repo` names) for consistency with RC-1.

---

## Evidence Chain

| Evidence | Reference |
|----------|-----------|
| HEAR-130 diff (window.py) | `git show d37db7d` |
| 17-test pass (RC-1..RC-4) | docs/HEAR-132-qa-evidence.md §"Unit Test Evidence" |
| Trace/review store inventory | docs/HEAR-133-qa-evidence.md |
| Prior security baseline | docs/HEAR-127-security-recheck.md |
| Full suite: 831/836 green (5 pre-existing) | deployment-evidence/hear-132/2026-04-22-hear-132/05-full-suite-summary.txt |
