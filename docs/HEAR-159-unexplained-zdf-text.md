# HEAR-159: Unexplained "Untertitelung des ZDF 2020" Text in Protocol

**Status:** INVESTIGATING (defect für v0.6.8)  
**Date Identified:** 2026-05-03  
**Severity:** MEDIUM  
**Component:** ASR Transcription, Protocol Engine  

---

## Problem Statement

During v0.6.7 test run (2026-05-03), user observed:
- **Live Transcript:** Working, speech recognized
- **Protocol Draft:** At the end, contains text "Untertitelung des ZDF 2020"
- **Confusion:** User does not know where this text comes from

### Initial Observations

1. **Text NOT found in source code:**
   - Search in `src/` for "Untertitelung", "ZDF", "2020" returns zero results
   - Text is not a hardcoded placeholder or default value

2. **Possible Origins:**
   - **Theory A:** Background audio from radio/TV captured by microphone
   - **Theory B:** AI/LLM-generated hallucination or prompt injection
   - **Theory C:** Sample/example text from training data leakage

3. **Evidence suggests Theory A (Background Audio):**
   - "Untertitelung des ZDF 2020" is a plausible German TV/media reference
   - Might indicate ASR picking up unintended audio input

---

## Immediate Debug Steps

**For next test session:**

1. **Isolate audio capture:** Test with headset microphone only (no ambient audio)
2. **Check raw transcripts:** Review actual transcript lines in database
3. **Enable verbose logging:** Check `protocol_engine.py` LLM request/response
4. **Verify Ollama output:** Log the raw JSON response from Ollama API

---

## Potential Root-Causes

### Root-Cause 1: Microphone Sensitivity / Background Audio
- **Risk:** Unintended audio captured during meeting
- **Impact:** Transcription quality degradation, spurious text in protocol
- **Mitigation:** Audio-input validation, conference-mode filtering

### Root-Cause 2: LLM Prompt Injection or Hallucination
- **Risk:** AI model generates plausible but false text
- **Impact:** Protocol contains fabricated decisions/action items
- **Mitigation:** Confidence scoring, traceability (HEAR-117/HEAR-118), manual review queue

### Root-Cause 3: Prompt Template Leakage
- **Risk:** Example text from system prompt not properly sanitized
- **Impact:** System/configuration text appears in output
- **Mitigation:** Prompt hardening, output validation

---

## Fix Strategy (Conditional)

**Phase 1 (Immediate):** Debug tests to identify actual source
- Logging in `protocol_engine.py:_extract_via_ollama()` 
- Log raw Ollama response before JSON parsing
- Enable ASR debug output to trace transcript lines

**Phase 2 (If Background Audio):**
- Audio input filter (silence detection, VAD)
- Microphone gain controls in UI
- Audio health check in System Readiness

**Phase 3 (If AI Hallucination):**
- Strengthen confidence review queue (HEAR-117)
- Implement output validation in protocol extraction
- Add traceability links (HEAR-118) to source transcript

---

## Acceptance Criteria

- [ ] AC1: Determine whether text comes from ASR, AI, or template
- [ ] AC2: Fix or mitigate root-cause
- [ ] AC3: Verify text does not appear in clean test run
- [ ] AC4: No regression in protocol quality tests

---

## Phase 3 Blocking?

**CONDITIONAL:**
- If background audio: **LOW PRIORITY** (user control via microphone)
- If AI hallucination: **MEDIUM PRIORITY** (impacts data integrity)
- If template leakage: **CRITICAL** (security/privacy implication)

**Recommendation:** Investigate first (Phase 1 debug), then decide on Phase 3 gate.

---

## Related Issues

- HEAR-117: Confidence Review Queue (manual override capability)
- HEAR-118: Traceability Store (source linking)
- HEAR-113: ASR quality baseline (74.29% accuracy on test set)
- protocol_engine.py: `_extract_via_ollama()` (LLM integration)
