from __future__ import annotations

import argparse
import json
import re
import threading
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil
from faster_whisper import WhisperModel


def _normalize_text(text: str) -> str:
    lowered = text.casefold()
    lowered = lowered.replace("-", " ")
    lowered = re.sub(r"[^\w\säöüß]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    return normalized.split() if normalized else []


def _word_error_rate(reference: str, hypothesis: str) -> float:
    ref_tokens = _tokenize(reference)
    hyp_tokens = _tokenize(hypothesis)
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0

    rows = len(ref_tokens) + 1
    cols = len(hyp_tokens) + 1
    distance = [[0] * cols for _ in range(rows)]

    for row in range(rows):
        distance[row][0] = row
    for col in range(cols):
        distance[0][col] = col

    for row in range(1, rows):
        for col in range(1, cols):
            substitution_cost = 0 if ref_tokens[row - 1] == hyp_tokens[col - 1] else 1
            distance[row][col] = min(
                distance[row - 1][col] + 1,
                distance[row][col - 1] + 1,
                distance[row - 1][col - 1] + substitution_cost,
            )

    return distance[-1][-1] / len(ref_tokens)


@dataclass
class ResourceTelemetry:
    peak_ram_mb: float = 0.0
    avg_cpu_pct: float = 0.0
    peak_cpu_pct: float = 0.0
    sample_count: int = 0


class ResourceSampler:
    def __init__(self, sample_interval: float = 0.1) -> None:
        self._process = psutil.Process()
        self._sample_interval = sample_interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.telemetry = ResourceTelemetry()
        self._cpu_sum = 0.0

    def start(self) -> None:
        self._process.cpu_percent(interval=None)
        self._thread.start()

    def stop(self) -> ResourceTelemetry:
        self._stop.set()
        self._thread.join()
        if self.telemetry.sample_count:
            self.telemetry.avg_cpu_pct = round(self._cpu_sum / self.telemetry.sample_count, 1)
        self.telemetry.peak_ram_mb = round(self.telemetry.peak_ram_mb, 1)
        self.telemetry.peak_cpu_pct = round(self.telemetry.peak_cpu_pct, 1)
        return self.telemetry

    def _run(self) -> None:
        while not self._stop.is_set():
            cpu_pct = self._process.cpu_percent(interval=self._sample_interval)
            ram_mb = self._process.memory_info().rss / (1024 * 1024)
            self._cpu_sum += cpu_pct
            self.telemetry.sample_count += 1
            if cpu_pct > self.telemetry.peak_cpu_pct:
                self.telemetry.peak_cpu_pct = cpu_pct
            if ram_mb > self.telemetry.peak_ram_mb:
                self.telemetry.peak_ram_mb = ram_mb


@dataclass
class BenchmarkResult:
    sample_id: str
    model: str
    model_source: str
    compute_type: str
    beam_size: int
    audio_seconds: float
    load_seconds: float
    transcribe_seconds: float
    total_seconds: float
    peak_ram_mb: float
    avg_cpu_pct: float
    peak_cpu_pct: float
    transcript_chars: int
    transcript_words: int
    reference_words: int
    wer: float
    accuracy_pct: float
    detected_language: str
    detected_language_probability: float | None
    transcript_path: str


@dataclass(frozen=True)
class DatasetSample:
    sample_id: str
    audio_path: Path
    reference_path: Path
    tags: tuple[str, ...] = ()
    notes: str = ""


def _resolve_model_path(repo_root: Path, model_name: str) -> str:
    local_dir = repo_root / "config" / "models" / "whisper" / model_name
    if (local_dir / "model.bin").exists():
        return str(local_dir)
    return model_name


def _audio_duration_seconds(audio_path: Path) -> float:
    with wave.open(str(audio_path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
    return round(frames / float(rate), 3)


def _benchmark_model(
    repo_root: Path,
    sample_id: str,
    audio_path: Path,
    reference_text: str,
    model_name: str,
    compute_type: str,
    beam_size: int,
    language: str,
    output_dir: Path,
) -> BenchmarkResult:
    model_source = _resolve_model_path(repo_root, model_name)
    load_start = time.perf_counter()
    model = WhisperModel(model_source, device="cpu", compute_type=compute_type)
    load_seconds = time.perf_counter() - load_start

    sampler = ResourceSampler(sample_interval=0.1)
    sampler.start()
    transcribe_start = time.perf_counter()
    segments, info = model.transcribe(str(audio_path), language=language, beam_size=beam_size)
    texts = [segment.text.strip() for segment in segments if segment.text.strip()]
    transcribe_seconds = time.perf_counter() - transcribe_start
    telemetry = sampler.stop()

    transcript = " ".join(texts).strip()
    safe_model_name = model_name.replace("/", "_")
    transcript_path = output_dir / f"whisper-{safe_model_name}-transcript.txt"
    transcript_path.write_text(transcript + "\n", encoding="utf-8")

    wer = _word_error_rate(reference_text, transcript)
    accuracy_pct = max(0.0, round((1.0 - wer) * 100.0, 2))

    return BenchmarkResult(
        sample_id=sample_id,
        model=model_name,
        model_source=model_source,
        compute_type=compute_type,
        beam_size=beam_size,
        audio_seconds=_audio_duration_seconds(audio_path),
        load_seconds=round(load_seconds, 3),
        transcribe_seconds=round(transcribe_seconds, 3),
        total_seconds=round(load_seconds + transcribe_seconds, 3),
        peak_ram_mb=telemetry.peak_ram_mb,
        avg_cpu_pct=telemetry.avg_cpu_pct,
        peak_cpu_pct=telemetry.peak_cpu_pct,
        transcript_chars=len(transcript),
        transcript_words=len(_tokenize(transcript)),
        reference_words=len(_tokenize(reference_text)),
        wer=round(wer, 4),
        accuracy_pct=accuracy_pct,
        detected_language=getattr(info, "language", language),
        detected_language_probability=round(getattr(info, "language_probability", 0.0), 4)
        if getattr(info, "language_probability", None) is not None
        else None,
        transcript_path=str(transcript_path),
    )


def _resolve_dataset_path(dataset_path: Path, value: str) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = dataset_path.parent / candidate
    return candidate.resolve()


def _load_dataset_samples(dataset_path: Path) -> list[DatasetSample]:
    payload: dict[str, Any] = json.loads(dataset_path.read_text(encoding="utf-8"))
    samples_payload = payload.get("samples")
    if not isinstance(samples_payload, list) or not samples_payload:
        raise ValueError(f"Dataset manifest has no samples: {dataset_path}")

    samples: list[DatasetSample] = []
    for item in samples_payload:
        if not isinstance(item, dict):
            raise ValueError(f"Dataset sample entry must be an object: {item!r}")
        sample_id = str(item.get("id", "")).strip()
        audio = str(item.get("audio", "")).strip()
        reference = str(item.get("reference", "")).strip()
        if not sample_id or not audio or not reference:
            raise ValueError(f"Dataset sample missing id/audio/reference: {item!r}")

        audio_path = _resolve_dataset_path(dataset_path, audio)
        reference_path = _resolve_dataset_path(dataset_path, reference)
        if not audio_path.exists():
            raise FileNotFoundError(f"Dataset audio not found for {sample_id}: {audio_path}")
        if not reference_path.exists():
            raise FileNotFoundError(f"Dataset reference not found for {sample_id}: {reference_path}")

        tags = tuple(str(tag).strip() for tag in item.get("tags", []) if str(tag).strip())
        notes = str(item.get("notes", "")).strip()
        samples.append(
            DatasetSample(
                sample_id=sample_id,
                audio_path=audio_path,
                reference_path=reference_path,
                tags=tags,
                notes=notes,
            )
        )

    return samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Whisper models for HEAR-113.")
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument(
        "--dataset",
        type=Path,
        help="Path to a dataset manifest JSON containing one or more audio/reference pairs.",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--beam-size", type=int, default=3)
    parser.add_argument("--language", default="de")
    args = parser.parse_args()
    if args.dataset:
        if args.audio or args.reference:
            parser.error("Use either --dataset or --audio/--reference, not both.")
    elif not args.audio or not args.reference:
        parser.error("Either --dataset or both --audio and --reference are required.")
    return args


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.dataset:
        samples = _load_dataset_samples(args.dataset)
    else:
        samples = [
            DatasetSample(
                sample_id=args.audio.stem,
                audio_path=args.audio,
                reference_path=args.reference,
            )
        ]

    models = args.models or ["small", "base"]
    results: list[BenchmarkResult] = []
    sample_summaries: list[dict[str, Any]] = []

    for sample in samples:
        sample_output_dir = output_dir / sample.sample_id
        sample_output_dir.mkdir(parents=True, exist_ok=True)
        reference_text = sample.reference_path.read_text(encoding="utf-8")
        sample_results = [
            _benchmark_model(
                repo_root=repo_root,
                sample_id=sample.sample_id,
                audio_path=sample.audio_path,
                reference_text=reference_text,
                model_name=model_name,
                compute_type=args.compute_type,
                beam_size=args.beam_size,
                language=args.language,
                output_dir=sample_output_dir,
            )
            for model_name in models
        ]
        results.extend(sample_results)

        best_accuracy = max(sample_results, key=lambda item: item.accuracy_pct)
        fastest = min(sample_results, key=lambda item: item.total_seconds)
        lowest_ram = min(sample_results, key=lambda item: item.peak_ram_mb)
        sample_summaries.append(
            {
                "sample_id": sample.sample_id,
                "audio": str(sample.audio_path),
                "reference": str(sample.reference_path),
                "tags": list(sample.tags),
                "notes": sample.notes,
                "best_accuracy_model": best_accuracy.model,
                "fastest_model": fastest.model,
                "lowest_ram_model": lowest_ram.model,
                "results": [asdict(result) for result in sample_results],
            }
        )

    best_accuracy = max(results, key=lambda item: item.accuracy_pct)
    fastest = min(results, key=lambda item: item.total_seconds)
    lowest_ram = min(results, key=lambda item: item.peak_ram_mb)

    report = {
        "benchmark": "HEAR-136",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "audio": str(samples[0].audio_path) if len(samples) == 1 else None,
        "reference": str(samples[0].reference_path) if len(samples) == 1 else None,
        "dataset": str(args.dataset.resolve()) if args.dataset else None,
        "sample_count": len(samples),
        "compute_type": args.compute_type,
        "beam_size": args.beam_size,
        "language": args.language,
        "results": [asdict(result) for result in results],
        "samples": sample_summaries,
        "summary": {
            "best_accuracy_model": best_accuracy.model,
            "fastest_model": fastest.model,
            "lowest_ram_model": lowest_ram.model,
        },
    }
    report_path = output_dir / "benchmark-results.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nSaved report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())