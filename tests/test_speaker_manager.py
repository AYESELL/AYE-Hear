"""Tests for SpeakerManager enrollment, scoring, and diarization pipeline (HEAR-012/014)."""
from __future__ import annotations

import math

import pytest

from ayehear.services.speaker_manager import (
    EnrollmentResult,
    SpeakerManager,
    SpeakerMatch,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# score_match — ADR-0003 thresholds
# ---------------------------------------------------------------------------


def test_score_match_high_confidence() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Anna", HIGH_CONFIDENCE_THRESHOLD)
    assert result.status == "high"
    assert result.requires_review is False


def test_score_match_medium_confidence() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Anna", 0.75)
    assert result.status == "medium"
    assert result.requires_review is True


def test_score_match_low_confidence() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Anna", 0.50)
    assert result.status == "low"
    assert result.requires_review is True
    # ADR-0003: low confidence must NOT assign a speaker name
    assert result.speaker_name == "Unknown Speaker"


def test_score_match_boundary_medium_lower() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Anna", MEDIUM_CONFIDENCE_THRESHOLD)
    assert result.status == "medium"


def test_score_match_boundary_high() -> None:
    sm = SpeakerManager()
    result = sm.score_match("Anna", HIGH_CONFIDENCE_THRESHOLD)
    assert result.status == "high"


# ---------------------------------------------------------------------------
# match_intro_to_participant — text-based matching
# ---------------------------------------------------------------------------


def test_match_intro_prefers_known_name() -> None:
    sm = SpeakerManager()
    result = sm.match_intro_to_participant(
        "Guten Morgen, ich bin Frau Schneider von AYE.",
        ["Frau Schneider", "Max Weber"],
    )
    assert result.speaker_name == "Frau Schneider"
    assert result.status in {"medium", "high"}


def test_match_intro_returns_unknown_without_candidates() -> None:
    sm = SpeakerManager()
    result = sm.match_intro_to_participant("Ich stelle mich spaeter vor.", [])
    assert result.speaker_name == "Unknown Speaker"
    assert result.status == "low"


def test_match_intro_returns_unknown_for_empty_text() -> None:
    sm = SpeakerManager()
    result = sm.match_intro_to_participant("", ["Anna"])
    assert result.speaker_name == "Unknown Speaker"


# ---------------------------------------------------------------------------
# enroll — stub path (no repository)
# ---------------------------------------------------------------------------


def test_enroll_without_repo_succeeds() -> None:
    sm = SpeakerManager()
    result = sm.enroll(
        participant_id="p-001",
        display_name="Anna",
        audio_samples=[0.1, 0.2, 0.3],
    )
    assert result.success is True
    assert result.display_name == "Anna"
    assert result.embedding_dim == 768


def test_enroll_empty_samples_produces_zero_vector() -> None:
    sm = SpeakerManager()
    result = sm.enroll(
        participant_id="p-002",
        display_name="Bob",
        audio_samples=[],
    )
    assert result.success is True
    assert result.embedding_dim == 768


# ---------------------------------------------------------------------------
# match_segment — stub path (no repository)
# ---------------------------------------------------------------------------


def test_match_segment_without_repo_returns_unknown() -> None:
    sm = SpeakerManager()
    result = sm.match_segment([0.1] * 768)
    assert result.speaker_name == "Unknown Speaker"
    assert result.status == "low"
    assert result.requires_review is True


# ---------------------------------------------------------------------------
# _cosine_similarity — unit vectors
# ---------------------------------------------------------------------------


def test_cosine_similarity_identical_vectors() -> None:
    vec = [1.0, 0.0, 0.0]
    score = SpeakerManager._cosine_similarity(vec, vec)
    assert abs(score - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors() -> None:
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    score = SpeakerManager._cosine_similarity(a, b)
    assert abs(score) < 1e-9


def test_cosine_similarity_zero_vector_returns_zero() -> None:
    score = SpeakerManager._cosine_similarity([0.0, 0.0], [1.0, 0.0])
    assert score == 0.0


def test_cosine_similarity_different_length_returns_zero() -> None:
    score = SpeakerManager._cosine_similarity([1.0], [1.0, 2.0])
    assert score == 0.0

