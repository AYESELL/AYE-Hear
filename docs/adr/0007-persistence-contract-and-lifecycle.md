---
status: accepted
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0007: Persistence Contract and Lifecycle

## Context

AYE Hear needs a canonical persistence contract that aligns the UI shell, audio pipeline, speaker identification flow and meeting protocol engine on one PostgreSQL-backed model.

Without this contract, implementation would drift across services and manual correction, auditability and protocol versioning would remain ambiguous.

## Decision

AYE Hear adopts the following canonical PostgreSQL persistence entities for V1:

1. `meetings`
2. `participants`
3. `speaker_profiles`
4. `transcript_segments`
5. `protocol_snapshots`
6. `protocol_action_items`

### Canonical Entities

#### `meetings`
- primary meeting record and lifecycle container
- fields include `id`, `title`, `started_at`, `ended_at`, `status`, `created_at`, `updated_at`
- owns the top-level relation for transcript and protocol artifacts

#### `participants`
- meeting-scoped participant registration
- fields include `id`, `meeting_id`, `speaker_profile_id`, `display_name`, `enrollment_status`, `created_at`, `updated_at`

#### `speaker_profiles`
- reusable enrolled speaker identity records
- fields include `id`, `display_name`, `embedding_vector`, `embedding_version`, `created_at`, `updated_at`
- embedding storage is PostgreSQL-native and must support pgvector-backed similarity search

#### `transcript_segments`
- transcript output units with speaker attribution state
- fields include `id`, `meeting_id`, `participant_id`, `start_ms`, `end_ms`, `segment_text`, `confidence_score`, `manual_correction`, `created_at`, `updated_at`

#### `protocol_snapshots`
- immutable protocol revisions generated from reviewed transcript state
- fields include `id`, `meeting_id`, `snapshot_version`, `snapshot_content`, `engine_version`, `generated_at`

#### `protocol_action_items`
- normalized actionable outputs from protocol snapshots
- fields include `id`, `protocol_snapshot_id`, `assignee_participant_id`, `title`, `description`, `status`, `due_date`, `created_at`, `updated_at`

## Lifecycle Rules

### Meeting Lifecycle

1. Create `meetings` record
2. Register `participants`
3. Resolve or create `speaker_profiles` during enrollment
4. Persist `transcript_segments` during capture and review
5. Generate immutable `protocol_snapshots`
6. Persist extracted `protocol_action_items`

### Manual Correction

- Speaker correction is mandatory when confidence is insufficient
- `manual_correction = true` marks reviewed transcript assignments
- Protocol generation must prefer reviewed transcript state over raw model output

### Versioning

- `protocol_snapshots` are append-only
- existing snapshots are never overwritten in place
- snapshot version increases monotonically within one meeting

## Consequences

**Positive:**
- One canonical storage contract across all subsystems
- Clear ownership of transcript corrections and protocol revisions
- Supports speaker matching, auditability and future export flows

**Negative:**
- Initial schema design is more deliberate than an ad hoc local store
- pgvector becomes part of the baseline PostgreSQL capability set

**Mitigations:**
- Keep flexible meeting and protocol metadata in structured JSON fields where justified
- Preserve append-only snapshot semantics to simplify review and recovery

## Related Documents

- [docs/architecture/SYSTEM_BOUNDARIES.md](../architecture/SYSTEM_BOUNDARIES.md)

## Related ADRs

- ADR-0003: Speaker Identification & Diarization Pipeline
- ADR-0005: Meeting Protocol Engine & LLM
- ADR-0006: PostgreSQL Local Deployment Model on Windows
- ADR-0008: Hardware Profiles and Acceleration Strategy

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08