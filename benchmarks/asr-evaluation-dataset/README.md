# HEAR-136 ASR Evaluation Dataset

This directory provides the repo-local contract for ASR quality benchmarking.

Purpose:
- keep audio/reference pairs in a predictable structure for the benchmark helper,
- separate benchmark input assets from generated evidence,
- provide one seeded sample so the dataset path is executable in CI/local validation,
- document how QA should add the real anonymized meeting corpus required by HEAR-136.

Structure:

```text
benchmarks/asr-evaluation-dataset/
  manifest.json
  references/
    hear-113-seed.txt
```

Manifest contract:
- `id`: stable sample identifier, used as output folder name
- `audio`: relative or absolute path to the WAV file
- `reference`: relative or absolute path to the ground-truth transcript
- `tags`: optional classifier labels like `synthetic`, `group`, `real-meeting`, `domain-tech`
- `notes`: optional short provenance/anonymization note

Seed sample:
- `hear-113-seed` points to the existing deterministic HEAR-113 WAV artifact.
- It is intentionally tagged as `synthetic` and is only a bootstrap sample.
- It does not satisfy the full HEAR-136 acceptance target of 10-15 anonymized real meeting recordings.

How to add real QA samples:
1. Store the anonymized WAV under a QA-controlled directory outside public evidence outputs.
2. Create or manually validate the matching ground-truth transcript.
3. Add one entry to `manifest.json` with a stable `id`, relative `audio`, and `reference` path.
4. Keep PII out of filenames, notes, and transcript content committed to the repo.

Benchmark usage:

```powershell
.\.venv\Scripts\python.exe tools\scripts\benchmark_whisper_models.py `
  --dataset benchmarks\asr-evaluation-dataset\manifest.json `
  --output-dir deployment-evidence\hear-136\local-run `
  --model small `
  --model base `
  --compute-type int8 `
  --beam-size 3 `
  --language de
```

The helper still supports the legacy single-pair mode via `--audio` and `--reference`.

Dataset acceptance validation:

```powershell
.\.venv\Scripts\python.exe tools\scripts\validate_hear_136_dataset.py `
  --manifest benchmarks\asr-evaluation-dataset\manifest.json `
  --allow-seed-only
```

Authoritative HEAR-136 readiness gate (for HEAR-137 go/no-go input):

```powershell
.\.venv\Scripts\python.exe tools\scripts\validate_hear_136_dataset.py `
  --manifest <qa-private-manifest.json> `
  --min-samples 10 `
  --min-real-samples 10 `
  --min-total-duration-seconds 1800
```