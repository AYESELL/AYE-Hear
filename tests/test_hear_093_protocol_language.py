"""Tests for HEAR-093: Protocol language selection UI and ProtocolEngine integration."""
import json
import unittest
from unittest.mock import MagicMock, patch

from ayehear.models.runtime import ProtocolSettings, RuntimeConfig
from ayehear.services.protocol_engine import ProtocolEngine


class TestProtocolSettings(unittest.TestCase):
    """ProtocolSettings model defaults and language list."""

    def test_default_language_is_deutsch(self):
        s = ProtocolSettings()
        assert s.protocol_language == "Deutsch"

    def test_language_options_contain_de_en_fr(self):
        s = ProtocolSettings()
        assert "Deutsch" in s.protocol_language_options
        assert "English" in s.protocol_language_options
        assert "Francais" in s.protocol_language_options

    def test_custom_language_stored(self):
        s = ProtocolSettings(protocol_language="English")
        assert s.protocol_language == "English"

    def test_runtime_config_has_protocol_language(self):
        cfg = RuntimeConfig()
        assert cfg.protocol.protocol_language == "Deutsch"


class TestProtocolEngineLanguage(unittest.TestCase):
    """ProtocolEngine respects the language parameter in prompts."""

    def test_default_language_is_deutsch(self):
        engine = ProtocolEngine()
        assert engine._language == "Deutsch"

    def test_custom_language_stored(self):
        engine = ProtocolEngine(language="English")
        assert engine._language == "English"

    def test_set_language_runtime(self):
        engine = ProtocolEngine()
        engine._language = "Francais"
        assert engine._language == "Francais"

    def _make_ollama_response(self, data: dict) -> MagicMock:
        body = json.dumps({"response": json.dumps(data)}).encode()
        resp_mock = MagicMock()
        resp_mock.read.return_value = body
        resp_mock.__enter__ = lambda s: s
        resp_mock.__exit__ = MagicMock(return_value=False)
        return resp_mock

    def _capture_prompt(self, language: str, lines: list[str]) -> str:
        """Run _extract_via_ollama and return the prompt sent to Ollama."""
        captured: list[str] = []

        response_data = {"summary": ["ok"], "decisions": [], "action_items": [], "open_questions": []}
        resp_mock = self._make_ollama_response(response_data)

        engine = ProtocolEngine(language=language)

        import urllib.request as _urllib_req
        original_urlopen = _urllib_req.urlopen

        def fake_urlopen(req, timeout=None):
            captured.append(req.data.decode())
            return resp_mock

        with patch.object(_urllib_req, "urlopen", fake_urlopen):
            engine._extract_via_ollama(lines)

        assert captured, "urlopen was not called"
        payload = json.loads(captured[0])
        return payload["prompt"]

    def test_deutsch_prompt_mentions_german(self):
        prompt = self._capture_prompt("Deutsch", ["Speaker: Hallo Welt"])
        assert "Deutsch" in prompt or "Protokoll" in prompt

    def test_english_prompt_in_english(self):
        prompt = self._capture_prompt("English", ["Speaker: Hello world"])
        assert "English" in prompt or "meeting assistant" in prompt.lower()

    def test_francais_prompt_in_french(self):
        prompt = self._capture_prompt("Francais", ["Speaker: Bonjour le monde"])
        assert "français" in prompt.lower() or "réunion" in prompt.lower()

    def test_unknown_language_falls_back_to_deutsch(self):
        prompt = self._capture_prompt("Klingon", ["Speaker: Qapla"])
        # Should still produce a valid prompt (Deutsch fallback)
        assert "Schema" in prompt or "Protokoll" in prompt


if __name__ == "__main__":
    unittest.main()
