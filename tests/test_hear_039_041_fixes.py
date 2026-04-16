"""Regression tests for HEAR-039, HEAR-040, HEAR-041 fixes.

- HEAR-039: enumerate_input_devices() fallback behaviour
- HEAR-040: speaker list actions visible state + feedback label
- HEAR-041: Start Meeting session state + Show Current State dialog content
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Pre-import at module level so patch.dict does not evict it from sys.modules.
import ayehear.services.audio_capture as _ac

# ---------------------------------------------------------------------------
# HEAR-039: enumerate_input_devices
# ---------------------------------------------------------------------------


def test_enumerate_returns_list_when_sounddevice_available() -> None:
    """enumerate_input_devices returns (index, name) tuples for input devices."""
    fake_devices = [
        {"name": "Microphone (Realtek)", "max_input_channels": 2},
        {"name": "Loopback Output", "max_input_channels": 0},   # output only
        {"name": "Headset Mic", "max_input_channels": 1},
    ]
    fake_sd = MagicMock()
    fake_sd.query_devices.return_value = fake_devices

    with patch.dict(sys.modules, {"sounddevice": fake_sd}):
        result = _ac.enumerate_input_devices()

    assert len(result) == 2
    assert result[0] == (0, "Microphone (Realtek)")
    assert result[1] == (2, "Headset Mic")


def test_enumerate_returns_empty_list_when_sounddevice_missing() -> None:
    """Graceful fallback: empty list when sounddevice is not installed."""
    with patch.dict(sys.modules, {"sounddevice": None}):
        result = _ac.enumerate_input_devices()

    assert result == []


def test_enumerate_returns_empty_list_on_query_error() -> None:
    """Graceful fallback: empty list when sounddevice raises an exception."""
    fake_sd = MagicMock()
    fake_sd.query_devices.side_effect = RuntimeError("No audio backend")

    with patch.dict(sys.modules, {"sounddevice": fake_sd}):
        result = _ac.enumerate_input_devices()

    assert result == []


# ---------------------------------------------------------------------------
# HEAR-039: AudioCaptureProfile.device_index + _open_stream wiring
# ---------------------------------------------------------------------------


def test_audio_capture_profile_defaults_device_index_to_none() -> None:
    """AudioCaptureProfile.device_index defaults to None (WASAPI default)."""
    profile = _ac.AudioCaptureProfile()
    assert profile.device_index is None


def test_audio_capture_profile_accepts_explicit_device_index() -> None:
    """AudioCaptureProfile stores an explicit device index correctly."""
    profile = _ac.AudioCaptureProfile(device_index=3)
    assert profile.device_index == 3


def test_open_stream_passes_device_index_to_sounddevice() -> None:
    """AudioCaptureService passes profile.device_index to sounddevice.InputStream."""
    fake_stream = MagicMock()
    fake_sd = MagicMock()
    fake_sd.InputStream.return_value = fake_stream

    svc = _ac.AudioCaptureService(profile=_ac.AudioCaptureProfile(device_index=2))

    with patch.dict(sys.modules, {"sounddevice": fake_sd}):
        svc.start(lambda seg: None)

    kwargs = fake_sd.InputStream.call_args.kwargs
    assert kwargs.get("device") == 2


def test_open_stream_passes_none_for_default_profile() -> None:
    """When device_index is None, sounddevice receives device=None (WASAPI default)."""
    fake_stream = MagicMock()
    fake_sd = MagicMock()
    fake_sd.InputStream.return_value = fake_stream

    svc = _ac.AudioCaptureService(profile=_ac.AudioCaptureProfile())

    with patch.dict(sys.modules, {"sounddevice": fake_sd}):
        svc.start(lambda seg: None)

    kwargs = fake_sd.InputStream.call_args.kwargs
    assert kwargs.get("device") is None


# ---------------------------------------------------------------------------
# Helpers for UI tests (PySide6 required)
# ---------------------------------------------------------------------------

try:
    import PySide6.QtWidgets  # noqa: F401
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

pytestmark_qt = pytest.mark.skipif(not _QT_AVAILABLE, reason="PySide6 not available")


@pytest.fixture(scope="module")
def qt_app(qapp):
    """Module-scoped Qt fixture; delegates to the session-scoped qapp in conftest.py.

    Tracks every MainWindow created via _make_window() so that all of them are
    explicitly closed and scheduled for deletion at module teardown.  Without this,
    abandoned QMainWindow objects are garbage-collected at an unpredictable time,
    leaving Qt's internal threads in an inconsistent state and causing the next
    test module (test_mic_level_widget) to crash with a Windows access violation.
    """
    _windows: list = []
    yield qapp, _windows
    # Close and delete all tracked windows before the module fixture tears down.
    import gc

    for win in _windows:
        try:
            win._refresh_timer.stop()
            win._asr_timer.stop()
            win.close()
            win.deleteLater()
        except Exception:  # noqa: BLE001
            pass
    for _ in range(5):
        qapp.processEvents()
    gc.collect()
    for _ in range(3):
        qapp.processEvents()


def _make_window(qt_app_fixture):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    qapp, _windows = qt_app_fixture
    cfg = RuntimeConfig()
    win = MainWindow(runtime_config=cfg)
    _windows.append(win)
    return win


# ---------------------------------------------------------------------------
# HEAR-039: UI — device combo populated / fallback item present
# ---------------------------------------------------------------------------


@pytestmark_qt
def test_audio_device_combo_has_fallback_item(qt_app) -> None:
    """Fallback item is present even when no real devices found."""
    with patch("ayehear.app.window.enumerate_input_devices", return_value=[]):
        win = _make_window(qt_app)

    assert win._audio_device.count() >= 1
    assert "microphone" in win._audio_device.itemText(0).lower()


@pytestmark_qt
def test_audio_device_combo_populated_with_real_devices(qt_app) -> None:
    """Dropdown replaces fallback with real devices when available."""
    fake_devices = [(0, "Mic A"), (2, "Mic B")]
    with patch("ayehear.app.window.enumerate_input_devices", return_value=fake_devices):
        win = _make_window(qt_app)

    assert win._audio_device.count() == 2
    assert win._audio_device.itemText(0) == "Mic A"
    assert win._audio_device.itemText(1) == "Mic B"


@pytestmark_qt
def test_selected_audio_profile_returns_none_for_fallback(qt_app) -> None:
    """_selected_audio_profile() returns device_index=None when fallback item active."""
    with patch("ayehear.app.window.enumerate_input_devices", return_value=[]):
        win = _make_window(qt_app)

    profile = win._selected_audio_profile()
    assert profile.device_index is None


@pytestmark_qt
def test_selected_audio_profile_returns_correct_device_index(qt_app) -> None:
    """_selected_audio_profile() returns the sounddevice index of the chosen device."""
    fake_devices = [(3, "USB Mic")]
    with patch("ayehear.app.window.enumerate_input_devices", return_value=fake_devices):
        win = _make_window(qt_app)

    assert win._audio_device.count() == 1
    profile = win._selected_audio_profile()
    assert profile.device_index == 3


# ---------------------------------------------------------------------------
# HEAR-040: Speaker list actions + status label
# ---------------------------------------------------------------------------


@pytestmark_qt
def test_add_speaker_creates_item_and_sets_status(qt_app) -> None:
    win = _make_window(qt_app)
    initial_count = win._speakers_list.count()
    win._add_speaker()
    assert win._speakers_list.count() == initial_count + 1
    assert win._speaker_status.text() != ""


@pytestmark_qt
def test_edit_speaker_no_selection_sets_status(qt_app) -> None:
    win = _make_window(qt_app)
    win._speakers_list.clearSelection()
    # Deselect by clearing current item
    win._speakers_list.setCurrentRow(-1)
    # Patch QMessageBox so no dialog blocks the test
    with patch("ayehear.app.window.QMessageBox.information"):
        win._edit_speaker()
    assert win._speaker_status.text() != ""


@pytestmark_qt
def test_remove_speaker_with_confirmation(qt_app) -> None:
    win = _make_window(qt_app)
    win._speakers_list.setCurrentRow(0)
    count_before = win._speakers_list.count()
    with patch(
        "ayehear.app.window.QMessageBox.question",
        return_value=__import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.Yes,
    ):
        win._remove_speaker()
    assert win._speakers_list.count() == count_before - 1
    assert "entfernt" in win._speaker_status.text().lower()


@pytestmark_qt
def test_remove_speaker_cancelled_keeps_item(qt_app) -> None:
    win = _make_window(qt_app)
    win._speakers_list.setCurrentRow(0)
    count_before = win._speakers_list.count()
    with patch(
        "ayehear.app.window.QMessageBox.question",
        return_value=__import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox.StandardButton.No,
    ):
        win._remove_speaker()
    assert win._speakers_list.count() == count_before


@pytestmark_qt
def test_item_changed_signal_updates_status_label(qt_app) -> None:
    """itemChanged signal fires after inline edit commit and updates status (HEAR-040)."""
    win = _make_window(qt_app)
    item = win._speakers_list.item(0)
    item.setText("Aktualisierter Name | Org | enrolled")
    assert "Gespeichert" in win._speaker_status.text()
    assert "Aktualisierter Name" in win._speaker_status.text()


@pytestmark_qt
def test_item_changed_does_not_fire_before_signal_connected(qt_app) -> None:
    """Verifies the signal is wired AFTER initial item population so startup
    does not produce spurious status messages."""
    with patch("ayehear.app.window.enumerate_input_devices", return_value=[]):
        win = _make_window(qt_app)
    # After construction the status label must be empty (no spurious itemChanged)
    assert win._speaker_status.text() == ""


# ---------------------------------------------------------------------------
# HEAR-041: Start Meeting / Show Current State
# ---------------------------------------------------------------------------


@pytestmark_qt
def test_start_meeting_empty_title_shows_warning(qt_app) -> None:
    win = _make_window(qt_app)
    win._meeting_title.clear()
    with patch("ayehear.app.window.QMessageBox.warning") as mock_warn:
        win._start_meeting()
    mock_warn.assert_called_once()
    assert win._session is None


@pytestmark_qt
def test_start_meeting_no_speakers_shows_warning(qt_app) -> None:
    win = _make_window(qt_app)
    win._meeting_title.setText("Test Meeting")
    win._speakers_list.clear()
    with patch("ayehear.app.window.QMessageBox.warning") as mock_warn:
        win._start_meeting()
    mock_warn.assert_called_once()
    assert win._session is None


@pytestmark_qt
def test_start_meeting_valid_input_creates_session_and_updates_ui(qt_app) -> None:
    win = _make_window(qt_app)
    win._meeting_title.setText("Q2 Review")
    # Ensure at least one speaker entry
    if win._speakers_list.count() == 0:
        win._add_speaker()
        win._speakers_list.item(0).setText("Alice | AYE | enrolled")

    with patch("ayehear.app.window.QMessageBox.information"):
        win._start_meeting()

    assert win._session is not None
    assert win._session.title == "Q2 Review"
    # HEAR-041: visual session state
    assert "aktiv" in win._meeting_status_label.text().lower()
    assert not win._start_meeting_btn.isEnabled()
    assert win._stop_meeting_btn.isEnabled()
    # Transcript pane updated
    assert "Q2 Review" in win._transcript_view.toPlainText()


@pytestmark_qt
def test_stop_meeting_resets_ui(qt_app) -> None:
    win = _make_window(qt_app)
    win._meeting_title.setText("My Meeting")
    if win._speakers_list.count() == 0:
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        item = QListWidgetItem("Bob | Corp | enrolled")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        win._speakers_list.addItem(item)

    with patch("ayehear.app.window.QMessageBox.information"):
        win._start_meeting()

    win._stop_meeting()
    assert win._session is None
    assert "kein" in win._meeting_status_label.text().lower()
    assert win._start_meeting_btn.isEnabled()
    assert not win._stop_meeting_btn.isEnabled()


@pytestmark_qt
def test_stop_meeting_exports_protocol_and_transcript(qt_app, tmp_path: Path) -> None:
    win = _make_window(qt_app)
    win._meeting_title.setText("Export Test")

    with patch("ayehear.app.window.QMessageBox.information"):
        win._start_meeting()

    win._protocol_view.setPlainText("Summary\n- Export ready")
    win._transcript_view.setPlainText("[00:00] Anna: Hallo")

    with patch.object(win, "_resolve_export_dir", return_value=tmp_path):
        win._stop_meeting()

    exported = {path.name for path in tmp_path.iterdir() if path.is_file()}
    # HEAR-070: protocol now exported as Markdown, DOCX and PDF (no longer .txt)
    assert any(name.endswith("-protocol.md") for name in exported)
    assert any(name.endswith("-protocol.docx") for name in exported)
    assert any(name.endswith("-protocol.pdf") for name in exported)
    assert any(name.endswith("-transcript.txt") for name in exported)


@pytestmark_qt
def test_show_current_state_includes_device_and_speakers(qt_app) -> None:
    win = _make_window(qt_app)
    win._meeting_title.setText("Board Meeting")
    if win._speakers_list.count() == 0:
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        item = QListWidgetItem("Carol | Org | enrolled")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        win._speakers_list.addItem(item)

    captured_text: list[str] = []

    def _capture(parent, title, text):
        captured_text.append(text)

    with patch("ayehear.app.window.QMessageBox.information", side_effect=_capture):
        win._show_current_state()

    assert captured_text, "QMessageBox.information was not called"
    state_text = captured_text[0]
    assert "Board Meeting" in state_text
    assert "Audio" in state_text or "Ger" in state_text


@pytestmark_qt
def test_show_current_state_with_active_session_shows_session_info(qt_app) -> None:
    win = _make_window(qt_app)
    win._meeting_title.setText("Active Session Test")
    if win._speakers_list.count() == 0:
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        item = QListWidgetItem("Dave | X | enrolled")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        win._speakers_list.addItem(item)

    with patch("ayehear.app.window.QMessageBox.information"):
        win._start_meeting()

    captured: list[str] = []

    def _cap(parent, title, text):
        captured.append(text)

    with patch("ayehear.app.window.QMessageBox.information", side_effect=_cap):
        win._show_current_state()

    assert captured
    assert "Active Session Test" in captured[0]
    assert "\u2705" in captured[0]  # green checkmark for active session
