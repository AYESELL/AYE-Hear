"""Tests for HEAR-085: ADR-0005 Protocol Draft Instead of Transcript Mirror.

Covers:
  AC1: Protocol view is never a transcript mirror — protocol and transcript panels are separate
  AC2: _rebuild_protocol_from_persistence() calls ProtocolEngine.generate()
  AC3: Explicit [DEGRADED] label shown when snapshot_repo is None
  AC3: [DEGRADED] content is blocked from export by _do_export_protocol
  AC4: Export content comes from structured snapshot, not transcript lines
  AC5: _update_protocol_live() does NOT append transcript text to protocol view
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(qapp, snapshot_repo=None, meeting_repo=None, participant_repo=None,
                 transcript_repo=None, speaker_manager=None):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(
            runtime_config=RuntimeConfig(),
            meeting_repo=meeting_repo,
            participant_repo=participant_repo,
            transcript_repo=transcript_repo,
            snapshot_repo=snapshot_repo,
            speaker_manager=speaker_manager,
        )
    return win


def _mock_meeting_repo(meeting_id="db-meet-085"):
    repo = MagicMock()
    fake = MagicMock()
    fake.id = meeting_id
    repo.create.return_value = fake
    repo.start.return_value = fake
    repo.end.return_value = fake
    return repo


def _mock_snapshot_repo(content: dict | None = None):
    repo = MagicMock()
    if content is not None:
        snap = MagicMock()
        snap.snapshot_content = content
        repo.latest.return_value = snap
    else:
        repo.latest.return_value = None
    return repo


def _activate_meeting(win, title="TestMeeting", speakers=None):
    """Drive _start_meeting via internal call (sets UI widgets, bypasses dialog / audio init)."""
    from PySide6.QtWidgets import QListWidgetItem
    if speakers is None:
        speakers = ["Alice", "Bob"]
    win._meeting_title.setText(title)
    win._speakers_list.clear()
    for name in speakers:
        win._speakers_list.addItem(QListWidgetItem(name))
    with patch("ayehear.app.window.QMessageBox"):
        with patch.object(win, "_start_audio_pipeline", return_value="Mock-Audio OK"):
            win._start_meeting()


# ---------------------------------------------------------------------------
# AC1: Protocol panel is structurally separate from transcript panel
# ---------------------------------------------------------------------------

class TestAC1ProtocolSeparateFromTranscript:
    def test_protocol_view_and_transcript_view_are_different_widgets(self, qapp):
        """Protocol and transcript views must be distinct QPlainTextEdit instances."""
        win = _make_window(qapp)
        assert win._protocol_view is not win._transcript_view

    def test_append_transcript_line_only_updates_transcript(self, qapp):
        """append_transcript_line appends to transcript, NOT to protocol (no active meeting)."""
        win = _make_window(qapp)
        initial_protocol = win._protocol_view.toPlainText()
        win.append_transcript_line("Hello World")
        assert "Hello World" in win._transcript_view.toPlainText()
        # Protocol unchanged when no active meeting
        assert win._protocol_view.toPlainText() == initial_protocol

    def test_transcript_text_never_appears_in_protocol_after_meeting_start_degraded(self, qapp):
        """With no snapshot_repo, transcript lines must NOT appear in protocol panel."""
        win = _make_window(qapp, snapshot_repo=None)
        _activate_meeting(win)
        # Simulate incoming transcript lines
        for i in range(5):
            win.append_transcript_line(f"Speaker A: sentence {i}")
        protocol_text = win._protocol_view.toPlainText()
        # None of the transcript sentences should be in protocol
        assert "sentence" not in protocol_text
        assert "Speaker A" not in protocol_text

    def test_protocol_not_contaminated_by_transcript_with_db(self, qapp):
        """With snapshot_repo connected but no snapshot yet, protocol text does not mirror transcript."""
        snap_repo = _mock_snapshot_repo(content=None)  # no snapshot yet
        mr = _mock_meeting_repo()
        win = _make_window(qapp, snapshot_repo=snap_repo, meeting_repo=mr)
        _activate_meeting(win)
        win.append_transcript_line("TopSecret: critical data point")
        protocol_text = win._protocol_view.toPlainText()
        assert "TopSecret" not in protocol_text
        assert "critical data point" not in protocol_text


# ---------------------------------------------------------------------------
# AC2: _rebuild_protocol_from_persistence delegates to ProtocolEngine
# ---------------------------------------------------------------------------

class TestAC2ProtocolEngineGenerate:
    def test_rebuild_calls_protocol_engine_generate(self, qapp):
        """_rebuild_protocol_from_persistence must call ProtocolEngine.generate()."""
        snap_repo = _mock_snapshot_repo(content=None)
        tr_repo = MagicMock()
        mr = _mock_meeting_repo("mtg-rebuild")
        win = _make_window(qapp, snapshot_repo=snap_repo, meeting_repo=mr, transcript_repo=tr_repo)

        with patch.object(win._protocol_engine, "generate") as mock_gen:
            with patch.object(win, "_refresh_protocol_display"):
                _activate_meeting(win)
                win._active_meeting_id = "mtg-rebuild"
                win._rebuild_protocol_from_persistence()
        mock_gen.assert_called_once_with("mtg-rebuild")

    def test_rebuild_calls_refresh_after_generate(self, qapp):
        """After generate(), _refresh_protocol_display() is called to update UI."""
        snap_repo = _mock_snapshot_repo()
        tr_repo = MagicMock()
        mr = _mock_meeting_repo("mtg-refresh")
        win = _make_window(qapp, snapshot_repo=snap_repo, meeting_repo=mr, transcript_repo=tr_repo)

        _activate_meeting(win)
        win._active_meeting_id = "mtg-refresh"

        call_order: list[str] = []

        def _fake_generate(mid):
            call_order.append("generate")
            # Return a minimal snapshot so the code reaches _refresh_protocol_display (HEAR-124)
            snap = MagicMock()
            snap.review_queue = None
            snap.trace_store = None
            return snap

        with patch.object(win._protocol_engine, "generate", side_effect=_fake_generate):
            with patch.object(win, "_refresh_protocol_display", side_effect=lambda: call_order.append("refresh")):
                win._rebuild_protocol_from_persistence()

        assert call_order == ["generate", "refresh"]

    def test_rebuild_no_op_when_no_active_meeting(self, qapp):
        """_rebuild_protocol_from_persistence must not crash when no meeting is active."""
        snap_repo = _mock_snapshot_repo()
        win = _make_window(qapp, snapshot_repo=snap_repo)
        win._active_meeting_id = None
        # Must not raise
        win._rebuild_protocol_from_persistence()


# ---------------------------------------------------------------------------
# AC3: Degraded label when persistence unavailable
# ---------------------------------------------------------------------------

class TestAC3DegradedLabel:
    def test_protocol_shows_degraded_when_no_snapshot_repo_at_start(self, qapp):
        """Immediately after _start_meeting without snapshot_repo, protocol shows [DEGRADED]."""
        win = _make_window(qapp, snapshot_repo=None)
        _activate_meeting(win)
        text = win._protocol_view.toPlainText()
        assert text.startswith("[DEGRADED]"), f"Expected [DEGRADED] prefix, got: {text[:80]!r}"

    def test_refresh_protocol_display_sets_degraded_when_no_repo(self, qapp):
        """_refresh_protocol_display sets [DEGRADED] label when snapshot_repo is None."""
        win = _make_window(qapp, snapshot_repo=None)
        win._protocol_view.setPlainText("old text")
        win._refresh_protocol_display()
        text = win._protocol_view.toPlainText()
        assert text.startswith("[DEGRADED]")

    def test_refresh_protocol_display_sets_degraded_when_no_active_meeting(self, qapp):
        """_refresh_protocol_display sets [DEGRADED] label when no meeting is active."""
        snap_repo = _mock_snapshot_repo()
        win = _make_window(qapp, snapshot_repo=snap_repo)
        win._active_meeting_id = None
        win._protocol_view.setPlainText("clean text")
        win._refresh_protocol_display()
        text = win._protocol_view.toPlainText()
        assert text.startswith("[DEGRADED]")

    def test_degraded_label_not_duplicated_on_repeated_refresh(self, qapp):
        """Calling _refresh_protocol_display twice does not stack [DEGRADED] prefixes."""
        win = _make_window(qapp, snapshot_repo=None)
        win._refresh_protocol_display()
        win._refresh_protocol_display()
        text = win._protocol_view.toPlainText()
        assert text.count("[DEGRADED]") == 1

    def test_update_protocol_live_without_db_sets_degraded_not_transcript(self, qapp):
        """_update_protocol_live without snapshot_repo must show [DEGRADED], not transcript text."""
        win = _make_window(qapp, snapshot_repo=None)
        win._active_meeting_id = "fake-id"
        win._update_protocol_live("Some important sentence from speaker")
        text = win._protocol_view.toPlainText()
        assert text.startswith("[DEGRADED]")
        assert "Some important sentence" not in text

    def test_protocol_view_ready_message_when_snapshot_repo_connected(self, qapp):
        """With snapshot_repo connected, start_meeting shows ready message, not degraded."""
        snap_repo = _mock_snapshot_repo(content=None)
        mr = _mock_meeting_repo()
        win = _make_window(qapp, snapshot_repo=snap_repo, meeting_repo=mr)
        _activate_meeting(win, title="BestMeeting", speakers=["Alice"])
        text = win._protocol_view.toPlainText()
        assert not text.startswith("[DEGRADED]"), f"Should not be degraded: {text[:80]!r}"
        assert "BestMeeting" in text


# ---------------------------------------------------------------------------
# AC3: [DEGRADED] content blocked from export
# ---------------------------------------------------------------------------

class TestAC3ExportBlockedOnDegraded:
    def test_export_blocked_when_protocol_is_degraded(self, qapp):
        """_do_export_protocol must show a warning and NOT write a file when content is [DEGRADED]."""
        win = _make_window(qapp, snapshot_repo=None)
        win._protocol_view.setPlainText("[DEGRADED] Protokollentwurf nicht verfügbar.")
        with patch("ayehear.app.window.QMessageBox") as mock_mb:
            win._do_export_protocol()
        mock_mb.warning.assert_called_once()
        args = mock_mb.warning.call_args[0]
        # Third argument is the message text
        assert "degradiert" in args[2].lower() or "nicht verfügbar" in args[2].lower() or "kein" in args[2].lower()

    def test_export_blocked_when_protocol_empty(self, qapp):
        """_do_export_protocol shows a different warning when protocol is empty."""
        win = _make_window(qapp, snapshot_repo=None)
        win._protocol_view.setPlainText("")
        with patch("ayehear.app.window.QMessageBox") as mock_mb:
            win._do_export_protocol()
        mock_mb.warning.assert_called_once()

    def test_export_warning_distinguishes_degraded_from_empty(self, qapp):
        """Warning message differs between empty protocol and degraded protocol."""
        win = _make_window(qapp, snapshot_repo=None)

        with patch("ayehear.app.window.QMessageBox") as mock_mb:
            win._protocol_view.setPlainText("")
            win._do_export_protocol()
            empty_msg = mock_mb.warning.call_args[0][2]

        with patch("ayehear.app.window.QMessageBox") as mock_mb:
            win._protocol_view.setPlainText("[DEGRADED] Backend not connected.")
            win._do_export_protocol()
            degraded_msg = mock_mb.warning.call_args[0][2]

        assert empty_msg != degraded_msg


# ---------------------------------------------------------------------------
# AC4: Export content is structured snapshot, not transcript
# ---------------------------------------------------------------------------

class TestAC4ExportContent:
    def test_export_writes_non_degraded_content(self, qapp, tmp_path):
        """When protocol has real content, export writes the file successfully."""
        win = _make_window(qapp, snapshot_repo=None)
        win._protocol_view.setPlainText(
            "# My Meeting\n\n## Decisions\n- Buy more coffee\n"
        )

        with patch("ayehear.utils.paths.exports_dir", return_value=tmp_path):
            with patch("ayehear.app.window.QMessageBox"):
                win._do_export_protocol()

        files = list(tmp_path.glob("*.md"))
        assert len(files) == 1, f"Expected 1 export file, got: {files}"
        content = files[0].read_text(encoding="utf-8")
        assert "Buy more coffee" in content

    def test_export_does_not_write_degraded_prefix(self, qapp, tmp_path):
        """Exported file must not start with [DEGRADED]."""
        win = _make_window(qapp, snapshot_repo=None)
        # Manually set a valid (non-degraded) protocol
        win._protocol_view.setPlainText("# Meeting\n\nClean structured content.")

        with patch("ayehear.utils.paths.exports_dir", return_value=tmp_path):
            with patch("ayehear.app.window.QMessageBox"):
                win._do_export_protocol()

        files = list(tmp_path.glob("*.md"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert not content.startswith("[DEGRADED]")


# ---------------------------------------------------------------------------
# AC5: _update_protocol_live never appends transcript text
# ---------------------------------------------------------------------------

class TestAC5UpdateProtocolLiveNeverMirrorsTranscript:
    def test_update_protocol_live_does_not_append_to_protocol(self, qapp):
        """Calling _update_protocol_live must NOT append text to protocol view."""
        snap_repo = _mock_snapshot_repo(content=None)
        mr = _mock_meeting_repo()
        win = _make_window(qapp, snapshot_repo=snap_repo, meeting_repo=mr)
        _activate_meeting(win)

        initial_len = len(win._protocol_view.toPlainText())
        with patch.object(win, "_refresh_protocol_display"):
            win._update_protocol_live("transcript text line 42")

        # Protocol text length must not have grown due to appending
        after_len = len(win._protocol_view.toPlainText())
        assert "transcript text line 42" not in win._protocol_view.toPlainText()

    def test_update_protocol_live_without_db_multiple_lines_no_stacking(self, qapp):
        """Multiple _update_protocol_live calls without DB must not stack text."""
        win = _make_window(qapp, snapshot_repo=None)
        win._active_meeting_id = "fake-meeting"
        for i in range(10):
            win._update_protocol_live(f"Line {i}: some content")
        text = win._protocol_view.toPlainText()
        # Must have exactly one [DEGRADED] prefix
        assert text.count("[DEGRADED]") == 1
        assert "Line 0" not in text
        assert "Line 9" not in text

    def test_update_protocol_live_with_db_delegates_to_refresh(self, qapp):
        """With snapshot_repo, _update_protocol_live calls _refresh_protocol_display, not append."""
        snap_repo = _mock_snapshot_repo(content=None)
        mr = _mock_meeting_repo()
        win = _make_window(qapp, snapshot_repo=snap_repo, meeting_repo=mr)
        _activate_meeting(win)

        with patch.object(win, "_refresh_protocol_display") as mock_refresh:
            win._update_protocol_live("important sentence")
        mock_refresh.assert_called_once()
        assert "important sentence" not in win._protocol_view.toPlainText()
