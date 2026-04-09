"""Repository/Facade layer for PostgreSQL-backed persistence (HEAR-010).

Each repository owns CRUD for a single aggregate root, enforcing the
ADR-0007 lifecycle rules:
  - No alternate DB backend path.
  - TranscriptSegment.manual_correction semantics are enforced here.
  - ProtocolSnapshot is append-only (no UPDATE path provided).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ayehear.storage.orm import (
    Meeting,
    Participant,
    ProtocolActionItem,
    ProtocolSnapshot,
    SpeakerProfile,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MeetingRepository
# ---------------------------------------------------------------------------

class MeetingRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def create(self, title: str, meeting_type: str = "internal", mode: str | None = None) -> Meeting:
        _mode = mode or meeting_type
        meeting = Meeting(title=title, mode=_mode, meeting_type=meeting_type)
        self._s.add(meeting)
        self._s.flush()
        logger.debug("Created meeting %s", meeting.id)
        return meeting

    def get_by_id(self, meeting_id: str) -> Meeting | None:
        return self._s.get(Meeting, meeting_id)

    def list_active(self) -> list[Meeting]:
        return (
            self._s.query(Meeting)
            .filter(Meeting.status == "active")
            .order_by(Meeting.created_at.desc())
            .all()
        )

    def start(self, meeting_id: str) -> Meeting:
        meeting = self._require(meeting_id)
        meeting.started_at = datetime.now(timezone.utc)
        meeting.status = "active"
        self._s.flush()
        return meeting

    def end(self, meeting_id: str) -> Meeting:
        meeting = self._require(meeting_id)
        meeting.ended_at = datetime.now(timezone.utc)
        meeting.status = "completed"
        self._s.flush()
        return meeting

    def _require(self, meeting_id: str) -> Meeting:
        obj = self.get_by_id(meeting_id)
        if obj is None:
            raise ValueError(f"Meeting {meeting_id!r} not found.")
        return obj


# ---------------------------------------------------------------------------
# SpeakerProfileRepository
# ---------------------------------------------------------------------------

class SpeakerProfileRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def upsert(
        self,
        display_name: str,
        embedding_vector: list[float] | None = None,
        embedding_version: str | None = None,
        profile_id: str | None = None,
    ) -> SpeakerProfile:
        if profile_id:
            profile = self._s.get(SpeakerProfile, profile_id)
            if profile is None:
                raise ValueError(f"SpeakerProfile {profile_id!r} not found.")
        else:
            profile = SpeakerProfile(display_name=display_name)
            self._s.add(profile)

        profile.display_name = display_name
        if embedding_vector is not None:
            profile.embedding_vector = embedding_vector
        if embedding_version is not None:
            profile.embedding_version = embedding_version
        self._s.flush()
        return profile

    def get_by_id(self, profile_id: str) -> SpeakerProfile | None:
        return self._s.get(SpeakerProfile, profile_id)

    def list_all(self) -> list[SpeakerProfile]:
        return self._s.query(SpeakerProfile).order_by(SpeakerProfile.display_name).all()


# ---------------------------------------------------------------------------
# ParticipantRepository
# ---------------------------------------------------------------------------

class ParticipantRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(
        self,
        meeting_id: str,
        display_name: str,
        speaker_profile_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        salutation: str | None = None,
        organization: str | None = None,
        naming_template: str | None = None,
    ) -> Participant:
        p = Participant(
            meeting_id=meeting_id,
            display_name=display_name,
            speaker_profile_id=speaker_profile_id,
            first_name=first_name,
            last_name=last_name,
            salutation=salutation,
            organization=organization,
            naming_template=naming_template,
        )
        self._s.add(p)
        self._s.flush()
        return p

    def get_by_id(self, participant_id: str) -> Participant | None:
        return self._s.get(Participant, participant_id)

    def list_for_meeting(self, meeting_id: str) -> list[Participant]:
        return (
            self._s.query(Participant)
            .filter(Participant.meeting_id == meeting_id)
            .all()
        )

    def mark_enrolled(self, participant_id: str, speaker_profile_id: str) -> Participant:
        p = self._s.get(Participant, participant_id)
        if p is None:
            raise ValueError(f"Participant {participant_id!r} not found.")
        p.speaker_profile_id = speaker_profile_id
        p.enrollment_status = "enrolled"
        self._s.flush()
        return p


# ---------------------------------------------------------------------------
# TranscriptSegmentRepository
# ---------------------------------------------------------------------------

class TranscriptSegmentRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(
        self,
        meeting_id: str,
        start_ms: int,
        end_ms: int,
        speaker_name: str = "Unknown Speaker",
        text: str = "",
        confidence_score: float = 0.0,
        participant_id: str | None = None,
        is_silence: bool = False,
        manual_correction: bool = False,
    ) -> TranscriptSegment:
        seg = TranscriptSegment(
            meeting_id=meeting_id,
            participant_id=participant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            speaker_name=speaker_name,
            text=text,
            confidence_score=confidence_score,
            is_silence=is_silence,
            manual_correction=manual_correction,
        )
        self._s.add(seg)
        self._s.flush()
        return seg

    def list_for_meeting(self, meeting_id: str) -> list[TranscriptSegment]:
        return (
            self._s.query(TranscriptSegment)
            .filter(TranscriptSegment.meeting_id == meeting_id)
            .order_by(TranscriptSegment.start_ms)
            .all()
        )

    def low_confidence(
        self, meeting_id: str, threshold: float = 0.65
    ) -> list[TranscriptSegment]:
        """Return unreviewed segments below the given confidence threshold."""
        return (
            self._s.query(TranscriptSegment)
            .filter(
                TranscriptSegment.meeting_id == meeting_id,
                TranscriptSegment.confidence_score < threshold,
                TranscriptSegment.manual_correction.is_(False),
            )
            .order_by(TranscriptSegment.start_ms)
            .all()
        )

    def apply_correction(
        self, segment_id: str, speaker_name: str
    ) -> TranscriptSegment:
        """Assign a corrected speaker name and mark the segment as manually reviewed."""
        seg = self._s.get(TranscriptSegment, segment_id)
        if seg is None:
            raise ValueError(f"TranscriptSegment {segment_id!r} not found.")
        seg.speaker_name = speaker_name
        seg.manual_correction = True
        self._s.flush()
        return seg


# ---------------------------------------------------------------------------
# ProtocolSnapshotRepository  (append-only per ADR-0007)
# ---------------------------------------------------------------------------

class ProtocolSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def append(
        self,
        meeting_id: str,
        content: dict | None = None,
        snapshot_content: dict | None = None,
        engine_version: str = "v1.0",
    ) -> ProtocolSnapshot:
        """Create the next immutable snapshot for a meeting."""
        _content = content if content is not None else (snapshot_content or {})
        current_max = (
            self._s.query(ProtocolSnapshot)
            .filter(ProtocolSnapshot.meeting_id == meeting_id)
            .count()
        )
        snapshot = ProtocolSnapshot(
            meeting_id=meeting_id,
            snapshot_version=current_max + 1,
            snapshot_content=_content,
            engine_version=engine_version,
        )
        self._s.add(snapshot)
        self._s.flush()
        return snapshot

    def latest(self, meeting_id: str) -> ProtocolSnapshot | None:
        return (
            self._s.query(ProtocolSnapshot)
            .filter(ProtocolSnapshot.meeting_id == meeting_id)
            .order_by(ProtocolSnapshot.snapshot_version.desc())
            .first()
        )

    def all_versions(self, meeting_id: str) -> list[ProtocolSnapshot]:
        return (
            self._s.query(ProtocolSnapshot)
            .filter(ProtocolSnapshot.meeting_id == meeting_id)
            .order_by(ProtocolSnapshot.snapshot_version)
            .all()
        )

    def add_action_item(
        self,
        protocol_snapshot_id: str,
        title: str,
        description: str | None = None,
        assignee_participant_id: str | None = None,
    ) -> ProtocolActionItem:
        item = ProtocolActionItem(
            protocol_snapshot_id=protocol_snapshot_id,
            title=title,
            description=description,
            assignee_participant_id=assignee_participant_id,
        )
        self._s.add(item)
        self._s.flush()
        return item
