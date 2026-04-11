---
status: active
owner: AYEHEAR_SECURITY
reviewed_date: 2026-04-09
adr_refs:
  - ADR-0003
  - ADR-0006
  - ADR-0007
  - ADR-0009
---

# AYE Hear Security Operations Runbook

**Version:** 1.0  
**Date:** 2026-04-09  
**Owner:** AYEHEAR_SECURITY

---

## 1. Scope

This runbook covers operational security procedures for AYE Hear V1 Windows
desktop deployments.  It is required reading for AYEHEAR_DEVOPS before creating
release packages and for AYEHEAR_SECURITY before phase sign-off.

---

## 2. Pre-Installation Checklist

### 2.1 Windows Volume Encryption (ADR-0009 — REQUIRED)

AYE Hear relies on OS-managed disk encryption as the primary data-at-rest
control for V1.  Before the installer runs, verify:

- [ ] **BitLocker** is active on the volume that will host the PostgreSQL data
  directory (`C:\AyeHear\data\pg16` — installer-managed default path).
- [ ] BitLocker status visible via `manage-bde -status`.
- [ ] If BitLocker is unavailable (non-Pro Windows), document the alternative
  OS-level volume encryption control and obtain AYEHEAR_SECURITY approval.

> **Rationale (ADR-0009):** Transcript text and speaker embeddings are
> classified `C_SENSITIVE`.  Volume-level encryption is the baseline V1 control
> while field-level pgcrypto encryption is deferred to Phase-1C.

#### 2.1.1 Pre-Flight Evidence Capture Script (QA-DP-01 — REQUIRED before GA)

Run the following script **before every GA release deployment** and attach the
generated evidence file to the release ticket.

```powershell
# From the repo root (runs manage-bde -status and writes a timestamped
# evidence file to deployment-evidence\bitlocker-evidence-<timestamp>.txt)
.\tools\scripts\Invoke-BitLockerPreFlight.ps1

# Non-C: drive example
.\tools\scripts\Invoke-BitLockerPreFlight.ps1 -Drive D
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0    | BitLocker Protection On — QA-DP-01 passed |
| 1    | Protection Off, manage-bde not found, or unexpected error |

**Evidence document format** (written to `deployment-evidence\bitlocker-evidence-YYYYMMDD-HHmmss.txt`):

```
===================================================================
AYE Hear — BitLocker Pre-Flight Evidence (QA-DP-01)
===================================================================
Date/Time  : 2026-04-11 07:55:32
Drive      : C:
Host       : AYEHEAR-PC
User       : ayehear-devops
ADR        : ADR-0009
Task       : HEAR-035
===================================================================

-- manage-bde -status C: --

Volume C: [OS Drive]
    ...
    Protection Status:     Protection On

-------------------------------------------------------------------
[PASS]  Drive C: — BitLocker Protection: On
-------------------------------------------------------------------
```

**If the script exits 1 (non-Pro Windows or BitLocker disabled):**

1. Obtain AYEHEAR_SECURITY written approval for the alternative encryption
   control used on the target machine.
2. Attach the approval note alongside the evidence file in the release ticket.
3. The release **must not proceed** without one of: a passing evidence file or
   a written AYEHEAR_SECURITY waiver.

> **QA gate:** QA-DP-01 (HEAR_QA_ACCEPTANCE_MATRIX.md) is cleared when a
> passing evidence file (`[PASS]`) is attached to the GA release ticket.
> First captured by task HEAR-035.

### 2.2 PostgreSQL Network Isolation (ADR-0006 / Finding H2)

- [ ] PostgreSQL `listen_addresses` must be `localhost` or `127.0.0.1` only.
- [ ] Confirmed via startup runtime check: `DatabaseBootstrap._check_loopback_only()`
  raises `RuntimeError` on any non-loopback binding and prevents the application
  from starting.
- [ ] Windows Firewall must block inbound TCP 5433 from non-loopback sources.

### 2.3 Credential Provisioning (ADR-0006)

- [ ] PostgreSQL DSN is injected by the installer at installation time.
- [ ] The DSN is stored in installer-managed configuration, not in source control.
- [ ] No default shared password exists in the installer image.
- [ ] Developer examples in code use `<installer-provided-or-env-loaded-dsn>`
  placeholder only — confirmed in `storage/database.py`.

---

## 3. Runtime Security Controls

### 3.1 Offline-First Enforcement (ADR-0006)

All processing remains local.  The following controls are active at runtime:

| Component | Control | Status |
|-----------|---------|--------|
| PostgreSQL | `_check_loopback_only()` validates `listen_addresses` on every startup | ✅ Implemented |
| Ollama LLM | `ProtocolEngine._validate_loopback_url()` rejects any non-loopback URL at construction time | ✅ Implemented |
| Whisper | `faster-whisper` runs local model files; no network calls | ✅ Confirmed |
| Audio capture | `sounddevice` WASAPI default device; no data transmitted | ✅ Confirmed |
| Telemetry | None — application has no telemetry or crash reporting by default | ✅ Confirmed |

### 3.2 Audio Buffer Handling (Finding H1)

The audio capture pipeline processes audio in 512-sample streaming callbacks
(~32 ms at 16 kHz).  There is no persisted ring buffer; audio samples are
passed immediately to the transcription callback and are garbage-collected
after processing.

**On `AudioCaptureService.stop()`:** the sounddevice stream is stopped and
closed via `_close_stream()`, releasing all device handles and callback
references.

**Phase-2 enhancement (not blocking):** Consider `mmap`-backed buffer with
`VirtualLock()` to prevent audio from being paged to swap.

### 3.3 Sensitive Data in Logs (Finding L2)

`DEBUG`-level log calls must never include `C_SENSITIVE` data (transcript
text, speaker names, participant details, embeddings).

Guideline:

```python
# ✅ Safe — operational metadata only
logger.debug("Segment created: id=%s silence=%s", seg.id, seg.is_silence)

