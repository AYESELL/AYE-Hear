---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-19
category: product-idea-register
---

# AYE Hear V2 Improvement Idea Register

## Purpose

This document captures architecture-screened product improvement ideas that go beyond the current V2 backlog baseline.

It serves three functions:

- document all currently discussed improvement candidates in one place,
- separate short-term implementation candidates from medium- and long-range ideas,
- map new ideas to existing backlog epics where possible to avoid duplicate scope.

## Evaluation Lens

All ideas in this register were screened against the current AYE Hear product direction:

- offline-first only,
- no cloud dependency,
- local traceability and reviewability,
- higher trust in protocol output over feature novelty,
- compatibility with manual override and confidence-based speaker handling.

## Idea Overview

| Rank | Idea | Horizon | User Value | Delivery Risk | Backlog Mapping |
|---|---|---|---|---|---|
| 1 | Action-item quality scoring and sharpening hints | Short | High | Low | Refines V2-01 |
| 2 | Uncertainty navigator before final export | Short | High | Medium | V2-12 |
| 3 | Evidence-linked protocol traceability | Short | High | Medium-High | V2-13 |
| 4 | Trust view per protocol statement | Short | Medium-High | Medium | Follows V2-12/V2-13 |
| 5 | Historical memory for recurring meetings | Medium | High | Medium | Related to V2-07 |
| 6 | Meeting modes by scenario | Medium | Medium-High | Medium | New candidate |
| 7 | Live acoustic health monitor | Medium | Medium | Low-Medium | Related to existing audio UX specs |
| 8 | Topic map instead of only linear transcript | Medium | Medium | Medium | Related to V2-05/V2-06 |
| 9 | Official review-and-release workflow for protocols | Long | High | Medium | New candidate |
| 10 | Silent moderator coach for meeting quality | Long | Medium-High | High | Related to V2-08 |

## Short-Term Focus

The recommended short-term wave is intentionally trust-centric rather than feature-broad.

### 1. Action-item quality scoring and sharpening hints

Why now:

- immediate business value,
- deterministic logic is feasible,
- directly improves protocol usefulness without new platform risk.

Target outcome:

- weak tasks become visible before export,
- users can correct owners, dates, and wording while context is still fresh.

Backlog decision:

- keep this inside V2-01,
- refine acceptance criteria instead of creating a duplicate epic.

### 2. Uncertainty navigator before final export

Why now:

- reduces manual review effort,
- improves trust without pretending AI certainty,
- aligns with quality gates and mandatory human review.

Target outcome:

- review focuses on the most risky items first,
- uncertainty reasons are explicit instead of hidden.

Backlog decision:

- added as V2-12 Confidence Review Workflow.

### 3. Evidence-linked protocol traceability

Why now:

- creates a strong differentiator for auditability,
- supports correction workflows and formal approval,
- strengthens the privacy-first argument because all evidence stays local.

Target outcome:

- users can inspect transcript origin for decisions, tasks, and risks,
- exports and reviews become easier to justify internally.

Backlog decision:

- added as V2-13 Evidence-Linked Protocol Traceability.

## Medium-Term Candidates

### Historical memory for recurring meetings

Idea:

- surface unresolved items, prior decisions, and repeated risks from earlier meetings.

Reason not short-term:

- depends on stable traceability and history linking semantics.

### Meeting modes by scenario

Idea:

- adapt extraction and export emphasis for board meeting, customer meeting, project status, or incident review.

Reason not short-term:

- requires configuration, UX, and prompt/rule differentiation that should build on the trust layer first.

### Live acoustic health monitor

Idea:

- show low signal, clipping, overlap, or noisy-room conditions while recording.

Reason not short-term:

- useful, but current trust bottleneck is more strongly tied to reviewability than capture feedback.

### Topic map instead of only linear transcript

Idea:

- present clustered themes, disagreement, and outcome state across the meeting.

Reason not short-term:

- depends on stronger segmentation and topic modeling maturity.

## Long-Term Candidates

### Official review-and-release workflow for protocols

Idea:

- distinguish draft, reviewed, approved, and official versions.

Reason not short-term:

- highest value once traceability and uncertainty workflows already exist.

### Silent moderator coach for meeting quality

Idea:

- give local hints about dominance, drift, and missing decisions while the meeting is still running.

Reason not short-term:

- requires reliable live signals and careful UX to avoid distraction or false authority.

## Recommended Sequencing

1. Deliver the short-term trust layer: V2-01 refinement, V2-12, V2-13.
2. Build on that with history and scenario-awareness.
3. Add more active live guidance only after reviewability and evidence quality are stable.

## Decision Note

Short-term prioritization deliberately favors review quality, traceability, and deterministic user value over additional model-driven intelligence.

This is the safer and more defensible route for AYE Hear's current maturity stage.