---
status: draft
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0001: AYE Hear Product Architecture

## Context

AYE Hear is a new product in the AYE product line designed to provide local meeting transcription, speaker identification, and protocol generation without cloud dependencies.

The product must:
- Run as a standalone Windows desktop application
- Support live speaker identification with pre-meeting voice enrollment
- Generate meeting protocols in real-time
- Support both internal meetings and external (customer/vendor) contexts
- Maintain complete privacy (no data leaves the user's machine)
- Adapt to both CPU-only and GPU-enabled laptops

## Decision

AYE Hear will be architected as an **offline-first Windows desktop application** with the following principles:

1. **Windows-First Deployment**
   - Target Windows 10/11 as primary runtime
   - Use WASAPI for standard microphone integration
   - Ship as installable .exe via NSIS or similar

2. **Local-Only Processing**
   - All audio ingestion, processing, and storage happens locally
   - No external API calls for transcription, diarization, or LLM inference
   - All models run via Ollama or similar local runtime

3. **Speaker Identification Before Recording**
   - Mandatory speaker enrollment (voice sample per participant) before meeting start
   - Voice embeddings stored locally and matched during live recording
   - Confidence scoring and fallback to "Unknown" when similarity is too low

4. **Real-Time Protocol Generation**
   - Live transcription with speaker labels
   - Event-triggered protocol updates (decision detected, task assigned, etc.)
   - On-demand interim views during the meeting

5. **Multi-Tier Computation**
   - CPU-optimized path: Whisper small/medium, adaptive VAD tuning
   - GPU-accelerated path: Whisper large-v3, faster diarization
   - Auto-detection and preset selection at startup

## Consequences

**Positive:**
- Complete data privacy (regulatory advantage)
- Offline-first model aligns with AYE KNOW principles
- No dependency on third-party transcription APIs
- Predictable cost structure (no per-minute billing)

**Negative:**
- Higher initial computational load on desktop
- Diarization accuracy limited by single microphone
- USB/network audio devices require driver support
- Customer must allocate local storage for historical meetings

**Mitigations:**
- Confidence scoring and manual correction UI
- Performance profiling on target hardware before V1 release
- Clear documentation on mic placement and audio quality

## Alternatives Considered

1. **Browser-based WebRTC app with local processing**
   - Rejected: Lower audio capture quality, Electron overhead

2. **Hybrid cloud + local (Whisper local, protocol generation in cloud)**
   - Rejected: Contradicts offline-first requirement

3. **Integration with Meeting Platforms (Teams, Zoom plugins)**
   - Rejected (post-V1): Requires deeper native integrations; V1 targets standalone UX

---

**Status:** Draft  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08
