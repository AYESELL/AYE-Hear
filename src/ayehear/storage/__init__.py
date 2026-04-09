"""Persistence layer for PostgreSQL-backed meeting, speaker and protocol state.

Public surface:
  DatabaseBootstrap   – connection + schema bootstrap (ADR-0006/0008)
  DatabaseConfig      – DSN holder
  MeetingRepository   – meeting CRUD and lifecycle
  SpeakerProfileRepository – enrollment and profile management
  ParticipantRepository  – meeting-scoped participant lifecycle
  TranscriptSegmentRepository – segment ingestion, review queue
  ProtocolSnapshotRepository  – append-only snapshot versioning
"""
from ayehear.storage.database import DatabaseBootstrap, DatabaseConfig
from ayehear.storage.orm import (
    Base,
    Meeting,
    Participant,
    ProtocolActionItem,
    ProtocolSnapshot,
    SpeakerProfile,
    TranscriptCorrectionLog,
    TranscriptSegment,
)
from ayehear.storage.repositories import (
    MeetingRepository,
    ParticipantRepository,
    ProtocolSnapshotRepository,
    SpeakerProfileRepository,
    TranscriptSegmentRepository,
)

__all__ = [
    "DatabaseBootstrap",
    "DatabaseConfig",
    "Base",
    "Meeting",
    "Participant",
    "ProtocolActionItem",
    "ProtocolSnapshot",
    "SpeakerProfile",
    "TranscriptCorrectionLog",
    "TranscriptSegment",
    "MeetingRepository",
    "ParticipantRepository",
    "ProtocolSnapshotRepository",
    "SpeakerProfileRepository",
    "TranscriptSegmentRepository",
]
