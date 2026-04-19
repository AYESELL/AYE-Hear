---
owner: AYEHEAR_ARCHITECT
status: imported
updated: 2026-04-19
category: task-batch
---

# AYE Hear V2 Short-Term Quality Wave Task Batch

## Purpose

This batch converts the short-term trust and review wave into executable tasks for delivery roles.

Source planning documents:

- docs/governance/HEAR_V2_BACKLOG.md
- docs/governance/HEAR_V2_IMPROVEMENT_IDEA_REGISTER.md
- docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md

## Scope Covered by This Batch

- V2-01 refinement: action-item quality scoring and sharpening hints
- V2-12: confidence-based review workflow
- V2-13: evidence-linked protocol traceability

## Import Result

Imported on 2026-04-19 into Task-CLI project hear.

Created tasks:

- HEAR-105 - Action-Item Quality Engine Plus
- HEAR-106 - Confidence Review Workflow
- HEAR-107 - Evidence-Linked Protocol Traceability
- HEAR-108 - Short-Term Quality Wave QA Validation
- HEAR-109 - Traceability and Review Privacy Check

## Batch Overview

| ID | Title | Role | Priority | SP | Purpose |
|---|---|---|---|---:|---|
| HEAR-105 | Action-Item Quality Engine Plus | AYEHEAR_DEVELOPER | high | 8 | Refine V2-01 with deterministic scoring and reason labels |
| HEAR-106 | Confidence Review Workflow | AYEHEAR_DEVELOPER | high | 8 | Build ranked uncertainty review queue |
| HEAR-107 | Evidence-Linked Protocol Traceability | AYEHEAR_DEVELOPER | high | 13 | Link protocol items to transcript evidence context |
| HEAR-108 | Short-Term Quality Wave QA Validation | AYEHEAR_QA | high | 5 | Validate scoring, queue, traceability, and export behavior |
| HEAR-109 | Traceability and Review Privacy Check | AYEHEAR_SECURITY | medium | 3 | Verify local-only evidence storage and no new outbound path |

## Task Specifications

### Action-Item Quality Engine Plus

**Owner:** AYEHEAR_DEVELOPER  
**Priority:** High  
**Story Points:** 8

**Description**

Refine V2-01 to score extracted action items for owner, due date, verb strength, measurability, and dependency clarity.

Required behavior:

- weak items are flagged as needing sharpening,
- explicit reason labels are visible,
- scoring is deterministic and reproducible,
- export reflects the final reviewed action-item quality state.

**Implementation Notes**

- Use docs/governance/HEAR_V2_BACKLOG.md V2-01 acceptance criteria.
- Use docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md Scope 1.
- No external model or service dependency may be introduced.

### Confidence Review Workflow

**Owner:** AYEHEAR_DEVELOPER  
**Priority:** High  
**Story Points:** 8

**Description**

Implement a ranked review queue for uncertain protocol items before final export.

Required behavior:

- queue sorted by severity,
- explicit uncertainty reasons,
- accept/edit/dismiss actions,
- persistence across restart and protocol revision changes.

**Implementation Notes**

- Use docs/governance/HEAR_V2_BACKLOG.md V2-12.
- Use docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md Scope 2.
- Manual review remains mandatory for flagged items.

### Evidence-Linked Protocol Traceability

**Owner:** AYEHEAR_DEVELOPER  
**Priority:** High  
**Story Points:** 13

**Description**

Implement local trace links from protocol decisions, tasks, and risks back to transcript context.

Required behavior:

- transcript excerpt, time range, speaker attribution state,
- distinction between direct evidence and inferred aggregation,
- persistence across restart and revision change,
- review UI access without external dependency.

**Implementation Notes**

- Use docs/governance/HEAR_V2_BACKLOG.md V2-13.
- Use docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md Scope 3.
- Security review is mandatory before completion.

### Short-Term Quality Wave QA Validation

**Owner:** AYEHEAR_QA  
**Priority:** High  
**Story Points:** 5

**Description**

Create and execute QA evidence for the short-term quality wave.

Minimum validation:

- deterministic action-item scoring cases,
- review queue ranking and persistence,
- traceability across restart and revision change,
- export correctness after user review.

### Traceability and Review Privacy Check

**Owner:** AYEHEAR_SECURITY  
**Priority:** Medium  
**Story Points:** 3

**Description**

Review whether the new quality and traceability wave preserves local-only storage and does not create any new data-exposure path.

Minimum validation:

- no outbound calls,
- trace links stored locally only,
- review queue data remains within approved runtime/data boundaries.

## Acceptance Tests and Deliverables

This section defines implementation-complete criteria for the short-term developer scope before QA and security sign-off.

### HEAR-105 Acceptance Tests and Deliverables

Acceptance tests:

- deterministic scoring test: identical input yields identical score and identical reason labels,
- reason-label coverage test: missing owner, missing due date, weak verb, low measurability,
- localization test: labels can be rendered in DE and EN without changing scoring logic,
- export integration test: reviewed sharpening state is represented in export output.

Deliverables:

- scoring rules documentation,
- test evidence for deterministic and reason-label behavior,
- updated user-facing wording for sharpening hints,
- implementation notes with touched modules and persistence impact.

### HEAR-106 Acceptance Tests and Deliverables

Acceptance tests:

- priority ordering test: queue consistently orders higher-risk items first,
- reason visibility test: each queue item shows explicit uncertainty cause,
- review action test: accept, edit, dismiss transitions produce expected protocol state,
- persistence test: queue state survives restart and reload of current meeting revision.

Deliverables:

- queue-state model description,
- review action state-machine summary,
- test evidence for ordering and persistence behavior,
- implementation notes with fallback and degraded-mode handling references.

### HEAR-107 Acceptance Tests and Deliverables

