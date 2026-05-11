from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
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
from ayehear.app.system_readiness import ReadinessChecker, SystemReadinessWidget
from ayehear.i18n import Translator, resolve_language
from ayehear.models.meeting import MeetingSession, Participant
from ayehear.models.runtime import RuntimeConfig
from ayehear.services.confidence_review import (
    ConfidenceReviewQueue,
    ItemType,
    cleanup_expired_review_files,
)
from ayehear.services.protocol_traceability import TraceabilityStore, cleanup_expired_trace_files
from ayehear.services.audio_capture import (
    AudioCaptureProfile,
    AudioCaptureService,
    AudioSegment,
    WavPersistenceConfig,
    enumerate_input_devices,
)
from ayehear.services.protocol_engine import ProtocolEngine
from ayehear.services.speaker_manager import SpeakerManager
from ayehear.services.transcription import AdaptiveTranscriptionQueue, TranscriptionService
from ayehear.storage.database import DatabaseBootstrap, DatabaseConfig, load_runtime_dsn
from ayehear.storage.repositories import (
    ProtocolSnapshotRepository,
    SpeakerProfileRepository,
)
from ayehear import __version__
from ayehear.utils.paths import reviews_dir, traces_dir

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from ayehear.storage.repositories import (
        MeetingRepository,
        ParticipantRepository,
        TranscriptSegmentRepository,
        ProtocolSnapshotRepository,
    )

logger = logging.getLogger(__name__)

_DEFAULT_MIN_TRANSCRIBE_WINDOW_MS = 3000
# HEAR-162: large-v3-turbo on CPU needs ≥6 s of German speech context to avoid
# hallucinations and produce coherent sentence-level output. The previous 2.8 s
# window caused short-clip hallucinations and produced nonsensical phrases.
# Each inference also takes 4-5 s on CPU, so longer windows keep the queue from
# stacking up while significantly improving transcript quality.
_LARGE_TURBO_MIN_TRANSCRIBE_WINDOW_MS = 6000

# Prefix used to identify degraded-state placeholder text in the protocol view
# so exports and tests can detect when the panel shows no real content.
_PROTOCOL_DEGRADED_PREFIX = "[DEGRADED]"


