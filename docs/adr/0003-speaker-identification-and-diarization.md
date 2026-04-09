---
status: accepted
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0003: Speaker Identification & Diarization Pipeline

## Context

Live speaker identification is core: "Who said what?" must be known in real-time with confidence flagging.

## Decision

Implement a **three-stage pipeline with mandatory pre-meeting context and enrollment**:

**Stage 0: Meeting Context + Participant Pre-Registration (Pre-Meeting)**

- User must select a meeting type before recording starts (`internal`, `external`, additional configured modes)
- User can pre-register participants before audio enrollment
- Supported participant name templates for V1:
  - `salutation_last_name_company` (example: `Frau Schneider | AYE`)
  - `full_name_company` (example: `Anna Schneider | AYE`)
- During live introduction, speaker matching must prefer this participant set over free-form name guessing

**Stage 1: Voice Enrollment (Pre-Meeting)**

- Each participant speaks 5-10 seconds reference phrase
- System extracts speaker embedding (768-dim vector)
- Embeddings stored in local PostgreSQL
- Quality check: Cosine similarity ≥ 0.75 acceptance

**Stage 2: Diarization + Identification (During Recording)**

1. VAD: Silero VAD filters silence/noise
2. Segmentation: Pyannote detects speaker change boundaries
3. Embedding: For each segment, generate embedding
4. Matching: Cosine similarity match
   - Name assignment uses participant-constrained matching first (from Stage 0)
   - Free-form matching is only a fallback when no participant candidate is plausible
   - ≥ 0.85 → Speaker name + high confidence
   - 0.65–0.84 → "Uncertain: possibly {name}"
   - < 0.65 → "Unknown Speaker"

**Confidence Scoring:**

```python
best_match = max(cosine_similarity(segment_embedding, enrolled_profiles))
if best_match >= 0.85:
    confidence = "high"
elif best_match >= 0.65:
    confidence = "medium"
else:
    confidence = "low"
```

## Consequences

**Positive:**

- Mandatory enrollment eliminates guessing
- Meeting-type and participant pre-registration reduce name ambiguity at runtime
- Confidence scoring ensures transparency
- Fallback to manual correction available

**Negative:**

- All participants must enroll first
- Single microphone limits accuracy

**Mitigations:**

- UI emphasizes enrollment before meeting
- UI must expose post-assignment correction for participant names and keep correction audit state
- Manual correction retroactively possible
- Confidence scores in export

---

**Status:** Accepted  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08
