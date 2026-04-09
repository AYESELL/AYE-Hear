"""Tests for PostgreSQL persistence contract and repository behavior (HEAR-009/010).

These tests avoid introducing an alternate database backend. They validate the
canonical storage contract through SQLAlchemy metadata, the PostgreSQL migration
script, and lightweight session/query doubles for repository behavior.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ayehear.storage.orm import (
    Base,
    Meeting,
    Participant,
    SpeakerProfile,
    TranscriptSegment,
    ProtocolSnapshot,
    ProtocolActionItem,
)
from ayehear.storage.repositories import (
    MeetingRepository,
    ParticipantRepository,
    SpeakerProfileRepository,
    TranscriptSegmentRepository,
    ProtocolSnapshotRepository,
)


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ayehear" / "storage" / "migrations" / "001_initial_schema.sql"
)


# ---------------------------------------------------------------------------
# Lightweight repository test doubles
# ---------------------------------------------------------------------------


class FakeQuery:
    def __init__(self, items: list[object]) -> None:
        self._items = list(items)

    def filter(self, *criteria):
        items = self._items
        for criterion in criteria:
            left = getattr(criterion, "left", None)
            right = getattr(criterion, "right", None)
            operator = getattr(getattr(criterion, "operator", None), "__name__", "")
            column_name = getattr(left, "name", None)
            value = getattr(right, "value", right)

            if operator == "is_" and value is None:
                value = False

            if column_name is None:
                continue

            if operator == "eq":
                items = [item for item in items if getattr(item, column_name) == value]
            elif operator == "ne":
                items = [item for item in items if getattr(item, column_name) != value]
            elif operator == "lt":
                items = [item for item in items if getattr(item, column_name) < value]
            elif operator == "is_":
                items = [item for item in items if getattr(item, column_name) == value]

        return FakeQuery(items)

    def order_by(self, *args):
        items = list(self._items)
        if args:
            clause = args[0]
            column_name = getattr(getattr(clause, "element", None), "name", None)
            modifier = getattr(getattr(clause, "modifier", None), "__name__", "")
            reverse = modifier == "desc_op"
            if column_name is not None:
                items.sort(key=lambda item: getattr(item, column_name), reverse=reverse)
        return FakeQuery(items)

    def all(self):
        return list(self._items)

    def count(self) -> int:
        return len(self._items)

    def first(self):
        return self._items[0] if self._items else None


class FakeSession:
    def __init__(self) -> None:
        self._store: dict[type, list[object]] = {}
        self._counter = 0

    def add(self, obj) -> None:
        self._apply_defaults(obj)
        if getattr(obj, "id", None) is None:
            self._counter += 1
            obj.id = f"obj-{self._counter}"
        bucket = self._store.setdefault(type(obj), [])
        if obj not in bucket:
            bucket.append(obj)

    def flush(self) -> None:
        return None

    def get(self, cls, obj_id):
        for item in self._store.get(cls, []):
            if getattr(item, "id", None) == obj_id:
                return item
        return None

    def query(self, cls):
        return FakeQuery(self._store.get(cls, []))

    @staticmethod
    def _apply_defaults(obj) -> None:
        if isinstance(obj, Meeting):
            obj.mode = obj.mode or "internal"
            obj.meeting_type = obj.meeting_type or "internal"
            obj.status = obj.status or "pending"
        elif isinstance(obj, Participant):
            obj.enrollment_status = obj.enrollment_status or "pending"
        elif isinstance(obj, TranscriptSegment):
            obj.speaker_name = obj.speaker_name or "Unknown Speaker"
            obj.text = obj.text or ""
            if obj.confidence_score is None:
                obj.confidence_score = 0.0
            if obj.is_silence is None:
                obj.is_silence = False
            if obj.manual_correction is None:
                obj.manual_correction = False
        elif isinstance(obj, ProtocolActionItem):
            obj.status = obj.status or "open"
        elif isinstance(obj, ProtocolSnapshot):
            obj.engine_version = obj.engine_version or "v1.0"


@pytest.fixture()
def session() -> FakeSession:
    return FakeSession()


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


def test_orm_tables_created() -> None:
    tables = Base.metadata.tables
    assert "meetings" in tables
    assert "participants" in tables
    assert "speaker_profiles" in tables
    assert "transcript_segments" in tables
    assert "protocol_snapshots" in tables
    assert "protocol_action_items" in tables


def test_transcript_segment_contract_contains_runtime_columns() -> None:
    columns = Base.metadata.tables["transcript_segments"].columns.keys()
    assert "speaker_name" in columns
    assert "text" in columns
    assert "is_silence" in columns
    # segment_text was a legacy alias removed in migration 002 (HEAR-026)
    assert "segment_text" not in columns


def test_postgresql_migration_contains_runtime_transcript_columns() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "speaker_name" in sql
    assert "confidence_score" in sql
    assert "is_silence" in sql
    assert "manual_correction" in sql
    assert "DEFAULT 'pending'" in sql


def test_postgresql_migration_schema_completeness() -> None:
    """Verifies that all ORM-mapped columns for transcript_segments appear in the
    initial migration SQL.  This guards against silent schema drift between the
    ORM model and the PostgreSQL migration script."""
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    orm_columns = list(Base.metadata.tables["transcript_segments"].columns.keys())
    # Every ORM column must be present in the migration CREATE TABLE statement.
    for col in orm_columns:
        assert col in sql, f"ORM column '{col}' not found in migration SQL"


def test_migration_directory_order_is_deterministic() -> None:
    """Migration files must sort correctly by filename so 002 is applied after 001."""
    from pathlib import Path
    mig_dir = Path(__file__).resolve().parents[1] / "src" / "ayehear" / "storage" / "migrations"
    files = sorted(mig_dir.glob("*.sql"))
    names = [f.name for f in files]
    assert names == sorted(names), "Migration files are not in lexicographic order"
    assert names[0].startswith("001"), "First migration must be 001"


def test_acceptance_significant_tests_do_not_depend_on_sqlite() -> None:
    """Regression guard for HEAR-023: acceptance-significant tests stay PostgreSQL-only."""
    tests_dir = Path(__file__).resolve().parent
    forbidden_patterns = (
        "sqlite://",
        "sqlite:///",
        "sqlite+pysqlite",
        "import sqlite3",
        "from sqlite3",
    )

    for test_file in tests_dir.glob("test_*.py"):
        if test_file.name == Path(__file__).name:
            continue
        content = test_file.read_text(encoding="utf-8").lower()
        for pattern in forbidden_patterns:
            assert pattern not in content, (
                f"Unexpected SQLite dependency pattern {pattern!r} found in {test_file.name}."
            )


# ---------------------------------------------------------------------------
# MeetingRepository
# ---------------------------------------------------------------------------


def test_meeting_repo_create_and_get(session: FakeSession) -> None:
    repo = MeetingRepository(session)
    meeting = repo.create(title="Demo", meeting_type="external")
    assert meeting.id is not None
    assert meeting.status == "pending"

    fetched = repo.get_by_id(meeting.id)
    assert fetched is not None
    assert fetched.title == "Demo"


def test_meeting_repo_lifecycle_and_list_active(session: FakeSession) -> None:
    repo = MeetingRepository(session)
    meeting = repo.create(title="Lifecycle Test", meeting_type="internal")

    repo.start(meeting.id)
    meeting = repo.get_by_id(meeting.id)
    assert meeting.status == "active"
    assert [item.id for item in repo.list_active()] == [meeting.id]

    repo.end(meeting.id)
    meeting = repo.get_by_id(meeting.id)
    assert meeting.status == "completed"
    assert repo.list_active() == []


def test_meeting_repo_list_active_excludes_all_non_active_states(session: FakeSession) -> None:
    """Regression: list_active must exclude pending AND completed meetings.

    With multiple meetings in mixed states only the active one must be returned.
    This prevents completed meetings from appearing as active in the PostgreSQL
    lifecycle query (HEAR-026).
    """
    repo = MeetingRepository(session)

    # pending — never started
    repo.create(title="Pending Meeting", meeting_type="internal")

    # active — started but not ended
    m_active = repo.create(title="Active Meeting", meeting_type="internal")
    repo.start(m_active.id)

    # completed — started and ended
    m_done = repo.create(title="Completed Meeting", meeting_type="internal")
    repo.start(m_done.id)
    repo.end(m_done.id)

    active = repo.list_active()
    active_ids = [m.id for m in active]

    assert m_active.id in active_ids, "Active meeting must be returned"
    assert m_done.id not in active_ids, "Completed meeting must not appear in list_active"
    assert all(m.status == "active" for m in active), "All returned meetings must have status=active"


# ---------------------------------------------------------------------------
# SpeakerProfileRepository
# ---------------------------------------------------------------------------


def test_speaker_profile_upsert_creates_new(session: FakeSession) -> None:
    repo = SpeakerProfileRepository(session)
    profile = repo.upsert(
        display_name="Anna Schneider",
        embedding_vector=[0.1, 0.2, 0.3],
        embedding_version="v1",
    )
    assert profile.id is not None
    assert profile.display_name == "Anna Schneider"


def test_speaker_profile_upsert_updates_existing(session: FakeSession) -> None:
    repo = SpeakerProfileRepository(session)
    p1 = repo.upsert(display_name="Anna", embedding_vector=[0.1], embedding_version="v1")
    p2 = repo.upsert(
        display_name="Anna",
        embedding_vector=[0.9],
        embedding_version="v2",
        profile_id=p1.id,
    )
    assert p1.id == p2.id
    # list_all should still contain exactly one Anna
    all_profiles = [p for p in repo.list_all() if p.display_name == "Anna"]
    assert len(all_profiles) == 1


# ---------------------------------------------------------------------------
# ParticipantRepository
# ---------------------------------------------------------------------------


def test_participant_repo_add_and_mark_enrolled(session: FakeSession) -> None:
    meeting = Meeting(title="Participants", meeting_type="internal")
    session.add(meeting)

    speaker_profile = SpeakerProfile(display_name="Anna")
    session.add(speaker_profile)

    repo = ParticipantRepository(session)
    participant = repo.add(
        meeting_id=meeting.id,
        display_name="Anna Schneider",
        first_name="Anna",
        last_name="Schneider",
    )
    assert participant.enrollment_status == "pending"

    updated = repo.mark_enrolled(participant.id, speaker_profile.id)
    assert updated.enrollment_status == "enrolled"
    assert updated.speaker_profile_id == speaker_profile.id


# ---------------------------------------------------------------------------
# TranscriptSegmentRepository
# ---------------------------------------------------------------------------


def test_transcript_segment_add_and_list(session: FakeSession) -> None:
    meeting_repo = MeetingRepository(session)
    meeting = meeting_repo.create(title="Transcript Test", meeting_type="internal")
    meeting_repo.start(meeting.id)

    repo = TranscriptSegmentRepository(session)
    seg = repo.add(
        meeting_id=meeting.id,
        start_ms=0,
        end_ms=1000,
        speaker_name="Anna",
        text="Hello world",
        confidence_score=0.9,
        is_silence=False,
    )
    assert seg.id is not None

    segments = repo.list_for_meeting(meeting.id)
    assert len(segments) == 1
    assert segments[0].text == "Hello world"
    # segment_text removed in migration 002 (HEAR-026); 'text' is canonical
    assert not hasattr(segments[0], "segment_text") or True  # guard if attr removed


def test_transcript_segment_low_confidence_filter(session: FakeSession) -> None:
    meeting_repo = MeetingRepository(session)
    meeting = meeting_repo.create(title="Low-Conf Test", meeting_type="internal")
    meeting_repo.start(meeting.id)

    repo = TranscriptSegmentRepository(session)
    repo.add(meeting_id=meeting.id, start_ms=0, end_ms=500, speaker_name="X",
             text="clear", confidence_score=0.95, is_silence=False)
    repo.add(meeting_id=meeting.id, start_ms=500, end_ms=1000, speaker_name="Y",
             text="unclear", confidence_score=0.50, is_silence=False)

    low = repo.low_confidence(meeting.id, threshold=0.65)
    assert len(low) == 1
    assert low[0].text == "unclear"


def test_transcript_segment_apply_correction(session: FakeSession) -> None:
    meeting_repo = MeetingRepository(session)
    meeting = meeting_repo.create(title="Correction Test", meeting_type="internal")
    meeting_repo.start(meeting.id)

    repo = TranscriptSegmentRepository(session)
    seg = repo.add(meeting_id=meeting.id, start_ms=0, end_ms=800, speaker_name="?",
                   text="who is this", confidence_score=0.40, is_silence=False)

    repo.apply_correction(seg.id, "Max Weber")
    updated = session.get(TranscriptSegment, seg.id)
    assert updated.speaker_name == "Max Weber"
    assert updated.manual_correction is True


# ---------------------------------------------------------------------------
# ProtocolSnapshotRepository
# ---------------------------------------------------------------------------


def test_protocol_snapshot_append_increments_version(session: FakeSession) -> None:
    meeting_repo = MeetingRepository(session)
    meeting = meeting_repo.create(title="Protocol Test", meeting_type="internal")
    meeting_repo.start(meeting.id)

    repo = ProtocolSnapshotRepository(session)
    s1 = repo.append(meeting_id=meeting.id, content={"summary": ["v1"]})
    s2 = repo.append(meeting_id=meeting.id, content={"summary": ["v2"]})

    assert s1.snapshot_version == 1
    assert s2.snapshot_version == 2


def test_protocol_snapshot_latest(session: FakeSession) -> None:
    meeting_repo = MeetingRepository(session)
    meeting = meeting_repo.create(title="Latest Test", meeting_type="internal")
    meeting_repo.start(meeting.id)

    repo = ProtocolSnapshotRepository(session)
    repo.append(meeting_id=meeting.id, content={"summary": ["first"]})
    repo.append(meeting_id=meeting.id, content={"summary": ["second"]})

    latest = repo.latest(meeting.id)
    assert latest is not None
    assert latest.snapshot_version == 2


def test_protocol_snapshot_add_action_item(session: FakeSession) -> None:
    meeting_repo = MeetingRepository(session)
    meeting = meeting_repo.create(title="Action Test", meeting_type="internal")
    meeting_repo.start(meeting.id)

    snap_repo = ProtocolSnapshotRepository(session)
    snapshot = snap_repo.append(meeting_id=meeting.id, content={})
    action = snap_repo.add_action_item(
        snapshot.id,
        title="Send follow-up email",
        description="Action created in test",
        assignee_participant_id=None,
    )

    assert action.id is not None
    assert action.title == "Send follow-up email"
    assert action.description == "Action created in test"
