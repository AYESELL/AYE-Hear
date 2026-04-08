from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ayehear.models.runtime import RuntimeConfig


class MainWindow(QMainWindow):
    def __init__(self, runtime_config: RuntimeConfig) -> None:
        super().__init__()
        self.runtime_config = runtime_config

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

    def _build_setup_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        meeting_box = QGroupBox("Meeting Setup")
        form = QFormLayout(meeting_box)
        form.addRow("Meeting Title", QLineEdit())
        form.addRow("Mode", QLineEdit("internal"))
        form.addRow("Default Input", QLineEdit("Windows default microphone"))
        layout.addWidget(meeting_box)

        speakers_box = QGroupBox("Speaker Enrollment")
        speakers_layout = QVBoxLayout(speakers_box)
        speakers_layout.addWidget(QLabel("Participants introduce themselves before recording starts."))
        speakers = QListWidget()
        speakers.addItems([
            "Anna Schneider | AYE | pending enrollment",
            "Max Weber | Customer | pending enrollment",
        ])
        speakers_layout.addWidget(speakers)
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

        transcript = QPlainTextEdit()
        transcript.setReadOnly(True)
        transcript.setPlainText(
            "[00:00] System: Meeting initialized.\n"
            "[00:07] Anna Schneider: Good morning, I am Anna from AYE...\n"
            "[00:15] Max Weber: Hello, I represent the customer side..."
        )
        status_layout.addWidget(transcript)
        layout.addWidget(status)
        return panel

    def _build_protocol_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        protocol_box = QGroupBox("Protocol Draft")
        protocol_layout = QVBoxLayout(protocol_box)
        protocol_layout.addWidget(QLabel("Decisions, action items and open questions update on significant events."))

        protocol = QPlainTextEdit()
        protocol.setReadOnly(True)
        protocol.setPlainText(
            "Summary\n"
            "- Meeting started with speaker enrollment.\n\n"
            "Decisions\n"
            "- Waiting for first confirmed decision.\n\n"
            "Action Items\n"
            "- No action items detected yet."
        )
        protocol_layout.addWidget(protocol)
        layout.addWidget(protocol_box)

        quality_box = QGroupBox("Review Queue")
        quality_layout = QVBoxLayout(quality_box)
        quality_layout.addWidget(QLabel("Unknown speakers and low-confidence assignments appear here."))
        quality_layout.addWidget(QListWidget())
        layout.addWidget(quality_box)
        return panel
