"""Unit tests for MicLevelWidget, MicState transitions, and RMS threshold mapping.

HEAR-044 — covers:
  - rms_to_band threshold mapping (low / ok / high)
  - MicLevelWidget state transitions (idle->initializing->active->degraded/error->idle)
  - No-signal timeout path
  - Thread-safe signal routing (on_audio_segment via queued signal)

Does NOT require pytest-qt; uses a QApplication fixture and
QApplication.processEvents() to flush the Qt event queue.
"""
from __future__ import annotations

import pytest

from PySide6.QtWidgets import QApplication

from ayehear.app.mic_level_widget import (
    LevelBand,
    MicState,
    _RMS_HIGH_THRESHOLD,
    _RMS_LOW_THRESHOLD,
    MicLevelWidget,
    rms_to_band,
)


# ── QApplication fixture ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    """Single QApplication instance for the test session."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def widget(qapp):
    w = MicLevelWidget()
    yield w
    # Stop timers before widget goes out of scope to prevent callbacks on dead objects
    w._no_signal_timer.stop()
    w._level_timer.stop()


def process_events(qapp):
    """Flush pending Qt events including queued signal deliveries."""
    for _ in range(5):
        qapp.processEvents()


# ── rms_to_band tests ─────────────────────────────────────────────────────────

class TestRmsToBand:
    def test_below_low_threshold_is_low(self):
        assert rms_to_band(0.0) == LevelBand.LOW
        assert rms_to_band(_RMS_LOW_THRESHOLD - 0.001) == LevelBand.LOW

    def test_exactly_low_threshold_is_ok(self):
        assert rms_to_band(_RMS_LOW_THRESHOLD) == LevelBand.OK

    def test_midrange_is_ok(self):
        assert rms_to_band(0.1) == LevelBand.OK

    def test_exactly_high_threshold_is_ok(self):
        assert rms_to_band(_RMS_HIGH_THRESHOLD) == LevelBand.OK

    def test_above_high_threshold_is_high(self):
        assert rms_to_band(_RMS_HIGH_THRESHOLD + 0.001) == LevelBand.HIGH
        assert rms_to_band(1.0) == LevelBand.HIGH

    def test_low_threshold_boundary_values(self):
        assert rms_to_band(0.0099) == LevelBand.LOW
        assert rms_to_band(0.01) == LevelBand.OK

    def test_high_threshold_boundary_values(self):
        assert rms_to_band(0.25) == LevelBand.OK
        assert rms_to_band(0.2501) == LevelBand.HIGH


# ── MicLevelWidget state-transition tests ─────────────────────────────────────

class TestMicLevelWidgetStateTransitions:
    def test_initial_state_is_idle(self, widget):
        assert widget.state == MicState.IDLE

    def test_set_initializing(self, widget):
        states = []
        widget.state_changed.connect(states.append)
        widget.set_initializing()
        assert widget.state == MicState.INITIALIZING
        assert states == [MicState.INITIALIZING]

    def test_set_active(self, widget):
        widget.set_initializing()
        states = []
        widget.state_changed.connect(states.append)
        widget.set_active()
        assert widget.state == MicState.ACTIVE
        assert states == [MicState.ACTIVE]

    def test_set_error(self, widget):
        widget.set_initializing()
        states = []
        widget.state_changed.connect(states.append)
        widget.set_error("device lost")
        assert widget.state == MicState.ERROR
        assert states == [MicState.ERROR]

    def test_reset_returns_to_idle(self, widget):
        widget.set_active()
        states = []
        widget.state_changed.connect(states.append)
        widget.reset()
        assert widget.state == MicState.IDLE
        assert states == [MicState.IDLE]

    def test_duplicate_transition_does_not_emit(self, widget):
        widget.set_initializing()
        states = []
        widget.state_changed.connect(states.append)
        widget.set_initializing()  # already INITIALIZING
        assert states == []

    def test_error_state_label_includes_reason(self, widget):
        widget.set_error("USB disconnected")
        assert "USB disconnected" in widget._state_label.text()

    def test_error_state_empty_reason(self, widget):
        widget.set_error()
        assert widget._state_label.text() == "Mic error"


