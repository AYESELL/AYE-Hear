"""Tests for HEAR-106: Confidence Review Workflow (V2-12).

Verifies:
- Queue build from snapshot content and transcript signals
- Severity ranking (HIGH before MEDIUM before LOW)
- All four review reasons are detectable
- apply_action: ACCEPT, EDIT, DISMISS
- EDIT requires edited_text
- effective_text reflects edit decision
- Dismissed items excluded from final items
- Persistence: save → load preserves full state
- accept_all marks all pending items accepted
- pending_count
- get_final_items filters by item_type
- Empty signals produce no flagged items
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ayehear.services.confidence_review import (
    ConfidenceReviewQueue,
    ItemType,
    ReviewAction,
    ReviewReason,
    ReviewSeverity,
    TranscriptSignals,
    _severity,
)
from ayehear.utils.paths import reviews_dir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SNAPSHOT_CONTENT = {
    "decisions": ["We decided to adopt the new CI pipeline."],
    "action_items": ["Alice will create the migration script by Friday."],
    "open_questions": ["Who owns the rollback plan?"],
}

SNAPSHOT_ID = "snap-001"
MEETING_ID = "meet-abc"


def _signals_fallback() -> TranscriptSignals:
    return TranscriptSignals(fallback_used=True, min_confidence=0.8, avg_confidence=0.85)


def _signals_low_speaker() -> TranscriptSignals:
    return TranscriptSignals(min_confidence=0.3, avg_confidence=0.75)


def _signals_unresolved() -> TranscriptSignals:
    return TranscriptSignals(has_unresolved_speakers=True, avg_confidence=0.9, min_confidence=0.9)


def _signals_clean() -> TranscriptSignals:
    return TranscriptSignals(min_confidence=0.95, avg_confidence=0.97)


# ---------------------------------------------------------------------------
# Queue building
# ---------------------------------------------------------------------------

class TestQueueBuild:
    def test_fallback_produces_items(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        assert len(q.items) > 0

    def test_clean_signals_produce_no_items(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_clean()
        )
        assert len(q.items) == 0

    def test_items_contain_all_content_types(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        types = {i.item_type for i in q.items}
        assert ItemType.DECISION in types
        assert ItemType.ACTION_ITEM in types
        assert ItemType.OPEN_QUESTION in types

    def test_fallback_reason_present(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        for item in q.items:
            assert ReviewReason.FALLBACK_PATH in item.reasons

    def test_unresolved_speaker_reason(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_unresolved()
        )
        reasons = {r for i in q.items for r in i.reasons}
        assert ReviewReason.UNRESOLVED_SPEAKER in reasons

    def test_low_speaker_confidence_reason(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_low_speaker()
        )
        reasons = {r for i in q.items for r in i.reasons}
        assert ReviewReason.LOW_SPEAKER_CONFIDENCE in reasons


# ---------------------------------------------------------------------------
# Severity ranking
# ---------------------------------------------------------------------------

class TestSeverityRanking:
    def test_high_comes_before_medium(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        if len(q.items) >= 2:
            for i in range(len(q.items) - 1):
                assert (
                    _severity(q.items[i].reasons) <= _severity(q.items[i + 1].reasons)
                    or q.items[i].severity == q.items[i + 1].severity
                )

    def test_fallback_gives_high_severity(self) -> None:
        reasons = [ReviewReason.FALLBACK_PATH]
        assert _severity(reasons) == ReviewSeverity.HIGH

    def test_unresolved_speaker_gives_high_severity(self) -> None:
        reasons = [ReviewReason.UNRESOLVED_SPEAKER]
        assert _severity(reasons) == ReviewSeverity.HIGH

    def test_conflicting_extraction_gives_medium(self) -> None:
        reasons = [ReviewReason.CONFLICTING_EXTRACTION]
        assert _severity(reasons) == ReviewSeverity.MEDIUM

    def test_low_transcript_confidence_gives_medium(self) -> None:
        reasons = [ReviewReason.LOW_TRANSCRIPT_CONFIDENCE]
        assert _severity(reasons) == ReviewSeverity.MEDIUM


# ---------------------------------------------------------------------------
# Review actions
# ---------------------------------------------------------------------------

class TestReviewActions:
    def _queue_with_items(self) -> ConfidenceReviewQueue:
        return ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )

    def test_accept_action_marks_reviewed(self) -> None:
        q = self._queue_with_items()
        item = q.items[0]
        q.apply_action(item.item_id, ReviewAction.ACCEPT)
        assert q._find(item.item_id).action == ReviewAction.ACCEPT
        assert q._find(item.item_id).is_reviewed()

    def test_edit_action_stores_edited_text(self) -> None:
        q = self._queue_with_items()
        item = q.items[0]
        q.apply_action(item.item_id, ReviewAction.EDIT, edited_text="Revised text here.")
        found = q._find(item.item_id)
        assert found.action == ReviewAction.EDIT
        assert found.edited_text == "Revised text here."
        assert found.effective_text() == "Revised text here."

    def test_edit_without_text_raises(self) -> None:
        q = self._queue_with_items()
        item = q.items[0]
        with pytest.raises(ValueError, match="edited_text is required"):
            q.apply_action(item.item_id, ReviewAction.EDIT)

    def test_dismiss_action(self) -> None:
        q = self._queue_with_items()
        item = q.items[0]
        q.apply_action(item.item_id, ReviewAction.DISMISS)
        assert q._find(item.item_id).is_dismissed()

    def test_accept_does_not_change_text(self) -> None:
        q = self._queue_with_items()
        item = q.items[0]
        original = item.item_text
        q.apply_action(item.item_id, ReviewAction.ACCEPT)
        assert q._find(item.item_id).effective_text() == original

    def test_unknown_item_id_raises(self) -> None:
        q = self._queue_with_items()
        with pytest.raises(ValueError, match="not found"):
            q.apply_action("nonexistent-id", ReviewAction.ACCEPT)


# ---------------------------------------------------------------------------
# pending_count / accept_all
# ---------------------------------------------------------------------------

class TestPendingCount:
    def test_initial_all_pending(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        assert q.pending_count == len(q.items)

    def test_accept_all_clears_pending(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        q.accept_all()
        assert q.pending_count == 0

    def test_partial_review_reduces_count(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        if q.items:
            q.apply_action(q.items[0].item_id, ReviewAction.ACCEPT)
            assert q.pending_count == len(q.items) - 1


# ---------------------------------------------------------------------------
# get_final_items
# ---------------------------------------------------------------------------

class TestGetFinalItems:
    def test_dismissed_excluded(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        action_items = [i for i in q.items if i.item_type == ItemType.ACTION_ITEM]
        for ai in action_items:
            q.apply_action(ai.item_id, ReviewAction.DISMISS)
        assert q.get_final_items(ItemType.ACTION_ITEM) == []

    def test_edited_text_returned(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        decisions = [i for i in q.items if i.item_type == ItemType.DECISION]
        if decisions:
            q.apply_action(decisions[0].item_id, ReviewAction.EDIT, edited_text="Edited decision.")
            finals = q.get_final_items(ItemType.DECISION)
            assert "Edited decision." in finals

    def test_pending_items_included_with_original_text(self) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        for item_type in ItemType:
            for final in q.get_final_items(item_type):
                assert isinstance(final, str)

    def test_clean_signals_return_all_snapshot_items(self) -> None:
        """No uncertainty → queue empty, but get_final_items must still return snapshot content (Finding #1)."""
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_clean()
        )
        assert len(q.items) == 0
        assert q.get_final_items(ItemType.DECISION) == SNAPSHOT_CONTENT["decisions"]
        assert q.get_final_items(ItemType.ACTION_ITEM) == SNAPSHOT_CONTENT["action_items"]
        assert q.get_final_items(ItemType.OPEN_QUESTION) == SNAPSHOT_CONTENT["open_questions"]


