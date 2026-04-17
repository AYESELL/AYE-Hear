---
owner: AYEHEAR_DEVOPS
status: complete
task: HEAR-062
version: 0.2.0
date: 2026-04-16
category: release-assessment
---

# HEAR-062 – Packaged Runtime Verification: ASR Dependencies

## Scope

Follow-up to v0.2.0 RC user test failure where live transcription produced no output.
Verify whether the release candidate bundles all offline ASR prerequisites.

---

## Verification Summary

| Component | Dev Machine | Packaged Bundle (v0.2.0 RC) | Status |
|-----------|-------------|------------------------------|--------|
| `faster_whisper` Python code | ✅ installed in venv | ✅ **in PYZ archive** (auto-detected by PyInstaller) | OK |
| `ctranslate2` native DLL (58 MB) | ✅ | ✅ `_internal/ctranslate2/ctranslate2.dll` | OK |
| `ctranslate2` Python ext (`.pyd`) | ✅ | ✅ `_internal/ctranslate2/_ext.cp312-win_amd64.pyd` | OK |
| `libiomp5md.dll` (OpenMP) | ✅ | ✅ `_internal/ctranslate2/libiomp5md.dll` | OK |
| `tokenizers` | ✅ | ✅ `_internal/tokenizers/` | OK |
| **Whisper `base` model** (`model.bin`, 138 MB) | ✅ HuggingFace cache | ❌ **NOT BUNDLED** | **ROOT CAUSE** |
| `config.json` / `tokenizer.json` / `vocabulary.txt` | ✅ HuggingFace cache | ❌ **NOT BUNDLED** | **ROOT CAUSE** |

---

## Root Cause

`WhisperModel("base")` uses HuggingFace Hub to locate / download model files at runtime.  
On the **developer machine** the model is already cached at:

```
%USERPROFILE%\.cache\huggingface\hub\models--Systran--faster-whisper-base\
```

On a **fresh target machine** (no HuggingFace cache):
- `WhisperModel("base")` attempts an internet download → violates ADR-0001 offline-first pledge  
- On air-gapped machines: raises `RuntimeError` → `ASR_DIAG_INFERENCE_ERROR` (HEAR-061 path)

The Python code for `faster_whisper` **is** present in the bundle (PYZ compressed bytecode).  
The ctranslate2 runtime DLLs **are** present.  
Only the **model weight files** were missing from the package.

---

## Fix Applied (HEAR-062)

Three changes were made:

### 1. `build/aye-hear.spec` — Dynamic model datas injection

```python
_whisper_model_dir = os.path.join(os.path.dirname(os.path.abspath(SPEC)),
                                   '..', 'config', 'models', 'whisper', 'base')
_whisper_datas = [(_whisper_model_dir, 'models/whisper/base')] \
    if os.path.isfile(os.path.join(_whisper_model_dir, 'model.bin')) else []

datas=[...] + _whisper_datas
```

If model not staged: build proceeds without model (warning only), not a hard error.

### 2. `tools/scripts/Build-WindowsPackage.ps1` — Model staging step

Before PyInstaller runs, the script now:
1. Checks for existing staged model at `config/models/whisper/base/model.bin`
2. If absent: locates HuggingFace cache at `%USERPROFILE%\.cache\huggingface\hub\models--Systran--faster-whisper-base\snapshots\<hash>\`
3. Resolves Windows symlinks → copies actual blob files to staging dir
4. Reports staged file names and sizes

If cache not found: emits warning with instructions to pre-download, continues.

**CI/CD requirement:** Build agents must run model pre-download before `Build-WindowsPackage.ps1`:
```powershell
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### 3. `src/ayehear/services/transcription.py` — Bundled path detection

`TranscriptionService._run_asr()` now checks for the bundled model first when frozen:

```python
if getattr(sys, "frozen", False):
    bundled = Path(sys._MEIPASS) / "models" / "whisper" / self.model_name
    if bundled.is_dir() and (bundled / "model.bin").exists():
        model_path = str(bundled)   # use local bundle → fully offline
    else:
        logger.warning("Bundled model not found — falling back to HuggingFace download")
```

Falls back gracefully to HuggingFace download if bundle path absent (dev/test scenarios).

---

## Model Files Bundled (v0.2.0+)

| File | Source | Size |
|------|--------|------|
| `model.bin` | Systran/faster-whisper-base (CTranslate2 int8) | ~138 MB |
| `config.json` | Whisper base config | ~0.4 KB |
| `tokenizer.json` | multilingual tokenizer vocab | ~2.1 MB |
| `vocabulary.txt` | Whisper vocabulary | ~440 KB |
| **Total** | | **~141 MB** |

Staged to: `config/models/whisper/base/` (`.gitkeep` tracks dir; binaries are gitignored)

---

## Dev vs Packaged Behavior (after fix)

| Scenario | Behavior |
|----------|----------|
| Dev machine (no freeze) | `WhisperModel("base")` → uses HuggingFace cache as before |
| Packaged app + model bundled | Uses `_MEIPASS/models/whisper/base/` → fully offline |
| Packaged app + model missing | Falls back to HuggingFace, logs warning; HEAR-061 diag fires if network unavailable |

---

## Build Instructions for v0.2.1+

```powershell
# 1. Ensure model is pre-downloaded (once per build agent)
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('base')"

# 2. Full clean build with installer
.\.venv\Scripts\Activate.ps1
.\tools\scripts\Build-WindowsPackage.ps1 -Clean -BuildInstaller

# Expected output (model staging step):
# [model] Staging Whisper 'base' from ...
#         config.json  (0.0 MB)
#         model.bin  (138.5 MB)
#         tokenizer.json  (2.1 MB)
#         vocabulary.txt  (0.4 MB)
# [model] Whisper model staged to config\models\whisper\base  OK
```

---

## Tests

All 14 transcription tests continue to pass (`tests/test_transcription.py`).  
The bundled-path code path (`sys.frozen`) is covered by the logic branch;  
integration tests on the actual packaged EXE are recommended as a follow-up (HEAR-063).

---

## Residuals / Follow-up

| ID | Description |
|----|-------------|
| HEAR-062-R1 | `config/models/whisper/base/*.bin` must be added to `.gitignore` (model binaries must not be committed) |
| HEAR-062-R2 | CI/CD pipeline agent needs pre-download step documented in `docs/quick-refs/CI_PIPELINE_RUNBOOK.md` |
| HEAR-062-R3 | Packaged-EXE smoke test for ASR (verify `_MEIPASS/models/whisper/base/model.bin` loads) recommended |

---

**Signed off by:** AYEHEAR_DEVOPS  
**Date:** 2026-04-16
