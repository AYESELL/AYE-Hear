---
status: draft
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0004: Audio Capture & Preprocessing (WASAPI)

## Context

High-quality audio input is the foundation. AYE Hear must use Windows default microphone without forcing specific devices.

## Decision

Implement audio capture using **WASAPI default device** with adaptive preprocessing:

**Capture Stack:**
- Primary: `sounddevice.rec()` with `device=None` (Windows default)
- Sample rate: 16 kHz (sufficient for speech)
- Channels: Mono (single clean stream)
- Format: 16-bit PCM

**Preprocessing Pipeline:**
- VAD: Silero VAD filters silence < 0.5 sec
- Level Normalization: RMS-based to -20dB target
- Noise Reduction: Optional via `noisereduce` library
- Chunking: 512-sample chunks (~32ms @ 16kHz)

**Buffer Strategy:**
- Ring buffer: 4 seconds of audio for look-ahead (diarization needs context)
- Older segments aged out after processing

**Error Handling:**
- Device disconnection → Graceful pause with UI prompt
- Buffer underrun → Retry capture, add silence marker
- Sample rate mismatch → Auto-resample via librosa

## Consequences

**Positive:**
- WASAPI = standard Windows audio, no conflicts
- 16 kHz reduces compute 3x vs. 44.1 kHz
- VAD improves diarization accuracy

**Negative:**
- Mono capture loses spatial info
- Preprocessing adds 50–100ms latency
- Noise reduction can clip speech if not tuned

**Mitigations:**
- Preprocessing tuning UI (VAD threshold, noise gate)
- Capture reference loudness at meeting start
- Pre-meeting audio test

---

**Status:** Draft  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08
