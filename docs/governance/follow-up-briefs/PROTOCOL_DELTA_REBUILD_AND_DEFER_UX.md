---
owner: AYEHEAR_DEVELOPER
status: ready
category: follow-up-brief
updated: 2026-05-02
---

# Follow-up Brief: Protocol Delta Rebuild and Deferred-State UX

## Goal
Reduce rebuild noise and make CPU-deferred protocol state explicit to users and QA.

## Why
Periodic rebuild currently runs every 10s and can create stale perception when generation is deferred under CPU load.

## References
- src/ayehear/app/window.py
- src/ayehear/services/protocol_engine.py
- src/ayehear/storage/repositories.py
- docs/HEAR-144-build-evidence.md

## Required Scope
- src/ayehear/app/window.py
- src/ayehear/services/protocol_engine.py
- tests/test_hear_141_async_pipeline.py
- add/extend protocol UI integration tests

## Implementation Requirements
1. Add delta gating: rebuild only when transcript state changed since last snapshot attempt.
2. Surface deferred status in protocol panel with clear user-facing text.
3. Keep offline-first behavior and existing fallback path intact.
4. Ensure no uncontrolled snapshot growth in idle periods.

## Acceptance Criteria
- No snapshot append when transcript input unchanged.
- Deferred CPU state is visible in UI and export metadata when applicable.
- Existing protocol tests remain green with new behavior.

## Verification
- pytest tests/test_hear_141_async_pipeline.py -q
- add tests for deferred UX marker and delta rebuild suppression

## Evidence To Produce
- snapshot count comparison before/after under idle input
- UI evidence for deferred marker
- targeted test summary
