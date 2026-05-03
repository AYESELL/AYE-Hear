---
owner: AYEHEAR_DEVELOPER
status: ready
category: follow-up-brief
updated: 2026-05-02
---

# Follow-up Brief: Speaker Reconciliation Persistence Consistency

## Goal
Guarantee DB state, review queue input, and UI output use the same final speaker assignment after post-ASR speaker refinement.

## Why
Current sequence may persist pre-match speaker while UI shows refined speaker, causing audit and traceability mismatch.

## References
- src/ayehear/app/window.py
- src/ayehear/storage/repositories.py
- docs/HEAR-133-qa-evidence.md

## Required Scope
- src/ayehear/app/window.py
- src/ayehear/storage/repositories.py
- tests/test_hear_084_persistent_lifecycle.py
- tests/test_speaker_manager.py

## Implementation Requirements
1. After resolve_speaker_from_segment(), reconcile persisted segment speaker when refined result differs from pre-match.
2. Preserve correction auditability (do not silently lose trace of automatic reconciliation).
3. Ensure protocol traceability and review queue consume reconciled state.
4. Avoid introducing extra write-amplification under high-frequency transcription.

## Acceptance Criteria
- Persisted speaker equals final speaker shown in transcript panel for each segment.
- Reconciliation path is covered by tests.
- No regression in confidence review workflow.

## Verification
- pytest tests/test_hear_084_persistent_lifecycle.py -q
- pytest tests/test_speaker_manager.py -q
- Add one integration test: pre-match != post-match, persistence resolves to post-match.

## Evidence To Produce
- log excerpt showing reconciliation update
- DB row comparison proof (before/after)
- test output summary
