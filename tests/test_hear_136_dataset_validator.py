from __future__ import annotations

import importlib.util
import json
import sys
import wave
from pathlib import Path

import pytest


def _load_validator_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "tools" / "scripts" / "validate_hear_136_dataset.py"
    )
    spec = importlib.util.spec_from_file_location("validate_hear_136_dataset", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_silent_wav(path: Path, seconds: float = 1.0, sample_rate: int = 16000) -> None:
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frames)


def test_validator_accepts_seed_manifest_in_seed_mode() -> None:
    validator = _load_validator_module()
    manifest = Path("benchmarks/asr-evaluation-dataset/manifest.json")

    summary = validator.validate_dataset_manifest(
        manifest,
        min_samples=10,
        min_real_samples=10,
        min_total_duration_seconds=1800.0,
        allow_seed_only=True,
    )

    assert summary["sample_count"] >= 1
    assert summary["thresholds"]["allow_seed_only"] is True


def test_validator_rejects_seed_manifest_for_authoritative_gate() -> None:
    validator = _load_validator_module()
    manifest = Path("benchmarks/asr-evaluation-dataset/manifest.json")

    with pytest.raises(ValueError, match="Sample count too low"):
        validator.validate_dataset_manifest(
            manifest,
            min_samples=10,
            min_real_samples=10,
            min_total_duration_seconds=1800.0,
            allow_seed_only=False,
        )


def test_validator_passes_minimum_custom_manifest(tmp_path: Path) -> None:
    validator = _load_validator_module()

    audio = tmp_path / "a.wav"
    ref = tmp_path / "a.txt"
    _write_silent_wav(audio, seconds=2.0)
    ref.write_text("eins zwei drei\n", encoding="utf-8")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "dataset": "hear-136-asr-evaluation",
                "samples": [
                    {
                        "id": "sample-1",
                        "audio": str(audio),
                        "reference": str(ref),
                        "tags": ["real-meeting", "german"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = validator.validate_dataset_manifest(
        manifest,
        min_samples=1,
        min_real_samples=1,
        min_total_duration_seconds=1.5,
        allow_seed_only=False,
    )

    assert summary["sample_count"] == 1
    assert summary["real_meeting_sample_count"] == 1
    assert summary["total_wav_duration_seconds"] >= 2.0