class MainWindow(QMainWindow):
    transcript_line_ready = Signal(str)

    def __init__(
        self,
        runtime_config: RuntimeConfig,
        db_session: "Session | None" = None,
        meeting_repo: "MeetingRepository | None" = None,
        participant_repo: "ParticipantRepository | None" = None,
        transcript_repo: "TranscriptSegmentRepository | None" = None,
        snapshot_repo: "ProtocolSnapshotRepository | None" = None,
        speaker_manager: "SpeakerManager | None" = None,
    ) -> None:
        super().__init__()
        self.runtime_config = runtime_config
        self._translator = Translator(self.runtime_config.protocol.language)
        self._db_session = db_session
        self._meeting_repo = meeting_repo
        self._participant_repo = participant_repo
        self._transcript_repo = transcript_repo
        self._snapshot_repo = snapshot_repo
        self._active_meeting_id: str | None = None
        self._session: MeetingSession | None = None
        self._audio_capture_service: AudioCaptureService | None = None
        self._transcription_service = TranscriptionService(
            model_name=self.runtime_config.models.whisper_model,
            profile=self.runtime_config.models.whisper_profile,
            language="de",
            transcript_repo=transcript_repo,
        )
        # HEAR-160: Start background ASR model warm-up immediately at app start.
        # WhisperModel (1.5 GB) loads lazily by default; warm-up ensures the model
        # is ready before the first meeting, preventing bad quality on initial chunks.
        self._transcription_service.warmup()
        # ADR-0003: speaker identification pipeline
        self._speaker_manager: SpeakerManager = speaker_manager or SpeakerManager()
        self._enrolled_speakers: dict[str, str] = {}  # participant_id -> profile_id
        # Maps list-item UUID (UserRole) -> DB Participant.id (HEAR-084 AC1/AC3)
        self._participant_id_map: dict[str, str] = {}
        # HEAR-085 AC2: protocol engine for structured draft generation (ADR-0005)
        self._protocol_engine = ProtocolEngine(
            snapshot_repo=snapshot_repo,
            transcript_repo=transcript_repo,
            ollama_model=self.runtime_config.models.ollama_model,
            language=self._translator.language,
        )
        # HEAR-087: system readiness checker + widget (built in _build_setup_panel)
        self._readiness_checker = ReadinessChecker()
        self._readiness_widget: SystemReadinessWidget | None = None
        self._audio_buffer_lock = threading.Lock()
        self._pending_audio_chunks: list[np.ndarray] = []
        self._pending_start_ms: int | None = None
        self._pending_end_ms: int = 0
        self._pending_duration_ms: int = 0
        self._asr_warned_no_text = False
        self._review_queue: ConfidenceReviewQueue | None = None
        self._trace_store: TraceabilityStore | None = None
        self._adaptive_queue: AdaptiveTranscriptionQueue | None = None
        # HEAR-154: delta gating — fingerprint of transcript used in last rebuild attempt
        self._last_protocol_transcript_fingerprint: str | None = None
        # HEAR-159: guard flag — prevents persistence layer reload during an open DB
        # transaction (race with the readiness timer → session closed under commit).
        self._persistence_transaction_active: bool = False
        # HEAR-162: True only when the current active meeting was successfully
        # committed to the DB.  False when the meeting INSERT failed or the session
        # is running in local-only mode.  Used by the HEAR-130 check to avoid
        # incorrectly disabling transcript persistence when the meeting was never
        # persisted in the first place.
        self._meeting_db_backed: bool = False

        self.setWindowTitle(f"AYE Hear v{__version__}")
        self.resize(1440, 900)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._header_label = QLabel(self._tr("ui.app.workspace_title"))
        self._header_label.setObjectName("pageTitle")
        self._header_label.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(self._header_label)

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
        # HEAR-085 AC2: also rebuild structured protocol draft on each refresh tick
        self._refresh_timer.timeout.connect(self._rebuild_protocol_from_persistence)

        self._asr_timer = QTimer(self)
        self._asr_timer.setInterval(1000)
        self._asr_timer.timeout.connect(self._process_pending_audio)
        self.transcript_line_ready.connect(self.append_transcript_line)

    def _tr(self, key: str, fallback: str | None = None, **kwargs: object) -> str:
        translated = self._translator.tr(key, **kwargs)
        if fallback is not None and translated == key:
            return fallback
        return translated

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

        self._meeting_box = QGroupBox(self._tr("ui.setup.group_title"))
        form = QFormLayout(self._meeting_box)

        self._meeting_title = QLineEdit()
        form.addRow(self._tr("ui.setup.meeting_title_label"), self._meeting_title)

        self._meeting_type = QComboBox()
        self._meeting_type.addItems(self.runtime_config.protocol.meeting_modes)
        form.addRow(self._tr("ui.setup.meeting_type_label"), self._meeting_type)

        self._participant_count = QSpinBox()
        self._participant_count.setRange(1, 30)
        self._participant_count.setValue(2)
        form.addRow(self._tr("ui.setup.participants_label"), self._participant_count)

        self._naming_template = QComboBox()
        self._naming_template.addItems([
            self._tr("ui.setup.template.with_salutation"),
            self._tr("ui.setup.template.with_full_name"),
        ])
        form.addRow(self._tr("ui.setup.participant_template_label"), self._naming_template)

        # HEAR-039: real Windows device selector
        self._audio_device = QComboBox()
        self._audio_device.addItem(self._tr("ui.setup.audio.default_microphone"), userData=None)
        self._populate_audio_devices()
        form.addRow(self._tr("ui.setup.audio_input_label"), self._audio_device)

        # HEAR-093/HEAR-185: protocol language selection is the single source
        # of truth for both UI and protocol language in phase 1.
        self._protocol_language = QComboBox()
        supported_languages = self.runtime_config.protocol.supported_languages
        if not supported_languages:
            supported_languages = ["de", "en"]
        for language_code in supported_languages:
            code = resolve_language(language_code)
            label_key = f"ui.language.option.{code}"
            self._protocol_language.addItem(self._tr(label_key), userData=code)

        default_lang = resolve_language(self.runtime_config.protocol.language)
        default_idx = self._protocol_language.findData(default_lang)
        if default_idx < 0:
            default_idx = self._protocol_language.findData("de")
        if default_idx >= 0:
            self._protocol_language.setCurrentIndex(default_idx)

        self._protocol_language.currentIndexChanged.connect(self._on_protocol_language_changed)
        form.addRow(self._tr("ui.setup.protocol_language_label"), self._protocol_language)

        layout.addWidget(self._meeting_box)

        self._speakers_box = QGroupBox(self._tr("ui.speaker.group_title"))
        speakers_layout = QVBoxLayout(self._speakers_box)
        self._speaker_help_label = QLabel(self._tr("ui.speaker.help_format"))
        speakers_layout.addWidget(self._speaker_help_label)

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
        # Guard flag: set True while programmatic list updates are in progress to
        # suppress spurious itemChanged feedback (HEAR-040).
        self._speaker_list_updating = False
        # HEAR-040: update status label after any user-committed inline edit
        self._speakers_list.itemChanged.connect(self._on_speaker_item_changed)

        speaker_btn_row = QHBoxLayout()
        self._add_speaker_btn = QPushButton(self._tr("ui.speaker.button.add"))
        self._add_speaker_btn.setToolTip(self._tr("ui.speaker.tooltip.add"))
        self._add_speaker_btn.clicked.connect(self._add_speaker)
        self._add_speaker_btn.setProperty("buttonClass", "secondary")
        self._edit_speaker_btn = QPushButton(self._tr("ui.speaker.button.edit"))
        self._edit_speaker_btn.setToolTip(self._tr("ui.speaker.tooltip.edit"))
        self._edit_speaker_btn.clicked.connect(self._edit_speaker)
        self._edit_speaker_btn.setProperty("buttonClass", "secondary")
        self._remove_speaker_btn = QPushButton(self._tr("ui.speaker.button.remove"))
        self._remove_speaker_btn.setToolTip(self._tr("ui.speaker.tooltip.remove"))
        self._remove_speaker_btn.clicked.connect(self._remove_speaker)
        self._remove_speaker_btn.setProperty("buttonClass", "destructive")
        speaker_btn_row.addWidget(self._add_speaker_btn)
        speaker_btn_row.addWidget(self._edit_speaker_btn)
        speaker_btn_row.addWidget(self._remove_speaker_btn)
        speakers_layout.addLayout(speaker_btn_row)

        # HEAR-040: visible feedback label for speaker actions
        self._speaker_status = QLabel("")
        self._speaker_status.setStyleSheet("color: #16A34A; font-weight: 600;")
        speakers_layout.addWidget(self._speaker_status)

        self._apply_template_btn = QPushButton(self._tr("ui.speaker.button.apply_template"))
        self._apply_template_btn.clicked.connect(self._apply_participant_template)
        self._apply_template_btn.setProperty("buttonClass", "primary")
        speakers_layout.addWidget(self._apply_template_btn)

        self._start_enrollment_btn = QPushButton(self._tr("ui.speaker.button.start_enrollment"))
        self._start_enrollment_btn.clicked.connect(self._start_enrollment)
        self._start_enrollment_btn.setProperty("buttonClass", "primary")
        speakers_layout.addWidget(self._start_enrollment_btn)

        layout.addWidget(self._speakers_box)

        # HEAR-087: system readiness indicators
        self._readiness_widget = SystemReadinessWidget(translator=self._tr)
        self._readiness_widget.set_refresh_callback(self._refresh_readiness)
        layout.addWidget(self._readiness_widget)

        # HEAR-041: meeting status indicator
        self._meeting_status_label = QLabel(self._tr("ui.meeting.status.inactive"))
        self._meeting_status_label.setStyleSheet("font-weight: 600; color: #64748B;")
        layout.addWidget(self._meeting_status_label)
        # HEAR-044: live mic state + level meter
        self._mic_level_widget = MicLevelWidget()
        layout.addWidget(self._mic_level_widget)
        controls = QHBoxLayout()
        self._start_meeting_btn = QPushButton(self._tr("ui.meeting.button.start"))
        self._start_meeting_btn.clicked.connect(self._start_meeting)
        self._start_meeting_btn.setProperty("buttonClass", "primary")
        self._stop_meeting_btn = QPushButton(self._tr("ui.meeting.button.stop"))
        self._stop_meeting_btn.clicked.connect(self._stop_meeting)
        self._stop_meeting_btn.setEnabled(False)
        self._stop_meeting_btn.setProperty("buttonClass", "destructive")
        self._show_state_btn = QPushButton(self._tr("ui.meeting.button.show_state"))
        self._show_state_btn.clicked.connect(self._show_current_state)
        self._show_state_btn.setProperty("buttonClass", "secondary")
        controls.addWidget(self._start_meeting_btn)
        controls.addWidget(self._stop_meeting_btn)
        controls.addWidget(self._show_state_btn)
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
        # HEAR-087: refresh readiness after devices are enumerated
        QTimer.singleShot(0, self._refresh_readiness)

    def _selected_audio_profile(self) -> AudioCaptureProfile:
        """Return an AudioCaptureProfile for the selected input device (HEAR-039).

        device_index is the sounddevice index (int) or None for WASAPI default.
        Use this when starting AudioCaptureService once the audio pipeline is
        integrated (ADR-0004).
        """
        device_index: int | None = self._audio_device.currentData()
        return AudioCaptureProfile(device_index=device_index)

    # ------------------------------------------------------------------
    # HEAR-087: system readiness
    # ------------------------------------------------------------------

    def _refresh_readiness(self) -> None:
        """Evaluate all component readiness states and update the indicator widget.
        
        This method now attempts to reload the persistence layer each time
        (in case the DSN file was created after app startup), then re-evaluates
        all component readiness states.
        """
        # Try to reload persistence layer if not already connected
        if self._meeting_repo is None:
            self._reload_persistence_layer()
        
        if self._readiness_widget is None:
            return
        components, aggregate = self._readiness_checker.check_all(
            meeting_repo=self._meeting_repo,
            participant_repo=self._participant_repo,
            transcript_repo=self._transcript_repo,
            snapshot_repo=self._snapshot_repo,
            speaker_profile_repo=getattr(self._speaker_manager, '_profiles', None),
            runtime_config=self.runtime_config,
        )
        self._readiness_widget.update_status(components, aggregate)

    def _reload_persistence_layer(self) -> bool:
        """Attempt to load or reload the persistence layer from DSN.
        
        Called by _refresh_readiness() to support dynamic DSN discovery
        when pg.dsn is written after app startup (e.g., post-provisioning).
        """
        # HEAR-159: Never reload the persistence layer while a DB transaction is open.
        # The Qt readiness timer may fire during _start_meeting()'s commit sequence,
        # closing the session under a live commit → FK violations or silent data loss.
        if self._persistence_transaction_active:
            logger.debug("Skipping persistence layer reload: transaction active.")
            return False
        # HEAR-166: During an active local-only meeting the current meeting_id was
        # never committed to meetings. Rebinding transcript/snapshot repositories in
        # this state would re-enable DB writes and trigger FK violations on every
        # segment/snapshot insert. Keep persistence disabled until meeting end.
        if self._active_meeting_id is not None and not self._meeting_db_backed:
            logger.debug(
                "Skipping persistence layer reload: active meeting %s is local-only.",
                self._active_meeting_id,
            )
            return False
        try:
            dsn = load_runtime_dsn()
            if dsn:
                logger.info("Loading runtime DSN for persistence layer reload.")
                bootstrap = DatabaseBootstrap(DatabaseConfig(dsn=dsn))
                bootstrap.bootstrap()
                new_session = bootstrap.session()
                
                # Close old session if it exists
                if self._db_session is not None:
                    self._db_session.close()
                
                self._db_session = new_session
                
                # Reinitialize all repositories
                from ayehear.storage.repositories import (
                    MeetingRepository,
                    ParticipantRepository,
                    TranscriptSegmentRepository,
                )
                self._meeting_repo = MeetingRepository(new_session)
                self._participant_repo = ParticipantRepository(new_session)
                self._transcript_repo = TranscriptSegmentRepository(new_session)
                self._snapshot_repo = ProtocolSnapshotRepository(new_session)
                
                # Reinitialize speaker manager with new session
                self._speaker_manager = SpeakerManager(
                    profile_repo=SpeakerProfileRepository(new_session),
                    participant_repo=self._participant_repo,
                )
                
                # Update services that depend on repos
                self._transcription_service.transcript_repo = self._transcript_repo
                # HEAR-130: ProtocolEngine uses _snapshots/_transcripts internally;
                # _snapshot_repo/_transcript_repo were wrong attribute names that left
                # the engine on a stale (closed) session after every reload.
                self._protocol_engine._snapshots = self._snapshot_repo
                self._protocol_engine._transcripts = self._transcript_repo

                # HEAR-130: verify the active meeting is still resolvable in the new
                # session.  Only check when _meeting_db_backed=True (i.e., the meeting
                # was actually committed to the DB).  If the meeting INSERT previously
                # failed, the local UUID won't be in the DB — that's expected, not an
                # anomaly, so do not disable persistence.
                if self._active_meeting_id is not None and self._meeting_db_backed:
                    try:
                        if self._meeting_repo.get_by_id(self._active_meeting_id) is None:
                            logger.error(
                                "HEAR-130: Active meeting %s not visible in new session "
                                "after reload; disabling transcript persistence to prevent FK violations.",
                                self._active_meeting_id,
                            )
                            self._transcript_repo = None
                            self._transcription_service.transcript_repo = None
                    except Exception as verify_exc:
                        logger.warning(
                            "HEAR-130: Could not verify active meeting %s after reload: %s",
                            self._active_meeting_id, verify_exc,
                        )

                logger.info("Persistence layer reloaded successfully.")
                return True
        except Exception as exc:
            logger.error("Failed to reload persistence layer: %s", exc)
        return False

    def _disable_persistence(self, reason: str) -> None:
        """Drop repository bindings and keep app operational in local-only mode."""
        logger.warning("Persistence disabled; falling back to local-only mode: %s", reason)
        self._meeting_db_backed = False  # HEAR-162: no DB-backed meeting in local-only mode
        if self._db_session is not None:
            try:
                self._db_session.close()
            except Exception:
                pass
        self._db_session = None
        self._meeting_repo = None
        self._participant_repo = None
        self._transcript_repo = None
        self._snapshot_repo = None
        self._transcription_service.transcript_repo = None
        self._protocol_engine._snapshots = None
        self._protocol_engine._transcripts = None
        if self._active_meeting_id is not None:
            self._refresh_protocol_display()

    def _save_review_queue(self) -> None:
        """Save the current review queue to local runtime/reviews storage (V2-12 / HEAR-117)."""
        if self._review_queue is None or self._active_meeting_id is None:
            return
        try:
            from pathlib import Path as _Path
            cleanup_expired_review_files(
                reviews_dir(),
                self.runtime_config.privacy.review_retention_days,
            )
            self._review_queue.save(_Path(f"review-{self._active_meeting_id}.json"))
            logger.debug("Review queue saved for meeting %s", self._active_meeting_id)
        except Exception as exc:
            logger.warning("Could not save review queue: %s", exc)

    def _save_trace_store(self) -> None:
        """Save the current trace store to local runtime/traces storage (V2-13 / HEAR-118)."""
        if self._trace_store is None or self._active_meeting_id is None:
            return
        try:
            from pathlib import Path as _Path
            cleanup_expired_trace_files(
                traces_dir(),
                self.runtime_config.privacy.trace_retention_days,
            )
            self._trace_store.save(_Path(f"trace-{self._active_meeting_id}.json"))
            logger.debug("Trace store saved for meeting %s", self._active_meeting_id)
        except Exception as exc:
            logger.warning("Could not save trace store: %s", exc)

    def _handle_persistence_error(self, source: str, exc: Exception) -> None:
        """Recover from DB/session errors to avoid repeated failure cascades."""
        logger.error("%s: %s", source, exc)
        if self._db_session is not None:
            try:
                self._db_session.rollback()
            except Exception as rollback_exc:
                logger.warning("Session rollback after '%s' failed: %s", source, rollback_exc)

        # Connection drops are usually recoverable by rebuilding session/repositories.
        if self._reload_persistence_layer():
            logger.info("Persistence recovered after '%s'.", source)
            return

        # If recovery fails, continue in local-only mode rather than failing every refresh.
        self._disable_persistence(source)


    # ------------------------------------------------------------------
    # Speaker management (HEAR-036 / HEAR-040)
    # ------------------------------------------------------------------

    # HEAR-093: Protocol language change handler
    def _on_protocol_language_changed(self, _index: int) -> None:
        """Propagate selected protocol language to i18n and protocol generation."""
        selected_language = resolve_language(str(self._protocol_language.currentData() or "de"))
        self.runtime_config.protocol.language = selected_language
        self.runtime_config.protocol.protocol_language = selected_language
        self._translator.set_language(selected_language)
        self._protocol_engine.set_language(selected_language)
        self._retranslate_ui()
        logger.debug("Protocol/UI language set to: %s", selected_language)

    def _retranslate_ui(self) -> None:
        self._header_label.setText(self._tr("ui.app.workspace_title"))
        self._meeting_box.setTitle(self._tr("ui.setup.group_title"))
        self._speakers_box.setTitle(self._tr("ui.speaker.group_title"))
        self._speaker_help_label.setText(self._tr("ui.speaker.help_format"))
        self._add_speaker_btn.setText(self._tr("ui.speaker.button.add"))
        self._add_speaker_btn.setToolTip(self._tr("ui.speaker.tooltip.add"))
        self._edit_speaker_btn.setText(self._tr("ui.speaker.button.edit"))
        self._edit_speaker_btn.setToolTip(self._tr("ui.speaker.tooltip.edit"))
        self._remove_speaker_btn.setText(self._tr("ui.speaker.button.remove"))
        self._remove_speaker_btn.setToolTip(self._tr("ui.speaker.tooltip.remove"))
        self._apply_template_btn.setText(self._tr("ui.speaker.button.apply_template"))
        self._start_enrollment_btn.setText(self._tr("ui.speaker.button.start_enrollment"))
        self._start_meeting_btn.setText(self._tr("ui.meeting.button.start"))
        self._stop_meeting_btn.setText(self._tr("ui.meeting.button.stop"))
        self._show_state_btn.setText(self._tr("ui.meeting.button.show_state"))
        if hasattr(self, "_transcript_group"):
            self._transcript_group.setTitle(self._tr("ui.transcript.group_title"))
        if hasattr(self, "_transcript_meta_label"):
            self._transcript_meta_label.setText(self._tr("ui.transcript.meta_label"))
        if hasattr(self, "_protocol_box"):
            self._protocol_box.setTitle(self._tr("ui.protocol.group_title"))
        if hasattr(self, "_protocol_subtitle_label"):
            self._protocol_subtitle_label.setText(self._tr("ui.protocol.subtitle"))
        if hasattr(self, "_review_box"):
            self._review_box.setTitle(self._tr("ui.review.group_title"))
        if hasattr(self, "_review_subtitle_label"):
            self._review_subtitle_label.setText(self._tr("ui.review.subtitle"))
        if hasattr(self, "_speaker_override"):
            self._speaker_override.setPlaceholderText(self._tr("ui.review.speaker_placeholder"))
        if hasattr(self, "_correct_btn"):
            self._correct_btn.setText(self._tr("ui.review.button.apply_correction"))
        if hasattr(self, "_export_btn"):
            self._export_btn.setText(self._tr("ui.export.button"))
            self._export_btn.setToolTip(self._tr("ui.export.tooltip"))
        if self._session is None:
            self._meeting_status_label.setText(self._tr("ui.meeting.status.inactive"))
        if self._readiness_widget is not None:
            self._readiness_widget.retranslate()

    def _on_speaker_item_changed(self, item: QListWidgetItem) -> None:
        """Update feedback label after user commits an inline edit (HEAR-040)."""
        if self._speaker_list_updating:
            return
        self._set_speaker_status(self._tr("ui.speaker.status.saved", text=item.text()[:40]))

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
        self._set_speaker_status(self._tr("ui.speaker.status.added"))

    def _edit_speaker(self) -> None:
        """Inline-Edit des ausgewählten Sprecher-Eintrags."""
        item = self._speakers_list.currentItem()
        if item is None:
            QMessageBox.information(
                self,
                self._tr("ui.speaker.edit.title"),
                self._tr("ui.speaker.select_required"),
            )
            self._set_speaker_status(self._tr("ui.speaker.status.none_selected"))
            return
        self._speakers_list.editItem(item)
        self._set_speaker_status(self._tr("ui.speaker.status.editing", text=item.text()[:40]))

    def _remove_speaker(self) -> None:
        """Entfernt den ausgewählten Sprecher nach Bestätigung."""
        item = self._speakers_list.currentItem()
        if item is None:
            QMessageBox.information(
                self,
                self._tr("ui.speaker.remove.title"),
                self._tr("ui.speaker.select_required"),
            )
            self._set_speaker_status(self._tr("ui.speaker.status.none_selected"))
            return
        answer = QMessageBox.question(
            self,
            self._tr("ui.speaker.remove.confirm_title"),
            self._tr("ui.speaker.remove.confirm_body", entry=item.text()),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            name = item.text()
            self._speakers_list.takeItem(self._speakers_list.row(item))
            self._set_speaker_status(self._tr("ui.speaker.status.removed", text=name[:40]))

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
        use_salutation = self._naming_template.currentText().startswith(
            self._tr("ui.setup.template.with_salutation")
        )
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
                self._tr("ui.enrollment.title"),
                self._tr("ui.meeting.start.missing_speakers"),
            )
            return

        # All speakers already enrolled → informational hint
        if not pending:
            QMessageBox.information(
                self,
                self._tr("ui.enrollment.title"),
                self._tr("ui.enrollment.all_done"),
            )
            return

        dlg = EnrollmentDialog(
            pending_speakers=pending,
            speaker_manager=self._speaker_manager,
            translator=self._tr,
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
                # HEAR-084 AC3: persist participant-to-profile linkage when repo available
                db_participant_id = self._participant_id_map.get(participant_id)
                if db_participant_id and self._participant_repo is not None:
                    try:
                        self._participant_repo.mark_enrolled(db_participant_id, profile_id)
                        logger.info(
                            "Enrollment persisted: participant=%s profile=%s",
                            db_participant_id, profile_id,
                        )
                    except Exception as exc:
                        logger.error("Failed to persist enrollment linkage: %s", exc)
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
        org = parts[1] if len(parts) > 1 else ""
        status = parts[2] if len(parts) > 2 else "pending enrollment"
        return name, org, status

    def _start_meeting(self) -> None:
        """Validiert das Setup und startet eine Meeting-Session."""
        title = self._meeting_title.text().strip()
        if not title:
            QMessageBox.warning(
                self,
                self._tr("ui.meeting.start.title"),
                self._tr("ui.meeting.start.missing_title"),
            )
            self._meeting_title.setFocus()
            return

        speakers = self._get_speaker_texts()
        if not speakers:
            QMessageBox.warning(
                self,
                self._tr("ui.meeting.start.title"),
                self._tr("ui.meeting.start.missing_speakers"),
            )
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

        local_meeting_id = str(uuid.uuid4())
        meeting_id = local_meeting_id

        # HEAR-084 AC1: persist meeting + participants to DB when repos available
        self._participant_id_map = {}
        meeting_persisted = False
        # HEAR-159: Block the readiness-timer reload while the transaction is open.
        # Cleared unconditionally after commit (or rollback) below.
        self._persistence_transaction_active = True
        if self._meeting_repo is not None:
            try:
                db_meeting = self._meeting_repo.create(
                    title=title,
                    meeting_type=self._meeting_type.currentText(),
                    mode=self._meeting_type.currentText(),
                )
                self._meeting_repo.start(db_meeting.id)
                meeting_id = db_meeting.id
                meeting_persisted = True
                logger.info("Meeting persisted to DB: %s", meeting_id)
            except Exception as exc:
                # HEAR-168: Temporarily lift the transaction guard so the error handler
                # can call _reload_persistence_layer() and attempt a reconnect.
                # The guard exists to prevent the readiness timer from interfering;
                # the failed transaction is already dead so the guard no longer protects anything.
                self._persistence_transaction_active = False
                self._handle_persistence_error(
                    "Failed to persist meeting to DB; using in-memory id",
                    exc,
                )
                # If recovery succeeded, _meeting_repo is restored (not None).
                # Retry the INSERT exactly once with the fresh session.
                if self._meeting_repo is not None:
                    try:
                        db_meeting = self._meeting_repo.create(
                            title=title,
                            meeting_type=self._meeting_type.currentText(),
                            mode=self._meeting_type.currentText(),
                        )
                        self._meeting_repo.start(db_meeting.id)
                        meeting_id = db_meeting.id
                        meeting_persisted = True
                        logger.info("Meeting persisted to DB after reconnect: %s", meeting_id)
                    except Exception as retry_exc:
                        logger.warning("Retry after reconnect also failed: %s", retry_exc)
                        self._disable_persistence("Failed to persist meeting to DB after reconnect")
                # Re-arm the guard: the commit block below still needs it.
                self._persistence_transaction_active = True

        if meeting_persisted and self._participant_repo is not None and self._session is not None:
            # Build participant_id_map: list-item UUID -> DB Participant.id
            for i in range(self._speakers_list.count()):
                item = self._speakers_list.item(i)
                list_uuid = item.data(Qt.ItemDataRole.UserRole)
                raw = item.text().strip()
                if not raw or not list_uuid:
                    continue
                p_name, p_org, _ = self._parse_speaker_raw(raw)
                name_parts = p_name.split()
                first_name = " ".join(name_parts[:-1]) if len(name_parts) > 1 else None
                last_name = name_parts[-1] if name_parts else p_name
                try:
                    db_participant = self._participant_repo.add(
                        meeting_id=meeting_id,
                        display_name=p_name,
                        first_name=first_name,
                        last_name=last_name,
                        organization=p_org,
                    )
                    self._participant_id_map[list_uuid] = db_participant.id
                    logger.debug("Participant persisted: %s -> %s", p_name, db_participant.id)
                except Exception as exc:
                    self._handle_persistence_error(
                        f"Failed to persist participant '{p_name}'",
                        exc,
                    )
                    break

        # HEAR-124: commit meeting + participants immediately so they survive any later
        # session.rollback() triggered by unrelated errors (e.g. protocol rebuild).
        if meeting_persisted and self._db_session is not None:
            try:
                self._db_session.commit()
                logger.debug("Meeting and participants committed to DB: %s", meeting_id)
            except Exception as exc:
                logger.error("Failed to commit meeting to DB: %s", exc)
                # Soft fallback: keep meeting alive in local-only mode when commit fails.
                # This avoids retry loops on an invalid DB session while preserving UX flow.
                try:
                    self._db_session.rollback()
                except Exception as rollback_exc:
                    logger.warning("Rollback after meeting commit failure failed: %s", rollback_exc)
                self._disable_persistence("Failed to commit meeting to DB during meeting start")
                meeting_persisted = False
                meeting_id = local_meeting_id
                self._participant_id_map = {}
        # HEAR-162: track whether the active meeting is backed by a committed DB row.
        # _reload_persistence_layer()'s HEAR-130 check only fires when this is True.
        self._meeting_db_backed = meeting_persisted
        # HEAR-159: Release guard — transaction is committed (or rolled back).
        self._persistence_transaction_active = False

        # Reconcile enrollment state collected before meeting start:
        # 1) persist participant->profile linkage now that DB participant IDs exist
        # 2) restrict live matching to enrolled profiles of this meeting
        self._reconcile_enrollment_links_after_start()
        self._register_meeting_profile_scope()

        known_speakers = [p.display_name for p in self._session.participants]
        # ADR-0003 Stage 0: register participant names for constrained intro matching
        self._speaker_manager.register_meeting_participants(known_speakers)
        self.set_active_meeting(meeting_id, known_speakers=known_speakers)
        audio_status = self._start_audio_pipeline()
        _start_time = datetime.now().strftime("%H:%M")

        # HEAR-041: transcript + protocol reflect meeting start
        self.append_transcript_line(
            f"[{_start_time}] Meeting '{title}' gestartet — {len(speakers)} Teilnehmer "
            f"| Audio: {device_label}."
        )
        self.append_transcript_line(f"[{_start_time}] System: {audio_status}")

        # HEAR-085 AC1/AC2: protocol panel shows structured state, never transcript mirror
        if self._snapshot_repo is not None:
            self._protocol_view.setPlainText(
                f"# {title}\n"
                f"Typ: {self._meeting_type.currentText()} | Sprecher: {len(speakers)}\n\n"
                "Aufnahme läuft — strukturierter Protokollentwurf erscheint nach der ersten "
                "Snapshot-Generierung (ca. 10 s nach dem ersten Transkript).\n"
            )
        else:
            self._protocol_view.setPlainText(self._tr("ui.protocol.degraded.unavailable"))

        # HEAR-041: visible session state
        self._meeting_status_label.setText(self._tr("ui.meeting.status.active", title=title))
        self._meeting_status_label.setStyleSheet("font-weight: 700; color: #16A34A;")
        self._start_meeting_btn.setEnabled(False)
        self._stop_meeting_btn.setEnabled(True)
        # HEAR-075: enable export while meeting is active
        self._export_btn.setEnabled(True)
        self._export_path_label.setText("")

        # HEAR-087: refresh readiness state after meeting start
        self._refresh_readiness()

    def _stop_meeting(self) -> None:
        """Beendet die aktive Meeting-Session (HEAR-041)."""
        self._transcribe_pending_buffer(force=True)
        self._stop_audio_pipeline()

        # HEAR-070: export artifacts before clearing session state
        meeting_id = self._active_meeting_id
        title = (self._session.title if self._session is not None else None) or ""
        self._export_meeting_artifacts(meeting_id, title)

        # HEAR-084 AC4: mark meeting as ended in DB
        if meeting_id and self._meeting_repo is not None:
            try:
                self._meeting_repo.end(meeting_id)
                logger.info("Meeting ended in DB: %s", meeting_id)
                # HEAR-168: commit the end update immediately — flush() alone leaves
                # the transaction open; idle_in_transaction_session_timeout (30 s)
                # would otherwise roll back the status change and all pending segments.
                if self._db_session is not None:
                    self._db_session.commit()
                    logger.debug("Meeting end committed: %s", meeting_id)
            except ValueError as exc:
                # HEAR-130: ValueError means the meeting ID is not in the DB (e.g. the
                # meeting was never committed or the session was reloaded and the meeting
                # is not visible).  This is a data-integrity warning, NOT a connectivity
                # failure — don't reload the session or disable persistence for it.
                logger.warning("Failed to end meeting in DB (not found): %s", exc)
            except Exception as exc:
                self._handle_persistence_error("Failed to end meeting in DB", exc)

        self.stop_active_meeting()
        self._session = None
        self._meeting_status_label.setText(self._tr("ui.meeting.status.inactive"))
        self._meeting_status_label.setStyleSheet("font-weight: 600; color: #64748B;")
        self._start_meeting_btn.setEnabled(True)
        self._stop_meeting_btn.setEnabled(False)
        # HEAR-075: keep export accessible after recording stops
        # (export button stays enabled so user can export the final protocol)
        self.append_transcript_line(self._tr("ui.meeting.stopped.line"))

    def _show_current_state(self) -> None:
        """Zeigt einen Dialog mit dem aktuellen Setup- und Session-Status (HEAR-041)."""
        title = self._meeting_title.text().strip() or self._tr("ui.meeting.state.unset")
        mode = self._meeting_type.currentText()
        device = self._audio_device.currentText()
        speakers = self._get_speaker_texts()

        lines = [
            self._tr("ui.meeting.state.title_line", value=title),
            self._tr("ui.meeting.state.type_line", value=mode),
            self._tr("ui.meeting.state.device_line", value=device),
            self._tr("ui.meeting.state.speakers_line", count=len(speakers)),
        ]
        for s in speakers:
            lines.append(f"  \u2022 {s}")
        lines.append("")
        if self._session is not None and self._session.started_at is not None:
            lines.append(self._tr("ui.meeting.state.active_line", title=self._session.title))
            lines.append(self._tr("ui.meeting.state.started_line", value=self._session.started_at.strftime('%H:%M:%S')))
            lines.append(self._tr("ui.meeting.state.participants_line", count=len(self._session.participants)))
        else:
            lines.append(self._tr("ui.meeting.state.none_active_line"))

        QMessageBox.information(self, self._tr("ui.meeting.state.title"), "\n".join(lines))

    def _start_audio_pipeline(self) -> str:
        """Start the live audio capture + ASR buffering loop for the active meeting."""
        if self._active_meeting_id is None:
            return self._tr("ui.audio.pipeline.not_started", fallback="Audio pipeline not started (no active meeting).")

        self._clear_audio_buffer()
        self._asr_warned_no_text = False

        self._mic_level_widget.set_initializing()
        try:
            profile = self._selected_audio_profile()
            # HEAR-168: resolve wav_output_dir against install root so that the
            # relative path "runtime/wav" maps to <install_root>/runtime/wav
            # instead of <CWD>/runtime/wav (which for packaged EXE = app/).
            from ayehear.utils.paths import resolve_install_root as _resolve_root
            _wav_dir_raw = self.runtime_config.privacy.wav_output_dir
            _wav_path = Path(_wav_dir_raw)
            if not _wav_path.is_absolute():
                _wav_path = _resolve_root() / _wav_path
            wav_config = WavPersistenceConfig(
                enabled=self.runtime_config.privacy.wav_persistence_enabled,
                output_dir=_wav_path,
                delete_on_meeting_end=self.runtime_config.privacy.wav_delete_on_meeting_end,
                retention_days=self.runtime_config.privacy.wav_retention_days,
            )
            self._audio_capture_service = AudioCaptureService(profile=profile, wav_config=wav_config)
            self._audio_capture_service.start(self._on_audio_segment, meeting_id=self._active_meeting_id)
            self._adaptive_queue = AdaptiveTranscriptionQueue(self._do_transcribe_segment)
            self._asr_timer.start()
            self._mic_level_widget.set_active()
            return self._tr("ui.audio.pipeline.active", fallback="Audio capture active, live transcription running.")
        except Exception as exc:
            logger.error("Audio-Pipeline konnte nicht gestartet werden: %s", exc)
            self._audio_capture_service = None
            self._mic_level_widget.set_error(str(exc))
            return self._tr(
                "ui.audio.pipeline.start_failed",
                fallback="Audio pipeline could not be started: {error}",
                error=exc,
            )

    def _stop_audio_pipeline(self) -> None:
        self._asr_timer.stop()
        if self._adaptive_queue is not None:
            self._adaptive_queue.flush_all()
            self._adaptive_queue = None
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
        if self._adaptive_queue is not None:
            self._adaptive_queue.push(segment)
        else:
            self._do_transcribe_segment(segment)

    def _do_transcribe_segment(self, segment: AudioSegment) -> None:
        """Run ASR + speaker resolution on a single segment and emit the transcript line."""
        samples = np.asarray(segment.samples, dtype=np.float32)
        meeting_id = self._active_meeting_id
        if meeting_id is None:
            return
        # ADR-0003: resolve speaker identity BEFORE persistence (HEAR-084 AC2)
        # Embedding-based pre-resolution ensures no segment is saved as unknown/0.0
        embedding = SpeakerManager._extract_embedding(samples.tolist())
        speaker_pre_match = self._speaker_manager.match_segment(embedding)

        result = self._transcription_service.transcribe_segment(
            segment,
            meeting_id=meeting_id,
            speaker_name=speaker_pre_match.speaker_name,
            confidence_score=speaker_pre_match.confidence,
        )

        text = result.text.strip() if result.text else ""
        # Refine with text hint (intro matching) — if improved, speaker_match overrides
        speaker_match = self._speaker_manager.resolve_speaker_from_segment(
            embedding, segment_text=text
        )

        # HEAR-153: reconcile persisted speaker when post-ASR refinement differs from pre-match
        if (
            result.segment_id is not None
            and self._transcript_repo is not None
            and speaker_match.speaker_name != speaker_pre_match.speaker_name
        ):
            try:
                self._transcript_repo.reconcile_speaker(
                    result.segment_id,
                    refined_speaker_name=speaker_match.speaker_name,
                    refined_confidence=speaker_match.confidence,
                )
            except Exception as exc:
                logger.warning("HEAR-153: speaker reconciliation failed for segment %s: %s", result.segment_id, exc)

        stamp = self._format_ms(segment.start_ms)
        review_tag = " [low-conf]" if speaker_match.requires_review else ""
        if text:
            self.transcript_line_ready.emit(
                f"[{stamp}] {speaker_match.speaker_name}{review_tag}: {text}"
            )
            return

        if (result.error or not self._asr_warned_no_text) and not text:
            self.transcript_line_ready.emit(
                self._tr("ui.transcript.system_no_text", stamp=stamp)
            )
            self._asr_warned_no_text = True

    def _consume_audio_buffer(self, force: bool) -> tuple[int, int, np.ndarray] | None:
        with self._audio_buffer_lock:
            if not self._pending_audio_chunks:
                return None

            if not force and self._pending_duration_ms < self._min_transcribe_window_ms():
                return None

            start_ms = self._pending_start_ms or 0
            end_ms = self._pending_end_ms
            chunks = self._pending_audio_chunks

            self._pending_audio_chunks = []
            self._pending_start_ms = None
            self._pending_end_ms = 0
            self._pending_duration_ms = 0

        return start_ms, end_ms, np.concatenate(chunks)

    def _min_transcribe_window_ms(self) -> int:
        """Return minimum buffered audio duration before ASR is triggered.

        HEAR-150: TheChola large-v3-turbo model showed short-clip hallucinations
        on 1-2s windows. For that model family, require a slightly longer window
        so ASR gets more context before inference.
        """
        model = (self._transcription_service.model_name or "").lower()
        if "large-v3-turbo" in model:
            return _LARGE_TURBO_MIN_TRANSCRIBE_WINDOW_MS
        return _DEFAULT_MIN_TRANSCRIBE_WINDOW_MS

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

        self._transcript_group = QGroupBox(self._tr("ui.transcript.group_title"))
        status_layout = QVBoxLayout(self._transcript_group)
        self._transcript_meta_label = QLabel(self._tr("ui.transcript.meta_label"))
        status_layout.addWidget(self._transcript_meta_label)

        self._transcript_view = QPlainTextEdit()
        self._transcript_view.setReadOnly(True)
        self._transcript_view.setPlainText(self._tr("ui.transcript.initial_line"))
        status_layout.addWidget(self._transcript_view)
        layout.addWidget(self._transcript_group)
        return panel

    def _build_protocol_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        self._protocol_box = QGroupBox(self._tr("ui.protocol.group_title"))
        protocol_layout = QVBoxLayout(self._protocol_box)
        self._protocol_subtitle_label = QLabel(self._tr("ui.protocol.subtitle"))
        protocol_layout.addWidget(self._protocol_subtitle_label)

        self._protocol_view = QPlainTextEdit()
        self._protocol_view.setReadOnly(True)
        self._protocol_view.setPlainText(self._tr("ui.protocol.default_text"))
        protocol_layout.addWidget(self._protocol_view)

        # HEAR-075: visible export action
        export_row = QHBoxLayout()
        self._export_btn = QPushButton(self._tr("ui.export.button"))
        self._export_btn.setToolTip(self._tr("ui.export.tooltip"))
        self._export_btn.clicked.connect(self._do_export_protocol)
        self._export_btn.setEnabled(False)
        self._export_btn.setProperty("buttonClass", "primary")
        export_row.addWidget(self._export_btn)
        export_row.addStretch(1)
        protocol_layout.addLayout(export_row)

        self._export_path_label = QLabel("")
        self._export_path_label.setStyleSheet("color: #2D6CDF; font-size: 11px;")
        self._export_path_label.setWordWrap(True)
        protocol_layout.addWidget(self._export_path_label)

        layout.addWidget(self._protocol_box)

        self._review_box = QGroupBox(self._tr("ui.review.group_title"))
        quality_layout = QVBoxLayout(self._review_box)
        self._review_subtitle_label = QLabel(self._tr("ui.review.subtitle"))
        quality_layout.addWidget(self._review_subtitle_label)

        self._review_list = QListWidget()
        quality_layout.addWidget(self._review_list)

        self._speaker_override = QComboBox()
        self._speaker_override.setEditable(True)
        self._speaker_override.setPlaceholderText(self._tr("ui.review.speaker_placeholder"))
        quality_layout.addWidget(self._speaker_override)

        self._correct_btn = QPushButton(self._tr("ui.review.button.apply_correction"))
        self._correct_btn.clicked.connect(self._apply_speaker_correction)
        self._correct_btn.setProperty("buttonClass", "primary")
        quality_layout.addWidget(self._correct_btn)

        layout.addWidget(self._review_box)
        return panel

    # ------------------------------------------------------------------
    # Review Queue: load + correction logic (HEAR-016)
    # ------------------------------------------------------------------

    def set_active_meeting(self, meeting_id: str, known_speakers: list[str] | None = None) -> None:
        """Called by orchestrator when a meeting session becomes active."""
        self._active_meeting_id = meeting_id
        cleanup_expired_review_files(reviews_dir(), self.runtime_config.privacy.review_retention_days)
        cleanup_expired_trace_files(traces_dir(), self.runtime_config.privacy.trace_retention_days)

        self._speaker_override.clear()
        for name in (known_speakers or []):
            self._speaker_override.addItem(name)

        # V2-12 / HEAR-117: try to restore a previously saved review queue for this meeting
        try:
            from pathlib import Path as _Path
            self._review_queue = ConfidenceReviewQueue.load(_Path(f"review-{meeting_id}.json"))
            logger.debug("Restored confidence review queue for meeting %s", meeting_id)
        except Exception:
            self._review_queue = None

        # V2-13 / HEAR-118: try to restore a previously saved trace store for this meeting
        try:
            from pathlib import Path as _Path
            self._trace_store = TraceabilityStore.load(_Path(f"trace-{meeting_id}.json"))
            logger.debug("Restored trace store for meeting %s", meeting_id)
        except Exception:
            self._trace_store = None

        self._refresh_review_queue()
        self._refresh_timer.start()

    def stop_active_meeting(self) -> None:
        self._refresh_timer.stop()
        self._save_review_queue()   # V2-12 / HEAR-117: persist final state before clearing
        self._save_trace_store()    # V2-13 / HEAR-118: persist trace state before clearing
        self._active_meeting_id = None
        self._meeting_db_backed = False  # HEAR-162: reset on meeting end
        self._review_queue = None
        self._trace_store = None
        self._speaker_manager.clear_meeting_context()

    def _reconcile_enrollment_links_after_start(self) -> None:
        """Persist deferred participant->profile links once DB IDs are available."""
        if self._participant_repo is None:
            return

        for list_uuid, profile_id in self._enrolled_speakers.items():
            db_participant_id = self._participant_id_map.get(list_uuid)
            if not db_participant_id:
                continue
            try:
                self._participant_repo.mark_enrolled(db_participant_id, profile_id)
                logger.debug(
                    "Enrollment linkage reconciled after meeting start: participant=%s profile=%s",
                    db_participant_id,
                    profile_id,
                )
            except Exception as exc:
                self._handle_persistence_error(
                    f"Failed to reconcile enrollment linkage for participant '{db_participant_id}'",
                    exc,
                )

    def _register_meeting_profile_scope(self) -> None:
        """Scope live embedding matching to enrolled profiles in the current meeting."""
        scoped_profile_ids: list[str] = []
        for i in range(self._speakers_list.count()):
            item = self._speakers_list.item(i)
            list_uuid = item.data(Qt.ItemDataRole.UserRole)
            if not list_uuid:
                continue
            profile_id = self._enrolled_speakers.get(list_uuid)
            if profile_id:
                scoped_profile_ids.append(profile_id)
        self._speaker_manager.register_meeting_profiles(scoped_profile_ids)

    def _refresh_review_queue(self) -> None:
        """Reload low-confidence and uncorrected segments from the repository."""
        self._review_list.clear()

        if self._transcript_repo is None or self._active_meeting_id is None:
            item = QListWidgetItem(self._tr("ui.review.no_active"))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._review_list.addItem(item)
            return

        try:
            segments = self._transcript_repo.low_confidence(
                self._active_meeting_id,
                threshold=self.runtime_config.protocol.minimum_confidence,
            )
        except Exception as exc:
            self._handle_persistence_error("Failed to load review queue", exc)
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
            QMessageBox.warning(
                self,
                self._tr("ui.review.correction.title"),
                self._tr("ui.review.correction.required"),
            )
            return

        segment_id: str = selected.data(Qt.ItemDataRole.UserRole)

        if self._transcript_repo is None:
            logger.warning("No transcript repository — correction not persisted.")
            return

        try:
            self._transcript_repo.apply_correction(segment_id, corrected_name)
            logger.info("Manual correction applied: segment=%s speaker=%s", segment_id, corrected_name)
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._tr("ui.error.title"),
                self._tr("ui.review.correction.save_failed", error=exc),
            )
            return

        # Remove from queue and refresh protocol snapshot if available
        row = self._review_list.row(selected)
        self._review_list.takeItem(row)
        self._refresh_protocol_display()

    def _refresh_protocol_display(self) -> None:
        """Reload the latest protocol snapshot and update the protocol view.

        Shows an explicit degraded label when persistence is not connected,
        so the panel clearly communicates its state per HEAR-085 AC3.
        """
        # AC3: explicit degraded label when persistence unavailable
        if self._snapshot_repo is None or self._active_meeting_id is None:
            current = self._protocol_view.toPlainText()
            if not current.startswith(_PROTOCOL_DEGRADED_PREFIX):
                self._protocol_view.setPlainText(self._tr("ui.protocol.degraded.unavailable"))
            return
        try:
            snapshot = self._snapshot_repo.latest(self._active_meeting_id)
            if snapshot is None:
                    current = self._protocol_view.toPlainText()
                    if not current.startswith(_PROTOCOL_DEGRADED_PREFIX):
                        self._protocol_view.setPlainText(self._tr("ui.protocol.degraded.no_snapshot"))
                    return
            content = snapshot.snapshot_content or {}
            lines: list[str] = []

            def _section(title: str, items: list[str]) -> None:
                lines.append(title)
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

            _section(self._tr("ui.protocol.section.summary", fallback="Summary"), content.get("summary", []))

            # V2-12 / HEAR-117: apply review decisions when queue is active
            if self._review_queue is not None:
                decisions = self._review_queue.get_final_items(ItemType.DECISION)
                raw_action_items = self._review_queue.get_final_items(ItemType.ACTION_ITEM)
                open_questions = self._review_queue.get_final_items(ItemType.OPEN_QUESTION)
            else:
                decisions = content.get("decisions", [])
                raw_action_items = content.get("action_items", [])
                open_questions = content.get("open_questions", [])

            _section(self._tr("ui.protocol.section.decisions", fallback="Decisions"), decisions)
            # V2-01 / HEAR-116: annotate weak action items
            annotated_action_items = self._protocol_engine.annotate_weak_items(
                raw_action_items,
                self._protocol_engine.score_action_items(raw_action_items),
            )
            _section(self._tr("ui.protocol.section.action_items", fallback="Action Items"), annotated_action_items)
            _section(self._tr("ui.protocol.section.open_questions", fallback="Open Questions"), open_questions)

            self._protocol_view.setPlainText("\n".join(lines).strip())
        except Exception as exc:
            # HEAR-130: only route genuine SQLAlchemy errors to _handle_persistence_error;
            # non-DB errors (e.g. TypeError from malformed snapshot content) must not
            # trigger a session reload — they are logged and swallowed instead.
            from sqlalchemy.exc import SQLAlchemyError
            if isinstance(exc, SQLAlchemyError):
                self._handle_persistence_error("Protocol refresh failed", exc)
            else:
                logger.error("Protocol refresh failed (non-DB): %s", exc)

    @staticmethod
    def _compute_transcript_fingerprint(text: str) -> str:
        """Return a short hash of the transcript text for delta-gating (HEAR-154)."""
        import hashlib
        return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:16]

    def _rebuild_protocol_from_persistence(self) -> None:
        """Generate a new protocol snapshot from persisted transcript data (HEAR-085 AC2).

        Called by the periodic refresh timer (every 10 s).  Uses ProtocolEngine
        to produce a structured draft from confirmed transcript segments and
        stores it as a new versioned snapshot.  No-ops when persistence is
        unavailable or no meeting is active.

        HEAR-154: delta gating — skips the LLM call when transcript has not
        changed since the last rebuild attempt, preventing idle snapshot growth.
        """
        if (
            self._active_meeting_id is None
            or self._transcript_repo is None
            or self._snapshot_repo is None
        ):
            return

        # HEAR-154: compute transcript fingerprint for delta gating
        current_transcript = self._transcript_view.toPlainText()
        current_fp = self._compute_transcript_fingerprint(current_transcript)
        if current_fp == self._last_protocol_transcript_fingerprint:
            logger.debug("HEAR-154: protocol rebuild skipped — transcript unchanged.")
            return

        try:
            snapshot = self._protocol_engine.generate(self._active_meeting_id)

            # HEAR-154: surface deferred state in protocol panel
            if self._protocol_engine.last_diagnostics.get("status") == "deferred":
                reason = self._protocol_engine.last_diagnostics.get("reason", "")
                self._protocol_view.setPlainText(
                    f"[⏸ DEFERRED] Protokollerstellung zurückgestellt — {reason}\n\n"
                    "Das System wartet auf niedrigere CPU-Last. Der letzte Stand "
                    "bleibt bis zur nächsten erfolgreichen Generierung erhalten."
                )
                # Do not update fingerprint on deferral: retry next tick
                return

            # Rebuild succeeded — update fingerprint
            self._last_protocol_transcript_fingerprint = current_fp

            # V2-12 / HEAR-117: seed review queue from first snapshot in this session
            if self._review_queue is None and snapshot.review_queue is not None:
                self._review_queue = snapshot.review_queue
                self._save_review_queue()
            # V2-13 / HEAR-118: seed trace store from first snapshot in this session
            if self._trace_store is None and snapshot.trace_store is not None:
                self._trace_store = snapshot.trace_store
                self._save_trace_store()
            self._refresh_protocol_display()
        except Exception as exc:
            # HEAR-124: only route genuine DB/SQLAlchemy errors to _handle_persistence_error
            # to avoid rolling back the active meeting on unrelated protocol-parsing failures.
            from sqlalchemy.exc import SQLAlchemyError
            if isinstance(exc, SQLAlchemyError):
                self._handle_persistence_error("Protocol rebuild failed", exc)
            else:
                logger.error("Protocol rebuild failed: %s", exc)

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
        profile_id: str = "ops",
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
            participants: list[str] = []
            if self._session is not None and hasattr(self, "_speakers_list"):
                for i in range(self._speakers_list.count()):
                    item = self._speakers_list.item(i)
                    if item is not None:
                        participants.append(item.text().split("|")[0].strip())
            start_time: str | None = None
            end_time: str | None = None
            if self._session is not None:
                if getattr(self._session, "started_at", None) is not None:
                    start_time = self._session.started_at.strftime("%H:%M")
                if getattr(self._session, "ended_at", None) is not None:
                    end_time = self._session.ended_at.strftime("%H:%M")
            md_text = self._format_as_markdown(
                draft, title, meeting_type,
                participants=participants,
                start_time=start_time,
                end_time=end_time,
                snapshot_content=self._resolve_snapshot_content(meeting_id),
                profile_id=profile_id,
                language=self._translator.language,
            )
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
                transcript_title = self._tr("export.transcript.header.title", fallback="Meeting Transcript")
                exported_label = self._tr("export.transcript.header.exported", fallback="Exported")
                header = f"{transcript_title} - {title}\n{exported_label}: {_dt.datetime.now().isoformat()}\n\n"
                txt_path.write_text(header + transcript, encoding="utf-8")
                written.append(txt_path)
            except OSError as exc:
                logger.error("Transcript export failed: %s", exc)

        return written

    def _resolve_snapshot_content(self, meeting_id: str | None) -> "dict | None":
        """Return snapshot_content dict from the latest protocol snapshot, or None."""
        if self._snapshot_repo is None or meeting_id is None:
            return None
        try:
            snapshot = self._snapshot_repo.latest(meeting_id)
            if snapshot is not None and hasattr(snapshot, "snapshot_content"):
                content = snapshot.snapshot_content
                if isinstance(content, dict):
                    return content
        except Exception:
            pass
        return None

    @staticmethod
    def _format_as_markdown(
        draft: str,
        title: str,
        meeting_type: str,
        participants: list[str] | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        snapshot_content: dict | None = None,
        profile_id: str = "ops",
        language: str = "de",
        generated_at: datetime | None = None,
    ) -> str:
        """Convert a plain-text protocol draft to branded AYE Hear Markdown.

        Produces a YAML front-matter block, a formatted header with metadata,
        an optional Meeting ROI Score block (V2-04, HEAR-175), icon-prefixed
        section headers, and an Aufgabenliste table at the end.
        Backwards-compatible: ``participants``, ``start_time``, ``end_time``
        and ``snapshot_content`` are all optional.  When ``snapshot_content``
        is ``None`` the score block is omitted.
        """
        import datetime as _dt
        import re

        from ayehear.services.export_profiles import get_profile
        from ayehear.services.decision_risk import (
            score_decision as _score_decision,
            get_high_risk_decisions as _get_high_risk_decisions,
            EMOJI_MAP as _RISK_EMOJI,
            get_risk_label_map as _get_risk_label_map,
            localize_indicators as _localize_indicators,
            RISK_HIGH as _RISK_HIGH,
        )

        resolved_language = resolve_language(language)
        translator = Translator(resolved_language)

        def _tr(key: str, fallback: str, **kwargs: object) -> str:
            value = translator.tr(key, **kwargs)
            if value == key:
                return fallback.format(**kwargs) if kwargs else fallback
            return value

        profile = get_profile(profile_id)
        risk_labels = _get_risk_label_map(resolved_language)

        now = generated_at or _dt.datetime.now()
        date_iso = now.strftime("%Y-%m-%d")
        date_de = now.strftime("%d.%m.%Y")
        date_display = date_de if resolved_language == "de" else date_iso
        export_ts = now.isoformat(timespec="seconds")
        start_str = start_time or ""
        end_str = end_time or ""
        time_range = (
            _tr(
                "export.protocol.header.time_range",
                "{start} – {end}",
                start=start_str,
                end=end_str,
            )
            if start_str or end_str
            else "—"
        )
        parts = participants or []

        # --- YAML front-matter ---
        fm_lines = [
            "---",
            f"meeting: {title}",
            f"type: {meeting_type}",
            f"date: {date_iso}",
            f"start: {start_str}",
            f"end: {end_str}",
            "participants:",
        ]
        if parts:
            for p in parts:
                fm_lines.append(f"  - {p}")
        else:
            fm_lines.append("  - —")
        fm_lines += [
            _tr("export.protocol.frontmatter.version", "protocol_version: Draft"),
            f"export: {export_ts}",
            "# logo: assets/Aye_Hear_Logo.png",
            "---",
            "",
        ]

        # --- Header ---
        header_lines = [
            f"# {_tr('export.protocol.header.title', 'MEETING PROTOCOL')}",
            "",
            f"**{_tr('export.protocol.header.meeting_label', 'Meeting')}:** {title}  ",
            f"**{_tr('export.protocol.header.type_label', 'Type')}:** {meeting_type}  ",
            f"**{_tr('export.protocol.header.date_label', 'Date')}:** {date_display}  ",
            f"**{_tr('export.protocol.header.time_label', 'Time')}:** {time_range}  ",
            "",
            f"**{_tr('export.protocol.header.participants_label', 'Participants')}:**",
        ]
        if parts:
            for p in parts:
                header_lines.append(f"- {p}")
        else:
            header_lines.append("- —")
        header_lines += ["", "---", ""]

        # --- ROI Score block (V2-04, HEAR-175) ---
        score_lines: list[str] = []
        if profile.include_score and snapshot_content is not None:
            from ayehear.services.meeting_score import calculate_roi_score
            roi = calculate_roi_score(snapshot_content)
            s = roi["score"]
            pos = roi["drivers_positive"]
            neg = roi["drivers_negative"]
            score_lines = [
                f"## {_tr('export.protocol.score.section_title', '📊 Meeting Effectiveness')}",
                "",
                f"**{_tr('export.protocol.score.label', 'Score')}: {s} / 100**",
                "",
            ]
            if pos:
                score_lines.append(_tr("export.protocol.score.positive", "✅ Positive") + ": " + " \u00b7 ".join(pos))
            if neg:
                score_lines.append(_tr("export.protocol.score.negative", "⚠️ Improvement Potential") + ": " + " \u00b7 ".join(neg))
            score_lines += ["", "---", ""]

        # --- Section mapping with icons ---
        _SECTION_MAP: dict[str, str] = {
            "Summary": _tr("export.protocol.section.summary", "📝 Summary"),
            "Decisions": _tr("export.protocol.section.decisions", "✅ Decisions"),
            "Action Items": _tr("export.protocol.section.action_items", "📌 Action Items"),
            "Open Questions": _tr("export.protocol.section.open_questions", "⚠️ Open Questions"),
            "Next Steps": _tr("export.protocol.section.next_steps", "🔷 Next Steps"),
            "Transcript": _tr("export.protocol.section.transcript", "🎙 Transcript"),
        }

        _LEGACY_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
            "Summary": ("Zusammenfassung",),
            "Decisions": ("Entscheidungen",),
            "Action Items": ("Aufgaben", "To-Dos", "To-Dos / Aufgaben"),
            "Open Questions": ("Offene Fragen", "Offene Punkte"),
            "Next Steps": ("Nächste Schritte",),
            "Transcript": ("Transkript",),
        }

        _section_alias_to_canonical: dict[str, str] = {}
        for canonical in _SECTION_MAP:
            _section_alias_to_canonical[canonical] = canonical
            plain_key = canonical.lower().replace(" ", "_")
            translated_plain = _tr(
                f"ui.protocol.section.{plain_key}",
                canonical,
            )
            _section_alias_to_canonical[translated_plain] = canonical
            for alias in _LEGACY_SECTION_ALIASES.get(canonical, ()):  # backwards compatibility
                _section_alias_to_canonical[alias] = canonical

        include_sections: dict[str, bool] = {
            "Summary": profile.include_summary,
            "Decisions": profile.include_decisions,
            "Action Items": profile.include_action_items,
            "Open Questions": profile.include_open_questions,
            "Next Steps": profile.include_next_steps,
            # Team and CEO outputs intentionally hide raw transcript for focus.
            "Transcript": profile.id in ("ops", "compliance"),
        }

        # --- Parse draft sections ---
        preamble: list[str] = []
        section_lines: dict[str, list[str]] = {k: [] for k in _SECTION_MAP}
        action_items_raw: list[str] = []
        decisions_raw: list[str] = []
        current_section: str | None = None
        body_lines: list[str] = []

        # Prefer decisions from structured snapshot_content when available
        _snapshot_decisions: list[str] = (
            snapshot_content.get("decisions", []) if snapshot_content else []
        )

        for raw in draft.splitlines():
            stripped = raw.strip()
            canonical = _section_alias_to_canonical.get(stripped)
            if canonical is not None:
                current_section = canonical
            else:
                if current_section is None:
                    preamble.append(raw)
                else:
                    section_lines[current_section].append(raw)

        decisions_rendered = 0
        max_decisions = profile.max_decisions

        if preamble:
            body_lines.extend(preamble)
            body_lines.append("")

        for section_name, icon_label in _SECTION_MAP.items():
            if not include_sections.get(section_name, True):
                continue

            lines = section_lines.get(section_name, [])
            if section_name == "Decisions":
                rendered_lines: list[str] = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("- "):
                        if max_decisions is not None and decisions_rendered >= max_decisions:
                            continue
                        decision_text = stripped[2:]
                        decisions_raw.append(decision_text)
                        assessed = _score_decision(decision_text)
                        emoji = _RISK_EMOJI[assessed["risk_level"]]
                        rendered_lines.append(f"- {decision_text} {emoji}")
                        decisions_rendered += 1
                    else:
                        rendered_lines.append(line)
                lines = rendered_lines
            elif section_name == "Action Items":
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("- "):
                        action_items_raw.append(stripped[2:])

            body_lines.append(f"## {icon_label}")
            body_lines.extend(lines)
            body_lines.append("")

        # If snapshot_content supplies decisions not in draft, prefer those
        all_decisions = _snapshot_decisions if _snapshot_decisions else decisions_raw
        if max_decisions is not None:
            all_decisions = all_decisions[:max_decisions]
        risk_entries = _get_high_risk_decisions(all_decisions)
        if profile.risk_filter == "high":
            risk_entries = [entry for entry in risk_entries if entry["risk_level"] == _RISK_HIGH]

        # --- Decision Risk section (V2-02, HEAR-176) ---
        risk_section_lines: list[str] = []
        if profile.include_risk_table and risk_entries:
            risk_section_lines = [
                "",
                f"## {_tr('export.protocol.risk.section_title', '⚠️ Decision Risks')}",
                "",
                "| " + _tr("export.protocol.risk.table.decision", "Decision") + " | "
                + _tr("export.protocol.risk.table.risk", "Risk") + " | "
                + _tr("export.protocol.risk.table.indicators", "Indicators") + " |",
                "|---|---|---|",
            ]
            for entry in risk_entries:
                emoji = _RISK_EMOJI[entry["risk_level"]]
                label = risk_labels[entry["risk_level"]]
                localized_indicators = _localize_indicators(entry["indicators"], resolved_language)
                indicators_str = ", ".join(localized_indicators) if localized_indicators else "—"
                short_text = entry["text"][:60] + ("…" if len(entry["text"]) > 60 else "")
                risk_section_lines.append(
                    f"| {short_text} | {emoji} {label} | {indicators_str} |"
                )
            risk_section_lines += [""]

        # --- Aufgabenliste table ---
        table_rows: list[tuple[str, str, str]] = []
        date_pattern = re.compile(r"\b(\d{1,2}\.\d{1,2}\.(?:\d{2,4})?)\b")
        for item in action_items_raw:
            # Pattern: "Name: task description bis DD.MM."
            if ":" in item:
                name, rest = item.split(":", 1)
                name = name.strip()
                rest = rest.strip()
            else:
                name = _tr("export.protocol.tasks.unassigned", "Open")
                rest = item
            m = date_pattern.search(rest)
            due = m.group(1) if m else "—"
            # Remove the date expression from task description
            task_text = date_pattern.sub("", rest)
            if resolved_language == "de":
                task_text = task_text.replace("bis", "")
            else:
                task_text = task_text.replace("by", "")
            task_text = task_text.strip().rstrip(",").strip()
            table_rows.append((task_text or rest, name, due))

        table_lines: list[str] = []
        if profile.include_task_table:
            if not table_rows:
                table_rows = [(_tr("export.protocol.tasks.none", "No open tasks"), "—", "—")]

            table_lines = [
                "",
                "---",
                "",
                f"## {_tr('export.protocol.tasks.section_title', 'Task List')}",
                "",
                "| # | " + _tr("export.protocol.tasks.table.task", "Task") + " | "
                + _tr("export.protocol.tasks.table.owner", "Responsible") + " | "
                + _tr("export.protocol.tasks.table.due", "Due") + " |",
                "|---|---------|---------------|--------|",
            ]
            for idx, (task, responsible, due) in enumerate(table_rows, start=1):
                table_lines.append(f"| {idx} | {task} | {responsible} | {due} |")

        compliance_lines: list[str] = []
        if profile.include_compliance_note:
            compliance_lines = [
                "",
                f"## {_tr('export.protocol.compliance.section_title', '🔏 Privacy & Compliance')}",
                "",
                _tr(
                    "export.protocol.compliance.local_only",
                    "This protocol was processed strictly locally. No audio, transcript, or protocol data left the local system boundary.",
                ) + "  ",
                _tr(
                    "export.protocol.compliance.offline_attested",
                    "Offline processing confirmed according to ADR-0001 (AYE Hear Offline-First principle).",
                ),
                "",
            ]

        # --- Footer ---
        footer_lines: list[str] = []
        if profile.include_ai_disclaimer or profile.include_offline_attestation:
            attest_parts = [_tr("export.protocol.footer.generated", "This protocol was generated automatically with AYE Hear")]
            if profile.include_offline_attestation:
                attest_parts.append(_tr("export.protocol.footer.offline", "Offline processing confirmed"))
            attest_parts.append(_tr("export.protocol.footer.review", "Please review before official distribution"))
            footer_lines.extend(["", "---", "", f"*{' · '.join(attest_parts)}.*"])
            if profile.include_ai_disclaimer:
                footer_lines.extend(
                    [
                        "",
                        "*"
                        + _tr(
                            "export.protocol.footer.disclaimer",
                            "Protocol and transcript quality can be affected by model and acoustic limitations. Human review is required before official distribution.",
                        )
                        + "*",
                    ]
                )

        all_lines = fm_lines + header_lines + score_lines + body_lines + risk_section_lines + table_lines + compliance_lines + footer_lines
        return "\n".join(all_lines)

    def _do_export_protocol(self) -> None:
        """Export the current protocol draft to <install_root>/exports/ as Markdown."""
        import datetime as _dt
        from ayehear.utils.paths import exports_dir as _exports_dir
        from ayehear.services.export_profiles import (
            PROFILE_CEO,
            PROFILE_OPS,
            PROFILE_TEAM,
            PROFILE_COMPLIANCE,
            get_profile_label,
        )

        draft = self._protocol_view.toPlainText().strip()
        if not draft or draft.startswith("[DEGRADED]"):
            if draft.startswith("[DEGRADED]"):
                QMessageBox.warning(
                    self,
                    self._tr("ui.export.warning.title"),
                    self._tr("ui.export.warning.degraded"),
                )
            else:
                QMessageBox.warning(
                    self,
                    self._tr("ui.export.warning.title"),
                    self._tr("ui.export.warning.empty"),
                )
            return

        title = ""
        if self._session is not None:
            title = self._session.title or ""

        profile_ids = [PROFILE_CEO, PROFILE_OPS, PROFILE_TEAM, PROFILE_COMPLIANCE]
        profile_labels = [get_profile_label(pid, self._translator.language) for pid in profile_ids]
        selected_label, ok = QInputDialog.getItem(
            self,
            self._tr("ui.export.profile.title"),
            self._tr("ui.export.profile.label"),
            profile_labels,
            profile_ids.index(PROFILE_OPS),
            False,
        )
        if not ok:
            return
        profile_id = PROFILE_OPS
        for pid in profile_ids:
            if get_profile_label(pid, self._translator.language) == selected_label:
                profile_id = pid
                break

        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:40]
        filename = f"protocol_{safe_title}_{timestamp}.md" if safe_title else f"protocol_{timestamp}.md"

        try:
            out_dir = _exports_dir()
            out_path = out_dir / filename
            participants: list[str] = []
            if self._session is not None and hasattr(self, "_speakers_list"):
                for i in range(self._speakers_list.count()):
                    item = self._speakers_list.item(i)
                    if item is not None:
                        participants.append(item.text().split("|")[0].strip())
            start_time: str | None = None
            end_time: str | None = None
            if self._session is not None:
                if getattr(self._session, "started_at", None) is not None:
                    start_time = self._session.started_at.strftime("%H:%M")
                if getattr(self._session, "ended_at", None) is not None:
                    end_time = self._session.ended_at.strftime("%H:%M")
            md_text = self._format_as_markdown(
                draft,
                title,
                self._meeting_type.currentText() if hasattr(self, "_meeting_type") else "",
                participants=participants,
                start_time=start_time,
                end_time=end_time,
                snapshot_content=self._resolve_snapshot_content(self._active_meeting_id),
                profile_id=profile_id,
                language=self._translator.language,
            )
            out_path.write_text(md_text, encoding="utf-8")
            self._export_path_label.setText(self._tr("ui.export.path_label", path=out_path))
            logger.info("Protocol exported to %s (profile=%s)", out_path, profile_id)
            QMessageBox.information(
                self,
                self._tr("ui.export.success.title"),
                self._tr("ui.export.success.body", path=out_path),
            )
        except OSError as exc:
            logger.error("Protocol export failed: %s", exc)
            QMessageBox.critical(
                self,
                self._tr("ui.export.error.title"),
                self._tr("ui.export.error.body", error=exc),
            )

    _TRANSCRIPT_SECTION_HEADER = "## Transcript"

    def _update_protocol_live(self, transcript_line: str) -> None:
        """Refresh the protocol draft view on each new transcript line (HEAR-085 AC1/AC2).

        Delegates to _refresh_protocol_display in all cases:
        - With DB: renders the latest structured snapshot.
        - Without DB: _refresh_protocol_display shows the [DEGRADED] label (AC3/AC5).
          Transcript text must never appear in the protocol panel (HEAR-085 AC1/AC5).
        """
        self._refresh_protocol_display()

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
