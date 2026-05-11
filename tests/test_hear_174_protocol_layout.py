"""Tests for HEAR-174: V2-11 AYE Brand Protocol Layout.

Tests for _format_as_markdown() — pure string tests, no Qt required.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make ayehear importable without Qt by stubbing PyQt6 before import
_qt_modules = [
    "PyQt6", "PyQt6.QtWidgets", "PyQt6.QtCore", "PyQt6.QtGui",
    "PyQt6.QtMultimedia", "PyQt6.sip",
]
for _mod in _qt_modules:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Directly import the static method without instantiating MainWindow
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _get_format_fn():
    """Import _format_as_markdown without triggering Qt."""
    # Patch heavy imports so the module loads in headless env
    with patch.dict(sys.modules, {m: MagicMock() for m in _qt_modules}):
        from ayehear.app.window import MainWindow  # noqa: PLC0415
        return MainWindow._format_as_markdown


_fmt = _get_format_fn()

DRAFT_FULL = """\
Summary
- Quarterly review completed successfully.
Decisions
- Proceed with Phase 2 implementation.
- Budget approved.
Action Items
- Anna: Report erstellen bis 15.05.
- Bob: Termin vereinbaren bis 20.05.2026
Open Questions
- Timeline for Phase 3?
Next Steps
- Schedule kick-off.
"""

DRAFT_NO_ACTIONS = """\
Summary
- Short meeting.
Decisions
- None.
"""


# ---------------------------------------------------------------------------
# YAML front-matter
# ---------------------------------------------------------------------------

class TestYamlFrontMatter:
    def test_frontmatter_block_present(self):
        md = _fmt(DRAFT_FULL, "Q1 Review", "internal")
        assert md.startswith("---\n"), "Must start with YAML front-matter"
        # Count opening and closing ---
        parts = md.split("---")
        assert len(parts) >= 3, "Front-matter must be closed with ---"

    def test_frontmatter_meeting_field(self):
        md = _fmt(DRAFT_FULL, "My Meeting", "external")
        assert "meeting: My Meeting" in md

    def test_frontmatter_participants_field_with_values(self):
        md = _fmt(DRAFT_FULL, "T", "t", participants=["Alice", "Bob"])
        assert "participants:" in md
        assert "  - Alice" in md
        assert "  - Bob" in md

    def test_frontmatter_participants_empty_fallback(self):
        md = _fmt(DRAFT_FULL, "T", "t", participants=[])
        assert "participants:" in md
        assert "  - —" in md

    def test_frontmatter_participants_none_fallback(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "participants:" in md

    def test_frontmatter_start_end(self):
        md = _fmt(DRAFT_FULL, "T", "t", start_time="09:00", end_time="10:30")
        assert "start: 09:00" in md
        assert "end: 10:30" in md

    def test_frontmatter_protokoll_version(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "protokoll_version: Entwurf" in md

    def test_frontmatter_export_timestamp(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert re.search(r"export: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", md)


# ---------------------------------------------------------------------------
# Header section
# ---------------------------------------------------------------------------

class TestHeaderSection:
    def test_main_heading(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "# BESPRECHUNGSPROTOKOLL" in md

    def test_termin_field(self):
        md = _fmt(DRAFT_FULL, "Projektmeeting", "t")
        assert "**Termin:** Projektmeeting" in md

    def test_typ_field(self):
        md = _fmt(DRAFT_FULL, "T", "Kundengespräch")
        assert "**Typ:** Kundengespräch" in md

    def test_datum_german_format(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert re.search(r"\*\*Datum:\*\* \d{2}\.\d{2}\.\d{4}", md)

    def test_zeit_field_with_times(self):
        md = _fmt(DRAFT_FULL, "T", "t", start_time="08:00", end_time="09:00")
        assert "**Zeit:** 08:00 – 09:00 Uhr" in md

    def test_teilnehmer_list(self):
        md = _fmt(DRAFT_FULL, "T", "t", participants=["Alice", "Bob"])
        assert "**Teilnehmer:**" in md
        lines = md.splitlines()
        tn_idx = next(i for i, l in enumerate(lines) if "**Teilnehmer:**" in l)
        following = "\n".join(lines[tn_idx:tn_idx + 5])
        assert "- Alice" in following
        assert "- Bob" in following


# ---------------------------------------------------------------------------
# Icon section headers
# ---------------------------------------------------------------------------

class TestIconSections:
    def test_zusammenfassung_icon(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "## 📝 Zusammenfassung" in md

    def test_entscheidungen_icon(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "## ✅ Entscheidungen" in md

    def test_todos_icon(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "## 📌 To-Dos / Aufgaben" in md

    def test_offene_punkte_icon(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "## ⚠️ Offene Punkte" in md

    def test_naechste_schritte_icon(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "## 🔷 Nächste Schritte" in md

    def test_no_raw_section_names(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        # Original section names must not appear as bare headers (without icon)
        for raw in ("## Summary", "## Decisions", "## Action Items", "## Open Questions"):
            assert raw not in md, f"Raw section '{raw}' must not appear without icon"


# ---------------------------------------------------------------------------
# Aufgabenliste table
# ---------------------------------------------------------------------------

class TestAufgabenliste:
    def test_table_header_present(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "## Aufgabenliste" in md
        assert "| # | Aufgabe | Verantwortlich | Fällig |" in md
        assert "|---|---------|---------------|--------|" in md

    def test_action_item_parsed_name(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "| Anna |" in md or "Anna" in md
        assert "| Bob |" in md or "Bob" in md

    def test_action_item_due_date_extracted(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "15.05." in md

    def test_empty_action_items_fallback(self):
        md = _fmt(DRAFT_NO_ACTIONS, "T", "t")
        assert "## Aufgabenliste" in md
        assert "Keine offenen Aufgaben" in md

    def test_table_row_count_matches_items(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        # 2 action items → 2 data rows
        rows = [l for l in md.splitlines() if re.match(r"\|\s*\d+\s*\|", l)]
        assert len(rows) == 2

    def test_no_action_items_one_fallback_row(self):
        md = _fmt(DRAFT_NO_ACTIONS, "T", "t")
        rows = [l for l in md.splitlines() if re.match(r"\|\s*\d+\s*\|", l)]
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

class TestFooter:
    def test_aye_hear_footer_present(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "AYE Hear" in md
        assert "Offline-Verarbeitung bestätigt" in md

    def test_quality_disclaimer_present(self):
        md = _fmt(DRAFT_FULL, "T", "t")
        assert "Menschliche Prüfung vor offiziellem Versand erforderlich" in md


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------

class TestBackwardsCompatibility:
    def test_minimal_call(self):
        """Old call signature with only 3 positional args must still work."""
        md = _fmt("Summary\n- OK\n", "Title", "internal")
        assert "# BESPRECHUNGSPROTOKOLL" in md
        assert "**Termin:** Title" in md

    def test_returns_string(self):
        md = _fmt("", "T", "t")
        assert isinstance(md, str)
