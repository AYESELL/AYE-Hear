---
batchId: hear-phase1-architecture
owner: AYEHEAR_ARCHITECT
status: ready-for-import
created: 2026-04-08
phase: Phase 1 Architecture (Governance & Decision)
---

# AYE Hear Phase 1 Architecture Task Batch

**Batch ID:** `hear-phase1-architecture`  
**Created By:** AYEHEAR_ARCHITECT  
**Status:** Ready for Import via Task-CLI  
**Update Date:** 2026-04-08

---

## Batch Overview

This batch establishes the foundational architectural decisions and governance framework for AYE Hear V1. All tasks follow the 8-Phase Workflow with explicit Phase gates and Acceptance Criteria. Tasks are sequenced to unblock downstream developer/DevOps/QA work.

### Batch Structure

| Task ID  | Title                                    | Role              | Priority | Type | Phase | Depends On                   |
| -------- | ---------------------------------------- | ----------------- | -------- | ---- | ----- | ---------------------------- |
| HEAR-001 | ADR Ratification: 0001-0005              | AYEHEAR_ARCHITECT | high     | TASK | 1-2   | —                            |
| HEAR-002 | PostgreSQL Runtime Decision on Windows   | AYEHEAR_ARCHITECT | high     | TASK | 2     | HEAR-001                     |
| HEAR-003 | Persistence Contract & Schema Approval   | AYEHEAR_ARCHITECT | high     | TASK | 2     | HEAR-002                     |
| HEAR-004 | System Boundary Definition               | AYEHEAR_ARCHITECT | high     | TASK | 2     | HEAR-001                     |
| HEAR-005 | Implementation Order & Developer Roadmap | AYEHEAR_ARCHITECT | high     | TASK | 2     | HEAR-002, HEAR-003, HEAR-004 |

---

## Individual Task Specifications

### HEAR-001: ADR Ratification: 0001-0005

**Owner:** AYEHEAR_ARCHITECT  
**Priority:** High  
**Phase:** 1-2 (PREP + CONTEXT)  
**Story Points:** 5

#### Description

Review and formally ratify ADR-0001 through ADR-0005 for AYE Hear:

- **ADR-0001:** Product Architecture (offline-first, Windows desktop, no cloud)
- **ADR-0002:** Windows Desktop App Stack (PySide6, Python 3.11+, PostgreSQL, Ollama)
- **ADR-0003:** Speaker Identification & Diarization (confidence scoring, manual override)
- **ADR-0004:** Audio Capture & Preprocessing (WASAPI, 16 kHz, Silero VAD)
- **ADR-0005:** Meeting Protocol Engine (local LLM, protocol aggregation, drafting)

Validate that each ADR:

- Follows the ADR template structure (Context, Decision, Consequences, Alternatives)
- Contains no conflicting database fallback references (PostgreSQL-only mandate)
- Aligns with offline-first principle
- Specifies observability/logging requirements
- Confirms cross-references in other ADRs

#### Implementation Notes

- Use docs/adr/README.md ADR template as checklist
- Verify each ADR title against 00XX-<title>.md filenames
- Check cross-references in ADR index
- Confirm no breaking changes from initial scaffold

#### Acceptance Criteria

- [ ] All 5 ADRs reviewed and marked as "Accepted" (status field)
- [ ] docs/adr/README.md index updated with all 5 ADRs listed
- [ ] No conflicting database references anywhere in ADR content (verified via grep)
- [ ] All 5 ADRs pass `pnpm docs:validate` (if applicable)
- [ ] Any required ADR updates committed to repository

#### Quality Gates

- [ ] Zero Lint/Compilation Errors
- [ ] No breaking ADR changes vs. current state
- [ ] Cross-reference links valid

---

### HEAR-002: PostgreSQL Runtime Decision on Windows

**Owner:** AYEHEAR_ARCHITECT  
**Priority:** High  
**Phase:** 2 (CONTEXT & DESIGN)  
**Story Points:** 8  
**Depends On:** HEAR-001

#### Description

Make an explicit architectural decision about how PostgreSQL is deployed/managed on Windows for local AYE Hear development and production:

**Decision Options:**

1. **Bundled PostgreSQL:** PostgreSQL binary bundled in installer (simplest, largest installer)
2. **Managed Service Prerequisite:** Assume user has PostgreSQL service running (smallest installer, highest user friction)
3. **Installer-Managed Setup:** NSIS installer manages PostgreSQL installation/initialization (moderate complexity, good UX)
4. **Container-Assisted (Dev-Only):** Docker/Podman for development; production uses option 1-3

**Evaluation Criteria:**

- User friction for first-time setup
- Installer size and deployment time
- Offline-first viability (can app run if PG is temporarily unavailable?)
- Development environment requirements
- Support burden for multiple OS versions (Windows 10, 11, Server)

