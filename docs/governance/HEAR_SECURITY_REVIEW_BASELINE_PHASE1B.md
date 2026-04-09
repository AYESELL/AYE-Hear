---
status: draft
owner: AYEHEAR_SECURITY
reviewed_date: 2026-04-09
baseline_scope: Phase-1B Implementation (HEAR-008 through HEAR-017)
---

# AYE Hear Security Review Baseline (Phase-1B)

**Date:** 2026-04-09  
**Reviewer:** AYEHEAR_SECURITY  
**Scope:** Implementation review of Phase-1B tasks (storage bootstrap, ORM, data persistence, audio capture, speaker management)  
**Status:** Phase-5 VALIDATE gate assessment  

---

## Executive Summary

Phase-1B implementation establishes core data persistence, audio pipeline, and speaker identification subsystems. **Security posture is currently incomplete** with critical gaps in credential management, data classification, and operational control. **Recommended action: BLOCKER status until credential management and data-at-rest protection plan are implemented.**

---

## Findings by Category

### 🔴 CRITICAL FINDINGS

#### Finding C1: Hardcoded Credentials in DSN Example

**Location:** `src/ayehear/storage/database.py:36` (example DSN in docstring)  
**Severity:** CRITICAL  
**Finding:** Example shows plaintext credentials in DSN string:  
```python
config = DatabaseConfig(dsn="postgresql+psycopg://user:pass@localhost/ayehear")
```

**Impact:** If this pattern is copied to production code or configuration, credentials leak into:
- Source code repositories (git history)
- Process environment variables visible via `ps`
- Log files if DSN is logged
- Memory dumps

**Required Control:** 
- ❌ Credentials must NEVER appear in source code
- ✅ Implement environment variable loading for DSN: `os.environ.get("AYEHEAR_DB_DSN")`
- ✅ Credentials passed via secure installer setup or local encrypted store
- ✅ Runtime validation that DSN contains no plaintext passwords

**ADR Reference:** ADR-0006 (Windows Runtime) must define installer-provided credential injection  
**Status:** **BLOCKER — Phase-1B cannot proceed to Phase-6 (REVIEW) without this control**

---

#### Finding C2: No Data Classification or Encryption-at-Rest Policy

**Location:** ORM and storage layer (all entities)  
**Severity:** CRITICAL  
**Finding:** The following sensitive data types are stored in PostgreSQL WITHOUT defined encryption:
- Speaker embeddings (`speaker_profiles.embedding_vector`) — biometric data
- Participant names and company (`participants.display_name, organization`) — PII
- Transcript segments with speaker assignment (`transcript_segments.segment_text, participant_id`) — meeting minutes (sensitive)
- Protocol snapshots and action items — meeting intelligence

**Impact:** 
- Local PostgreSQL database file is unencrypted on Windows disk
- If device is compromised or hard drive accessed, all meeting intelligence and speaker profiles are exposed
- GDPR Art. 32 requires encryption-at-rest or equivalent safeguards for PII

**Evidence from Code:**
```python
# ORM entities with no encryption directives
embedding_vector: Mapped[list | None] = mapped_column(JSON, nullable=True)  # biometric!
segment_text: Mapped[str] = mapped_column(Text, nullable=False)  # meeting content
```

**Required Controls:**
1. **Data Classification (Immediate):**
   - C_SENSITIVE: Speaker embeddings, transcript text, participant identity, protocol decisions
   - C_INTERNAL: Meeting metadata, timestamps
   
2. **Encryption Strategy (Phase-1C blockers):**
   - PostgreSQL native: `pgcrypto` extension for C_SENSITIVE columns (transparent encryption)
   - OR: Application-layer encryption before PostgreSQL insert (envelope encryption)
   - OR: Windows EFS/BitLocker requirement (document as operational control)
   - Decision: ADR-0009 required ("Data Protection & Encryption Model")
   
3. **Key Management:**
   - Master encryption key must be protected (separate from data)
   - Installer must regenerate or derive key per installation
   - NEVER hardcode encryption keys

**ADR Reference:** New ADR-0009 required  
**Status:** **BLOCKER — Encryption model must be approved before Phase-1C**

---

#### Finding C3: No Access Control or Audit Trail for Speaker Data

**Location:** `services/speaker_manager.py`, repositories.py  
**Severity:** CRITICAL  
**Finding:** Speaker profile retrieval and modification has no logging or access control:
- `SpeakerProfileRepository.upsert()` can modify any profile without tracking WHO and WHEN
- No logging of profile updates or corrections
- No soft-delete or historical tracking of enrollment changes
- Manual correction workflow stores `manual_correction=true` but does not log the correction reason or approver

