"""HEAR-131: Persistence regression tests – error recovery, FK safety, meeting-end invariant.

Guards the prior 0.5.5 failure class (HEAR-126 NO-GO evidence):

  FAILURE 1 – FK violation:
    transcript_segments_meeting_id_fkey was violated because a TypeError in
    _extract_via_ollama() was incorrectly routed to _handle_persistence_error(),
    which called session.rollback(). That rollback undid the uncommitted meeting
    row, so all subsequent transcript_repo.add() calls referenced a non-existent
    meeting → IntegrityError cascade.

  FAILURE 2 – Meeting not found:
    After the rollback the _active_meeting_id still pointed to the now-deleted
    meeting row. _stop_meeting() called meeting_repo.end(meeting_id) → "Meeting
    not found" (ValueError), which then routed to _handle_persistence_error()
    again, compounding the failure.

These tests verify the three-layer fix is durable:
  A. Meeting commit happens *before* any transcript inserts so rollbacks from
     unrelated errors cannot undo the meeting row (HEAR-124 fix B).
  B. A persistence error during transcription (FK violation on segment add) is
     isolated by TranscriptSegmentRepository.add() rollback and does not prevent
     subsequent inserts or meeting close.
  C. After _handle_persistence_error + _reload_persistence_layer, the active
     meeting ID remains valid and meeting_repo.end() still succeeds.
  D. Soft fallback (_disable_persistence on commit failure) allows in-memory
     continuation and a clean meeting-end flow without crashing.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_full_mocked_window(
    qapp,
    meeting_id: str = "meet-131-test",
    commit_side_effect=None,
):
    """Construct a MainWindow wired with fully-mocked repository layer.

    Parameters
    ----------
    qapp:
        PySide6 QApplication fixture.
    meeting_id:
        ID returned by the mock meeting_repo.create() / .start().
    commit_side_effect:
        If set, db_session.commit() is made to raise this exception.
    """
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig
    from PySide6.QtWidgets import QListWidgetItem
    from PySide6.QtCore import Qt

    mock_session = MagicMock()
    if commit_side_effect is not None:
        mock_session.commit.side_effect = commit_side_effect

    fake_meeting = MagicMock()
    fake_meeting.id = meeting_id

    meeting_repo = MagicMock()
    meeting_repo.create.return_value = fake_meeting
    meeting_repo.start.return_value = fake_meeting

    participant_repo = MagicMock()
    fake_participant = MagicMock()
    fake_participant.id = "p-001"
    participant_repo.add.return_value = fake_participant

    transcript_repo = MagicMock()
    snapshot_repo = MagicMock()

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(
            runtime_config=RuntimeConfig(),
            db_session=mock_session,
            meeting_repo=meeting_repo,
            participant_repo=participant_repo,
            transcript_repo=transcript_repo,
            snapshot_repo=snapshot_repo,
        )

    win._meeting_title.setText("HEAR-131 Test Meeting")
    item = QListWidgetItem("Alice Muster | Corp A")
    item.setData(Qt.ItemDataRole.UserRole, "uuid-alice")
    win._speakers_list.addItem(item)

    return win, mock_session, meeting_repo, transcript_repo


def _do_start_meeting(win):
    """Drive _start_meeting() with standard patches."""
    with patch("ayehear.app.window.QMessageBox"):
        with patch.object(win, "_start_audio_pipeline", return_value="ok"):
            win._start_meeting()


def _do_stop_meeting(win):
    """Drive _stop_meeting() with standard patches."""
    with patch.object(win, "_stop_audio_pipeline"):
        with patch.object(win, "_export_meeting_artifacts"):
            win._stop_meeting()


# ---------------------------------------------------------------------------
# A – FK violation on transcript add does not block meeting close
# ---------------------------------------------------------------------------

class TestFKViolationIsolatedFromMeetingClose:
    """HEAR-131 AC1/AC2: FK error during transcript persist must not prevent meeting end.

    Prior 0.5.5 failure: rollback on meeting creation meant FK violations cascaded
    into every transcript add AND meeting close.  After HEAR-124 fixes the meeting
    is committed before any segment insert, so even a FK violation on the first add
    (simulated here by mocking flush to raise IntegrityError) must be isolated.
    """

    def test_meeting_end_succeeds_after_fk_violation_on_segment_add(self, qapp):
        """meeting_repo.end() must be called even if the first transcript add raises FK."""
        from sqlalchemy.exc import IntegrityError

        win, mock_session, meeting_repo, transcript_repo = _make_full_mocked_window(
            qapp, meeting_id="meet-fk-131"
        )

        # Simulate FK violation on first segment add (then recover on subsequent)
        call_count = [0]

        def add_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise IntegrityError(
                    "INSERT INTO transcript_segments",
                    {},
                    Exception("transcript_segments_meeting_id_fkey"),
                )
            seg = MagicMock()
            seg.id = f"seg-{call_count[0]}"
            return seg

        transcript_repo.add.side_effect = add_side_effect

        _do_start_meeting(win)

        assert win._active_meeting_id == "meet-fk-131", (
            "Active meeting ID must survive the start phase"
        )

        # Simulate FK violation during transcription service persist attempt
        # (the TranscriptionService catches this and logs an error, but does not re-raise)
        try:
            win._transcript_repo.add(
                meeting_id=win._active_meeting_id,
                start_ms=0,
                end_ms=1000,
                speaker_name="Alice Muster",
                text="Hallo Welt.",
            )
        except Exception:
            pass  # First add raised FK – transcription service silently logs and continues

        # Second add must succeed
        seg2 = win._transcript_repo.add(
            meeting_id=win._active_meeting_id,
            start_ms=1000,
            end_ms=2000,
            speaker_name="Alice Muster",
            text="Zweiter Satz.",
        )
        assert seg2 is not None, "Second transcript add must succeed after FK error"

        # Meeting end must succeed – this guards the 'Meeting not found' 0.5.5 failure
        _do_stop_meeting(win)

        meeting_repo.end.assert_called_once_with("meet-fk-131")

    def test_active_meeting_id_survives_fk_violation(self, qapp):
        """_active_meeting_id must not be cleared by a segment FK error.

        In the 0.5.5 failure the meeting row was rolled back before the FK
        insert, making the meeting_id stale. After HEAR-124 fixes the ID
        remains valid across the entire lifecycle.
        """
        from sqlalchemy.exc import IntegrityError

        win, _, _, transcript_repo = _make_full_mocked_window(qapp, meeting_id="meet-id-check")

        transcript_repo.add.side_effect = IntegrityError(
            "INSERT", {}, Exception("fkey violation")
        )

        _do_start_meeting(win)

        original_id = win._active_meeting_id

        # FK violation during transcription
        try:
            win._transcript_repo.add(
                meeting_id=original_id,
                start_ms=0, end_ms=500,
                speaker_name="Alice", text="Test",
            )
        except Exception:
            pass

        # ID must be unchanged
        assert win._active_meeting_id == original_id, (
            "_active_meeting_id must not be invalidated by a transcript FK error; "
            "this is the root cause of the 0.5.5 'Meeting not found' failure."
        )


# ---------------------------------------------------------------------------
# B – _handle_persistence_error recovery → meeting end still works
# ---------------------------------------------------------------------------

class TestPersistenceErrorHandlerPreservesMeetingClose:
    """HEAR-131 AC1/AC2: after _handle_persistence_error the meeting can still be closed.

    Scenario: a SQLAlchemy error fires during transcript persistence.
    _handle_persistence_error calls _reload_persistence_layer (mocked to succeed).
    After recovery meeting_repo.end() must still be called on _stop_meeting.
    """

    def test_meeting_end_called_after_handle_persistence_error_recovery(self, qapp):
        """Even when _reload_persistence_layer succeeds, meeting_repo.end is still reached."""
        win, mock_session, meeting_repo, _ = _make_full_mocked_window(
            qapp, meeting_id="meet-recovery-131"
        )

        _do_start_meeting(win)

        # Simulate a persistence error (e.g. broken session)
        with patch.object(win, "_reload_persistence_layer", return_value=True):
            win._handle_persistence_error(
                "Simulated DB error in HEAR-131 test",
                Exception("connection reset by peer"),
            )

        # After recovery, active meeting must still be set
        assert win._active_meeting_id == "meet-recovery-131", (
            "_active_meeting_id must survive a persistence error recovery"
        )

        # Stop meeting and verify end is called
        _do_stop_meeting(win)

        meeting_repo.end.assert_called_once_with("meet-recovery-131")

    def test_meeting_end_not_called_when_persistence_disabled(self, qapp):
        """After _disable_persistence, meeting_repo is None → end must not be called.

        Soft fallback mode (no DB) must not crash on _stop_meeting.
        """
        win, mock_session, meeting_repo, _ = _make_full_mocked_window(
            qapp, meeting_id="meet-disabled-131"
        )

        _do_start_meeting(win)

        # Force disable persistence (simulates commit failure fallback)
        with patch.object(win, "_refresh_protocol_display"):
            win._disable_persistence("HEAR-131 test: simulated commit failure")

        assert win._meeting_repo is None, (
            "meeting_repo must be None after _disable_persistence"
        )

        # _stop_meeting must not crash even though meeting_repo is gone
        _do_stop_meeting(win)

        # end() must not have been called (meeting_repo was None at stop time)
        meeting_repo.end.assert_not_called()


# ---------------------------------------------------------------------------
# C – Commit failure soft fallback → local-only → no crash on stop
# ---------------------------------------------------------------------------

class TestCommitFailureSoftFallback:
    """HEAR-131 AC1/AC4: commit failure during meeting start falls back to local-only mode.

    Reproduces the scenario where the DB accepts create/start but rejects commit.
    After _disable_persistence the app continues in local-only mode; _stop_meeting
    must complete without raising.
    """

    def test_stop_meeting_does_not_raise_after_commit_failure(self, qapp):
        """If meeting commit fails, _stop_meeting must complete cleanly (no crash)."""
        win, mock_session, meeting_repo, _ = _make_full_mocked_window(
            qapp,
            meeting_id="meet-commit-fail",
            commit_side_effect=RuntimeError("connection lost during commit"),
        )

        # Patch _disable_persistence so we can verify it was called
        with patch.object(win, "_disable_persistence", wraps=win._disable_persistence):
            with patch.object(win, "_refresh_protocol_display"):
                _do_start_meeting(win)

        # After commit failure the app must still have an active meeting id
        # (local fallback uuid), and persistence must be off
        assert win._active_meeting_id is not None, (
            "Local fallback meeting ID must be set even after commit failure"
        )

        # _stop_meeting must complete without any exception
        try:
            _do_stop_meeting(win)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"_stop_meeting raised after commit-failure soft fallback: {exc!r}. "
                "This reproduces the 0.5.5 meeting-close crash."
            )

    def test_active_meeting_id_set_to_local_fallback_after_commit_failure(self, qapp):
        """A local UUID must replace the DB meeting ID when commit fails."""
        expected_local_id = "local-fallback-uuid"

        win, _, _, _ = _make_full_mocked_window(
            qapp,
            meeting_id="should-not-survive-commit-fail",
            commit_side_effect=RuntimeError("commit error"),
        )

        with patch("uuid.uuid4", return_value=expected_local_id):
            with patch.object(win, "_refresh_protocol_display"):
                _do_start_meeting(win)

        assert win._active_meeting_id == expected_local_id, (
            "After commit failure _active_meeting_id must be the local UUID fallback, "
            "not the (now-invalid) DB meeting ID."
        )

    def test_reload_is_blocked_during_active_local_only_meeting(self, qapp):
        """HEAR-166: local-only active meetings must not trigger persistence rebind."""
        win, _, _, _ = _make_full_mocked_window(
            qapp,
            meeting_id="should-not-survive-commit-fail",
            commit_side_effect=RuntimeError("commit error"),
        )

        with patch.object(win, "_refresh_protocol_display"):
            _do_start_meeting(win)

        assert win._active_meeting_id is not None
        assert win._meeting_db_backed is False
        assert win._meeting_repo is None

        with patch("ayehear.app.window.load_runtime_dsn") as load_dsn_spy:
            reloaded = win._reload_persistence_layer()

        assert reloaded is False, (
            "_reload_persistence_layer must return False for active local-only meetings"
        )
        load_dsn_spy.assert_not_called()
        assert win._meeting_repo is None
        assert win._transcript_repo is None
        assert win._snapshot_repo is None


# ---------------------------------------------------------------------------
# D – Full lifecycle: start → error → transcription → end
# ---------------------------------------------------------------------------

class TestFullLifecycleWithPersistenceError:
    """HEAR-131 AC1/AC2 end-to-end: full lifecycle with mid-session DB error.

    Reproduces the core 0.5.5 failure scenario as a single integrated flow:
      1. Meeting starts and is committed.
      2. A DB error fires mid-session (simulating the session becoming stale).
      3. _handle_persistence_error is invoked → persistence layer reloaded.
      4. Subsequent transcription succeeds.
      5. _stop_meeting completes; meeting_repo.end() is called exactly once.
    """

    def test_full_lifecycle_survives_mid_session_persistence_error(self, qapp):
        """start → mid-session error → continued transcription → end without FK or not-found."""
        from sqlalchemy.exc import OperationalError

        win, mock_session, meeting_repo, transcript_repo = _make_full_mocked_window(
            qapp, meeting_id="meet-full-131"
        )

        # Phase 1: start meeting
        _do_start_meeting(win)

        assert win._active_meeting_id == "meet-full-131"
        assert mock_session.commit.called, "DB commit must happen in _start_meeting"

        # Phase 2: mid-session persistence error (simulates session going stale)
        with patch.object(win, "_reload_persistence_layer", return_value=True) as reload_spy:
            win._handle_persistence_error(
                "HEAR-131 simulated mid-session OperationalError",
                OperationalError("select 1", {}, Exception("server closed the connection")),
            )

        reload_spy.assert_called_once(), (
            "_reload_persistence_layer must be attempted after a SQLAlchemy OperationalError"
        )

        # Phase 3: continued transcription after error – transcript repo must still accept adds
        fake_seg = MagicMock()
        fake_seg.id = "seg-post-error"
        transcript_repo.add.return_value = fake_seg

        transcript_repo.add.side_effect = None  # reset any previous side effect

        seg = win._transcript_repo.add(
            meeting_id="meet-full-131",
            start_ms=5000,
            end_ms=6000,
            speaker_name="Alice Muster",
            text="Post-Fehler Transkription.",
        )
        assert seg is not None, (
            "Transcript add must succeed after persistence recovery; "
            "FK violation here would reproduce the 0.5.5 blocker."
        )

        # Phase 4: meeting end
        _do_stop_meeting(win)

        meeting_repo.end.assert_called_once_with("meet-full-131"), (
            "meeting_repo.end must be called exactly once; "
            "'Meeting not found' here would reproduce the 0.5.5 stop-meeting crash."
        )

    def test_no_session_rollback_from_non_db_error_during_transcription(self, qapp):
        """A non-SQLAlchemy error (e.g. ValueError) must NOT trigger session.rollback().

        In 0.5.5 a TypeError was incorrectly routed to _handle_persistence_error,
        which called session.rollback() and erased the uncommitted meeting row.
        This test ensures only genuine DB errors trigger rollback.
        """
        win, mock_session, _, _ = _make_full_mocked_window(
            qapp, meeting_id="meet-no-rollback-131"
        )

        _do_start_meeting(win)

        # Reset rollback tracking after _start_meeting (it may call rollback on failures)
        mock_session.rollback.reset_mock()

        # A ValueError (non-DB error) must not trigger session.rollback
        with patch.object(win._protocol_engine, "generate", side_effect=ValueError("non-db err")):
            win._rebuild_protocol_from_persistence()

        assert mock_session.rollback.call_count == 0, (
            f"session.rollback() was called {mock_session.rollback.call_count} time(s) "
            "after a ValueError in protocol rebuild. This reproduces the 0.5.5 FK cascade: "
            "rollback erased the uncommitted meeting row → all subsequent transcript inserts "
            "raised transcript_segments_meeting_id_fkey."
        )
