from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path
from typing import Any


def _resolve_path(manifest_path: Path, raw: str) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = manifest_path.parent / candidate
    return candidate.resolve()


def _wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
    if rate <= 0:
        raise ValueError(f"Invalid sample rate in WAV: {path}")
    return frames / float(rate)


def validate_dataset_manifest(
    manifest_path: Path,
    *,
    min_samples: int,
    min_real_samples: int,
    min_total_duration_seconds: float,
    allow_seed_only: bool,
) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("Manifest must contain a non-empty 'samples' list.")

    seen_ids: set[str] = set()
    real_samples = 0
    total_duration_seconds = 0.0

    for entry in samples:
        if not isinstance(entry, dict):
            raise ValueError(f"Each sample entry must be an object: {entry!r}")

        sample_id = str(entry.get("id", "")).strip()
        audio_raw = str(entry.get("audio", "")).strip()
        reference_raw = str(entry.get("reference", "")).strip()
        if not sample_id or not audio_raw or not reference_raw:
            raise ValueError(f"Sample missing id/audio/reference: {entry!r}")
        if sample_id in seen_ids:
            raise ValueError(f"Duplicate sample id in manifest: {sample_id}")
        seen_ids.add(sample_id)

        audio_path = _resolve_path(manifest_path, audio_raw)
        reference_path = _resolve_path(manifest_path, reference_raw)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found for sample '{sample_id}': {audio_path}")
        if not reference_path.exists():
            raise FileNotFoundError(f"Reference file not found for sample '{sample_id}': {reference_path}")

        tags = {str(tag).strip() for tag in entry.get("tags", []) if str(tag).strip()}
        if "real-meeting" in tags:
            real_samples += 1

        if audio_path.suffix.casefold() == ".wav":
            total_duration_seconds += _wav_duration_seconds(audio_path)

    sample_count = len(samples)

    if allow_seed_only:
        min_samples = 1
        min_real_samples = 0
        min_total_duration_seconds = 0.0

    if sample_count < min_samples:
        raise ValueError(f"Sample count too low: {sample_count} < {min_samples}")
    if real_samples < min_real_samples:
        raise ValueError(f"real-meeting sample count too low: {real_samples} < {min_real_samples}")
    if total_duration_seconds < min_total_duration_seconds:
        raise ValueError(
            "Total WAV duration too low: "
            f"{round(total_duration_seconds, 1)}s < {round(min_total_duration_seconds, 1)}s"
        )

    return {
        "dataset": payload.get("dataset"),
        "manifest": str(manifest_path.resolve()),
        "sample_count": sample_count,
        "real_meeting_sample_count": real_samples,
        "total_wav_duration_seconds": round(total_duration_seconds, 1),
        "thresholds": {
            "min_samples": min_samples,
            "min_real_samples": min_real_samples,
            "min_total_duration_seconds": min_total_duration_seconds,
            "allow_seed_only": allow_seed_only,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate HEAR-136 ASR dataset readiness.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--min-samples", type=int, default=10)
    parser.add_argument("--min-real-samples", type=int, default=10)
    parser.add_argument("--min-total-duration-seconds", type=float, default=1800.0)
    parser.add_argument(
        "--allow-seed-only",
        action="store_true",
        help="Relax thresholds for bootstrap validation of the seed sample only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = validate_dataset_manifest(
        manifest_path=args.manifest,
        min_samples=args.min_samples,
        min_real_samples=args.min_real_samples,
        min_total_duration_seconds=args.min_total_duration_seconds,
        allow_seed_only=args.allow_seed_only,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
