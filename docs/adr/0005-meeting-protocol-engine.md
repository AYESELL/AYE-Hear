---
status: draft
context_date: 2026-04-08
decision_owner: AYEHEAR_ARCHITECT
---

# ADR-0005: Meeting Protocol Engine & LLM

## Context

Converting live transcript into structured protocol requires real-time context extraction.

## Decision

Implement a **staged local LLM protocol engine**:

**Stage 1: Segment Accumulation**
- Collect 5–10 recent segments (rolling window)
- Format as structured JSON

**Stage 2: LLM Inference**
- Use 7B–13B model (Llama 2, Mistral) via Ollama
- Extract: Decisions, Action Items, Open Questions, Risks, Summary
- Confidence scores (0.0–1.0)
- Only include ≥ 0.65 confidence

**Stage 3: Protocol Aggregation**
- Persistent "current draft" in SQLite
- New extractions add/merge
- Version history tracked

**Stage 4: UI Presentation**
- Confirmed (user-approved)
- Proposed (LLM suggestions)
- Open (unresolved)

## Consequences

**Positive:**
- Local LLM = privacy + no API costs
- Real-time updates
- Confidence prevents fake facts

**Negative:**
- Quality depends on model size
- Requires 4–8 GB VRAM
- Prompt engineering critical

**Mitigations:**
- Pilot with real meetings
- Manual correction always available
- Confidence scores in export

---

**Status:** Draft  
**Owner:** AYEHEAR_ARCHITECT  
**Updated:** 2026-04-08
