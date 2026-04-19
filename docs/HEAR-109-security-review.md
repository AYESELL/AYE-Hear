---
owner: AYEHEAR_SECURITY
task: HEAR-109
status: APPROVED
date: 2026-04-19
category: security-review
---

# HEAR-109: Traceability and Review Privacy Check

## Scope

Phase-5 security validation for the short-term quality wave introduced by:
- HEAR-106 Confidence Review Workflow
- HEAR-107 Evidence-Linked Protocol Traceability
- HEAR-108 integrated QA validation

Review focus:
- local-only persistence of review and traceability state,
- absence of new outbound paths,
- approved handling of transcript-backed trace context in review and persistence flows.

---

## Executive Decision

APPROVED

The reviewed scope preserves the offline-first boundary and now enforces an
explicit runtime-only persistence contract for transcript-backed review and
traceability state. No new outbound network path was introduced in the quality
wave. No export path now accepts internal trace/review persistence artifacts.

---

## Security Checklist

| Check | Result | Evidence |
|---|---|---|
| No new outbound path in review / traceability scope | PASS | ConfidenceReviewQueue and TraceabilityStore use only local JSON persistence; no network client/import added in reviewed modules |
| Transcript-backed trace context stored locally only | PASS | Review queue state constrained to runtime/reviews; trace context constrained to runtime/traces |
| Internal trace context excluded from approved external artifact boundary | PASS | Export artifacts remain in exports/; review/trace state now rejects exports/ and other non-runtime paths |
| Existing offline-first controls remain intact | PASS | Protocol engine still rejects non-loopback Ollama endpoints; database bootstrap still rejects non-loopback PostgreSQL bindings |

---

## Evidence Reviewed

Code and tests reviewed:
- src/ayehear/services/confidence_review.py
- src/ayehear/services/protocol_traceability.py
- src/ayehear/utils/paths.py
- src/ayehear/services/protocol_engine.py
- src/ayehear/storage/database.py
- tests/test_hear_106_confidence_review.py
- tests/test_hear_107_protocol_traceability.py
- tests/test_hear_108_quality_wave_validation.py
- tests/test_qa_runtime_evidence.py
- docs/HEAR-108-qa-evidence.md

Validation intent:
- review-state persistence remains local and within install-root runtime state,
- trace-link persistence remains local and within install-root runtime state,
- no reviewed module introduces remote HTTP, telemetry, analytics, or non-loopback transport,
- transcript-backed trace excerpts stay inside internal runtime storage and are not redirected to exports/.

---

## Findings

### F1. Runtime boundary guardrail was implicit, not enforced

Status: RESOLVED IN HEAR-109

Before this task, the review and traceability stores documented local JSON
persistence but accepted arbitrary filesystem paths. That was acceptable in unit
tests but too weak as a security contract because transcript-backed state could
be written outside the approved runtime subtree by future callers.

Implemented control:
- review queue persistence now resolves only inside install-root/runtime/reviews,
- traceability persistence now resolves only inside install-root/runtime/traces,
- absolute paths outside those boundaries raise ValueError,
- regression tests cover both accepted runtime paths and rejected exports/ paths.

Security outcome:
- transcript-context persistence cannot silently drift into user-export or other
  ad hoc locations through these service APIs.

### F2. No new outbound path found in the short-term wave

Status: CONFIRMED

The reviewed HEAR-106 and HEAR-107 services contain no HTTP, socket, telemetry,
or analytics calls. Existing network-capable code remains bounded to prior
controls:
- ProtocolEngine validates Ollama endpoints as loopback-only.
- DatabaseBootstrap validates PostgreSQL listen_addresses as loopback-only.

Security outcome:
- no new transcript or trace-context transmission path was introduced by this wave.

### F3. Transcript-backed trace context remains inside approved internal boundary

Status: CONFIRMED

Traceability content contains transcript excerpts, time ranges, and speaker
attribution state. This is sensitive internal review data and must not be mixed
with final user-facing export artifacts by default.

Confirmed behavior after HEAR-109 hardening:
- review queue state is runtime-only,
- trace-link state is runtime-only,
- final protocol/transcript exports remain under exports/ as separate user
  artifacts,
- no reviewed code path auto-exports trace-link JSON or review-state JSON.

Security outcome:
- approved artifact boundaries are preserved.

---

## Residual Risk

No blocker identified for the reviewed scope.

Residual note:
- The traceability and confidence-review stores are still service-level building
  blocks and not yet fully integrated into a production UI persistence flow.
  This is not a security blocker, but future integration must continue to use
  the enforced runtime paths introduced here.

---

## Validation Commands

Recommended verification command for this review:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_hear_106_confidence_review.py tests/test_hear_107_protocol_traceability.py tests/test_hear_108_quality_wave_validation.py tests/test_qa_runtime_evidence.py -q
```

---

## Sign-off

Decision: APPROVED

AYEHEAR_SECURITY confirms that the short-term quality wave preserves local-only
storage and does not add a new outbound path for review or traceability data.

Reviewer: AYEHEAR_SECURITY  
Date: 2026-04-19