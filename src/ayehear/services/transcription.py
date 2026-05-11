"""Transcription pipeline integration (HEAR-013).

Wraps faster-whisper for offline ASR and persists segments to PostgreSQL
via TranscriptSegmentRepository. No external network calls are made at runtime;
model loading is restricted to bundled or already-local sources only.

Transcription profiles map to faster-whisper compute_type / beam_size settings:
  - fast   : int8, beam_size=1
  - balanced: float16 (or int8 on CPU), beam_size=3
  - accurate: float16, beam_size=5
"""
from __future__ import annotations

import logging
import math
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ayehear.services.audio_capture import AudioSegment
    from ayehear.storage.repositories import TranscriptSegmentRepository

logger = logging.getLogger(__name__)


def _resolve_model_source(model_name: str) -> tuple[str, dict[str, Any]]:
    """Return a local-only WhisperModel source and loader kwargs.

    Packaged runtimes must load the staged bundle from ``sys._MEIPASS`` and
    fail closed if it is missing. Development/CI runs may use model aliases,
    but only with ``local_files_only=True`` so faster-whisper never downloads
    from HuggingFace at runtime.
    """
    configured_path = Path(model_name)
    if configured_path.exists():
        return str(configured_path), {}

    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "models" / "whisper" / model_name  # type: ignore[attr-defined]
        if bundled.is_dir() and (bundled / "model.bin").exists():
            logger.debug("Using bundled Whisper model: %s", bundled)
            return str(bundled), {}
        raise RuntimeError(
            f"Bundled Whisper model '{model_name}' not found at {bundled}. "
            "AYE Hear blocks runtime model downloads to preserve offline-first operation."
        )

    return model_name, {"local_files_only": True}


def _resource_snapshot() -> dict:
    """Return current CPU% and RAM MB (HEAR-095). Returns empty dict if psutil unavailable."""
    try:
        import psutil  # type: ignore[import-untyped]
        process = psutil.Process()
        return {
            "cpu_pct": psutil.cpu_percent(interval=None),
            "ram_mb": round(process.memory_info().rss / (1024 * 1024), 1),
        }
    except Exception:
        return {}


_PROFILES: dict[str, dict] = {
    "fast":     {"compute_type": "int8",   "beam_size": 1},
    "balanced": {"compute_type": "int8",   "beam_size": 3},
    "accurate": {"compute_type": "float16","beam_size": 5},
}

# HEAR-061: diagnostic codes surfaced in TranscriptResult.asr_diagnostic
ASR_DIAG_NOT_INSTALLED = "not_installed"
ASR_DIAG_MODEL_LOAD_ERROR = "model_load_error"
ASR_DIAG_INFERENCE_ERROR = "inference_error"
ASR_DIAG_EMPTY_RESULT = "empty_result"


class AsrUnavailableError(RuntimeError):
    """Raised when faster-whisper is not installed or cannot be imported (HEAR-061)."""


# HEAR-152: review reason codes to distinguish transcript vs speaker uncertainty
REVIEW_REASON_TRANSCRIPT_QUALITY = "transcript_quality"
REVIEW_REASON_SPEAKER_ATTRIBUTION = "speaker_attribution"


@dataclass
class TranscriptResult:
    text: str
    confidence: float
    start_ms: int
    end_ms: int
    language: str = "de"
    segment_id: str | None = None
    requires_review: bool = False
    error: str | None = None
    # HEAR-061: actionable diagnostic code — see ASR_DIAG_* constants
    asr_diagnostic: str = ""
    # HEAR-152: separate ASR recognition confidence from speaker attribution confidence
    asr_confidence: float = 0.0
    speaker_confidence: float = 0.0
    # HEAR-152: reason code(s) explaining why review is flagged
    review_reason: str = ""


