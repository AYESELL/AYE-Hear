---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-19
category: architecture-plan
---

# Quality-First Next Release Scope

## Decision Summary

The next release after `0.5.3` should prioritize output trust and ASR-informed quality improvement over additional product intelligence.

Reason:
- the current product is functionally complete for the approved V1 scope,
- the main user-visible weakness is still transcript quality and the downstream protocol quality that depends on it,
- adding broader interpretation features before improving reviewability and understanding ASR/runtime trade-offs would increase risk faster than value.

## Approved Release Goal

Improve practical protocol quality for real usage without materially increasing runtime complexity before the next intensive validation cycle.

This release should optimize for:
- better human review of uncertain output,
- more trustworthy task quality,
- local auditability of protocol statements,
- evidence-based ASR profile selection on target hardware.

## Approved Feature Scope

### 1. ASR benchmark and hardware-aware profile decision

Purpose:
- determine whether `small` should remain default or whether `base` produces a better accuracy/latency trade-off on target hardware,
- measure CPU, RAM, and latency impact before expanding product intelligence further.

Expected outcome:
- one evidence-backed recommendation for the next release default profile,
- explicit go/no-go criteria for any heavier ASR profile change.

### 2. V2-01 Action-Item Quality Engine Plus

Purpose:
- improve the execution quality of already extracted action items,
- make weak items visible instead of silently exporting vague tasks.

Why included now:
- deterministic,
- low architectural risk,
- improves usefulness even when transcript quality is imperfect.

### 3. V2-12 Confidence Review Workflow

Purpose:
- rank the most uncertain protocol items before export,
- reduce the need for full manual re-reading.

Why included now:
- directly mitigates low-trust output,
- aligns with confidence-scored architecture and manual review requirements,
- bounded local-only implementation.

### 4. V2-13 Evidence-Linked Protocol Traceability

Purpose:
- let users inspect transcript backing for decisions, tasks, and risks,
- speed up correction and approval.

Why included now:
- strengthens trust without adding a second model stack,
- helps diagnose whether a problem came from transcript quality, speaker attribution, or extraction.

## Explicitly Deferred for the Following Release

### Deferred because they add interpretation breadth before root-cause quality is stabilized

- V2-02 Decision Risk Radar
- V2-04 Meeting ROI Score
- V2-05 Scene Segmentation
- V2-06 Conflict and Consensus Map
- V2-07 Organizational Memory Linker
- V2-08 Live Moderator Assistant
- V2-09 Missing-Information Detector
- V2-10 Next-Meeting Necessity Predictor

Reason:
- these features add more inference layers and/or continuous runtime work,
- they risk masking ASR weakness instead of making it diagnosable,
- they should follow only after the trust/review layer and ASR profile evidence are in place.

### Deferred because they are lower-value than trust improvement for the immediate release

- V2-03 Persona Export Profiles
- V2-11 Classical German Protocol and AYE Brand Layout

Reason:
- these may improve presentation and audience fit,
- they do not address the core complaint about wrong transcript input and low protocol trust.

## Release Sequencing

Recommended order:

1. ASR benchmark and profile recommendation
2. V2-01 Action-Item Quality Engine Plus
3. V2-12 Confidence Review Workflow
4. V2-13 Evidence-Linked Protocol Traceability
5. integrated QA, security review, and next release candidate validation

## Persona and Role Delegation

### AYEHEAR_DEVELOPER

Owns implementation for:
- ASR profile handling/config changes after benchmark decision,
- V2-01,
- V2-12,
- V2-13.

### AYEHEAR_QA

Owns:
- ASR benchmark execution,
- integrated validation of trust/review features,
- regression and runtime-load evidence.

### AYEHEAR_SECURITY

Owns:
- local-only persistence review for review/traceability state,
- confirmation that no outbound path or export leakage is introduced.

### AYEHEAR_ARCHITECT

Owns:
- scope freeze and sequencing,
- final release readiness reconciliation after evidence is complete.

## Claude Code / Agent Execution Decision

### Decision

Use Claude Code only for bounded implementation tasks with explicit briefings.

Good fit:
- V2-01 deterministic scoring implementation,
- V2-12 review queue integration,
- V2-13 traceability persistence and UI plumbing,
- narrowly scoped ASR config/profile adjustments after QA evidence exists.

Not a good primary fit:
- release-governance decisions,
- benchmark interpretation as sole authority,
- final QA or security sign-off.

### Task-CLI Integration Position

Current repo/tooling supports Task-CLI as a work queue and status tracker, but not as a direct Claude execution transport.

Implication:
- tasks can store title, description, owner role, story points, and implementation notes,
- tasks do not provide a dedicated Claude-specific prompt or execution field,
- therefore Claude work should be launched with an explicit task briefing prompt, using the task as the source of truth rather than the only instruction artifact.

### Required Briefing Pattern for Claude Code

For every developer task intended for Claude Code, create or provide a concise execution brief containing at least:

1. task goal and acceptance criteria,
2. approved files/modules to touch,
3. relevant ADRs and design docs,
4. required tests to run,
5. constraints on runtime load, offline-first behavior, and persistence boundaries,
6. expected evidence/doc updates.

Practical recommendation:
- keep the task in Task-CLI,
- generate one explicit prompt per developer task or tightly coupled task pair,
- attach or reference the prompt/brief from the task description or implementation notes.

## Release Gate Before Intensive Testing

Do not start the next intensive validation cycle until all of the following are true:

- ASR benchmark recommendation is documented,
- selected ASR profile/default is implemented or explicitly unchanged by evidence,
- V2-01, V2-12, and V2-13 implementation is complete,
- integrated QA/security task set is ready.

## Architect Approval

Phase 2 approval is granted for the scope above.

The next release should be a quality-first trust wave, not a breadth wave.