**Impact:**
- Insider threat: User or malware could silently alter speaker profiles to misattribute speech
- Auditability failure: Cannot prove speaker profiles were not tampered with
- GDPR Art. 5 (accountability): No audit trail for PII modification requests

**Required Controls:**
1. **Audit Logging (Phase-1C):**
   - Create `speaker_profile_audit_log` table:
     ```sql
     CREATE TABLE speaker_profile_audit_log (
       id UUID PRIMARY KEY,
       speaker_profile_id UUID NOT NULL REFERENCES speaker_profiles(id),
       action VARCHAR(50) NOT NULL,  -- 'created', 'updated', 'deleted', 'correction'
       old_embedding_vector JSONB,
       new_embedding_vector JSONB,
       changed_by_user VARCHAR(256),  -- local user context or service principal
       changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
       reason VARCHAR(512)  -- for manual_correction events
     );
     ```
   - Log all upsert operations with timestamp, reason

2. **Soft-Delete & Versioning:**
   - Add `is_deleted BOOLEAN DEFAULT FALSE` to `speaker_profiles`
   - Add `embedding_history` JSONB to track version progression
   - Never physically delete profiles

3. **Role-Based Manual Correction:**
   - Only AYEHEAR_DEVELOPER (app UI) can inspect/correct
   - Each correction requires reason entry
   - Correction stored as new audit log entry with reason

**ADR Reference:** ADR-0003 (Speaker ID) must specify audit trail semantics  
**Status:** **BLOCKER — Audit trail design must be reviewed before HEAR-012 completion**

---

### 🟠 HIGH FINDINGS

#### Finding H1: Audio Buffer Sensitive Data Retention

**Location:** `services/audio_capture.py` (4-second ring buffer in memory)  
**Severity:** HIGH  
**Finding:** Audio capture maintains a 4-second ring buffer in RAM for diarization look-ahead. This buffer contains raw audio and can be accessed by other processes (memory dump, debugger).

**Impact:**
- Unencrypted audio in memory could leak meeting content if VM/device is compromised
- Process debugging or crash dumps would contain audio samples

**Mitigation (Phase-1B):**
- ✅ Document: Ring buffer only retained for 4 seconds during active capture (minimal window)
- ✅ Clear buffer on capture stop: `buffer.clear()` or zero-out
- 🔄 Future (Phase-2): Consider mmap-backed buffer with memory-locking to prevent swap

**Status:** Documented, not blocking Phase-1B

---

#### Finding H2: No Validation of Local-Only Network Connectivity

**Location:** `storage/database.py` (PostgreSQL connection)  
**Severity:** HIGH  
**Finding:** Database connection to `localhost:5432` assumes installer correctly configured PostgreSQL as loopback-only. No runtime check verifies:
- PostgreSQL is not listening on network interfaces (0.0.0.0)
- Local firewall rules restrict external access to port 5432
- Honest but misconfigured installer could open PostgreSQL to LAN

**Impact:** If PostgreSQL accidentally listens on network interface, meeting data becomes remotely accessible without encryption

**Required Control:**
- Add startup validation in `DatabaseBootstrap._verify_connection()`:
  ```python
  # Check that PostgreSQL is loopback-only
  result = session.execute(text("SHOW listen_addresses"))
  listen_addr = result.scalar()
  if listen_addr != "localhost" and listen_addr != "127.0.0.1":
      raise RuntimeError(f"PostgreSQL listen_addresses={listen_addr}; must be localhost only")
  ```

**ADR Reference:** ADR-0006 (Windows Runtime) must mandate loopback-only PostgreSQL config  
**Status:** HIGH priority, can add to HEAR-008 or HEAR-017

---

#### Finding H3: Incomplete Offline-Only Validation (Missing Network Tests)

**Location:** All services  
**Severity:** HIGH  
**Finding:** No automated test validates that the application does NOT make external API calls:
- No network traffic inspection in test suite
- No integration test that runs offline (network disabled)
- Protocol engine integration with Ollama assumes loopback connectivity

**Impact:** Hidden network call to cloud API could be introduced accidentally in refactoring

**Required Testing (QA responsibility HEAR-018):**
- Test matrix should include "Offline Validation" scenario:
  - Disable networking
  - Start meeting
  - Verify application runs without network connectivity
  - Check for no `socket.connect()` or `requests.post()` calls to public IPs

