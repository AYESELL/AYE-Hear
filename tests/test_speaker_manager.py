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


def test_match_intro_handles_salutation_and_company_display_name() -> None:
    sm = SpeakerManager()
    result = sm.match_intro_to_participant(
        "Guten Morgen, ich bin Frau Schneider von AYE.",
        ["Frau Schneider | AYE", "Max Weber | Customer GmbH"],
    )

    assert result.speaker_name == "Frau Schneider | AYE"
    assert result.status in {"medium", "high"}


def test_match_intro_rejects_first_name_only_when_names_are_ambiguous() -> None:
    sm = SpeakerManager()
    result = sm.match_intro_to_participant(
        "Ich bin Max.",
        ["Max Weber", "Max Müller"],
    )

    assert result.speaker_name == "Unknown Speaker"
    assert result.status == "low"


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


# ---------------------------------------------------------------------------
# Stage 0: constrained pipeline matching (HEAR-021)
# ---------------------------------------------------------------------------


def test_register_meeting_participants_stores_names() -> None:
    sm = SpeakerManager()
    sm.register_meeting_participants(["Frau Schneider", "Max Weber"])
    assert sm._meeting_participants == ["Frau Schneider", "Max Weber"]


def test_register_meeting_participants_replaces_previous_list() -> None:
    sm = SpeakerManager()
    sm.register_meeting_participants(["Alice"])
    sm.register_meeting_participants(["Bob", "Carol"])
    assert sm._meeting_participants == ["Bob", "Carol"]


def test_clear_meeting_context_resets_list() -> None:
    sm = SpeakerManager()
    sm.register_meeting_participants(["Alice"])
    sm.clear_meeting_context()
    assert sm._meeting_participants == []


# --- _looks_like_intro ---


def test_looks_like_intro_german_patterns() -> None:
    assert SpeakerManager._looks_like_intro("Guten Morgen, ich bin Frau Schneider.")
    assert SpeakerManager._looks_like_intro("Mein Name ist Max Weber.")
    assert SpeakerManager._looks_like_intro("Ich heisse Anna.")
    assert SpeakerManager._looks_like_intro("Ich heiße Klaus.")
    assert SpeakerManager._looks_like_intro("Ich stelle mich kurz vor.")
    assert SpeakerManager._looks_like_intro("Hier ist Thomas vom Support.")
    assert SpeakerManager._looks_like_intro("Hier spricht Frau Meier.")


def test_looks_like_intro_english_patterns() -> None:
    assert SpeakerManager._looks_like_intro("My name is John Smith.")
    assert SpeakerManager._looks_like_intro("I am Anna from AYE.")
    assert SpeakerManager._looks_like_intro("I'm the product lead.")
    assert SpeakerManager._looks_like_intro("This is Maria speaking.")


def test_looks_like_intro_rejects_ordinary_speech() -> None:
    assert not SpeakerManager._looks_like_intro("Das Budget wurde genehmigt.")
    assert not SpeakerManager._looks_like_intro("Wann ist der nächste Termin?")
    assert not SpeakerManager._looks_like_intro("Nächster Punkt auf der Agenda.")
    assert not SpeakerManager._looks_like_intro("")


def test_looks_like_intro_case_insensitive() -> None:
    assert SpeakerManager._looks_like_intro("MEIN NAME IST Anna.")
    assert SpeakerManager._looks_like_intro("ICH BIN der Entwickler.")


# --- resolve_speaker_from_segment ---


def test_resolve_prefers_constrained_intro_when_confident() -> None:
    sm = SpeakerManager()
    sm.register_meeting_participants(["Frau Schneider", "Max Weber"])

    result = sm.resolve_speaker_from_segment(
        segment_embedding=[0.0] * 768,
        segment_text="Guten Morgen, ich bin Frau Schneider.",
    )
    assert result.speaker_name == "Frau Schneider"
    assert result.status in ("medium", "high")


def test_resolve_falls_back_to_embedding_for_non_intro_text() -> None:
    """Ordinary speech → embedding path → no profiles loaded → Unknown Speaker."""
    sm = SpeakerManager()
    sm.register_meeting_participants(["Frau Schneider"])

    result = sm.resolve_speaker_from_segment(
        segment_embedding=[0.1] * 768,
        segment_text="Das Budget ist bereits genehmigt.",
    )
    # no profiles in repo → Unknown Speaker from embedding path
    assert result.speaker_name == "Unknown Speaker"


def test_resolve_falls_back_when_no_participants_registered() -> None:
    """Intro text with no participant list → skip Stage 0 → embedding → Unknown."""
    sm = SpeakerManager()
    # No register_meeting_participants() call

    result = sm.resolve_speaker_from_segment(
        segment_embedding=[0.0] * 768,
        segment_text="Ich bin Anna.",
    )
    assert result.speaker_name == "Unknown Speaker"


def test_resolve_low_confidence_intro_falls_back_to_embedding() -> None:
    """Intro that doesn't match any participant → low confidence → fall back to embedding."""
    sm = SpeakerManager()
    sm.register_meeting_participants(["Frau Schneider", "Max Weber"])

    # The text is an intro but 'Herr Unbekannt' is not in participant list
    result = sm.resolve_speaker_from_segment(
        segment_embedding=[0.0] * 768,
        segment_text="Ich bin Herr Unbekannt vom Finanzamt.",
    )
    # intro match confidence is low → falls back to embedding → no profiles → Unknown
    assert result.speaker_name == "Unknown Speaker"
    assert result.requires_review is True


def test_resolve_unknown_explicitly_set_when_no_match() -> None:
    """Whether via intro or embedding path, Unknown Speaker is always explicit."""
    sm = SpeakerManager()
    result = sm.resolve_speaker_from_segment(
        segment_embedding=[0.0] * 768,
        segment_text="",
    )
    assert result.speaker_name == "Unknown Speaker"
    assert result.status == "low"
    assert result.requires_review is True


# --- ambiguous-name handling ---


def test_resolve_ambiguous_name_selects_best_match() -> None:
    """When two participants have similar names, the closer match wins."""
    sm = SpeakerManager()
    sm.register_meeting_participants(["Anna Schneider", "Andreas Schneider"])

    # "ich bin Anna" should match "Anna Schneider" over "Andreas Schneider"
    result = sm.resolve_speaker_from_segment(
        segment_embedding=[0.0] * 768,
        segment_text="Ich bin Anna Schneider.",
    )
    assert result.speaker_name == "Anna Schneider"


def test_resolve_uses_full_name_when_available() -> None:
    sm = SpeakerManager()
    sm.register_meeting_participants(["Max Weber", "Max Müller"])

    result = sm.resolve_speaker_from_segment(
        segment_embedding=[0.0] * 768,
        segment_text="Mein Name ist Max Müller.",
    )
    assert result.speaker_name == "Max Müller"

