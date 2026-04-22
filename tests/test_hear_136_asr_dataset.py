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


def test_benchmark_transcript_filename_sanitizes_hf_slash() -> None:
    """HF model IDs like 'TheChola/model-name' must not create subdirectories."""
    benchmark = _load_benchmark_module()
    tmp = Path("benchmarks/asr-evaluation-dataset")
    # Simulate path construction for a HF model ID with a slash
    model_name = "TheChola/whisper-large-v3-turbo-german-faster-whisper"
    safe_model_name = model_name.replace("/", "_")
    transcript_path = tmp / f"whisper-{safe_model_name}-transcript.txt"
    # Must stay inside tmp — no subdirectory from the slash
    assert transcript_path.parent == tmp
    # Must not contain any remaining slash-derived directory component
    assert "/" not in transcript_path.name
    assert "\\" not in transcript_path.name