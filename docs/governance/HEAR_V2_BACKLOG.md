---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-19
category: v2-backlog
version: 0.3.0
---

# AYE Hear V2 Backlog

## Purpose

This file is the single source of truth for V2 product backlog planning.
It is architecture-owned and must be updated whenever a V2 backlog item changes status.

Related planning documents:

- docs/governance/HEAR_V2_IMPROVEMENT_IDEA_REGISTER.md
- docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md

## Governance Rules

- Keep this file versioned in Git (every status change via commit).
- Update `updated` in frontmatter for every meaningful change.
- Add one entry to the Change Log for each update batch.
- Do not delete completed items; move them to "Completed".
- Keep IDs stable (`V2-01`, `V2-02`, ...).

## Status Model

- `planned`: scoped but not started
- `ready`: approved and ready for implementation
- `in-progress`: implementation active
- `review`: implementation done, awaiting QA/architect review
- `done`: accepted and closed
- `blocked`: cannot proceed due to dependency/risk

## Prioritization Buckets

- `Now`: 0 to 3 months
- `Next`: 3 to 6 months
- `Later`: 6 to 12 months

## Backlog Overview

| ID | Epic | Priority | SP | Status | Owner Role |
|---|---|---|---:|---|---|
| V2-01 | Action-Item Quality Engine | Now | 8 | planned | AYEHEAR_DEVELOPER |
| V2-02 | Decision Risk Radar | Now | 8 | planned | AYEHEAR_DEVELOPER |
| V2-03 | Persona Export Profiles | Now | 5 | planned | AYEHEAR_DEVELOPER |
| V2-04 | Meeting ROI Score | Now | 5 | planned | AYEHEAR_DEVELOPER |
| V2-05 | Scene Segmentation | Next | 8 | planned | AYEHEAR_DEVELOPER |
| V2-06 | Conflict and Consensus Map | Next | 8 | planned | AYEHEAR_DEVELOPER |
| V2-07 | Organizational Memory Linker | Next | 13 | planned | AYEHEAR_DEVELOPER |
| V2-08 | Live Moderator Assistant | Later | 13 | planned | AYEHEAR_DEVELOPER |
| V2-09 | Missing-Information Detector | Later | 13 | planned | AYEHEAR_DEVELOPER |
| V2-10 | Next-Meeting Necessity Predictor | Later | 8 | planned | AYEHEAR_DEVELOPER |
| V2-11 | Classical German Protocol and AYE Brand Layout | Now | 8 | planned | AYEHEAR_DEVELOPER |
| V2-12 | Confidence Review Workflow | Now | 8 | ready | AYEHEAR_DEVELOPER |
| V2-13 | Evidence-Linked Protocol Traceability | Now | 13 | ready | AYEHEAR_DEVELOPER |

**Total Estimated Scope:** 118 SP

## Detailed Epics

### V2-01 Action-Item Quality Engine (8 SP)

**Goal**
Automatically evaluate action items for execution quality.

**Acceptance Criteria**
- Every action item gets a score for owner, due date, verb clarity, measurability.
- Weak action items are flagged as "needs sharpening" in export with explicit reason labels.
- Reason labels cover at least missing owner, missing due date, weak verb, and low measurability.
- Score logic works language-agnostic with localized labels (DE/EN/FR).
- Scoring remains deterministic and explainable without requiring an additional cloud or model path.

### V2-02 Decision Risk Radar (8 SP)

**Goal**
Make decision quality and follow-up risk visible.

**Acceptance Criteria**
- Decision fields: owner, due date, dependency, risk are evaluated.
- Red/yellow/green risk level uses documented deterministic rules.
- Export includes "open decision risks" section.

### V2-03 Persona Export Profiles (5 SP)

**Goal**
Generate target-group specific protocol outputs.

**Acceptance Criteria**
- At least four profiles: CEO Briefing, Operations, Project Team, Compliance.
- Profiles control granularity, wording and section emphasis.
- Same meeting data produces reproducible profile-specific outputs.

### V2-04 Meeting ROI Score (5 SP)

**Goal**
Quantify meeting effectiveness.

**Acceptance Criteria**
- Score formula is transparent and documented.
- Score includes at least: decisions, action quality, speaking balance.
- Export includes top three positive/negative score drivers.

### V2-05 Scene Segmentation (8 SP)

**Goal**
Transform transcript into narrative meeting phases.

**Acceptance Criteria**
- Scene types include context, discussion, decision, next steps.
- Each scene has a time range and short summary.
- Scene sequence is readable and traceable in export.

### V2-06 Conflict and Consensus Map (8 SP)

**Goal**
Reveal disagreement and convergence per topic.

**Acceptance Criteria**
- Different positions are grouped under shared topics.
- Topic-level consensus state: open, partial, reached.
- Export marks unresolved or postponed topics.

### V2-07 Organizational Memory Linker (13 SP)

**Goal**
Detect repeated topics and link historical context.

**Acceptance Criteria**
- Similar current topics link to prior meeting references.
- Linked decisions include last known status.
- History context can be toggled in output.