# ── Level-bar tests ───────────────────────────────────────────────────────────

class TestMicLevelWidgetLevelBar:
    def test_level_bar_updates_on_segment(self, qapp, widget):
        widget.set_active()
        widget.on_audio_segment(rms=0.1, is_silence=False)
        process_events(qapp)
        assert widget._pending_rms == pytest.approx(0.1)
        assert widget._has_pending is True

    def test_refresh_level_bar_updates_value(self, widget):
        widget.set_active()
        widget._pending_rms = 0.1
        widget._has_pending = True
        widget._refresh_level_bar()
        expected = min(100, int(0.1 * 200))
        assert widget._level_bar.value() == expected

    def test_refresh_level_bar_skips_when_no_pending(self, widget):
        widget.set_active()
        widget._has_pending = False
        widget._level_bar.setValue(42)
        widget._refresh_level_bar()
        assert widget._level_bar.value() == 42

    def test_refresh_level_bar_low_rms_guidance(self, widget):
        widget.set_active()
        widget._pending_rms = 0.005
        widget._has_pending = True
        widget._refresh_level_bar()
        text = widget._guidance_label.text().lower()
        assert "louder" in text or "closer" in text

    def test_refresh_level_bar_ok_rms_guidance(self, widget):
        widget.set_active()
        widget._pending_rms = 0.1
        widget._has_pending = True
        widget._refresh_level_bar()
        assert "good" in widget._guidance_label.text().lower()

    def test_refresh_level_bar_high_rms_guidance(self, widget):
        widget.set_active()
        widget._pending_rms = 0.5
        widget._has_pending = True
        widget._refresh_level_bar()
        assert "loud" in widget._guidance_label.text().lower()


# ── No-signal timeout tests ───────────────────────────────────────────────────

class TestMicLevelWidgetNoSignalTimeout:
    def test_no_signal_triggers_degraded(self, widget):
        widget.set_active()
        states: list[MicState] = []
        widget.state_changed.connect(states.append)
        widget._no_signal_timer.stop()
        widget._on_no_signal_timeout()
        assert widget.state == MicState.DEGRADED
        assert MicState.DEGRADED in states

    def test_non_silent_segment_restarts_timer(self, qapp, widget):
        widget.set_active()
        widget._no_signal_timer.stop()
        assert not widget._no_signal_timer.isActive()
        widget.on_audio_segment(rms=0.05, is_silence=False)
        process_events(qapp)
        assert widget._no_signal_timer.isActive()

    def test_degraded_recovers_on_non_silent_segment(self, qapp, widget):
        widget.set_active()
        widget._on_no_signal_timeout()
        assert widget.state == MicState.DEGRADED
        states: list[MicState] = []
        widget.state_changed.connect(states.append)
        widget.on_audio_segment(rms=0.05, is_silence=False)
        process_events(qapp)
        assert widget.state == MicState.ACTIVE
        assert MicState.ACTIVE in states

    def test_no_signal_timer_stops_on_reset(self, widget):
        widget.set_active()
        assert widget._no_signal_timer.isActive()
        widget.reset()
        assert not widget._no_signal_timer.isActive()

    def test_no_signal_timer_stops_on_error(self, widget):
        widget.set_active()
        assert widget._no_signal_timer.isActive()
        widget.set_error("fault")
        assert not widget._no_signal_timer.isActive()

    def test_level_timer_stops_on_reset(self, widget):
        widget.set_active()
        assert widget._level_timer.isActive()
        widget.reset()
        assert not widget._level_timer.isActive()

    def test_no_signal_label_text(self, widget):
        widget.set_active()
        widget._on_no_signal_timeout()
        assert "signal" in widget._state_label.text().lower()
