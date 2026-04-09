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
    """When faster-whisper is unavailable the service returns empty text, no error."""
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    with patch.dict("sys.modules", {"faster_whisper": None}):
        result = svc.transcribe_segment(segment, meeting_id="m-001", speaker_name="Anna", confidence_score=0.9)

    assert isinstance(result, TranscriptResult)
    assert result.text == ""
    assert result.error is None


def test_transcribe_segment_low_confidence_flagged() -> None:
    svc = TranscriptionService()
    segment = FakeAudioSegment(samples=np.zeros(512, dtype=np.float32))

    with patch.dict("sys.modules", {"faster_whisper": None}):
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
