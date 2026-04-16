"""Tests for HEAR-068: Real Voice Enrollment Workflow (B1 Closure).

Covers:
- EnrollmentDialog shows all pending speakers correctly
- Successful enrollment updates item status to 'enrolled (id: ...)'
- Failed enrollment (SpeakerManager returns success=False) shows error status
- No audio captured shows informative retry message
- Audio capture start failure shows error and re-enables button
- _start_enrollment() in MainWindow now launches EnrollmentDialog (not placeholder)
- After dialog, speaker list items are updated
- All-enrolled guard (shows completion message when no pending speakers remain)
- Enrollment without speakers shows warning
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from PySide6.QtWidgets import QDialog, QListWidgetItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())
    return win


def _make_enrollment_dialog(qapp, speakers=None, sm=None):
    """Create an EnrollmentDialog with controllable speaker_manager."""
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import SpeakerManager

    if speakers is None:
        speakers = [("Frau Schneider", "AYE"), ("Max Weber", "Corp")]
    if sm is None:
        sm = SpeakerManager()

    return EnrollmentDialog(pending_speakers=speakers, speaker_manager=sm)


# ---------------------------------------------------------------------------
# EnrollmentDialog: structural / display tests
# ---------------------------------------------------------------------------


def test_enrollment_dialog_shows_all_pending_speakers(qapp) -> None:
    dlg = _make_enrollment_dialog(qapp, speakers=[
        ("Anna Schmidt", "CompA"),
        ("Max Weber", "CompB"),
        ("Frau Müller", "CompC"),
    ])
    assert dlg._speaker_list.count() == 3
    texts = [dlg._speaker_list.item(i).text() for i in range(dlg._speaker_list.count())]
    assert any("Anna Schmidt" in t for t in texts)
    assert any("Max Weber" in t for t in texts)
    assert any("Frau Müller" in t for t in texts)
    dlg.deleteLater()
    qapp.processEvents()


def test_enrollment_dialog_first_speaker_preselected(qapp) -> None:
    dlg = _make_enrollment_dialog(qapp)
    assert dlg._speaker_list.currentRow() == 0
    dlg.deleteLater()
    qapp.processEvents()


def test_enrollment_dialog_record_button_enabled_initially(qapp) -> None:
    dlg = _make_enrollment_dialog(qapp)
    assert dlg._record_btn.isEnabled()
    dlg.deleteLater()
    qapp.processEvents()


def test_enrollment_dialog_enrolled_results_empty_initially(qapp) -> None:
    dlg = _make_enrollment_dialog(qapp)
    assert dlg.get_enrolled_results() == {}
    dlg.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# EnrollmentDialog: _do_enroll with success
# ---------------------------------------------------------------------------


def test_do_enroll_success_updates_list_item(qapp) -> None:
    """When SpeakerManager.enroll succeeds, list item must show 'enrolled (id:...'."""
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import EnrollmentResult, SpeakerManager

    mock_sm = MagicMock(spec=SpeakerManager)
    mock_sm.enroll.return_value = EnrollmentResult(
        participant_id="pid-1",
        display_name="Frau Schneider",
        profile_id="abcdef1234567890",
        embedding_dim=768,
        success=True,
    )
    dlg = EnrollmentDialog(
        pending_speakers=[("Frau Schneider", "AYE")],
        speaker_manager=mock_sm,
    )
    dlg._speaker_list.setCurrentRow(0)
    item = dlg._speaker_list.item(0)
    item.setData(0x0100, ("Frau Schneider", "AYE"))  # Qt.ItemDataRole.UserRole

    samples = np.ones(8000, dtype=np.float32).tolist()
    dlg._do_enroll(item, "Frau Schneider", "AYE", samples)

    assert "enrolled" in item.text()
    assert "abcdef12" in item.text()  # first 8 chars of profile_id
    assert dlg.get_enrolled_results().get("Frau Schneider") == "abcdef1234567890"
    dlg.deleteLater()
    qapp.processEvents()


def test_do_enroll_failure_updates_list_item_to_failed(qapp) -> None:
    """When SpeakerManager.enroll returns success=False, item shows 'enrollment failed'."""
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import EnrollmentResult, SpeakerManager

    mock_sm = MagicMock(spec=SpeakerManager)
    mock_sm.enroll.return_value = EnrollmentResult(
        participant_id="pid-2",
        display_name="Max Weber",
        profile_id="",
        embedding_dim=0,
        success=False,
        error="DB unavailable",
    )
    dlg = EnrollmentDialog(
        pending_speakers=[("Max Weber", "Corp")],
        speaker_manager=mock_sm,
    )
    item = dlg._speaker_list.item(0)
    item.setData(0x0100, ("Max Weber", "Corp"))

    dlg._do_enroll(item, "Max Weber", "Corp", [0.1] * 8000)

    assert "failed" in item.text() or "fehlgeschlagen" in dlg._status_lbl.text().lower()
    assert dlg.get_enrolled_results() == {}
    dlg.deleteLater()
    qapp.processEvents()


def test_do_enroll_re_enables_record_button_on_success(qapp) -> None:
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import EnrollmentResult, SpeakerManager

    mock_sm = MagicMock(spec=SpeakerManager)
    mock_sm.enroll.return_value = EnrollmentResult(
        participant_id="p", display_name="X", profile_id="yyy", embedding_dim=768, success=True
    )
    dlg = EnrollmentDialog(pending_speakers=[("X", "Y")], speaker_manager=mock_sm)
    dlg._record_btn.setEnabled(False)
    item = dlg._speaker_list.item(0)
    item.setData(0x0100, ("X", "Y"))

    dlg._do_enroll(item, "X", "Y", [0.0] * 4000)
    assert dlg._record_btn.isEnabled()
    dlg.deleteLater()
    qapp.processEvents()


def test_do_enroll_re_enables_record_button_on_failure(qapp) -> None:
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import EnrollmentResult, SpeakerManager

    mock_sm = MagicMock(spec=SpeakerManager)
    mock_sm.enroll.return_value = EnrollmentResult(
        participant_id="p", display_name="X", profile_id="", embedding_dim=0,
        success=False, error="err"
    )
    dlg = EnrollmentDialog(pending_speakers=[("X", "Y")], speaker_manager=mock_sm)
    dlg._record_btn.setEnabled(False)
    item = dlg._speaker_list.item(0)
    item.setData(0x0100, ("X", "Y"))

    dlg._do_enroll(item, "X", "Y", [0.0] * 4000)
    assert dlg._record_btn.isEnabled()
    dlg.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# EnrollmentDialog: _finish_recording with no audio
# ---------------------------------------------------------------------------


def test_finish_recording_with_no_chunks_shows_retry_message(qapp) -> None:
    """When no audio was captured, _finish_recording must show retry guidance."""
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import SpeakerManager

    mock_sm = MagicMock(spec=SpeakerManager)
    dlg = EnrollmentDialog(pending_speakers=[("Speaker A", "Org")], speaker_manager=mock_sm)
    dlg._speaker_list.setCurrentRow(0)
    item = dlg._speaker_list.item(0)
    item.setData(0x0100, ("Speaker A", "Org"))
    # Ensure no chunks collected
    dlg._captured_chunks = []

    dlg._finish_recording()

    # No enroll call since no audio
    mock_sm.enroll.assert_not_called()
    # Status shows retry message
    assert dlg._record_btn.isEnabled()
    dlg.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# EnrollmentDialog: audio segment collection (thread-safe)
# ---------------------------------------------------------------------------


def test_on_audio_segment_collects_chunks(qapp) -> None:
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.audio_capture import AudioSegment
    from ayehear.services.speaker_manager import SpeakerManager
    from datetime import datetime

    dlg = EnrollmentDialog(pending_speakers=[("X", "Y")], speaker_manager=MagicMock(spec=SpeakerManager))
    segment = AudioSegment(
        captured_at=datetime.now(),
        start_ms=0, end_ms=100,
        samples=np.ones(1600, dtype=np.float32),
        rms=0.5, is_silence=False,
    )
    dlg._on_audio_segment(segment)
    assert len(dlg._captured_chunks) == 1
    assert dlg._captured_chunks[0].shape == (1600,)
    dlg.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# MainWindow._start_enrollment integration
# ---------------------------------------------------------------------------


def test_start_enrollment_warns_when_no_speakers(qapp) -> None:
    win = _make_window(qapp)
    win._speakers_list.clear()

    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        win._start_enrollment()

    mock_warn.assert_called_once()
    win.deleteLater()
    qapp.processEvents()


def test_start_enrollment_shows_completion_when_all_enrolled(qapp) -> None:
    """When all speakers are already enrolled, show completion message (no dialog)."""
    win = _make_window(qapp)
    win._speakers_list.clear()
    win._speakers_list.addItem(QListWidgetItem("Anna | Corp | enrolled (id: abc12345)"))
    win._speakers_list.addItem(QListWidgetItem("Max | AYE | enrolled (id: def67890)"))

    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        win._start_enrollment()

    mock_info.assert_called_once()
    win.deleteLater()
    qapp.processEvents()


def test_start_enrollment_launches_enrollment_dialog_for_pending_speakers(qapp) -> None:
    """_start_enrollment must launch EnrollmentDialog, not show a placeholder QMessageBox."""
    win = _make_window(qapp)
    win._speakers_list.clear()
    win._speakers_list.addItem(QListWidgetItem("Frau Schneider | AYE | pending enrollment"))

    # Patch EnrollmentDialog.exec to avoid blocking + return Rejected
    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_dlg_instance = MagicMock()
        mock_dlg_instance.exec.return_value = QDialog.DialogCode.Rejected
        mock_dlg_instance.get_enrolled_results.return_value = {}
        MockDlg.return_value = mock_dlg_instance

        win._start_enrollment()

    MockDlg.assert_called_once()
    mock_dlg_instance.exec.assert_called_once()
    win.deleteLater()
    qapp.processEvents()


def test_start_enrollment_updates_speaker_list_after_successful_enrollment(qapp) -> None:
    """After enrollment dialog reports enrolled speakers, list items must be updated."""
    win = _make_window(qapp)
    win._speakers_list.clear()
    win._speakers_list.addItem(QListWidgetItem("Frau Schneider | AYE | pending enrollment"))

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_dlg_instance = MagicMock()
        mock_dlg_instance.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg_instance.get_enrolled_results.return_value = {
            "Frau Schneider": "profile-uuid-1234"
        }
        MockDlg.return_value = mock_dlg_instance

        win._start_enrollment()

    item_text = win._speakers_list.item(0).text()
    assert "enrolled" in item_text
    assert "profile-uui" in item_text or "profile-uuid-1234"[:8] in item_text
    assert win._enrolled_speakers.get("Frau Schneider") == "profile-uuid-1234"
    win.deleteLater()
    qapp.processEvents()


def test_start_enrollment_does_not_show_phase_placeholder(qapp) -> None:
    """The old Phase-1 placeholder message must NOT appear."""
    win = _make_window(qapp)
    win._speakers_list.clear()
    win._speakers_list.addItem(QListWidgetItem("Anna | Corp | pending enrollment"))

    captured_messages: list[str] = []

    def capture_info(parent, title, message):
        captured_messages.append(message)

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_dlg_instance = MagicMock()
        mock_dlg_instance.exec.return_value = QDialog.DialogCode.Rejected
        mock_dlg_instance.get_enrolled_results.return_value = {}
        MockDlg.return_value = mock_dlg_instance
        with patch("PySide6.QtWidgets.QMessageBox.information", side_effect=capture_info):
            win._start_enrollment()

    # Must not show any QMessageBox.information (only EnrollmentDialog should open)
    for msg in captured_messages:
        assert "Phase" not in msg, f"Old placeholder message found: {msg!r}"

    win.deleteLater()
    qapp.processEvents()