@dataclass
class TranscriptionService:
    """Offline ASR service backed by faster-whisper.

    Pass transcript_repo=None for unit testing without a DB connection.
    The model is loaded lazily on the first transcription call.
    """

    model_name: str = "TheChola/whisper-large-v3-turbo-german-faster-whisper"
    profile: str = "balanced"
    language: str = "de"
    transcript_repo: "TranscriptSegmentRepository | None" = None
    _model: Any = field(default=None, init=False, repr=False)
    # HEAR-160: thread-safety for background model warm-up
    _model_load_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _model_ready: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    @property
    def is_ready(self) -> bool:
        """True when the ASR model is loaded and ready (HEAR-160)."""
        return self._model_ready.is_set()

    def warmup(self) -> None:
        """Load the ASR model in a background daemon thread (non-blocking).

        Call at app startup so the model is ready before the first meeting,
        avoiding bad transcription quality on the first audio chunks (HEAR-160).
        Subsequent calls are no-ops when the model is already loaded.
        """
        if self._model is not None:
            self._model_ready.set()
            return
        t = threading.Thread(
            target=self._load_model_background,
            daemon=True,
            name="asr-warmup",
        )
        t.start()

    def _load_model_background(self) -> None:
        """Background thread: load WhisperModel and signal readiness (HEAR-160)."""
        with self._model_load_lock:
            if self._model is not None:
                self._model_ready.set()
                return
            try:
                from faster_whisper import WhisperModel  # type: ignore[import-untyped]

                opts = _PROFILES[self.profile]
                model_path, model_kwargs = _resolve_model_source(self.model_name)
                logger.info(
                    "ASR warm-up: loading model '%s' in background...", self.model_name
                )
                self._model = WhisperModel(
                    model_path,
                    device="cpu",
                    compute_type=opts["compute_type"],
                    **model_kwargs,
                )
                logger.info(
                    "ASR warm-up complete: model '%s' ready.", self.model_name
                )
            except Exception as exc:
                logger.error("ASR warm-up failed: %s", exc)
                # _model stays None; will be retried lazily on first audio chunk
            finally:
                # Always set so callers do not block forever even on failure
                self._model_ready.set()

    def active_profile(self) -> str:
        return self.profile

    def configure(self, *, model_name: str, language: str) -> None:
        """Apply ASR language/model updates; force lazy reload when model changes."""
        if self.model_name != model_name:
            self.model_name = model_name
            self._model = None
            self._model_ready.clear()
        self.language = language

    def set_profile(self, profile: str) -> None:
        if profile not in _PROFILES:
            raise ValueError(f"Unknown profile '{profile}'. Valid: {list(_PROFILES)}")
        self.profile = profile
        self._model = None  # force reload with new settings

    def transcribe_segment(
        self,
        audio_segment: "AudioSegment",
        meeting_id: str,
        speaker_name: str = "Unknown Speaker",
        confidence_score: float = 0.0,
    ) -> TranscriptResult:
        """Transcribe a single audio segment and persist to PostgreSQL.

        Returns a TranscriptResult. Segments with low ASR confidence are flagged
        for transcript quality review; segments with low speaker confidence are
        flagged for attribution review (HEAR-152).
        """
        try:
            text, language, asr_confidence = self._run_asr(audio_segment.samples.tolist())
        except AsrUnavailableError as exc:
            logger.warning("ASR unavailable: %s", exc)
            return TranscriptResult(
                text="",
                confidence=0.0,
                asr_confidence=0.0,
                speaker_confidence=confidence_score,
                start_ms=audio_segment.start_ms,
                end_ms=audio_segment.end_ms,
                error=str(exc),
                asr_diagnostic=ASR_DIAG_NOT_INSTALLED,
                requires_review=False,
                review_reason="",
            )
        except Exception as exc:
            logger.warning("ASR failed for segment [%d\u2013%d]: %s", audio_segment.start_ms, audio_segment.end_ms, exc)
            return TranscriptResult(
                text="",
                confidence=0.0,
                asr_confidence=0.0,
                speaker_confidence=confidence_score,
                start_ms=audio_segment.start_ms,
                end_ms=audio_segment.end_ms,
                error=str(exc),
                asr_diagnostic=ASR_DIAG_INFERENCE_ERROR,
                requires_review=True,
                review_reason=REVIEW_REASON_TRANSCRIPT_QUALITY,
            )

        asr_diagnostic = ASR_DIAG_EMPTY_RESULT if not text else ""

        # HEAR-152: independent review policy
        low_asr = asr_confidence < 0.65
        low_speaker = confidence_score < 0.65
        requires_review = low_asr or low_speaker
        if low_asr and low_speaker:
            review_reason = f"{REVIEW_REASON_TRANSCRIPT_QUALITY},{REVIEW_REASON_SPEAKER_ATTRIBUTION}"
        elif low_asr:
            review_reason = REVIEW_REASON_TRANSCRIPT_QUALITY
        elif low_speaker:
            review_reason = REVIEW_REASON_SPEAKER_ATTRIBUTION
        else:
            review_reason = ""

        result = TranscriptResult(
            text=text,
            confidence=confidence_score,  # backward-compat: confidence == speaker_confidence
            asr_confidence=asr_confidence,
            speaker_confidence=confidence_score,
            start_ms=audio_segment.start_ms,
            end_ms=audio_segment.end_ms,
            language=language,
            requires_review=requires_review,
            asr_diagnostic=asr_diagnostic,
            review_reason=review_reason,
        )

        if self.transcript_repo is not None and meeting_id:
            try:
                segment = self.transcript_repo.add(
                    meeting_id=meeting_id,
                    start_ms=audio_segment.start_ms,
                    end_ms=audio_segment.end_ms,
                    speaker_name=speaker_name,
                    text=text,
                    confidence_score=confidence_score,
                    asr_confidence=asr_confidence,
                    speaker_confidence=confidence_score,
                    is_silence=audio_segment.is_silence,
                )
                result.segment_id = segment.id
                # HEAR-168: commit each segment immediately so it survives session
                # teardown.  flush() alone leaves the transaction open; with
                # idle_in_transaction_session_timeout=30s the PG backend kills the
                # connection after meeting stop and rolls back all pending segments.
                self.transcript_repo._s.commit()
            except Exception as exc:
                logger.error("Failed to persist segment: %s", exc)

        return result

    def _run_asr(self, samples: list[float]) -> tuple[str, str, float]:
        """Run faster-whisper inference synchronously.

        Returns (text, detected_language, asr_confidence). Raises AsrUnavailableError when
        faster-whisper is not installed, and RuntimeError on model load failure.
        Returns ("", language, 0.0) when the model produces no speech segments.

        asr_confidence is derived from the mean avg_logprob of output segments
        using exp(avg_logprob), clamped to [0.0, 1.0] (HEAR-152).
        """
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        except ImportError as exc:
            raise AsrUnavailableError(
                "faster-whisper ist nicht installiert. "
                "Bitte 'pip install faster-whisper' ausf\u00fchren."
            ) from exc

        if self._model is None:
            with self._model_load_lock:
                if self._model is None:  # double-checked under lock
                    opts = _PROFILES[self.profile]
                    model_path, model_kwargs = _resolve_model_source(self.model_name)
                    try:
                        self._model = WhisperModel(
                            model_path,
                            device="cpu",
                            compute_type=opts["compute_type"],
                            **model_kwargs,
                        )
                    except Exception as exc:
                        # Keep _model None so next call retries
                        raise RuntimeError(
                            f"Whisper-Modell '{self.model_name}' konnte nicht geladen werden: {exc}"
                        ) from exc

        import numpy as np

        audio = np.asarray(samples, dtype=np.float32)
        beam_size = _PROFILES[self.profile]["beam_size"]

        # HEAR-095: resource telemetry at ASR inference boundaries
        res_before = _resource_snapshot()
        if res_before:
            logger.debug(
                "ASR inference start — cpu_pct=%.1f ram_mb=%.1f model=%s",
                res_before.get("cpu_pct", 0), res_before.get("ram_mb", 0), self.model_name,
            )

        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=beam_size,
        )

        collected = [(seg.text.strip(), getattr(seg, "avg_logprob", None)) for seg in segments if seg.text.strip()]
        texts = [t for t, _ in collected]
        logprobs = [lp for _, lp in collected if lp is not None]

        res_after = _resource_snapshot()
        if res_after:
            logger.debug(
                "ASR inference end   — cpu_pct=%.1f ram_mb=%.1f",
                res_after.get("cpu_pct", 0), res_after.get("ram_mb", 0),
            )

        # HEAR-152: derive ASR confidence from mean avg_logprob (exp-mapped, clamped)
        if logprobs:
            mean_logprob = sum(logprobs) / len(logprobs)
            asr_confidence = max(0.0, min(1.0, math.exp(mean_logprob)))
        else:
            asr_confidence = 0.0

        return " ".join(texts), info.language, asr_confidence


