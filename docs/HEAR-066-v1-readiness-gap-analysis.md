---
owner: AYEHEAR_QA
status: active
updated: 2026-04-16
category: release-governance
---

# HEAR-066: V1 Readiness Gap Analysis (Soll-Ist, Go/No-Go)

## Executive Decision

**Current decision: NO-GO for "product complete V1".**

Reason: Multiple V1-critical capabilities are currently implemented as placeholders/stubs or are only partially validated on real hardware. This conflicts with the V1 promise and with the expectation of a complete operational workflow.

Notes:
- Existing release decision in HEAR-052 is "GO for Operations handoff".
- This document evaluates a stricter quality question: "Is V1 functionally complete for reliable day-to-day usage without repeated clarification?"

## Scope and Evidence Sources

- Product scope and success criteria: `docs/PRODUCT_FOUNDATION.md`
- Current release decision baseline: `docs/HEAR-052-release-decision.md`
- QA matrix and phase sign-offs: `docs/governance/HEAR_QA_ACCEPTANCE_MATRIX.md`
- Regression evidence bundle: `docs/HEAR-063-regression-qa-evidence.md`
- Runtime implementation:
  - `src/ayehear/app/window.py`
  - `src/ayehear/services/speaker_manager.py`
  - `src/ayehear/services/audio_capture.py`
  - `src/ayehear/services/transcription.py`
- Project maturity statement: `README.md`

## V1 Capability Matrix (Soll vs Ist)

Legend:
- Green = implemented and acceptance-ready
- Yellow = partial implementation / constrained behavior
- Red = missing or placeholder behavior in V1-critical path

| Capability | V1 Soll | Ist (Code + Evidence) | Status | Impact |
|---|---|---|---|---|
| Speaker enrollment (microphone voice profile capture) | Real enrollment before meeting, confidence-aware | `_start_enrollment()` explicitly states Phase 1 placeholder, no capture, no enrollment call from UI path | Red | Major: weak speaker recognition baseline |
| Speaker embedding extraction quality | Production-grade embedding (pyannote-based) | `_extract_embedding()` is deterministic stub; comment says to replace in production | Red | Major: matching quality cannot meet robust V1 expectation |
| Speaker attribution review path | Confidence scoring + correction | Implemented and tested (high/medium/low; manual correction path exists) | Green | Positive control exists |
| ASR operational diagnostics | Actionable feedback on no model / inference issues | Implemented (`asr_diagnostic`, user-visible actionable messages) | Green | Better operability |
| Offline-first boundary | No external dependencies by default | Enforced by loopback checks and QA evidence | Green | Security/privacy baseline met |
| Protocol generation in runtime | Snapshot generation and display | Implemented with DB-backed snapshots and refresh | Green | Core function available |
| Export format contract | Export as Markdown, DOCX, PDF (product foundation) | Runtime exports only `protocol.txt` and `transcript.txt` | Red | User-facing mismatch to V1 promise |
| Artifact transparency (where data is stored) | User knows exact storage/export location | Export path is shown at meeting stop; DB location still implicit for non-technical user | Yellow | Support burden, user confusion |
| Audio pipeline robustness on target hardware | Stable 60-min use, device interruption resilience | Strong automated checks; target hardware full acceptance still residual | Yellow | Remaining field risk |

## Critical Gaps (Blockers)

### B1 - Enrollment is not a real workflow yet

Evidence:
- `window._start_enrollment()` describes itself as "Phase-1 placeholder" and states real microphone enrollment follows in Phase 2.
- HEAR-063 confirms enrollment block behavior and verifies that fake success was intentionally removed.

Risk:
- Without real enrollment, speaker recognition quality depends on intro text matching and fallback paths, not on robust voice-profile onboarding.

Release effect:
- Blocks claim "complete V1 speaker recognition workflow".

### B2 - Speaker embedding remains stubbed

Evidence:
- `SpeakerManager._extract_embedding()` is documented as deterministic stub and marked for replacement by real model inference.

Risk:
- Voice similarity decisions cannot reflect production audio variance.
- Increased "Unknown Speaker" or unstable attribution under realistic conditions.

Release effect:
- Blocks confidence in speaker identification KPI.

### B3 - Export promise mismatch (MD/DOCX/PDF vs TXT only)

Evidence:
- Product Foundation states exports are Markdown, DOCX, PDF.
- Runtime export currently writes only `*-protocol.txt` and `*-transcript.txt`.

Risk:
- Direct user expectation mismatch.
- Operational handoff may appear complete while user-level acceptance fails.

Release effect:
- Blocks "V1 feature complete" claim unless scope is explicitly reduced.

## Priority Remediation Plan (QA-driven)

1. **P0: Decide V1 scope truthfully in writing (24h)**
   - Either implement missing capabilities (B1-B3), or formally downscope V1 promise in Product Foundation and release docs.
   - Owner: Architect + Product + QA.

2. **P0: Implement real enrollment path (B1)**
   - Microphone capture flow for enrollment samples.
   - UI status transitions: pending -> recording -> enrolled/failed.
   - Acceptance tests for enrollment success/failure and persistence.

3. **P0: Replace deterministic embedding stub (B2)**
   - Integrate real embedding extraction backend (pyannote or approved equivalent).
   - Add calibration tests for thresholds on target hardware dataset.

4. **P1: Align export implementation to V1 contract (B3)**
   - Provide Markdown export minimum.
   - Add DOCX/PDF generation or officially move to post-V1 scope with explicit release note.

5. **P1: Add user-facing storage transparency**
   - Show export folder and DB location in UI settings/help panel.
   - Include "Open export folder" action.

6. **P1: Hardware acceptance closure**
   - Execute full end-to-end run with real microphone + real ASR model on target machine.
   - Track speaker-ID accuracy against V1 KPI.

## Updated Release Recommendation

- **Operational handoff readiness:** can remain GO (as already decided in HEAR-052) for controlled internal deployment.
- **Product completeness readiness (what user asked):** **NO-GO until B1-B3 are resolved or scope is explicitly reduced and approved.**

## Immediate Governance Actions

To prevent recurrence of "reported done but still placeholder" situations:

1. Add mandatory gate: "No placeholders/stubs in V1-critical user workflow".
2. Add mandatory gate: "V1 Capability Matrix fully green before claiming product-complete".
3. Require explicit discrepancy note in release decision whenever Ops-handoff GO differs from Product-complete GO.

---

Reviewer: AYEHEAR_QA  
Date: 2026-04-16
