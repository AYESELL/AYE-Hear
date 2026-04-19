---
task: HEAR-118
owner: AYEHEAR_ARCHITECT
status: implemented
updated: 2026-04-19
category: execution-brief
---

# HEAR-118 Claude Execution Brief

## Goal

Implement the traceability layer so protocol items can be inspected against their transcript context, speaker attribution state, and evidence type.

The feature should make errors diagnosable and reviews faster, without leaking internal trace state into external artifact boundaries.

## Primary Files To Inspect

- `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/HEAR_V2_BACKLOG.md`
- `src/ayehear/services/protocol_traceability.py`
- `tests/test_hear_107_protocol_traceability.py`
- `tests/test_hear_108_quality_wave_validation.py`

## Likely Integration Points

- `src/ayehear/services/protocol_engine.py`
- `src/ayehear/app/window.py`
- local persistence/path utilities if needed for trace storage boundaries

## Constraints

- all trace data remains local-only,
- persistence must stay within approved runtime boundaries,
- trace references must be revision-safe,
- direct versus inferred evidence must be visible,
- external export should not dump internal trace JSON by default.

## ADR and Design References

- `docs/adr/0001-ayehear-product-architecture.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/QUALITY_GATES.md`

## Acceptance Focus

- users can inspect source context for protocol items,
- trace links survive restart and revision changes,
- unresolved/low-confidence speaker state is preserved in trace context,
- trace storage remains compliant with local-only rules.

## Minimum Tests To Run

- `tests/test_hear_107_protocol_traceability.py`
- `tests/test_hear_108_quality_wave_validation.py`
- any integration tests touching UI/view behavior or persistence boundaries

## Expected Evidence Updates

- HEAR-118 implementation notes,
- docs if new traceability UI behavior is surfaced,
- explicit note on how direct/inferred backing is represented.

## Ready-To-Use Claude Prompt

Implement HEAR-118 in the AYE Hear repository.

Scope:
- Build the evidence-linked protocol traceability layer.
- Make protocol items auditable against transcript context and speaker attribution state.

Read first:
- `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/HEAR_V2_BACKLOG.md`
- `src/ayehear/services/protocol_traceability.py`
- `tests/test_hear_107_protocol_traceability.py`
- `tests/test_hear_108_quality_wave_validation.py`

Constraints:
- no outbound path,
- runtime-bound storage only,
- revision-safe persistence,
- do not expose internal trace JSON in final external exports by default.

Deliver:
- code changes,
- tests,
- concise summary of trace storage, trace lookup behavior, and direct-vs-inferred handling.

## Implementation Notes

### Changes

**`src/ayehear/services/protocol_engine.py`**
- Added `from ayehear.services.protocol_traceability import TraceabilityStore`
- `ProtocolSnapshot` now includes `trace_store: TraceabilityStore | None`
- New public method: `build_trace_store(meeting_id, snapshot_id, snapshot_content)` — loads transcript segments (with `text`, `start_ms`, `end_ms`) from `self._transcripts.list_for_meeting()`, calls `TraceabilityStore.build_links()` with `fallback_used` from `self._last_diagnostics`. No model or network call.
- `generate()` now calls `build_trace_store()` in both the no-repo and repo paths; result is attached to the returned `ProtocolSnapshot`

**`src/ayehear/app/window.py`**
- Added `from ayehear.services.protocol_traceability import TraceabilityStore`
- `MainWindow.__init__()`: `self._trace_store: TraceabilityStore | None = None`
- `set_active_meeting()`: tries `TraceabilityStore.load(Path(f"trace-{meeting_id}.json"))` to restore trace state across restarts
- `stop_active_meeting()`: calls `_save_trace_store()` before clearing
- `_save_trace_store()`: new private helper — saves store to `runtime/traces/trace-{meeting_id}.json`
- `_rebuild_protocol_from_persistence()`: seeds `self._trace_store` from `snapshot.trace_store` on first generate (preserves trace context on subsequent generates)

### Trace storage, lookup, and direct-vs-inferred handling

- **Storage**: `runtime/traces/trace-{meeting_id}.json` (ADR-0011 boundary enforced; save/load reject paths outside `runtime/traces/`)
- **Lookup**: `store.get_links_for_item(item_type, item_text)` returns all `TraceLink` objects for an exact item. Each link exposes `time_range`, `primary_speaker`, `has_unresolved_speaker`, and per-segment `speaker_attribution_state`.
- **Direct vs. Inferred**: keyword-overlap heuristic (≥2 words of ≥4 chars shared between protocol item and segment text → `DIRECT`; otherwise → `INFERRED`). When `fallback_used=True` all items are forced `INFERRED` because rule-based extraction has no positional backing. External exports never include the internal trace JSON.

### Tests

- `tests/test_hear_118_protocol_traceability_integration.py` — 17 new integration tests covering: `build_trace_store()` with/without transcript repo, `ProtocolSnapshot.trace_store`, no-transcript → all INFERRED, fallback → all INFERRED, keyword-overlap → DIRECT link, unresolved/corrected speaker state propagation, determinism, `generate()` integration (no-repo, with-repo, synthetic snapshot_id, summary counts), save/load persistence, and boundary enforcement
- All 50 tests pass: test_hear_107, test_hear_108, test_hear_118