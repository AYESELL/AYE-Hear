"""Voice Enrollment Dialog for AYE Hear (HEAR-068).

Implements real microphone-based speaker enrollment as required by ADR-0003 Stage 1:
  - User selects a pending speaker from the list
  - Clicks Record: AudioCaptureService captures 7 seconds of speech
  - Embedding is extracted, profile persisted via SpeakerManager.enroll()
  - UI shows status transitions: pending -> recording -> enrolled / failed

Usage::

    pending = [("Frau Schneider", "AYE", "uuid-1"), ("Max Weber", "Corp", "uuid-2")]
    dlg = EnrollmentDialog(pending, speaker_manager, parent=window)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        for participant_id, profile_id in dlg.get_enrolled_results().items():
            print(f"{participant_id} enrolled with profile {profile_id}")
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime

import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ayehear.services.audio_capture import AudioCaptureProfile, AudioCaptureService, AudioSegment
from ayehear.services.speaker_manager import SpeakerManager

logger = logging.getLogger(__name__)

# Default recording duration in milliseconds (ADR-0003: 5-10 seconds reference phrase)
_DEFAULT_RECORDING_MS = 7_000
# Progress timer tick in milliseconds
_PROGRESS_TICK_MS = 100

# Known enrollment statuses that should be shown in the speaker list
_STATUS_PENDING = "pending enrollment"
_STATUS_RECORDING = "recording..."
_STATUS_ENROLLED_PREFIX = "enrolled"
_STATUS_FAILED = "enrollment failed"

# Enrollment phrase shown to the user (German, clear and natural)
_ENROLLMENT_PHRASE = (
    "\u201eMein Name ist [Ihr Name] und ich nehme an diesem Meeting teil.\u201c"
)


class EnrollmentDialog(QDialog):
    """Modal dialog for pre-meeting voice enrollment of all pending speakers.

    Thread-safety: AudioCaptureService fires callbacks on an audio thread.
    Audio chunks are collected into ``_captured_chunks`` protected by ``_lock``.
    All UI mutations happen on the main thread via QTimer slots.
    """

    def __init__(
        self,
        pending_speakers: list[tuple[str, str, str]],
        speaker_manager: SpeakerManager,
        *,
        recording_duration_ms: int = _DEFAULT_RECORDING_MS,
        capture_factory: Callable[[], AudioCaptureService] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialise the dialog.

        Args:
            pending_speakers: List of (display_name, organisation, participant_id) tuples
                for speakers that still need enrollment.  ``participant_id`` is the
                stable identity key used in enrollment results (not the display name).
            speaker_manager: SpeakerManager instance used to extract and persist
                voice embeddings.
            recording_duration_ms: How long to record each speaker (default 7 s).
            capture_factory: Optional factory that creates an AudioCaptureService.
                Inject a mock in tests to avoid real audio hardware.
            parent: Optional Qt parent widget.
        """
        super().__init__(parent)
        self._pending_speakers = list(pending_speakers)
        self._speaker_manager = speaker_manager
        self._recording_duration_ms = recording_duration_ms
        self._capture_factory = capture_factory or self._default_capture_factory

        self._capture_service: AudioCaptureService | None = None
        self._captured_chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._enrolled_results: dict[str, str] = {}  # participant_id -> profile_id

        self._elapsed_ms = 0

        self._setup_ui()

        # QTimer for stopping the recording after the configured duration
        self._record_timer = QTimer(self)
        self._record_timer.setSingleShot(True)
        self._record_timer.timeout.connect(self._finish_recording)

        # QTimer for updating the progress bar during recording
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(_PROGRESS_TICK_MS)
        self._progress_timer.timeout.connect(self._tick_progress)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("Stimm-Enrollment")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        instr_box = QGroupBox("Anleitung")
        instr_layout = QVBoxLayout(instr_box)
        instr_layout.addWidget(QLabel(
            "Sprechen Sie nach dem Klick auf <b>Aufnehmen</b> die folgende Phrase\n"
            "laut und deutlich in das Mikrofon (7 Sekunden):"
        ))
        phrase_lbl = QLabel(_ENROLLMENT_PHRASE)
        phrase_lbl.setStyleSheet("font-style: italic; font-size: 13px; color: #1a4a7a;")
        phrase_lbl.setWordWrap(True)
        instr_layout.addWidget(phrase_lbl)
        layout.addWidget(instr_box)

        layout.addWidget(QLabel("Sprecher (auswählen, dann Aufnehmen drücken):"))
        self._speaker_list = QListWidget()
        for name, org, participant_id in self._pending_speakers:
            item = QListWidgetItem(f"{name} | {org}")
            item.setData(Qt.ItemDataRole.UserRole, (name, org, participant_id))
            self._speaker_list.addItem(item)
        if self._speaker_list.count() > 0:
            self._speaker_list.setCurrentRow(0)
        layout.addWidget(self._speaker_list)

        self._status_lbl = QLabel("Bereit zur Aufnahme.")
        self._status_lbl.setStyleSheet("font-weight: 600;")
        layout.addWidget(self._status_lbl)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, self._recording_duration_ms)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%v ms / %m ms")
        layout.addWidget(self._progress_bar)

        btn_row = QHBoxLayout()
        self._record_btn = QPushButton("\u25b6\ufe0f Aufnehmen (7 s)")
        self._record_btn.clicked.connect(self._on_record_clicked)
        btn_row.addWidget(self._record_btn)

        close_btn = QPushButton("Fertig")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_enrolled_results(self) -> dict[str, str]:
        """Return dict of participant_id -> profile_id for all successfully enrolled speakers."""
        return dict(self._enrolled_results)

    # ------------------------------------------------------------------
    # Recording flow (triggered by UI)
    # ------------------------------------------------------------------

    def _on_record_clicked(self) -> None:
        """Start audio capture for the currently selected speaker."""
        item = self._speaker_list.currentItem()
        if item is None:
            self._set_status("Bitte zuerst einen Sprecher aus der Liste auswählen.", error=False)
            return

        name, org, _participant_id = item.data(Qt.ItemDataRole.UserRole)

        # Reset capture state
        with self._lock:
            self._captured_chunks = []
        self._elapsed_ms = 0
        self._progress_bar.setValue(0)
        self._record_btn.setEnabled(False)

        # Update list item to show "recording" state
        item.setText(f"{name} | {org} | {_STATUS_RECORDING}")
        self._set_status(f"Aufnahme für {name!r} läuft… sprechen Sie jetzt!", error=False)

        # Start audio capture
        self._capture_service = self._capture_factory()
        try:
            self._capture_service.start(self._on_audio_segment)
        except Exception as exc:
            logger.error("Audio capture start failed: %s", exc)
            item.setText(f"{name} | {org} | {_STATUS_FAILED}")
            self._set_status(f"Audio-Start fehlgeschlagen: {exc}", error=True)
            self._capture_service = None
            self._record_btn.setEnabled(True)
            return

        # Start progress + stop timers
        self._progress_timer.start()
        self._record_timer.start(self._recording_duration_ms)
        logger.info("Enrollment recording started for speaker '%s'", name)

    def _on_audio_segment(self, segment: AudioSegment) -> None:
        """Collect non-silent audio chunks from the capture thread (thread-safe)."""
        chunk = np.asarray(segment.samples, dtype=np.float32).reshape(-1)
        if chunk.size > 0:
            with self._lock:
                self._captured_chunks.append(chunk)

    def _tick_progress(self) -> None:
        self._elapsed_ms += _PROGRESS_TICK_MS
        self._progress_bar.setValue(min(self._elapsed_ms, self._recording_duration_ms))

    def _finish_recording(self) -> None:
        """Called when the recording timer fires — stop capture and run enrollment."""
        self._progress_timer.stop()
        self._progress_bar.setValue(self._recording_duration_ms)

        if self._capture_service is not None:
            try:
                self._capture_service.stop()
            except Exception as exc:
                logger.warning("Error stopping capture service: %s", exc)
            self._capture_service = None

        with self._lock:
            chunks = list(self._captured_chunks)

        item = self._speaker_list.currentItem()
        if item is None:
            self._record_btn.setEnabled(True)
            return

        name, org, participant_id = item.data(Qt.ItemDataRole.UserRole)

        if not chunks:
            item.setText(f"{name} | {org} | {_STATUS_PENDING}")
            self._set_status(
                "Keine Audiodaten aufgenommen. Mikrofon prüfen und erneut versuchen.",
                error=True,
            )
            self._record_btn.setEnabled(True)
            logger.warning("No audio captured for speaker '%s'", name)
            return

        samples = np.concatenate(chunks).tolist()
        logger.info(
            "Recording finished for '%s': %.1f seconds captured",
            name,
            len(samples) / 16_000,
        )
        self._do_enroll(item, name, org, participant_id, samples)

    def _do_enroll(
        self,
        item: QListWidgetItem,
        name: str,
        org: str,
        participant_id: str,
        samples: list[float],
    ) -> None:
        """Extract embedding and persist speaker profile via SpeakerManager."""
        self._set_status(f"Embedding wird berechnet für {name!r}…", error=False)

        try:
            result = self._speaker_manager.enroll(
                participant_id=participant_id,
                display_name=name,
                audio_samples=samples,
            )
        except Exception as exc:
            logger.error("Enrollment raised exception for '%s': %s", name, exc)
            item.setText(f"{name} | {org} | {_STATUS_FAILED}")
            self._set_status(f"Enrollment fehlgeschlagen: {exc}", error=True)
            self._record_btn.setEnabled(True)
            return

        if result.success:
            self._enrolled_results[participant_id] = result.profile_id
            item.setText(f"{name} | {org} | {_STATUS_ENROLLED_PREFIX} (id: {result.profile_id[:8]})")
            self._set_status(
                f"\u2713 {name!r} erfolgreich enrolliert"
                f" (Embedding-Dim: {result.embedding_dim}).",
                error=False,
            )
            logger.info(
                "Speaker '%s' enrolled: profile_id=%s embedding_dim=%d",
                name,
                result.profile_id,
                result.embedding_dim,
            )
        else:
            item.setText(f"{name} | {org} | {_STATUS_FAILED}")
            self._set_status(
                f"Enrollment fehlgeschlagen für {name!r}: {result.error}",
                error=True,
            )
            logger.error("Enrollment failed for '%s': %s", name, result.error)

        self._record_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str, *, error: bool) -> None:
        color = "#a00000" if error else "#1a7a1a"
        self._status_lbl.setStyleSheet(f"font-weight: 600; color: {color};")
        self._status_lbl.setText(message)

    @staticmethod
    def _default_capture_factory() -> AudioCaptureService:
        return AudioCaptureService(profile=AudioCaptureProfile())

    # ------------------------------------------------------------------
    # Cleanup on close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._record_timer.stop()
        self._progress_timer.stop()
        if self._capture_service is not None:
            try:
                self._capture_service.stop()
            except Exception:
                pass
            self._capture_service = None
        super().closeEvent(event)
