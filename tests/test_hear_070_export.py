"""Tests for HEAR-070: Align Export Outputs with V1 Contract (B3 Closure).

Covers:
- Protocol exported as Markdown (.md), DOCX (.docx) and PDF (.pdf)
- Transcript exported as .txt (unchanged)
- Markdown file contains expected section headers
- DOCX file is a valid Word document with the meeting title
- PDF file is non-empty and starts with the PDF magic bytes
- Export artifact list includes all three protocol formats + transcript
- _format_as_markdown correctly converts section headers
- Empty protocol/transcript does not create files
- _export_meeting_artifacts returns empty list when meeting_id is None
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())
    return win


# ---------------------------------------------------------------------------
# _format_as_markdown unit tests
# ---------------------------------------------------------------------------


def test_format_as_markdown_adds_h1_title() -> None:
    from ayehear.app.window import MainWindow

    md = MainWindow._format_as_markdown("Summary\n- Item 1", "My Meeting", "internal")
    assert "# My Meeting" in md


def test_format_as_markdown_adds_type_line() -> None:
    from ayehear.app.window import MainWindow

    md = MainWindow._format_as_markdown("Decisions\n- Done", "Test", "external")
    assert "**Type:** external" in md


def test_format_as_markdown_converts_section_headers() -> None:
    from ayehear.app.window import MainWindow

    sections = ["Summary", "Decisions", "Action Items", "Open Questions"]
    protocol = "\n\n".join(f"{s}\n- Sample item" for s in sections)
    md = MainWindow._format_as_markdown(protocol, "T", "t")

    for section in sections:
        assert f"## {section}" in md


def test_format_as_markdown_preserves_list_items() -> None:
    from ayehear.app.window import MainWindow

    md = MainWindow._format_as_markdown("Decisions\n- Buy coffee\n- Cancel meeting", "T", "t")
    assert "- Buy coffee" in md
    assert "- Cancel meeting" in md


def test_format_as_markdown_non_section_lines_not_prefixed() -> None:
    """Lines that are not known section headers must not get ## prefix."""
    from ayehear.app.window import MainWindow

    md = MainWindow._format_as_markdown("Meeting: Quarterly Review\n- Note", "T", "t")
    assert "## Meeting: Quarterly Review" not in md
    assert "Meeting: Quarterly Review" in md


# ---------------------------------------------------------------------------
# _export_meeting_artifacts: full integration via tmp_path
# ---------------------------------------------------------------------------


