---
owner: AYEHEAR_SECURITY
status: ready
category: follow-up-brief
updated: 2026-05-02
---

# Follow-up Brief: Privacy Defaults and Retention Hardening

## Goal
Re-assert production-safe privacy defaults and verify retention controls for WAV, review, and trace artifacts.

## Why
Security posture should be benchmark-friendly but production-safe by default and auditable.

## References
- docs/HEAR-141-security-recheck.md
- docs/HEAR-142-security-review.md
- config/default.yaml
- src/ayehear/services/audio_capture.py
- src/ayehear/services/confidence_review.py
- src/ayehear/services/protocol_traceability.py

## Required Scope
- Security validation of defaults in runtime configuration.
- Review retention-policy coverage for runtime/reviews and runtime/traces.
- Verify no outbound path or export-boundary violations are introduced.

## Acceptance Criteria
- Production default config is privacy-safe and explicitly documented.
- Retention and cleanup behavior is defined for all sensitive runtime artifacts.
- Security report classifies blocking vs non-blocking findings.

## Verification
- static review of config and code paths
- optional runtime smoke validation of cleanup behavior
- updated security review document with decision

## Evidence To Produce
- docs/HEAR-<new>-security-review.md
- short risk matrix with severity and mitigation status
- explicit approval/conditional/no-go decision
