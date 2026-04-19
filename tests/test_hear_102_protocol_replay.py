from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ayehear.__main__ import main
from ayehear.models.runtime import ModelSettings, RuntimeConfig
from ayehear.services.protocol_engine import OllamaModelUnavailableError
from ayehear.services.protocol_replay import ProtocolReplayResult, ProtocolReplayService


def test_discover_models_unions_configured_and_local_models() -> None:
    service = ProtocolReplayService()

    with patch(
        "ayehear.services.protocol_engine.ProtocolEngine.available_models",
        return_value=["llama3:8b", "mistral:7b"],
    ):
        models = service.discover_models(["mistral:7b", "phi3:mini"])

    assert models == ["mistral:7b", "phi3:mini", "llama3:8b"]


def test_replay_baseline_writes_model_tagged_exports_and_manifest(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(
        "Meeting Transcript - Sample\nExported: 2026-04-18T10:00:00\n\nAnna: Hallo\n",
        encoding="utf-8",
    )
    service = ProtocolReplayService()

    def _fake_summary(self, transcript_window, *, allow_fallback=None):
        assert allow_fallback is False
        return {
            "summary": [f"summary for {self._ollama_model}"],
            "decisions": [],
            "action_items": ["Task"],
            "open_questions": [],
        }

    with patch("ayehear.services.protocol_engine.ProtocolEngine.summarize_window", new=_fake_summary):
        results = service.replay_baseline(
            baseline,
            tmp_path / "out",
            meeting_title="Replay Meeting",
            models=["mistral:7b", "llama3:8b"],
        )

    assert len(results) == 2
    names = [result.output_path.name for result in results]
    assert any("mistral-7b-protocol.md" in name for name in names)
    assert any("llama3-8b-protocol.md" in name for name in names)
    for result in results:
        content = result.output_path.read_text(encoding="utf-8")
        assert f"- Model: {result.model}" in content
        assert "- Duration Ms:" in content
        assert "## Summary" in content

    manifest = next((tmp_path / "out").glob("*_manifest.json"))
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["baseline"].endswith("baseline.txt")
    assert len(payload["results"]) == 2


def test_replay_baseline_writes_failure_artifact_without_fallback_mixing(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("Anna: Bitte pruefe das.\n", encoding="utf-8")
    service = ProtocolReplayService()

    def _strict_failure(self, transcript_window, *, allow_fallback=None):
        assert allow_fallback is False
        raise OllamaModelUnavailableError("Configured Ollama model 'mistral:7b' is unavailable.")

    with patch("ayehear.services.protocol_engine.ProtocolEngine.summarize_window", new=_strict_failure):
        results = service.replay_baseline(
            baseline,
            tmp_path / "out",
            meeting_title="Replay Meeting",
            models=["mistral:7b"],
        )

    assert len(results) == 1
    assert results[0].status == "failed"
    content = results[0].output_path.read_text(encoding="utf-8")
    assert "- Status: failed" in content
    assert "Meeting recorded:" not in content
    assert "## Error" in content


def test_protocol_replay_cli_uses_default_configured_model(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("Anna: Hallo\n", encoding="utf-8")
    result = ProtocolReplayResult(
        model="phi3:mini",
        status="success",
        started_at="2026-04-18T10:00:00",
        duration_ms=12,
        output_path=tmp_path / "phi3.md",
    )

    with patch(
        "ayehear.__main__.load_runtime_config",
        return_value=RuntimeConfig(models=ModelSettings(ollama_model="phi3:mini")),
    ), patch(
        "ayehear.__main__.ProtocolReplayService.replay_baseline",
        return_value=[result],
    ) as mock_replay:
        exit_code = main(
            [
                "protocol-replay",
                "--baseline",
                str(baseline),
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "phi3:mini: success" in captured.out
    assert mock_replay.call_args.kwargs["configured_models"] == ["phi3:mini"]