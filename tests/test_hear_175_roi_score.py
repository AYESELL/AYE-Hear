"""Tests for HEAR-175: V2-04 Meeting ROI Score (deterministic, offline)."""
from __future__ import annotations

import pytest

from ayehear.services.meeting_score import calculate_roi_score


class TestCalculateRoiScoreEmpty:
    def test_empty_dict_returns_zero(self):
        result = calculate_roi_score({})
        assert result["score"] == 0

    def test_empty_dict_no_error(self):
        result = calculate_roi_score({})
        assert "score" in result
        assert "drivers_positive" in result
        assert "drivers_negative" in result
        assert "components" in result

    def test_none_input_handled(self):
        # None should be treated as empty dict
        result = calculate_roi_score(None)  # type: ignore[arg-type]
        assert result["score"] == 0

    def test_negative_drivers_present_for_empty(self):
        result = calculate_roi_score({})
        assert len(result["drivers_negative"]) > 0


class TestDecisionComponent:
    def test_no_decisions_zero(self):
        result = calculate_roi_score({"decisions": []})
        assert result["components"]["decisions"] == 0

    def test_one_decision(self):
        result = calculate_roi_score({"decisions": ["Wir nutzen PostgreSQL"]})
        assert result["components"]["decisions"] == 15

    def test_two_decisions(self):
        result = calculate_roi_score({"decisions": ["A", "B"]})
        assert result["components"]["decisions"] == 15

    def test_three_decisions(self):
        result = calculate_roi_score({"decisions": ["A", "B", "C"]})
        assert result["components"]["decisions"] == 25

    def test_six_decisions(self):
        result = calculate_roi_score({"decisions": ["A", "B", "C", "D", "E", "F"]})
        assert result["components"]["decisions"] == 33

    def test_positive_driver_for_decisions(self):
        result = calculate_roi_score({"decisions": ["A", "B", "C"]})
        assert any("Entscheidung" in d for d in result["drivers_positive"])

    def test_negative_driver_for_no_decisions(self):
        result = calculate_roi_score({"decisions": []})
        assert any("Entscheidung" in d for d in result["drivers_negative"])


class TestActionItemComponent:
    def test_no_action_items_zero(self):
        result = calculate_roi_score({"action_items": []})
        assert result["components"]["action_items"] == 0

    def test_items_with_owner_and_date(self):
        items = ["Max Mustermann: Report fertigstellen bis 15.5.", "Anna Müller: Review durchführen bis 20.5."]
        result = calculate_roi_score({"action_items": items})
        # Both owner and date present → full marks
        assert result["components"]["action_items"] == 33

    def test_items_without_date_reduces_score(self):
        items = ["Max: Report fertigstellen", "Anna: Review durchführen"]
        result_with = calculate_roi_score({"action_items": ["Max: Bericht bis 15.5."]})
        result_without = calculate_roi_score({"action_items": ["Aufgabe ohne Datum"]})
        assert result_with["components"]["action_items"] > result_without["components"]["action_items"]

    def test_negative_driver_for_no_due_dates(self):
        result = calculate_roi_score({"action_items": ["Aufgabe ohne Datum"]})
        assert any("Fälligkeitsdatum" in d for d in result["drivers_negative"])

    def test_positive_driver_for_all_owners(self):
        result = calculate_roi_score({"action_items": ["Max: Aufgabe bis 15.5."]})
        assert any("Verantwortliche" in d for d in result["drivers_positive"])


class TestCompletenessComponent:
    def test_all_five_sections_max(self):
        content = {
            "summary": ["Kurze Zusammenfassung"],
            "decisions": ["Entscheidung A"],
            "action_items": ["Aufgabe 1"],
            "open_questions": ["Frage 1"],
            "next_steps": ["Schritt 1"],
        }
        result = calculate_roi_score(content)
        assert result["components"]["completeness"] == 33

    def test_three_sections(self):
        content = {
            "summary": ["Zusammenfassung"],
            "decisions": ["Entscheidung"],
            "action_items": ["Aufgabe"],
        }
        result = calculate_roi_score(content)
        assert result["components"]["completeness"] == 18  # 3 * 6

    def test_all_sections_positive_driver(self):
        content = {
            "summary": ["s"],
            "decisions": ["d"],
            "action_items": ["a"],
            "open_questions": ["q"],
            "next_steps": ["n"],
        }
        result = calculate_roi_score(content)
        assert any("alle" in d.lower() or "Alle" in d for d in result["drivers_positive"])

    def test_missing_summary_negative_driver(self):
        content = {"decisions": ["d"], "action_items": ["a"]}
        result = calculate_roi_score(content)
        assert any("Zusammenfassung" in d for d in result["drivers_negative"])


