---
status: accepted
context_date: 2026-04-22
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0015: Async-First Audio Pipeline and Retention Controls

## Context

The packaged 0.6.0 test with a higher-accuracy ASR model shows clearly improved transcript quality, but also higher local compute pressure during meetings.

Observed field behavior indicates two architectural risks:

- Real-time capture, transcription, and protocol drafting currently contend for the same CPU budget under load.
- Speaker-related data can survive reinstall scenarios because PostgreSQL runtime data is preserved outside the installer overwrite path.

AYE Hear remains bound to offline-first execution and privacy-by-design constraints. Any change must preserve:

- reliable audio capture under load,
- no cloud/runtime external processing,
- explicit and controllable lifecycle for personal/speaker data.

## Decision

Adopt a **hybrid async-first pipeline** as the default architecture direction for next iterations:

1. **Capture-first priority model**
   - Audio capture remains the highest-priority runtime path.
   - When resources are constrained, transcription/protocol work is delayed before capture quality is degraded.

2. **Time-shifted downstream processing**
   - Transcription is executed asynchronously from persisted segment queues.
   - Protocol generation is decoupled and can run with lower scheduling priority than capture/transcription.

3. **Optional segment persistence for QA/benchmarking**
   - WAV segment persistence is opt-in only (config flag), not default behavior.
   - Persisted audio is used for controlled benchmark corpus acquisition and QA replay.

4. **Retention and deletion controls are mandatory before rollout**
   - Speaker enrollment data and optional WAV artifacts require explicit retention rules.
   - Reinstall/upgrade/uninstall paths must define data lifecycle behavior (keep/delete prompt or enforced purge mode).

## Consequences

### Positive

- Better resilience on CPU-constrained devices by protecting capture continuity.
- Higher flexibility for heavy ASR models without forcing synchronous protocol latency.
- Reproducible benchmark corpus collection path for HEAR-136/HEAR-137.

### Negative

- Live transcript and protocol updates may become more delayed under high load.
- More operational complexity (queueing, backlog visibility, retention jobs).
- Additional governance burden for privacy and deletion semantics.

### Mitigations

- Surface processing state in UI (capture active, transcription backlog, protocol lag).
- Define queue backpressure and bounded storage thresholds.
- Enforce explicit retention policy and deletion operations validated by Security.

## Guardrails and Non-Goals

- No cloud fallback or external API offloading.
- No silent long-term persistence of biometric/speaker-related data.
- No phase-3 implementation before Security and QA design review for retention controls.

## Required Follow-Up Tasks

- HEAR-141 (AYEHEAR_DEVELOPER): implementation of adaptive pipeline behavior and opt-in WAV persistence.
- HEAR-142 (AYEHEAR_SECURITY): privacy review for WAV-on-disk and speaker data retention lifecycle.

## Alternatives Considered

1. **Keep fully synchronous pipeline**
   - Rejected: unacceptable capture risk under higher ASR compute load.

2. **Record-first, full post-meeting processing only**
   - Deferred: robust for capture, but changes live UX expectations too strongly for immediate adoption.

3. **Lower-accuracy model only**
   - Rejected: conflicts with observed quality gains needed for product value.

## Review Decision Package (Security + QA)

### Core Decision Question

For V0.6.x rollout, which retention and processing policy should be approved to balance capture reliability, user experience, and privacy compliance?

### Option A: Hybrid Async + Default Retention TTL

- Capture-first priority with asynchronous transcription/protocol processing.
- WAV persistence stays opt-in.
- Speaker enrollment and optional WAV artifacts use default auto-delete retention (for example 7-30 days), configurable by operator.
- Reinstall/uninstall offers explicit data cleanup prompt.

Pros:
- Strong balance between live UX and resilience under load.
- Privacy risk reduced through bounded retention.
- Keeps benchmark corpus workflow possible when explicitly enabled.

Cons:
- More operational complexity (TTL jobs, retention config).
- Requires clear UI communication for pending backlog and retention state.

### Option B: Record-First Strict Mode

- Capture path only during meeting; transcription/protocol only after stop.
- WAV persistence mandatory for processing pipeline.
- Short mandatory retention window and forced cleanup at export completion.

Pros:
- Maximum capture stability under load.
- Deterministic processing and simplified runtime scheduling.

Cons:
- Significant live UX downgrade (no near-live transcript updates).
- Higher initial user friction and process change.

### Option C: Keep Current Sync Flow + Performance Tuning Only

- Preserve current near-live pipeline, no architectural decoupling.
- Apply smaller model/profile tuning and selective throttling.

Pros:
- Lowest implementation effort and minimal UX changes.

Cons:
- Does not adequately mitigate capture-risk under high ASR load.
- Leaves core contention problem unresolved.

### Architect Recommendation

Recommend **Option A** for V0.6.x as the best compromise between product value and privacy governance.

### Final Decision (2026-04-22)

**Accepted:** Option A (Hybrid Async + default retention TTL).

Decision scope:

- Capture path has highest runtime priority.
- Transcription and protocol generation are allowed to lag under load.
- WAV persistence remains opt-in only and is never enabled by default.
- Retention and deletion controls are mandatory implementation gates.

Implementation gate clarification:

- This ADR is accepted as architecture direction.
- HEAR-141 execution still requires HEAR-142 privacy controls to be specified and approved before rollout.

Security acceptance criteria:

- Retention policy defined for speaker enrollment and optional WAV artifacts.
- Reinstall/uninstall cleanup behavior explicitly approved.
- No silent indefinite persistence of biometric/speaker-related data.

QA acceptance criteria:

- Capture continuity verified under stress profile.
- Acceptable lag thresholds defined and validated for transcript/protocol updates.
- Backlog and processing-state visibility verified in installed runtime evidence.

## Approval Preconditions for Phase 3

- Security sign-off on retention/deletion model (HEAR-142).
- QA sign-off on acceptable transcript/protocol lag behavior under load.
- Explicit operator-visible controls for data cleanup in runtime/uninstall flow.

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-22