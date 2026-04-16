from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
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

from ayehear.app.enrollment_dialog import EnrollmentDialog
from ayehear.app.mic_level_widget import MicLevelWidget
from ayehear.models.meeting import MeetingSession, Participant
from ayehear.models.runtime import RuntimeConfig
from ayehear.services.audio_capture import (
    AudioCaptureProfile,
    AudioCaptureService,
    AudioSegment,
    enumerate_input_devices,
)
from ayehear.services.speaker_manager import SpeakerManager
from ayehear.services.transcription import TranscriptionService

if TYPE_CHECKING:
    from ayehear.storage.repositories import (
        TranscriptSegmentRepository,
        ProtocolSnapshotRepository,
    )

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    transcript_line_ready = Signal(str)

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        transcript_repo: "TranscriptSegmentRepository | None" = None,
        snapshot_repo: "ProtocolSnapshotRepository | None" = None,
        speaker_manager: "SpeakerManager | None" = None,
    ) -> None:
        super().__init__()
        self.runtime_config = runtime_config
        self._transcript_repo = transcript_repo
        self._snapshot_repo = snapshot_repo
        self._active_meeting_id: str | None = None
        self._session: MeetingSession | None = None
        self._audio_capture_service: AudioCaptureService | None = None
        self._transcription_service = TranscriptionService(
            profile=self.runtime_config.models.whisper_profile,
            language="de",
            transcript_repo=transcript_repo,
        )
        # ADR-0003: speaker identification pipeline
        self._speaker_manager: SpeakerManager = speaker_manager or SpeakerManager()
        self._enrolled_speakers: dict[str, str] = {}  # participant_id -> profile_id
        self._audio_buffer_lock = threading.Lock()
        self._pending_audio_chunks: list[np.ndarray] = []
        self._pending_start_ms: int | None = None
        self._pending_end_ms: int = 0
        self._pending_duration_ms: int = 0
        self._asr_warned_no_text = False

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

        self._asr_timer = QTimer(self)
        self._asr_timer.setInterval(1000)
        self._asr_timer.timeout.connect(self._process_pending_audio)
        self.transcript_line_ready.connect(self.append_transcript_line)

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
            import uuid as _uuid
            item = QListWidgetItem(entry)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.setData(Qt.ItemDataRole.UserRole, str(_uuid.uuid4()))
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
        # HEAR-044: live mic state + level meter
        self._mic_level_widget = MicLevelWidget()
        layout.addWidget(self._mic_level_widget)
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
        import uuid as _uuid
        item = QListWidgetItem("Name | Organisation | pending enrollment")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        item.setData(Qt.ItemDataRole.UserRole, str(_uuid.uuid4()))
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
        import uuid as _uuid
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
            item.setData(Qt.ItemDataRole.UserRole, str(_uuid.uuid4()))
            self._speakers_list.addItem(item)

    def _start_enrollment(self) -> None:
        """Open the real voice enrollment dialog (HEAR-074 / ADR-0003 Stage 1).

        Collects pending speakers from the list, opens EnrollmentDialog for
        microphone-based recording, and updates list item status after each
        successful enrollment.  The dialog guides the user with on-screen
        instructions and shows status transitions (pending → recording →
        enrolled / failed).

        Speaker items are identified by a stable UUID stored in
        ``Qt.ItemDataRole.UserRole`` so that display-name changes do not break
        enrollment linkage (HEAR-079).
        """
        import uuid as _uuid
        pending: list[tuple[str, str, str]] = []
        for i in range(self._speakers_list.count()):
            item = self._speakers_list.item(i)
            raw = item.text().strip()
            if not raw:
                continue
            name, org, status = self._parse_speaker_raw(raw)
            if "enrolled" not in status.lower():
                participant_id = item.data(Qt.ItemDataRole.UserRole)
                if not participant_id:
                    participant_id = str(_uuid.uuid4())
                    item.setData(Qt.ItemDataRole.UserRole, participant_id)
                pending.append((name, org, participant_id))

        # No speakers at all → warning
        if self._speakers_list.count() == 0:
            QMessageBox.warning(
                self,
                "Enrollment",
                "Bitte mindestens einen Sprecher hinzufügen.",
            )
            return

        # All speakers already enrolled → informational hint
        if not pending:
            QMessageBox.information(
                self,
                "Enrollment",
                "Alle Sprecher sind bereits enrolliert.",
            )
            return

        dlg = EnrollmentDialog(
            pending_speakers=pending,
            speaker_manager=self._speaker_manager,
            parent=self,
        )
        from PySide6.QtWidgets import QDialog
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        enrolled = dlg.get_enrolled_results() if accepted else {}
        # Update list items by stable participant_id (HEAR-079)
        pending_ids = {pid for _, _, pid in pending}
        for i in range(self._speakers_list.count()):
            item = self._speakers_list.item(i)
            participant_id = item.data(Qt.ItemDataRole.UserRole)
            if not participant_id:
                continue
            name, org, _ = self._parse_speaker_raw(item.text().strip())
            if participant_id in enrolled:
                profile_id = enrolled[participant_id]
                item.setText(f"{name} | {org} | enrolled (id: {profile_id[:8]})")
                self._enrolled_speakers[participant_id] = profile_id
            elif accepted and participant_id in pending_ids:
                # Dialog was accepted but this speaker was not recorded
                item.setText(f"{name} | {org} | enrollment failed")
        enrolled_count = len(enrolled)
        self._set_speaker_status(
            f"Enrollment abgeschlossen: {enrolled_count}/{len(pending)} Sprecher registriert."
        )

    @staticmethod
    def _parse_speaker_raw(raw: str) -> tuple[str, str, str]:
        """Parse a speaker list entry into (name, org, status) tuple."""
        parts = [p.strip() for p in raw.split("|")]
        name = parts[0] if parts else raw
        org = parts[1] if len(parts) > 1 else "Organisation"
        status = parts[2] if len(parts) > 2 else ""
        return name, org, status

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
        # ADR-0003 Stage 0: register participant names for constrained intro matching
        self._speaker_manager.register_meeting_participants(known_speakers)
        self.set_active_meeting(meeting_id, known_speakers=known_speakers)
        audio_status = self._start_audio_pipeline()

        # HEAR-041: transcript + protocol reflect meeting start
        self.append_transcript_line(
            f"[00:00] Meeting '{title}' gestartet — {len(speakers)} Teilnehmer "
            f"| Audio: {device_label}."
        )
        self.append_transcript_line(f"[00:00] System: {audio_status}")
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
        # HEAR-075: enable export while meeting is active
        self._export_btn.setEnabled(True)
        self._export_path_label.setText("")

        QMessageBox.information(self, "Meeting gestartet", f"Meeting '{title}' ist jetzt aktiv.")

    def _stop_meeting(self) -> None:
        """Beendet die aktive Meeting-Session (HEAR-041)."""
        self._transcribe_pending_buffer(force=True)
        self._stop_audio_pipeline()

        # HEAR-070: export artifacts before clearing session state
        meeting_id = self._active_meeting_id
        title = (self._session.title if self._session is not None else None) or ""
        self._export_meeting_artifacts(meeting_id, title)

        self.stop_active_meeting()
        self._session = None
        self._meeting_status_label.setText("\u26aa Kein aktives Meeting")
        self._meeting_status_label.setStyleSheet("font-weight: 600; color: #888;")
        self._start_meeting_btn.setEnabled(True)
        self._stop_meeting_btn.setEnabled(False)
        # HEAR-075: keep export accessible after recording stops
        # (export button stays enabled so user can export the final protocol)
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
        if self._session is not None and self._session.started_at is not None:
            lines.append(f"\u2705 Aktive Session: {self._session.title}")
            lines.append(f"   Gestartet:    {self._session.started_at.strftime('%H:%M:%S')}")
            lines.append(f"   Teilnehmer:   {len(self._session.participants)}")
        else:
            lines.append("\u26aa Keine aktive Meeting-Session.")

        QMessageBox.information(self, "Aktueller Status", "\n".join(lines))

    def _start_audio_pipeline(self) -> str:
        """Start the live audio capture + ASR buffering loop for the active meeting."""
        if self._active_meeting_id is None:
            return "Audio-Pipeline nicht gestartet (kein aktives Meeting)."

        self._clear_audio_buffer()
        self._asr_warned_no_text = False

        profile = self._selected_audio_profile()
        self._audio_capture_service = AudioCaptureService(profile=profile)
        self._mic_level_widget.set_initializing()
        try:
            self._audio_capture_service.start(self._on_audio_segment)
            self._asr_timer.start()
            self._mic_level_widget.set_active()
            return "Audioaufnahme aktiv, Live-Transkription läuft."
        except Exception as exc:
            logger.error("Audio-Pipeline konnte nicht gestartet werden: %s", exc)
            self._audio_capture_service = None
            self._mic_level_widget.set_error(str(exc))
            return f"Audio-Pipeline konnte nicht gestartet werden: {exc}"

    def _stop_audio_pipeline(self) -> None:
        self._asr_timer.stop()
        if self._audio_capture_service is not None:
            self._audio_capture_service.stop()
            self._audio_capture_service = None
        self._mic_level_widget.reset()

    def _clear_audio_buffer(self) -> None:
        with self._audio_buffer_lock:
            self._pending_audio_chunks = []
            self._pending_start_ms = None
            self._pending_end_ms = 0
            self._pending_duration_ms = 0

    def _on_audio_segment(self, segment: AudioSegment) -> None:
        """Collect non-silent chunks in a thread-safe buffer for periodic ASR."""
        # HEAR-044: feed the level meter (thread-safe via Signal/Slot)
        self._mic_level_widget.on_audio_segment(segment.rms, segment.is_silence)

        if self._active_meeting_id is None or segment.is_silence:
            return

        chunk = np.asarray(segment.samples, dtype=np.float32).reshape(-1)
        if chunk.size == 0:
            return

        with self._audio_buffer_lock:
            if self._pending_start_ms is None:
                self._pending_start_ms = segment.start_ms
            self._pending_audio_chunks.append(chunk)
            self._pending_end_ms = segment.end_ms
            self._pending_duration_ms += max(0, segment.end_ms - segment.start_ms)

    def _process_pending_audio(self) -> None:
        self._transcribe_pending_buffer(force=False)

    def _transcribe_pending_buffer(self, force: bool) -> None:
        payload = self._consume_audio_buffer(force=force)
        if payload is None:
            return

        start_ms, end_ms, samples = payload
        meeting_id = self._active_meeting_id
        if meeting_id is None:
            return

        segment = AudioSegment(
            captured_at=datetime.now(),
            start_ms=start_ms,
            end_ms=end_ms,
            samples=samples,
            rms=float(np.sqrt(np.mean(samples ** 2))),
            is_silence=False,
        )
        # ADR-0003: resolve speaker identity before persistence — no hardcoded assignment
        embedding = SpeakerManager._extract_embedding(samples.tolist())

        result = self._transcription_service.transcribe_segment(
            segment,
            meeting_id=meeting_id,
            speaker_name="unknown",
            confidence_score=0.0,
        )

        text = result.text.strip() if result.text else ""
        speaker_match = self._speaker_manager.resolve_speaker_from_segment(
            embedding, segment_text=text
        )

        stamp = self._format_ms(start_ms)
        review_tag = " [low-conf]" if speaker_match.requires_review else ""
        if text:
            self.transcript_line_ready.emit(
                f"[{stamp}] {speaker_match.speaker_name}{review_tag}: {text}"
            )
            return

        if (result.error or not self._asr_warned_no_text) and not text:
            self.transcript_line_ready.emit(
                f"[{stamp}] System: Audio erkannt, aber noch kein Transkriptions-Text verfügbar."
            )
            self._asr_warned_no_text = True

    def _consume_audio_buffer(self, force: bool) -> tuple[int, int, np.ndarray] | None:
        with self._audio_buffer_lock:
            if not self._pending_audio_chunks:
                return None

            if not force and self._pending_duration_ms < 1800:
                return None

            start_ms = self._pending_start_ms or 0
            end_ms = self._pending_end_ms
            chunks = self._pending_audio_chunks

            self._pending_audio_chunks = []
            self._pending_start_ms = None
            self._pending_end_ms = 0
            self._pending_duration_ms = 0

        return start_ms, end_ms, np.concatenate(chunks)

    @staticmethod
    def _format_ms(total_ms: int) -> str:
        total_seconds = max(0, total_ms // 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

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
        protocol_layout.addWidget(QLabel(
            "Decisions, action items and open questions update on significant events."
        ))

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

        # HEAR-075: visible export action
        export_row = QHBoxLayout()
        self._export_btn = QPushButton("Export Protocol…")
        self._export_btn.setToolTip(
            "Protokoll als Markdown-Datei in den exports/-Ordner speichern"
        )
        self._export_btn.clicked.connect(self._do_export_protocol)
        self._export_btn.setEnabled(False)
        export_row.addWidget(self._export_btn)
        export_row.addStretch(1)
        protocol_layout.addLayout(export_row)

        self._export_path_label = QLabel("")
        self._export_path_label.setStyleSheet("color: #1a4a7a; font-size: 11px;")
        self._export_path_label.setWordWrap(True)
        protocol_layout.addWidget(self._export_path_label)

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
        self._speaker_manager.clear_meeting_context()

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

    # ------------------------------------------------------------------
    # HEAR-070 / HEAR-075: Protocol export (multi-format)
    # ------------------------------------------------------------------

    def _resolve_export_dir(self) -> "Path":
        """Return the directory where meeting artifacts are written (HEAR-073 / ADR-0011).

        Delegates to ``ayehear.utils.paths.exports_dir()`` so the path honours
        ``AYEHEAR_INSTALL_DIR`` and install-root-relative semantics.  Extracted
        as a dedicated method so tests can patch it without touching the
        filesystem helper.
        """
        from pathlib import Path as _Path
        from ayehear.utils.paths import exports_dir as _exports_dir
        return _exports_dir()

    def _export_meeting_artifacts(
        self,
        meeting_id: str | None,
        title: str,
    ) -> "list[Path]":
        """Export the current protocol and transcript as multi-format artifacts.

        Returns a list of ``Path`` objects for every file that was written.
        Returns an empty list when ``meeting_id`` is ``None`` or both the
        protocol and transcript views are empty.

        Protocol is written as Markdown, DOCX and PDF.
        Transcript is written as plain text (``-transcript.txt``).
        """
        import datetime as _dt
        from pathlib import Path as _Path

        if meeting_id is None:
            return []

        draft = self._protocol_view.toPlainText().strip()
        transcript = self._transcript_view.toPlainText().strip()

        if not draft and not transcript:
            return []

        meeting_type = ""
        if self._session is not None:
            meeting_type = self._meeting_type.currentText() if hasattr(self, "_meeting_type") else ""

        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:40] or "meeting"
        base_name = f"{safe_title}_{timestamp}"

        try:
            out_dir: _Path = self._resolve_export_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.error("Cannot create export directory: %s", exc)
            return []

        written: list[_Path] = []

        if draft:
            md_text = self._format_as_markdown(draft, title, meeting_type)
            # Markdown
            md_path = out_dir / f"{base_name}-protocol.md"
            try:
                md_path.write_text(md_text, encoding="utf-8")
                written.append(md_path)
            except OSError as exc:
                logger.error("Markdown export failed: %s", exc)

            # DOCX
            docx_path = out_dir / f"{base_name}-protocol.docx"
            try:
                from docx import Document as _Document  # type: ignore[import-untyped]
                doc = _Document()
                doc.add_heading(title, level=1)
                for line in md_text.splitlines():
                    if line.startswith("## "):
                        doc.add_heading(line[3:], level=2)
                    elif line.startswith("# "):
                        doc.add_heading(line[2:], level=1)
                    else:
                        doc.add_paragraph(line)
                doc.save(str(docx_path))
                written.append(docx_path)
            except Exception as exc:
                logger.error("DOCX export failed: %s", exc)

            # PDF via reportlab
            pdf_path = out_dir / f"{base_name}-protocol.pdf"
            try:
                from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
                from reportlab.platypus import SimpleDocTemplate, Paragraph  # type: ignore[import-untyped]
                from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-untyped]
                styles = getSampleStyleSheet()
                story = []
                for line in md_text.splitlines():
                    style = styles["Heading2"] if line.startswith("## ") else styles["Normal"]
                    text = line.lstrip("#").strip() or "\u00a0"
                    story.append(Paragraph(text, style))
                doc_pdf = SimpleDocTemplate(str(pdf_path), pagesize=A4)
                doc_pdf.build(story)
                written.append(pdf_path)
            except Exception as exc:
                logger.error("PDF export failed: %s", exc)

        # Transcript TXT
        if transcript:
            txt_path = out_dir / f"{base_name}-transcript.txt"
            try:
                header = f"Meeting Transcript — {title}\nExported: {_dt.datetime.now().isoformat()}\n\n"
                txt_path.write_text(header + transcript, encoding="utf-8")
                written.append(txt_path)
            except OSError as exc:
                logger.error("Transcript export failed: %s", exc)

        return written

    @staticmethod
    def _format_as_markdown(draft: str, title: str, meeting_type: str) -> str:
        """Convert a plain-text protocol draft to Markdown.

        Known section header names are converted to ``## Header`` lines.
        All other lines are preserved verbatim.
        """
        import datetime as _dt
        _SECTIONS = {"Summary", "Decisions", "Action Items", "Open Questions", "Transcript"}
        lines = [
            f"# {title}",
            "",
            f"**Type:** {meeting_type}",
            f"**Date:** {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]
        for raw in draft.splitlines():
            stripped = raw.strip()
            if stripped in _SECTIONS:
                lines.append(f"## {stripped}")
            else:
                lines.append(raw)
        return "\n".join(lines)

    def _do_export_protocol(self) -> None:
        """Export the current protocol draft to <install_root>/exports/ as Markdown."""
        import datetime as _dt
        from ayehear.utils.paths import exports_dir as _exports_dir

        draft = self._protocol_view.toPlainText().strip()
        if not draft:
            QMessageBox.warning(self, "Export", "Das Protokoll ist noch leer — nichts zu exportieren.")
            return

        title = ""
        if self._session is not None:
            title = self._session.title or ""

        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:40]
        filename = f"protocol_{safe_title}_{timestamp}.md" if safe_title else f"protocol_{timestamp}.md"

        try:
            out_dir = _exports_dir()
            out_path = out_dir / filename
            header = f"# Meeting Protocol — {title}\n\nExported: {_dt.datetime.now().isoformat()}\n\n"
            out_path.write_text(header + draft, encoding="utf-8")
            self._export_path_label.setText(f"Exportiert: {out_path}")
            logger.info("Protocol exported to %s", out_path)
            QMessageBox.information(
                self,
                "Export erfolgreich",
                f"Protokoll gespeichert:\n{out_path}",
            )
        except OSError as exc:
            logger.error("Protocol export failed: %s", exc)
            QMessageBox.critical(self, "Export fehlgeschlagen", f"Fehler beim Schreiben:\n{exc}")

    def _update_protocol_live(self, transcript_line: str) -> None:
        """Update the protocol draft incrementally on each new transcript line (HEAR-075).

        When a database snapshot repository is available, delegates to the full
        refresh.  In the simple / no-DB case, appends a lightweight transcript
        summary so the panel is never static during an active meeting.
        """
        if self._snapshot_repo is not None and self._active_meeting_id is not None:
            self._refresh_protocol_display()
            return

        # No DB: maintain a running live view from transcript lines
        current = self._protocol_view.toPlainText()
        # Only extend the Transcript section (add if not present)
        if "## Transcript" not in current:
            current = current.rstrip() + "\n\n## Transcript\n"
        current = current.rstrip() + f"\n{transcript_line}"
        self._protocol_view.setPlainText(current)
        self._protocol_view.verticalScrollBar().setValue(
            self._protocol_view.verticalScrollBar().maximum()
        )

    def append_transcript_line(self, line: str) -> None:
        """Append a new transcribed line to the live transcript view (HEAR-075: also updates protocol)."""
        self._transcript_view.appendPlainText(line)
        # Scroll to bottom
        self._transcript_view.verticalScrollBar().setValue(
            self._transcript_view.verticalScrollBar().maximum()
        )
        # HEAR-075: keep protocol draft visible and up-to-date during meeting
        if self._active_meeting_id is not None:
            self._update_protocol_live(line)
