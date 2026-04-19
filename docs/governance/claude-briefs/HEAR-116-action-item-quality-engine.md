---
task: HEAR-116
owner: AYEHEAR_ARCHITECT
status: implemented
updated: 2026-04-19
category: execution-brief
---

# HEAR-116 Claude Execution Brief

## Goal

Extend and integrate V2-01 so that extracted action items are scored, explained, and sharpened deterministically before final export.

This task should improve usefulness of already extracted tasks, not invent new tasks or introduce another AI layer.

## Primary Files To Inspect

- `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/HEAR_V2_BACKLOG.md`
- `src/ayehear/services/action_item_quality.py`
- `tests/test_hear_105_action_item_quality.py`
- `tests/test_hear_108_quality_wave_validation.py`

## Likely Integration Points

- `src/ayehear/services/protocol_engine.py`
- `src/ayehear/app/window.py`
- export formatting paths if score/hints are surfaced in output

## Constraints

- scoring must remain deterministic and explainable,
- no new model dependency,
- no network call,
- localised labels may vary but scoring semantics must not,
- avoid creating a second interpretation pipeline.

## ADR and Design References

- `docs/adr/0001-ayehear-product-architecture.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/QUALITY_GATES.md`

## Acceptance Focus

- reason labels are stable,
- sharpening state is explicit,
- reviewed/final export can reflect the improved task quality presentation,
- integration remains low-risk and testable.

## Minimum Tests To Run

- `tests/test_hear_105_action_item_quality.py`
- `tests/test_hear_108_quality_wave_validation.py`
- any newly added integration tests touching export or protocol flow

## Expected Evidence Updates

- HEAR-116 implementation notes,
- documentation if user-visible export/review behavior changes,
- tests proving deterministic behavior.

## Implementation Notes

### What was built

`ActionItemQualityEngine` (HEAR-105) already implemented deterministic scoring with 5 dimensions, stable reason codes, and localized hints. HEAR-116 wires it into `ProtocolEngine` and the display layer.

### Changes

**`src/ayehear/services/protocol_engine.py`**
- Added `from ayehear.services.action_item_quality import ActionItemQuality, ActionItemQualityEngine`
- `ProtocolSnapshot` now includes `action_item_quality: list[ActionItemQuality]` (default empty list)
- `ProtocolEngine.__init__()` creates `self._quality_engine = ActionItemQualityEngine(language=language)`
- New public method: `score_action_items(texts) -> list[ActionItemQuality]` — delegates to quality engine, no network/model call
- New static method: `annotate_weak_items(items, qualities) -> list[str]` — appends `[⚠ needs sharpening: reason_code, ...]` to items below the sharpening threshold using stable English enum values as reason codes
- `generate()` now scores all extracted action items, stores quality signals in `ProtocolActionItem.description` field (`score:N sharpening:True|False reasons:code1,code2`), and returns quality alongside the snapshot

**`src/ayehear/app/window.py`**
- `_refresh_protocol_display()` now annotates weak action items via `annotate_weak_items()` before rendering, so the protocol view (and downstream Markdown/DOCX/PDF export) shows `[⚠ needs sharpening: ...]` on items below the 75-point threshold

### Where quality signals appear

| Signal type | Location |
|-------------|----------|
| In-memory quality results | `ProtocolSnapshot.action_item_quality` |
| Persisted quality summary | `ProtocolActionItem.description` in DB |
| Display annotation | Protocol panel action items (live display) |
| Export (Markdown/DOCX/PDF) | Via annotated draft text from display |

### Tests

- `tests/test_hear_116_quality_engine_integration.py` — 15 new tests covering: `score_action_items()`, `annotate_weak_items()`, `generate()` integration with and without repo, description content, determinism, language flow
- All 46 tests pass: test_hear_105, test_hear_108, test_hear_116

## Ready-To-Use Claude Prompt

Implement HEAR-116 in the AYE Hear repository.

Scope:
- Build out V2-01 Action-Item Quality Engine Plus.
- Improve scoring/integration of existing action items only.
- Keep the system deterministic, local-only, and easy to review.

Read first:
- `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md`
- `docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md`
- `docs/governance/HEAR_V2_BACKLOG.md`
- `src/ayehear/services/action_item_quality.py`
- `tests/test_hear_105_action_item_quality.py`
- `tests/test_hear_108_quality_wave_validation.py`

Constraints:
- no new model path,
- no cloud call,
- stable reason codes,
- minimal, focused integration.

Deliver:
- code changes,
- tests,
- any necessary export/review integration,
- short note on where the quality signals appear and how they are validated.