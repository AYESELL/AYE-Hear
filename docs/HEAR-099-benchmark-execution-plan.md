# HEAR-099 — Model Benchmark Matrix (QA Execution Plan)

**Task:** HEAR-099 — Model benchmark matrix for recognition and protocol quality  
**Execution Date:** 2026-04-19  
**QA Role:** AYEHEAR_QA  
**Dependency:** HEAR-103 (✅ COMPLETED) — Mistral:7b proven stable

---

## Objective

Run comprehensive benchmark across ASR (Whisper) and LLM (Ollama) models:
1. Capture transcription quality (Whisper variants)
2. Assess protocol generation quality (Ollama variants)
3. Measure latency + resource usage (CPU/RAM)
4. Recommend optimal model pair for Phase 1B default

---

## Benchmark Scope

### ASR Models (Whisper)
- **Small** (39M params, ~1.4 GB)
- **Base** (74M params, ~1.4 GB)

### LLM Models (Ollama)
- **mistral:7b** ✅ (PROVEN: HEAR-103 — 21s, full protocol)
- **llama3.1:8b** (Alternative: reasoning/quality)
- **orca2:13b** (Optional: semantic understanding)

### Test Baseline
- Same frozen transcript: `exports/test-baseline-transcript-HEAR-103.txt`
- Metric: Action item accuracy, summary quality, latency

---

## Execution Plan

### Phase 1: ASR Quality Evaluation (Whisper)

**Test Setup:**
- Fixed audio sample: German meeting, 2 min duration, 3 speakers
- Expected transcription: Baseline from HEAR-103

**Command Template:**
```python
from faster_whisper import WhisperModel
model = WhisperModel("small")  # or "base"
segments, info = model.transcribe("meeting-audio.wav")
transcript = "\n".join([s.text for s in segments])
```

**Metrics to Capture:**
- Transcription accuracy (vs. baseline)
- WER (Word Error Rate) — if reference transcript available
- Latency (seconds to transcribe)
- CPU/RAM usage

**Expected Results:**
| Model | Accuracy | Latency | RAM | Winner |
|-------|----------|---------|-----|--------|
| Whisper small | ~95% | 5-10s | ~500MB | TBD |
| Whisper base | ~98% | 15-20s | ~1GB | TBD |

---

### Phase 2: Protocol Generation Quality (Ollama)

**Using Frozen Transcript from HEAR-103:**
```bash
python -m ayehear protocol-replay \
  --baseline exports/test-baseline-transcript-HEAR-103.txt \
  --model mistral:7b      # PROVEN: 21s, full protocol
  --model llama3.1:8b     # NEW: test for quality improvement
  --model orca2:13b       # OPTIONAL: deeper semantics
```

**HEAR-103 Established Baseline:**
- ✅ mistral:7b: 21 sec, complete protocol (action items, decisions, summary)
- ❌ qwen3.5:latest: timeout
- ❌ deepseek-r1:8b: JSON parse error

**Metrics to Capture:**
- Protocol completion (summary? action items? decisions?)
- Action item accuracy (parsed correctly?)
- Latency (seconds)
- CPU/RAM usage
- Error rate

**Expected Results:**
| Model | Status | Latency | Action Items | Completeness | Winner |
|-------|--------|---------|--------------|--------------|--------|
| mistral:7b | ✅ | 21s | ✅ Full | ✅ Yes | BASELINE |
| llama3.1:8b | ? | ? | ? | ? | ? |
| orca2:13b | ? | ? | ? | ? | ? |

---

## Execution Commands

### Step 1: Verify Baseline

```powershell
# Confirm HEAR-103 transcript exists
Get-ChildItem "exports/test-baseline-transcript-HEAR-103.txt" -Verbose

# Confirm mistral:7b protocol
Get-ChildItem "exports/replays/*mistral*" -Verbose
```

**Status:** ✅ READY

---

### Step 2: ASR Benchmark (Whisper)

```python
# Python script: benchmark_whisper.py
import os
from faster_whisper import WhisperModel
import time

models = ["small", "base"]
audio_file = "meeting-audio.wav"  # Fixed test sample

for model_name in models:
    print(f"\n=== Benchmarking Whisper {model_name} ===")
    
    model = WhisperModel(model_name)
    
    start = time.time()
    segments, info = model.transcribe(audio_file, language="de")
    duration_sec = time.time() - start
    
    transcript = "\n".join([s.text for s in segments])
    
    print(f"Duration: {duration_sec:.2f}s")
    print(f"Transcript length: {len(transcript)} chars")
    print(f"First 200 chars: {transcript[:200]}")
    
    # Save output
    with open(f"exports/benchmark/whisper-{model_name}-transcript.txt", "w") as f:
        f.write(transcript)

print("\n✅ Whisper benchmark complete. Outputs in exports/benchmark/")
```

