---
status: accepted
context_date: 2026-04-09
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0009: Data Protection and Encryption-at-Rest Model

## Context

AYE Hear stores locally captured meeting intelligence, participant identity data and speaker embeddings in PostgreSQL on Windows endpoints.

Phase-1B implementation and the security baseline identified two architecture gaps that must be closed before Phase-1C proceeds:

- no canonical classification for sensitive meeting data
- no approved encryption-at-rest model for the local PostgreSQL deployment

The model must preserve:

- offline-first operation without cloud key custody
- compatibility with the installer-managed PostgreSQL runtime from ADR-0006
- auditability expectations for manual speaker correction and participant identity review from ADR-0003 and ADR-0007
- a pragmatic Windows operational story for V1

## Decision

AYE Hear adopts a **layered local data-protection model** for V1:

1. **Canonical data classification in the application architecture**
2. **Mandatory volume-level encryption on managed Windows installations**
3. **Field-level protection for selected application secrets and future high-risk payloads**
4. **No source-controlled credentials or static encryption material**

### Data Classification

AYE Hear uses the following minimum classes:

#### `C_SENSITIVE`

- `speaker_profiles.embedding_vector` and related biometric matching artifacts
- `participants.display_name`, `first_name`, `last_name`, `salutation`, `organization`
- `transcript_segments.segment_text` and participant-linked transcript attribution
- `protocol_snapshots.snapshot_content`
- `protocol_action_items.title` and `description` when derived from sensitive meeting content

#### `C_INTERNAL`

- meeting metadata, timestamps, lifecycle state, model/runtime versions
- non-secret operational diagnostics that do not contain transcript text or biometric material

### Encryption-at-Rest Model

- Production Windows deployments must run on a machine where OS-managed disk encryption is enabled for the volume containing PostgreSQL data and local application state
- For managed enterprise environments, BitLocker is the canonical operational control; equivalent OS-managed protection must be documented if another Windows volume encryption control is used
- This volume-level encryption is the baseline required control for V1 release readiness
- Application and installer design must not assume plaintext disk access outside that protected volume

### Field-Level Protection Boundary

- PostgreSQL credentials, installer-generated secrets and future local API tokens must be stored via OS-protected secret storage or installer-protected configuration, not as plaintext in repository-tracked files
- AYE Hear reserves field-level cryptographic protection for local secrets, key-encryption material and future payloads that exceed the acceptable exposure window of volume-level encryption alone
- Transcript text and embeddings are not required to use column-level encryption in V1 if the mandatory disk-encryption and audit controls are in place, but the schema must remain compatible with later pgcrypto or application-layer encryption if threat posture changes

### Key Handling Responsibilities

- The installer or local administration workflow is responsible for generating installation-specific secret material
- Secret material must be rotatable without schema redesign
- No master key, DSN password or recovery secret may be hardcoded, baked into the installer image as a shared default or committed to source control
- Developer examples must use placeholders only

### Audit and Retention Expectations

- Any manual correction that changes participant attribution or speaker identity remains auditable under ADR-0003 and ADR-0007 follow-up implementation
- Security-sensitive data classes must have explicit retention defaults in downstream product and compliance documentation
- Export, deletion and profile reset workflows must treat speaker embeddings as biometric data and transcript text as sensitive meeting content

## Rationale

### Why layered protection instead of immediate column encryption everywhere

- V1 is a local Windows desktop product and already depends on machine-local operational controls
- Mandatory disk encryption materially reduces the exposure risk for lost devices and offline disk access
- Immediate blanket column encryption would add substantial implementation complexity to similarity search, review workflows and local recovery without changing the requirement that secrets still need separate handling

### Why classification is mandatory now

- Without a shared classification, downstream developer, QA and security tasks cannot reason consistently about retention, export, deletion and audit scope
- Biometric speaker embeddings require stricter treatment than generic meeting metadata

## Consequences

**Positive:**

- Security controls are explicit enough to unblock downstream implementation and QA validation
- Windows packaging, installer logic and QA can test against a concrete protection baseline
- Future migration to stronger field-level encryption remains possible without revisiting classification

**Negative:**

- Release readiness now depends on documented and testable Windows disk-encryption controls
- Some high-sensitivity local data still relies on host security posture in V1

**Mitigations:**

- Enforce BitLocker or equivalent as a deployment prerequisite in packaging and operations runbooks
- Keep secrets out of source-controlled config and examples
- Add audit logging and offline validation in downstream Phase-1C tasks

## Related ADRs

- ADR-0003: Speaker Identification & Diarization Pipeline
- ADR-0006: PostgreSQL Local Deployment Model on Windows
- ADR-0007: Persistence Contract and Lifecycle

## Related Governance Documents

- [docs/governance/HEAR_SECURITY_REVIEW_BASELINE_PHASE1B.md](../governance/HEAR_SECURITY_REVIEW_BASELINE_PHASE1B.md)

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-09