**ADR Reference:** ADR-0005 ("Offline-First") must specify offline testing baseline  
**Status:** QA/HEAR-018, deferred to HEAR-018 completion validation

---

### 🟡 MEDIUM FINDINGS

#### Finding M1: No Credential Rotation or Expiration Policy

**Location:** Installer and runtime  
**Severity:** MEDIUM  
**Finding:** Once PostgreSQL credentials are set during installation, no password rotation mechanism exists

**Impact:** If PostgreSQL password is compromised (device stolen, user account compromised), password cannot be rotated without reinstalling

**Mitigation (Phase-1C+):**
- Document in ADR-0006: Installer creates signed credentials with optional expiration
- Add "Change Database Password" option in application settings
- Test password rotation scenario

**Status:** Deferred to Phase-1C, not blocking Phase-1B

---

#### Finding M2: Speaker Profile Biometric Data Classification

**Location:** `orm.py` SpeakerProfile entity  
**Severity:** MEDIUM  
**Finding:** Embed vectors (speaker embeddings) are biometric data under GDPR and some privacy laws, but classification is not explicit

**Impact:** May require explicit user consent and data minimization

**Mitigation (ADR-0009):**
- Explicitly mark `speaker_profiles.embedding_vector` as C_SENSITIVE
- Document: embeddings are retained for meeting duration + 30 days (configurable)
- Add "Delete All Speaker Profiles" option in UI
- Document data retention policy in GDPR consent form

**Status:** Requires ADR-0009 (data protection); document in UI consent workflow

---

#### Finding M3: Manual Correction Workflow Lacks Verification Logic

**Location:** `services/speaker_manager.py` (HEAR-016)  
**Severity:** MEDIUM  
**Finding:** Manual correction allows UI to reassign speaker identity to any participant without validation that that speaker is plausibly part of the meeting

**Impact:** User could accidentally assign unknown speaker to wrong participant (false positive)

**Mitigation (Phase-1C — HEAR-016):**
- Add validation: manual reassignment only to participants pre-registered for meeting
- Add confirmation dialog showing confidence score before correction
- Log correction reason (required field)

**Status:** Phase-1C task HEAR-016, add to acceptance criteria

---

### 🟢 LOW FINDINGS

#### Finding L1: Logging Sensitive Data in DEBUG Mode

**Location:** `app/window.py`, `services/*.py`  
**Severity:** LOW  
**Finding:** Development code has `logger.debug()` calls that may log transcripts or speaker names

**Example:**
```python
logger.debug("Created meeting %s", meeting.id)  # ✅ safe
# But future logs might include:
logger.debug("Transcript %s: %s", segment_id, segment_text)  # ❌ redact!
```

**Mitigation (Phase-1B):**
- Code review guideline: DEBUG logs must NOT include C_SENSITIVE data
- Use `logger.info()` for operational events only
- For debugging: wrap sensitive data: `logger.debug("Segment created: %s", redact(segment_text))`

**Status:** LOW, add to developer runbook

---

## Implementation Blockers Summary

| Blocker | Finding | Resolution | Owner | Target |
|---------|---------|-----------|-------|--------|
| **B1** | C1: Hardcoded credentials | Implement env-var loading + ADR-0006 credential injection | AYEHEAR_ARCHITECTURE (ADR-0006) | Phase-1B HOLD |
| **B2** | C2: No encryption-at-rest | Define encryption model in ADR-0009 + implement C_SENSITIVE marking | AYEHEAR_ARCHITECT + AYEHEAR_SECURITY | ADR-0009 (Phase-1C gate) |
| **B3** | C3: No audit trail | Design + implement speaker_profile_audit_log table + repository logging | AYEHEAR_DEVELOPER (HEAR-012) + HEAR-018 QA | HEAR-012 acceptance criteria |

---

## Required Controls Checklist

### Immediate (Must have before Phase-1B → Phase-6 REVIEW)

- [ ] **Credential Management:** Implement `os.environ.get("AYEHEAR_DB_DSN")` pattern
- [ ] **No Hardcoded Credentials:** Code audit and remove example hardcoded password from docstring
- [ ] **Loopback-Only Validation:** Add PostgreSQL listen_addresses check to bootstrap
- [ ] **Data Classification Plan:** Document C_SENSITIVE entities (speaker profiles, transcripts, participant names)
- [ ] **ADR-0006 Update:** Specify installer-managed credential provisioning (no hardcoding)
- [ ] **ADR-0009 Creation:** Define encryption model for C_SENSITIVE data (decision on pgcrypto vs app-layer vs OS-level)