Acceptance tests:

- trace-link creation test: decision, action item, and risk entries receive source references,
- trace-context test: transcript excerpt, time range, and speaker-attribution state are accessible,
- revision-safety test: trace links remain stable across protocol revision updates,
- restart test: trace links persist across app restart,
- direct-vs-inferred labeling test: UI clearly distinguishes source-backed versus inferred entries.

Deliverables:

- trace-link persistence contract note,
- mapping documentation between protocol items and transcript context,
- test evidence for revision-safe behavior,
- implementation notes listing boundaries for transcript data exposure.

## Execution Order and Dependencies

The short-term wave must be delivered in a controlled sequence so QA and security can validate stable artifacts.

### Dependency Matrix

| Task | Depends On | Can Start | Completion Gate |
|---|---|---|---|
| HEAR-105 | none | immediately | deterministic scoring evidence complete |
| HEAR-106 | HEAR-105 | after HEAR-105 core scoring contract is stable | queue persistence and review actions validated |
| HEAR-107 | HEAR-106 | after HEAR-106 review-state contract is stable | traceability and revision safety validated |
| HEAR-108 | HEAR-105, HEAR-106, HEAR-107 | after all developer tasks are feature-complete | QA evidence package published |
| HEAR-109 | HEAR-107 | once trace-link persistence exists | security review note and no-outbound confirmation |

### Recommended Flow

1. Start HEAR-105 and lock deterministic scoring semantics.
2. Start HEAR-106 once HEAR-105 rule output is stable enough for ranking logic.
3. Start HEAR-107 once HEAR-106 review state transitions are stable.
4. Run HEAR-108 across all three developer outcomes as one integrated quality wave.
5. Complete HEAR-109 in parallel with late HEAR-108 once traceability persistence is testable.

### Parallelization Guardrails

- HEAR-108 test design may begin early, but execution evidence must wait for HEAR-107 implementation-complete.
- HEAR-109 can prepare checklist early, but final sign-off requires the implemented trace-link persistence path.
- No task in this wave is complete without explicit implementation notes and evidence links.

## Role Handoff Notes

### Handoff to AYEHEAR_DEVELOPER

Scope:

- HEAR-105, HEAR-106, HEAR-107.

Mandatory constraints:

- no external service dependency,
- no cloud calls,
- deterministic scoring and review behavior,
- persistence compatibility across restart and protocol revisions.

Definition of done for developer handoff:

- all acceptance tests in this document are implemented and passing,
- module-level implementation notes are written in task notes,
- touched UX states are documented for QA reproducibility.

### Handoff to AYEHEAR_QA

Scope:

- HEAR-108 integrated validation of HEAR-105 through HEAR-107 outputs.

QA focus:

- deterministic behavior under repeated runs,
- review queue ordering and action correctness,
- trace-link integrity across restart and revision updates,
- export consistency after review corrections.

Definition of done for QA handoff:

- consolidated evidence document with pass and fail observations,
- explicit mapping from each acceptance test to evidence artifact,
- residual risk list with severity and follow-up recommendation.

### Handoff to AYEHEAR_SECURITY

Scope:

- HEAR-109 review of traceability and review-data boundaries.

Security focus:

- no new outbound paths,
- local-only persistence of trace and review metadata,
- no unintended transcript-context leakage outside approved artifact boundaries.

Definition of done for security handoff:

- signed review note referencing inspected components,
- explicit confirmation that offline-first and local-storage guarantees remain intact,
- escalation notes for any detected boundary risk.

## Task Batch Creation Script

```powershell
Import-Module G:\Repo\platform-tools\tools\task-cli\task-cli.psd1 -Force

$tasks = @(
  @{
    Title = "Action-Item Quality Engine Plus"
    Role = "AYEHEAR_DEVELOPER"
    Priority = "high"
    Type = "TASK"
    StoryPoints = 8
    Description = "Implement V2-01 refinement from docs/governance/HEAR_V2_BACKLOG.md and docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md Scope 1. Deliver deterministic action-item scoring, explicit reason labels, and sharpening hints without new external dependencies."
  },
  @{
    Title = "Confidence Review Workflow"
    Role = "AYEHEAR_DEVELOPER"
    Priority = "high"
    Type = "TASK"
    StoryPoints = 8
    Description = "Implement V2-12 from docs/governance/HEAR_V2_BACKLOG.md and docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md Scope 2. Deliver ranked uncertainty review queue, explicit reasons, review actions, and persistent queue state."
  },
  @{
    Title = "Evidence-Linked Protocol Traceability"
    Role = "AYEHEAR_DEVELOPER"
    Priority = "high"
    Type = "TASK"
    StoryPoints = 13
    Description = "Implement V2-13 from docs/governance/HEAR_V2_BACKLOG.md and docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md Scope 3. Deliver local trace links from protocol items to transcript context with revision-safe persistence and clear direct-vs-inferred labeling."
  },
  @{
    Title = "Short-Term Quality Wave QA Validation"
    Role = "AYEHEAR_QA"
    Priority = "high"
    Type = "TASK"
    StoryPoints = 5
    Description = "Create and execute QA validation for the short-term quality wave. Cover deterministic scoring, review queue ordering and persistence, traceability across restart and revision change, and export correctness after review."
  },
  @{
    Title = "Traceability and Review Privacy Check"
    Role = "AYEHEAR_SECURITY"
    Priority = "medium"
    Type = "TASK"
    StoryPoints = 3
    Description = "Review the short-term quality wave for local-only evidence storage, absence of new outbound paths, and approved handling of transcript-backed trace context in review and persistence flows."
  }
)

New-TaskBatch -Tasks $tasks -BatchId "hear-v2-shortterm-quality-wave" -Project "hear" -CreatedByRole "AYEHEAR_ARCHITECT"
```