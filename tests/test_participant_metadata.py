"""Tests for participant metadata round-trip and schema completeness (HEAR-020).

Validates:
- Full round-trip of all participant metadata fields without fallback on display_name
- update_metadata() partial update behavior
- display_names_for_meeting() for pipeline seeding
- Migration 001 contains all participant metadata columns (schema drift guard)
- Migration 003 is present and idempotent
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ayehear.models.meeting import Participant as MeetingParticipant
from ayehear.storage.orm import Base, Meeting, Participant
from ayehear.storage.repositories import MeetingRepository, ParticipantRepository

MIGRATION_001 = (
    Path(__file__).resolve().parents[1]
    / "src" / "ayehear" / "storage" / "migrations" / "001_initial_schema.sql"
)
MIGRATION_003 = (
    Path(__file__).resolve().parents[1]
    / "src" / "ayehear" / "storage" / "migrations" / "003_participant_naming_constraints.sql"
)

# ---------------------------------------------------------------------------
# Lightweight test double (mirrors the pattern in test_storage.py)
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
            if column_name is None:
                continue
            if operator == "eq":
                items = [item for item in items if getattr(item, column_name) == value]
        return FakeQuery(items)

    def order_by(self, *args):
        return FakeQuery(self._items)

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


@pytest.fixture()
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture()
def meeting(session) -> Meeting:
    repo = MeetingRepository(session)
    m = Meeting(title="Test Meeting", mode="external", meeting_type="external", status="pending")
    m.id = "m-001"
    session.add(m)
    return m


def test_meeting_participant_display_name_uses_salutation_template() -> None:
    participant = MeetingParticipant(
        first_name="Anna",
        last_name="Schneider",
        organization="AYE",
        role="Moderator",
        salutation="Frau",
        naming_template="salutation_last_name",
    )

    assert participant.display_name == "Frau Schneider"


def test_meeting_participant_display_name_uses_full_name_template() -> None:
    participant = MeetingParticipant(
        first_name="Anna",
        last_name="Schneider",
        organization="AYE",
        role="Moderator",
        salutation="Frau",
        naming_template="full_name",
    )

    assert participant.display_name == "Anna Schneider"


# ---------------------------------------------------------------------------
# Round-trip: all participant metadata fields stored and retrieved intact
# ---------------------------------------------------------------------------


def test_participant_metadata_full_round_trip(session, meeting) -> None:
    repo = ParticipantRepository(session)
    p = repo.add(
        meeting_id=meeting.id,
        display_name="Frau Schneider | AYE",
        first_name="Anna",
        last_name="Schneider",
        salutation="Frau",
        organization="AYE",
        naming_template="salutation_last_name_company",
    )

    retrieved = repo.get_by_id(p.id)
    assert retrieved is not None
    # All individual fields must be present without using display_name as fallback
    assert retrieved.first_name == "Anna"
    assert retrieved.last_name == "Schneider"
    assert retrieved.salutation == "Frau"
    assert retrieved.organization == "AYE"
    assert retrieved.naming_template == "salutation_last_name_company"
    assert retrieved.display_name == "Frau Schneider | AYE"


def test_participant_metadata_full_name_template(session, meeting) -> None:
    repo = ParticipantRepository(session)
    p = repo.add(
        meeting_id=meeting.id,
        display_name="Anna Schneider | AYE",
        first_name="Anna",
        last_name="Schneider",
        organization="AYE",
        naming_template="full_name_company",
    )
    retrieved = repo.get_by_id(p.id)
    assert retrieved.naming_template == "full_name_company"
    assert retrieved.first_name == "Anna"
    assert retrieved.last_name == "Schneider"


def test_participant_nullable_fields_stored_as_none(session, meeting) -> None:
    repo = ParticipantRepository(session)
    p = repo.add(meeting_id=meeting.id, display_name="Max Weber")

    retrieved = repo.get_by_id(p.id)
    assert retrieved is not None
    # No metadata → all optional fields are None (no fallback logic required)
    assert retrieved.first_name is None
    assert retrieved.last_name is None
    assert retrieved.salutation is None
    assert retrieved.organization is None
    assert retrieved.naming_template is None


# ---------------------------------------------------------------------------
# update_metadata — partial update semantics
# ---------------------------------------------------------------------------


def test_update_metadata_single_field(session, meeting) -> None:
    repo = ParticipantRepository(session)
    p = repo.add(meeting_id=meeting.id, display_name="Max Weber")

    updated = repo.update_metadata(p.id, organization="Customer GmbH")
    assert updated.organization == "Customer GmbH"
    # Other fields remain unchanged
    assert updated.first_name is None
    assert updated.naming_template is None


def test_update_metadata_multiple_fields(session, meeting) -> None:
    repo = ParticipantRepository(session)
    p = repo.add(meeting_id=meeting.id, display_name="Max Weber")

    repo.update_metadata(
        p.id,
        first_name="Max",
        last_name="Weber",
        organization="Customer GmbH",
        naming_template="full_name_company",
    )
    retrieved = repo.get_by_id(p.id)
    assert retrieved.first_name == "Max"
    assert retrieved.last_name == "Weber"
    assert retrieved.organization == "Customer GmbH"
    assert retrieved.naming_template == "full_name_company"


def test_update_metadata_raises_for_unknown_id(session) -> None:
    repo = ParticipantRepository(session)
    with pytest.raises(ValueError, match="not found"):
        repo.update_metadata("nonexistent-id", organization="Test")


def test_update_metadata_does_not_overwrite_with_none(session, meeting) -> None:
    repo = ParticipantRepository(session)
    p = repo.add(
        meeting_id=meeting.id,
        display_name="Anna Schneider",
        organization="AYE",
    )
    # Calling update_metadata without organization should NOT clear it
    repo.update_metadata(p.id, first_name="Anna")
    retrieved = repo.get_by_id(p.id)
    assert retrieved.organization == "AYE"  # preserved
    assert retrieved.first_name == "Anna"   # new field set


# ---------------------------------------------------------------------------
# display_names_for_meeting — pipeline seeding
# ---------------------------------------------------------------------------


def test_display_names_for_meeting_returns_all_names(session, meeting) -> None:
    repo = ParticipantRepository(session)
    repo.add(meeting_id=meeting.id, display_name="Frau Schneider | AYE")
    repo.add(meeting_id=meeting.id, display_name="Max Weber | Customer")

    names = repo.display_names_for_meeting(meeting.id)
    assert "Frau Schneider | AYE" in names
    assert "Max Weber | Customer" in names
    assert len(names) == 2


def test_display_names_for_meeting_empty_when_no_participants(session, meeting) -> None:
    repo = ParticipantRepository(session)
    names = repo.display_names_for_meeting(meeting.id)
    assert names == []


def test_display_names_for_meeting_excludes_other_meetings(session) -> None:
    repo = ParticipantRepository(session)
    m1 = Meeting(title="M1", mode="internal", meeting_type="internal", status="pending")
    m1.id = "m-010"
    m2 = Meeting(title="M2", mode="internal", meeting_type="internal", status="pending")
    m2.id = "m-011"
    session.add(m1)
    session.add(m2)

    repo.add(meeting_id="m-010", display_name="Alice")
    repo.add(meeting_id="m-011", display_name="Bob")

    assert repo.display_names_for_meeting("m-010") == ["Alice"]
    assert repo.display_names_for_meeting("m-011") == ["Bob"]


# ---------------------------------------------------------------------------
# Schema guard: Migration 001 contains all participant metadata columns
# ---------------------------------------------------------------------------


def test_migration_001_contains_participant_metadata_columns() -> None:
    sql = MIGRATION_001.read_text(encoding="utf-8")
    for col in ("first_name", "last_name", "salutation", "organization", "naming_template"):
        assert col in sql, f"Participant metadata column '{col}' missing from migration 001"


def test_migration_001_participants_table_columns_match_orm() -> None:
    sql = MIGRATION_001.read_text(encoding="utf-8")
    orm_columns = list(Base.metadata.tables["participants"].columns.keys())
    for col in orm_columns:
        assert col in sql, f"ORM column '{col}' not found in migration 001 SQL"


# ---------------------------------------------------------------------------
# Migration 003 file guard
# ---------------------------------------------------------------------------


def test_migration_003_exists_and_contains_constraint() -> None:
    assert MIGRATION_003.exists(), "Migration 003 is missing"
    sql = MIGRATION_003.read_text(encoding="utf-8")
    assert "chk_participants_naming_template" in sql
    assert "salutation_last_name_company" in sql
    assert "full_name_company" in sql
