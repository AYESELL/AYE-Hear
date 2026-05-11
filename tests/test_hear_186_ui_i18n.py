from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from ayehear.i18n import Translator


def _make_window(language: str, qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    cfg = RuntimeConfig()
    cfg.protocol.language = language
    cfg.protocol.protocol_language = language

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=cfg)
    return win


def test_mainwindow_labels_are_german_in_de_mode(qapp):
    win = _make_window("de", qapp)

    assert win._meeting_box.title() == "Meeting-Setup"
    assert win._speakers_box.title() == "Sprecher-Enrollment"
    assert win._start_meeting_btn.text() == "Meeting starten"
    assert win._export_btn.text() == "Protokoll exportieren..."
    assert win._readiness_widget.title() == "System-Readiness"

    win.deleteLater()
    qapp.processEvents()


def test_mainwindow_labels_are_english_in_en_mode(qapp):
    win = _make_window("en", qapp)

    assert win._meeting_box.title() == "Meeting Setup"
    assert win._speakers_box.title() == "Speaker Enrollment"
    assert win._start_meeting_btn.text() == "Start Meeting"
    assert win._export_btn.text() == "Export Protocol..."
    assert win._readiness_widget.title() == "System Readiness"

    win.deleteLater()
    qapp.processEvents()


def test_protocol_language_switch_retranslates_core_labels(qapp):
    win = _make_window("de", qapp)

    idx_en = win._protocol_language.findData("en")
    assert idx_en >= 0
    win._protocol_language.setCurrentIndex(idx_en)
    qapp.processEvents()

    assert win._header_label.text() == "AYE Hear Workspace"
    assert win._meeting_box.title() == "Meeting Setup"
    assert win._start_meeting_btn.text() == "Start Meeting"
    assert win._export_btn.text() == "Export Protocol..."

    win.deleteLater()
    qapp.processEvents()


def test_enrollment_dialog_labels_follow_translator(qapp):
    from ayehear.app.enrollment_dialog import EnrollmentDialog

    translator = Translator("en")
    dialog = EnrollmentDialog(
        pending_speakers=[("Anna", "Corp", "pid-1")],
        speaker_manager=MagicMock(),
        translator=translator.tr,
    )

    assert dialog.windowTitle() == "Voice Enrollment"
    assert dialog._record_btn.text() == "▶️ Record (7 s)"
    assert dialog._status_lbl.text() == "Ready to record."

    dialog.deleteLater()
    qapp.processEvents()
