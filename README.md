# AYE Hear

AYE Hear is a Windows-first desktop product for local meeting transcription, speaker identification and live protocol generation.

## Current Scaffold

- Offline-first desktop shell based on PySide6
- Local runtime configuration in `config/default.yaml`
- Python package scaffold under `src/ayehear`
- Test scaffold under `tests`
- Role-specific agent configuration in `.github`
- Windows CI smoke workflow in `.github/workflows/windows-build.yml`

## Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m ayehear.app
pytest tests -q
```

## Core Documentation

- `docs/PRODUCT_FOUNDATION.md`
- `docs/adr/README.md`
- `docs/governance/QUALITY_GATES.md`
- `docs/governance/7-PHASE-WORKFLOW.md`

## Next Build Targets

1. Replace placeholder services with real audio capture and enrollment flows.
2. Add PostgreSQL persistence for meetings, speakers and protocol revisions.
3. Integrate faster-whisper, diarization and local LLM orchestration.
