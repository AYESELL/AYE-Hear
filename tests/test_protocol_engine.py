"""Tests for ProtocolEngine — snapshot generation and rule-based extraction (HEAR-015)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ayehear.services.protocol_engine import ProtocolEngine, ProtocolContent


# ---------------------------------------------------------------------------
# summarize_window — rule-based extraction (no repo, no LLM)
# ---------------------------------------------------------------------------


def test_summarize_empty_window_returns_no_items() -> None:
    engine = ProtocolEngine()
    result = engine.summarize_window([])
    assert result["decisions"] == []
    assert result["action_items"] == []
    assert result["open_questions"] == []
    assert len(result["summary"]) >= 1


def test_summarize_window_detects_decision() -> None:
    engine = ProtocolEngine()
    result = engine.summarize_window([
        "Anna: Wir entscheiden uns fuer Option A.",
        "Max: Alles klar.",
    ])
    assert any("Option A" in d for d in result["decisions"])


def test_summarize_window_detects_action_item() -> None:
    engine = ProtocolEngine()
    result = engine.summarize_window([
        "Anna: Bitte sende das Protokoll bis Freitag.",
    ])
    assert len(result["action_items"]) >= 1


def test_summarize_window_detects_open_question() -> None:
    engine = ProtocolEngine()
    result = engine.summarize_window([
        "Max: Wann ist der naechste Termin?",
    ])
    assert len(result["open_questions"]) >= 1


def test_summarize_window_summary_contains_segment_count() -> None:
    engine = ProtocolEngine()
    lines = ["Anna: Test one.", "Max: Test two.", "Anna: Test three."]
    result = engine.summarize_window(lines)
    assert "3" in result["summary"][0] or "three" in result["summary"][0].lower()


# ---------------------------------------------------------------------------
# generate — stub path (no repositories)
# ---------------------------------------------------------------------------


def test_generate_without_repo_returns_version_1() -> None:
    engine = ProtocolEngine()
    snapshot = engine.generate("m-001")
    assert snapshot.meeting_id == "m-001"
    assert snapshot.version == 1
    assert snapshot.snapshot_id is None


# ---------------------------------------------------------------------------
# generate — with mocked repositories
# ---------------------------------------------------------------------------


def test_generate_calls_snapshot_append() -> None:
    mock_transcript_repo = MagicMock()
    mock_transcript_repo.list_for_meeting.return_value = []

    mock_snapshot_row = MagicMock()
    mock_snapshot_row.id = "snap-1"
    mock_snapshot_row.snapshot_version = 1

    mock_snapshot_repo = MagicMock()
    mock_snapshot_repo.append.return_value = mock_snapshot_row
    mock_snapshot_repo.add_action_item.return_value = MagicMock()

    engine = ProtocolEngine(
        snapshot_repo=mock_snapshot_repo,
        transcript_repo=mock_transcript_repo,
    )
    snapshot = engine.generate("m-002")

    mock_snapshot_repo.append.assert_called_once()
    assert snapshot.snapshot_id == "snap-1"
    assert snapshot.version == 1


def test_generate_persists_action_items() -> None:
    mock_transcript_repo = MagicMock()
    seg = MagicMock()
    seg.start_ms = 0
    seg.speaker_name = "Anna"
    seg.text = "Bitte sende das Follow-up."
    seg.is_silence = False
    mock_transcript_repo.list_for_meeting.return_value = [seg]

    mock_snapshot_row = MagicMock()
    mock_snapshot_row.id = "snap-2"
    mock_snapshot_row.snapshot_version = 2

    mock_snapshot_repo = MagicMock()
    mock_snapshot_repo.append.return_value = mock_snapshot_row

    engine = ProtocolEngine(
        snapshot_repo=mock_snapshot_repo,
        transcript_repo=mock_transcript_repo,
    )
    engine.generate("m-003")

    # Action item was extracted from 'Bitte sende…' and add_action_item called
    mock_snapshot_repo.add_action_item.assert_called()


# ---------------------------------------------------------------------------
# _extract_rule_based — keyword coverage
# ---------------------------------------------------------------------------


def test_rule_based_all_empty_for_neutral_transcript() -> None:
    engine = ProtocolEngine()
    content = engine._extract_rule_based([
        "[0ms] Anna: Guten Morgen.",
        "[500ms] Max: Wie geht es dir?",
    ])
    # "Wie geht es dir?" has a '?' so should be in open_questions
    assert any("?" in q for q in content.open_questions)


def test_rule_based_no_duplicate_classification() -> None:
    engine = ProtocolEngine()
    lines = ["[0ms] Anna: Bitte bereite die Agenda vor."]
    content = engine._extract_rule_based(lines)
    # Should appear only in action_items, not in decisions
    assert len(content.action_items) == 1
    assert len(content.decisions) == 0
