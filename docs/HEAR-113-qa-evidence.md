---
owner: AYEHEAR_QA
status: draft
updated: 2026-04-19
category: qa-evidence
---

# HEAR-113 QA Evidence - ASR Benchmark and Release Profile Recommendation

## Scope
Execute the quality-first ASR benchmark required by [docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md](docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md) and produce one evidence-backed recommendation for the next default Whisper profile.

This task compares `small` versus `base` on CPU-only execution for:
- transcript quality,
- wall-clock latency,
- CPU load,
- peak RAM,
- release suitability for the next default profile.

## Inputs Reviewed
- Scope approval: [docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md](docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md)
- Hardware policy: [docs/adr/0008-hardware-profiles-and-acceleration-strategy.md](docs/adr/0008-hardware-profiles-and-acceleration-strategy.md)
- Current runtime default: [config/default.yaml](config/default.yaml)
- Existing benchmark method seed: [docs/HEAR-099-benchmark-execution-plan.md](docs/HEAR-099-benchmark-execution-plan.md)
- Reference transcript: [exports/test-baseline-transcript-HEAR-103.txt](exports/test-baseline-transcript-HEAR-103.txt)

## Method
Because the workspace contained no curated benchmark audio asset, the benchmark used a deterministic offline input path:

1. Generate a WAV file from the HEAR-103 baseline transcript via local Windows TTS (`Microsoft Hedda Desktop`, `de-DE`).
2. Run `faster-whisper` with the repo-staged `small` and `base` models in CPU / `int8` / `beam_size=3` mode.
3. Measure:
   - transcript WER against the baseline transcript,
   - derived accuracy percentage,
   - model load + transcription wall-clock time,
   - process peak RAM,
   - average and peak CPU percent.

### Execution Command

```powershell
.\tools\scripts\Invoke-HEAR-113-ASRBenchmark.ps1
```

### Benchmark Host
- Machine: `SAM_ULTRA`
- OS: Windows 11 Pro `10.0.26200`
- CPU: `12th Gen Intel(R) Core(TM) i9-12900K`
- RAM: `34,212,798,464` bytes (~31.9 GiB)

Hardware artifact:
- [deployment-evidence/hear-113/2026-04-19/hardware-profile.txt](deployment-evidence/hear-113/2026-04-19/hardware-profile.txt)

## Results

### Summary Table

| Model | Accuracy | WER | Total Time | Peak RAM | Avg CPU | Peak CPU | Result |
|------|----------|-----|------------|----------|---------|----------|--------|
| `small` | `74.29%` | `0.2571` | `11.686s` | `585.9 MB` | `391.1%` | `448.8%` | Best transcript quality |
| `base` | `71.43%` | `0.2857` | `3.905s` | `337.0 MB` | `397.2%` | `520.8%` | Fastest and lowest RAM |

### Interpretation
1. `small` produced the more accurate transcript on this benchmark host, outperforming `base` by `2.86` absolute accuracy points.
2. `base` was materially faster and more memory-efficient on this host, but the speed benefit did not compensate for the observed transcript-quality regression.
3. The current default in [config/default.yaml](config/default.yaml) is already `whisper_model: small` with `whisper_profile: balanced`; this benchmark does not justify changing that default.

## Transcript Quality Notes

### `small`
- Better preservation of speaker names and sentence boundaries.
- Still shows normalization artifacts from synthesized speech input, for example `Null Uhr` instead of bracket timestamps.

### `base`
- Additional degradation on names and token boundaries, for example `Karol`, `Ur-Bob`, and `Stark-Holder-Team`.
- Faster result, but weaker textual fidelity for downstream protocol quality.

Artifacts:
- [deployment-evidence/hear-113/2026-04-19/benchmark-results.json](deployment-evidence/hear-113/2026-04-19/benchmark-results.json)
- [deployment-evidence/hear-113/2026-04-19/whisper-small-transcript.txt](deployment-evidence/hear-113/2026-04-19/whisper-small-transcript.txt)
- [deployment-evidence/hear-113/2026-04-19/whisper-base-transcript.txt](deployment-evidence/hear-113/2026-04-19/whisper-base-transcript.txt)
- [deployment-evidence/hear-113/2026-04-19/hear-113-reference.wav](deployment-evidence/hear-113/2026-04-19/hear-113-reference.wav)

## Release Recommendation

### Recommended Next Default Profile
Keep the current default unchanged for the next release:

```yaml
models:
  whisper_profile: balanced
  whisper_model: small
```

### Rationale
- The approved quality-first scope prioritizes trustworthy output over raw speed.
- On the benchmark host, `small` is the only tested profile that improved transcript quality relative to `base`.
- No evidence from this task shows a quality benefit large enough to justify switching the default to `base`.
- ADR-0008 keeps CPU-only correctness as the authoritative baseline; `small` remains the safer default under that policy.

## Go / No-Go Boundary for Heavier ASR Profile Changes

Before the next intensive validation cycle, any change to a heavier default ASR profile is **NO-GO** unless all of the following conditions are met on representative CPU-only hardware:

1. The heavier candidate improves transcript accuracy by at least `+3.0` absolute percentage points versus the current `small` default on the same corpus.
2. The improvement is reproduced on both:
   - the deterministic HEAR-113 reference audio, and
   - at least one real microphone capture representative of the target usage environment.
3. Total processing time stays within `1.5x` the `small` baseline on the same host.
   - Current reference baseline from this run: `11.686s`
   - Derived ceiling for a heavier candidate on comparable input: `17.529s`
4. Peak RAM stays within `+250 MB` of the `small` baseline on the same host.
   - Current reference baseline from this run: `585.9 MB`
   - Derived ceiling for a heavier candidate on comparable input: `835.9 MB`
5. Packaging and runtime remain offline-first:
   - bundled local model only,
   - no HuggingFace/runtime download dependency,
   - no outbound network path introduced.

If any one of these conditions is not met, a heavier default-profile change remains **NO-GO** for the next release wave.

## Acceptance Assessment

1. Compare Whisper `small` versus `base` for quality, latency, CPU, and RAM
- Status: **PASS**
- Evidence: benchmark JSON + generated transcripts in [deployment-evidence/hear-113/2026-04-19](deployment-evidence/hear-113/2026-04-19)

2. Produce one release recommendation for the next default profile
- Status: **PASS**
- Decision: keep `small` + `balanced` as the next default.

3. Define go/no-go boundary for heavier ASR profile change
- Status: **PASS**
- Decision: heavier default change blocked unless the explicit five-part gate above is satisfied.

## Residual Risks

### R1 - Synthetic speech benchmark input is not a substitute for live microphone capture
- Severity: **Medium**
- Impact: The ranking is reliable for deterministic comparison, but acoustic realism is limited.
- Required follow-up: repeat the same measurement pattern on at least one real microphone recording before approving any heavier default profile.

### R2 - Single hardware host does not represent the full CPU-only fleet
- Severity: **Medium**
- Impact: The benchmark host is a high-end CPU-only Windows machine; lower-tier laptops may show different latency and RAM behavior.
- Required follow-up: run the same harness on the minimum/recommended hardware profile set before broadening the ASR default policy.

## QA Recommendation
- **GO** to keep the current `small` default for the next release.
- **NO-GO** for any heavier default ASR profile change before the next intensive validation cycle unless the documented gate is satisfied.