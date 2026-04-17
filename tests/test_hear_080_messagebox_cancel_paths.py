"""Tests for HEAR-080: Explicit No/Cancel path coverage for messagebox flows.

Covers the negative paths that the global ``patch_qt_messageboxes`` fixture
masks by auto-returning ``Yes`` for all ``QMessageBox.question()`` calls.

Flows with explicit No/Cancel coverage
---------------------------------------
1. **_remove_speaker – No response** (critical data-deletion workflow)
   - Speaker count unchanged
   - Speaker text/data unchanged
   - Status label does not say "entfernt"
   - No corruption when multiple speakers exist

2. **_start_enrollment – Rejected (Cancel)** (critical data-creation workflow)
   - Pending speaker items NOT modified to 'enrolled' or 'enrollment failed'
   - ``_enrolled_speakers`` dict NOT modified
   - Status label reflects 0/N result

The tests shadow the session-scoped ``patch_qt_messageboxes`` autouse fixture
with explicit per-test patches so the return value is controlled deliberately.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidgetItem, QMessageBox


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())
    return win


def _add_speaker(list_widget, text: str, participant_id: str | None = None) -> QListWidgetItem:
    item = QListWidgetItem(text)
    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
    if participant_id:
        item.setData(Qt.ItemDataRole.UserRole, participant_id)
    list_widget.addItem(item)
    return item


# ---------------------------------------------------------------------------
# Flow 1: _remove_speaker – No/Cancel path
# ---------------------------------------------------------------------------

class TestRemoveSpeakerCancelPath:
    """Validates that pressing No in the removal confirmation dialog
    does not mutate the speaker list or produce misleading status text."""

    def test_no_answer_leaves_count_unchanged(self, qapp):
        """Selecting No must keep the speaker count identical."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        _add_speaker(win._speakers_list, "Alice | Corp | pending enrollment")
        _add_speaker(win._speakers_list, "Bob | AYE | pending enrollment")
        win._speakers_list.setCurrentRow(0)
        count_before = win._speakers_list.count()

        with patch(
            "ayehear.app.window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            win._remove_speaker()

        assert win._speakers_list.count() == count_before

        win.deleteLater()
        qapp.processEvents()

    def test_no_answer_preserves_all_speaker_texts(self, qapp):
        """Selecting No must not alter any speaker text in the list."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        texts = [
            "Alice | Corp | pending enrollment",
            "Bob | AYE | enrolled (id: abc12345)",
        ]
        for t in texts:
            _add_speaker(win._speakers_list, t)
        win._speakers_list.setCurrentRow(0)

        with patch(
            "ayehear.app.window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            win._remove_speaker()

        actual_texts = [
            win._speakers_list.item(i).text()
            for i in range(win._speakers_list.count())
        ]
        assert actual_texts == texts

        win.deleteLater()
        qapp.processEvents()

    def test_no_answer_status_label_does_not_say_entfernt(self, qapp):
        """Status label must not contain 'entfernt' after a No response."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        _add_speaker(win._speakers_list, "Eve | Org | pending enrollment")
        win._speakers_list.setCurrentRow(0)

        with patch(
            "ayehear.app.window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            win._remove_speaker()

        assert "entfernt" not in win._speaker_status.text().lower()

        win.deleteLater()
        qapp.processEvents()

    def test_no_answer_on_second_speaker_keeps_all_intact(self, qapp):
        """Selecting No for a non-first speaker must leave ALL speakers untouched."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        names = [
            "Alice | Corp | pending enrollment",
            "Bob | AYE | pending enrollment",
            "Carol | X | pending enrollment",
        ]
        for n in names:
            _add_speaker(win._speakers_list, n)
        win._speakers_list.setCurrentRow(1)  # select Bob

        with patch(
            "ayehear.app.window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            win._remove_speaker()

        assert win._speakers_list.count() == 3
        assert win._speakers_list.item(1).text() == "Bob | AYE | pending enrollment"

        win.deleteLater()
        qapp.processEvents()

    def test_no_selection_shows_information_not_question(self, qapp):
        """When nothing is selected, information() must fire instead of question()."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        _add_speaker(win._speakers_list, "Only | Org | pending enrollment")
        win._speakers_list.clearSelection()
        win._speakers_list.setCurrentRow(-1)

        with (
            patch(
                "ayehear.app.window.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ) as mock_q,
            patch("ayehear.app.window.QMessageBox.information") as mock_info,
        ):
            win._remove_speaker()

        mock_q.assert_not_called()
        mock_info.assert_called_once()

        win.deleteLater()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# Flow 2: _start_enrollment – dialog Rejected (Cancel) path
# ---------------------------------------------------------------------------

class TestEnrollmentDialogCancelPath:
    """Validates that cancelling the EnrollmentDialog does not corrupt
    speaker item texts, enrolled_speakers dict, or produce misleading state."""

    def test_cancelled_dialog_leaves_speaker_items_unchanged(self, qapp):
        """Cancelling enrollment must not change any speaker item text."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        original_text = "Anna | Corp | pending enrollment"
        _add_speaker(win._speakers_list, original_text, participant_id="pid-anna")

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Rejected
            mock_instance.get_enrolled_results.return_value = {}
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        assert win._speakers_list.item(0).text() == original_text
        assert "enrollment failed" not in win._speakers_list.item(0).text()
        assert "enrolled (id:" not in win._speakers_list.item(0).text()

        win.deleteLater()
        qapp.processEvents()

    def test_cancelled_dialog_does_not_populate_enrolled_speakers(self, qapp):
        """_enrolled_speakers must remain empty after enrollment dialog is cancelled."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        _add_speaker(win._speakers_list, "Max | AYE | pending enrollment", participant_id="pid-max")

        enrolled_before = dict(win._enrolled_speakers)

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Rejected
            mock_instance.get_enrolled_results.return_value = {}
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        assert win._enrolled_speakers == enrolled_before

        win.deleteLater()
        qapp.processEvents()

    def test_cancelled_dialog_multiple_speakers_none_modified(self, qapp):
        """Cancelling with multiple pending speakers must leave all items unchanged."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        original_texts = [
            "Speaker 1 | Org | pending enrollment",
            "Speaker 2 | Org | pending enrollment",
            "Speaker 3 | Org | pending enrollment",
        ]
        for i, t in enumerate(original_texts):
            _add_speaker(win._speakers_list, t, participant_id=f"pid-{i}")

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Rejected
            mock_instance.get_enrolled_results.return_value = {}
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        for i, expected in enumerate(original_texts):
            assert win._speakers_list.item(i).text() == expected

        win.deleteLater()
        qapp.processEvents()

    def test_cancelled_dialog_status_shows_zero_enrolled(self, qapp):
        """Status label must reflect 0/N after cancelled enrollment dialog."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        _add_speaker(win._speakers_list, "Eva | AYE | pending enrollment", participant_id="pid-eva")

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Rejected
            mock_instance.get_enrolled_results.return_value = {}
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        label_text = win._speaker_status.text()
        # 0 speakers were enrolled out of 1 pending
        assert "0/1" in label_text

        win.deleteLater()
        qapp.processEvents()

    def test_cancelled_dialog_does_not_call_get_enrolled_results(self, qapp):
        """get_enrolled_results must NOT be called when the dialog is cancelled."""
        win = _make_window(qapp)
        win._speakers_list.clear()
        _add_speaker(win._speakers_list, "Test | Org | pending enrollment", participant_id="pid-t")

        with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
            mock_instance = MagicMock()
            mock_instance.exec.return_value = QDialog.DialogCode.Rejected
            MockDlg.return_value = mock_instance

            win._start_enrollment()

        mock_instance.get_enrolled_results.assert_not_called()

        win.deleteLater()
        qapp.processEvents()
