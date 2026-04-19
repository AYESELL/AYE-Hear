---
task: HEAR-115
owner: AYEHEAR_ARCHITECT
status: implemented
updated: 2026-04-19
category: execution-brief
---

# HEAR-115 Claude Execution Brief

## Start Gate

Do not implement this task before HEAR-113 has published the benchmark outcome and recommended release profile decision.

## Goal

Implement the smallest safe code/config changes required to apply the evidence-backed Whisper profile/model decision for the next release.

The task is not a general ASR redesign. It is a bounded profile/default tuning task.

## Required Outcome

- runtime configuration reflects the selected Whisper model/profile decision,
- startup/runtime wiring remains coherent from config to `TranscriptionService`,
- offline-first behavior is preserved,
- no unacceptable runtime-load increase is introduced without explicit guardrails,
- tests cover the changed wiring and defaults.

## Primary Files To Inspect

- `config/default.yaml`
- `src/ayehear/models/runtime.py`
- `src/ayehear/app/window.py`
- `src/ayehear/services/transcription.py`
- `tests/test_hear_094_whisper_small.py`
- `tests/test_hear_098_model_wiring.py`

## Likely Additional Files

- any benchmark evidence doc produced by HEAR-113,
- release or QA evidence docs if the default changes.

## Constraints

- Do not introduce a new cloud or remote inference path.
- Do not add continuous background profiling or heavy runtime telemetry.
- Do not widen scope into diarization or protocol-engine redesign.
- Keep CPU-only fallback behavior intact per ADR-0008.
- Prefer configuration-driven selection over hard-coded branching.

## ADR and Design References

- `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md`
- `docs/adr/0001-ayehear-product-architecture.md`
- `docs/adr/0008-hardware-profiles-and-acceleration-strategy.md`
- `docs/governance/QUALITY_GATES.md`

## Acceptance Focus

- selected Whisper model/profile is correctly loaded from runtime config,
- default changes are explicit and test-covered,
- resource-impact handling stays conservative,
- no regression in packaged-model path behavior.

## Minimum Tests To Run

- `tests/test_hear_094_whisper_small.py`
- `tests/test_hear_098_model_wiring.py`
- any directly affected transcription tests

## Expected Evidence Updates

- update implementation notes in HEAR-115,
- if defaults change, update relevant docs/config references,
- reference HEAR-113 benchmark evidence in task notes.

## Implementation Notes

### HEAR-113 Benchmark Decision (2026-04-19)

Hardware: i9-12900K, 32 GB RAM, Windows 11 Pro, CPU-only (no GPU). Profile: `balanced` (int8, beam_size=3).

| Model | Accuracy | Total time | Peak RAM |
|-------|----------|------------|----------|
| small | 74.29%   | 11.7 s     | 585.9 MB |
| base  | 71.43%   | 3.9 s      | 337.0 MB |

Decision: **keep `whisper-small` / `balanced` as the release default** (`small` is the best-accuracy model per benchmark summary; accuracy difference of ~2.9 pp outweighs the latency/RAM advantage of `base` for the quality-first release).

### Changes applied

- `src/ayehear/services/transcription.py`: `TranscriptionService.model_name` default changed from `"base"` to `"small"` — aligns the class standalone default with the config default and the benchmark decision, closing the end-to-end coherence gap.
- `tests/test_hear_094_whisper_small.py`: `test_default_model_name_is_base` renamed to `test_default_model_name_is_small` with updated assertion.
- `tests/test_hear_115_asr_profile_tuning.py`: new focused test file — 6 tests covering default model, default profile, config/service coherence, window.py wiring path, CPU-safe int8 check, and base override path.
- `config/default.yaml` and `src/ayehear/models/runtime.py` required no changes (already correct).

### Test results

32 tests passed (test_hear_094_whisper_small, test_hear_098_model_wiring, test_hear_115_asr_profile_tuning, test_transcription). No regressions.

## Ready-To-Use Claude Prompt

Implement HEAR-115 in the AYE Hear repository.

Scope:
- Apply the benchmark-backed Whisper model/profile decision from HEAR-113.
- Keep the change small, configuration-driven, and offline-first.

Read first:
- `docs/architecture/QUALITY_FIRST_NEXT_RELEASE_SCOPE.md`
- `docs/adr/0001-ayehear-product-architecture.md`
- `docs/adr/0008-hardware-profiles-and-acceleration-strategy.md`
- `config/default.yaml`
- `src/ayehear/models/runtime.py`
- `src/ayehear/app/window.py`
- `src/ayehear/services/transcription.py`
- `tests/test_hear_094_whisper_small.py`
- `tests/test_hear_098_model_wiring.py`

Constraints:
- no cloud calls,
- no broad ASR redesign,
- no extra continuous runtime load beyond the chosen profile wiring,
- preserve CPU-only fallback semantics.

Deliver:
- minimal code/config updates,
- focused tests,
- any necessary doc/config default updates,
- brief summary of what changed and which tests passed.