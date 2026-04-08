---
status: draft
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0003: Speaker Identification & Diarization Pipeline

## Context

Live speaker identification is core: "Who said what?" must be known in real-time with confidence flagging.

## Decision

Implement a **two-stage pipeline with mandatory pre-meeting voice enrollment**:

**Stage 1: Voice Enrollment (Pre-Meeting)**
- Each participant speaks 5-10 seconds reference phrase
- System extracts speaker embedding (768-dim vector)
- Embeddings stored locally in SQLite
- Quality check: Cosine similarity ≥ 0.75 acceptance

**Stage 2: Diarization + Identification (During Recording)**
1. VAD: Silero VAD filters silence/noise
2. Segmentation: Pyannote detects speaker change boundaries
3. Embedding: For each segment, generate embedding
4. Matching: Cosine similarity match
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
- Confidence scoring ensures transparency
- Fallback to manual correction available

**Negative:**
- All participants must enroll first
- Single microphone limits accuracy

**Mitigations:**
- UI emphasizes enrollment before meeting
- Manual correction retroactively possible
- Confidence scores in export

---

**Status:** Draft  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08
