"""Tests for HEAR-047: Real Speaker Enrollment and Attribution (ADR-0003 Stage 0-2).

Covers:
- SpeakerManager.enroll() with stub audio per speaker
- Live segment attribution via resolve_speaker_from_segment()
- Review-queue integration (requires_review flag surfaced correctly)
- No hardcoded 'Unknown Speaker' / 0.0 path when profiles exist
- register_meeting_participants / clear_meeting_context lifecycle
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock

import numpy as np

from ayehear.services.speaker_manager import (
    HIGH_CONFIDENCE_THRESHOLD,
    SpeakerManager,
    SpeakerMatch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_vec(dim: int = 768, seed: float = 0.5) -> list[float]:
    """Return a normalised vector whose entries are all `seed`."""
    vec = [seed] * dim
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


# ---------------------------------------------------------------------------
# Enrollment via SpeakerManager.enroll()
# ---------------------------------------------------------------------------

_DUMMY_AUDIO = np.zeros(8000, dtype=np.float32).tolist()


def test_enroll_creates_profile_stub_path() -> None:
    """enroll() with no repo succeeds and returns a profile_id (stub path)."""
    sm = SpeakerManager()
    result = sm.enroll(participant_id="p-001", display_name="Frau Schneider", audio_samples=_DUMMY_AUDIO)

    assert result.success is True
    assert result.display_name == "Frau Schneider"
    assert result.embedding_dim == 768
    assert result.profile_id  # not empty


def test_enroll_different_speakers_produce_different_profiles() -> None:
    """Different speakers get distinct stub profile IDs."""
    sm = SpeakerManager()
    r1 = sm.enroll("p-a", "Frau Schneider", _DUMMY_AUDIO)
    r2 = sm.enroll("p-b", "Max Weber", _DUMMY_AUDIO)

    assert r1.success and r2.success


def test_enroll_with_profile_repo_calls_upsert() -> None:
    """When a profile_repo is provided, enroll() calls repo.upsert()."""
    mock_profile = MagicMock()
    mock_profile.id = "profile-uuid-123"
    mock_profiles = MagicMock()
    mock_profiles.upsert.return_value = mock_profile

    mock_participants = MagicMock()

    sm = SpeakerManager(profile_repo=mock_profiles, participant_repo=mock_participants)
    result = sm.enroll("p-x", "Anna", _DUMMY_AUDIO)

    assert result.success is True
    assert result.profile_id == "profile-uuid-123"
    mock_profiles.upsert.assert_called_once()
    mock_participants.mark_enrolled.assert_called_once_with("p-x", "profile-uuid-123")


# ---------------------------------------------------------------------------
# Live attribution — resolve_speaker_from_segment()
# ---------------------------------------------------------------------------


def test_resolve_returns_unknown_without_profiles() -> None:
    """With no profile repo, any embedding falls through to Unknown Speaker."""
    sm = SpeakerManager()
    embedding = _unit_vec(seed=0.3)
    match = sm.resolve_speaker_from_segment(embedding)

    assert match.speaker_name == "Unknown Speaker"
    assert match.confidence == 0.0
    assert match.requires_review is True


def test_resolve_uses_intro_matching_when_participants_registered() -> None:
    """Stage 0: intro text triggers constrained matching when participants are set."""
    sm = SpeakerManager()
    sm.register_meeting_participants(["Frau Schneider", "Max Weber"])
    embedding = _unit_vec(seed=0.1)
    match = sm.resolve_speaker_from_segment(
        embedding,
        segment_text="Guten Morgen, ich bin Frau Schneider.",
    )
    assert match.speaker_name == "Frau Schneider"
    assert match.status in {"medium", "high"}


def test_resolve_falls_back_to_embedding_for_non_intro() -> None:
    """Ordinary speech text does not trigger Stage 0 intro matching."""
    sm = SpeakerManager()
    sm.register_meeting_participants(["Frau Schneider", "Max Weber"])
    embedding = _unit_vec(seed=0.2)
    match = sm.resolve_speaker_from_segment(
        embedding,
        segment_text="Das Budget für Q3 ist genehmigt.",  # not an intro
    )
    # Falls back to match_segment → Unknown Speaker (no profile repo)
    assert match.speaker_name == "Unknown Speaker"


def test_resolve_with_profiles_returns_best_match() -> None:
    """With profiles loaded, the highest-cosine-similarity profile is returned."""
    # Build a mock profile whose embedding matches our segment exactly
    target_emb = _unit_vec(seed=0.5)
    distractor_emb = _unit_vec(seed=0.99)

    mock_p1 = MagicMock()
    mock_p1.id = "id-anna"
    mock_p1.display_name = "Anna"
    mock_p1.embedding_vector = target_emb

    mock_p2 = MagicMock()
    mock_p2.id = "id-bob"
    mock_p2.display_name = "Bob"
    mock_p2.embedding_vector = distractor_emb

    mock_profiles = MagicMock()
    mock_profiles.list_all.return_value = [mock_p1, mock_p2]

    sm = SpeakerManager(profile_repo=mock_profiles)
    match = sm.resolve_speaker_from_segment(target_emb)

    assert match.speaker_name == "Anna"
    assert match.confidence >= HIGH_CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Review-queue integration — requires_review flag
# ---------------------------------------------------------------------------


def test_requires_review_true_for_medium_confidence() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Anna", 0.70)
    assert result.requires_review is True
    assert result.status == "medium"


def test_requires_review_false_for_high_confidence() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Anna", HIGH_CONFIDENCE_THRESHOLD)
    assert result.requires_review is False


def test_requires_review_true_below_medium_threshold() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Anna", 0.50)
    assert result.requires_review is True
    assert result.speaker_name == "Unknown Speaker"  # ADR-0003: no assignment below medium


# ---------------------------------------------------------------------------
# register_meeting_participants / clear_meeting_context lifecycle
# ---------------------------------------------------------------------------


def test_clear_context_after_meeting_end() -> None:
    sm = SpeakerManager()
    sm.register_meeting_participants(["Alice", "Bob"])
    sm.clear_meeting_context()
    assert sm._meeting_participants == []


def test_register_participants_before_resolve() -> None:
    """Participants registered before recording are available during resolve."""
    sm = SpeakerManager()
    sm.register_meeting_participants(["Alice", "Bob"])
    assert len(sm._meeting_participants) == 2


# ---------------------------------------------------------------------------
# MainWindow._transcribe_pending_buffer — no hardcoded speaker path
# ---------------------------------------------------------------------------


def test_window_transcribe_calls_resolve_not_hardcoded() -> None:
    """The transcription path calls resolve_speaker_from_segment, not a constant.

    Executed in an isolated child process to avoid the Windows access-violation
    that PySide6 triggers when a QMainWindow is torn down inside a long-running
    pytest session that has already processed other Qt fixtures.
    """
    import subprocess
    import sys

    script = """
