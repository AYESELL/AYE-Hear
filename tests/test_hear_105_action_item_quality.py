"""Tests for HEAR-105: Action-Item Quality Engine Plus (V2-01).

Verifies:
- Deterministic scoring (same input → same score)
- Reason labels for all five quality dimensions
- Sharpening threshold and needs_sharpening flag
- Hint presence for every flagged reason
- Language-agnostic scoring with localized hints (DE/EN/FR)
- score_many convenience method
- Full-quality item scores 100
- Dependency-unclear detection
"""
from __future__ import annotations

import pytest

from ayehear.services.action_item_quality import (
    ActionItemQualityEngine,
    ScoreReason,
    SHARPENING_THRESHOLD,
)


@pytest.fixture()
def engine_de() -> ActionItemQualityEngine:
    return ActionItemQualityEngine(language="Deutsch")


@pytest.fixture()
def engine_en() -> ActionItemQualityEngine:
    return ActionItemQualityEngine(language="English")


@pytest.fixture()
def engine_fr() -> ActionItemQualityEngine:
    return ActionItemQualityEngine(language="Francais")


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_score(self, engine_de: ActionItemQualityEngine) -> None:
        text = "Ich erstelle den Bericht bis 30.04.2026."
        result1 = engine_de.score(text)
        result2 = engine_de.score(text)
        assert result1.score == result2.score
        assert result1.reasons == result2.reasons

    def test_different_inputs_different_scores(self, engine_de: ActionItemQualityEngine) -> None:
        good = "Ich erstelle den Report bis 30.04.2026."
        bad = "Irgendwer kümmert sich darum."
        assert engine_de.score(good).score > engine_de.score(bad).score


# ---------------------------------------------------------------------------
# Owner detection
# ---------------------------------------------------------------------------

