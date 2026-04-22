from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_benchmark_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "scripts" / "benchmark_whisper_models.py"
    spec = importlib.util.spec_from_file_location("benchmark_whisper_models", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hear_136_manifest_resolves_seed_sample() -> None:
    benchmark = _load_benchmark_module()
    manifest = Path("benchmarks/asr-evaluation-dataset/manifest.json")

    samples = benchmark._load_dataset_samples(manifest)

    assert len(samples) >= 1
    seed = next(sample for sample in samples if sample.sample_id == "hear-113-seed")
    assert seed.audio_path.exists()
    assert seed.reference_path.exists()
    assert "synthetic" in seed.tags


def test_hear_136_manifest_is_wired_for_benchmark_contract() -> None:
    manifest = Path("benchmarks/asr-evaluation-dataset/manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert payload["dataset"] == "hear-136-asr-evaluation"
    assert payload["owner"] == "AYEHEAR_QA"
    assert payload["samples"][0]["id"] == "hear-113-seed"
    assert payload["samples"][0]["reference"] == "references/hear-113-seed.txt"


def test_aggregate_model_results_averages_across_samples() -> None:
    """summary must reflect per-model mean WER across all samples, not best single run.

    Without aggregation, max(accuracy_pct) on the flat results list picks the model
    that happened to run on the easiest sample.  _aggregate_model_results must pick
    the model with the lowest mean WER across all samples.
    """
    benchmark = _load_benchmark_module()

    def _make(model: str, sample_id: str, wer: float, secs: float = 1.0, ram: float = 1000.0):
        return benchmark.BenchmarkResult(
            sample_id=sample_id, model=model, model_source=model,
            compute_type="int8", beam_size=3, audio_seconds=1.0,
            load_seconds=0.1, transcribe_seconds=secs - 0.1, total_seconds=secs,
            peak_ram_mb=ram, avg_cpu_pct=50.0, peak_cpu_pct=80.0,
            transcript_chars=10, transcript_words=2, reference_words=2,
            wer=wer, accuracy_pct=round((1.0 - wer) * 100.0, 2),
            detected_language="de", detected_language_probability=0.99,
            transcript_path="out/x.txt",
        )

    # model-a: great on easy sample (wer=0.05), poor on hard (wer=0.40) -> mean 0.225
    # model-b: consistently good (wer=0.15, 0.20) -> mean 0.175
    # Without aggregation, max(accuracy_pct) picks model-a (easy-sample score 95%).
    # With aggregation, model-b wins (lower mean WER across both samples).
    results = [
        _make("model-a", "easy", wer=0.05),
        _make("model-a", "hard", wer=0.40),
        _make("model-b", "easy", wer=0.15),
        _make("model-b", "hard", wer=0.20),
    ]

    aggs, best_acc, _fastest, _ram = benchmark._aggregate_model_results(results)

    assert best_acc == "model-b", (
        f"model-b (mean WER 0.175) should beat model-a (0.225); got {best_acc}"
    )
    assert aggs["model-a"]["sample_count"] == 2
    assert aggs["model-b"]["mean_wer"] == 0.175
    assert aggs["model-a"]["mean_wer"] == 0.225


def test_benchmark_transcript_filename_sanitizes_hf_slash(tmp_path: Path) -> None:
    """_benchmark_model must not create subdirectories for HF model IDs with slashes.

    This test calls the actual production function (_benchmark_model) with a
    mocked WhisperModel so it fails if the sanitization is ever removed.
    """
    import unittest.mock as mock
    import pytest

    benchmark = _load_benchmark_module()

    repo_root = Path(__file__).resolve().parents[1]
    audio_path = (
        repo_root / "deployment-evidence" / "hear-113" / "2026-04-19" / "hear-113-reference.wav"
    )
    if not audio_path.exists():
        pytest.skip("Seed WAV not present")

    mock_segment = mock.MagicMock()
    mock_segment.text = "test transcript"
    mock_info = mock.MagicMock()
    mock_info.language = "de"
    mock_info.language_probability = 0.99
    mock_model = mock.MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    model_name = "TheChola/whisper-large-v3-turbo-german-faster-whisper"
    with mock.patch.object(benchmark, "WhisperModel", return_value=mock_model):
        result = benchmark._benchmark_model(
            repo_root=repo_root,
            sample_id="test-sample",
            audio_path=audio_path,
            reference_text="test transcript",
            model_name=model_name,
            compute_type="int8",
            beam_size=3,
            language="de",
            output_dir=tmp_path,
        )

    transcript_path = Path(result.transcript_path)
    assert transcript_path.parent == tmp_path, (
        f"Transcript must be directly in output_dir; got {transcript_path}"
    )
    assert "/" not in transcript_path.name
    assert "\\" not in transcript_path.name
    assert transcript_path.exists()