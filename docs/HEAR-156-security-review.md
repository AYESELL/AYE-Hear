---
owner: AYEHEAR_SECURITY
task: HEAR-156
status: APPROVED
date: 2026-05-02
category: security-review
prior-review: HEAR-141-security-recheck.md
---

# HEAR-156: Privacy Defaults and Runtime Retention Hardening Recheck

## Scope

Phase-5 security recheck for privacy-safe defaults and retention coverage of
sensitive runtime artifacts.

Reviewed files:
- config/default.yaml
- src/ayehear/models/runtime.py
- src/ayehear/app/window.py
- src/ayehear/services/audio_capture.py
- src/ayehear/services/confidence_review.py
- src/ayehear/services/protocol_traceability.py
- tests/test_config.py
- tests/test_hear_106_confidence_review.py
- tests/test_hear_107_protocol_traceability.py

Prior security baselines:
- HEAR-142 security review
- HEAR-141 security recheck
- HEAR-127 security recheck

---

## Executive Decision

APPROVED

Repository defaults are again production-safe: raw WAV persistence is disabled
by default, review and trace artifacts now have explicit retention defaults,
and runtime cleanup is defined for all three sensitive artifact classes. No new
outbound path or export-boundary regression was introduced.

---

## Acceptance Criteria Assessment

| AC | Requirement | Result |
|----|-------------|--------|
| AC-1 | Production default config is privacy-safe and explicitly documented | PASS |
| AC-2 | Retention and cleanup behavior is defined for WAV, review, and trace artifacts | PASS |
| AC-3 | No outbound path or export-boundary regression introduced | PASS |
| AC-4 | Review contains explicit approval / conditional / no-go decision | PASS - APPROVED |

---

## Security Checklist

| Check | Result | Evidence |
|-------|--------|----------|
| WAV persistence remains opt-in by default | PASS | config/default.yaml now sets privacy.wav_persistence_enabled: false |
| Runtime config exposes explicit review and trace retention controls | PASS | PrivacySettings includes review_retention_days and trace_retention_days |
| Review JSON cleanup is implemented and bounded | PASS | cleanup_expired_review_files() removes only runtime/reviews/*.json older than a clamped 1-30 day TTL |
| Trace JSON cleanup is implemented and bounded | PASS | cleanup_expired_trace_files() removes only runtime/traces/*.json older than a clamped 1-30 day TTL |
| Cleanup executes on runtime save path | PASS | MainWindow._save_review_queue() and _save_trace_store() run cleanup before writing new state |
| Cleanup executes on meeting activation before restore | PASS | MainWindow.set_active_meeting() runs cleanup before attempting to load retained review / trace state |
| Export boundary remains unchanged | PASS | Only runtime/reviews and runtime/traces cleanup paths were added; no export path changed |
| No new network or cloud dependency introduced | PASS | Changes use pathlib, time, and existing local runtime path helpers only |

---

## Risk Matrix

| Finding | Severity | Status | Notes |
|---------|----------|--------|-------|
| F1: Benchmark-friendly WAV default had replaced production-safe default in repository config | High | Mitigated | Default restored to false in config/default.yaml |
| F2: Review queue JSON retention was previously undefined in code | Medium | Mitigated | Explicit TTL config and cleanup helper added |
| F3: Trace store JSON retention was previously undefined in code | Medium | Mitigated | Explicit TTL config and cleanup helper added |
| F4: Runtime cleanup is opportunistic, not scheduler-driven | Low | Accepted | Cleanup now runs on meeting activation and on save; sufficient for current offline desktop scope |

---

## Verification

Executed command:

```text
python -m pytest tests/test_config.py tests/test_hear_106_confidence_review.py tests/test_hear_107_protocol_traceability.py
```

Result:
- 73 tests passed
- No failures in config, review persistence, or trace persistence slices

Additional verified behaviors:
- Existing WAV retention enforcement remains in audio_capture.py from HEAR-141.
- New tests cover expired vs recent review JSON and trace JSON cleanup.

---

## Findings

### F1 - Repository default had drifted from production-safe privacy posture

The checked-in default config enabled WAV persistence for benchmark collection.
That was acceptable as a temporary test override but not as the repository's
production baseline.

Assessment:
Blocking until reverted. Resolved in this task by restoring the opt-in default.

### F2 - Review and trace retention was enforced by boundary only, not by lifecycle

runtime/reviews and runtime/traces were constrained to local-only directories,
but there was no explicit TTL cleanup path. This left sensitive transcript-backed
artifacts eligible for indefinite retention.

Assessment:
Medium severity privacy gap. Resolved by adding explicit retention config and
cleanup functions wired into runtime lifecycle touchpoints.

---

## Recommendation

APPROVED

HEAR-156 closes the privacy-default drift and adds defined runtime retention
coverage for review and trace artifacts without weakening offline-first or local
boundary guarantees. Future benchmark work should use environment-specific
overrides or test fixtures instead of changing repository defaults.