class TestScoreCap:
    def test_score_capped_at_100(self):
        content = {
            "summary": ["Lange Zusammenfassung"],
            "decisions": ["A", "B", "C", "D", "E", "F", "G"],
            "action_items": ["Max: Aufgabe 1 bis 10.5.", "Anna: Aufgabe 2 bis 15.5."],
            "open_questions": ["Frage?"],
            "next_steps": ["Nächster Schritt"],
        }
        result = calculate_roi_score(content)
        assert result["score"] <= 100

    def test_score_increases_with_content(self):
        empty = calculate_roi_score({})
        full = calculate_roi_score({
            "summary": ["s"],
            "decisions": ["a", "b", "c", "d"],
            "action_items": ["Max: Task bis 10.5."],
            "open_questions": ["q"],
            "next_steps": ["n"],
        })
        assert full["score"] > empty["score"]

    def test_drivers_are_lists(self):
        result = calculate_roi_score({})
        assert isinstance(result["drivers_positive"], list)
        assert isinstance(result["drivers_negative"], list)


class TestMarkdownIntegration:
    """Tests for _format_as_markdown integration with snapshot_content."""

    def _make_snapshot(self):
        return {
            "summary": ["Kurze Zusammenfassung"],
            "decisions": ["Wir setzen auf PostgreSQL"],
            "action_items": ["Max: Report bis 15.5."],
            "open_questions": ["Wie geht es weiter?"],
        }

    def test_score_block_present_when_snapshot_content_given(self):
        from ayehear.app.window import MainWindow
        md = MainWindow._format_as_markdown(
            draft="Summary\nKurze Zusammenfassung\n",
            title="Test Meeting",
            meeting_type="Jour Fixe",
            snapshot_content=self._make_snapshot(),
        )
        assert "## 📊 Meeting-Effektivität" in md or "## \U0001f4ca Meeting-Effektivit\u00e4t" in md

    def test_score_block_contains_score(self):
        from ayehear.app.window import MainWindow
        md = MainWindow._format_as_markdown(
            draft="Summary\nKurze Zusammenfassung\n",
            title="Test Meeting",
            meeting_type="Jour Fixe",
            snapshot_content=self._make_snapshot(),
        )
        assert "**Score:" in md

    def test_score_block_absent_without_snapshot_content(self):
        from ayehear.app.window import MainWindow
        md = MainWindow._format_as_markdown(
            draft="Summary\nKurze Zusammenfassung\n",
            title="Test Meeting",
            meeting_type="Jour Fixe",
        )
        assert "Meeting-Effektivit" not in md

    def test_score_block_absent_with_none_snapshot_content(self):
        from ayehear.app.window import MainWindow
        md = MainWindow._format_as_markdown(
            draft="Summary\nKurze Zusammenfassung\n",
            title="Test Meeting",
            meeting_type="Jour Fixe",
            snapshot_content=None,
        )
        assert "Meeting-Effektivit" not in md

    def test_hear_174_tests_not_broken(self):
        """Regression: _format_as_markdown without snapshot_content still works."""
        from ayehear.app.window import MainWindow
        md = MainWindow._format_as_markdown(
            draft="Summary\nKurze Zusammenfassung\nDecisions\n- Entscheidung A\nAction Items\n- Max: Aufgabe bis 15.5.",
            title="Regression Test",
            meeting_type="Jour Fixe",
            participants=["Max Mustermann"],
            start_time="09:00",
            end_time="10:00",
        )
        assert "# BESPRECHUNGSPROTOKOLL" in md
        assert "---" in md
        assert "Aufgabenliste" in md