#### Implementation Notes

- Create ADR-0006 documenting the decision
- Include deployment topology diagram (ASCII or Mermaid)
- Define "local PostgreSQL" network binding (127.0.0.1, named pipe, Unix socket compatibility)
- Specify PostgreSQL version lock (14.x, 15.x, 16.x)
- Document upgrade path for PostgreSQL version changes

#### Acceptance Criteria

- [ ] ADR-0006 created and set to "Accepted"
- [ ] PostgreSQL deployment model chosen (one of 4 options)
- [ ] Deployment diagram included in ADR
- [ ] PostgreSQL version lock decided (e.g., PostgreSQL 16+)
- [ ] Installer team (AYEHEAR_DEVOPS) has clear deployment spec
- [ ] docs/adr/README.md updated with ADR-0006

#### Quality Gates

- [ ] ADR passes architectural review (no unresolved trade-offs)
- [ ] No secondary database fallback mentioned anywhere
- [ ] Offline-first implications documented

---

### HEAR-003: Persistence Contract & Schema Approval

**Owner:** AYEHEAR_ARCHITECT  
**Priority:** High  
**Phase:** 2 (CONTEXT & DESIGN)  
**Story Points:** 8  
**Depends On:** HEAR-002

#### Description

Define and approve the canonical persistence contract for AYE Hear. This contract specifies the PostgreSQL schema entities that all subsystems (UI, audio, speaker ID, protocol engine) must implement and respect.

**Canonical Entities:**

1. **meetings:** Session metadata, timestamps, title, participant list
2. **participants:** Speaker profiles enrolled for this meeting (name, enrollment status, speaker embeddings foreign key)
3. **speaker_profiles:** Persistent speaker embeddings + metadata (speaker name, 768-dim vector, confidence baseline, created_at)
4. **transcript_segments:** Recognized speech segments (speaker_id, start_ms, end_ms, text, confidence, language)
5. **protocol_snapshots:** Timestamped protocol revisions (meeting_id, snapshot_number, content, timestamp, llm_used)
6. **protocol_action_items:** Extracted action items + assignments (protocol_snapshot_id, description, assignee, status, due_date)

**Contract Requirements:**

- All entities use surrogate keys (id BIGSERIAL PRIMARY KEY)
- Timestamps are UTC-normalized (created_at, updated_at)
- Speaker identification uses pgvector for embedding storage (768-dim float32)
- No PII is stored in plaintext without encryption justification
- Soft deletes or audit trail for protocol revisions
- Foreign key constraints enforce referential integrity

#### Implementation Notes

- Create design document: docs/architecture/PERSISTENCE_CONTRACT.md
- Include entity-relationship diagram (Mermaid or text)
- Define SQL data types and constraints for each entity
- Specify indexing strategy for speaker similarity search (pgvector functions)
- Document lifecycle (meeting creation → enrollment → transcription → protocol → completion)
- Security review required before storage layer implementation

#### Acceptance Criteria

- [ ] Design document PERSISTENCE_CONTRACT.md created and approved
- [ ] All 6 canonical entities defined with columns, types, constraints
- [ ] Entity-relationship diagram included
- [ ] pgvector usage documented for speaker embeddings
- [ ] Lifecycle flow documented (meeting → protocol)
- [ ] AYEHEAR_SECURITY reviews PII handling and encryption strategy (no secondary embedded DB fallback for sensitive data)
- [ ] docs/adr/README.md references new contract document

#### Quality Gates

- [ ] Design reviewed by AYEHEAR_SECURITY (PII, encryption, audit)
- [ ] No hardcoded credentials in schema example
- [ ] Zero conflicting database fallback mentions

---

### HEAR-004: System Boundary Definition

**Owner:** AYEHEAR_ARCHITECT  
**Priority:** High  
**Phase:** 2 (CONTEXT & DESIGN)  
**Story Points:** 8  
**Depends On:** HEAR-001

#### Description

Define clear subsystem boundaries for AYE Hear components:

**Subsystems:**

1. **Audio Pipeline:** Audio capture (WASAPI) → preprocessing (16 kHz, VAD) → Whisper transcription
2. **Speaker Identification:** Enrollment (pyannote speaker embedding capture) → Similarity matching (pgvector queries) → Diarization (speaker-to-segment assignment)
3. **Meeting Protocol Engine:** Transcript aggregation → LLM processing (Ollama) → action item extraction → persistent drafting
4. **UI Shell & Storage Facade:** Qt-based UI → Storage adapter (PostgreSQL) → Service orchestration

**Boundaries to Define:**

