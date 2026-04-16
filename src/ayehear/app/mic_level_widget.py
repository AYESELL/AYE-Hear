"""Live microphone state indicator and level meter widget (ADR-0004, HEAR-044).

Provides:
  MicState       – capture state enum (Idle, Initializing, Active, Degraded, Error)
  LevelBand      – RMS threshold mapping (low / ok / high)
  MicLevelWidget – QWidget shown in the setup panel; thread-safe via Signal/Slot

Design constraints (from architecture spec):
  - No raw-audio persistence.
  - No outbound network calls.
  - UI refresh 4-10 Hz; all Qt widget mutations happen on the UI thread.
  - No-signal degraded state after 3 s without a non-silent segment.
"""
from __future__ import annotations

import enum
import logging
from typing import Optional

from PySide6.QtCore import QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# ── RMS thresholds (normalised, per spec) ─────────────────────────────────────
_RMS_LOW_THRESHOLD = 0.01
_RMS_HIGH_THRESHOLD = 0.25

# No-signal timeout in milliseconds (spec: 3 s)
_NO_SIGNAL_TIMEOUT_MS = 3_000

# UI refresh cadence (100 ms = 10 Hz, within the 4-10 Hz target)
_LEVEL_UPDATE_INTERVAL_MS = 100

# Level-bar scale: map RMS 0.0-0.5 → 0-100
_RMS_SCALE = 200


# ── Enums ─────────────────────────────────────────────────────────────────────

