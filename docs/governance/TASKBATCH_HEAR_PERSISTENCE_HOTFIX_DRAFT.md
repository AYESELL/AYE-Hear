---
owner: AYEHEAR_ARCHITECT
status: draft
updated: 2026-04-19
category: task-batch
---

# TaskBatch Draft - Persistence Hotfix Follow-Up after HEAR-128

## Purpose

Create a focused cross-role task batch to resolve the 0.5.5 NO-GO persistence failures documented in HEAR-126 and reconciled in HEAR-128.

Primary authority:
- docs/HEAR-128-readiness-reconciliation.md
- docs/HEAR-126-qa-evidence.md
- docs/HEAR-127-security-recheck.md

## Proposed Batch Metadata

- Batch ID: `hear-persistence-hotfix-20260419`
- Project: `hear`
- CreatedByRole: `AYEHEAR_ARCHITECT`

## Proposed Tasks (ready for New-TaskBatch)

```powershell
$tasks = @(
  @{
    Title = "Persistence lifecycle continuity fix"
    Role = "AYEHEAR_DEVELOPER"
    Priority = "critical"
    Type = "TASK"
    StoryPoints = 5
    Description = @"
Fix meeting lifecycle continuity so active meeting IDs remain DB-resolvable for the full session.

Acceptance Criteria:
1) During installed-runtime flow, transcript segment persistence does not hit transcript_segments_meeting_id_fkey.
2) Meeting-close path resolves the same persisted meeting ID and does not emit 'Meeting not found'.
3) Protocol rebuild does not enter repeated failure cascade after persistence recovery paths.
4) Root-cause note references affected code paths and explains durability guarantees.
"@
  },
  @{
    Title = "Persistence regression test expansion"
    Role = "AYEHEAR_DEVELOPER"
    Priority = "high"
    Type = "TASK"
    StoryPoints = 3
    Description = @"
Add regression coverage for installed-like lifecycle transitions around persistence reload/error handling.

Acceptance Criteria:
1) New test reproduces start meeting -> persistence error/recovery -> continued transcription -> end meeting.
2) Regression suite includes checks that no FK violation occurs and meeting end remains successful.
3) Existing HEAR-124 related tests remain green.
4) Test notes explain why the new case guards the prior 0.5.5 failure class.
"@
  },
  @{
    Title = "Installed E2E re-run for persistence hotfix candidate"
    Role = "AYEHEAR_QA"
    Priority = "critical"
    Type = "TASK"
    StoryPoints = 3
    Description = @"
Execute installed-package E2E re-validation on the next versioned candidate containing the persistence hotfix.

Acceptance Criteria:
1) Evidence bundle contains runtime logs, error signature extract, and export listing from installed run.
2) Zero transcript_segments_meeting_id_fkey errors in captured run.
3) Zero meeting-close 'Meeting not found' failures in captured run.
4) Explicit GO/NO-GO statement documented with mapped acceptance criteria.
"@
  },
  @{
    Title = "Traceability/review persistence evidence check"
    Role = "AYEHEAR_QA"
    Priority = "high"
    Type = "TASK"
    StoryPoints = 2
    Description = @"
Validate that runtime trace/review stores are populated when transcript/protocol content exists.

Acceptance Criteria:
1) Captured trace/review artifacts for contentful run are non-empty.
2) Stored artifacts map to the same meeting session under test.
3) Any remaining empty-store scenarios are classified as expected or defect with evidence.
"@
  },
  @{
    Title = "Security boundary recheck after persistence fix"
    Role = "AYEHEAR_SECURITY"
    Priority = "high"
    Type = "TASK"
    StoryPoints = 2
    Description = @"
Recheck that persistence hotfix changes do not regress offline-first or export-boundary security constraints.

Acceptance Criteria:
1) No new outbound/network path introduced by fix.
2) Local-only fallback and DB/session cleanup behavior remain deterministic and scoped.
3) Export artifacts still exclude internal trace/review JSON by default.
4) Security recommendation explicitly states APPROVED or NO-GO.
"@
  },
  @{
    Title = "Final readiness reconciliation for post-hotfix candidate"
    Role = "AYEHEAR_ARCHITECT"
    Priority = "critical"
    Type = "TASK"
    StoryPoints = 2
    Description = @"
Issue final GO/NO-GO readiness reconciliation after developer, QA, and security follow-ups complete.

Acceptance Criteria:
1) Reconciliation cites build, QA, and security evidence for the same candidate.
2) Authority statement clearly updates or preserves current release-state records.
3) Product/governance communication references are aligned and non-contradictory.
"@
  }
)

New-TaskBatch `
  -Tasks $tasks `
  -BatchId "hear-persistence-hotfix-20260419" `
  -Project hear `
  -CreatedByRole AYEHEAR_ARCHITECT `
  -DuplicateWindow 600 `
  -WhatIf
```

## Suggested Execution Sequence

1. Developer tasks first (fix + regression tests).
2. QA installed E2E and trace/review evidence tasks next.
3. Security boundary recheck in parallel with QA evidence analysis.
4. Architect reconciliation only after QA + Security outputs are complete.

## Notes

- This is a draft definition; `-WhatIf` is intentionally enabled.
- Remove `-WhatIf` only when ready to create tasks in Task-CLI.