# ---------------------------------------------------------------------------
# Persistence (save / load)
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        q.save(Path("queue.json"), install_root=tmp_path)
        assert (reviews_dir(tmp_path) / "queue.json").exists()

    def test_load_restores_items(self, tmp_path: Path) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        if q.items:
            q.apply_action(q.items[0].item_id, ReviewAction.ACCEPT)
        p = Path("queue.json")
        q.save(p, install_root=tmp_path)

        restored = ConfidenceReviewQueue.load(p, install_root=tmp_path)
        assert restored.meeting_id == MEETING_ID
        assert restored.snapshot_id == SNAPSHOT_ID
        assert len(restored.items) == len(q.items)

    def test_load_preserves_review_actions(self, tmp_path: Path) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        if not q.items:
            pytest.skip("No flagged items with given signals")
        item_id = q.items[0].item_id
        q.apply_action(item_id, ReviewAction.EDIT, edited_text="Persisted edit.")
        p = Path("queue.json")
        q.save(p, install_root=tmp_path)

        restored = ConfidenceReviewQueue.load(p, install_root=tmp_path)
        found = restored._find(item_id)
        assert found.action == ReviewAction.EDIT
        assert found.edited_text == "Persisted edit."

    def test_load_preserves_severity(self, tmp_path: Path) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        p = Path("queue.json")
        q.save(p, install_root=tmp_path)
        restored = ConfidenceReviewQueue.load(p, install_root=tmp_path)
        for orig, rest in zip(q.items, restored.items):
            assert orig.severity == rest.severity

    def test_get_final_items_after_load_clean_signals(self, tmp_path: Path) -> None:
        """After save/load with clean signals, get_final_items must restore snapshot items (Finding #1)."""
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_clean()
        )
        p = Path("queue_clean.json")
        q.save(p, install_root=tmp_path)
        restored = ConfidenceReviewQueue.load(p, install_root=tmp_path)
        assert restored.get_final_items(ItemType.DECISION) == SNAPSHOT_CONTENT["decisions"]
        assert restored.get_final_items(ItemType.ACTION_ITEM) == SNAPSHOT_CONTENT["action_items"]

    def test_save_rejects_export_boundary(self, tmp_path: Path) -> None:
        q = ConfidenceReviewQueue.build(
            MEETING_ID, SNAPSHOT_ID, SNAPSHOT_CONTENT, _signals_fallback()
        )
        forbidden = tmp_path / "exports" / "queue.json"
        with pytest.raises(ValueError, match="runtime/reviews"):
            q.save(forbidden, install_root=tmp_path)

    def test_load_rejects_outside_runtime_reviews(self, tmp_path: Path) -> None:
        forbidden = tmp_path / "exports" / "queue.json"
        forbidden.parent.mkdir(parents=True, exist_ok=True)
        forbidden.write_text(json.dumps({}), encoding="utf-8")
        with pytest.raises(ValueError, match="runtime/reviews"):
            ConfidenceReviewQueue.load(forbidden, install_root=tmp_path)


