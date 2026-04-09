---
owner: AYEHEAR_QA
status: active
updated: 2026-04-09
category: governance
---

# HEAR QA Acceptance Matrix (HEAR-018)

## Purpose

This matrix defines QA acceptance checks for:

- transcription output quality
- speaker confidence and assignment behavior
- manual correction workflow
- protocol generation outputs
- offline-only runtime validation
- encryption and local data-protection validation

It maps each check to ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0009 and to quality gates in docs/governance/QUALITY_GATES.md.

## Traceability

- ADR-0003: Speaker Identification & Diarization Pipeline
- ADR-0004: Audio Capture & Preprocessing (WASAPI)
- ADR-0005: Meeting Protocol Engine & LLM
- ADR-0006: PostgreSQL Local Deployment Model on Windows
- ADR-0007: Persistence Contract and Lifecycle
- ADR-0009: Data Protection and Encryption-at-Rest Model
- Governance: docs/governance/QUALITY_GATES.md

## Acceptance Matrix

| ID       | Area                | Scenario                                                 | Expected Result                                                                       | ADR Mapping                  | Quality Gate Mapping                                              | Test Type                 | Evidence                                             |
| -------- | ------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------- | ----------------------------------------------------------------- | ------------------------- | ---------------------------------------------------- |
| QA-TX-01 | Transcription       | Continuous capture with normal speech                    | Transcript segments are stored with timestamps and meeting relation                   | ADR-0004, ADR-0007           | Functional Validation: Happy Path, Acceptance Criteria            | Integration               | DB query + exported protocol sample                  |
| QA-TX-02 | Transcription       | Device interruption during active session                | Graceful error handling, recoverable capture flow, no crash                           | ADR-0004                     | Functional Validation: Error Paths                                | Manual + Integration      | Error logs + UI screenshot                           |
| QA-SP-01 | Speaker Confidence  | Enrolled speaker speaks clearly                          | Correct participant assignment with high confidence (>= 0.85)                         | ADR-0003                     | AI/ML: Confidence Scoring                                         | Integration               | Segment records with confidence values               |
| QA-SP-02 | Speaker Confidence  | Similar voices / ambiguous segment                       | Medium confidence path is explicit and reviewable                                     | ADR-0003                     | AI/ML: Confidence Scoring, Fallback Behavior                      | Integration + Manual      | Review queue screenshot + segment flags              |
| QA-SP-03 | Speaker Confidence  | Unknown speaker not enrolled                             | Segment marked unknown/uncertain, no silent hard assignment                           | ADR-0003                     | Security & Privacy: Speaker Data                                  | Manual + Integration      | Transcript segment state                             |
| QA-MC-01 | Manual Correction   | Reviewer reassigns participant in low-confidence segment | Correction is persisted and audit state marks manual correction                       | ADR-0003, ADR-0007           | AI/ML: Fallback Behavior, Functional: Acceptance Criteria         | Integration               | DB record diff before/after correction               |
| QA-MC-02 | Manual Correction   | Corrected segments feed downstream protocol generation   | Protocol generation prefers reviewed state over raw assignment                        | ADR-0005, ADR-0007           | Architecture: Interface Contracts, Functional: Happy Path         | Integration               | Protocol snapshot content + correction trail         |
| QA-PR-01 | Protocol Output     | Decision/action statements in meeting                    | Protocol draft includes decisions and action items with confidence threshold handling | ADR-0005                     | AI/ML: Confidence Scoring, Functional: Acceptance Criteria        | Integration               | Protocol snapshot + action item records              |
| QA-PR-02 | Protocol Versioning | Multiple protocol generations in one meeting             | Immutable snapshot version increments; old snapshots unchanged                        | ADR-0007                     | Functional: Acceptance Criteria, Architecture: ADR Alignment      | Integration               | Snapshot version history query                       |
| QA-PV-01 | Offline Runtime     | Core meeting flow executes while the machine is offline  | Meeting setup, enrollment, recording and protocol generation complete without outbound dependency | ADR-0003, ADR-0005, ADR-0007 | Security & Privacy: No External Calls, Functional: Happy Path     | Manual + Runtime check    | Offline run log + protocol artifact                  |
| QA-PV-02 | Network Boundary    | Local PostgreSQL runtime is validated during test run    | Runtime remains loopback-only and fails closed if listen_addresses exposes non-loopback interfaces | ADR-0006, ADR-0007           | Security & Privacy: Local Storage, Architecture: ADR Alignment    | Manual + Runtime check    | SHOW listen_addresses output + bootstrap evidence    |
| QA-DP-01 | Data Protection     | Host volume storing PostgreSQL data and app state is reviewed | BitLocker or approved equivalent protects the relevant local volume as baseline encryption-at-rest control | ADR-0009, ADR-0006           | Security & Privacy: Local Storage, Credentials                    | Manual + Operations check | manage-bde -status output + deployment note          |
| QA-DP-02 | Secret Handling     | Repo-tracked config and examples are reviewed            | No live DSNs, passwords or static encryption material exist in source-controlled artifacts | ADR-0009, ADR-0007           | Security & Privacy: Credentials, No External Calls                | Review + Manual           | Config review notes + sample file check              |

## Execution Plan

1. Run focused regression and integration tests for participant mapping, diarization, correction and protocol persistence.
2. Execute manual scenario checks for device interruption, review workflow UX and offline runtime behavior.
3. Capture local runtime evidence: network monitor output, PostgreSQL listen_addresses, BitLocker status and protocol exports.
4. Review repo-tracked configuration/examples for plaintext secrets or unapproved secret material.
5. Record pass/fail per matrix item in task notes and release checklist.

## Evidence Checklist

- [ ] Test log bundle attached (unit/integration/manual)
- [ ] Confidence score examples attached
- [ ] Manual correction before/after evidence attached
- [ ] Protocol snapshot/version evidence attached
- [ ] Offline/no-network validation evidence attached
- [ ] Loopback-only PostgreSQL evidence attached
- [ ] BitLocker or equivalent encryption evidence attached
- [ ] Secret-storage/config review evidence attached

## Sign-off Template

- QA Reviewer: ********\_\_\_\_********
- Date: ********\_\_\_\_********
- Result: [ ] PASS [ ] PASS WITH RISKS [ ] FAIL
- Residual Risks: ********************\_\_********************
