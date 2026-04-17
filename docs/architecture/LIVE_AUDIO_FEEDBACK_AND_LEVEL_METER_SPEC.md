---
owner: AYEHEAR_ARCHITECT
status: draft
updated: 2026-04-15
category: architecture-spec
---

# Live Audio Feedback and Level Meter - Architecture Spec

## Goal

Provide immediate and explicit runtime feedback during enrollment and meeting start so users can verify:

- microphone capture is active,
- audio is actually reaching the pipeline,
- speaking volume is in a usable range,
- there is no silent failure while waiting for first transcript output.

## Problem Statement

Current user experience can appear unresponsive when ASR output is delayed. Users need a clear capture-state signal and a near-real-time level indicator independent of transcript timing.

## Scope

In scope:

- setup panel capture state indicator (Idle, Initializing, Active, Degraded, Error)
- live level meter in setup/transcript context with low/ok/high guidance
- explicit text feedback for "no signal", "too low", and "clipping risk"
- integration with existing audio capture callback and thread-safe UI update path
- test coverage for UI state transitions and meter behavior

Out of scope:

- cloud/offline architecture changes
- speaker identification model changes
- protocol engine redesign

## ADR Alignment

- ADR-0003: Speaker identification remains unchanged; manual override remains mandatory for low confidence.
- ADR-0004: Uses existing local WASAPI capture pipeline.
- ADR-0009: No additional external transfer; only local transient UI telemetry.

## UX Contract

## Required States

1. Idle
- Label: "Mic idle"
- Meter hidden or zeroed

2. Initializing
- Label: "Mic initializing..."
- Meter visible with neutral style

3. Active
- Label: "Mic active"
- Meter updates continuously from incoming segments

4. Degraded
- Label examples:
  - "No signal for 3s"
  - "Input too low"
  - "Input too high / clipping risk"
- Meter remains visible

5. Error
- Label: "Mic error: <reason>"
- Meeting controls remain responsive; user can retry

## Meter Semantics

Use normalized RMS from incoming segments and map to user-facing bands:

- low: rms < 0.01
- ok: 0.01 <= rms <= 0.25
- high: rms > 0.25

Guidance text:

- low: "Speak louder or move closer to microphone."
- ok: "Input level looks good."
- high: "Input is very loud; reduce distance or gain."

Update rate target:

- UI refresh cadence 4-10 Hz
- no blocking work in UI thread

## Failure and Timeout Behavior

- If capture starts but no non-silent segment arrives within 3 seconds, show degraded state.
- If capture callback stops unexpectedly, switch to error state and keep controls usable.
- On stop meeting, meter resets to idle and any timer is stopped.

## Privacy and Security Constraints

- No raw audio persistence for meter feature.
- No outbound network calls.
- No new telemetry export.
- Any optional diagnostic logs must remain local and avoid sensitive content.

## Implementation Guidance for AYEHEAR_DEVELOPER

- Add a dedicated UI component in setup panel:
  - capture state label
  - horizontal level bar with color thresholds
  - short guidance text
- Feed meter from AudioCaptureService callback using signal/slot boundary for thread safety.
- Keep existing transcript behavior; meter is independent and immediate.
- Add unit/UI tests for:
  - state transitions (idle->initializing->active->degraded/error->idle)
  - threshold mapping low/ok/high
  - no-signal timeout path

## QA Acceptance Addendum

New QA scenarios to execute and attach evidence:

- QA-AF-01: Start meeting with valid mic -> active state visible within 1s
- QA-AF-02: Silence input for >=3s -> degraded "no signal" feedback
- QA-AF-03: Quiet speech -> low-level guidance
- QA-AF-04: Loud input -> clipping-risk guidance
- QA-AF-05: Capture fault simulation -> error state without UI freeze

Evidence:

- screenshots of each state
- short runtime log excerpt for state transitions
- regression test output

## Architect Phase-2 Gate for this scope

Phase 3 implementation is approved only if:

- this UX contract is referenced in task notes,
- developer task includes tests for state + threshold logic,
- QA task includes explicit manual/runtime evidence for all QA-AF scenarios,
- security confirms no new outbound path and no raw-audio persistence.
