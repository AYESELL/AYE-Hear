"""Transcription pipeline integration (HEAR-013).

Wraps faster-whisper for offline ASR and persists segments to PostgreSQL
via TranscriptSegmentRepository. No external network calls are made at runtime.

Transcription profiles map to faster-whisper compute_type / beam_size settings:
  - fast   : int8, beam_size=1
  - balanced: float16 (or int8 on CPU), beam_size=3
  - accurate: float16, beam_size=5
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ayehear.services.audio_capture import AudioSegment
    from ayehear.storage.repositories import TranscriptSegmentRepository

logger = logging.getLogger(__name__)

_PROFILES: dict[str, dict] = {
    "fast":     {"compute_type": "int8",   "beam_size": 1},
    "balanced": {"compute_type": "int8",   "beam_size": 3},
    "accurate": {"compute_type": "float16","beam_size": 5},
}


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


@dataclass
class TranscriptionService:
    """Offline ASR service backed by faster-whisper.

    Pass transcript_repo=None for unit testing without a DB connection.
    The model is loaded lazily on the first transcription call.
    """

    model_name: str = "base"
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
        except Exception as exc:
            logger.warning("ASR failed for segment [%d–%d]: %s", audio_segment.start_ms, audio_segment.end_ms, exc)
            return TranscriptResult(
                text="",
                confidence=0.0,
                start_ms=audio_segment.start_ms,
                end_ms=audio_segment.end_ms,
                error=str(exc),
                requires_review=True,
            )

        requires_review = confidence_score < 0.65

        result = TranscriptResult(
            text=text,
            confidence=confidence_score,
            start_ms=audio_segment.start_ms,
            end_ms=audio_segment.end_ms,
            language=language,
            requires_review=requires_review,
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

        Returns (text, detected_language). Falls back to an empty string
        if the model is unavailable (no ML runtime installed).
        """
        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError:
            logger.warning("faster-whisper is not installed; returning empty transcript.")
            return "", self.language

        if self._model is None:
            opts = _PROFILES[self.profile]
            self._model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type=opts["compute_type"],
            )

        import numpy as np

        audio = np.asarray(samples, dtype=np.float32)
        beam_size = _PROFILES[self.profile]["beam_size"]

        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=beam_size,
        )

        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        return " ".join(texts), info.language
