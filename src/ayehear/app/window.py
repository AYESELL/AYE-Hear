from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ayehear.models.runtime import RuntimeConfig

if TYPE_CHECKING:
    from ayehear.storage.repositories import (
        TranscriptSegmentRepository,
        ProtocolSnapshotRepository,
    )

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        runtime_config: RuntimeConfig,
        transcript_repo: "TranscriptSegmentRepository | None" = None,
        snapshot_repo: "ProtocolSnapshotRepository | None" = None,
    ) -> None:
        super().__init__()
        self.runtime_config = runtime_config
        self._transcript_repo = transcript_repo
        self._snapshot_repo = snapshot_repo
        self._active_meeting_id: str | None = None

        self.setWindowTitle("AYE Hear")
        self.resize(1440, 900)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("AYE Hear Workspace")
        header.setObjectName("pageTitle")
        header.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_setup_panel())
        splitter.addWidget(self._build_transcript_panel())
        splitter.addWidget(self._build_protocol_panel())
        splitter.setSizes([320, 500, 500])
        layout.addWidget(splitter)

        self.setCentralWidget(central)

        # Auto-refresh review queue every 10 s while a meeting is active
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(10_000)
        self._refresh_timer.timeout.connect(self._refresh_review_queue)

    # ------------------------------------------------------------------
    # Panel builders
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Panel builders
    # ------------------------------------------------------------------
    def _build_setup_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        meeting_box = QGroupBox("Meeting Setup")
        form = QFormLayout(meeting_box)
        form.addRow("Meeting Title", QLineEdit())

        meeting_type = QComboBox()
        meeting_type.addItems(self.runtime_config.protocol.meeting_modes)
        form.addRow("Meeting Type", meeting_type)

        participant_count = QSpinBox()
        participant_count.setRange(1, 30)
        participant_count.setValue(2)
        form.addRow("Participants", participant_count)

        naming_template = QComboBox()
        naming_template.addItems([
            "Herr/Frau + Last Name + Company",
            "First Name + Last Name + Company",
        ])
        form.addRow("Participant Template", naming_template)

        form.addRow("Default Input", QLineEdit("Windows default microphone"))
        layout.addWidget(meeting_box)

        speakers_box = QGroupBox("Speaker Enrollment")
        speakers_layout = QVBoxLayout(speakers_box)
        speakers_layout.addWidget(QLabel("Participants introduce themselves before recording starts."))
        speakers = QListWidget()
        speakers.addItems([
            "Frau Schneider | AYE | pending enrollment",
            "Max Weber | Customer GmbH | pending enrollment",
        ])
        speakers_layout.addWidget(speakers)
        speakers_layout.addWidget(QPushButton("Apply Participant Template"))
        speakers_layout.addWidget(QPushButton("Start Enrollment"))
        layout.addWidget(speakers_box)

        controls = QHBoxLayout()
        controls.addWidget(QPushButton("Start Meeting"))
        controls.addWidget(QPushButton("Show Current State"))
        layout.addLayout(controls)
        layout.addStretch(1)
        return panel

    def _build_transcript_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        status = QGroupBox("Live Transcript")
        status_layout = QVBoxLayout(status)
        status_layout.addWidget(QLabel("Input: default microphone | Whisper profile: balanced"))

        self._transcript_view = QPlainTextEdit()
        self._transcript_view.setReadOnly(True)
        self._transcript_view.setPlainText("[00:00] System: Meeting initialized.")
        status_layout.addWidget(self._transcript_view)
        layout.addWidget(status)
        return panel

    def _build_protocol_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        protocol_box = QGroupBox("Protocol Draft")
        protocol_layout = QVBoxLayout(protocol_box)
        protocol_layout.addWidget(QLabel("Decisions, action items and open questions update on significant events."))

        self._protocol_view = QPlainTextEdit()
        self._protocol_view.setReadOnly(True)
        self._protocol_view.setPlainText(
            "Summary\n"
            "- Meeting started with speaker enrollment.\n\n"
            "Decisions\n"
            "- Waiting for first confirmed decision.\n\n"
            "Action Items\n"
            "- No action items detected yet."
        )
        protocol_layout.addWidget(self._protocol_view)
        layout.addWidget(protocol_box)

        quality_box = QGroupBox("Review Queue")
        quality_layout = QVBoxLayout(quality_box)
        quality_layout.addWidget(QLabel("Unknown speakers and low-confidence assignments appear here."))

        self._review_list = QListWidget()
        quality_layout.addWidget(self._review_list)

        self._speaker_override = QComboBox()
        self._speaker_override.setEditable(True)
        self._speaker_override.setPlaceholderText("Assign correct speaker name…")
        quality_layout.addWidget(self._speaker_override)

        correct_btn = QPushButton("Apply Correction")
        correct_btn.clicked.connect(self._apply_speaker_correction)
        quality_layout.addWidget(correct_btn)

        layout.addWidget(quality_box)
        return panel

    # ------------------------------------------------------------------
    # Review Queue: load + correction logic (HEAR-016)
    # ------------------------------------------------------------------

    def set_active_meeting(self, meeting_id: str, known_speakers: list[str] | None = None) -> None:
        """Called by orchestrator when a meeting session becomes active."""
        self._active_meeting_id = meeting_id

        self._speaker_override.clear()
        for name in (known_speakers or []):
            self._speaker_override.addItem(name)

        self._refresh_review_queue()
        self._refresh_timer.start()

    def stop_active_meeting(self) -> None:
        self._refresh_timer.stop()
        self._active_meeting_id = None

    def _refresh_review_queue(self) -> None:
        """Reload low-confidence and uncorrected segments from the repository."""
        self._review_list.clear()

        if self._transcript_repo is None or self._active_meeting_id is None:
            item = QListWidgetItem("(No active meeting or repository not connected)")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._review_list.addItem(item)
            return

        try:
            segments = self._transcript_repo.low_confidence(
                self._active_meeting_id,
                threshold=self.runtime_config.protocol.minimum_confidence,
            )
        except Exception as exc:
            logger.error("Failed to load review queue: %s", exc)
            return

        for seg in segments:
            label = (
                f"[{seg.start_ms}ms] {seg.speaker_name} "
                f"(confidence={seg.confidence_score:.2f}): {seg.text[:60]}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, seg.id)
            self._review_list.addItem(item)

    def _apply_speaker_correction(self) -> None:
        """Persist a manual speaker correction for the selected review queue item."""
        selected = self._review_list.currentItem()
        corrected_name = self._speaker_override.currentText().strip()

        if selected is None or not corrected_name:
            QMessageBox.warning(self, "Correction", "Select a segment and enter a speaker name.")
            return

        segment_id: str = selected.data(Qt.ItemDataRole.UserRole)

        if self._transcript_repo is None:
            logger.warning("No transcript repository — correction not persisted.")
            return

        try:
            self._transcript_repo.apply_correction(segment_id, corrected_name)
            logger.info("Manual correction applied: segment=%s speaker=%s", segment_id, corrected_name)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not save correction:\n{exc}")
            return

        # Remove from queue and refresh protocol snapshot if available
        row = self._review_list.row(selected)
        self._review_list.takeItem(row)
        self._refresh_protocol_display()

    def _refresh_protocol_display(self) -> None:
        """Reload the latest protocol snapshot and update the protocol view."""
        if self._snapshot_repo is None or self._active_meeting_id is None:
            return
        try:
            snapshot = self._snapshot_repo.latest(self._active_meeting_id)
            if snapshot is None:
                return
            content = snapshot.content or {}
            lines: list[str] = []

            def _section(title: str, items: list[str]) -> None:
                lines.append(title)
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

            _section("Summary", content.get("summary", []))
            _section("Decisions", content.get("decisions", []))
            _section("Action Items", content.get("action_items", []))
            _section("Open Questions", content.get("open_questions", []))

            self._protocol_view.setPlainText("\n".join(lines).strip())
        except Exception as exc:
            logger.error("Protocol refresh failed: %s", exc)

    def append_transcript_line(self, line: str) -> None:
        """Append a new transcribed line to the live transcript view."""
        self._transcript_view.appendPlainText(line)
        # Scroll to bottom
        self._transcript_view.verticalScrollBar().setValue(
            self._transcript_view.verticalScrollBar().maximum()
        )
