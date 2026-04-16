"""Regression tests for HEAR-060: Stub Enrollment replaced with explicit Phase-1 block.

Covers:
- _start_enrollment shows informational dialog instead of running fake success
- No speaker item is mutated to 'enrolled (id: stub-...)' after calling enrollment
- Status remains 'pending enrollment' for all speakers
- Empty-speaker guard still works
- _name_to_stub_audio is removed (no fake audio generation)
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, call, patch

import pytest


def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())
    return win


# ---------------------------------------------------------------------------
# Stub audio helper must be removed
# ---------------------------------------------------------------------------

def test_name_to_stub_audio_does_not_exist():
    """_name_to_stub_audio must be removed from MainWindow (HEAR-060)."""
    from ayehear.app.window import MainWindow

    assert not hasattr(MainWindow, "_name_to_stub_audio"), (
        "_name_to_stub_audio must be removed; stub enrollment is no longer allowed"
    )


# ---------------------------------------------------------------------------
# _start_enrollment — blocked state
# ---------------------------------------------------------------------------

def test_start_enrollment_shows_dialog_not_fake_success(qapp):
    """_start_enrollment must open EnrollmentDialog (HEAR-068), not a placeholder QMessageBox."""
    win = _make_window(qapp)

    from PySide6.QtWidgets import QDialog, QListWidgetItem
    win._speakers_list.clear()
    win._speakers_list.addItem(QListWidgetItem("Anna Schmidt | Corp | pending enrollment"))
    win._speakers_list.addItem(QListWidgetItem("Max Weber | AYE | pending enrollment"))

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Rejected
        mock_instance.get_enrolled_results.return_value = {}
        MockDlg.return_value = mock_instance

        win._start_enrollment()

    # Must open EnrollmentDialog, not QMessageBox
    MockDlg.assert_called_once()
    mock_instance.exec.assert_called_once()

    win.deleteLater()
    qapp.processEvents()


def test_start_enrollment_does_not_mutate_items_to_enrolled(qapp):
    """When EnrollmentDialog is cancelled, no item must contain 'enrolled (id:' tokens."""
    win = _make_window(qapp)

    from PySide6.QtWidgets import QDialog, QListWidgetItem
    win._speakers_list.clear()
    for name in ["Anna Schmidt | Corp | pending enrollment", "Max Weber | AYE | pending enrollment"]:
        win._speakers_list.addItem(QListWidgetItem(name))

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Rejected
        mock_instance.get_enrolled_results.return_value = {}
        MockDlg.return_value = mock_instance

        win._start_enrollment()

    for i in range(win._speakers_list.count()):
        text = win._speakers_list.item(i).text()
        assert "enrolled (id:" not in text, (
            f"Item must not contain 'enrolled (id:...' when dialog was cancelled: {text!r}"
        )
        assert "enrollment failed" not in text, (
            f"Item must not show failure when dialog was cancelled: {text!r}"
        )

    win.deleteLater()
    qapp.processEvents()


def test_start_enrollment_items_remain_pending(qapp):
    """Speakers must stay 'pending enrollment' when EnrollmentDialog is cancelled."""
    from ayehear.app.window import MainWindow
    win = _make_window(qapp)

    from PySide6.QtWidgets import QDialog, QListWidgetItem
    win._speakers_list.clear()
    win._speakers_list.addItem(QListWidgetItem("Frau Schneider | AYE | pending enrollment"))

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Rejected
        mock_instance.get_enrolled_results.return_value = {}
        MockDlg.return_value = mock_instance

        win._start_enrollment()

    text = win._speakers_list.item(0).text()
    _, _, status = MainWindow._parse_speaker_raw(text)
    assert status == "pending enrollment", f"Expected 'pending enrollment', got: {status!r}"

    win.deleteLater()
    qapp.processEvents()


def test_start_enrollment_empty_speakers_shows_warning(qapp):
    """Empty speaker list must trigger a warning, not an info dialog."""
    win = _make_window(qapp)
    win._speakers_list.clear()

    with (
        patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn,
        patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
    ):
        win._start_enrollment()

    mock_warn.assert_called_once()
    mock_info.assert_not_called()

    win.deleteLater()
    qapp.processEvents()


def test_start_enrollment_sets_status_label(qapp):
    """Status label must show enrollment result (or cancellation) after dialog closes."""
    win = _make_window(qapp)

    from PySide6.QtWidgets import QDialog, QListWidgetItem
    win._speakers_list.clear()
    win._speakers_list.addItem(QListWidgetItem("Anna | Corp | pending enrollment"))
    win._speakers_list.addItem(QListWidgetItem("Max | AYE | pending enrollment"))

    win._speaker_status.setText("")

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Rejected
        mock_instance.get_enrolled_results.return_value = {}
        MockDlg.return_value = mock_instance

        win._start_enrollment()

    label = win._speaker_status.text()
    assert label, "Status label must not be empty after enrollment dialog closes"
    # Cancelled dialog => shows cancel/abort message
    assert "enrollment" in label.lower() or "sprecher" in label.lower()

    win.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# SpeakerManager.enroll must NOT be called during Phase-1 block
# ---------------------------------------------------------------------------

def test_start_enrollment_does_not_call_speaker_manager_enroll(qapp):
    """SpeakerManager.enroll() must not be called when EnrollmentDialog is cancelled."""
    win = _make_window(qapp)

    from PySide6.QtWidgets import QDialog, QListWidgetItem
    win._speakers_list.clear()
    win._speakers_list.addItem(QListWidgetItem("Anna | Corp | pending enrollment"))

    win._speaker_manager.enroll = MagicMock()

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Rejected
        mock_instance.get_enrolled_results.return_value = {}
        MockDlg.return_value = mock_instance

        win._start_enrollment()

    win._speaker_manager.enroll.assert_not_called()

    win.deleteLater()
    qapp.processEvents()
