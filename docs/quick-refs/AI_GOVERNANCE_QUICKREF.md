---
owner: AYEHEAR_SECURITY
status: draft
updated: 2026-04-08
---

# AI Governance Quick Reference

## Covered AI/ML Components

1. **Diarization:** Pyannote.audio (speaker segmentation)
2. **Speaker ID:** Speaker embeddings + cosine matching
3. **Transcription:** Faster-Whisper (speech-to-text)
4. **Protocol Engine:** Local LLM via Ollama (decision/task extraction)

---

## Governance Checklist

- ✅ System Record: Documented
- ✅ Risk Classification: Offline-only, low risk
- ✅ Prompt Log: Protocol engine prompts versioned
- ✅ Confidence Scoring: All speaker IDs scored
- ✅ Manual Override: User can correct AI decisions
- ✅ Privacy: No audio external transmission

---

## Privacy Controls

| Control | Status |
|---------|--------|
| Audio transmission | ❌ Disabled (local-only) |
| Speaker profile encryption | ✅ Planned (v1.x) |
| Telemetry | ❌ Disabled (opt-in v2+) |
| Export artifacts | ✅ User keeps all |

---

**Owner:** AYEHEAR_SECURITY
