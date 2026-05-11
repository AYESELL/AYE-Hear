---
owner: AYEHEAR_ARCHITECT
status: active
updated: 2026-05-04
category: execution-pack
---

# HEAR Follow-up Implementation Pack (2026-05-02)

## Purpose
This pack defines concrete follow-up execution tasks after critical product-readiness review of ASR, transcription, and protocol generation.

## Created Follow-up Tasks

| Task ID | Role | Priority | Parent | Objective |
|---|---|---|---|---|
| HEAR-152 | AYEHEAR_DEVELOPER | high | HEAR-150 | Split ASR confidence semantics from speaker confidence and harden review routing. |
| HEAR-153 | AYEHEAR_DEVELOPER | high | HEAR-149 | Persist final speaker reconciliation state after post-ASR refinement. |
| HEAR-154 | AYEHEAR_DEVELOPER | medium | HEAR-146 | Add protocol delta rebuild gating and explicit deferred-state UX. |
| HEAR-155 | AYEHEAR_QA | critical | HEAR-135 | Close installed E2E gate on new candidate and deliver real-corpus benchmark verdict. |
| HEAR-156 | AYEHEAR_SECURITY | high | HEAR-143 | Recheck privacy-safe defaults and retention hardening for runtime artifacts. |
| HEAR-157 | AYEHEAR_DEVOPS | high | HEAR-151 | Build new installer candidate and stabilize installed E2E automation support for QA. |

## Task Briefing Documents

- HEAR-152 briefing: docs/governance/follow-up-briefs/ASR_CONFIDENCE_SEMANTIC_SPLIT.md
- HEAR-153 briefing: docs/governance/follow-up-briefs/SPEAKER_RECONCILIATION_PERSISTENCE.md
- HEAR-154 briefing: docs/governance/follow-up-briefs/PROTOCOL_DELTA_REBUILD_AND_DEFER_UX.md
- HEAR-155 briefing: docs/governance/follow-up-briefs/INSTALLED_E2E_GATE_AND_REAL_CORPUS_BENCHMARK.md
- HEAR-156 briefing: docs/governance/follow-up-briefs/PRIVACY_DEFAULTS_AND_RETENTION_HARDENING.md
- HEAR-157 briefing: docs/governance/follow-up-briefs/CANDIDATE_REBUILD_AND_E2E_AUTOMATION_SUPPORT.md

## Review and Verification Workflow

1. Owner starts task in Task-CLI and copies the linked briefing document into implementation notes.
2. Owner implements only in the required scope listed in the briefing.
3. Owner executes the verification commands listed in the briefing and stores outputs in deployment evidence.
4. Owner updates task notes with:
   - change summary,
   - test commands and result counts,
   - evidence paths.
5. QA/Security/Architect perform role-based review according to the task role.
6. Task can only move to DONE after evidence completeness and gate checks are confirmed.

## Mandatory Evidence Rules

- Every task must provide reproducible command evidence.
- Every task must provide file-path-based proof artifacts.
- HEAR-155 must include explicit GO/NO-GO statement for installed candidate quality.
- HEAR-156 must include explicit approval/conditional/no-go security statement.

## Related Governance References

- docs/HEAR-135-readiness-reconciliation.md
- docs/HEAR-132-qa-evidence.md
- docs/HEAR-141-security-recheck.md
- docs/HEAR-142-security-review.md
- docs/governance/QUALITY_GATES.md
- docs/governance/DEFINITIONS_OF_DONE.md

## 2026-05-04 QA Runtime Follow-up (0.6.10)

### Scope
- Validate whether runtime WAV artifacts were generated for quality optimization.
- Validate whether meeting, transcript, and protocol data were written consistently to PostgreSQL.

### Findings
- Runtime configuration in installed package has `privacy.wav_persistence_enabled: true` and `wav_output_dir: runtime/wav`.
- No WAV artifacts were present in `D:/AYE/AyeHear/runtime/wav` after the test run.
- Database writes for latest completed meeting were consistent:
   - meeting persisted and completed,
   - transcript segments persisted with text and confidence values,
   - protocol snapshots persisted with non-empty JSONB content.

### Root Cause (WAV Missing)
- `AudioCaptureService._on_stream_finished()` can set `_active=False` before UI/service calls `stop()`.
- Previous `stop()` implementation returned early when `_active` was already false.
- Result: `_flush_wav()` could be skipped even with buffered non-silence frames.

### Implemented Fix
- Updated `AudioCaptureService.stop()` to always attempt stream cleanup and WAV flush, even when `_active` is already false.
- Added regression test for the stream-finished-before-stop sequence:
   - `test_stop_flushes_wav_after_stream_finished_callback`.

### Evidence Targets
- Code: `src/ayehear/services/audio_capture.py`
- Test: `tests/test_hear_141_async_pipeline.py`
- Runtime log used for diagnosis: `D:/AYE/AyeHear/logs/ayehear.log`
