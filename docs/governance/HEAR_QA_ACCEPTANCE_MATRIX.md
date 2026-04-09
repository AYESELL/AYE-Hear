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

It maps each check to ADR-0003, ADR-0004, ADR-0005, ADR-0007 and to quality gates in docs/governance/QUALITY_GATES.md.

## Traceability

- ADR-0003: Speaker Identification & Diarization Pipeline
- ADR-0004: Audio Capture & Preprocessing (WASAPI)
- ADR-0005: Meeting Protocol Engine & LLM
- ADR-0007: Persistence Contract and Lifecycle
- Governance: docs/governance/QUALITY_GATES.md

## Acceptance Matrix

| ID       | Area                | Scenario                                                 | Expected Result                                                                       | ADR Mapping                  | Quality Gate Mapping                                         | Test Type              | Evidence                                     |
| -------- | ------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------ | ---------------------- | -------------------------------------------- |
| QA-TX-01 | Transcription       | Continuous capture with normal speech                    | Transcript segments are stored with timestamps and meeting relation                   | ADR-0004, ADR-0007           | Functional Validation: Happy Path, Acceptance Criteria       | Integration            | DB query + exported protocol sample          |
| QA-TX-02 | Transcription       | Device interruption during active session                | Graceful error handling, recoverable capture flow, no crash                           | ADR-0004                     | Functional Validation: Error Paths                           | Manual + Integration   | Error logs + UI screenshot                   |
| QA-SP-01 | Speaker Confidence  | Enrolled speaker speaks clearly                          | Correct participant assignment with high confidence (>= 0.85)                         | ADR-0003                     | AI/ML: Confidence Scoring                                    | Integration            | Segment records with confidence values       |
| QA-SP-02 | Speaker Confidence  | Similar voices / ambiguous segment                       | Medium confidence path is explicit and reviewable                                     | ADR-0003                     | AI/ML: Confidence Scoring, Fallback Behavior                 | Integration + Manual   | Review queue screenshot + segment flags      |
| QA-SP-03 | Speaker Confidence  | Unknown speaker not enrolled                             | Segment marked unknown/uncertain, no silent hard assignment                           | ADR-0003                     | Security & Privacy: Speaker Data                             | Manual + Integration   | Transcript segment state                     |
| QA-MC-01 | Manual Correction   | Reviewer reassigns participant in low-confidence segment | Correction is persisted and audit state marks manual correction                       | ADR-0003, ADR-0007           | AI/ML: Fallback Behavior, Functional: Acceptance Criteria    | Integration            | DB record diff before/after correction       |
| QA-MC-02 | Manual Correction   | Corrected segments feed downstream protocol generation   | Protocol generation prefers reviewed state over raw assignment                        | ADR-0005, ADR-0007           | Architecture: Interface Contracts, Functional: Happy Path    | Integration            | Protocol snapshot content + correction trail |
| QA-PR-01 | Protocol Output     | Decision/action statements in meeting                    | Protocol draft includes decisions and action items with confidence threshold handling | ADR-0005                     | AI/ML: Confidence Scoring, Functional: Acceptance Criteria   | Integration            | Protocol snapshot + action item records      |
| QA-PR-02 | Protocol Versioning | Multiple protocol generations in one meeting             | Immutable snapshot version increments; old snapshots unchanged                        | ADR-0007                     | Functional: Acceptance Criteria, Architecture: ADR Alignment | Integration            | Snapshot version history query               |
| QA-PV-01 | Offline Privacy     | Full test run in local mode                              | No external network/API calls and data remains local                                  | ADR-0004, ADR-0005, ADR-0007 | Security & Privacy: No External Calls, Local Storage         | Manual + Runtime check | Network monitor output + local DB evidence   |

## Execution Plan

1. Run focused integration tests for transcription, diarization, correction and protocol persistence.
2. Execute manual scenario checks for device interruption and review workflow UX.
3. Collect evidence artifacts (queries, logs, screenshots, protocol exports).
4. Record pass/fail per matrix item in task notes and release checklist.

## Evidence Checklist

- [ ] Test log bundle attached (unit/integration/manual)
- [ ] Confidence score examples attached
- [ ] Manual correction before/after evidence attached
- [ ] Protocol snapshot/version evidence attached
- [ ] Offline/no-network validation evidence attached

## Sign-off Template

- QA Reviewer: ********\_\_\_\_********
- Date: ********\_\_\_\_********
- Result: [ ] PASS [ ] PASS WITH RISKS [ ] FAIL
- Residual Risks: ********************\_\_********************