def test_export_creates_markdown_file(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Summary\n- Test summary\n\nDecisions\n- A decision was made.")
    win._transcript_view.setPlainText("[00:00] Speaker: Hello")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("test-meeting-id", "Test Meeting")

    names = [p.name for p in exported]
    assert any(n.endswith(".md") for n in names)
    win.deleteLater()
    qapp.processEvents()


def test_export_creates_docx_file(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Summary\n- Item")
    win._transcript_view.setPlainText("[00:01] X: Text")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("meet-id-1", "Meeting One")

    names = [p.name for p in exported]
    assert any(n.endswith(".docx") for n in names)
    win.deleteLater()
    qapp.processEvents()


def test_export_creates_pdf_file(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Decisions\n- Approved")
    win._transcript_view.setPlainText("[00:00] A: Yes")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("meet-id-2", "Meeting Two")

    names = [p.name for p in exported]
    assert any(n.endswith(".pdf") for n in names)
    win.deleteLater()
    qapp.processEvents()


def test_export_creates_transcript_txt(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Summary\n- Nothing")
    win._transcript_view.setPlainText("[00:10] Bob: Hello world")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("meet-id-3", "Meeting Three")

    names = [p.name for p in exported]
    assert any(n.endswith("-transcript.txt") for n in names)
    win.deleteLater()
    qapp.processEvents()


def test_export_returns_all_four_artifacts(qapp, tmp_path: Path) -> None:
    """Full export must return md + docx + pdf + txt = 4 paths."""
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Summary\n- OK\n\nAction Items\n- Task A")
    win._transcript_view.setPlainText("[00:00] Speaker: Test")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("full-export-id", "Full Export")

    exts = {p.suffix for p in exported}
    assert ".md" in exts
    assert ".docx" in exts
    assert ".pdf" in exts
    assert ".txt" in exts
    assert len(exported) == 4
    win.deleteLater()
    qapp.processEvents()


def test_export_returns_no_protocol_txt(qapp, tmp_path: Path) -> None:
    """Old -protocol.txt must NOT be created (HEAR-070 removes this format)."""
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Decisions\n- Yes")
    win._transcript_view.setPlainText("[00:00] X: Hi")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("no-txt-id", "No Txt")

    names = [p.name for p in exported]
    assert not any(n.endswith("-protocol.txt") for n in names), (
        "Protocol must no longer be exported as .txt (use .md/.docx/.pdf per HEAR-070)"
    )
    win.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Content sanity checks
# ---------------------------------------------------------------------------


def test_markdown_content_contains_protocol_text(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Summary\n- The team agreed on the plan.\n\nDecisions\n- Plan approved.")
    win._transcript_view.setPlainText("[00:00] Speaker: Text")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("md-content-id", "Content Test")

    md_path = next(p for p in exported if p.suffix == ".md")
    content = md_path.read_text(encoding="utf-8")
    assert "Content Test" in content
    assert "## Summary" in content
    assert "The team agreed on the plan." in content
    assert "## Decisions" in content
    assert "Plan approved." in content
    win.deleteLater()
    qapp.processEvents()


def test_docx_contains_meeting_title(qapp, tmp_path: Path) -> None:
    from docx import Document

    win = _make_window(qapp)
    win._protocol_view.setPlainText("Summary\n- Check DOCX title")
    win._transcript_view.setPlainText("[00:00] X: text")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("docx-title-id", "My DOCX Meeting")

    docx_path = next(p for p in exported if p.suffix == ".docx")
    doc = Document(str(docx_path))
    full_text = " ".join(p.text for p in doc.paragraphs)
    assert "My DOCX Meeting" in full_text
    win.deleteLater()
    qapp.processEvents()


def test_pdf_is_non_empty_and_valid(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Action Items\n- Review PDF export")
    win._transcript_view.setPlainText("[00:00] X: text")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("pdf-valid-id", "PDF Test Meeting")

    pdf_path = next(p for p in exported if p.suffix == ".pdf")
    data = pdf_path.read_bytes()
    assert len(data) > 100
    assert data[:4] == b"%PDF", "File must start with PDF magic bytes"
    win.deleteLater()
    qapp.processEvents()


def test_transcript_content_preserved(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Summary\n- ok")
    win._transcript_view.setPlainText("[00:05] Frau Schneider: Guten Morgen!")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("txt-content-id", "Transcript Test")

    txt_path = next(p for p in exported if p.suffix == ".txt")
    content = txt_path.read_text(encoding="utf-8")
    assert "Frau Schneider" in content
    assert "Guten Morgen" in content
    win.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_export_returns_empty_list_for_none_meeting_id(qapp) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("Summary\n- ok")
    result = win._export_meeting_artifacts(None, "Test")
    assert result == []
    win.deleteLater()
    qapp.processEvents()


def test_export_no_files_created_when_protocol_empty(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("")
    win._transcript_view.setPlainText("")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("empty-id", "Empty Meeting")

    assert exported == []
    assert list(tmp_path.iterdir()) == []
    win.deleteLater()
    qapp.processEvents()


def test_export_only_transcript_when_protocol_empty(qapp, tmp_path: Path) -> None:
    win = _make_window(qapp)
    win._protocol_view.setPlainText("")
    win._transcript_view.setPlainText("[00:00] X: Hello")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        exported = win._export_meeting_artifacts("partial-id", "Partial")

    # Only transcript, no protocol files
    assert len(exported) == 1
    assert exported[0].suffix == ".txt"
    win.deleteLater()
    qapp.processEvents()