### Phase-1C Blockers (Before Phase-1C tasks execute)

- [ ] **Encryption Implementation:** Finalize and implement encryption-at-rest per ADR-0009
- [ ] **Audit Trail Schema:** Create and deploy speaker_profile_audit_log table
- [ ] **Audit Logging Code:** Update SpeakerProfileRepository to log all upsert operations
- [ ] **Offline Testing:** Add network validation test to QA matrix (HEAR-018)
- [ ] **Manual Correction Validation:** Add participant-matching check to HEAR-016

### Documentation (Phase-1B completion)

- [ ] **Operational Security Runbook:** docs/governance/HEAR_SECURITY_RUNBOOK.md
  - Credential setup (installer responsibilities)
  - Local backup and recovery procedures
  - Incident response if device is lost or stolen
- [ ] **Data Retention Policy:** docs/governance/HEAR_DATA_RETENTION.md
  - How long speaker profiles are retained
  - How long transcripts/meeting data are retained
  - User data deletion request procedure (GDPR Art. 17)
- [ ] **Consent & Privacy Form:** docs/governance/HEAR_PRIVACY_FORM.md
  - User acknowledgment of local-only audio processing
  - Biometric data usage (speaker embeddings)
  - Data retention periods

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation | Status |
|------|------------|--------|-----------|--------|
| Credentials leak to source control | HIGH | CRITICAL | Env-var loading, no hardcoding rule | **BLOCKER** |
| Database accessed from LAN | MEDIUM | CRITICAL | Loopback-only validation + docs | **HIGH** |
| Speaker profiles tampered with (deliberate or accidental) | MEDIUM | HIGH | Audit trail + access logs | **BLOCKER** |
| Encryption-at-rest not implemented | HIGH | CRITICAL | ADR-0009 + implementation gate | **BLOCKER** |
| Meeting data recovered from unencrypted backup | MEDIUM | HIGH | Encryption + secure backup procedure docs | Phase-2 |
| Sensitive data in debug logs | LOW | MEDIUM | Code review guideline | Phase-1B documentation |

---

## Compliance Mapping

### GDPR

- **Art. 5 (Integrity & Confidentiality):** Encryption-at-rest (ADR-0009 & C2), Access logging (C3)
- **Art. 17 (Right to Erasure):** Data retention policy & deletion procedure required
- **Art. 32 (Security):** Encryption, audit trails, credential management (C1, C2, C3)

### Windows Security Best Practices

- **Credential Storage:** Use DPAPI (Data Protection API) or ask installer for user input (ADR-0006)
- **File Permissions:** PostgreSQL data directory should have restricted ACLs
- **Network Isolation:** Loopback-only binding (validation in H2)

---

## Next Steps (Phase-1B → Phase-1C Handoff)

1. **AYEHEAR_ARCHITECT:** Update ADR-0006 and create ADR-0009 with credential & encryption models
2. **AYEHEAR_DEVELOPER:** Implement blockers B1 & B3 (credential loading, audit trail schema & code)
3. **AYEHEAR_DEVELOPER:** Update HEAR-012 acceptance criteria to include audit trail validation
4. **AYEHEAR_SECURITY:** Validate ADR-0009 encryption model is adequate before Phase-1C execution
5. **AYEHEAR_QA:** Add offline & encryption validation to HEAR-018 acceptance matrix

---

## References

- [ADR-0003: Speaker Identification & Diarization](./0003-speaker-identification-and-diarization.md)
- [ADR-0004: Audio Capture & Preprocessing](./0004-audio-capture-and-preprocessing.md)
- [ADR-0005: Offline-First Architecture](./0005-offline-first-architecture.md) (if exists)
- [ADR-0006: Windows Runtime & Deployment](./0006-windows-runtime-and-deployment.md)
- [ADR-0007: Persistence Contract & Lifecycle](./0007-persistence-contract-and-lifecycle.md)
- **ADR-0009 (TO BE CREATED):** Data Protection & Encryption Model
- [PRODUCT_FOUNDATION.md](../PRODUCT_FOUNDATION.md)
- [Governance: QUALITY_GATES.md](./QUALITY_GATES.md)

---

**Baseline Status:** READY FOR PHASE-1C PLANNING  
**Security Blockers:** 3 CRITICAL (credentials, encryption, audit trail)  
**Estimated Resolution Time:** 1–2 sprints (Phases 1B–1C)  
**Reviewer Sign-off:** AYEHEAR_SECURITY (pending architecture review of ADR-0006/ADR-0009)
