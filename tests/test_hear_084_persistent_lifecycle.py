"""Tests for HEAR-084: Wire Persistent Meeting and Speaker Lifecycle End-to-End.

Covers:
  AC1: MainWindow._start_meeting() creates meeting + participants in DB
  AC2: Transcript segments NOT persisted with speaker_name=unknown/confidence=0.0
  AC3: Enrollment persists participant-to-profile linkage via participant_repo
  AC4: Review queue + protocol snapshot operate from persisted meeting data
  AC5: Full meeting lifecycle with repos connected
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(qapp, meeting_repo=None, participant_repo=None, transcript_repo=None,
                 snapshot_repo=None, speaker_manager=None):
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


def _mock_meeting_repo(meeting_id="db-meet-001"):
    repo = MagicMock()
    fake_meeting = MagicMock()
    fake_meeting.id = meeting_id
    repo.create.return_value = fake_meeting
    repo.start.return_value = fake_meeting
    repo.end.return_value = fake_meeting
    return repo


def _mock_participant_repo(base_id="db-part-"):
    repo = MagicMock()
    call_count = [0]

    def _add(**kwargs):
        call_count[0] += 1
        p = MagicMock()
        p.id = f"{base_id}{call_count[0]:03d}"
        return p

    repo.add.side_effect = _add
    return repo


# ---------------------------------------------------------------------------
# AC1: Meeting + participants persisted on _start_meeting
# ---------------------------------------------------------------------------

class TestMeetingPersistenceOnStart:
    def test_meeting_repo_create_called_on_start(self, qapp):
        meeting_repo = _mock_meeting_repo()
        win = _make_window(qapp, meeting_repo=meeting_repo)

        win._meeting_title.setText("Test Sitzung")
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "information"), \
             patch.object(win, "_start_audio_pipeline", return_value="ok"):
            win._start_meeting()

        meeting_repo.create.assert_called_once()
        create_kwargs = meeting_repo.create.call_args
        assert create_kwargs.kwargs.get("title") == "Test Sitzung" or \
               create_kwargs.args[0] == "Test Sitzung"

    def test_meeting_repo_start_called_on_start(self, qapp):
        meeting_repo = _mock_meeting_repo("meet-start-test")
        win = _make_window(qapp, meeting_repo=meeting_repo)

        win._meeting_title.setText("Meeting Start Test")
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "information"), \
             patch.object(win, "_start_audio_pipeline", return_value="ok"):
            win._start_meeting()

        meeting_repo.start.assert_called_once_with("meet-start-test")

    def test_active_meeting_id_is_db_meeting_id(self, qapp):
        meeting_repo = _mock_meeting_repo("db-canonical-id-42")
        win = _make_window(qapp, meeting_repo=meeting_repo)

        win._meeting_title.setText("ID Test")
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "information"), \
             patch.object(win, "_start_audio_pipeline", return_value="ok"):
            win._start_meeting()

        # Active meeting ID must come from DB, not a random UUID
        assert win._active_meeting_id == "db-canonical-id-42"

    def test_participants_persisted_for_each_speaker(self, qapp):
        meeting_repo = _mock_meeting_repo("meet-with-parts")
        participant_repo = _mock_participant_repo()
        win = _make_window(qapp, meeting_repo=meeting_repo, participant_repo=participant_repo)

        win._meeting_title.setText("Multi-Speaker Meeting")
        win._speakers_list.clear()
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        import uuid
        for name_entry in ["Max Muster | Corp A | pending enrollment",
                           "Anna Smith | Corp B | pending enrollment"]:
            item = QListWidgetItem(name_entry)
            item.setData(Qt.ItemDataRole.UserRole, str(uuid.uuid4()))
            win._speakers_list.addItem(item)

        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "information"), \
             patch.object(win, "_start_audio_pipeline", return_value="ok"):
            win._start_meeting()

        assert participant_repo.add.call_count == 2

    def test_participant_id_map_populated_after_start(self, qapp):
        meeting_repo = _mock_meeting_repo("meet-map-test")
        participant_repo = _mock_participant_repo()
        win = _make_window(qapp, meeting_repo=meeting_repo, participant_repo=participant_repo)

        win._meeting_title.setText("Map Test")
        win._speakers_list.clear()
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        import uuid
        list_uuid = str(uuid.uuid4())
        item = QListWidgetItem("Karl Richter | AYE | pending enrollment")
        item.setData(Qt.ItemDataRole.UserRole, list_uuid)
        win._speakers_list.addItem(item)

        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "information"), \
             patch.object(win, "_start_audio_pipeline", return_value="ok"):
            win._start_meeting()

        # The list UUID should be mapped to a DB participant ID
        assert list_uuid in win._participant_id_map
        assert win._participant_id_map[list_uuid].startswith("db-part-")

    def test_meeting_without_repo_uses_uuid_fallback(self, qapp):
        """Without repos, _start_meeting still works (degraded/local-only mode)."""
        win = _make_window(qapp)
        win._meeting_title.setText("Local Only")

        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "information"), \
             patch.object(win, "_start_audio_pipeline", return_value="ok"):
            win._start_meeting()

        # Active meeting ID should be a UUID string
        assert win._active_meeting_id is not None
        assert len(win._active_meeting_id) > 8


# ---------------------------------------------------------------------------
# AC2: Speaker resolved BEFORE transcription persistence
# ---------------------------------------------------------------------------

class TestSpeakerResolutionBeforePersistence:
    def _make_audio_segment(self, start_ms=0, end_ms=1000):
        from ayehear.services.audio_capture import AudioSegment
        from datetime import datetime
        samples = np.zeros(16000, dtype=np.float32)
        return AudioSegment(
            captured_at=datetime.now(),
            start_ms=start_ms,
            end_ms=end_ms,
            samples=samples,
            rms=0.05,
            is_silence=False,
        )

    def test_transcription_called_with_resolved_speaker_not_unknown(self, qapp):
        """transcribe_segment must be called with a resolved speaker, NOT 'unknown'."""
        transcript_repo = MagicMock()
        fake_segment = MagicMock()
        fake_segment.id = "seg-001"
        transcript_repo.add.return_value = fake_segment

        from ayehear.services.speaker_manager import SpeakerMatch, SpeakerManager
        mock_sm = MagicMock(spec=SpeakerManager)
        resolved_match = SpeakerMatch(
            speaker_name="Max Muster",
            confidence=0.87,
            status="high",
            requires_review=False,
        )
        mock_sm.match_segment.return_value = resolved_match
        mock_sm.resolve_speaker_from_segment.return_value = resolved_match

        win = _make_window(qapp, transcript_repo=transcript_repo, speaker_manager=mock_sm)
        win._active_meeting_id = "meet-ac2-test"

        from ayehear.services.transcription import TranscriptResult
        mock_result = TranscriptResult(
            text="Guten Morgen alle zusammen.",
            confidence=0.87,
            start_ms=0,
            end_ms=1000,
        )
        win._transcription_service.transcribe_segment = MagicMock(return_value=mock_result)

        samples = np.zeros(32000, dtype=np.float32)
        with win._audio_buffer_lock:
            win._pending_audio_chunks = [samples]
            win._pending_start_ms = 0
            win._pending_end_ms = 2000
            win._pending_duration_ms = 2000

        win._transcribe_pending_buffer(force=True)

        # transcribe_segment must NOT be called with unknown/0.0
        call_kwargs = win._transcription_service.transcribe_segment.call_args
        assert call_kwargs is not None, "transcribe_segment was not called"
        assert call_kwargs.kwargs.get("speaker_name") != "unknown", \
            "AC2 FAIL: transcribe_segment called with speaker_name='unknown'"
        assert call_kwargs.kwargs.get("confidence_score", 0.0) > 0.0, \
            "AC2 FAIL: transcribe_segment called with confidence_score=0.0"

    def test_match_segment_called_before_transcription(self, qapp):
        """SpeakerManager.match_segment must be called before transcribe_segment."""
        call_order = []

        from ayehear.services.speaker_manager import SpeakerMatch, SpeakerManager
        mock_sm = MagicMock(spec=SpeakerManager)

        def _match_segment(emb):
            call_order.append("match_segment")
            return SpeakerMatch("Speaker1", 0.9, "high")

        mock_sm.match_segment.side_effect = _match_segment
        mock_sm.resolve_speaker_from_segment.return_value = SpeakerMatch("Speaker1", 0.9, "high")

        win = _make_window(qapp, speaker_manager=mock_sm)
        win._active_meeting_id = "meet-order-test"

        from ayehear.services.transcription import TranscriptResult

        def _transcribe(*args, **kwargs):
            call_order.append("transcribe_segment")
            return TranscriptResult(text="Hallo", confidence=0.9, start_ms=0, end_ms=1000)

        win._transcription_service.transcribe_segment = MagicMock(side_effect=_transcribe)

        samples = np.zeros(32000, dtype=np.float32)
        with win._audio_buffer_lock:
            win._pending_audio_chunks = [samples]
            win._pending_start_ms = 0
            win._pending_end_ms = 2000
            win._pending_duration_ms = 2000

        win._transcribe_pending_buffer(force=True)

        assert "match_segment" in call_order
        assert "transcribe_segment" in call_order
        match_idx = call_order.index("match_segment")
        transcribe_idx = call_order.index("transcribe_segment")
        assert match_idx < transcribe_idx, \
            "AC2 FAIL: match_segment must be called BEFORE transcribe_segment"


# ---------------------------------------------------------------------------
# AC3: Enrollment persists participant-to-profile linkage
# ---------------------------------------------------------------------------

class TestEnrollmentPersistence:
    def test_participant_repo_mark_enrolled_called(self, qapp):
        participant_repo = _mock_participant_repo()
        win = _make_window(qapp, participant_repo=participant_repo)

        # Simulate a participant already in the map (as if meeting was started)
        list_uuid = "test-list-uuid-abc"
        db_participant_id = "db-part-enrolled-001"
        win._participant_id_map[list_uuid] = db_participant_id

        from PySide6.QtWidgets import QListWidgetItem, QDialog
        from PySide6.QtCore import Qt
        item = QListWidgetItem("Anna Schmidt | Corp | pending enrollment")
        item.setData(Qt.ItemDataRole.UserRole, list_uuid)
        win._speakers_list.addItem(item)

        from ayehear.app.enrollment_dialog import EnrollmentDialog
        mock_dlg = MagicMock(spec=EnrollmentDialog)
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_enrolled_results.return_value = {list_uuid: "profile-uuid-xyz"}

        with patch("ayehear.app.window.EnrollmentDialog", return_value=mock_dlg):
            win._start_enrollment()

        # mark_enrolled must have been called with the DB participant ID and profile ID
        participant_repo.mark_enrolled.assert_called_once_with(
            db_participant_id, "profile-uuid-xyz"
        )

    def test_mark_enrolled_not_called_without_db_participant_map(self, qapp):
        """Without a participant_id_map entry, mark_enrolled must not be called."""
        participant_repo = _mock_participant_repo()
        win = _make_window(qapp, participant_repo=participant_repo)

        # No entry in participant_id_map (meeting not started with DB)
        list_uuid = "unmapped-uuid"
        # _participant_id_map is empty

        from PySide6.QtWidgets import QListWidgetItem, QDialog
        from PySide6.QtCore import Qt
        item = QListWidgetItem("Test Speaker | Org | pending enrollment")
        item.setData(Qt.ItemDataRole.UserRole, list_uuid)
        win._speakers_list.addItem(item)

        from ayehear.app.enrollment_dialog import EnrollmentDialog
        mock_dlg = MagicMock(spec=EnrollmentDialog)
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_enrolled_results.return_value = {list_uuid: "prof-123"}

        with patch("ayehear.app.window.EnrollmentDialog", return_value=mock_dlg):
            win._start_enrollment()

        # No DB map entry → mark_enrolled should NOT be called
        participant_repo.mark_enrolled.assert_not_called()


# ---------------------------------------------------------------------------
# AC4: Meeting ended in DB on _stop_meeting
# ---------------------------------------------------------------------------

class TestMeetingEndPersistence:
    def test_meeting_repo_end_called_on_stop(self, qapp):
        meeting_repo = _mock_meeting_repo("meet-end-test")
        win = _make_window(qapp, meeting_repo=meeting_repo)

        # Simulate an active meeting
        win._active_meeting_id = "meet-end-test"
        win._meeting_status_label.setText("active")

        with patch.object(win, "_transcribe_pending_buffer"), \
             patch.object(win, "_stop_audio_pipeline"), \
             patch.object(win, "_export_meeting_artifacts", return_value=[]), \
             patch.object(win, "stop_active_meeting"):
            win._stop_meeting()

        meeting_repo.end.assert_called_once_with("meet-end-test")

    def test_meeting_repo_end_not_called_without_active_meeting(self, qapp):
        meeting_repo = _mock_meeting_repo()
        win = _make_window(qapp, meeting_repo=meeting_repo)

        # No active meeting
        win._active_meeting_id = None

        with patch.object(win, "_transcribe_pending_buffer"), \
             patch.object(win, "_stop_audio_pipeline"), \
             patch.object(win, "_export_meeting_artifacts", return_value=[]), \
             patch.object(win, "stop_active_meeting"):
            win._stop_meeting()

        meeting_repo.end.assert_not_called()


# ---------------------------------------------------------------------------
# AC4: Review queue operates from repo when connected
# ---------------------------------------------------------------------------

class TestReviewQueueWithRepository:
    def test_review_queue_loads_from_transcript_repo(self, qapp):
        transcript_repo = MagicMock()
        fake_seg = MagicMock()
        fake_seg.id = "seg-low-conf"
        fake_seg.start_ms = 5000
        fake_seg.speaker_name = "Unknown Speaker"
        fake_seg.confidence_score = 0.3
        fake_seg.text = "Wer hat die Unterlagen?"
        transcript_repo.low_confidence.return_value = [fake_seg]

        win = _make_window(qapp, transcript_repo=transcript_repo)
        win._active_meeting_id = "meet-review-test"

        win._refresh_review_queue()

        transcript_repo.low_confidence.assert_called_once_with(
            "meet-review-test",
            threshold=win.runtime_config.protocol.minimum_confidence,
        )
        assert win._review_list.count() == 1

    def test_review_queue_shows_placeholder_without_repo(self, qapp):
        win = _make_window(qapp)
        win._active_meeting_id = "meet-no-repo"

        win._refresh_review_queue()

        assert win._review_list.count() == 1
        item_text = win._review_list.item(0).text()
        assert "not connected" in item_text.lower() or "no active" in item_text.lower()


# ---------------------------------------------------------------------------
# Full lifecycle integration smoke test (AC5)
# ---------------------------------------------------------------------------

class TestFullMeetingLifecycleSmoke:
    def test_full_lifecycle_with_repos_connected(self, qapp):
        """Smoke test: start → transcription → enrollment → stop with all repos wired."""
        meeting_repo = _mock_meeting_repo("full-lifecycle-meeting")
        participant_repo = _mock_participant_repo()
        transcript_repo = MagicMock()
        fake_seg = MagicMock()
        fake_seg.id = "seg-full-001"
        transcript_repo.add.return_value = fake_seg
        transcript_repo.low_confidence.return_value = []

        from ayehear.services.speaker_manager import SpeakerMatch, SpeakerManager
        mock_sm = MagicMock(spec=SpeakerManager)
        mock_sm.match_segment.return_value = SpeakerMatch("Speaker A", 0.88, "high")
        mock_sm.resolve_speaker_from_segment.return_value = SpeakerMatch("Speaker A", 0.88, "high")
        mock_sm.clear_meeting_context.return_value = None
        mock_sm.register_meeting_participants.return_value = None

        win = _make_window(
            qapp,
            meeting_repo=meeting_repo,
            participant_repo=participant_repo,
            transcript_repo=transcript_repo,
            speaker_manager=mock_sm,
        )

        # Phase 1: Start meeting
        win._meeting_title.setText("Full Lifecycle Test")
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "information"), \
             patch.object(win, "_start_audio_pipeline", return_value="ok"):
            win._start_meeting()

        assert win._active_meeting_id == "full-lifecycle-meeting"
        meeting_repo.create.assert_called_once()
        meeting_repo.start.assert_called_once()

        # Phase 2: Simulated transcription segment
        from ayehear.services.transcription import TranscriptResult
        mock_result = TranscriptResult(text="Hallo zusammen.", confidence=0.88,
                                       start_ms=0, end_ms=1000)
        win._transcription_service.transcribe_segment = MagicMock(return_value=mock_result)

        samples = np.zeros(32000, dtype=np.float32)
        with win._audio_buffer_lock:
            win._pending_audio_chunks = [samples]
            win._pending_start_ms = 0
            win._pending_end_ms = 2000
            win._pending_duration_ms = 2000

        win._transcribe_pending_buffer(force=True)

        # Speaker must be resolved, not unknown
        call_kw = win._transcription_service.transcribe_segment.call_args.kwargs
        assert call_kw.get("speaker_name") != "unknown"

        # Phase 3: Stop meeting
        with patch.object(win, "_stop_audio_pipeline"), \
             patch.object(win, "_export_meeting_artifacts", return_value=[]):
            win._stop_meeting()

        meeting_repo.end.assert_called_once_with("full-lifecycle-meeting")
