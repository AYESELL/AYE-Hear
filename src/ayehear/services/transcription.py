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
import sys
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


@dataclass
class TranscriptionService:
    """Offline ASR service backed by faster-whisper.

    Pass transcript_repo=None for unit testing without a DB connection.
    The model is loaded lazily on the first transcription call.
    """

    model_name: str = "small"
    profile: str = "balanced"
    language: str = "de"
    transcript_repo: "TranscriptSegmentRepository | None" = None
    _model: Any = field(default=None, init=False, repr=False)

    def active_profile(self) -> str:
        return self.profile

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

        Returns a TranscriptResult. Segments with confidence < 0.65 are flagged
        as requiring manual review.
        """
        try:
            text, language = self._run_asr(audio_segment.samples.tolist())
        except AsrUnavailableError as exc:
            logger.warning("ASR unavailable: %s", exc)
            return TranscriptResult(
                text="",
                confidence=0.0,
                start_ms=audio_segment.start_ms,
                end_ms=audio_segment.end_ms,
                error=str(exc),
                asr_diagnostic=ASR_DIAG_NOT_INSTALLED,
                requires_review=False,
            )
        except Exception as exc:
            logger.warning("ASR failed for segment [%d\u2013%d]: %s", audio_segment.start_ms, audio_segment.end_ms, exc)
            return TranscriptResult(
                text="",
                confidence=0.0,
                start_ms=audio_segment.start_ms,
                end_ms=audio_segment.end_ms,
                error=str(exc),
                asr_diagnostic=ASR_DIAG_INFERENCE_ERROR,
                requires_review=True,
            )

        requires_review = confidence_score < 0.65
        asr_diagnostic = ASR_DIAG_EMPTY_RESULT if not text else ""

        result = TranscriptResult(
            text=text,
            confidence=confidence_score,
            start_ms=audio_segment.start_ms,
            end_ms=audio_segment.end_ms,
            language=language,
            requires_review=requires_review,
            asr_diagnostic=asr_diagnostic,
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
                    is_silence=audio_segment.is_silence,
                )
                result.segment_id = segment.id
            except Exception as exc:
                logger.error("Failed to persist segment: %s", exc)

        return result

    def _run_asr(self, samples: list[float]) -> tuple[str, str]:
        """Run faster-whisper inference synchronously.

        Returns (text, detected_language). Raises AsrUnavailableError when
        faster-whisper is not installed, and RuntimeError on model load failure.
        Returns ("", language) when the model produces no speech segments.
        """
        try:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        except ImportError as exc:
            raise AsrUnavailableError(
                "faster-whisper ist nicht installiert. "
                "Bitte 'pip install faster-whisper' ausf\u00fchren."
            ) from exc

        if self._model is None:
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

        texts = [seg.text.strip() for seg in segments if seg.text.strip()]

        res_after = _resource_snapshot()
        if res_after:
            logger.debug(
                "ASR inference end   — cpu_pct=%.1f ram_mb=%.1f",
                res_after.get("cpu_pct", 0), res_after.get("ram_mb", 0),
            )

        return " ".join(texts), info.language
