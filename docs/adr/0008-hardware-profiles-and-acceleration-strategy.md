---
status: accepted
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0008: Hardware Profiles and Acceleration Strategy

## Context

AYE Hear must run on Windows laptops with significantly different hardware capabilities. Audio capture, diarization, transcription and local LLM inference all compete for CPU, RAM and optionally GPU resources.

The product needs a formal baseline for:

- CPU-only execution
- optional GPU acceleration
- predictable fallback behavior

## Decision

AYE Hear defines two supported runtime tiers for V1:

1. **CPU-only baseline** as the mandatory compatibility target
2. **GPU-accelerated tier** as an optional optimization path

### CPU-only Baseline

- Must remain functional on Windows systems without a supported GPU
- Prioritizes correctness, reviewability and offline reliability over raw speed
- Uses smaller and more conservative local models where necessary
- Remains the default fallback whenever acceleration is unavailable or unstable

### GPU-accelerated Tier

- Intended for supported local NVIDIA CUDA environments
- May accelerate diarization, transcription and local LLM inference
- Must never change product semantics, confidence handling or review requirements

## Runtime Policy

- Device capability is detected at startup
- The application selects the highest safe profile supported by the machine
- Any acceleration failure must degrade gracefully to CPU-only mode
- Manual correction and confidence scoring remain mandatory in all profiles

## Consequences

**Positive:**

- V1 remains deployable on ordinary Windows hardware
- Higher-end machines gain meaningful performance improvements
- Operations and QA can test against a stable compatibility baseline

**Negative:**

- Performance expectations differ by hardware tier
- Additional validation is required for GPU-specific runtime paths

**Mitigations:**

- Publish minimum and recommended hardware guidance
- Keep CPU-only as the authoritative fallback path
- Treat profile selection as configuration plus runtime detection, not as product forks

## Related ADRs

- ADR-0001: AYE Hear Product Architecture
- ADR-0003: Speaker Identification & Diarization Pipeline
- ADR-0004: Audio Capture & Preprocessing (WASAPI)
- ADR-0005: Meeting Protocol Engine & LLM

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08
