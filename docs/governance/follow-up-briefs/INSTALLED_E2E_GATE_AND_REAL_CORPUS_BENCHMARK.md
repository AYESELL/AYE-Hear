---
owner: AYEHEAR_QA
status: ready
category: follow-up-brief
updated: 2026-05-02
---

# Follow-up Brief: Installed E2E Gate Closure and Real-Corpus ASR Benchmark

## Goal
Close current HOLD/NO-GO state by producing same-candidate installed evidence and authoritative ASR benchmark evidence on real meeting corpus.

## Why
Current evidence confirms fixes in source/tests, but installed-candidate proof chain is incomplete and benchmark corpus is seed-only.

## References
- docs/HEAR-135-readiness-reconciliation.md
- docs/HEAR-132-qa-evidence.md
- docs/HEAR-137-benchmark-prep.md
- benchmarks/asr-evaluation-dataset/manifest.json
- tools/scripts/benchmark_whisper_models.py
- tools/scripts/validate_hear_136_dataset.py

## Required Scope
1. Installed-package E2E rerun on new candidate including latest fixes.
2. Real-corpus dataset validation (non-seed authoritative gate).
3. HEAR-137 style benchmark run with gate verdict.

## Acceptance Criteria
- Installed E2E on new candidate shows:
  - zero transcript FK violations
  - zero meeting-close not-found errors
  - stable protocol rebuild
  - non-empty review/trace stores for contentful sessions
- Dataset gate passes minimum real-sample and duration constraints.
- Benchmark report provides go/no-go recommendation with metrics.

## Verification Commands
- python tools/scripts/validate_hear_136_dataset.py --manifest <qa-manifest> --min-samples 10 --min-real-samples 10 --min-total-duration-seconds 1800
- python tools/scripts/benchmark_whisper_models.py --dataset <qa-manifest> --output-dir <evidence-dir> --model small --model base --model TheChola/whisper-large-v3-turbo-german-faster-whisper --model distil-whisper/distil-large-v3 --compute-type int8 --beam-size 3 --language de

## Evidence To Produce
- docs/HEAR-<new>-qa-evidence.md
- deployment-evidence/hear-<new>/... runtime logs and signature extracts
- benchmark JSON and summary table with recommendation
