---
owner: AYEHEAR_SECURITY
task: HEAR-119
status: APPROVED
date: 2026-04-19
category: security-review
---

# HEAR-119: Security Review for Quality-First Trust Wave

## Scope

Phase-5 security validation for the quality-first trust wave introduced by:
- HEAR-115 ASR profile tuning
- HEAR-116 Action-Item Quality Engine Plus
- HEAR-117 Confidence Review Workflow
- HEAR-118 Evidence-Linked Protocol Traceability

Review focus:
- no new outbound path in the ASR, review, or traceability flow,
- no leakage of transcript-backed review or traceability state outside approved runtime boundaries,
- continued compliance with offline-first and local-storage-only rules.

---

## Executive Decision

APPROVED

The reviewed scope remains local-only after one additional hardening change in
the ASR loader. Review and traceability persistence stay constrained to
runtime-owned storage, protocol exports do not include internal review/trace
JSON by default, and the quality-first wave does not introduce any new remote
transport path.

---

## Security Checklist

| Check | Result | Evidence |
|---|---|---|
| No new outbound path in ASR / review / traceability scope | PASS | ProtocolEngine still enforces loopback-only Ollama URLs; review and traceability services are local JSON only; TranscriptionService now blocks runtime Whisper downloads and uses local-only model resolution |
| Transcript-backed review state stays in approved runtime boundary | PASS | ConfidenceReviewQueue persistence remains constrained to runtime/reviews and is restored only from that boundary |
| Transcript-backed trace state stays in approved runtime boundary | PASS | TraceabilityStore persistence remains constrained to runtime/traces and is restored only from that boundary |
| External export does not leak internal review / trace JSON | PASS | Protocol export remains separate from runtime review and trace persistence; no reviewed path exports the internal JSON stores by default |
| Offline-first contract preserved after HEAR-115 default-model change | PASS | Whisper model aliases now load with local_files_only=True in dev/CI and packaged runtime fails closed when the bundled model is missing |

---

## Evidence Reviewed

Code and tests reviewed:
- src/ayehear/services/transcription.py
- src/ayehear/services/protocol_engine.py
- src/ayehear/services/confidence_review.py
- src/ayehear/services/protocol_traceability.py
- src/ayehear/app/window.py
- src/ayehear/utils/paths.py
- tests/test_transcription.py
- tests/test_hear_094_whisper_small.py
- tests/test_hear_095_resource_telemetry.py
- tests/test_hear_115_asr_profile_tuning.py
- tests/test_hear_106_confidence_review.py
- tests/test_hear_107_protocol_traceability.py
- tests/test_hear_108_quality_wave_validation.py
- tests/test_hear_117_confidence_review_integration.py
- tests/test_hear_118_protocol_traceability_integration.py
- docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md
- docs/architecture/SHORT_TERM_QUALITY_AND_TRACEABILITY_PACK.md

Validation intent:
- ASR model loading must not trigger a runtime download,
- transcript-backed review and trace state must remain inside runtime-owned storage,
- no reviewed quality-wave feature may introduce a new remote network path,
- final exports must remain clean of internal review/trace persistence artifacts.

---

## Findings

### F1. ASR loader still permitted a runtime model-download fallback

Status: RESOLVED IN HEAR-119

The HEAR-115 tuning work changed the default Whisper model to small, but the
ASR loader still allowed the packaged-runtime branch to fall back to a
HuggingFace download when the bundled model was missing. That behavior would
violate the offline-first pledge on a fresh target machine.

Implemented control:
- added local-only Whisper model source resolution,
- development and CI alias-based loading now passes local_files_only=True,
- packaged runtime now requires the bundled model under sys._MEIPASS/models/whisper/<model>,
- packaged runtime fails closed with an explicit error when the bundle is missing,
- regression tests cover local-files-only alias loading, bundled-runtime loading,
  and fail-closed behavior for missing packaged bundles.

Security outcome:
- HEAR-115 no longer leaves a latent outbound runtime path in the ASR layer.

### F2. Confidence review and traceability persistence remain runtime-bound

Status: CONFIRMED

The reviewed HEAR-117 and HEAR-118 integrations continue to persist internal
state only through runtime/reviews and runtime/traces. MainWindow restores and
saves those stores through relative filenames that resolve into the enforced
runtime boundary.

Security outcome:
- transcript-backed internal review state cannot drift into exports or arbitrary
  filesystem locations through the reviewed APIs.

### F3. Export boundary remains clean of internal quality-wave state

Status: CONFIRMED

The quality-first trust wave adds review and traceability state for internal
inspection, but the reviewed export flow does not serialize or embed those JSON
stores into the final external protocol artifacts by default.

Security outcome:
- reviewability improves without widening the external artifact boundary.

### F4. No additional remote transport path was introduced

Status: CONFIRMED

The reviewed modules do not add HTTP, telemetry, analytics, or remote socket
usage beyond the already controlled local-only paths. Existing network-capable
code remains bounded to explicit loopback enforcement for Ollama and PostgreSQL.

Security outcome:
- the quality-first wave preserves the local-only processing model.

---

## Residual Risk

No blocker identified for the reviewed scope.

Residual note:
- Development and CI runs that use model aliases still depend on an already
  present local Whisper cache or an explicit local model path. This is
  acceptable for offline-first behavior because the loader now fails instead of
  downloading. Build and packaging evidence must continue to verify that the
  required Whisper bundle is staged into packaged artifacts.

---

## Validation Commands

Recommended verification command for this review:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_transcription.py tests/test_hear_094_whisper_small.py tests/test_hear_095_resource_telemetry.py tests/test_hear_115_asr_profile_tuning.py tests/test_hear_106_confidence_review.py tests/test_hear_107_protocol_traceability.py tests/test_hear_108_quality_wave_validation.py tests/test_hear_117_confidence_review_integration.py tests/test_hear_118_protocol_traceability_integration.py -q
```

Observed result:
- 138 passed

---

## Sign-off

Decision: APPROVED

AYEHEAR_SECURITY confirms that the quality-first trust wave preserves local-only
processing and approved runtime artifact boundaries after the ASR runtime
download fallback was removed.

Reviewer: AYEHEAR_SECURITY  
Date: 2026-04-19