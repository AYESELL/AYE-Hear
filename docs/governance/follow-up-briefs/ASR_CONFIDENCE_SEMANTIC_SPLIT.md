---
owner: AYEHEAR_DEVELOPER
status: ready
category: follow-up-brief
updated: 2026-05-02
---

# Follow-up Brief: ASR Confidence Semantic Split

## Goal
Separate ASR recognition confidence from speaker attribution confidence so quality gates, review queue ranking, and diagnostics are semantically correct.

## Why
Current flow passes speaker confidence into transcription confidence paths, which distorts review priorities and root-cause analysis.

## References
- docs/HEAR-135-readiness-reconciliation.md
- docs/HEAR_ASR_QUALITY_STRATEGY_REVIEW_AND_APPROVAL.md
- src/ayehear/app/window.py
- src/ayehear/services/transcription.py
- src/ayehear/services/speaker_manager.py

## Required Scope
- src/ayehear/services/transcription.py
- src/ayehear/app/window.py
- src/ayehear/storage/repositories.py (only if persistence fields need extension)
- tests/test_transcription.py
- tests/test_hear_084_persistent_lifecycle.py

## Implementation Requirements
1. Introduce distinct confidence semantics in runtime result objects:
   - asr_confidence
   - speaker_confidence
2. Ensure review decisions are computed against explicit policy:
   - low ASR => transcript quality review
   - low speaker confidence => attribution review
3. Keep backward compatibility for export and UI labels where possible.
4. Add migration-safe handling if schema changes are needed.

## Acceptance Criteria
- ASR and speaker confidence are persisted and surfaced independently.
- Review queue reason codes can distinguish transcript uncertainty vs speaker uncertainty.
- No regression in existing meeting lifecycle tests.
- Full targeted test pack passes.

## Verification
- pytest tests/test_transcription.py -q
- pytest tests/test_hear_084_persistent_lifecycle.py -q
- Add one integration test proving mixed confidence cases are routed correctly.

## Evidence To Produce
- QA snippet with before/after confidence field samples
- test output summary
- short implementation note in task implementation notes
