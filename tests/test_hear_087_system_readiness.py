"""Tests for HEAR-087: Visible System Readiness Indicators in Main UI.

Covers:
  AC1: Each component shows one explicit state: Ready, Degraded, Blocked, Unknown
  AC2: Aggregate top-line state distinguishes Product Path Ready/Degraded/Blocked
  AC3: Database, Ollama, enrollment failures surfaced visibly with reason text
  AC4: UI warns when product-complete testing should be stopped (BLOCKED aggregate)
  AC5: Automated tests cover rendered status states and degraded/blocking scenarios
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from ayehear.app.system_readiness import (
    ComponentStatus,
    ReadinessChecker,
    ReadinessState,
    SystemReadinessWidget,
    _aggregate_state,
)


# ---------------------------------------------------------------------------
# ReadinessChecker unit tests (pure logic, no Qt)
# ---------------------------------------------------------------------------

class TestReadinessCheckerDatabase:
    def test_database_ready_when_both_repos_connected(self):
        checker = ReadinessChecker()
        with patch("ayehear.storage.database.load_runtime_dsn", return_value="postgresql://localhost/ayehear"):
            status = checker.check_database(MagicMock(), MagicMock())
        assert status.state == ReadinessState.READY
        assert "connected" in status.reason.lower()

    def test_database_degraded_when_repos_connected_but_no_dsn(self):
        """Repos non-null but no runtime DSN -> DEGRADED (in-memory/dev mode)."""
        checker = ReadinessChecker()
        with patch("ayehear.storage.database.load_runtime_dsn", return_value=None):
            status = checker.check_database(MagicMock(), MagicMock())
        assert status.state == ReadinessState.DEGRADED
        assert status.reason

    def test_database_blocked_when_meeting_repo_missing(self):
        checker = ReadinessChecker()
        status = checker.check_database(None, MagicMock())
        assert status.state == ReadinessState.BLOCKED

    def test_database_blocked_when_participant_repo_missing(self):
        checker = ReadinessChecker()
        status = checker.check_database(MagicMock(), None)
        assert status.state == ReadinessState.BLOCKED

    def test_database_blocked_when_both_repos_missing(self):
        checker = ReadinessChecker()
        status = checker.check_database(None, None)
        assert status.state == ReadinessState.BLOCKED
        assert status.reason  # must have reason text


class TestReadinessCheckerTranscript:
    def test_transcript_ready_when_repo_connected(self):
        checker = ReadinessChecker()
        status = checker.check_transcript_persistence(MagicMock())
        assert status.state == ReadinessState.READY

    def test_transcript_blocked_when_no_repo(self):
        checker = ReadinessChecker()
        status = checker.check_transcript_persistence(None)
        assert status.state == ReadinessState.BLOCKED
        assert status.reason


class TestReadinessCheckerEnrollment:
    def test_enrollment_ready_when_both_repos_connected(self):
        """READY requires BOTH participant_repo AND speaker_profile_repo per spec."""
        checker = ReadinessChecker()
        status = checker.check_enrollment_persistence(MagicMock(), MagicMock())
        assert status.state == ReadinessState.READY

    def test_enrollment_degraded_when_only_participant_repo(self):
        """Participant repo only -> DEGRADED (recording works, no profile persistence)."""
        checker = ReadinessChecker()
        status = checker.check_enrollment_persistence(MagicMock(), None)
        assert status.state == ReadinessState.DEGRADED
        assert status.reason

    def test_enrollment_blocked_when_no_participant_repo(self):
        checker = ReadinessChecker()
        status = checker.check_enrollment_persistence(None, None)
        assert status.state == ReadinessState.BLOCKED
        assert status.reason


class TestReadinessCheckerLLM:
    def test_llm_ready_when_ollama_reachable_and_snapshot_connected(self):
        checker = ReadinessChecker()
        with patch("socket.create_connection"):
            status = checker.check_llm_path(MagicMock())
        assert status.state == ReadinessState.READY

    def test_llm_degraded_when_ollama_unreachable(self):
        checker = ReadinessChecker()
        with patch("socket.create_connection", side_effect=OSError("refused")):
            status = checker.check_llm_path(MagicMock())
        assert status.state == ReadinessState.DEGRADED
        assert "fallback" in status.reason.lower() or "unavailable" in status.reason.lower()

    def test_llm_degraded_when_ollama_reachable_but_no_snapshot_repo(self):
        checker = ReadinessChecker()
        with patch("socket.create_connection"):
            status = checker.check_llm_path(None)
        assert status.state == ReadinessState.DEGRADED

    def test_llm_reason_not_empty(self):
        checker = ReadinessChecker()
        with patch("socket.create_connection", side_effect=OSError("refused")):
            status = checker.check_llm_path(None)
        assert status.reason


class TestReadinessCheckerAudio:
    def test_audio_ready_when_devices_enumerable(self):
        checker = ReadinessChecker()
        with patch("ayehear.services.audio_capture.enumerate_input_devices", return_value=[(0, "Mic A"), (1, "Mic B")]):
            status = checker.check_audio_input()
        assert status.state == ReadinessState.READY

    def test_audio_blocked_when_no_devices(self):
        """No devices found -> BLOCKED per spec (no usable capture path)."""
        checker = ReadinessChecker()
        with patch("ayehear.services.audio_capture.enumerate_input_devices", return_value=[]):
            status = checker.check_audio_input()
        assert status.state == ReadinessState.BLOCKED

    def test_audio_blocked_on_enumeration_error(self):
        """Enumeration failure -> BLOCKED (no usable capture path)."""
        checker = ReadinessChecker()
        with patch("ayehear.services.audio_capture.enumerate_input_devices", side_effect=RuntimeError("no audio")):
            status = checker.check_audio_input()
        assert status.state == ReadinessState.BLOCKED


class TestReadinessCheckerExport:
    def test_export_ready_when_dir_writable(self, tmp_path):
        checker = ReadinessChecker()
        with patch("ayehear.utils.paths.exports_dir", return_value=tmp_path):
            status = checker.check_export_target(None)
        assert status.state == ReadinessState.READY

    def test_export_blocked_when_not_writable(self, tmp_path):
        checker = ReadinessChecker()
        with patch("ayehear.utils.paths.exports_dir", side_effect=OSError("no permission")):
            status = checker.check_export_target(None)
        assert status.state == ReadinessState.BLOCKED
        assert status.reason


# ---------------------------------------------------------------------------
# Aggregate state logic (AC2)
# ---------------------------------------------------------------------------

class TestAggregateState:
    def test_ready_when_all_ready(self):
        components = [
            ComponentStatus(name="Database / Runtime Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Transcript Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Speaker Enrollment Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Local LLM / Protocol Engine", state=ReadinessState.READY),
        ]
        assert _aggregate_state(components) == ReadinessState.READY

    def test_degraded_when_llm_degraded_only(self):
        components = [
            ComponentStatus(name="Database / Runtime Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Transcript Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Speaker Enrollment Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Local LLM / Protocol Engine", state=ReadinessState.DEGRADED),
        ]
        assert _aggregate_state(components) == ReadinessState.DEGRADED

    def test_blocked_when_database_blocked(self):
        components = [
            ComponentStatus(name="Database / Runtime Persistence", state=ReadinessState.BLOCKED),
            ComponentStatus(name="Transcript Persistence", state=ReadinessState.READY),
        ]
        assert _aggregate_state(components) == ReadinessState.BLOCKED

    def test_blocked_when_transcript_blocked(self):
        components = [
            ComponentStatus(name="Database / Runtime Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Transcript Persistence", state=ReadinessState.BLOCKED),
        ]
        assert _aggregate_state(components) == ReadinessState.BLOCKED

    def test_blocked_when_enrollment_blocked(self):
        components = [
            ComponentStatus(name="Database / Runtime Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Speaker Enrollment Persistence", state=ReadinessState.BLOCKED),
        ]
        assert _aggregate_state(components) == ReadinessState.BLOCKED

    def test_degraded_not_blocked_when_only_non_critical_blocked(self):
        """Export target blocked -> only DEGRADED (not a hard-stop component)."""
        components = [
            ComponentStatus(name="Database / Runtime Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Transcript Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Speaker Enrollment Persistence", state=ReadinessState.READY),
            ComponentStatus(name="Export Target", state=ReadinessState.BLOCKED),
        ]
        assert _aggregate_state(components) == ReadinessState.DEGRADED


# ---------------------------------------------------------------------------
# SystemReadinessWidget Qt tests (AC1, AC3, AC4)
# ---------------------------------------------------------------------------

def _make_widget(qapp):
    return SystemReadinessWidget()


class TestSystemReadinessWidgetRendering:
    def test_widget_shows_component_rows_after_update(self, qapp):
        widget = _make_widget(qapp)
        components = [
            ComponentStatus("Database / Runtime Persistence", ReadinessState.READY, "DB connected"),
            ComponentStatus("Transcript Persistence", ReadinessState.BLOCKED, "No repo"),
        ]
        widget.update_status(components, ReadinessState.BLOCKED)
        # Both component labels should exist
        assert len(widget._component_rows) == 2

    def test_aggregate_label_text_reflects_state(self, qapp):
        widget = _make_widget(qapp)
        components = [
            ComponentStatus("Database / Runtime Persistence", ReadinessState.BLOCKED, "Unavailable"),
        ]
        widget.update_status(components, ReadinessState.BLOCKED)
        text = widget._aggregate_label.text()
        assert "Blocked" in text

    def test_aggregate_label_shows_ready(self, qapp):
        widget = _make_widget(qapp)
        components = [
            ComponentStatus("Database / Runtime Persistence", ReadinessState.READY, "Connected"),
        ]
        widget.update_status(components, ReadinessState.READY)
        text = widget._aggregate_label.text()
        assert "Ready" in text

    def test_aggregate_label_shows_degraded(self, qapp):
        widget = _make_widget(qapp)
        components = [
            ComponentStatus("Local LLM / Protocol Engine", ReadinessState.DEGRADED, "Fallback"),
        ]
        widget.update_status(components, ReadinessState.DEGRADED)
        text = widget._aggregate_label.text()
        assert "Degraded" in text

    def test_component_reason_text_visible(self, qapp):
        widget = _make_widget(qapp)
        components = [
            ComponentStatus("Database / Runtime Persistence", ReadinessState.BLOCKED, "Postgres offline"),
        ]
        widget.update_status(components, ReadinessState.BLOCKED)
        row_texts = [lbl.text() for lbl in widget._component_rows]
        assert any("Postgres offline" in t for t in row_texts)

    def test_update_replaces_old_rows(self, qapp):
        widget = _make_widget(qapp)
        widget.update_status(
            [ComponentStatus("A", ReadinessState.READY)], ReadinessState.READY
        )
        assert len(widget._component_rows) == 1
        widget.update_status(
            [ComponentStatus("B", ReadinessState.READY), ComponentStatus("C", ReadinessState.READY)],
            ReadinessState.READY,
        )
        assert len(widget._component_rows) == 2

    def test_set_unknown_clears_rows(self, qapp):
        widget = _make_widget(qapp)
        widget.update_status(
            [ComponentStatus("X", ReadinessState.READY)], ReadinessState.READY
        )
        widget.set_unknown()
        assert len(widget._component_rows) == 0

    def test_blocked_aggregate_sets_tooltip(self, qapp):
        widget = _make_widget(qapp)
        components = [ComponentStatus("Database / Runtime Persistence", ReadinessState.BLOCKED)]
        widget.update_status(components, ReadinessState.BLOCKED)
        tooltip = widget._aggregate_label.toolTip()
        assert tooltip  # must not be empty for BLOCKED


# ---------------------------------------------------------------------------
# AC4: MainWindow integrates SystemReadinessWidget (smoke test)
# ---------------------------------------------------------------------------

class TestMainWindowReadinessIntegration:
    def _make_window(self, qapp, meeting_repo=None, participant_repo=None,
                     transcript_repo=None, snapshot_repo=None, speaker_manager=None):
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

    def test_readiness_widget_created_on_window_init(self, qapp):
        win = self._make_window(qapp)
        assert win._readiness_widget is not None
        assert isinstance(win._readiness_widget, SystemReadinessWidget)

    def test_refresh_readiness_does_not_crash_without_repos(self, qapp):
        win = self._make_window(qapp)
        # Must not raise
        win._refresh_readiness()

    def test_refresh_readiness_blocked_when_no_repos(self, qapp):
        win = self._make_window(qapp)
        win._refresh_readiness()
        text = win._readiness_widget._aggregate_label.text()
        assert "Blocked" in text

    def test_refresh_readiness_shows_ready_with_all_repos(self, qapp, tmp_path):
        from ayehear.services.speaker_manager import SpeakerManager
        mr = MagicMock()
        pr = MagicMock()
        tr = MagicMock()
        sr = MagicMock()
        profile_repo = MagicMock()
        sm = SpeakerManager(profile_repo=profile_repo, participant_repo=pr)
        win = self._make_window(qapp, meeting_repo=mr, participant_repo=pr,
                                transcript_repo=tr, snapshot_repo=sr,
                                speaker_manager=sm)
        with patch("socket.create_connection"), \
             patch("ayehear.utils.paths.exports_dir", return_value=tmp_path), \
             patch("ayehear.services.audio_capture.enumerate_input_devices", return_value=[(0, "Mic")]), \
             patch("ayehear.storage.database.load_runtime_dsn", return_value="postgresql://localhost/ayehear"):
            win._refresh_readiness()
        text = win._readiness_widget._aggregate_label.text()
        assert "Ready" in text