# ---------------------------------------------------------------------------
# HEAR-141: Adaptive transcription queue
# ---------------------------------------------------------------------------

_CPU_HIGH_THRESHOLD = 75.0   # percent — above this, batch segments before ASR
_CPU_FRAME_SCALE = 4          # combine this many segments when CPU is high


def get_cpu_load() -> float:
    """Return current system CPU load (0–100).  Returns 0.0 if psutil unavailable."""
    try:
        import psutil  # type: ignore[import-untyped]
        return psutil.cpu_percent(interval=None)
    except Exception:
        return 0.0


class AdaptiveTranscriptionQueue:
    """Queue that batches AudioSegments before ASR when CPU is busy (HEAR-141).

    Callers push segments via :meth:`push`.  When the queue decides to flush
    (based on CPU load), it calls *transcribe_fn* with the merged segment.

    Batching strategy:
    - CPU  < threshold (normal): flush every segment immediately (1×)
    - CPU >= threshold (busy):   accumulate up to *batch_size* segments first

    This reduces the ASR invocation rate under load, trading latency for
    reduced CPU contention between audio capture and ASR inference.
    """

    def __init__(
        self,
        transcribe_fn: "Callable[[AudioSegment], None]",
        cpu_high_threshold: float = _CPU_HIGH_THRESHOLD,
        batch_size: int = _CPU_FRAME_SCALE,
    ) -> None:
        self._transcribe = transcribe_fn
        self._cpu_threshold = cpu_high_threshold
        self._batch_size = batch_size
        self._buffer: "list[AudioSegment]" = []

    def push(self, segment: "AudioSegment") -> None:
        """Accept a new segment; flush to ASR when conditions are met."""
        self._buffer.append(segment)
        cpu = get_cpu_load()
        busy = cpu >= self._cpu_threshold
        if not busy or len(self._buffer) >= self._batch_size:
            self._flush()

    def flush_all(self) -> None:
        """Force-flush any buffered segments (e.g., on meeting stop)."""
        if self._buffer:
            self._flush()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush(self) -> None:
        if not self._buffer:
            return
        if len(self._buffer) == 1:
            merged = self._buffer[0]
        else:
            merged = _merge_segments(self._buffer)
        self._buffer = []
        try:
            self._transcribe(merged)
        except Exception as exc:
            logger.error("AdaptiveTranscriptionQueue: transcribe_fn raised: %s", exc)


def _merge_segments(segments: "list[AudioSegment]") -> "AudioSegment":
    """Concatenate multiple AudioSegments into a single merged segment.

    The merged segment spans from the first segment's start_ms to the last
    segment's end_ms.  Silence flag is True only when *all* segments are silent.
    """
    import numpy as np
    from ayehear.services.audio_capture import AudioSegment

    combined = np.concatenate([s.samples for s in segments], axis=0)
    rms = float(np.sqrt(np.mean(combined ** 2)))
    return AudioSegment(
        captured_at=segments[0].captured_at,
        start_ms=segments[0].start_ms,
        end_ms=segments[-1].end_ms,
        samples=combined,
        rms=rms,
        is_silence=all(s.is_silence for s in segments),
    )

