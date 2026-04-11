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
    TranscriptCorrectionLog,
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

    def update_metadata(
        self,
        participant_id: str,
        *,
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        salutation: str | None = None,
        organization: str | None = None,
        naming_template: str | None = None,
    ) -> Participant:
        """Update individual metadata fields for a pre-registered participant.

        Only non-None keyword arguments are applied, leaving other fields unchanged.
        Raises ValueError when the participant does not exist (HEAR-020).
        """
        p = self._s.get(Participant, participant_id)
        if p is None:
            raise ValueError(f"Participant {participant_id!r} not found.")
        if display_name is not None:
            p.display_name = display_name
        if first_name is not None:
            p.first_name = first_name
        if last_name is not None:
            p.last_name = last_name
        if salutation is not None:
            p.salutation = salutation
        if organization is not None:
            p.organization = organization
        if naming_template is not None:
            p.naming_template = naming_template
        self._s.flush()
        return p

    def display_names_for_meeting(self, meeting_id: str) -> list[str]:
        """Return the ordered display names of all participants in a meeting.

        Used by SpeakerManager.register_meeting_participants() to seed the
        participant-constrained intro-matching set (HEAR-021 / ADR-0003 Stage 0).
        """
        return [p.display_name for p in self.list_for_meeting(meeting_id)]


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
        """Return unreviewed, non-silence segments below the given confidence threshold."""
        return (
            self._s.query(TranscriptSegment)
            .filter(
                TranscriptSegment.meeting_id == meeting_id,
                TranscriptSegment.is_silence.is_(False),
                TranscriptSegment.confidence_score < threshold,
                TranscriptSegment.manual_correction.is_(False),
            )
            .order_by(TranscriptSegment.start_ms)
            .all()
        )

    def apply_correction(
        self,
        segment_id: str,
        speaker_name: str,
        participant_id: str | None = None,
    ) -> TranscriptSegment:
        """Assign a corrected speaker name, update participant mapping, and log the audit trail.

        Writes an immutable TranscriptCorrectionLog entry with the before-state,
        then updates the segment in-place (ADR-0003 / ADR-0007 / HEAR-022).

        Args:
            segment_id:     ID of the TranscriptSegment to correct.
            speaker_name:   Corrected display name to assign to the segment.
            participant_id: When provided, also updates the participant FK link
                            so the segment is associated with the correct Participant
                            record (enables downstream protocol grouping by participant).
        """
        seg = self._s.get(TranscriptSegment, segment_id)
        if seg is None:
            raise ValueError(f"TranscriptSegment {segment_id!r} not found.")

        # Audit log: capture before-state (HEAR-022)
        log_entry = TranscriptCorrectionLog(
            transcript_segment_id=seg.id,
            previous_speaker_name=seg.speaker_name,
            corrected_speaker_name=speaker_name,
            previous_participant_id=seg.participant_id,
            corrected_participant_id=participant_id,
        )
        self._s.add(log_entry)

        # Apply corrections to the segment
        seg.speaker_name = speaker_name
        if participant_id is not None:
            seg.participant_id = participant_id
        seg.manual_correction = True
        self._s.flush()
        return seg

    def correction_history(self, segment_id: str) -> list[TranscriptCorrectionLog]:
        """Return all correction log entries for a segment, oldest first.

        Provides the full audit trail for ADR-0007 compliance checks and QA review.
        """
        return (
            self._s.query(TranscriptCorrectionLog)
            .filter(TranscriptCorrectionLog.transcript_segment_id == segment_id)
            .order_by(TranscriptCorrectionLog.corrected_at)
            .all()
        )

    def list_for_protocol(self, meeting_id: str) -> list[TranscriptSegment]:
        """Return non-silence segments in chronological order for protocol generation.

        Since apply_correction() updates speaker_name in-place, segments returned
        here already reflect the reviewed (corrected) state. The manual_correction
        flag on each segment indicates which assignments were manually verified.
        This makes the 'prefer reviewed state' intent explicit (HEAR-022 / ADR-0007).
        """
        return (
            self._s.query(TranscriptSegment)
            .filter(
                TranscriptSegment.meeting_id == meeting_id,
                TranscriptSegment.is_silence.is_(False),
            )
            .order_by(TranscriptSegment.start_ms)
            .all()
        )


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
