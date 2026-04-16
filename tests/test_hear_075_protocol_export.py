"""Tests for HEAR-075: Visible Protocol Preview and Manual Export UI.

Covers:
- Export button exists in MainWindow
- Export button disabled before meeting starts, enabled after start
- Export button remains enabled after meeting stops
- _do_export_protocol writes a Markdown file to exports_dir
- Export file contains meeting title and draft content
- Export path label shows path after export
- _update_protocol_live appends transcript line when no DB
- append_transcript_line calls _update_protocol_live during active meeting
- Export shows warning when draft is empty
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())
    return win


# ---------------------------------------------------------------------------
# Export button existence and state transitions
# ---------------------------------------------------------------------------

class TestExportButtonState:
    def test_export_button_exists(self, qapp):
        win = _make_window(qapp)
        assert hasattr(win, "_export_btn"), "_export_btn must exist"
        win.deleteLater()
        qapp.processEvents()

    def test_export_button_disabled_initially(self, qapp):
        win = _make_window(qapp)
        assert not win._export_btn.isEnabled(), "Export button must be disabled before meeting starts"
        win.deleteLater()
        qapp.processEvents()

    def test_export_button_enabled_during_meeting(self, qapp):
        """Export button must become enabled when a meeting starts."""
        win = _make_window(qapp)
        from PySide6.QtWidgets import QListWidgetItem

        win._meeting_title.setText("Test Meeting")
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Anna | Corp | pending enrollment"))

        with (
            patch.object(win, "_start_audio_pipeline", return_value="OK"),
            patch("PySide6.QtWidgets.QMessageBox.information"),
        ):
            win._start_meeting()

        assert win._export_btn.isEnabled(), "Export button must be enabled during meeting"
        win.deleteLater()
        qapp.processEvents()

    def test_export_button_remains_enabled_after_stop(self, qapp):
        """Export button must stay enabled after meeting stops (post-meeting export)."""
        win = _make_window(qapp)
        from PySide6.QtWidgets import QListWidgetItem

        win._meeting_title.setText("Test Meeting")
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Anna | Corp | pending enrollment"))

        with (
            patch.object(win, "_start_audio_pipeline", return_value="OK"),
            patch("PySide6.QtWidgets.QMessageBox.information"),
        ):
            win._start_meeting()

        with (
            patch.object(win, "_transcribe_pending_buffer"),
            patch.object(win, "_stop_audio_pipeline"),
        ):
            win._stop_meeting()

        assert win._export_btn.isEnabled(), "Export button must remain enabled after meeting stops"
        win.deleteLater()
        qapp.processEvents()

    def test_export_path_label_exists(self, qapp):
        win = _make_window(qapp)
        assert hasattr(win, "_export_path_label"), "_export_path_label must exist"
        assert win._export_path_label.text() == ""
        win.deleteLater()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# _do_export_protocol
# ---------------------------------------------------------------------------

class TestDoExportProtocol:
    def test_export_writes_markdown_file(self, qapp, tmp_path):
        """_do_export_protocol must write a .md file to exports_dir."""
        win = _make_window(qapp)
        win._protocol_view.setPlainText(
            "Summary\n- Test meeting.\n\nDecisions\n- Decision A."
        )
        win._session = MagicMock()
        win._session.title = "Sprint Review"

        with (
            patch("ayehear.utils.paths.resolve_install_root", return_value=tmp_path),
            patch("PySide6.QtWidgets.QMessageBox.information"),
        ):
            win._do_export_protocol()

        exports = list((tmp_path / "exports").glob("protocol_*.md"))
        assert len(exports) == 1, f"Expected 1 exported file, got {len(exports)}"
        content = exports[0].read_text(encoding="utf-8")
        assert "Sprint Review" in content
        assert "Decision A" in content

        win.deleteLater()
        qapp.processEvents()

    def test_export_path_label_updated(self, qapp, tmp_path):
        """After export, _export_path_label must show the export path."""
        win = _make_window(qapp)
        win._protocol_view.setPlainText("Some content")
        win._session = MagicMock()
        win._session.title = "My Meeting"

        with (
            patch("ayehear.utils.paths.resolve_install_root", return_value=tmp_path),
            patch("PySide6.QtWidgets.QMessageBox.information"),
        ):
            win._do_export_protocol()

        label = win._export_path_label.text()
        assert label.startswith("Exportiert:"), f"Expected label to start with 'Exportiert:', got {label!r}"
        assert ".md" in label

        win.deleteLater()
        qapp.processEvents()

    def test_export_empty_draft_shows_warning(self, qapp):
        """Empty protocol draft must trigger a warning, not create a file."""
        win = _make_window(qapp)
        win._protocol_view.setPlainText("")

        with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
            win._do_export_protocol()

        mock_warn.assert_called_once()

        win.deleteLater()
        qapp.processEvents()

    def test_export_file_contains_markdown_header(self, qapp, tmp_path):
        """Exported file must start with # Meeting Protocol header."""
        win = _make_window(qapp)
        win._protocol_view.setPlainText("Decisions\n- Keep offline.")
        win._session = MagicMock()
        win._session.title = "Standup"

        with (
            patch("ayehear.utils.paths.resolve_install_root", return_value=tmp_path),
            patch("PySide6.QtWidgets.QMessageBox.information"),
        ):
            win._do_export_protocol()

        exports = list((tmp_path / "exports").glob("protocol_*.md"))
        content = exports[0].read_text(encoding="utf-8")
        assert content.startswith("# Meeting Protocol")

        win.deleteLater()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# _update_protocol_live