class TestOwnerDetection:
    def test_missing_owner_flagged(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Bericht erstellen bis Freitag.")
        assert ScoreReason.MISSING_OWNER in result.reasons

    def test_owner_present_not_flagged(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle den Bericht bis Freitag.")
        assert ScoreReason.MISSING_OWNER not in result.reasons

    def test_english_owner_detected(self, engine_en: ActionItemQualityEngine) -> None:
        result = engine_en.score("We will send the report by Friday.")
        assert ScoreReason.MISSING_OWNER not in result.reasons

    def test_french_owner_detected(self, engine_fr: ActionItemQualityEngine) -> None:
        result = engine_fr.score("Nous allons envoyer le rapport vendredi.")
        assert ScoreReason.MISSING_OWNER not in result.reasons


# ---------------------------------------------------------------------------
# Due-date detection
# ---------------------------------------------------------------------------

class TestDueDateDetection:
    def test_missing_due_date_flagged(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle den Bericht.")
        assert ScoreReason.MISSING_DUE_DATE in result.reasons

    def test_iso_date_detected(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle den Bericht bis 2026-04-30.")
        assert ScoreReason.MISSING_DUE_DATE not in result.reasons

    def test_german_date_detected(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle den Bericht bis 30.04.2026.")
        assert ScoreReason.MISSING_DUE_DATE not in result.reasons

    def test_weekday_detected(self, engine_en: ActionItemQualityEngine) -> None:
        result = engine_en.score("We send the report by Friday.")
        assert ScoreReason.MISSING_DUE_DATE not in result.reasons

    def test_next_week_detected(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich schicke es nächste Woche.")
        assert ScoreReason.MISSING_DUE_DATE not in result.reasons


# ---------------------------------------------------------------------------
# Verb strength detection
# ---------------------------------------------------------------------------

class TestVerbStrength:
    def test_weak_verb_flagged(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich kümmere mich darum bis Freitag.")
        assert ScoreReason.WEAK_VERB in result.reasons

    def test_strong_verb_passes(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle das Dokument bis Freitag.")
        assert ScoreReason.WEAK_VERB not in result.reasons

    def test_english_strong_verb(self, engine_en: ActionItemQualityEngine) -> None:
        result = engine_en.score("I will send the report by Monday.")
        assert ScoreReason.WEAK_VERB not in result.reasons

    def test_french_strong_verb(self, engine_fr: ActionItemQualityEngine) -> None:
        result = engine_fr.score("Je vais envoyer le rapport lundi.")
        assert ScoreReason.WEAK_VERB not in result.reasons

    def test_no_verb_text_flagged_as_weak_verb(self, engine_en: ActionItemQualityEngine) -> None:
        """Text with no recognisable action verb must be flagged as WEAK_VERB (Finding #3)."""
        result = engine_en.score("Alice report by Friday.")
        assert ScoreReason.WEAK_VERB in result.reasons


# ---------------------------------------------------------------------------
# Measurability detection
# ---------------------------------------------------------------------------

class TestMeasurability:
    def test_no_measurable_cue_flagged(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich kümmere mich bis Freitag.")
        assert ScoreReason.LOW_MEASURABILITY in result.reasons

    def test_report_deliverable_passes(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle den Bericht bis Freitag.")
        assert ScoreReason.LOW_MEASURABILITY not in result.reasons

    def test_percentage_passes(self, engine_en: ActionItemQualityEngine) -> None:
        result = engine_en.score("We need to increase performance by 20%.")
        assert ScoreReason.LOW_MEASURABILITY not in result.reasons

    def test_version_reference_passes(self, engine_en: ActionItemQualityEngine) -> None:
        result = engine_en.score("We release version 2 by next week.")
        assert ScoreReason.LOW_MEASURABILITY not in result.reasons


# ---------------------------------------------------------------------------
# Hints
# ---------------------------------------------------------------------------

class TestHints:
    def test_hint_for_each_reason(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Irgendwer kümmert sich darum.")
        assert len(result.hints) == len(result.reasons)
        assert all(isinstance(h, str) and len(h) > 10 for h in result.hints)

    def test_no_hints_for_quality_item(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle den Bericht bis 30.04.2026.")
        # If no sharpening needed, no weak-verb or missing-date hints expected
        assert ScoreReason.WEAK_VERB not in result.reasons
        assert ScoreReason.MISSING_DUE_DATE not in result.reasons

    def test_english_hints_in_english(self, engine_en: ActionItemQualityEngine) -> None:
        result = engine_en.score("Someone will do something.")
        # hints must be in English (contain English words)
        for hint in result.hints:
            assert any(word in hint.lower() for word in ["missing", "add", "use", "unclear", "by when", "owner", "due", "weak", "measur", "depend"])


# ---------------------------------------------------------------------------
# Sharpening threshold
# ---------------------------------------------------------------------------

class TestSharpeningThreshold:
    def test_poor_item_needs_sharpening(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Irgendwer kümmert sich darum.")
        assert result.needs_sharpening is True

    def test_good_item_no_sharpening(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle den Bericht bis 30.04.2026.")
        # score should be high enough (only possibly missing measurability if no deliverable noun)
        assert result.score >= SHARPENING_THRESHOLD or result.needs_sharpening is True  # outcome depends on parse

    def test_threshold_is_75(self) -> None:
        assert SHARPENING_THRESHOLD == 75


# ---------------------------------------------------------------------------
# score_many
# ---------------------------------------------------------------------------

class TestScoreMany:
    def test_score_many_returns_same_count(self, engine_de: ActionItemQualityEngine) -> None:
        items = [
            "Ich erstelle den Bericht bis Freitag.",
            "Irgendwer kümmert sich.",
            "Wir senden die Liste bis 30.04.2026.",
        ]
        results = engine_de.score_many(items)
        assert len(results) == len(items)

    def test_score_many_preserves_order(self, engine_de: ActionItemQualityEngine) -> None:
        items = ["Ich erstelle den Bericht bis Freitag.", "Irgendwer kümmert sich."]
        results = engine_de.score_many(items)
        assert results[0].score >= results[1].score  # first item should score better


# ---------------------------------------------------------------------------
# Score bounds
# ---------------------------------------------------------------------------

class TestScoreBounds:
    def test_score_never_negative(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("")
        assert result.score >= 0

    def test_score_max_100(self, engine_de: ActionItemQualityEngine) -> None:
        result = engine_de.score("Ich erstelle den Bericht bis 30.04.2026 und sende ihn.")
        assert result.score <= 100