**Expected Outcome:**
- Two transcripts: `whisper-small-transcript.txt`, `whisper-base-transcript.txt`
- Latency measurements
- Quality comparison

---

### Step 3: Protocol Generation Benchmark (Ollama)

**Already have mistral:7b from HEAR-103:**
```bash
# Output: exports/replays/HEAR-103-Benchmark-Test_20260419_094155_mistral-7b-protocol.md
# Duration: 21 sec
# Status: ✅ Complete
```

**Execute llama3.1 and orca2:**
```bash
python -m ayehear protocol-replay \
  --baseline "exports/test-baseline-transcript-HEAR-103.txt" \
  --output-dir "exports/replays" \
  --title "HEAR-099-Ollama-Benchmark" \
  --model llama3.1:8b
  
python -m ayehear protocol-replay \
  --baseline "exports/test-baseline-transcript-HEAR-103.txt" \
  --output-dir "exports/replays" \
  --title "HEAR-099-Ollama-Benchmark" \
  --model orca2:13b
```

**Expected Outcomes:**
- Three protocol files: `mistral-7b`, `llama3.1-8b`, `orca2-13b`
- Latency per model
- Quality assessment per model

---

## Benchmark Results Template

### ASR (Whisper) Results

| Model | Status | Latency (s) | Accuracy | RAM (MB) |
|-------|--------|-------------|----------|----------|
| small | ⏳ | - | - | - |
| base | ⏳ | - | - | - |
| **Winner** | - | - | - | - |

### LLM (Ollama) Results

| Model | Status | Latency (s) | Summary | Action Items | Completeness |
|-------|--------|-------------|---------|--------------|--------------|
| mistral:7b | ✅ | 21 | ✅ | ✅ | 100% |
| llama3.1:8b | ⏳ | - | - | - | - |
| orca2:13b | ⏳ | - | - | - | - |
| **Winner** | - | - | - | - | - |

---

## Quality Gate Checklist

- [ ] ASR benchmark complete (Whisper small + base)
- [ ] LLM benchmark complete (mistral + llama3.1 + orca2)
- [ ] Latency measurements recorded for all models
- [ ] Resource usage (CPU/RAM) documented
- [ ] Action item accuracy assessed
- [ ] Protocol completeness evaluated
- [ ] Model pair recommendation defined
- [ ] Evidence documented in `docs/HEAR-099-qa-evidence.md`
- [ ] All tests passed without critical errors

---

## Phase 1B Recommendation

**Expected Outcome (based on HEAR-103 findings):**

✅ **Recommended Model Pair:**
- **ASR:** Whisper `base` (best accuracy/speed tradeoff)
- **LLM:** Mistral `:7b` (PROVEN stable, 21s latency, full protocol)

**Rationale:**
- Whisper `base` has better accuracy than `small` (though slower)
- Mistral:7b is proven reliable from HEAR-103 (qwen/deepseek failed)
- Combination: ~15-30s end-to-end latency (acceptable)

**Fallback Strategy:**
- If llama3.1:8b outperforms mistral:7b significantly → update recommendation
- If all LLMs timeout → default to mistral:7b (only working option)

---

## Residual Risks

1. **llama3.1:8b / orca2:13b compatibility**
   - Risk: Models may not be installed or may have compatibility issues
   - Mitigation: Run with error handling, skip if model unavailable
   
2. **Audio sample availability**
   - Risk: No fixed audio sample, may need to generate
   - Mitigation: Use synthesized German meeting audio or capture from HEAR-103 recording

3. **Transcription quality measurement**
   - Risk: No ground truth transcript for WER calculation
   - Mitigation: Manual spot-check of transcription accuracy

---

## Sign-Off

| Role | Status | Notes |
|------|--------|-------|
| **QA Lead** | ⏳ | Awaiting execution results |
| **Architect** | ⏳ | Pending recommendation for default pair |
| **DevOps** | ⏳ | Pending config file update |

---

**Task Status:** IN_PROGRESS (awaiting full benchmark execution)  
**Next Steps:** Execute Whisper and Ollama benchmarks, populate results matrix, document in `docs/HEAR-099-qa-evidence.md`, recommend default model pair for Phase 1B.

