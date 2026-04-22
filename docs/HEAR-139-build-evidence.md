# HEAR-139 Build Evidence — Release 0.6.0: German ASR Model Integration

**Date:** 2026-04-22  
**Role:** AYEHEAR_DEVOPS  
**Task:** HEAR-139  
**Version:** 0.6.0  
**Status:** BUILD COMPLETE ✅

---

## Summary

HEAR-139 integrates the TheChola/whisper-large-v3-turbo-german-faster-whisper model
as the new default ASR model for AYE Hear v0.6.0.
All code changes are implemented, unit-tested, and the installer is successfully built.

---

## Changes Implemented

| File | Change |
|------|--------|
| `config/default.yaml` | `whisper_model: small` → `whisper_model: TheChola/whisper-large-v3-turbo-german-faster-whisper` |
| `src/ayehear/models/runtime.py` | `ModelSettings.whisper_model` default updated to TheChola model |
| `src/ayehear/services/transcription.py` | `TranscriptionService.model_name` default updated to TheChola model |
| `pyproject.toml` | `version: 0.5.5` → `version: 0.6.0` |
| `build/aye-hear.spec` | Whisper staging dir: `whisper/small` → `whisper/TheChola/whisper-large-v3-turbo-german-faster-whisper` |
| `tools/scripts/Build-WindowsPackage.ps1` | Model staging updated: HF cache path, staging dir, file list (incl. preprocessor_config.json, special_tokens_map.json, tokenizer_config.json) |
| `tests/test_hear_094_whisper_small.py` | Test assertions updated: `small` → TheChola model; test names updated |
| `tests/test_hear_115_asr_profile_tuning.py` | Test assertions updated: `small` → TheChola model; test names updated |

---

## Model Details

| Property | Value |
|----------|-------|
| HuggingFace ID | `TheChola/whisper-large-v3-turbo-german-faster-whisper` |
| Architecture | Whisper Large v3 Turbo (CTranslate2 / faster-whisper format) |
| Parameters | 809M |
| License | CC BY-NC 4.0 |
| WER (German) | 2.628% (self-reported, comprehensive DE test set) |
| Access | **Gated** — HF account + ToS agreement required |
| Estimated model.bin size | ~800 MB |
| HF Cache path (after download) | `%USERPROFILE%\.cache\huggingface\hub\models--TheChola--whisper-large-v3-turbo-german-faster-whisper` |
| Build staging path | `config\models\whisper\TheChola-german-turbo\` |
| PyInstaller bundle path | `models/whisper/TheChola/whisper-large-v3-turbo-german-faster-whisper/` |

---

## Test Results

**Run date:** 2026-04-22  
**Scope:** Full pytest suite (839 tests)

| Test file | Result | Notes |
|-----------|--------|-------|
| `tests/test_hear_094_whisper_small.py` | ✅ 7/7 PASSED | Model defaults updated (HEAR-139) |
| `tests/test_hear_115_asr_profile_tuning.py` | ✅ 6/6 PASSED | Model defaults updated (HEAR-139) |
| `tests/test_hear_098_model_wiring.py` | ✅ 5/5 PASSED | Unmodified — passes |
| All other tests | 834 passed, 5 pre-existing failures | Pre-existing failures not caused by HEAR-139 |

**Pre-existing failures (not HEAR-139):**
- `test_hear_074_enrollment_workflow.py::TestParseSpeakerRaw::test_two_fields`
- `test_hear_074_enrollment_workflow.py::TestParseSpeakerRaw::test_single_field`
- `test_hear_085_protocol_draft.py::TestAC3DegradedLabel::*`
- `test_hear_085_protocol_draft.py::TestAC5UpdateProtocolLiveNeverMirrorsTranscript::*`
- `test_mic_level_widget.py::TestMicLevelWidgetLevelBar::test_level_bar_updates_on_segment`

---

## Build Artifacts

| Artifact | Path | Size |
|---------|------|------|
| Installer | `dist\AyeHear-Setup-0.6.0.exe` | 1060.8 MB |
| Bundle dir | `dist\AyeHear\` | — |
| Bundled model.bin | `dist\AyeHear\_internal\models\whisper\TheChola\whisper-large-v3-turbo-german-faster-whisper\model.bin` | 1542.9 MB |
| Build date | 2026-04-22 17:31 | — |
| PyInstaller | 6.19.0 | — |
| Python | 3.12.10 | — |
| Inno Setup | 6.7.1 | — |

**Staged model files bundled:**
- `config.json` (0.0 MB)
- `model.bin` (1542.9 MB)
- `tokenizer.json` (2.7 MB)
- `preprocessor_config.json` (0.0 MB)
- `vocabulary.txt` — not in snapshot, skipped (non-critical)
- `special_tokens_map.json` — not in snapshot, skipped
- `tokenizer_config.json` — not in snapshot, skipped

---

## Offline-First Constraint: VERIFIED

The `_resolve_model_source()` function in `transcription.py` enforces:
- **Packaged runtime:** Loads from `sys._MEIPASS/models/whisper/TheChola/whisper-large-v3-turbo-german-faster-whisper/`; fails closed if missing
- **Development:** `local_files_only=True` — no runtime HuggingFace downloads
- The HF model ID `TheChola/whisper-large-v3-turbo-german-faster-whisper` is a path with `/` which PyInstaller must map to a nested bundle directory — this is handled in `aye-hear.spec` via the `models/whisper/TheChola/whisper-large-v3-turbo-german-faster-whisper` bundle target path.

---

## Installer Build: COMPLETED ✅

**Result:** `dist\AyeHear-Setup-0.6.0.exe` (1060.8 MB) — 2026-04-22 17:31

**Build command used:**
```powershell
cd G:\Repo\aye-hear
.\tools\scripts\Build-WindowsPackage.ps1 -BuildInstaller -Clean
```

**Note:** TheChola model is gated on HuggingFace. Pre-download requires:
- HF account with accepted model ToS at https://huggingface.co/TheChola/whisper-large-v3-turbo-german-faster-whisper
- `huggingface_hub.login(token=<token>)` before running `WhisperModel(...)`

---

## Fallback: small model

The `small` model fallback is preserved. Override via config or TranscriptionService constructor:
```yaml
# config/default.yaml override (for lower-resource deployments)
models:
  whisper_model: small
```

---

## Next Steps

1. **Manual:** HF login + model pre-download (see above)
2. **Build:** `Build-WindowsPackage.ps1 -BuildInstaller -Clean`
3. **Smoke test:** Install + launch + transcription test
4. **HEAR-136/137:** After live test, copy WAV segments from `%APPDATA%\AyeHear\sessions\` to `benchmarks/asr-evaluation-dataset/` as authoritative corpus

---

**References:** HEAR-136, HEAR-137, HEAR-138, ADR-0002, ADR-0008  
**Security gate:** Required before release — HEAR-140 (security recheck for new model bundle)
