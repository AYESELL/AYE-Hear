---
owner: AYEHEAR_ARCHITECT
status: active
date: 2026-04-22
category: benchmark-preparation
---

# HEAR-137 Benchmark Preparation Note

## Purpose

Prepare HEAR-137 so the 4-candidate ASR benchmark can be executed immediately once HEAR-136 provides the required representative dataset.

## Current Readiness State

Ready now:
- Benchmark harness exists in [tools/scripts/benchmark_whisper_models.py](tools/scripts/benchmark_whisper_models.py).
- Dataset contract exists in [benchmarks/asr-evaluation-dataset/manifest.json](benchmarks/asr-evaluation-dataset/manifest.json).
- Contract coverage exists in [tests/test_hear_136_asr_dataset.py](tests/test_hear_136_asr_dataset.py).
- Seed sample `hear-113-seed` is enough to prove the harness wiring and output shape.

Not ready for authoritative GO/NO-GO:
- The current manifest contains only one synthetic bootstrap sample.
- HEAR-136 acceptance requires a representative anonymized real-meeting corpus and validated ground-truth transcripts.
- Therefore the current seed-only dataset is suitable for a dry run, but not for the model-default decision.

## Decision Rule

HEAR-136 is:
- **not required** for a local dry run of the benchmark helper,
- **still required** for the authoritative HEAR-137 go/no-go decision that would justify switching the packaged default model.

## Recommended HEAR-137 Execution Split

### 1. Dry Run Now (seed-only, non-authoritative)

Purpose:
- verify model IDs,
- verify transcript file naming,
- verify JSON output structure,
- smoke-test local model resolution and offline execution.

Example command:

```powershell
.\tools\scripts\Invoke-HEAR-137-ASRBenchmarkDryRun.ps1
```

Underlying helper:
- [tools/scripts/Invoke-HEAR-137-ASRBenchmarkDryRun.ps1](tools/scripts/Invoke-HEAR-137-ASRBenchmarkDryRun.ps1)
- [tools/scripts/benchmark_whisper_models.py](tools/scripts/benchmark_whisper_models.py)

Expected use:
- engineering smoke test only,
- no release-default decision,
- no override of current `small` default.

### 2. Final Run After HEAR-136 (authoritative)

Prerequisites:
- manifest expanded to 10-15 anonymized real meeting recordings,
- validated ground-truth references present,
- corpus includes realistic acoustic and domain variation.

Decision scope:
- compare `small`, `large-v3-turbo`, `TheChola/whisper-large-v3-turbo-german-faster-whisper`, and `distil-whisper/distil-large-v3`,
- measure WER, CER, runtime, RAM, and hallucination rate,
- apply the documented go/no-go gates from [docs/governance/HEAR_ASR_QUALITY_STRATEGY_REVIEW_AND_APPROVAL.md](docs/governance/HEAR_ASR_QUALITY_STRATEGY_REVIEW_AND_APPROVAL.md).

## Preferred Outcome if Gate Passes

If the final HEAR-137 run yields GO for `TheChola/whisper-large-v3-turbo-german-faster-whisper`, then:
- it becomes the preferred target default for the next installer version,
- HEAR-138 should bundle it as the packaged default model,
- `small` remains the validated offline fallback until the packaged runtime revalidation is complete.