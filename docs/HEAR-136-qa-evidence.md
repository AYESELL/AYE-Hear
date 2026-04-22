# HEAR-136 QA Evidence - ASR Evaluation Dataset and Ground-Truth Readiness

**Task:** HEAR-136 — ASR quality: Build evaluation dataset and ground-truth transcripts  
**Role:** AYEHEAR_QA  
**Date:** 2026-04-22  
**Status:** IN_PROGRESS (Infrastructure complete; authoritative references deferred to live tests)

## Scope

Prepare the benchmark dataset infrastructure for HEAR-137 by providing:
- a stable dataset manifest contract,
- benchmark-loader compatibility,
- automated contract checks,
- an explicit readiness gate separating seed-only dry run from authoritative go/no-go input.

## Delivered in this task update

1. Dataset contract and bootstrap sample
- `benchmarks/asr-evaluation-dataset/manifest.json` exposes the sample list consumed by `tools/scripts/benchmark_whisper_models.py`.
- Seed sample `hear-113-seed` remains available for deterministic dry runs.

2. Dataset operational guidance
- `benchmarks/asr-evaluation-dataset/README.md` now documents both:
  - seed-only validation mode, and
  - authoritative readiness validation thresholds.

3. Readiness validator (new)
- `tools/scripts/validate_hear_136_dataset.py` validates:
  - manifest structure,
  - id uniqueness,
  - file existence,
  - count of `real-meeting` tagged samples,
  - total WAV duration threshold.
- The validator supports strict mode for final gate checks and `--allow-seed-only` for bootstrap smoke checks.

4. Unit coverage (new)
- `tests/test_hear_136_dataset_validator.py` verifies:
  - seed manifest passes only in seed mode,
  - seed manifest correctly fails strict authoritative thresholds,
  - custom manifest passes once thresholds are met.

## Evidence and commands

Seed-mode validation (expected PASS):

```powershell
.\.venv\Scripts\python.exe tools\scripts\validate_hear_136_dataset.py `
  --manifest benchmarks\asr-evaluation-dataset\manifest.json `
  --allow-seed-only
```

Authoritative readiness gate (required before final HEAR-137 go/no-go):

```powershell
.\.venv\Scripts\python.exe tools\scripts\validate_hear_136_dataset.py `
  --manifest <qa-private-manifest.json> `
  --min-samples 10 `
  --min-real-samples 10 `
  --min-total-duration-seconds 1800
```

## Current readiness assessment

- Infrastructure readiness: **GO**
- Authoritative corpus readiness (10-15 anonymized real meeting recordings + validated ground-truth): **HOLD**

Reason for HOLD:
- The workspace currently contains one synthetic seed WAV only (`hear-113-reference.wav`).
- No representative real-meeting corpus is present in-repo at this time.

## Interim product decision (2026-04-22)

- Accepted for now: proceed with the implemented HEAR-136 technical infrastructure and seed-only harness validation.
- Deferred: authoritative reference corpus creation is moved to controlled live-test execution because current standalone operation does not yet provide an export-ready reference flow.
- Constraint: no packaged-default model switch may be justified from seed-only benchmark results.
- Required for final model decision: live-test reference data must be captured, documented, and used as the authoritative benchmark input before HEAR-137 go/no-go closure.

## Remaining completion criteria for HEAR-136

1. Add 10-15 anonymized real meeting recordings (about 30 minutes total) in a QA-controlled dataset path.
2. Provide validated ground-truth references for each sample.
3. Update manifest to include real samples with `real-meeting` tags.
4. Run strict validator gate and archive output in HEAR-136 evidence bundle.
