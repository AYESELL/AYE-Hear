---
task: HEAR-117
owner: AYEHEAR_ARCHITECT
status: implemented
updated: 2026-04-19
category: execution-brief
---

# HEAR-117 Claude Execution Brief

## Goal

Implement the confidence review workflow so users are guided to the most uncertain protocol items before export.

This is a trust and review task, not a new inference engine.

## Primary Files To Inspect

- `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/HEAR_V2_BACKLOG.md`
- `src/ayehear/services/confidence_review.py`
- `tests/test_hear_106_confidence_review.py`
- `tests/test_hear_108_quality_wave_validation.py`

## Likely Integration Points

- `src/ayehear/services/protocol_engine.py`
- `src/ayehear/app/window.py`
- final export path where reviewed decisions must affect output

## Constraints

- review state must stay inside approved runtime persistence boundaries,
- workflow must remain fully local,
- no silent auto-acceptance of uncertain items,
- ranking must be deterministic,
- preserve existing offline-first and manual-review guarantees.

## ADR and Design References

- `docs/adr/0001-ayehear-product-architecture.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/QUALITY_GATES.md`

## Acceptance Focus

- reasons include transcript, speaker, extraction, and fallback signals,
- queue ordering is explicit and testable,
- restart persistence works,
- export reflects accepted/edited/dismissed decisions correctly.

## Minimum Tests To Run

- `tests/test_hear_106_confidence_review.py`
- `tests/test_hear_108_quality_wave_validation.py`
- any integration tests added for UI/export persistence behavior

## Expected Evidence Updates

- HEAR-117 implementation notes,
- docs if review workflow becomes user-visible,
- QA-relevant notes on persistence and export behavior.

## Ready-To-Use Claude Prompt

Implement HEAR-117 in the AYE Hear repository.

Scope:
- Build the local confidence review workflow for uncertain protocol items.
- Prioritize reviewability and deterministic export outcomes.

Read first:
- `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/HEAR_V2_BACKLOG.md`
- `src/ayehear/services/confidence_review.py`
- `tests/test_hear_106_confidence_review.py`
- `tests/test_hear_108_quality_wave_validation.py`

Constraints:
- local-only persistence,
- deterministic ranking,
- no silent acceptance,
- no export of internal review-state artifacts.

Deliver:
- code updates,
- focused tests,
- integration notes for how reviewed items affect final protocol output.

## Implementation Notes

### Changes

**`src/ayehear/services/protocol_engine.py`**
- Added `from ayehear.services.confidence_review import ConfidenceReviewQueue`
- `ProtocolSnapshot` now includes `review_queue: ConfidenceReviewQueue | None`
- New public method: `build_review_queue(meeting_id, snapshot_id, snapshot_content)` — loads transcript segments from `self._transcripts.list_for_meeting()`, converts to signal dicts, calls `ConfidenceReviewQueue.build_signals(segment_dicts, self.last_diagnostics)`, then `ConfidenceReviewQueue.build()`. No model or network call.
- `generate()` now calls `build_review_queue()` in both the no-repo and repo paths; result is attached to the returned `ProtocolSnapshot`

**`src/ayehear/app/window.py`**
- Added `from ayehear.services.confidence_review import ConfidenceReviewQueue, ItemType`
- `MainWindow.__init__()`: `self._review_queue: ConfidenceReviewQueue | None = None`
- `set_active_meeting()`: tries `ConfidenceReviewQueue.load(Path(f"review-{meeting_id}.json"))` to restore queue across restarts
- `stop_active_meeting()`: calls `_save_review_queue()` before clearing, ensuring user decisions survive meeting stop
- `_save_review_queue()`: new private helper — saves queue to `runtime/reviews/review-{meeting_id}.json`
- `_rebuild_protocol_from_persistence()`: seeds `self._review_queue` from `snapshot.review_queue` on first generate (preserves user decisions on subsequent generates)
- `_refresh_protocol_display()`: when `self._review_queue is not None`, renders `Decisions`, `Action Items`, and `Open Questions` via `queue.get_final_items()` — dismissed items are hidden, edited items show revised text

### How reviewed items affect export

The `_refresh_protocol_display()` method feeds reviewed items into the protocol view. `_export_meeting_artifacts()` and `_do_export_protocol()` read from the protocol view, so all export formats (Markdown, DOCX, PDF) automatically reflect accepted/edited/dismissed review decisions. No internal review-state JSON is included in exported artifacts.

### Tests

- `tests/test_hear_117_confidence_review_integration.py` — 17 new integration tests covering: `build_review_queue()` with/without transcript repo, `ProtocolSnapshot.review_queue`, determinism, fallback signal propagation, review workflow (dismiss/edit/accept), `get_final_items()` after review, save/load persistence, and boundary enforcement
- All 54 tests pass: test_hear_106, test_hear_108, test_hear_117