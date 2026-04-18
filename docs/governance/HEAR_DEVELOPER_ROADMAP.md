---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-08
category: implementation-roadmap
---

# AYE Hear Developer Roadmap

## Related Planning Documents

- V2 backlog baseline and status tracking: `docs/governance/HEAR_V2_BACKLOG.md`

## Purpose

This roadmap defines the architecture-approved implementation order after Phase-1 architect decisions.

## Preconditions

- ADR-0001 through ADR-0008 are accepted
- PostgreSQL local runtime model is fixed
- Persistence contract and system boundaries are documented

## Implementation Sequence

1. PostgreSQL connection and migration bootstrap
2. ORM/domain models for meetings, participants, speaker profiles, transcript segments, protocol snapshots and action items
3. Storage facade and repository layer (PostgreSQL only)
4. Audio capture service integration (Windows path)
5. Enrollment flow and speaker profile lifecycle
6. Transcription pipeline integration
7. Diarization and speaker matching integration
8. Protocol engine generation and snapshot versioning
9. UI review and correction workflow completion
10. End-to-end validation across the full meeting lifecycle

## Dependency Rules

- Steps 1 to 3 are mandatory foundation gates
- Steps 4 to 8 can be parallelized where interfaces are stable
- Step 9 depends on upstream service availability
- Step 10 depends on all previous steps

## Suggested Workstream Split

- AYEHEAR_DEVELOPER: steps 1 to 9 implementation delivery
- AYEHEAR_QA: test design and acceptance gates from step 4 onward
- AYEHEAR_SECURITY: storage/privacy reviews at steps 3, 5, 8
- AYEHEAR_DEVOPS: packaging and release readiness from step 1 onward

## Risk Focus

- Runtime consistency for local PostgreSQL lifecycle on Windows
- Confidence-threshold handling in speaker assignment and manual correction
- Protocol snapshot immutability and rollback-safe versioning
- UI responsiveness under concurrent background processing

## Phase-1B Active Tasks

- HEAR-008: PostgreSQL Bootstrap and Migration Pipeline (AYEHEAR_DEVELOPER)
- HEAR-009: ORM Domain Models (Meeting/Speaker/Transcript/Protocol) (AYEHEAR_DEVELOPER)
- HEAR-010: Storage Facade and Repository Layer (AYEHEAR_DEVELOPER)
- HEAR-011: Audio Capture Integration (Windows Path) (AYEHEAR_DEVELOPER)
- HEAR-012: Speaker Enrollment and Profile Lifecycle (AYEHEAR_DEVELOPER)
- HEAR-013: Transcription Pipeline Integration (AYEHEAR_DEVELOPER)
- HEAR-014: Diarization and Speaker Matching (AYEHEAR_DEVELOPER)
- HEAR-015: Protocol Engine Snapshot Versioning (AYEHEAR_DEVELOPER)
- HEAR-016: UI Review and Manual Correction Workflow (AYEHEAR_DEVELOPER)
- HEAR-017: Windows Packaging and Local Runtime Operations (AYEHEAR_DEVOPS)
- HEAR-018: QA Test Strategy and Acceptance Matrix (AYEHEAR_QA)
- HEAR-019: Security Review Baseline (Local Privacy and Storage) (AYEHEAR_SECURITY)

## Definition of Ready for Phase-1B

- This roadmap is accepted by AYEHEAR_ARCHITECT
- Role owners agree on sequencing and dependencies
- Initial task batch per role is created in Task-CLI