- Service-to-service communication patterns (sync or async; in-process or queue)
- Data ownership (which service owns which entities in persistence)
- Error handling & fallback strategy (e.g., if speaker ID fails, transcript still captured)
- Threading model (UI thread, audio capture thread, LLM thread)
- Configuration object passing (RuntimeConfig usage across services)

#### Implementation Notes

- Create design document: docs/architecture/SYSTEM_BOUNDARIES.md
- Include component architecture diagram (Mermaid)
- Define inter-service contracts (function signatures, error types)
- Specify thread safety guarantees for each subsystem
- Document testing strategy per subsystem (unit/integration boundaries)

#### Acceptance Criteria

- [ ] SYSTEM_BOUNDARIES.md created and approved
- [ ] 4 subsystems clearly defined with responsibilities
- [ ] Service communication patterns specified (sync/async, queue/direct)
- [ ] Data ownership per subsystem documented
- [ ] Error handling strategy for critical paths (transcription, speaker ID, protocol engine)
- [ ] Component architecture diagram included (Mermaid or text)
- [ ] AYEHEAR_QA has clear boundaries for test isolation

#### Quality Gates

- [ ] Architecture aligns with onion/layered principles
- [ ] No circular dependencies between subsystems
- [ ] Offline-first principle preserved

---

### HEAR-005: Implementation Order & Developer Roadmap

**Owner:** AYEHEAR_ARCHITECT  
**Priority:** High  
**Phase:** 2 (CONTEXT & DESIGN)  
**Story Points:** 5  
**Depends On:** HEAR-002, HEAR-003, HEAR-004

#### Description

Based on decisions from HEAR-001 through HEAR-004, define the canonical implementation order for AYEHEAR_DEVELOPER and AYEHEAR_QA teams.

**Typical Implementation Sequence:**

1. **PostgreSQL Connection Module** (unblocking persistence)
2. **ORM Models** (Speaker, Meeting, TranscriptSegment, ProtocolSnapshot, ActionItem)
3. **Storage Layer** (PostgreSQLStore data access layer)
4. **Audio Capture Service** (real WASAPI integration, testing harness)
5. **Speaker Enrollment Flow** (UI + persistence)
6. **Transcription Integration** (Whisper → storage)
7. **Diarization & Speaker Matching** (pyannote + pgvector queries)
8. **Protocol Engine** (LLM drafting → storage)
9. **UI Completion** (transcript review, manual corrections, protocol editing)
10. **End-to-End Testing** (full meeting lifecycle)

**Dependency Constraints:**

- Tasks 1-3 must complete before 4-8 can start
- Tasks 4-9 can proceed in parallel where possible
- Task 10 requires 1-9 complete

#### Implementation Notes

- Create roadmap document: docs/governance/HEAR_DEVELOPER_ROADMAP.md
- Define acceptance criteria per implementation block
- Specify communication channels for inter-task dependencies
- Document risk/mitigation for critical paths (PG availability, Whisper reliability)
- Recommend 2-3 sprint allocation per major block

#### Acceptance Criteria

- [ ] Roadmap document created with 10 implementation blocks
- [ ] Dependencies clearly mapped
- [ ] Per-block acceptance criteria defined
- [ ] Parallelization opportunities identified
- [ ] Risk assessment for critical paths included
- [ ] Task batch HEAR-101..199 prepared for AYEHEAR_DEVELOPER
- [ ] Task batch HEAR-201..299 prepared for AYEHEAR_DEVOPS
- [ ] Task batch HEAR-301..399 prepared for AYEHEAR_QA

#### Quality Gates

- [ ] Roadmap dependencies verified (no circular waits)
- [ ] Estimated critical path identified
- [ ] All subsystems (DEVELOPER, DEVOPS, QA, SECURITY) have clear next tasks

---

## Task Batch Creation Script

Below is the PowerShell script to import this task batch into the Task-CLI system. Ensure Task-CLI is loaded first.

