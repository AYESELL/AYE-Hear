---
owner: AYEHEAR_QA
task_id: HEAR-155
status: in-progress
category: qa-evidence
updated: 2026-05-02
---

# HEAR-155 QA Evidence: Installed E2E Gate Closure and Real-Corpus Benchmark

**Task Status:** IN-PROGRESS (Blocked on HEAR-157)  
**Current Date:** 2026-05-02  
**Assessment:** HOLD / NO-GO until HEAR-157 delivers a new packaged candidate and authoritative real-corpus evidence becomes available.

---

## Executive Summary

HEAR-155 requires three sequential phases to close the HOLD state from HEAR-135:
1. **Installed E2E rerun** on new candidate with HEAR-152 fixes
2. **Real-corpus dataset validation** (authoritative benchmark dataset)
3. **Multi-model ASR benchmark** with go/no-go verdict

**CRITICAL BLOCKER:** Phase 1 and downstream phases cannot proceed until **HEAR-157 (AYEHEAR_DEVOPS)** delivers a new packaged installer candidate containing HEAR-152 ASR confidence refactoring.

---

## Blockage Analysis

### Current State (as of 2026-05-02)

| Artifact | Status | Details |
|----------|--------|---------|
| **Latest packaged candidate** | 0.6.2 (build evidence dated 2026-04-22) | Documented in HEAR-151 build evidence; not yet re-evidenced by QA as an installed E2E candidate for HEAR-155 |
| **Latest QA-evidenced installed candidate** | 0.5.5 (installed E2E dated 2026-04-19) | Last candidate with installed QA evidence; result remained NO-GO |
| **HEAR-152 completion** | ✅ Done 2026-05-02 09:14:24 | ASR/speaker confidence split verified (110/110 tests green) |
| **HEAR-157 (new build)** | ❌ OPEN | Required to package HEAR-152 fixes into installer |
| **Real-corpus dataset** | ❌ Not available | Seed-only manifest.json present; authoritative QA corpus not yet provided |

### Dependency Chain

```
HEAR-155 (QA: gate closure)
  ├─> requires: New candidate build WITH HEAR-152 fixes
  │     └─> HEAR-157 (DEVOPS) ← BLOCKING
  ├─> requires: Real meeting corpus (10+ samples, 10+ real-meeting, 1800+ sec)
  │     └─> External data provision ← TBD
  └─> requires: Benchmark automation to be available
        └─> ✅ Scripts ready (validate + benchmark tools present)
```

---

## Phase 1: Installed E2E Validation — BLOCKED

**Requirement:** Run installed-package E2E on new candidate after HEAR-152 merge.

**Expected Success Criteria (from HEAR-155 brief):**
- Zero `transcript_segments_meeting_id` FK violations
- Zero "Meeting not found" errors on close
- Stable protocol rebuild (no repeated failures)
- Non-empty review/trace stores for contentful sessions

**Status:** 🔴 **BLOCKED** — Awaiting HEAR-157 new candidate delivery

**Previous Evidence (0.5.5, 2026-04-19):**
```
From docs/HEAR-126-qa-evidence.md:
- ❌ Transcript persistence: FK constraint failures
- ❌ Protocol rebuild: Repeated failures observed
- ❌ Meeting close: 'Meeting not found' in logs
→ Result: NO-GO for 0.5.5 candidate
```

---

## Phase 2: Real-Corpus Dataset Validation — BLOCKED

**Requirement:** Validate QA dataset meets minimum thresholds before benchmark.

**Validation Command (ready):**
```powershell
cd G:\Repo\aye-hear
python tools/scripts/validate_hear_136_dataset.py `
  --manifest <qa-manifest-path> `
  --min-samples 10 `
  --min-real-samples 10 `
  --min-total-duration-seconds 1800
```

**Status:** 🔴 **BLOCKED** — No authoritative QA corpus provided yet

**Current Data State:**
```json
manifest.json: 1 sample (synthetic seed only)
  ├─ hear-113-seed (synthetic, TTS-generated)
  └─ NOT SUITABLE for authoritative go/no-go decisions
```

**Action Required:**
1. Obtain real meeting recordings (min 10 distinct sessions)
2. Create `qa-manifest.json` with proper `"real-meeting"` tags
3. Validate manifest against gate constraints
4. Store in `benchmarks/asr-evaluation-dataset/` for traceability

---

## Phase 3: Multi-Model ASR Benchmark — BLOCKED

**Requirement:** Run benchmark with 4 model variants and deliver verdict.

**Benchmark Command (ready):**
```powershell
cd G:\Repo\aye-hear
python tools/scripts/benchmark_whisper_models.py `
  --dataset <qa-manifest-path> `
  --output-dir deployment-evidence/hear-155 `
  --model small `
  --model base `
  --model TheChola/whisper-large-v3-turbo-german-faster-whisper `
  --model distil-whisper/distil-large-v3 `
  --compute-type int8 `
  --beam-size 3 `
  --language de