class MicState(enum.Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    ERROR = "error"


class LevelBand(enum.Enum):
    LOW = "low"
    OK = "ok"
    HIGH = "high"


def rms_to_band(rms: float) -> LevelBand:
    """Map a normalised RMS value to the corresponding LevelBand."""
    if rms < _RMS_LOW_THRESHOLD:
        return LevelBand.LOW
    if rms <= _RMS_HIGH_THRESHOLD:
        return LevelBand.OK
    return LevelBand.HIGH


_GUIDANCE = {
    LevelBand.LOW: "Speak louder or move closer to microphone.",
    LevelBand.OK: "Input level looks good.",
    LevelBand.HIGH: "Input is very loud; reduce distance or gain.",
}

_STATE_LABEL = {
    MicState.IDLE: "Mic idle",
    MicState.INITIALIZING: "Mic initializing...",
    MicState.ACTIVE: "Mic active",
    MicState.ERROR: "Mic error",
}

_LEVEL_BAR_COLORS = {
    LevelBand.LOW: "#aaaaaa",
    LevelBand.OK: "#1a8a1a",
    LevelBand.HIGH: "#cc4400",
}


class MicLevelWidget(QWidget):
    """Setup-panel component displaying capture state, level bar, and guidance.

    All widget mutations are performed on the UI thread via Signal/Slot to
    ensure thread safety when called from the audio capture callback.

    Signals
    -------
    state_changed(MicState)
        Emitted whenever the capture state changes.
    """

    # Internal Signal used to cross the thread boundary from the audio callback
    # into the UI thread. Qt queued connection is automatic for cross-thread
    # signals when the receiving object lives in a different thread.
    _segment_received = Signal(float, bool)  # (rms, is_silence)

    state_changed = Signal(object)  # MicState

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._state: MicState = MicState.IDLE
        self._last_rms: float = 0.0
        self._pending_rms: float = 0.0
        self._has_pending: bool = False

        self._build_ui()
        self._connect_signals()
        self._apply_state(MicState.IDLE)

        # No-signal watchdog: fires if no non-silent segment arrives within 3 s
        self._no_signal_timer = QTimer(self)
        self._no_signal_timer.setSingleShot(True)
        self._no_signal_timer.setInterval(_NO_SIGNAL_TIMEOUT_MS)
        self._no_signal_timer.timeout.connect(self._on_no_signal_timeout)

        # Smooth level-bar refresh at ~10 Hz
        self._level_timer = QTimer(self)
        self._level_timer.setInterval(_LEVEL_UPDATE_INTERVAL_MS)
        self._level_timer.timeout.connect(self._refresh_level_bar)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(4)

        row = QHBoxLayout()
        self._state_label = QLabel("Mic idle")
        self._state_label.setStyleSheet("font-weight: 600;")
        row.addWidget(self._state_label)
        row.addStretch(1)
        outer.addLayout(row)

        self._level_bar = QProgressBar()
        self._level_bar.setRange(0, 100)
        self._level_bar.setValue(0)
        self._level_bar.setTextVisible(False)
        self._level_bar.setFixedHeight(10)
        outer.addWidget(self._level_bar)

        self._guidance_label = QLabel("")
        self._guidance_label.setStyleSheet("color: #555; font-size: 11px;")
        outer.addWidget(self._guidance_label)

    def _connect_signals(self) -> None:
        self._segment_received.connect(self._handle_segment)

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> MicState:
        return self._state

    def set_initializing(self) -> None:
        """Call when the capture service has been requested to open the device."""
        self._transition(MicState.INITIALIZING)

    def set_active(self) -> None:
        """Call when the capture stream is confirmed open and streaming."""
        self._transition(MicState.ACTIVE)
        self._no_signal_timer.start()
        self._level_timer.start()

    def set_error(self, reason: str = "") -> None:
        """Call when the capture device fails or the stream closes unexpectedly."""
        self._no_signal_timer.stop()
        self._level_timer.stop()
        label = f"Mic error: {reason}" if reason else "Mic error"
        self._state_label.setText(label)
        self._level_bar.setValue(0)
        self._guidance_label.setText("")
        if self._state != MicState.ERROR:
            self._state = MicState.ERROR
            self.state_changed.emit(MicState.ERROR)

    def reset(self) -> None:
        """Call on meeting stop to return to idle."""
        self._no_signal_timer.stop()
        self._level_timer.stop()
        self._transition(MicState.IDLE)
        self._last_rms = 0.0
        self._pending_rms = 0.0
        self._has_pending = False

    def on_audio_segment(self, rms: float, is_silence: bool) -> None:
        """Thread-safe entry point called from the audio capture callback.

        This method may be called from any thread.  It emits a queued Signal
        so that actual widget updates happen on the UI thread.
        """
        self._segment_received.emit(rms, is_silence)

    # ── Slots (always run on UI thread) ───────────────────────────────────────

    @Slot(float, bool)
    def _handle_segment(self, rms: float, is_silence: bool) -> None:
        if not is_silence:
            # Non-silent segment arrived — reset no-signal watchdog
            self._no_signal_timer.stop()
            self._no_signal_timer.start()

            if self._state in (MicState.INITIALIZING, MicState.DEGRADED):
                self._transition(MicState.ACTIVE)

        self._pending_rms = rms
        self._has_pending = True

    @Slot()
    def _refresh_level_bar(self) -> None:
        if not self._has_pending:
            return
        rms = self._pending_rms
        self._has_pending = False
        self._last_rms = rms

        scaled = min(100, int(rms * _RMS_SCALE))
        self._level_bar.setValue(scaled)

        band = rms_to_band(rms)
        color = _LEVEL_BAR_COLORS[band]
        self._level_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; }}"
        )
        self._guidance_label.setText(_GUIDANCE[band])

    @Slot()
    def _on_no_signal_timeout(self) -> None:
        """3 s without a non-silent segment → Degraded."""
        if self._state == MicState.ACTIVE:
            self._transition(MicState.DEGRADED)
            self._state_label.setText("No signal for 3s")
            self._guidance_label.setText("No signal detected. Check microphone connection.")

    # ── State-transition helper ────────────────────────────────────────────────

    def _apply_state(self, state: MicState) -> None:
        """Apply visual representation for a state (no transition logic)."""
        self._state_label.setText(_STATE_LABEL.get(state, state.value))
        if state in (MicState.IDLE, MicState.ERROR):
            self._level_bar.setValue(0)
            self._guidance_label.setText("")
        if state == MicState.INITIALIZING:
            self._guidance_label.setText("")
            self._level_bar.setValue(0)

    def _transition(self, new_state: MicState) -> None:
        if self._state == new_state:
            return
        logger.debug("MicLevelWidget: %s → %s", self._state.value, new_state.value)
        self._state = new_state
        self._apply_state(new_state)
        self.state_changed.emit(new_state)
