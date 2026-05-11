"""Tests for HEAR-187: Protocol and export localization alignment (DE/EN)."""
from __future__ import annotations

from datetime import datetime

from ayehear.app.window import MainWindow
from ayehear.services.export_profiles import (
    PROFILE_CEO,
    PROFILE_COMPLIANCE,
    PROFILE_OPS,
    PROFILE_TEAM,
)


def _snapshot() -> dict:
    return {
        "summary": ["Meeting summary"],
        "decisions": [
            "Unklar, wer verantwortlich, eventuell Q4",
            "Deployment bis 15.05. durch Max",
        ],
        "action_items": ["Anna: Follow-up bis 20.05.2026"],
        "open_questions": ["Next deployment slot?"],
        "next_steps": ["Prepare handover"],
    }


def _draft_en() -> str:
    return """\
Summary
- Meeting summary.
Decisions
- Unclear ownership, maybe Q4.
Action Items
- Anna: Follow-up by 20.05.2026
Open Questions
- Next deployment slot?
Next Steps
- Prepare handover.
"""


def _draft_de() -> str:
    return """\
Zusammenfassung
- Besprechung zusammengefasst.
Entscheidungen
- Unklar, wer verantwortlich, eventuell Q4.
Aufgaben
- Anna: Follow-up bis 20.05.2026
Offene Fragen
- Nächster Deployment-Slot?
Nächste Schritte
- Übergabe vorbereiten.
"""


def test_markdown_export_is_fully_german_for_de_language() -> None:
    md = MainWindow._format_as_markdown(
        draft=_draft_de(),
        title="Quartalsreview",
        meeting_type="intern",
        snapshot_content=_snapshot(),
        profile_id=PROFILE_OPS,
        language="de",
    )

    assert "# BESPRECHUNGSPROTOKOLL" in md
    assert "## 📝 Zusammenfassung" in md
    assert "## ⚠️ Entscheidungsrisiken" in md
    assert "## Aufgabenliste" in md
    assert "## 🔏 Datenschutz & Compliance" not in md
    assert "Offline-Verarbeitung bestätigt" in md
    assert "Please review before official distribution" not in md
    assert "## 📝 Summary" not in md
    assert "## ⚠️ Decision Risks" not in md


def test_markdown_export_is_fully_english_for_en_language() -> None:
    md = MainWindow._format_as_markdown(
        draft=_draft_en(),
        title="Quarterly Review",
        meeting_type="internal",
        snapshot_content=_snapshot(),
        profile_id=PROFILE_OPS,
        language="en",
    )

    assert "# MEETING PROTOCOL" in md
    assert "## 📝 Summary" in md
    assert "## ⚠️ Decision Risks" in md
    assert "## Task List" in md
    assert "Offline processing confirmed" in md
    assert "Please review before official distribution" in md
    assert "## 📝 Zusammenfassung" not in md
    assert "## ⚠️ Entscheidungsrisiken" not in md
    assert "## Aufgabenliste" not in md


def test_no_mixed_core_headers_inside_single_export() -> None:
    md_de = MainWindow._format_as_markdown(
        draft=_draft_de(),
        title="M1",
        meeting_type="intern",
        snapshot_content=_snapshot(),
        profile_id=PROFILE_OPS,
        language="de",
    )
    md_en = MainWindow._format_as_markdown(
        draft=_draft_en(),
        title="M2",
        meeting_type="internal",
        snapshot_content=_snapshot(),
        profile_id=PROFILE_OPS,
        language="en",
    )

    de_core = ["## 📝 Zusammenfassung", "## ✅ Entscheidungen", "## Aufgabenliste"]
    en_core = ["## 📝 Summary", "## ✅ Decisions", "## Task List"]

    assert all(header in md_de for header in de_core)
    assert all(header not in md_de for header in en_core)

    assert all(header in md_en for header in en_core)
    assert all(header not in md_en for header in de_core)


def test_profile_outputs_are_valid_in_both_languages() -> None:
    profile_ids = [PROFILE_CEO, PROFILE_OPS, PROFILE_TEAM, PROFILE_COMPLIANCE]

    for profile_id in profile_ids:
        md_de = MainWindow._format_as_markdown(
            draft=_draft_de(),
            title="DE",
            meeting_type="intern",
            snapshot_content=_snapshot(),
            profile_id=profile_id,
            language="de",
        )
        md_en = MainWindow._format_as_markdown(
            draft=_draft_en(),
            title="EN",
            meeting_type="internal",
            snapshot_content=_snapshot(),
            profile_id=profile_id,
            language="en",
        )

        if profile_id == PROFILE_TEAM:
            assert "## 📊 Meeting-Effektivität" not in md_de
            assert "## 📊 Meeting Effectiveness" not in md_en
            assert "## ✅ Entscheidungen" not in md_de
            assert "## ✅ Decisions" not in md_en
        if profile_id == PROFILE_COMPLIANCE:
            assert "## 🔏 Datenschutz & Compliance" in md_de
            assert "## 🔏 Privacy & Compliance" in md_en


def test_markdown_output_is_deterministic_for_same_input_and_language() -> None:
    args = {
        "draft": _draft_en(),
        "title": "Deterministic",
        "meeting_type": "internal",
        "snapshot_content": _snapshot(),
        "profile_id": PROFILE_OPS,
        "language": "en",
        "generated_at": datetime(2026, 5, 11, 12, 30, 0),
    }

    md_1 = MainWindow._format_as_markdown(**args)
    md_2 = MainWindow._format_as_markdown(**args)

    assert md_1 == md_2
