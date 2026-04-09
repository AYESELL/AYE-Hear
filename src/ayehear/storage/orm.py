"""SQLAlchemy Declarative ORM models aligned with ADR-0007 canonical entities.

Entities: meetings, participants, speaker_profiles, transcript_segments,
          protocol_snapshots, protocol_action_items
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    mode: Mapped[str] = mapped_column(String(64), nullable=False, default="internal")
    meeting_type: Mapped[str] = mapped_column(String(64), nullable=False, default="internal")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    participants: Mapped[list[Participant]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    transcript_segments: Mapped[list[TranscriptSegment]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    protocol_snapshots: Mapped[list[ProtocolSnapshot]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    # embedding stored as JSON array (pgvector extension optional for V1)
    embedding_vector: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    participants: Mapped[list[Participant]] = relationship(back_populates="speaker_profile")


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    meeting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    speaker_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("speaker_profiles.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    # ADR-0007: participant metadata fields for HEAR-017
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    salutation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(256), nullable=True)
    naming_template: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enrollment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )  # pending | enrolled | skipped
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    meeting: Mapped[Meeting] = relationship(back_populates="participants")
    speaker_profile: Mapped[SpeakerProfile | None] = relationship(back_populates="participants")
    transcript_segments: Mapped[list[TranscriptSegment]] = relationship(
        back_populates="participant"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    meeting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_name: Mapped[str] = mapped_column(String(256), nullable=False, default="Unknown Speaker")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_silence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # manual_correction=True marks reviewed/corrected speaker assignments (ADR-0007)
    manual_correction: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    meeting: Mapped[Meeting] = relationship(back_populates="transcript_segments")
    participant: Mapped[Participant | None] = relationship(back_populates="transcript_segments")


class ProtocolSnapshot(Base):
    __tablename__ = "protocol_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    meeting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_content: Mapped[dict] = mapped_column(JSON, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1.0")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    meeting: Mapped[Meeting] = relationship(back_populates="protocol_snapshots")
    action_items: Mapped[list[ProtocolActionItem]] = relationship(
        back_populates="protocol_snapshot", cascade="all, delete-orphan"
    )


class ProtocolActionItem(Base):
    __tablename__ = "protocol_action_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    protocol_snapshot_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("protocol_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    assignee_participant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    protocol_snapshot: Mapped[ProtocolSnapshot] = relationship(back_populates="action_items")
