"""Tests for HEAR-176: Decision Risk Radar (V2-02).

Covers:
- score_decision() risk levels and indicators
- get_high_risk_decisions() filtering
- _format_as_markdown() integration: emoji labels + risk table section
- Backwards-compatibility: no decisions in snapshot_content → no error
"""
from __future__ import annotations

import pytest

from ayehear.services.decision_risk import (
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    EMOJI_MAP,
    score_decision,
    get_high_risk_decisions,
)


# ---------------------------------------------------------------------------
# score_decision – unit tests
# ---------------------------------------------------------------------------

class TestScoreDecision:
    def test_low_risk_clear_decision(self):
        """Clear decision with owner, date → low risk (0 points)."""
        result = score_decision("Budget für Q3 freigegeben durch Max bis 30.06.")
        assert result["risk_level"] == RISK_LOW
        assert result["risk_points"] == 0
        assert result["indicators"] == []

    def test_high_risk_unklar_eventuell(self):
        """Unklar + no owner + no date + risk keyword → high risk."""
        result = score_decision("Unklar, wer verantwortlich, eventuell Q4")
        assert result["risk_level"] == RISK_HIGH
        assert result["risk_points"] >= 3

    def test_low_or_medium_with_date_and_owner(self):
        """Decision with date and named person is low or medium risk."""
        result = score_decision("Deployment bis 15.05. durch Max")
        assert result["risk_level"] in (RISK_LOW, RISK_MEDIUM)
        assert result["risk_points"] <= 2

    def test_high_risk_dependency_plus_risk_keyword(self):
        """Dependency + risk keyword → high risk."""
        result = score_decision("abhängig von Lieferant, offen")
        assert result["risk_level"] == RISK_HIGH
        assert "Abhängigkeit" in result["indicators"]
        assert "Risikobegriff" in result["indicators"]

    def test_medium_risk_no_owner_no_date(self):
        """Missing owner and date (but no other indicators) → medium (2 pts).

        A generic sentence without 'durch Name', 'von Name', or 'Name:' has no
        detectable owner.  Without a date pattern either, risk = 2 → medium.
        """
        result = score_decision("API soll grundlegend überarbeitet werden")
        assert result["risk_level"] == RISK_MEDIUM
        assert result["risk_points"] == 2
        assert "Kein Eigentümer" in result["indicators"]
        assert "Kein Datum" in result["indicators"]

    def test_medium_risk_dependency_only(self):
        """Only one indicator → medium risk."""
        result = score_decision("Abschluss sobald Lieferant liefert — durch Julia bis 20.05.")
        assert result["risk_level"] in (RISK_LOW, RISK_MEDIUM)
        assert result["risk_points"] <= 2

    def test_empty_string(self):
        """Empty decision text → low risk, 0 points, no crash."""
        result = score_decision("")
        assert result["risk_level"] == RISK_LOW
        assert result["risk_points"] == 0
        assert result["indicators"] == []

    def test_whitespace_only(self):
        """Whitespace-only decision → low risk, no crash."""
        result = score_decision("   ")
        assert result["risk_level"] == RISK_LOW

    def test_indicators_present_in_result(self):
        """Result always contains all three expected keys."""
        result = score_decision("irgendwas")
        assert "risk_level" in result
        assert "risk_points" in result
        assert "indicators" in result

    def test_risk_points_bounds(self):
        """risk_points is always between 0 and 4."""
        texts = [
            "Budget freigegeben",
            "Unklar, wer das macht, abhängig von API, eventuell fraglich",
            "Max erledigt das bis 10.05.",
        ]
        for text in texts:
            r = score_decision(text)
            assert 0 <= r["risk_points"] <= 4


# ---------------------------------------------------------------------------
# get_high_risk_decisions – unit tests
# ---------------------------------------------------------------------------

class TestGetHighRiskDecisions:
    def test_filters_low_risk(self):
        """Low-risk decisions are excluded from the result."""
        decisions = ["Budget freigegeben durch Max bis 30.06."]
        result = get_high_risk_decisions(decisions)
        assert result == []

    def test_includes_medium_and_high(self):
        """Medium and high risk decisions appear in result."""
        decisions = [
            "Budget freigegeben durch Max bis 30.06.",    # low
            "Unklar, wer das Deployment übernimmt",       # high
            "API-Schnittstelle soll überarbeitet werden", # medium
        ]
        result = get_high_risk_decisions(decisions)
        assert len(result) == 2
        texts = [r["text"] for r in result]
        assert "Unklar, wer das Deployment übernimmt" in texts
        assert "API-Schnittstelle soll überarbeitet werden" in texts

    def test_empty_list(self):
        """Empty input returns empty list without error."""
        assert get_high_risk_decisions([]) == []

    def test_result_structure(self):
        """Each result item has text, risk_level, indicators keys."""
        decisions = ["Unklar, wer das macht"]
        result = get_high_risk_decisions(decisions)
        assert len(result) == 1
        item = result[0]
        assert "text" in item
        assert "risk_level" in item
        assert "indicators" in item

    def test_order_preserved(self):
        """Order of flagged decisions matches input order.

        Only medium/high entries appear, in input order.
        A decision with owner ('durch Max') AND date ('bis 30.06.') scores
        0 points → low → excluded.
        """
        decisions = [
            "Unklar, wer das macht",                    # high (3 pts)
            "Budget freigegeben durch Max bis 30.06.",  # low (0 pts, excluded)
            "API soll grundlegend überarbeitet werden",  # medium (2 pts)
        ]
        result = get_high_risk_decisions(decisions)
        assert result[0]["text"] == "Unklar, wer das macht"
        assert result[1]["text"] == "API soll grundlegend überarbeitet werden"


