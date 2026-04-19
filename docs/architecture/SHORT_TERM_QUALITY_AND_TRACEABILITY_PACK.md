---
owner: AYEHEAR_ARCHITECT
status: ready-for-implementation
updated: 2026-04-19
category: architecture-spec
---

# Short-Term Quality and Traceability Pack

## Goal

Define the next short-term product wave that most directly improves trust in protocol output without violating offline-first, local-only, and manual-review constraints.

This pack covers three aligned scopes:

- V2-01 refinement for action-item quality,
- V2-12 Confidence Review Workflow,
- V2-13 Evidence-Linked Protocol Traceability.

## Why This Wave Comes Next

Current product value depends less on adding more intelligence and more on making generated output easier to trust, review, and correct.

The next delivery wave should therefore optimize for:

- faster human review,
- explicit uncertainty instead of hidden ambiguity,
- locally auditable protocol statements,
- clear improvement in export quality and operational usefulness.

## ADR Alignment

- ADR-0001: All processing remains local and offline-first.
- ADR-0003: Speaker uncertainty remains visible and manually correctable.
- ADR-0005: Protocol extraction remains staged, confidence-aware, and user-reviewable.
- ADR-0010: No completion claims without evidence-backed quality in V1-critical flows.
- ADR-0011: Runtime and artifact persistence remain install-root-relative.

## Scope 1: V2-01 Refinement - Action-Item Quality Engine Plus

## Problem

Extracted action items are only valuable if they are executable.

Current risk:

- tasks may be present but too vague,
- missing owner or due date is easy to miss,
- weak wording reduces operational follow-through.

## Product Intent

Every action item should receive a deterministic execution-quality score and clear sharpening hints.

The goal is not to invent new tasks, but to improve the quality of tasks already extracted.

## Required Deterministic Checks

At minimum the engine must evaluate:

- owner present,
- due date present,
- verb strength,
- measurability,
- dependency clarity when referenced.

## User-Facing Contract

- Weak items are visibly marked as needing sharpening.
- The user sees explicit reason labels, not only a numeric score.
- Review actions can improve the item before final export.

## Acceptance Addendum

- Reason labels must be stable and explainable.
- The same input produces the same score and same reasons.
- Localization may change labels, but not scoring semantics.

## Scope 2: V2-12 Confidence Review Workflow

## Problem

Users should not have to manually re-read the whole protocol to discover the few places that are most likely wrong.

Current risk:

- uncertainty is spread across transcript, speaker attribution, and extraction layers,
- review effort is too broad and insufficiently prioritized,
- low-trust items can slip into export unless the user performs an expensive full review.

## Product Intent

Create a ranked review queue that surfaces the most uncertain protocol items before final export.

## Required Inputs to Review Priority

The workflow must combine at least these signals:

- low speaker-confidence or unresolved speaker assignment,
- low transcript-confidence or noisy transcript segments,
- conflicting protocol extraction evidence,
- fallback-path usage or degraded runtime mode.

## User-Facing Contract

- The review queue is sorted by severity.
- Each item shows why it is flagged.
- The user can accept, edit, or dismiss the flagged protocol item.
- Review decisions update the final protocol state deterministically.

## Persistence Contract

- Review status must survive restart.
- Queue state must remain linked to the active meeting and current protocol revision.
- Auditability must remain local and bounded to the app runtime/data model.

## Out of Scope

- no external reviewer workflow,
- no cloud-based confidence service,
- no automatic silent acceptance of uncertain items.

## Scope 3: V2-13 Evidence-Linked Protocol Traceability

## Problem

Important protocol statements need local proof context if users are expected to trust, approve, and operationalize them.

Current risk:

- decisions and tasks appear as final statements with insufficient origin visibility,
- correction becomes slower because the user must search the transcript manually,
- approval workflows remain weaker than they could be.

## Product Intent

Each important protocol item should expose its source context from the transcript layer.

Traceability should cover at least:

- transcript excerpt,
- time range,
- speaker attribution state,
- whether the item is directly quoted or inferred from aggregation.

## User-Facing Contract

- From a decision, task, or risk item, the user can open the source context.
- The UI clearly distinguishes direct backing from inferred synthesis.
- Traceability remains available across restarts and revision changes.

## Persistence Expectations

- Trace links must be stored locally.
- Revision-safe references must not silently drift when protocol snapshots change.
- Export behavior may omit internal trace details for final external documents, but review views must retain them.

## Privacy and Security Constraints

- no external evidence store,
- no outbound transcript transmission,
- no additional cloud analytics,
- local data only, with the same storage governance as existing meeting artifacts.

## Sequencing and Dependency Guidance

Recommended implementation order:

1. V2-01 refinement
2. V2-12 review workflow
3. V2-13 traceability layer

Reasoning:

- V2-01 creates better structured items to review.
- V2-12 defines the review loop where uncertainty becomes actionable.
- V2-13 deepens that review loop with source evidence and auditability.

## QA and Security Expectations

QA must verify at least:

- deterministic scoring outcomes for action items,
- review queue ordering and persistence,
- traceability links across restart and revision changes,
- export behavior with and without reviewed corrections.

Security must verify at least:

- no new outbound paths,
- local-only storage of trace context,
- no leakage of transcript context outside the approved artifact boundaries.

## Architect Approval Note

Phase 3 implementation is approved for this short-term pack because the interfaces are product-facing but architecturally bounded:

- trust improves without weakening offline-first guarantees,
- human review becomes stronger rather than bypassed,
- new scope builds on existing transcript and protocol foundations instead of introducing a second interpretation stack.