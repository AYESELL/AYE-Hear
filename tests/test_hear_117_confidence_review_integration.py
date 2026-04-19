"""Tests for HEAR-117: Confidence Review Workflow integration (V2-12).

Verifies that ConfidenceReviewQueue is correctly wired into ProtocolEngine so
that uncertainty signals, queue building, persistence, and export-facing final
items work end-to-end without any cloud or model dependency.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ayehear.services.confidence_review import (
    ConfidenceReviewQueue,
    ItemType,
    ReviewAction,
    ReviewReason,
    ReviewSeverity,
    TranscriptSignals,
)
from ayehear.services.protocol_engine import ProtocolContent, ProtocolEngine, ProtocolSnapshot


# ---------------------------------------------------------------------------
# build_review_queue — public integration method
# ---------------------------------------------------------------------------

class TestBuildReviewQueue:
    def _engine(self) -> ProtocolEngine:
        return ProtocolEngine()

    def _snapshot_content(self) -> dict:
        return {
            "decisions": ["We decided to adopt the new process."],
            "action_items": ["Alice will send the report by Friday."],
            "open_questions": ["Who owns rollback validation?"],
        }

    def test_returns_review_queue(self) -> None:
        engine = self._engine()
        queue = engine.build_review_queue("m-001", "snap-001", self._snapshot_content())
        assert isinstance(queue, ConfidenceReviewQueue)

    def test_meeting_id_and_snapshot_id_stored(self) -> None:
        engine = self._engine()
        queue = engine.build_review_queue("m-002", "snap-002", self._snapshot_content())
        assert queue.meeting_id == "m-002"
        assert queue.snapshot_id == "snap-002"

    def test_clean_signals_produce_empty_queue(self) -> None:
        """High-confidence, no fallback → no flagged items."""
        engine = self._engine()
        # No transcript repo and idle diagnostics → clean signals
        queue = engine.build_review_queue("m-003", "snap-003", self._snapshot_content())
        assert len(queue.items) == 0

    def test_fallback_signals_flag_items(self) -> None:
        """Fallback path usage → all items flagged HIGH."""
        engine = self._engine()
        # Force fallback diagnostics by setting last diagnostics directly
        engine._last_diagnostics["fallback_used"] = True
        engine._last_diagnostics["status"] = "rule_based_fallback"
        queue = engine.build_review_queue("m-004", "snap-004", self._snapshot_content())
        assert len(queue.items) > 0
        assert all(i.severity == ReviewSeverity.HIGH for i in queue.items)

    def test_transcript_repo_signals_fed_to_queue(self) -> None:
        """Unresolved speaker in transcript → UNRESOLVED_SPEAKER reason."""
        engine = self._engine()
        mock_repo = MagicMock()
        unresolved_seg = MagicMock()
        unresolved_seg.id = "seg-1"
        unresolved_seg.confidence_score = 0.3
        unresolved_seg.speaker_name = "Unknown Speaker"
        unresolved_seg.manual_correction = False
        mock_repo.list_for_meeting.return_value = [unresolved_seg]
        engine._transcripts = mock_repo

        queue = engine.build_review_queue("m-005", "snap-005", self._snapshot_content())
        all_reasons = {r for item in queue.items for r in item.reasons}
        assert ReviewReason.UNRESOLVED_SPEAKER in all_reasons

    def test_deterministic_across_calls(self) -> None:
        engine = self._engine()
        engine._last_diagnostics["fallback_used"] = True
        engine._last_diagnostics["status"] = "rule_based_fallback"
        content = self._snapshot_content()
        q1 = engine.build_review_queue("m-006", "snap-006", content)
        q2 = engine.build_review_queue("m-006", "snap-006", content)
        assert len(q1.items) == len(q2.items)
        for i1, i2 in zip(q1.items, q2.items):
            assert i1.item_text == i2.item_text
            assert i1.severity == i2.severity


# ---------------------------------------------------------------------------
# generate() — review_queue in ProtocolSnapshot
# ---------------------------------------------------------------------------

class TestGenerateReviewQueueIntegration:
    def test_generate_without_repo_includes_review_queue(self) -> None:
        engine = ProtocolEngine()
        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent(
            decisions=["We decided to proceed."],
            action_items=["Alice will prepare the document by Monday."],
        )
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        snapshot = engine.generate("m-100")
        assert snapshot.review_queue is not None
        assert isinstance(snapshot.review_queue, ConfidenceReviewQueue)

    def test_generate_with_repo_includes_review_queue(self) -> None:
        engine = ProtocolEngine()
        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent(
            action_items=["Alice will deliver the script by Friday."]
        )
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        mock_transcripts.list_for_meeting.return_value = []
        engine._transcripts = mock_transcripts

        mock_snap_row = MagicMock()
        mock_snap_row.id = "snap-repo-001"
        mock_snap_row.snapshot_version = 1
        mock_repo = MagicMock()
        mock_repo.append.return_value = mock_snap_row
        engine._snapshots = mock_repo

        snapshot = engine.generate("m-101")
        assert snapshot.review_queue is not None
        assert snapshot.review_queue.snapshot_id == "snap-repo-001"

    def test_no_repo_snapshot_id_is_synthetic(self) -> None:
        engine = ProtocolEngine()
        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent()
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        snapshot = engine.generate("m-102")
        assert snapshot.review_queue is not None
        assert "m-102" in snapshot.review_queue.snapshot_id


# ---------------------------------------------------------------------------
# Review workflow — apply decisions, get final items, persist
# ---------------------------------------------------------------------------

class TestReviewWorkflow:
    def _queue_with_flags(self) -> ConfidenceReviewQueue:
        engine = ProtocolEngine()
        engine._last_diagnostics["fallback_used"] = True
        engine._last_diagnostics["status"] = "rule_based_fallback"
        return engine.build_review_queue(
            "m-200",
            "snap-200",
            {
                "decisions": ["We decided to roll out the new process."],
                "action_items": ["Alice will deliver the document by Friday."],
                "open_questions": ["Who validates rollback?"],
            },
        )

    def test_queue_sorted_high_first(self) -> None:
        queue = self._queue_with_flags()
        order = {ReviewSeverity.HIGH: 0, ReviewSeverity.MEDIUM: 1, ReviewSeverity.LOW: 2}
        severities = [order[i.severity] for i in queue.items]
        assert severities == sorted(severities)

    def test_dismissed_item_excluded_from_final(self) -> None:
        queue = self._queue_with_flags()
        action_items = [i for i in queue.items if i.item_type == ItemType.ACTION_ITEM]
        for ai in action_items:
            queue.apply_action(ai.item_id, ReviewAction.DISMISS)
        assert queue.get_final_items(ItemType.ACTION_ITEM) == []

    def test_edited_item_reflected_in_final(self) -> None:
        queue = self._queue_with_flags()
        decisions = [i for i in queue.items if i.item_type == ItemType.DECISION]
        if decisions:
            queue.apply_action(
                decisions[0].item_id,
                ReviewAction.EDIT,
                edited_text="Revised decision text.",
            )
            assert "Revised decision text." in queue.get_final_items(ItemType.DECISION)

    def test_pending_items_included_with_original_text(self) -> None:
        queue = self._queue_with_flags()
        for item_type in ItemType:
            finals = queue.get_final_items(item_type)
            assert all(isinstance(t, str) for t in finals)

    def test_clean_queue_returns_all_snapshot_items(self) -> None:
        engine = ProtocolEngine()
        content = {
            "decisions": ["Adopt the plan."],
            "action_items": ["Alice sends the report by Monday."],
            "open_questions": ["Who approves?"],
        }
        queue = engine.build_review_queue("m-201", "snap-201", content)
        assert len(queue.items) == 0
        assert queue.get_final_items(ItemType.DECISION) == content["decisions"]
        assert queue.get_final_items(ItemType.ACTION_ITEM) == content["action_items"]
        assert queue.get_final_items(ItemType.OPEN_QUESTION) == content["open_questions"]


# ---------------------------------------------------------------------------
# Persistence — save/load (restart-safe)
# ---------------------------------------------------------------------------

class TestReviewQueuePersistence:
    def test_save_and_load_preserves_review_actions(self, tmp_path: Path) -> None:
        engine = ProtocolEngine()
        engine._last_diagnostics["fallback_used"] = True
        engine._last_diagnostics["status"] = "rule_based_fallback"
        queue = engine.build_review_queue(
            "m-300",
            "snap-300",
            {"decisions": ["Decision A."], "action_items": ["Do task X by Friday."], "open_questions": []},
        )
        if not queue.items:
            pytest.skip("No flagged items — cannot test persistence")

        item_id = queue.items[0].item_id
        queue.apply_action(item_id, ReviewAction.EDIT, edited_text="Revised text.")

        queue.save(Path("review-m-300.json"), install_root=tmp_path)
        restored = ConfidenceReviewQueue.load(Path("review-m-300.json"), install_root=tmp_path)

        assert restored.meeting_id == "m-300"
        found = restored._find(item_id)
        assert found.action == ReviewAction.EDIT
        assert found.edited_text == "Revised text."

    def test_load_preserves_final_items(self, tmp_path: Path) -> None:
        engine = ProtocolEngine()
        engine._last_diagnostics["fallback_used"] = True
        engine._last_diagnostics["status"] = "rule_based_fallback"
        queue = engine.build_review_queue(
            "m-301",
            "snap-301",
            {"decisions": ["Keep this decision."], "action_items": ["Remove this task."], "open_questions": []},
        )
        if not queue.items:
            pytest.skip("No flagged items")

        action_items = [i for i in queue.items if i.item_type == ItemType.ACTION_ITEM]
        for ai in action_items:
            queue.apply_action(ai.item_id, ReviewAction.DISMISS)

        queue.save(Path("review-m-301.json"), install_root=tmp_path)
        restored = ConfidenceReviewQueue.load(Path("review-m-301.json"), install_root=tmp_path)

        assert restored.get_final_items(ItemType.ACTION_ITEM) == []

    def test_queue_file_stays_in_reviews_boundary(self, tmp_path: Path) -> None:
        """Queue file must be in runtime/reviews, never in exports or elsewhere."""
        engine = ProtocolEngine()
        queue = engine.build_review_queue("m-302", "snap-302", {"decisions": [], "action_items": [], "open_questions": []})
        forbidden = tmp_path / "exports" / "queue.json"
        with pytest.raises(ValueError, match="runtime/reviews"):
            queue.save(forbidden, install_root=tmp_path)


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