# ---------------------------------------------------------------------------

class TestUpdateProtocolLive:
    def test_appends_transcript_when_no_db(self, qapp):
        """Without a snapshot repo, live update must append transcript line."""
        win = _make_window(qapp)
        win._snapshot_repo = None
        win._active_meeting_id = "mtg-001"
        win._protocol_view.setPlainText("Summary\n- Started.")

        win._update_protocol_live("[00:30] Anna: Hello everyone.")

        text = win._protocol_view.toPlainText()
        assert "[00:30] Anna: Hello everyone." in text

    def test_transcript_section_added_on_first_update(self, qapp):
        """First live update must add a '## Transcript' section."""
        win = _make_window(qapp)
        win._snapshot_repo = None
        win._active_meeting_id = "mtg-001"
        win._protocol_view.setPlainText("Summary\n- Started.")

        win._update_protocol_live("[00:01] System: Ready.")

        text = win._protocol_view.toPlainText()
        assert "## Transcript" in text

    def test_second_update_appends_without_duplicate_section(self, qapp):
        """Second update must NOT add another '## Transcript' header."""
        win = _make_window(qapp)
        win._snapshot_repo = None
        win._active_meeting_id = "mtg-001"
        win._protocol_view.setPlainText("Summary\n- Started.")

        win._update_protocol_live("[00:01] System: Ready.")
        win._update_protocol_live("[00:02] Anna: Hi.")

        text = win._protocol_view.toPlainText()
        assert text.count("## Transcript") == 1

    def test_delegates_to_refresh_when_snapshot_repo_present(self, qapp):
        """With snapshot repo, _update_protocol_live must call _refresh_protocol_display."""
        win = _make_window(qapp)
        win._snapshot_repo = MagicMock()
        win._active_meeting_id = "mtg-001"

        with patch.object(win, "_refresh_protocol_display") as mock_refresh:
            win._update_protocol_live("[00:01] Test line.")

        mock_refresh.assert_called_once()


# ---------------------------------------------------------------------------
# append_transcript_line integration
# ---------------------------------------------------------------------------

class TestAppendTranscriptLineIntegration:
    def test_protocol_updated_during_active_meeting(self, qapp):
        """append_transcript_line must trigger protocol update when meeting is active."""
        win = _make_window(qapp)
        win._active_meeting_id = "mtg-002"
        win._snapshot_repo = None
        win._protocol_view.setPlainText("Summary\n- Started.")

        win.append_transcript_line("[00:10] Max: Good morning.")

        text = win._protocol_view.toPlainText()
        assert "[00:10] Max: Good morning." in text

    def test_protocol_not_updated_without_active_meeting(self, qapp):
        """append_transcript_line must NOT update protocol when no meeting is active."""
        win = _make_window(qapp)
        win._active_meeting_id = None
        win._snapshot_repo = None
        initial_text = "Summary\n- Waiting."
        win._protocol_view.setPlainText(initial_text)

        win.append_transcript_line("[00:00] System: Meeting initialized.")

        # Protocol draft must remain unchanged
        assert win._protocol_view.toPlainText() == initial_text