# ❌ Never — contains meeting content
logger.debug("Segment text: %s", seg.text)
```

Code reviewers must reject any PR that adds `C_SENSITIVE` data to log calls.

---

## 4. Known Phase-1C Blockers (Not Blocking V1 Release)

These items are documented in the Security Baseline
(`HEAR_SECURITY_REVIEW_BASELINE_PHASE1B.md`) as Phase-1C gates.  They do
not block V1 release given the ADR-0009 volume-encryption control is in place.

| ID | Finding | Plan | Target |
|----|---------|------|--------|
| B1 | C2: No field-level encryption | Implement pgcrypto or app-layer encryption per ADR-0009 | Phase-1C |
| B2 | C3: No audit trail for speaker profiles | Design + implement `speaker_profile_audit_log` table | HEAR-012 acceptance criteria |
| M1 | No credential rotation mechanism | Add "Change DB Password" workflow to settings | Phase-1C+ |
| M3 | Manual correction lacks validation | Add participant-matching check (HEAR-016) | Phase-1C |

---

## 5. Incident Response (Device Lost or Stolen)

1. **Immediate:** If BitLocker is active, data-at-rest is protected.  No remote
   wipe is necessary for V1 (all data is local).
2. **PostgreSQL credentials:** Notify the local administrator to rotate the DSN
   password on any shared infrastructure if the same credential was reused.
3. **Speaker profiles:** Speaker embeddings are biometric data (GDPR).
   Document the loss in the organisation's breach log and assess whether GDPR
   Art. 33 breach notification is required.
4. **Transcripts:** Meeting content was stored locally; assess meeting
   sensitivity and notify participants if required.

---

## 6. Data Retention

| Data Type | Classification | Default Retention | Deletion Mechanism |
|-----------|---------------|-------------------|--------------------|
| Speaker embeddings | C_SENSITIVE (biometric) | Session + 30 days (configurable) | "Delete Speaker Profiles" UI action |
| Transcript segments | C_SENSITIVE | Meeting lifetime + 90 days | Meeting archive/delete workflow |
| Protocol snapshots | C_SENSITIVE | Indefinite (user-managed) | Manual export + delete |
| Meeting metadata | C_INTERNAL | Indefinite | Meeting delete workflow |

> **Note:** Full data retention policy (GDPR Art. 17 compliance) is documented
> in `HEAR_DATA_RETENTION.md` (Phase-1C deliverable).

---

## 7. GDPR Compliance Summary

| Article | Requirement | V1 Status |
|---------|-------------|-----------|
| Art. 5 (Integrity) | Encryption-at-rest | ✅ BitLocker baseline per ADR-0009 |
| Art. 5 (Accountability) | Audit trail for PII changes | ⚠️ Phase-1C (speaker profile audit log) |
| Art. 17 (Erasure) | User data deletion| ⚠️ Basic UI delete; full policy in Phase-1C |
| Art. 32 (Security) | Technical measures | ✅ BitLocker + loopback validation + no telemetry |

---

## 8. References

- [ADR-0006: PostgreSQL Local Deployment](../adr/0006-postgresql-local-deployment-model.md)
- [ADR-0009: Data Protection & Encryption](../adr/0009-data-protection-and-encryption-at-rest-model.md)
- [Security Review Baseline](./HEAR_SECURITY_REVIEW_BASELINE_PHASE1B.md)
- [Quality Gates](./QUALITY_GATES.md)

---

**Maintained by:** AYEHEAR_SECURITY  
**Next review:** Phase-1C planning
