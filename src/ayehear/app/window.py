from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from ayehear.models.meeting import MeetingSession, Participant
from ayehear.models.runtime import RuntimeConfig
from ayehear.services.audio_capture import AudioCaptureProfile, enumerate_input_devices

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
        self._session: MeetingSession | None = None

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

        self._meeting_title = QLineEdit()
        form.addRow("Meeting Title", self._meeting_title)

        self._meeting_type = QComboBox()
        self._meeting_type.addItems(self.runtime_config.protocol.meeting_modes)
        form.addRow("Meeting Type", self._meeting_type)

        self._participant_count = QSpinBox()
        self._participant_count.setRange(1, 30)
        self._participant_count.setValue(2)
        form.addRow("Participants", self._participant_count)

        self._naming_template = QComboBox()
        self._naming_template.addItems([
            "Herr/Frau + Last Name + Company",
            "First Name + Last Name + Company",
        ])
        form.addRow("Participant Template", self._naming_template)

        # HEAR-039: real Windows device selector
        self._audio_device = QComboBox()
        self._audio_device.addItem("Windows default microphone", userData=None)
        self._populate_audio_devices()
        form.addRow("Audio Input", self._audio_device)
        layout.addWidget(meeting_box)

        speakers_box = QGroupBox("Speaker Enrollment")
        speakers_layout = QVBoxLayout(speakers_box)
        speakers_layout.addWidget(QLabel(
            "Doppelklick zum Bearbeiten. Format: Name | Organisation | Status"
        ))

        self._speakers_list = QListWidget()
        self._speakers_list.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        for entry in [
            "Frau Schneider | AYE | pending enrollment",
            "Max Weber | Customer GmbH | pending enrollment",
        ]:
            item = QListWidgetItem(entry)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._speakers_list.addItem(item)
        speakers_layout.addWidget(self._speakers_list)
        # HEAR-040: update status label after any user-committed inline edit
        self._speakers_list.itemChanged.connect(self._on_speaker_item_changed)

        speaker_btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add")
        add_btn.setToolTip("Neuen Sprecher hinzufügen")
        add_btn.clicked.connect(self._add_speaker)
        edit_btn = QPushButton("Edit")
        edit_btn.setToolTip("Ausgewählten Sprecher bearbeiten")
        edit_btn.clicked.connect(self._edit_speaker)
        remove_btn = QPushButton("Remove")
        remove_btn.setToolTip("Ausgewählten Sprecher entfernen")
        remove_btn.clicked.connect(self._remove_speaker)
        speaker_btn_row.addWidget(add_btn)
        speaker_btn_row.addWidget(edit_btn)
        speaker_btn_row.addWidget(remove_btn)
        speakers_layout.addLayout(speaker_btn_row)

        # HEAR-040: visible feedback label for speaker actions
        self._speaker_status = QLabel("")
        self._speaker_status.setStyleSheet("color: #1a7a1a; font-weight: 600;")
        speakers_layout.addWidget(self._speaker_status)

        apply_template_btn = QPushButton("Apply Participant Template")
        apply_template_btn.clicked.connect(self._apply_participant_template)
        speakers_layout.addWidget(apply_template_btn)

        start_enrollment_btn = QPushButton("Start Enrollment")
        start_enrollment_btn.clicked.connect(self._start_enrollment)
        speakers_layout.addWidget(start_enrollment_btn)

        layout.addWidget(speakers_box)

        # HEAR-041: meeting status indicator
        self._meeting_status_label = QLabel("\u26aa Kein aktives Meeting")
        self._meeting_status_label.setStyleSheet("font-weight: 600; color: #888;")
        layout.addWidget(self._meeting_status_label)

        controls = QHBoxLayout()
        self._start_meeting_btn = QPushButton("Start Meeting")
        self._start_meeting_btn.clicked.connect(self._start_meeting)
        self._stop_meeting_btn = QPushButton("Stop Meeting")
        self._stop_meeting_btn.clicked.connect(self._stop_meeting)
        self._stop_meeting_btn.setEnabled(False)
        show_state_btn = QPushButton("Show Current State")
        show_state_btn.clicked.connect(self._show_current_state)
        controls.addWidget(self._start_meeting_btn)
        controls.addWidget(self._stop_meeting_btn)
        controls.addWidget(show_state_btn)
        layout.addLayout(controls)
        layout.addStretch(1)
        return panel

    # ------------------------------------------------------------------
    # HEAR-039: audio device helpers
    # ------------------------------------------------------------------

    def _populate_audio_devices(self) -> None:
        """Fill the Audio Input dropdown with available Windows capture devices."""
        devices = enumerate_input_devices()
        if devices:
            self._audio_device.clear()
            for idx, name in devices:
                self._audio_device.addItem(name, userData=idx)
        # If no devices found the fallback item set during construction remains.

    def _selected_audio_profile(self) -> AudioCaptureProfile:
        """Return an AudioCaptureProfile for the selected input device (HEAR-039).

        device_index is the sounddevice index (int) or None for WASAPI default.
        Use this when starting AudioCaptureService once the audio pipeline is
        integrated (ADR-0004).
        """
        device_index: int | None = self._audio_device.currentData()
        return AudioCaptureProfile(device_index=device_index)

    # ------------------------------------------------------------------
    # Speaker management (HEAR-036 / HEAR-040)
    # ------------------------------------------------------------------

    def _on_speaker_item_changed(self, item: QListWidgetItem) -> None:
        """Update feedback label after user commits an inline edit (HEAR-040)."""
        self._set_speaker_status(f"Gespeichert: {item.text()[:40]}")

    def _set_speaker_status(self, message: str) -> None:
        """Show a short status message below the speaker list."""
        self._speaker_status.setText(message)

    def _add_speaker(self) -> None:
        """Add a new editable speaker entry to the list."""
        item = QListWidgetItem("Name | Organisation | pending enrollment")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._speakers_list.addItem(item)
        self._speakers_list.setCurrentItem(item)
        self._speakers_list.editItem(item)
        self._set_speaker_status("Neuer Sprecher hinzugef\u00fcgt \u2014 Namen direkt editieren.")

    def _edit_speaker(self) -> None:
        """Inline-Edit des ausgewählten Sprecher-Eintrags."""
        item = self._speakers_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Edit Speaker", "Bitte einen Sprecher ausw\u00e4hlen.")
            self._set_speaker_status("Kein Sprecher ausgew\u00e4hlt.")
            return
        self._speakers_list.editItem(item)
        self._set_speaker_status(f"Bearbeite: {item.text()[:40]}")

    def _remove_speaker(self) -> None:
        """Entfernt den ausgewählten Sprecher nach Bestätigung."""
        item = self._speakers_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Remove Speaker", "Bitte einen Sprecher ausw\u00e4hlen.")
            self._set_speaker_status("Kein Sprecher ausgew\u00e4hlt.")
            return
        answer = QMessageBox.question(
            self,
            "Sprecher entfernen",
            f"'{item.text()}' entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            name = item.text()
            self._speakers_list.takeItem(self._speakers_list.row(item))
            self._set_speaker_status(f"Sprecher entfernt: {name[:40]}")

    def _get_speaker_texts(self) -> list[str]:
        """Gibt alle nicht-leeren Sprecher-Texte zurück."""
        result = []
        for i in range(self._speakers_list.count()):
            text = self._speakers_list.item(i).text().strip()
            if text:
                result.append(text)
        return result

    # ------------------------------------------------------------------
    # Setup action handlers (HEAR-037)
    # ------------------------------------------------------------------

    def _apply_participant_template(self) -> None:
        """Generiert Platzhalter-Sprecher aus Anzahl und Namens-Template."""
        count = self._participant_count.value()
        use_salutation = self._naming_template.currentText().startswith("Herr/Frau")
        self._speakers_list.clear()
        for i in range(1, count + 1):
            if use_salutation:
                text = f"Herr/Frau Teilnehmer_{i} | Organisation | pending enrollment"
            else:
                text = f"Vorname_{i} Nachname_{i} | Organisation | pending enrollment"
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._speakers_list.addItem(item)

    def _start_enrollment(self) -> None:
        """Startet den Speaker-Enrollment-Prozess (Platzhalter – ADR-0004)."""
        speakers = self._get_speaker_texts()
        if not speakers:
            QMessageBox.warning(self, "Enrollment", "Bitte mindestens einen Sprecher hinzufügen.")
            return
        QMessageBox.information(
            self,
            "Speaker Enrollment",
            f"Enrollment gestartet für {len(speakers)} Sprecher.\n\n"
            "Teilnehmer sprechen jetzt ihren Namen in das Mikrofon.\n\n"
            "Hinweis: Audio-Pipeline-Integration ausstehend (ADR-0004).",
        )

    def _start_meeting(self) -> None:
        """Validiert das Setup und startet eine Meeting-Session."""
        title = self._meeting_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Start Meeting", "Bitte einen Meeting-Titel eingeben.")
            self._meeting_title.setFocus()
            return

        speakers = self._get_speaker_texts()
        if not speakers:
            QMessageBox.warning(self, "Start Meeting", "Bitte mindestens einen Sprecher hinzufügen.")
            return

        import uuid
        from datetime import datetime

        participants: list[Participant] = []
        for s in speakers:
            parts = [p.strip() for p in s.split("|")]
            display = parts[0] if parts else s
            org = parts[1] if len(parts) > 1 else ""
            name_parts = display.split()
            last = name_parts[-1] if name_parts else display
            first: str | None = " ".join(name_parts[:-1]) if len(name_parts) > 1 else None
            participants.append(
                Participant(first_name=first, last_name=last, organization=org, role="participant")
            )

        device_label = self._audio_device.currentText()

        self._session = MeetingSession(
            title=title,
            mode=self._meeting_type.currentText(),
            meeting_type=self._meeting_type.currentText(),
            participants=participants,
            started_at=datetime.now(),
        )

        meeting_id = str(uuid.uuid4())
        known_speakers = [p.display_name for p in self._session.participants]
        self.set_active_meeting(meeting_id, known_speakers=known_speakers)

        # HEAR-041: transcript + protocol reflect meeting start
        self.append_transcript_line(
            f"[00:00] Meeting '{title}' gestartet — {len(speakers)} Teilnehmer "
            f"| Audio: {device_label}."
        )
        self._protocol_view.setPlainText(
            f"Meeting: {title}\n"
            f"Typ:     {self._meeting_type.currentText()}\n"
            f"Audio:   {device_label}\n"
            f"Sprecher ({len(speakers)}): {', '.join(speakers[:5])}\n\n"
            "Decisions\n- Waiting for first confirmed decision.\n\n"
            "Action Items\n- No action items detected yet."
        )

        # HEAR-041: visible session state
        self._meeting_status_label.setText(f"\U0001f7e2 Meeting aktiv: {title}")
        self._meeting_status_label.setStyleSheet("font-weight: 700; color: #1a7a1a;")
        self._start_meeting_btn.setEnabled(False)
        self._stop_meeting_btn.setEnabled(True)

        QMessageBox.information(self, "Meeting gestartet", f"Meeting '{title}' ist jetzt aktiv.")

    def _stop_meeting(self) -> None:
        """Beendet die aktive Meeting-Session (HEAR-041)."""
        self.stop_active_meeting()
        self._session = None
        self._meeting_status_label.setText("\u26aa Kein aktives Meeting")
        self._meeting_status_label.setStyleSheet("font-weight: 600; color: #888;")
        self._start_meeting_btn.setEnabled(True)
        self._stop_meeting_btn.setEnabled(False)
        self.append_transcript_line("[--:--] Meeting beendet.")

    def _show_current_state(self) -> None:
        """Zeigt einen Dialog mit dem aktuellen Setup- und Session-Status (HEAR-041)."""
        title = self._meeting_title.text().strip() or "(nicht gesetzt)"
        mode = self._meeting_type.currentText()
        device = self._audio_device.currentText()
        speakers = self._get_speaker_texts()

        lines = [
            f"Meeting-Titel:  {title}",
            f"Meeting-Typ:    {mode}",
            f"Audio-Ger\u00e4t:   {device}",
            f"Sprecher ({len(speakers)}):",
        ]
        for s in speakers:
            lines.append(f"  \u2022 {s}")
        lines.append("")
        if self._session is not None:
            lines.append(f"\u2705 Aktive Session: {self._session.title}")
            lines.append(f"   Gestartet:    {self._session.started_at.strftime('%H:%M:%S')}")
            lines.append(f"   Teilnehmer:   {len(self._session.participants)}")
        else:
            lines.append("\u26aa Keine aktive Meeting-Session.")

        QMessageBox.information(self, "Aktueller Status", "\n".join(lines))

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
            content = snapshot.snapshot_content or {}
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
