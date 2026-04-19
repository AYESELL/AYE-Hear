"""HEAR-124: Meeting lifecycle FK persistence defect – deterministic regression tests.

Root-cause summary (HEAR-123 NO-GO blocker):
  1. _extract_via_ollama() returns ProtocolContent fields as ``dict`` when the LLM
     yields a nested object instead of a list → TypeError downstream.
  2. That TypeError was routed to _handle_persistence_error() which called
     session.rollback() – undoing the uncommitted meeting row.
  3. After the rollback the meeting no longer existed in the DB; all subsequent
     transcript segment inserts failed with transcript_segments_meeting_id_fkey.

The three fixes verified here:
  A. _coerce_str_list() in protocol_engine.py coerces any LLM shape to list[str].
  B. _start_meeting() commits the DB session after meeting+participants are created
     (so future rollbacks don't touch the already-durable meeting row).
  C. _rebuild_protocol_from_persistence() only routes SQLAlchemyError to
     _handle_persistence_error(); plain TypeErrors are just logged.
  D. TranscriptSegmentRepository.add() calls session.rollback() after a flush
     failure so subsequent add() calls are not blocked by "transaction rolled back".
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# A – LLM output coercion
# ---------------------------------------------------------------------------

class TestCoerceStrList:
    """_coerce_str_list must normalise all shapes the LLM might return."""

    def _fn(self, value):
        from ayehear.services.protocol_engine import _coerce_str_list
        return _coerce_str_list(value)

    def test_list_of_strings_passed_through(self):
        assert self._fn(["a", "b"]) == ["a", "b"]

    def test_plain_string_wrapped_in_list(self):
        assert self._fn("summary text") == ["summary text"]

    def test_empty_string_returns_empty_list(self):
        assert self._fn("") == []

    def test_dict_values_flattened_to_strings(self):
        result = self._fn({"k1": "v1", "k2": "v2"})
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)
        assert len(result) == 2

    def test_none_returns_empty_list(self):
        assert self._fn(None) == []

    def test_list_with_non_string_items_filtered(self):
        result = self._fn(["good", 42, None, "also good"])
        assert result == ["good", "also good"]

    def test_mixed_list_keeps_strings_only(self):
        result = self._fn(["text", {"nested": "dict"}, "other"])
        assert result == ["text", "other"]


class TestOllamaOutputCoercion:
    """_extract_via_ollama must not raise when the LLM response has non-list fields."""

    def _make_engine(self):
        from ayehear.services.protocol_engine import ProtocolEngine
        return ProtocolEngine(
            snapshot_repo=None,
            transcript_repo=None,
            ollama_base_url="http://127.0.0.1:11434",
        )

    def _patch_urlopen(self, engine, response_json: str):
        """Return a context manager that patches urllib.request.urlopen."""
        import json
        import io
        import urllib.request

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"response": response_json}).encode()

        return patch("urllib.request.urlopen", return_value=mock_resp)

    def test_dict_summary_does_not_raise(self):
        """HEAR-124 defect A: when LLM returns 'summary' as dict, no TypeError."""
        import json

        llm_payload = json.dumps({
            "summary": {"text": "Meeting über Budgetplanung"},
            "decisions": ["Budget erhöht"],
            "action_items": ["Alice: Report erstellen"],
            "open_questions": [],
        })
        engine = self._make_engine()
        with self._patch_urlopen(engine, llm_payload):
            content = engine._extract_via_ollama(["[0ms] Alice: Hallo"])
        # Must not raise; summary must be a list
        assert isinstance(content.summary, list)
        assert isinstance(content.decisions, list)
        assert isinstance(content.action_items, list)

    def test_string_action_items_do_not_raise(self):
        """action_items as plain string must not crash downstream join."""
        import json

        llm_payload = json.dumps({
            "summary": ["ok"],
            "decisions": [],
            "action_items": "Alice: Report erstellen",
            "open_questions": [],
        })
        engine = self._make_engine()
        with self._patch_urlopen(engine, llm_payload):
            content = engine._extract_via_ollama(["[0ms] Alice: Hallo"])
        assert isinstance(content.action_items, list)
        assert len(content.action_items) == 1

    def test_normal_list_output_unchanged(self):
        """Correct LLM output (list[str]) must pass through unmodified."""
        import json

        llm_payload = json.dumps({
            "summary": ["Summary line 1", "Summary line 2"],
            "decisions": ["Decision A"],
            "action_items": ["Action 1", "Action 2"],
            "open_questions": ["Question?"],
        })
        engine = self._make_engine()
        with self._patch_urlopen(engine, llm_payload):
            content = engine._extract_via_ollama(["[0ms] Alice: Text"])
        assert content.summary == ["Summary line 1", "Summary line 2"]
        assert content.decisions == ["Decision A"]
        assert content.action_items == ["Action 1", "Action 2"]
        assert content.open_questions == ["Question?"]


# ---------------------------------------------------------------------------
# B – Meeting commit after _start_meeting
# ---------------------------------------------------------------------------

def _make_window_with_mocks(qapp, *, commit_spy=None):
    """Build a MainWindow with a fully-mocked DB layer."""
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig
    from PySide6.QtWidgets import QListWidgetItem

    mock_session = MagicMock()
    if commit_spy is not None:
        mock_session.commit = commit_spy

    fake_meeting = MagicMock()
    fake_meeting.id = "test-meeting-124"

    mock_meeting_repo = MagicMock()
    mock_meeting_repo.create.return_value = fake_meeting
    mock_meeting_repo.start.return_value = fake_meeting

    mock_participant_repo = MagicMock()
    fake_participant = MagicMock()
    fake_participant.id = "participant-1"
    mock_participant_repo.add.return_value = fake_participant

    mock_transcript_repo = MagicMock()
    mock_snapshot_repo = MagicMock()

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(
            runtime_config=RuntimeConfig(),
            db_session=mock_session,
            meeting_repo=mock_meeting_repo,
            participant_repo=mock_participant_repo,
            transcript_repo=mock_transcript_repo,
            snapshot_repo=mock_snapshot_repo,
        )

    win._meeting_title.setText("Test Meeting 124")
    from PySide6.QtCore import Qt
    item = QListWidgetItem("Alice Muster | Firma")
    item.setData(Qt.ItemDataRole.UserRole, "uuid-001")
    win._speakers_list.addItem(item)

    return win, mock_session, mock_meeting_repo


class TestMeetingCommitAfterStart:
    """HEAR-124 fix B: session.commit() must be called after meeting+participants are created."""

    def test_commit_called_after_meeting_persisted(self, qapp):
        commit_spy = MagicMock()
        win, mock_session, _ = _make_window_with_mocks(qapp, commit_spy=commit_spy)

        with patch("ayehear.app.window.QMessageBox"):
            with patch.object(win, "_start_audio_pipeline", return_value="OK"):
                win._start_meeting()

        commit_spy.assert_called()

    def test_commit_not_called_when_no_db_session(self, qapp):
        """Without a DB session, commit must not be attempted."""
        from ayehear.app.window import MainWindow
        from ayehear.models.runtime import RuntimeConfig

        with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
            win = MainWindow(runtime_config=RuntimeConfig())

        from PySide6.QtWidgets import QListWidgetItem
        win._meeting_title.setText("No-DB Meeting")
        win._speakers_list.addItem(QListWidgetItem("Bob"))

        # Must not raise even though there is no session
        with patch("ayehear.app.window.QMessageBox"):
            with patch.object(win, "_start_audio_pipeline", return_value="OK"):
                win._start_meeting()  # should not crash


# ---------------------------------------------------------------------------
# C – Error routing in _rebuild_protocol_from_persistence
# ---------------------------------------------------------------------------

class TestRebuildProtocolErrorRouting:
    """HEAR-124 fix C: non-SQLAlchemy errors must not trigger session rollback."""

    def _make_window(self, qapp):
        from ayehear.app.window import MainWindow
        from ayehear.models.runtime import RuntimeConfig

        mock_session = MagicMock()
        mock_meeting_repo = MagicMock()
        mock_transcript_repo = MagicMock()
        mock_snapshot_repo = MagicMock()

        with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
            win = MainWindow(
                runtime_config=RuntimeConfig(),
                db_session=mock_session,
                meeting_repo=mock_meeting_repo,
                transcript_repo=mock_transcript_repo,
                snapshot_repo=mock_snapshot_repo,
            )
        win._active_meeting_id = "meet-routing-test"
        return win, mock_session

    def test_type_error_does_not_call_session_rollback(self, qapp):
        """TypeError from protocol engine must not trigger session.rollback()."""
        win, mock_session = self._make_window(qapp)

        with patch.object(
            win._protocol_engine,
            "generate",
            side_effect=TypeError("expected string or bytes-like object, got 'dict'"),
        ):
            win._rebuild_protocol_from_persistence()

        mock_session.rollback.assert_not_called()

    def test_sqlalchemy_error_calls_handle_persistence_error(self, qapp):
        """SQLAlchemyError must still be routed to the persistence error handler."""
        from sqlalchemy.exc import SQLAlchemyError

        win, mock_session = self._make_window(qapp)

        with patch.object(
            win._protocol_engine,
            "generate",
            side_effect=SQLAlchemyError("connection lost"),
        ):
            with patch.object(win, "_handle_persistence_error") as mock_handler:
                win._rebuild_protocol_from_persistence()

        mock_handler.assert_called_once()
        call_args = mock_handler.call_args[0]
        assert "Protocol rebuild failed" in call_args[0]

    def test_type_error_does_not_reload_persistence_layer(self, qapp):
        """A non-DB TypeError must not trigger _reload_persistence_layer."""
        win, mock_session = self._make_window(qapp)

        with patch.object(
            win._protocol_engine,
            "generate",
            side_effect=TypeError("expected string, got dict"),
        ):
            with patch.object(win, "_reload_persistence_layer") as mock_reload:
                win._rebuild_protocol_from_persistence()

        mock_reload.assert_not_called()


# ---------------------------------------------------------------------------
# D – TranscriptSegmentRepository rollback on flush failure
# ---------------------------------------------------------------------------

class TestSegmentRepoRollbackOnFlushFailure:
    """HEAR-124 fix D: flush failure must trigger session.rollback() to clear error state."""

    def _make_repo(self):
        from ayehear.storage.repositories import TranscriptSegmentRepository

        mock_session = MagicMock()
        repo = TranscriptSegmentRepository(mock_session)
        return repo, mock_session

    def test_rollback_called_when_flush_raises(self):
        repo, mock_session = self._make_repo()
        mock_session.flush.side_effect = Exception("FK violation")

        with pytest.raises(Exception, match="FK violation"):
            repo.add(
                meeting_id="meet-1",
                start_ms=0,
                end_ms=1000,
                speaker_name="Alice",
                text="Hello",
            )

        mock_session.rollback.assert_called_once()

    def test_second_add_can_succeed_after_flush_failure(self):
        """After a flush failure, a subsequent add() must not be blocked by rolled-back state."""
        repo, mock_session = self._make_repo()

        call_count = [0]

        def flush_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("FK violation on first call")
            # Second call succeeds

        mock_session.flush.side_effect = flush_side_effect
        from ayehear.storage.orm import TranscriptSegment
        mock_session.add = MagicMock()

        # First add fails
        with pytest.raises(Exception):
            repo.add(meeting_id="meet-1", start_ms=0, end_ms=1000, text="Fail")

        # Session should be rolled back now
        mock_session.rollback.assert_called_once()
        mock_session.rollback.reset_mock()
        mock_session.flush.side_effect = None  # Allow second flush to succeed

        from ayehear.storage.orm import TranscriptSegment as _Seg
        mock_session.flush = MagicMock()  # Clean mock for second call
        result = repo.add(meeting_id="meet-1", start_ms=1000, end_ms=2000, text="OK")
        mock_session.flush.assert_called_once()

    def test_no_rollback_on_successful_add(self):
        """rollback must NOT be called on a successful add."""
        repo, mock_session = self._make_repo()
        mock_session.flush.side_effect = None

        from ayehear.storage.orm import TranscriptSegment
        repo.add(meeting_id="meet-1", start_ms=0, end_ms=1000, text="OK")

        mock_session.rollback.assert_not_called()


# ---------------------------------------------------------------------------
# E – End-to-end: meeting survives protocol rebuild TypeError
# ---------------------------------------------------------------------------

class TestMeetingDurableAfterProtocolError:
    """Integration scenario: meeting committed before protocol rebuild error occurs."""

    def test_meeting_id_preserved_after_type_error_in_rebuild(self, qapp):
        """After a TypeError in protocol rebuild, _active_meeting_id must still be set."""
        from ayehear.app.window import MainWindow
        from ayehear.models.runtime import RuntimeConfig
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt

        mock_session = MagicMock()
        fake_meeting = MagicMock()
        fake_meeting.id = "durable-meeting-001"

        mock_meeting_repo = MagicMock()
        mock_meeting_repo.create.return_value = fake_meeting
        mock_meeting_repo.start.return_value = fake_meeting

        mock_participant_repo = MagicMock()
        mock_participant_repo.add.return_value = MagicMock(id="p-001")

        mock_transcript_repo = MagicMock()
        mock_snapshot_repo = MagicMock()

        with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
            win = MainWindow(
                runtime_config=RuntimeConfig(),
                db_session=mock_session,
                meeting_repo=mock_meeting_repo,
                participant_repo=mock_participant_repo,
                transcript_repo=mock_transcript_repo,
                snapshot_repo=mock_snapshot_repo,
            )

        win._meeting_title.setText("Durable Meeting")
        item = QListWidgetItem("Alice")
        item.setData(Qt.ItemDataRole.UserRole, "uuid-alice")
        win._speakers_list.addItem(item)

        with patch("ayehear.app.window.QMessageBox"):
            with patch.object(win, "_start_audio_pipeline", return_value="OK"):
                win._start_meeting()

        assert win._active_meeting_id == "durable-meeting-001"
        # commit must have been called once after meeting creation
        mock_session.commit.assert_called()

        # Now simulate a protocol rebuild TypeError (the HEAR-123 trigger)
        with patch.object(
            win._protocol_engine,
            "generate",
            side_effect=TypeError("expected string or bytes-like object, got 'dict'"),
        ):
            win._rebuild_protocol_from_persistence()

        # meeting_id must still be set — rollback must NOT have cleared it
        assert win._active_meeting_id == "durable-meeting-001"
        # session.rollback must NOT have been called by the TypeError path
        # (commit was called during _start_meeting but rollback must stay silent)
        rollback_calls = mock_session.rollback.call_count
        assert rollback_calls == 0, (
            f"session.rollback() was called {rollback_calls} time(s) after TypeError; "
            "expected 0 — TypeError is not a DB error."
        )
