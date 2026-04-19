from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from ayehear.models.runtime import ModelSettings, RuntimeConfig
from ayehear.services.protocol_engine import OllamaModelUnavailableError, ProtocolEngine


def test_protocol_engine_default_ollama_model_is_mistral_7b() -> None:
    engine = ProtocolEngine()
    assert engine._ollama_model == "mistral:7b"


def test_main_window_passes_runtime_ollama_model_to_protocol_engine(qapp) -> None:
    from ayehear.app.window import MainWindow

    cfg = RuntimeConfig(models=ModelSettings(ollama_model="llama3:8b"))
    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        window = MainWindow(runtime_config=cfg)

    assert window._protocol_engine._ollama_model == "llama3:8b"
    window.deleteLater()
    qapp.processEvents()


def test_protocol_engine_uses_configured_model_in_ollama_payload() -> None:
    response = MagicMock()
    response.read.return_value = json.dumps(
        {
            "response": json.dumps(
                {
                    "summary": ["ok"],
                    "decisions": [],
                    "action_items": [],
                    "open_questions": [],
                }
            )
        }
    ).encode()
    response.__enter__.return_value = response
    response.__exit__.return_value = None

    with patch.object(ProtocolEngine, "available_models", return_value=["llama3:8b"]), patch(
        "urllib.request.urlopen",
        return_value=response,
    ) as mock_urlopen:
        engine = ProtocolEngine(ollama_model="llama3:8b")
        result = engine.summarize_window(["Anna: Bitte pruefe den Entwurf."])

    request = mock_urlopen.call_args.args[0]
    payload = json.loads(request.data.decode())
    assert payload["model"] == "llama3:8b"
    assert result["summary"] == ["ok"]


def test_protocol_engine_falls_back_when_configured_model_missing() -> None:
    engine = ProtocolEngine(ollama_model="mistral:7b")

    with patch.object(ProtocolEngine, "available_models", return_value=["llama3:8b"]):
        result = engine.summarize_window(["Anna: Bitte sende das Follow-up."])

    assert result["action_items"] == ["Bitte sende das Follow-up."]
    assert engine.last_diagnostics["fallback_used"] is True
    assert engine.last_diagnostics["status"] == "rule_based_fallback"


def test_protocol_engine_raises_without_fallback_when_configured_model_missing() -> None:
    engine = ProtocolEngine(ollama_model="mistral:7b", fallback_enabled=False)

    with patch.object(ProtocolEngine, "available_models", return_value=["llama3:8b"]):
        with pytest.raises(OllamaModelUnavailableError, match="Configured Ollama model"):
            engine.summarize_window(
                ["Anna: Bitte sende das Follow-up."],
                allow_fallback=False,
            )