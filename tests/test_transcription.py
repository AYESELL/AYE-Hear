"""Tests for TranscriptionService (HEAR-013).

All tests run without a real faster-whisper model or database.
The audio capture dependency is mocked with a dataclass stand-in.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ayehear.services.transcription import TranscriptionService, TranscriptResult


@dataclass
class FakeAudioSegment:
    samples: np.ndarray
    start_ms: int = 0
    end_ms: int = 1000
    rms: float = 0.05
    is_silence: bool = False


# ---------------------------------------------------------------------------
# active_profile / set_profile
# ---------------------------------------------------------------------------


def test_active_profile_default() -> None:
    svc = TranscriptionService()
    assert svc.active_profile() == "balanced"


def test_set_profile_changes_profile() -> None:
    svc = TranscriptionService()
    svc.set_profile("fast")
    assert svc.active_profile() == "fast"


def test_set_profile_rejects_unknown() -> None:
    svc = TranscriptionService()
    with pytest.raises(ValueError, match="Unknown profile"):
        svc.set_profile("turbo")


# ---------------------------------------------------------------------------
# transcribe_segment — faster-whisper not installed path
# ---------------------------------------------------------------------------


def test_transcribe_segment_returns_result_without_whisper() -> None:
    """When faster-whisper is unavailable, service returns empty text with not_installed diagnostic."""
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    with patch.dict("sys.modules", {"faster_whisper": None}):
        result = svc.transcribe_segment(segment, meeting_id="m-001", speaker_name="Anna", confidence_score=0.9)

    assert isinstance(result, TranscriptResult)
    assert result.text == ""
    # HEAR-061: not_installed diagnostic and error message must be set
    assert result.asr_diagnostic == "not_installed"
    assert result.error is not None
    assert "faster-whisper" in result.error.lower() or "installiert" in result.error.lower()


def test_transcribe_segment_low_confidence_flagged() -> None:
    """Low confidence on actual inference result flags requires_review.

    Note: when faster-whisper is not installed (not_installed diagnostic),
    requires_review is False because there is no transcript to review.
    """
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    mock_seg = MagicMock()
    mock_seg.text = ""  # empty output from model
    mock_info = MagicMock()
    mock_info.language = "de"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    mock_whisper = MagicMock()
    mock_whisper.WhisperModel.return_value = mock_model

    with patch.dict("sys.modules", {"faster_whisper": mock_whisper}):
        result = svc.transcribe_segment(segment, meeting_id="m-001", speaker_name="?", confidence_score=0.40)

    assert result.requires_review is True


def test_transcribe_segment_high_confidence_not_flagged() -> None:
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    with patch.dict("sys.modules", {"faster_whisper": None}):
        result = svc.transcribe_segment(segment, meeting_id="m-001", speaker_name="Anna", confidence_score=0.90)

    assert result.requires_review is False


# ---------------------------------------------------------------------------
# transcribe_segment — with mock faster-whisper
# ---------------------------------------------------------------------------


def test_transcribe_segment_with_mock_whisper() -> None:
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    mock_seg = MagicMock()
    mock_seg.text = "Guten Morgen"
    mock_info = MagicMock()
    mock_info.language = "de"

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    mock_whisper_module = MagicMock()
    mock_whisper_module.WhisperModel.return_value = mock_model

    with patch.dict("sys.modules", {"faster_whisper": mock_whisper_module}):
        result = svc.transcribe_segment(segment, meeting_id="m-002", speaker_name="Anna", confidence_score=0.92)

    assert result.text == "Guten Morgen"
    assert result.language == "de"
    assert result.error is None
    assert result.requires_review is False


def test_transcribe_segment_persists_to_repo() -> None:
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    mock_repo = MagicMock()
    mock_repo.add.return_value = MagicMock(id="seg-1")
    svc.transcript_repo = mock_repo

    mock_seg = MagicMock()
    mock_seg.text = "Hello"
    mock_info = MagicMock()
    mock_info.language = "de"

    mock_model_instance = MagicMock()
    mock_model_instance.transcribe.return_value = ([mock_seg], mock_info)

    mock_whisper = MagicMock()
    mock_whisper.WhisperModel.return_value = mock_model_instance

    with patch.dict("sys.modules", {"faster_whisper": mock_whisper}):
        result = svc.transcribe_segment(segment, meeting_id="m-003", speaker_name="Anna", confidence_score=0.88)

    mock_repo.add.assert_called_once()
    assert result.segment_id == "seg-1"


# ---------------------------------------------------------------------------
# HEAR-061: asr_diagnostic codes
# ---------------------------------------------------------------------------


def test_asr_diagnostic_not_installed_when_faster_whisper_missing() -> None:
    """asr_diagnostic must be 'not_installed' when faster-whisper is unavailable."""
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    with patch.dict("sys.modules", {"faster_whisper": None}):
        result = svc.transcribe_segment(segment, meeting_id="m-diag-01", speaker_name="Anna", confidence_score=0.9)

    assert result.asr_diagnostic == "not_installed"
    assert result.error is not None


def test_asr_diagnostic_empty_result_when_whisper_returns_no_segments() -> None:
    """asr_diagnostic must be 'empty_result' when model produces no speech text."""
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    mock_info = MagicMock()
    mock_info.language = "de"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], mock_info)  # empty segments

    mock_whisper = MagicMock()
    mock_whisper.WhisperModel.return_value = mock_model

    with patch.dict("sys.modules", {"faster_whisper": mock_whisper}):
        result = svc.transcribe_segment(segment, meeting_id="m-diag-02", speaker_name="Anna", confidence_score=0.9)

    assert result.text == ""
    assert result.asr_diagnostic == "empty_result"
    assert result.error is None


def test_asr_diagnostic_empty_for_successful_transcription() -> None:
    """asr_diagnostic must be empty string when transcription succeeds."""
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    mock_seg = MagicMock()
    mock_seg.text = "Guten Morgen"
    mock_info = MagicMock()
    mock_info.language = "de"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    mock_whisper = MagicMock()
    mock_whisper.WhisperModel.return_value = mock_model

    with patch.dict("sys.modules", {"faster_whisper": mock_whisper}):
        result = svc.transcribe_segment(segment, meeting_id="m-diag-03", speaker_name="Anna", confidence_score=0.9)

    assert result.text == "Guten Morgen"
    assert result.asr_diagnostic == ""
    assert result.error is None


def test_asr_diagnostic_inference_error_when_transcribe_raises() -> None:
    """asr_diagnostic must be 'inference_error' when transcribe() raises."""
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("CUDA out of memory")

    mock_whisper = MagicMock()
    mock_whisper.WhisperModel.return_value = mock_model

    with patch.dict("sys.modules", {"faster_whisper": mock_whisper}):
        result = svc.transcribe_segment(segment, meeting_id="m-diag-04", speaker_name="Anna", confidence_score=0.9)

    assert result.text == ""
    assert result.asr_diagnostic == "inference_error"
    assert result.error is not None
    assert "CUDA" in result.error


def test_asr_diagnostic_not_installed_does_not_require_review() -> None:
    """not_installed diagnostic must NOT set requires_review (it's a config issue, not data)."""
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    with patch.dict("sys.modules", {"faster_whisper": None}):
        result = svc.transcribe_segment(segment, meeting_id="m-diag-05", speaker_name="Anna", confidence_score=0.9)

    assert result.requires_review is False


def test_run_asr_raises_asr_unavailable_error_when_not_installed() -> None:
    """_run_asr must raise AsrUnavailableError (not return empty) when import fails."""
    from ayehear.services.transcription import AsrUnavailableError

    svc = TranscriptionService()

    with patch.dict("sys.modules", {"faster_whisper": None}):
        with pytest.raises(AsrUnavailableError):
            svc._run_asr([0.0] * 512)