### V2-08 Live Moderator Assistant (13 SP)

**Goal**
Give non-intrusive live guidance for meeting quality.

**Acceptance Criteria**
- Detect at least speaking dominance, topic drift, no decision trend.
- Hinting is silent-friendly and can be disabled.
- Offline-first principle is fully preserved.

### V2-09 Missing-Information Detector (13 SP)

**Goal**
Identify critical blind spots after meeting end.

**Acceptance Criteria**
- Detect at least six gap types (e.g., no owner, no deadline, no KPI).
- Gaps are risk-prioritized.
- Provide concrete follow-up prompts.

### V2-10 Next-Meeting Necessity Predictor (8 SP)

**Goal**
Recommend whether a follow-up meeting is needed.

**Acceptance Criteria**
- Recommendation uses open points, risk and dependency signals.
- Explanation is explicit and user-readable.
- Outcome classes: no follow-up, async follow-up, short decision meeting.

### V2-11 Classical German Protocol and AYE Brand Layout (8 SP)

**Goal**
Deliver protocol exports in AYE visual style while following a classical German meeting-minutes structure.

**Acceptance Criteria**
- Output header includes mandatory metadata fields: meeting title, short summary, location, meeting date/time, participant list.
- Output includes protocol metadata: protocol version and protocol creation date.
- Output body keeps structured sections for results, decisions, protocol notes, tasks and open items.
- Layout, typography and colors follow AYE design tokens and export style rules (ADR-0014 alignment).
- Generated protocol template is consistent across Markdown, DOCX and PDF exports.
- Protocol footer contains product branding statement: "This protocol was automatically created with help from AYE Hear." (localized DE/EN/FR).
- Protocol includes mandatory AI-assistance disclaimer stating that transcript/protocol quality can be affected by model limitations and acoustic issues, and that human review is required before official use.
- Protocol may include a compliance statement for GDPR and EU AI Act alignment only when release evidence and active runtime configuration support that claim.
- Compliance statement must include offline-processing attestation that no protocol/transcript content left the local application boundary during the recorded session.

### V2-12 Confidence Review Workflow (8 SP)

**Goal**
Reduce review effort by focusing the user on the most uncertain protocol statements before final export.

**Acceptance Criteria**
- Review queue ranks uncertain items by explicit reason and severity.
- Uncertainty reasons include at least low speaker confidence, low transcript confidence, conflicting extraction signals, and fallback-path usage.
- User can accept, edit, or dismiss flagged items and the final protocol reflects the reviewed decision.
- Workflow remains fully local and does not require any external service.

### V2-13 Evidence-Linked Protocol Traceability (13 SP)

**Goal**
Make protocol statements auditable by linking decisions, tasks, and risks back to the transcript context that produced them.

**Acceptance Criteria**
- Decisions, action items, and risks can be opened with transcript excerpt, speaker attribution, and time range context.
- Traceability links are persisted locally and survive app restart and protocol revision changes.
- Review UI makes it clear whether a protocol item has direct transcript backing or was inferred from aggregation.
- Export and review behavior remains compliant with offline-first and local-storage-only principles.

## Current Delivery Wave

- Wave 1 (Now): V2-01 to V2-04, V2-11 to V2-13
- Wave 2 (Next): V2-05 to V2-07
- Wave 3 (Later): V2-08 to V2-10

## Operating Procedure for Updates

Use this checklist on every backlog update:

1. Adjust status in Backlog Overview table.
2. Update `updated` date in frontmatter.
3. Increment `version` (patch for status changes, minor for new epics, major for structure changes).
4. Add Change Log entry.
5. Commit with conventional message, e.g.:
   - `docs(backlog): update V2-03 status to in-progress`
   - `docs(backlog): add V2-11 compliance assistant epic`

## Change Log

### 2026-04-19 (v0.3.0)

- Added planning references for the V2 idea register and short-term design pack.
- Refined V2-01 acceptance criteria with explicit reason labels and deterministic scoring expectations.
- Added V2-12 Confidence Review Workflow as ready short-term scope.
- Added V2-13 Evidence-Linked Protocol Traceability as ready short-term scope.
- Updated Wave 1 and total estimated scope from 97 SP to 118 SP.

### 2026-04-18 (v0.2.2)

- Extended V2-11 with conditional GDPR/EU AI Act compliance statement requirement.
- Added mandatory offline-processing attestation requirement for protocol compliance footer text.

### 2026-04-18 (v0.2.1)

- Extended V2-11 with mandatory product-branding footer text in protocol exports.
- Extended V2-11 with mandatory AI-assistance disclaimer and explicit human-review requirement.

### 2026-04-18 (v0.2.0)

- Added V2-11 for classical German protocol structure with AYE brand-compliant styling.
- Added mandatory protocol metadata requirements (version and creation date).
- Updated delivery wave mapping and total scope from 89 SP to 97 SP.

### 2026-04-18 (v0.1.0)

- Created initial V2 backlog baseline with V2-01 to V2-10.
- Added acceptance criteria, SP sizing, and priority waves.
- Defined update procedure for ongoing maintenance.
