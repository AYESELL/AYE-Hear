# AYE Hear

AYE Hear is a Windows-first desktop product for local meeting transcription, speaker identification and live protocol generation.

## Current State

- Offline-first desktop application based on PySide6
- Local runtime configuration in `config/default.yaml`
- Runtime path model and local persistence under `src/ayehear`
- Automated regression coverage under `tests`
- Role-specific agent configuration in `.github`
- Windows packaging path with installer evidence in `docs/HEAR-100-build-evidence.md`

## Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m ayehear.app
pytest tests -q

# Deterministic multi-model protocol replay
python -m ayehear protocol-replay --baseline exports\My_Meeting_20260416_201958-transcript.txt --title "Replay Run"
```

## Core Documentation

- `docs/PRODUCT_FOUNDATION.md`
- `docs/adr/README.md`
- `docs/governance/QUALITY_GATES.md`
- `docs/governance/7-PHASE-WORKFLOW.md`

## Formal Closure Targets

1. Complete the installed-package E2E evidence bundle for non-default path commissioning per `docs/HEAR-091-INSTALLED-E2E-CHECKLIST.md`.
2. Reconcile release/readiness communication so product-complete status is derived from installed E2E evidence, not only from code-level feature closure.
3. Finish Phase-1B benchmark closure and default-model documentation alignment for the packaged runtime path.