# ---------------------------------------------------------------------------
# Emoji map sanity
# ---------------------------------------------------------------------------

def test_emoji_map_contains_all_levels():
    assert RISK_LOW in EMOJI_MAP
    assert RISK_MEDIUM in EMOJI_MAP
    assert RISK_HIGH in EMOJI_MAP
    # Emojis are non-empty strings
    for emoji in EMOJI_MAP.values():
        assert emoji and isinstance(emoji, str)


# ---------------------------------------------------------------------------
# _format_as_markdown integration tests
# ---------------------------------------------------------------------------

def _call_format(draft: str, snapshot_content: dict | None = None) -> str:
    """Helper: call _format_as_markdown with minimal required args."""
    from ayehear.app.window import MainWindow
    return MainWindow._format_as_markdown(
        draft=draft,
        title="Test Meeting",
        meeting_type="intern",
        snapshot_content=snapshot_content,
    )


DRAFT_WITH_DECISIONS = """\
Summary
- This is the summary.
Decisions
- Budget für Q3 freigegeben durch Max bis 30.06.
- Architektur-Entscheidung offen bis nächste Woche
- Unklar, wer das Deployment übernimmt
Action Items
- Max: Server-Setup bis 20.05.
"""

DRAFT_ALL_GREEN = """\
Summary
- All good.
Decisions
- Budget freigegeben durch Julia bis 30.06.
- Design abgeschlossen durch Thomas bis 15.05.
Action Items
- Julia: Follow-up bis 25.05.
"""

DRAFT_NO_DECISIONS = """\
Summary
- Keine Entscheidungen getroffen.
Action Items
- Max: Aufgabe erledigen bis 30.05.
"""


class TestFormatAsMarkdownRiskIntegration:
    def test_decision_lines_have_emoji(self):
        """Each decision line in the markdown ends with a risk emoji."""
        md = _call_format(DRAFT_WITH_DECISIONS)
        # The high-risk decision should have 🔴
        assert "🔴" in md or "\U0001f534" in md
        # The low-risk decision should have 🟢
        assert "🟢" in md or "\U0001f7e2" in md

    def test_risk_section_present_when_risky(self):
        """Risk table section appears when there are medium/high decisions."""
        md = _call_format(DRAFT_WITH_DECISIONS)
        assert "Entscheidungsrisiken" in md

    def test_risk_section_absent_when_all_green(self):
        """Risk table section is omitted when all decisions are low risk."""
        md = _call_format(DRAFT_ALL_GREEN)
        assert "Entscheidungsrisiken" not in md

    def test_no_decisions_no_risk_section(self):
        """No decisions in draft → no risk section, no crash."""
        md = _call_format(DRAFT_NO_DECISIONS)
        assert "Entscheidungsrisiken" not in md

    def test_snapshot_decisions_override_draft(self):
        """snapshot_content decisions are used when provided."""
        snapshot = {"decisions": ["Unklar, wer das macht, fraglich"]}
        md = _call_format("Summary\n- ok\n", snapshot_content=snapshot)
        # Risk section must appear because snapshot has a high-risk decision
        assert "Entscheidungsrisiken" in md

    def test_empty_snapshot_decisions_no_crash(self):
        """Empty decisions list in snapshot_content causes no error."""
        md = _call_format(DRAFT_NO_DECISIONS, snapshot_content={"decisions": []})
        assert "Entscheidungsrisiken" not in md

    def test_no_snapshot_content_no_crash(self):
        """snapshot_content=None is fully backwards-compatible."""
        md = _call_format(DRAFT_WITH_DECISIONS, snapshot_content=None)
        # Should produce output without crashing
        assert "BESPRECHUNGSPROTOKOLL" in md

    def test_risk_table_contains_medium_high_only(self):
        """The risk table does not list low-risk decisions."""
        md = _call_format(DRAFT_WITH_DECISIONS)
        # Low-risk decision should NOT appear in the risk table header area
        lines = md.splitlines()
        in_risk_section = False
        risk_table_texts: list[str] = []
        for line in lines:
            if "Entscheidungsrisiken" in line:
                in_risk_section = True
            elif in_risk_section and line.startswith("## "):
                break
            elif in_risk_section and line.startswith("| ") and "Risiko" not in line and "---" not in line:
                risk_table_texts.append(line)
        # "Budget für Q3 freigegeben durch Max bis 30.06." is low risk → not in table
        assert not any("Budget für Q3 freigegeben" in t for t in risk_table_texts)
