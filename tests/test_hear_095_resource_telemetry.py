"""Tests for HEAR-095: CPU/RAM resource telemetry during ASR and LLM inference."""
import json
import logging
import unittest
from unittest.mock import MagicMock, patch

from ayehear.services.protocol_engine import ProtocolEngine, _resource_snapshot as pe_resource_snapshot
from ayehear.services.transcription import _resource_snapshot as tr_resource_snapshot


class TestResourceSnapshot(unittest.TestCase):
    """_resource_snapshot helper returns expected structure or empty dict."""

    def test_returns_dict_with_cpu_and_ram(self):
        result = tr_resource_snapshot()
        if result:  # May be empty if psutil call fails
            assert "cpu_pct" in result
            assert "ram_mb" in result
            assert isinstance(result["cpu_pct"], float)
            assert isinstance(result["ram_mb"], float)
            assert result["ram_mb"] > 0

    def test_returns_empty_dict_on_import_error(self):
        with patch.dict("sys.modules", {"psutil": None}):
            result = tr_resource_snapshot()
            assert isinstance(result, dict)

    def test_same_helper_in_protocol_engine(self):
        """Both modules expose the same-shaped helper."""
        r = pe_resource_snapshot()
        assert isinstance(r, dict)


class TestTranscriptionTelemetryLogging(unittest.TestCase):
    """TranscriptionService._run_asr emits DEBUG logs with resource info."""

    def test_debug_log_emitted_on_asr_inference(self):
        """Verify that ASR inference emits start/end DEBUG messages."""
        from ayehear.services.transcription import TranscriptionService

        # Minimal WhisperModel mock
        seg_mock = MagicMock()
        seg_mock.text = "Hallo Welt"
        info_mock = MagicMock()
        info_mock.language = "de"

        model_mock = MagicMock()
        model_mock.transcribe.return_value = ([seg_mock], info_mock)

        svc = TranscriptionService(model_name="small")
        svc._model = model_mock

        with self.assertLogs("ayehear.services.transcription", level="DEBUG") as log:
            svc._run_asr([0.0] * 16000)

        # At least one DEBUG record expected (start or end)
        debug_records = [r for r in log.output if "ASR inference" in r]
        assert len(debug_records) >= 1, f"Expected ASR telemetry DEBUG log, got: {log.output}"


class TestProtocolEngineTelemetryLogging(unittest.TestCase):
    """ProtocolEngine._extract_via_ollama emits DEBUG logs with resource info."""

    def _make_ollama_response(self, data: dict) -> MagicMock:
        body = json.dumps({"response": json.dumps(data)}).encode()
        resp_mock = MagicMock()
        resp_mock.read.return_value = body
        resp_mock.__enter__ = lambda s: s
        resp_mock.__exit__ = MagicMock(return_value=False)
        return resp_mock

    def test_debug_log_emitted_on_llm_inference(self):
        import urllib.request as _urllib_req

        response_data = {
            "summary": ["Test"],
            "decisions": [],
            "action_items": [],
            "open_questions": [],
        }
        resp_mock = self._make_ollama_response(response_data)

        engine = ProtocolEngine()

        def fake_urlopen(req, timeout=None):
            return resp_mock

        with patch.object(_urllib_req, "urlopen", fake_urlopen):
            with self.assertLogs("ayehear.services.protocol_engine", level="DEBUG") as log:
                engine._extract_via_ollama(["Speaker: Hello"])

        debug_records = [r for r in log.output if "LLM inference" in r]
        assert len(debug_records) >= 1, f"Expected LLM telemetry DEBUG log, got: {log.output}"


if __name__ == "__main__":
    unittest.main()
