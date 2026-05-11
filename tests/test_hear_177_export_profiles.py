"""Tests for HEAR-177: Persona Export Profiles (V2-03)."""
from __future__ import annotations

from ayehear.app.window import MainWindow
from ayehear.services.export_profiles import PROFILE_OPS, get_profile


DRAFT_PROFILE = """\
Summary
- Weekly status sync completed.
Decisions
- Entscheidung 1 durch Max bis 10.05.
- Entscheidung 2 durch Max bis 11.05.
- Entscheidung 3 durch Max bis 12.05.
- Entscheidung 4 durch Max bis 13.05.
- Entscheidung 5 durch Max bis 14.05.
- Entscheidung 6 durch Max bis 15.05.
- Entscheidung 7 durch Max bis 16.05.
Action Items
- Max: Follow-up vorbereiten bis 18.05.
Open Questions
- Wie priorisieren wir Sprint 2?
Next Steps
- Kickoff terminieren.
Transcript
- [00:01] Hallo zusammen.
"""


def _snapshot() -> dict:
    return {
        "summary": ["Weekly status sync completed."],
        "decisions": [
            "Entscheidung 1 durch Max bis 10.05.",
            "Entscheidung 2 durch Max bis 11.05.",
            "Entscheidung 3 durch Max bis 12.05.",
            "Entscheidung 4 durch Max bis 13.05.",
            "Entscheidung 5 durch Max bis 14.05.",
            "Unklar, wer die Freigabe übernimmt",
        ],
        "action_items": ["Max: Follow-up vorbereiten bis 18.05."],
        "open_questions": ["Wie priorisieren wir Sprint 2?"],
        "next_steps": ["Kickoff terminieren."],
    }


def test_ceo_profile_hides_todos_and_limits_decisions_to_five():
    md = MainWindow._format_as_markdown(
        draft=DRAFT_PROFILE,
        title="CEO Export",
        meeting_type="intern",
        snapshot_content=_snapshot(),
        profile_id="ceo",
    )
    assert "## 📌 To-Dos / Aufgaben" not in md
    assert "## Aufgabenliste" not in md
    decision_lines = [line for line in md.splitlines() if line.startswith("- Entscheidung")]
    assert len(decision_lines) == 5
    assert "Team-Protokoll" not in md


def test_team_profile_hides_score_and_decisions_section():
    md = MainWindow._format_as_markdown(
        draft=DRAFT_PROFILE,
        title="Team Export",
        meeting_type="intern",
        snapshot_content=_snapshot(),
        profile_id="team",
    )
    assert "Meeting-Effektivit" not in md
    assert "## ✅ Entscheidungen" not in md
    assert "## ⚠️ Entscheidungsrisiken" not in md


def test_compliance_profile_contains_privacy_block_and_offline_attestation():
    md = MainWindow._format_as_markdown(
        draft=DRAFT_PROFILE,
        title="Compliance Export",
        meeting_type="intern",
        snapshot_content=_snapshot(),
        profile_id="compliance",
    )
    assert "## 🔏 Datenschutz & Compliance" in md
    assert "Offline-Verarbeitung bestätigt gemäß ADR-0001" in md


def test_ops_profile_contains_full_default_sections():
    md = MainWindow._format_as_markdown(
        draft=DRAFT_PROFILE,
        title="Ops Export",
        meeting_type="intern",
        snapshot_content=_snapshot(),
        profile_id="ops",
    )
    assert "## 📊 Meeting-Effektivität" in md
    assert "## ✅ Entscheidungen" in md
    assert "## 📌 To-Dos / Aufgaben" in md
    assert "## Aufgabenliste" in md


def test_get_profile_unknown_falls_back_to_ops():
    profile = get_profile("unknown")
    assert profile.id == PROFILE_OPS


def test_format_as_markdown_without_profile_id_is_ops_compatible():
    md = MainWindow._format_as_markdown(
        draft=DRAFT_PROFILE,
        title="Default Export",
        meeting_type="intern",
        snapshot_content=_snapshot(),
    )
    assert "## 📊 Meeting-Effektivität" in md
    assert "## ✅ Entscheidungen" in md
    assert "## Aufgabenliste" in md