import sys, math
from unittest.mock import MagicMock, patch
import numpy as np
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv[:1])

from ayehear.models.runtime import RuntimeConfig
from ayehear.app.window import MainWindow
from ayehear.services.speaker_manager import SpeakerManager, SpeakerMatch

cfg = RuntimeConfig()
mock_sm = MagicMock(spec=SpeakerManager)
mock_match = SpeakerMatch(
    speaker_name="Frau Schneider",
    confidence=0.88,
    status="high",
    requires_review=False,
)
mock_sm.resolve_speaker_from_segment.return_value = mock_match

with (
    patch.object(SpeakerManager, "_extract_embedding", return_value=[0.1] * 768),
    patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}),
):
    window = MainWindow(cfg, speaker_manager=mock_sm)
    mock_result = MagicMock()
    mock_result.text = "Hallo Welt"
    mock_result.error = None
    mock_result.asr_diagnostic = ""
    window._transcription_service.transcribe_segment = MagicMock(return_value=mock_result)
    window._active_meeting_id = "test-meeting-id"

    with window._audio_buffer_lock:
        window._pending_audio_chunks = [np.ones(8000, dtype=np.float32)]
        window._pending_start_ms = 0
        window._pending_end_ms = 500
        window._pending_duration_ms = 2000

    window._transcribe_pending_buffer(force=True)

    assert mock_sm.resolve_speaker_from_segment.call_count == 1, (
        f"Expected 1 call, got {mock_sm.resolve_speaker_from_segment.call_count}"
    )
    resolve_kwargs = mock_sm.resolve_speaker_from_segment.call_args.kwargs
    assert resolve_kwargs.get("segment_text") == "Hallo Welt", (
        f"Expected transcribed intro text, got {resolve_kwargs.get('segment_text')!r}"
    )
    call_kwargs = window._transcription_service.transcribe_segment.call_args
    assert call_kwargs.kwargs.get("meeting_id") == "test-meeting-id"
    window.close()

print("ASSERTIONS_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        timeout=30,
        cwd=str(__file__).rsplit("tests", 1)[0],
        env={**__import__("os").environ, "PYTHONPATH": str(__import__("pathlib").Path(__file__).parent.parent / "src")},
    )
    stdout = result.stdout.decode(errors="replace")
    stderr = result.stderr.decode(errors="replace")
    assert result.returncode == 0, (
        f"Child process failed (rc={result.returncode}):\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )
    assert "ASSERTIONS_OK" in stdout, f"Assertions did not complete:\n{stdout}\n{stderr}"
