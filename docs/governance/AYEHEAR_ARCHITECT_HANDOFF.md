---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-04-08
category: handoff
---

# AYE Hear Architect Handoff

## Purpose

This document hands over the current AYE Hear repository baseline to the responsible AYEHEAR_ARCHITECT and establishes the immediate architectural priorities.

## Current Repository Baseline

The repository already contains:

- Product framing in docs/PRODUCT_FOUNDATION.md
- Core ADR set in docs/adr/0001 through 0005
- Governance baseline in docs/governance/
- Quick references in docs/quick-refs/
- Local Python desktop scaffold in src/ayehear/
- Initial CI smoke workflow in .github/workflows/windows-build.yml
- Role-specific agent files in .github/agents/

## Architectural Non-Negotiables

The following constraints are mandatory and already reflected in the repository:

1. PostgreSQL is the only valid database target for AYE Hear.
2. No secondary embedded database path is part of the architecture or may be reintroduced.
3. The product remains offline-first with no cloud runtime dependency.
4. Speaker identification is mandatory from the beginning, with confidence scoring and manual correction.
5. Windows desktop runtime is the primary execution model.

## Immediate Architect Tasks

1. Review and ratify ADR-0001 through ADR-0005.
2. Decide the canonical PostgreSQL runtime shape for local Windows deployments.
3. Approve the first persistence contract for meetings, speakers, transcript segments and protocol revisions.
4. Define the boundary between UI shell, audio pipeline, speaker identification and protocol engine.
5. Set the implementation order for:
   - PostgreSQL persistence
   - audio capture and enrollment
   - diarization and speaker matching
   - protocol engine integration

## Current Gaps Requiring Architectural Decision

### PostgreSQL Runtime on Windows

The repository is aligned to PostgreSQL conceptually, but the operational model still needs an explicit product decision:

- bundled local PostgreSQL
- managed local service prerequisite
- installer-managed PostgreSQL setup
- container-assisted local runtime for development only

This must be documented in a follow-up ADR before persistence implementation expands.

### Persistence Contract

The next architecture deliverable should define canonical entities such as:

- meetings
- participants
- speaker_profiles
- transcript_segments
- protocol_snapshots
- protocol_action_items

### Hardware Profiles

The product also needs a formal architecture note for CPU-only versus GPU-accelerated runtime tiers.

## Agent Configuration Status

The repository now follows the expected local structure for individual agents:

- .github/agents/ayehear-architect.agent.md
- .github/agents/ayehear-developer.agent.md
- .github/agents/ayehear-devops.agent.md
- .github/agents/ayehear-qa.agent.md
- .github/agents/ayehear-security.agent.md

This path is canonical for repository-local individual agents.

## Recommended Next Deliverables

1. ADR for PostgreSQL local deployment model on Windows.
2. ADR or design note for persistence schema and lifecycle.
3. First PostgreSQL-backed data access layer in src/ayehear/storage/.
4. Task batch for AYEHEAR_DEVELOPER, AYEHEAR_QA and AYEHEAR_SECURITY.

## Phase 1 Architecture Task Batch — READY FOR IMPORT

All 5 architecture tasks have been prepared and are ready for immediate import via Task-CLI:

| Document                                       | Purpose                                                  | Location         |
| ---------------------------------------------- | -------------------------------------------------------- | ---------------- |
| HEAR_PHASE1_ARCHITECTURE_TASKBATCH.md          | Complete task specifications (5 tasks, AC, dependencies) | docs/governance/ |
| HEAR_PHASE1_TASKPAKET_AKTIVIERUNGSANLEITUNG.md | German summary + activation guide                        | docs/governance/ |
| HEAR_PHASE1_QUICK_START.md                     | 5-minute quick reference + import steps                  | docs/governance/ |
| Import-HEAR-Phase1-Architecture-Batch.ps1      | One-click PowerShell import script                       | tools/scripts/   |

**Quick Import:**

```powershell
cd G:\Repo\aye-hear
& .\tools\scripts\Import-HEAR-Phase1-Architecture-Batch.ps1
```

This creates tasks **HEAR-001 through HEAR-005** automatically with all AC and dependencies pre-configured.

**Tasks Created:**

- HEAR-001: ADR Ratification (5 SP)
- HEAR-002: PostgreSQL Runtime Decision (8 SP)
- HEAR-003: Persistence Contract & Schema (8 SP)
- HEAR-004: System Boundary Definition (8 SP)
- HEAR-005: Implementation Order Roadmap (5 SP)

**Total:** 34 Story Points | ~6-8 working days with parallelization

## Acceptance Of This Handoff

The handoff is complete when AYEHEAR_ARCHITECT confirms:

- ADR set is structurally acceptable
- PostgreSQL-only rule is enforced
- agent layout under .github/agents is accepted
- next architecture task batch is defined

**Phase 1 Architecture Task Batch Ready:** Import via `tools/scripts/Import-HEAR-Phase1-Architecture-Batch.ps1` or use Quick Start guide at `docs/governance/HEAR_PHASE1_QUICK_START.md`

**Acceptance Now Includes:**

- ✅ Tasks HEAR-001 through HEAR-005 are importable and ready to execute
- ✅ All AC and dependencies pre-configured in task batch
- ✅ Documentation complete (3 reference guides + PowerShell script)
- ✅ Phase 1B task templates prepared (for post-Phase-1 creation)

**Final Confirmation Needed:**

1. Architect reviews and accepts the 5 phase-1 tasks
2. Architect imports task batch (one PowerShell command)
3. Architect starts HEAR-001 and begins Phase 1
4. Upon Phase 1 completion, create Phase 1B batch for Developer/DevOps/QA/Security teams