# ---------------------------------------------------------------------------
# build_signals from raw segment dicts
# ---------------------------------------------------------------------------

class TestBuildSignals:
    def test_fallback_signal_from_diagnostics(self) -> None:
        diagnostics = {"fallback_used": True, "status": "rule_based_fallback"}
        signals = ConfidenceReviewQueue.build_signals([], diagnostics)
        assert signals.fallback_used is True

    def test_unresolved_speaker_detected(self) -> None:
        segments = [
            {"confidence_score": 0.9, "speaker_name": "Unknown Speaker", "manual_correction": False}
        ]
        signals = ConfidenceReviewQueue.build_signals(segments)
        assert signals.has_unresolved_speakers is True

    def test_min_confidence_computed(self) -> None:
        segments = [
            {"confidence_score": 0.9, "speaker_name": "Alice", "manual_correction": False},
            {"confidence_score": 0.3, "speaker_name": "Bob", "manual_correction": False},
        ]
        signals = ConfidenceReviewQueue.build_signals(segments)
        assert signals.min_confidence == pytest.approx(0.3)

    def test_conflicting_segments_counted(self) -> None:
        segments = [
            {"confidence_score": 0.2, "speaker_name": "Alice", "manual_correction": True},
        ]
        signals = ConfidenceReviewQueue.build_signals(segments)
        assert signals.conflicting_segments == 1

    def test_empty_segments_return_defaults(self) -> None:
        signals = ConfidenceReviewQueue.build_signals([])
        assert signals.min_confidence == 1.0
        assert signals.fallback_used is False