```powershell
# Phase 1: Load Task-CLI
cd G:\Repo\aye-hear
Import-Module G:\Repo\platform-tools\tools\task-cli\task-cli.psd1 -Force

# Phase 2: Define Architecture Batch Tasks
$architectureBatch = @(
  @{
    Title       = "ADR Ratification: 0001-0005"
    Role        = "AYEHEAR_ARCHITECT"
    Priority    = "high"
    Type        = "TASK"
    StoryPoints = 5
    Description = "Review and formally ratify all 5 core ADRs (0001-0005). Validate structure, PostgreSQL-only mandate, offline-first alignment, observability requirements, and cross-references. Update docs/adr/README.md index."
  },
  @{
    Title       = "PostgreSQL Runtime Decision on Windows"
    Role        = "AYEHEAR_ARCHITECT"
    Priority    = "high"
    Type        = "TASK"
    StoryPoints = 8
    Description = "Create ADR-0006 documenting PostgreSQL deployment model decision (bundled, managed service, installer-managed, or container-assisted). Include deployment topology diagram and PostgreSQL version lock. Decision unblocks AYEHEAR_DEVELOPER persistence implementation."
  },
  @{
    Title       = "Persistence Contract & Schema Approval"
    Role        = "AYEHEAR_ARCHITECT"
    Priority    = "high"
    Type        = "TASK"
    StoryPoints = 8
    Description = "Create docs/architecture/PERSISTENCE_CONTRACT.md defining 6 canonical entities (meetings, participants, speaker_profiles, transcript_segments, protocol_snapshots, protocol_action_items). Include ER diagram, pgvector strategy for speaker embeddings, and PII handling per AYEHEAR_SECURITY review."
  },
  @{
    Title       = "System Boundary Definition"
    Role        = "AYEHEAR_ARCHITECT"
    Priority    = "high"
    Type        = "TASK"
    StoryPoints = 8
    Description = "Create docs/architecture/SYSTEM_BOUNDARIES.md defining 4 subsystems (Audio Pipeline, Speaker Identification, Meeting Protocol Engine, UI Shell). Include component architecture diagram, service communication patterns, data ownership, threading model, and test isolation strategy."
  },
  @{
    Title       = "Implementation Order & Developer Roadmap"
    Role        = "AYEHEAR_ARCHITECT"
    Priority    = "high"
    Type        = "TASK"
    StoryPoints = 5
    Description = "Create docs/governance/HEAR_DEVELOPER_ROADMAP.md with 10-step implementation sequence: PostgreSQL, ORM Models, Storage Layer, Audio Capture, Enrollment, Transcription, Diarization, Protocol Engine, UI, End-to-End Testing. Map dependencies, define per-block AC, identify parallelization and risk mitigations."
  }
)

# Phase 3: Create Task Batch
Write-Host "==> Creating HEAR Phase 1 Architecture Batch..."
New-TaskBatch -Tasks $architectureBatch `
  -BatchId "hear-phase1-architecture" `
  -CreatedByRole "AYEHEAR_ARCHITECT" | Select-Object Count, Status

# Phase 4: Verify Tasks Created
Write-Host ""
Write-Host "==> Verifying tasks (HEAR-001 through HEAR-005)..."
Get-Task -Role AYEHEAR_ARCHITECT -Status OPEN |
  Where-Object { $_.Id -match 'HEAR-(001|002|003|004|005)' } |
  Select-Object Id, Title, Priority |
  Format-Table -AutoSize

Write-Host ""
Write-Host "? Phase 1 Architecture batch created: hear-phase1-architecture"
Write-Host "? Next: AYEHEAR_ARCHITECT starts HEAR-001 (ADR Ratification)"
```

### Execution Steps

1. **Open Terminal:** PowerShell in `G:\Repo\aye-hear`
2. **Run Script:** Copy the script above and paste into terminal
3. **Verify Import:** Check that tasks HEAR-001 through HEAR-005 appear in Task-CLI with status `OPEN`
4. **Start Work:** `Start-Task -Id HEAR-001 -Force`

---

## Next Batch: Phase 1B (Dependent Tasks)

After HEAR-001 through HEAR-005 are completed and approved, create Phase 1B with downstream tasks:

- **HEAR-101..110:** AYEHEAR_DEVELOPER foundation tasks (PostgreSQL module, ORM, storage layer)
- **HEAR-201..210:** AYEHEAR_DEVOPS foundation tasks (Build pipeline, CI skeleton, installer layout)
- **HEAR-301..310:** AYEHEAR_QA foundation tasks (Test strategy, hardware profile matrix, quality gates)
- **HEAR-401..410:** AYEHEAR_SECURITY foundation tasks (Privacy audit, offline-first verification, credential handling)

---

## Traceability & Links

| Document                                                       | Purpose                | Status          |
| -------------------------------------------------------------- | ---------------------- | --------------- |
| [PRODUCT_FOUNDATION.md](../PRODUCT_FOUNDATION.md)              | Product brief          | Reference       |
| [AYEHEAR_ARCHITECT_HANDOFF.md](./AYEHEAR_ARCHITECT_HANDOFF.md) | Hand-off document      | Complete        |
| [ADR Index](../adr/README.md)                                  | Architecture decisions | 0001-0005 draft |
| [7-Phase Workflow](./7-PHASE-WORKFLOW.md)                      | Delivery discipline    | Reference       |
| [AGENTS.md](./AGENTS.md)                                       | Agent roles            | Reference       |

---

**Batch Owner:** AYEHEAR_ARCHITECT  
**Created:** 2026-04-08  
**Status:** Ready for Import
