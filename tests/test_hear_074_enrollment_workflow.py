"""Tests for HEAR-074: Real microphone voice enrollment workflow.

Covers:
- _start_enrollment opens EnrollmentDialog with correct pending speakers
- Successful enrollment updates list items to 'enrolled (id: ...)' status
- Failed enrollment updates list item to 'enrollment failed' status
- Already-enrolled speakers are excluded from pending list
- Status label reflects enrollment results
- _parse_speaker_raw parses all three fields correctly
- EnrollmentDialog receives correct speaker_manager instance
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())
    return win


# ---------------------------------------------------------------------------
# _parse_speaker_raw
# ---------------------------------------------------------------------------

class TestParseSpeakerRaw:
    def test_full_entry(self):
        from ayehear.app.window import MainWindow
        name, org, status = MainWindow._parse_speaker_raw("Anna Schmidt | Corp | pending enrollment")
        assert name == "Anna Schmidt"
        assert org == "Corp"
        assert status == "pending enrollment"

    def test_two_fields(self):
        from ayehear.app.window import MainWindow
        name, org, status = MainWindow._parse_speaker_raw("Max | AYE")
        assert name == "Max"
        assert org == "AYE"
        assert status == ""

    def test_single_field(self):
        from ayehear.app.window import MainWindow
        name, org, status = MainWindow._parse_speaker_raw("Solo")
        assert name == "Solo"
        assert org == "Organisation"
        assert status == ""

    def test_enrolled_status(self):
        from ayehear.app.window import MainWindow
        name, org, status = MainWindow._parse_speaker_raw("Eva | Org | enrolled (id: abc12345)")
        assert name == "Eva"
        assert status.startswith("enrolled")


# ---------------------------------------------------------------------------
# _start_enrollment: pending speaker filtering
# ---------------------------------------------------------------------------

class TestStartEnrollmentPendingFilter:
    def test_already_enrolled_excluded_from_pending(self, qapp):
        """Speakers with 'enrolled' status must NOT appear in pending list."""
        win = _make_window(qapp)

        from PySide6.QtWidgets import QDialog, QListWidgetItem
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Anna | Corp | enrolled (id: abc12345)"))
        win._speakers_list.addItem(QListWidgetItem("Max | AYE | pending enrollment"))

        captured_pending = []

        def capture_init(pending_speakers, speaker_manager, parent=None):
            captured_pending.extend(pending_speakers)
            mock = MagicMock()
            mock.exec.return_value = QDialog.DialogCode.Rejected
            mock.get_enrolled_results.return_value = {}
            return mock

        with patch("ayehear.app.window.EnrollmentDialog", side_effect=capture_init):
            win._start_enrollment()

        # Only 'Max | AYE' is pending
        assert len(captured_pending) == 1
        assert captured_pending[0][0] == "Max"
        assert captured_pending[0][1] == "AYE"

        win.deleteLater()
        qapp.processEvents()

    def test_all_enrolled_shows_information(self, qapp):
        """When all speakers are enrolled, information box is shown without opening dialog."""
        win = _make_window(qapp)

        from PySide6.QtWidgets import QListWidgetItem
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Anna | Corp | enrolled (id: abc12345)"))

        with (
            patch("ayehear.app.window.EnrollmentDialog") as MockDlg,
            patch("PySide6.QtWidgets.QMessageBox.information") as mock_info,
        ):
            win._start_enrollment()

        MockDlg.assert_not_called()
        mock_info.assert_called_once()

        win.deleteLater()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# _start_enrollment: success path
# ---------------------------------------------------------------------------

class TestStartEnrollmentSuccess:
    def test_successful_enrollment_updates_item_text(self, qapp):
        """After Accepted with enrolled results, item text must contain 'enrolled (id:'."""
        win = _make_window(qapp)

        from PySide6.QtWidgets import QDialog, QListWidgetItem
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Anna Schmidt | Corp | pending enrollment"))

        fake_profile_id = "abc12345-dead-beef-0000-000000000000"

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Accepted
            mock_instance.get_enrolled_results.return_value = {"Anna Schmidt": fake_profile_id}
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        text = win._speakers_list.item(0).text()
        assert "enrolled (id:" in text
        assert fake_profile_id[:8] in text

        win.deleteLater()
        qapp.processEvents()

    def test_successful_enrollment_adds_to_enrolled_speakers(self, qapp):
        """Enrolled speaker must be added to _enrolled_speakers dict."""
        win = _make_window(qapp)

        from PySide6.QtWidgets import QDialog, QListWidgetItem
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Eva Muster | AYE | pending enrollment"))

        fake_id = "profile-uuid-0001"

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Accepted
            mock_instance.get_enrolled_results.return_value = {"Eva Muster": fake_id}
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        assert "Eva Muster" in win._enrolled_speakers
        assert win._enrolled_speakers["Eva Muster"] == fake_id

        win.deleteLater()
        qapp.processEvents()

    def test_unrecorded_speaker_marked_failed_on_accept(self, qapp):
        """Pending speaker not in results dict should be 'enrollment failed' after Accepted."""
        win = _make_window(qapp)

        from PySide6.QtWidgets import QDialog, QListWidgetItem
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Recorded | Org | pending enrollment"))
        win._speakers_list.addItem(QListWidgetItem("Skipped | Org | pending enrollment"))

        fake_id = "abcdef00-1234-5678-0000-000000000000"

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Accepted
            mock_instance.get_enrolled_results.return_value = {"Recorded": fake_id}
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        text_skipped = win._speakers_list.item(1).text()
        assert "enrollment failed" in text_skipped

        win.deleteLater()
        qapp.processEvents()

    def test_status_label_shows_count_on_accept(self, qapp):
        """Status label must show '1/1 Sprecher registriert' after successful enrollment."""
        win = _make_window(qapp)

        from PySide6.QtWidgets import QDialog, QListWidgetItem
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Max | AYE | pending enrollment"))

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Accepted
            mock_instance.get_enrolled_results.return_value = {"Max": "profile-xyz"}
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        label = win._speaker_status.text()
        assert "1/1" in label

        win.deleteLater()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# _start_enrollment: speaker_manager passed correctly
# ---------------------------------------------------------------------------

class TestStartEnrollmentSpeakerManager:
    def test_dialog_receives_correct_speaker_manager(self, qapp):
        """EnrollmentDialog must be constructed with the window's _speaker_manager."""
        win = _make_window(qapp)

        from PySide6.QtWidgets import QDialog, QListWidgetItem
        win._speakers_list.clear()
        win._speakers_list.addItem(QListWidgetItem("Test | Org | pending enrollment"))

        received_manager = []

        def capture_init(pending_speakers, speaker_manager, parent=None):
            received_manager.append(speaker_manager)
            mock = MagicMock()
            mock.exec.return_value = QDialog.DialogCode.Rejected
            mock.get_enrolled_results.return_value = {}
            return mock

        with patch("ayehear.app.window.EnrollmentDialog", side_effect=capture_init):
            win._start_enrollment()

        assert len(received_manager) == 1
        assert received_manager[0] is win._speaker_manager

        win.deleteLater()
        qapp.processEvents()
