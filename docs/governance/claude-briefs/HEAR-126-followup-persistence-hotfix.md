---
task: HEAR-126-followup
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-19
category: execution-brief
---

# HEAR-126 Follow-up Claude Execution Brief

## Goal

Implement a focused persistence hotfix after HEAR-126 NO-GO for installed candidate 0.5.5.

The fix must eliminate meeting lifecycle breakdown in installed runtime:
- no transcript FK failures against transcript_segments_meeting_id_fkey,
- no repeated protocol rebuild failure cascade due rolled-back session state,
- no meeting end failure with "Meeting ... not found",
- trace/review files become non-empty when transcript/protocol content exists.

## Trigger and Evidence

Primary QA report:
- docs/HEAR-126-qa-evidence.md

Primary runtime evidence:
- deployment-evidence/hear-126/2026-04-19-hear-126/04-runtime-log-tail.txt
- deployment-evidence/hear-126/2026-04-19-hear-126/05-runtime-error-signatures.txt
- deployment-evidence/hear-126/2026-04-19-hear-126/07-trace-store.json
- deployment-evidence/hear-126/2026-04-19-hear-126/08-review-store.json

Key reproduced signatures:
- Failed to persist segment: transcript_segments_meeting_id_fkey
- Protocol rebuild failed
- Failed to end meeting in DB: Meeting '...' not found

## Primary Files To Inspect

- src/ayehear/app/window.py
- src/ayehear/services/transcription.py
- src/ayehear/storage/repositories.py
- tests/test_hear_124_meeting_lifecycle_fk.py
- tests/test_hear_084_persistent_lifecycle.py

## Likely Failure Surface

1. Active meeting id and DB durability diverge during error recovery.
2. _handle_persistence_error() always rolls back and may reload persistence layer during an active meeting.
3. _reload_persistence_layer() replaces the session and repos without validating active meeting continuity.
4. Transcription/protocol timers continue against a meeting id that may no longer resolve in the current repo/session.

## Constraints

- Keep architecture local-only and deterministic.
- No network dependency changes.
- No schema-breaking migration unless strictly required.
- Keep hotfix scoped to lifecycle/persistence behavior.
- Preserve existing HEAR-124 guardrails and do not regress their tests.

## Required Outcomes

1. Meeting row exists and remains endable for the full active meeting lifecycle.
2. TranscriptSegmentRepository.add() can persist segments for active meeting ids in installed runtime.
3. Protocol rebuild does not enter persistent failure loop after one segment persistence error.
4. Review and trace stores reflect generated content (not always empty for contentful runs).

## Acceptance Focus

- zero transcript_segments_meeting_id_fkey errors in installed run,
- zero "Failed to end meeting in DB" for the same run,
- protocol rebuild stable for active meeting,
- evidence bundle for rerun shows non-empty trace/review when applicable.

## Minimum Tests To Run

- tests/test_hear_124_meeting_lifecycle_fk.py
- tests/test_hear_084_persistent_lifecycle.py
- tests/test_hear_047_speaker_attribution.py
- targeted new regression tests for persistence reload + active meeting continuity

## Suggested Implementation Strategy

1. Add explicit active-meeting continuity checks around persistence reload.
2. Avoid blind rollback/reload for non-recoverable logical state mismatches; classify errors.
3. Ensure meeting start durability is validated after any repo/session swap.
4. Gate transcript writes if meeting cannot be resolved, with deterministic recovery path.
5. Add regression test that simulates installed-like flow: start meeting -> protocol error/reload path -> continue transcription -> stop meeting.

## Expected Evidence Updates

- New developer implementation notes in task system.
- Fresh installed E2E rerun evidence bundle under deployment-evidence/hear-126 or follow-up task folder.
- Updated QA report with GO/NO-GO after rerun.

## Ready-To-Use Claude Prompt

Implement the HEAR-126 persistence follow-up hotfix in AYE Hear.

Context:
- HEAR-126 installed-package E2E for 0.5.5 is NO-GO.
- Runtime still shows transcript FK failures, protocol rebuild cascade, and failed meeting end.

Read first:
- docs/HEAR-126-qa-evidence.md
- deployment-evidence/hear-126/2026-04-19-hear-126/04-runtime-log-tail.txt
- src/ayehear/app/window.py
- src/ayehear/services/transcription.py
- src/ayehear/storage/repositories.py
- tests/test_hear_124_meeting_lifecycle_fk.py

Deliver:
- minimal code fix for lifecycle/persistence continuity,
- regression tests for the failing sequence,
- short note explaining root cause and why the fix prevents FK and meeting-end failures,
- verification commands and outcomes.
