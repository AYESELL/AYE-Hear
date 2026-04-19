---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-19
category: execution-briefs
---

# Claude Execution Briefs - Quality-First Wave

This directory contains the explicit execution briefs required by HEAR-114 for
developer tasks intended for Claude Code.

Purpose:
- keep Task-CLI as the workflow system of record,
- provide Claude Code with concrete implementation instructions,
- avoid relying on task title/description alone as the execution prompt.

## Brief Index

- HEAR-115: [HEAR-115-asr-profile-tuning.md](HEAR-115-asr-profile-tuning.md)
- HEAR-116: [HEAR-116-action-item-quality-engine.md](HEAR-116-action-item-quality-engine.md)
- HEAR-117: [HEAR-117-confidence-review-workflow.md](HEAR-117-confidence-review-workflow.md)
- HEAR-118: [HEAR-118-protocol-traceability.md](HEAR-118-protocol-traceability.md)
- HEAR-126 Follow-up: [HEAR-126-followup-persistence-hotfix.md](HEAR-126-followup-persistence-hotfix.md)

## Usage Rule

For Claude Code execution:

1. Start the Task-CLI task normally.
2. Open the corresponding brief in this directory.
3. Use the brief as the primary execution prompt.
4. Record implementation notes back into the task.

## Start Conditions

- HEAR-115 should start only after HEAR-113 provides the ASR benchmark decision.
- HEAR-116, HEAR-117, and HEAR-118 may proceed in parallel, provided the architect-approved scope in `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md` is not exceeded.