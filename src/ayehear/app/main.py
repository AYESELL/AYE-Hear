from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ayehear.app.window import MainWindow
from ayehear.services.speaker_manager import SpeakerManager
from ayehear.storage.database import DatabaseBootstrap, DatabaseConfig, load_runtime_dsn
from ayehear.storage.repositories import (
    MeetingRepository,
    ParticipantRepository,
    ProtocolSnapshotRepository,
    SpeakerProfileRepository,
    TranscriptSegmentRepository,
)
from ayehear.utils.config import load_runtime_config
from ayehear.utils.logging import setup_logging


logger = logging.getLogger(__name__)


def main() -> int:
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("AYE Hear")
    app.setOrganizationName("AYESELL")

    config_path = Path("config/default.yaml")
    runtime_config = load_runtime_config(config_path)

    db_session = None
    meeting_repo = None
    participant_repo = None
    transcript_repo = None
    snapshot_repo = None
    speaker_manager = None

    try:
        dsn = load_runtime_dsn()
        if dsn:
            bootstrap = DatabaseBootstrap(DatabaseConfig(dsn=dsn))
            bootstrap.bootstrap()
            db_session = bootstrap.session()

            meeting_repo = MeetingRepository(db_session)
            participant_repo = ParticipantRepository(db_session)
            transcript_repo = TranscriptSegmentRepository(db_session)
            snapshot_repo = ProtocolSnapshotRepository(db_session)
            speaker_manager = SpeakerManager(
                profile_repo=SpeakerProfileRepository(db_session),
                participant_repo=participant_repo,
            )
            logger.info("Persistence bootstrap completed; review queue and protocol snapshots enabled.")
        else:
            logger.warning(
                "No runtime DSN found (env or installer path). Starting in local-only mode without persistence."
            )
    except Exception as exc:
        logger.error("Database bootstrap failed; starting in degraded local-only mode: %s", exc)
        if db_session is not None:
            db_session.close()
            db_session = None

    window = MainWindow(
        runtime_config=runtime_config,
        db_session=db_session,
        meeting_repo=meeting_repo,
        participant_repo=participant_repo,
        transcript_repo=transcript_repo,
        snapshot_repo=snapshot_repo,
        speaker_manager=speaker_manager,
    )
    window.show()

    try:
        return app.exec()
    finally:
        if db_session is not None:
            try:
                # Safely close database session even if PostgreSQL connection is broken.
                # This handles the case where the server closed the connection unexpectedly
                # during rollback (ADR-0006 loopback safety constraint applies).
                db_session.close()
            except Exception as exc:
                # Log but don't propagate: the app is shutting down and we don't want
                # a database close error to mask the exit code or raise during cleanup.
                logger.warning(
                    "Database session close() raised during shutdown; connection may be disconnected. "
                    "Error: %s %s", type(exc).__name__, exc
                )