```

**Status:** 🔴 **BLOCKED** — Depends on Phase 2 (real corpus)

**Verification Checklist:**
- [ ] All 4 models run without exception
- [ ] Resource telemetry captured (RAM, CPU)
- [ ] WER metrics calculated per model
- [ ] Go/no-go recommendation issued based on quality gates
- [ ] Evidence saved to `deployment-evidence/hear-155/benchmark-results.json`

---

## Acceptance Criteria Status

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Installed E2E zero FK violations | 🔴 BLOCKED | Pending new candidate |
| Installed E2E zero meeting-close errors | 🔴 BLOCKED | Pending new candidate |
| Installed protocol rebuild stable | 🔴 BLOCKED | Pending new candidate |
| Dataset gate: min 10 samples | 🔴 BLOCKED | No QA corpus |
| Dataset gate: min 10 real-meeting | 🔴 BLOCKED | No QA corpus |
| Dataset gate: min 1800s WAV | 🔴 BLOCKED | No QA corpus |
| Benchmark run complete | 🔴 BLOCKED | No QA corpus |
| Go/no-go verdict issued | 🔴 BLOCKED | No corpus + no new candidate |

## Current Gate Decision

- **Installed candidate quality:** **NO-GO / BLOCKED**
- **Reason:** The required same-candidate evidence chain is incomplete. HEAR-155 still lacks both a newly packaged candidate with QA-runnable installed-runtime automation and an authoritative real-meeting corpus for the benchmark gate.
- **Authority alignment:** This preserves the post-hotfix HOLD / NO-GO posture from HEAR-135 until a new packaged candidate is built, installed E2E passes, and the benchmark corpus gate is satisfied.

---

## Unblocking Actions (Priority Order)

### Action 1: HEAR-157 Completion (CRITICAL)
- **Owner:** AYEHEAR_DEVOPS
- **Deliverable:** New packaged installer candidate with HEAR-152 fixes
- **Success Signal:** Versioned installer artifact in `dist/` with build evidence, checksum, and documented installed-runtime smoke/start-check commands for QA handover
- **Dependency for:** Phase 1 installed E2E rerun

### Action 2: Real-Corpus Acquisition (CRITICAL)
- **Owner:** AYEHEAR_PRODUCT / Test Data Provider
- **Deliverable:** Anonymized real meeting recordings (min 10 sessions, 30+ minutes total)
- **Format:** WAV files with reference transcripts and `real-meeting` tags
- **Destination:** `benchmarks/asr-evaluation-dataset/` with updated `qa-manifest.json`
- **Dependency for:** Phase 2 validation + Phase 3 benchmark

### Action 3: Automation Checkpoint (OPTIONAL - can proceed in parallel)
- **Owner:** AYEHEAR_QA
- **Goal:** Validate automation scripts work (dry-run with seed corpus)
- **Command:** Run validation script with seed manifest, expect pass
- **Status:** Can begin now (does not block Actions 1-2)

---

## Automation Readiness (Checkpoint)

**Status:** ✅ **COMPLETE** (2026-05-02 11:49 UTC)

Testing whether Phase 2-3 scripts run without syntax errors on seed corpus:

### Phase 2 Dry-Run: Dataset Validation
```powershell
cd G:\Repo\aye-hear
python tools/scripts/validate_hear_136_dataset.py `
  --manifest benchmarks/asr-evaluation-dataset/manifest.json `
  --allow-seed-only
```

**Result:** ✅ PASS
```json
{
  "dataset": "hear-136-asr-evaluation",
  "manifest": "G:\\Repo\\aye-hear\\benchmarks\\asr-evaluation-dataset\\manifest.json",
  "sample_count": 1,
  "real_meeting_sample_count": 0,
  "total_wav_duration_seconds": 87.2,
  "thresholds": {
    "min_samples": 1,
    "min_real_samples": 0,
    "min_total_duration_seconds": 0.0,
    "allow_seed_only": true
  }
}
```

### Phase 3 Dry-Run: Multi-Model Benchmark (Small Model)
```powershell
cd G:\Repo\aye-hear
python tools/scripts/benchmark_whisper_models.py `
  --dataset benchmarks/asr-evaluation-dataset/manifest.json `
  --output-dir deployment-evidence/hear-155-checkpoint-phase3 `
  --model small `
  --compute-type int8 `
  --language de `
  --beam-size 3
```

**Result:** ✅ PASS

| Metric | Value |
|--------|-------|
| Sample | hear-113-seed (87.2s synthetic audio) |
| Model | whisper-small (int8, beam_size=3) |
| WER (Word Error Rate) | 0.087 (8.7% errors) |
| Accuracy | 91.3% |
| Transcription Time | 9.207s (87.2s audio @ ~9.5x speedup) |
| Load Time | 1.001s |
| Total Time | 10.208s |
| Peak RAM | 586.8 MB |
| Avg CPU | 393.4% (multi-core) |
| Peak CPU | 470.4% |

**Evidence Path:** `deployment-evidence/hear-155-checkpoint-phase3/benchmark-results.json`

**Conclusion:** Phase 2-3 automation is syntactically valid and executes successfully on the seed corpus. Phase 1 remains blocked until HEAR-157 delivers a new packaged candidate plus working installed-runtime smoke/start-check support.

---

## Next Steps for HEAR-155

1. **Wait for HEAR-157:** Monitor task status daily; expect delivery by 2026-05-04
2. **Secure real corpus:** Coordinate with product team on data availability
3. **Re-plan Phase sequence:** Once unblocked, execute in order:
   - Phase 1: Installed E2E on new candidate (2-4 hours)
   - Phase 2: Dataset validation (30 min)
   - Phase 3: Benchmark run (2-6 hours depending on model count)
4. **Update this report:** Document execution results and go/no-go verdict

---

## References

- Parent Task: HEAR-135 (Readiness Reconciliation)
- Blocking Task: HEAR-157 (Build new candidate)
- ASR Confidence Fix: HEAR-152 (Completed 2026-05-02)
- Benchmark Preparation: HEAR-137, HEAR-136
- Previous Release Gate: docs/HEAR-128-readiness-reconciliation.md
- Last Installed E2E: docs/HEAR-126-qa-evidence.md (NO-GO 0.5.5)

---

**Report Generated:** 2026-05-02 09:47 UTC  
**Status:** IN-PROGRESS / BLOCKED ON EXTERNAL DEPENDENCIES  
**Next Review:** After HEAR-157 candidate delivery
