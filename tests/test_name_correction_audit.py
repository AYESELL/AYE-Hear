"""Tests for transcript correction persistence and audit trail (HEAR-022).

Validates:
- apply_correction() creates an audit log entry before mutating the segment
- apply_correction() updates speaker_name and sets manual_correction=True
- apply_correction() optionally links the correct participant_id
- Repeated corrections each produce a new log entry (full history preserved)
- correction_history() returns all entries oldest-first
- list_for_protocol() returns non-silence segments in chronological order
- Protocol engine uses reviewed (corrected) speaker names
- manual_correction flag semantics remain intact (ADR-0007)
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ayehear.storage.orm import (
    Meeting,
    Participant,
    TranscriptCorrectionLog,
    TranscriptSegment,
)
from ayehear.storage.repositories import (
    MeetingRepository,
    TranscriptSegmentRepository,
)
from ayehear.services.protocol_engine import ProtocolEngine

MIGRATION_004 = (
    Path(__file__).resolve().parents[1]
    / "src" / "ayehear" / "storage" / "migrations" / "004_transcript_correction_log.sql"
)

# ---------------------------------------------------------------------------
# Lightweight test doubles
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
                items = [item for item in items if getattr(item, column_name, None) == value]
            elif operator == "is_":
                # Treat is_(False) as == False
                if value is None:
                    value = False
                items = [item for item in items if getattr(item, column_name, None) == value]
        return FakeQuery(items)

    def order_by(self, *args):
        items = list(self._items)
        if args:
            clause = args[0]
            # Handle UnaryExpression (col.asc()/col.desc()) and bare Column usage
            col = (
                getattr(getattr(clause, "element", None), "name", None)
                or getattr(clause, "key", None)
                or getattr(clause, "name", None)
            )
            modifier = getattr(getattr(clause, "modifier", None), "__name__", "")
            reverse = modifier == "desc_op"
            if col:
                items.sort(
                    key=lambda o: (getattr(o, col) is None, getattr(o, col, None)),
                    reverse=reverse,
                )
        return FakeQuery(items)

    def all(self) -> list:
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
        cls = type(obj)
        if getattr(obj, "id", None) is None:
            self._counter += 1
            obj.id = f"obj-{self._counter}"
        # apply ORM-level defaults
        if isinstance(obj, TranscriptSegment):
            obj.speaker_name = getattr(obj, "speaker_name", None) or "Unknown Speaker"
            obj.text = getattr(obj, "text", None) or ""
            if obj.confidence_score is None:
                obj.confidence_score = 0.0
            if obj.is_silence is None:
                obj.is_silence = False
            if obj.manual_correction is None:
                obj.manual_correction = False
        bucket = self._store.setdefault(cls, [])
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


def _make_segment(session: FakeSession, meeting_id: str = "m-001") -> TranscriptSegment:
    seg = TranscriptSegment(
        meeting_id=meeting_id,
        start_ms=0,
        end_ms=1000,
        speaker_name="Unknown Speaker",
        text="Guten Morgen.",
        confidence_score=0.45,
        is_silence=False,
        manual_correction=False,
    )
    session.add(seg)
    return seg


# ---------------------------------------------------------------------------
# apply_correction — core semantics
# ---------------------------------------------------------------------------


def test_apply_correction_updates_speaker_name(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)

    repo.apply_correction(seg.id, "Frau Schneider")

    assert seg.speaker_name == "Frau Schneider"


def test_apply_correction_sets_manual_correction_true(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)
    assert seg.manual_correction is False

    repo.apply_correction(seg.id, "Max Weber")

    assert seg.manual_correction is True


def test_apply_correction_updates_participant_id_when_provided(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)
    assert seg.participant_id is None

    repo.apply_correction(seg.id, "Frau Schneider", participant_id="p-001")

    assert seg.participant_id == "p-001"


def test_apply_correction_leaves_participant_id_unchanged_when_not_provided(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)
    seg.participant_id = "p-existing"

    repo.apply_correction(seg.id, "Max Weber")

    assert seg.participant_id == "p-existing"  # unchanged


def test_apply_correction_raises_for_unknown_segment(session) -> None:
    repo = TranscriptSegmentRepository(session)
    with pytest.raises(ValueError, match="not found"):
        repo.apply_correction("nonexistent-id", "Anna")


# ---------------------------------------------------------------------------
# apply_correction — audit log creation
# ---------------------------------------------------------------------------


def test_apply_correction_creates_log_entry(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)

    repo.apply_correction(seg.id, "Frau Schneider")

    logs = session.query(TranscriptCorrectionLog).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.transcript_segment_id == seg.id
    assert log.previous_speaker_name == "Unknown Speaker"
    assert log.corrected_speaker_name == "Frau Schneider"


def test_apply_correction_log_captures_previous_participant_id(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)
    seg.participant_id = "p-before"

    repo.apply_correction(seg.id, "Frau Schneider", participant_id="p-after")

    logs = session.query(TranscriptCorrectionLog).all()
    assert logs[0].previous_participant_id == "p-before"
    assert logs[0].corrected_participant_id == "p-after"


def test_apply_correction_log_participant_id_nullable_when_not_provided(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)

    repo.apply_correction(seg.id, "Max Weber")

    log = session.query(TranscriptCorrectionLog).all()[0]
    assert log.corrected_participant_id is None


# ---------------------------------------------------------------------------
# correction_history — multiple corrections
# ---------------------------------------------------------------------------


def test_correction_history_returns_all_entries(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)

    repo.apply_correction(seg.id, "Frau Schneider")
    repo.apply_correction(seg.id, "Anna Schneider")  # reviewer changes again

    history = repo.correction_history(seg.id)
    assert len(history) == 2
    assert history[0].corrected_speaker_name == "Frau Schneider"
    assert history[1].corrected_speaker_name == "Anna Schneider"


def test_correction_history_empty_for_uncorrected_segment(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)

    history = repo.correction_history(seg.id)
    assert history == []


def test_correction_history_preserves_before_state_across_chained_corrections(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)  # speaker_name = "Unknown Speaker"

    repo.apply_correction(seg.id, "Frau Schneider")  # first correction
    # After first correction, seg.speaker_name == "Frau Schneider"
    repo.apply_correction(seg.id, "Anna Schneider")  # second correction

    history = repo.correction_history(seg.id)
    # First log entry must have captured "Unknown Speaker" as the before-state
    assert history[0].previous_speaker_name == "Unknown Speaker"
    # Second log entry must capture the intermediate name "Frau Schneider"
    assert history[1].previous_speaker_name == "Frau Schneider"


# ---------------------------------------------------------------------------
# list_for_protocol — reviewed state preference
# ---------------------------------------------------------------------------


def test_list_for_protocol_excludes_silence(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg_speech = TranscriptSegment(
        meeting_id="m-001", start_ms=0, end_ms=1000,
        speaker_name="Anna", text="Hallo.", confidence_score=0.9,
        is_silence=False, manual_correction=False,
    )
    seg_silence = TranscriptSegment(
        meeting_id="m-001", start_ms=1000, end_ms=2000,
        speaker_name="Unknown Speaker", text="",
        confidence_score=0.0, is_silence=True, manual_correction=False,
    )
    session.add(seg_speech)
    session.add(seg_silence)

    results = repo.list_for_protocol("m-001")
    assert len(results) == 1
    assert results[0].speaker_name == "Anna"


def test_list_for_protocol_reflects_corrected_speaker_name(session) -> None:
    repo = TranscriptSegmentRepository(session)
    seg = _make_segment(session)  # speaker_name="Unknown Speaker"

    repo.apply_correction(seg.id, "Max Weber")
    results = repo.list_for_protocol("m-001")

    assert results[0].speaker_name == "Max Weber"
    assert results[0].manual_correction is True


def test_list_for_protocol_orders_by_start_ms(session) -> None:
    repo = TranscriptSegmentRepository(session)
    for ms in (2000, 0, 1000):
        seg = TranscriptSegment(
            meeting_id="m-001", start_ms=ms, end_ms=ms + 500,
            speaker_name="Anna", text="Text.", confidence_score=0.9,
            is_silence=False, manual_correction=False,
        )
        session.add(seg)

    results = repo.list_for_protocol("m-001")
    assert [s.start_ms for s in results] == [0, 1000, 2000]


# ---------------------------------------------------------------------------
# Protocol engine uses reviewed state
# ---------------------------------------------------------------------------


def test_protocol_engine_generates_from_corrected_transcript() -> None:
    """ProtocolEngine.generate() must use corrected speaker names from list_for_protocol."""
    mock_transcript_repo = MagicMock()

    corrected_seg = MagicMock()
    corrected_seg.start_ms = 0
    corrected_seg.speaker_name = "Frau Schneider"
    corrected_seg.text = "Wir entscheiden uns für Option A."
    corrected_seg.is_silence = False
    corrected_seg.manual_correction = True

    # The repo exposes list_for_protocol() for protocol generation
    mock_transcript_repo.list_for_protocol.return_value = [corrected_seg]

    mock_snapshot_row = MagicMock()
    mock_snapshot_row.id = "snap-1"
    mock_snapshot_row.snapshot_version = 1

    mock_snapshot_repo = MagicMock()
    mock_snapshot_repo.append.return_value = mock_snapshot_row

    engine = ProtocolEngine(
        snapshot_repo=mock_snapshot_repo,
        transcript_repo=mock_transcript_repo,
    )
    snapshot = engine.generate("m-001")

    # Verify that list_for_protocol was called (not list_for_meeting)
    mock_transcript_repo.list_for_protocol.assert_called_once_with("m-001")

    # The decision from the corrected speaker should appear in the snapshot content
    call_kwargs = mock_snapshot_repo.append.call_args
    assert call_kwargs is not None
    content = call_kwargs.kwargs.get("content") or call_kwargs.args[1] if call_kwargs.args else {}
    if not content:
        # Try positional or keyword fallback
        all_args = call_kwargs.kwargs
        content = all_args.get("content", {})
    decisions = content.get("decisions", [])
    assert any("Option A" in d for d in decisions)


# ---------------------------------------------------------------------------
# Migration 004 file guard
# ---------------------------------------------------------------------------


def test_migration_004_exists() -> None:
    assert MIGRATION_004.exists(), "Migration 004 is missing"


def test_migration_004_contains_correction_log_table() -> None:
    sql = MIGRATION_004.read_text(encoding="utf-8")
    assert "transcript_correction_log" in sql
    assert "previous_speaker_name" in sql
    assert "corrected_speaker_name" in sql
    assert "previous_participant_id" in sql
    assert "corrected_participant_id" in sql


def test_migration_004_index_present() -> None:
    sql = MIGRATION_004.read_text(encoding="utf-8")
    assert "idx_correction_log_segment_id" in sql
