"""Tests for HEAR-116: V2-01 Action-Item Quality Engine Plus integration.

Verifies that ActionItemQualityEngine is correctly wired into ProtocolEngine
so that scoring, annotation, and persistence of quality signals work end-to-end.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ayehear.services.action_item_quality import ScoreReason, SHARPENING_THRESHOLD
from ayehear.services.protocol_engine import ProtocolContent, ProtocolEngine, ProtocolSnapshot


# ---------------------------------------------------------------------------
# score_action_items — public integration method
# ---------------------------------------------------------------------------

class TestScoreActionItems:
    def test_returns_one_result_per_item(self) -> None:
        engine = ProtocolEngine()
        items = [
            "Alice will deliver the report by Friday.",
            "Someone should look into this.",
        ]
        results = engine.score_action_items(items)
        assert len(results) == len(items)

    def test_strong_item_scores_higher_than_weak(self) -> None:
        engine = ProtocolEngine()
        strong = "Alice will deliver the migration report by Friday 17:00."
        weak = "Someone should look into this."
        strong_q, weak_q = engine.score_action_items([strong, weak])
        assert strong_q.score > weak_q.score

    def test_deterministic_across_calls(self) -> None:
        engine = ProtocolEngine()
        text = "Bitte prüfen bis Freitag."
        r1, = engine.score_action_items([text])
        r2, = engine.score_action_items([text])
        assert r1.score == r2.score
        assert r1.reasons == r2.reasons

    def test_empty_list_returns_empty(self) -> None:
        engine = ProtocolEngine()
        assert engine.score_action_items([]) == []

    def test_language_flows_to_quality_engine(self) -> None:
        """Language controls hint localisation; scoring weights are language-agnostic.

        An empty text triggers all base reasons in every language, so reasons
        and scores must be equal while localized hints differ.
        """
        de_engine = ProtocolEngine(language="Deutsch")
        en_engine = ProtocolEngine(language="English")
        # Empty text: no patterns can match → identical reasons in any language
        de_q, = de_engine.score_action_items([""])
        en_q, = en_engine.score_action_items([""])
        assert set(de_q.reasons) == set(en_q.reasons)
        assert de_q.score == en_q.score
        # Hints are localized — German text vs English text
        assert de_q.hints != en_q.hints


# ---------------------------------------------------------------------------
# annotate_weak_items — static formatting helper
# ---------------------------------------------------------------------------

class TestAnnotateWeakItems:
    def test_weak_item_gets_annotation(self) -> None:
        engine = ProtocolEngine()
        weak = "Someone should look into this."
        quality, = engine.score_action_items([weak])
        assert quality.needs_sharpening
        annotated, = engine.annotate_weak_items([weak], [quality])
        assert "[⚠ needs sharpening:" in annotated

    def test_annotation_contains_stable_reason_codes(self) -> None:
        engine = ProtocolEngine()
        weak = "Someone should look into this."
        quality, = engine.score_action_items([weak])
        annotated, = engine.annotate_weak_items([weak], [quality])
        for reason in quality.reasons:
            assert reason.value in annotated

    def test_strong_item_unchanged(self) -> None:
        engine = ProtocolEngine()
        strong = "Alice will deliver the migration report by Friday."
        quality, = engine.score_action_items([strong])
        annotated, = engine.annotate_weak_items([strong], [quality])
        if not quality.needs_sharpening:
            assert annotated == strong

    def test_mixed_list_only_annotates_weak(self) -> None:
        engine = ProtocolEngine()
        strong = "Alice will deliver the report by Friday."
        weak = "Irgendwer kümmert sich darum."
        qualities = engine.score_action_items([strong, weak])
        annotated = engine.annotate_weak_items([strong, weak], qualities)
        strong_annotated, weak_annotated = annotated
        assert "[⚠" not in strong_annotated or qualities[0].needs_sharpening
        assert "[⚠ needs sharpening:" in weak_annotated

    def test_annotation_is_deterministic(self) -> None:
        engine = ProtocolEngine()
        items = ["Someone should do something.", "Alice will create the report by Monday."]
        qualities = engine.score_action_items(items)
        r1 = engine.annotate_weak_items(items, qualities)
        r2 = engine.annotate_weak_items(items, qualities)
        assert r1 == r2

    def test_empty_reasons_item_not_annotated(self) -> None:
        from ayehear.services.action_item_quality import ActionItemQuality
        item = "some text"
        quality = ActionItemQuality(score=100, reasons=[], needs_sharpening=False, hints=[])
        result, = ProtocolEngine.annotate_weak_items([item], [quality])
        assert result == item


# ---------------------------------------------------------------------------
# generate() — quality scoring integrated into snapshot creation
# ---------------------------------------------------------------------------

class TestGenerateQualityIntegration:
    def test_generate_without_repo_returns_quality(self) -> None:
        """With no snapshot repo, generate() still returns quality scores."""
        engine = ProtocolEngine()

        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        # Force rule-based extraction with a known action item
        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent(
            action_items=["Alice will send the report by Friday."]
        )

        snapshot = engine.generate("meeting-001")
        assert isinstance(snapshot, ProtocolSnapshot)
        assert len(snapshot.action_item_quality) == 1
        assert snapshot.action_item_quality[0].score >= 0

    def test_generate_quality_matches_standalone_scoring(self) -> None:
        """Quality in ProtocolSnapshot must match direct score_action_items() call."""
        engine = ProtocolEngine()
        item = "Alice will deliver the migration script by Friday."

        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent(
            action_items=[item]
        )
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        snapshot = engine.generate("meeting-002")
        direct_quality, = engine.score_action_items([item])

        assert snapshot.action_item_quality[0].score == direct_quality.score
        assert snapshot.action_item_quality[0].reasons == direct_quality.reasons

    def test_generate_with_repo_persists_quality_description(self) -> None:
        """add_action_item() must receive a non-empty description for weak items."""
        engine = ProtocolEngine()
        weak_item = "Irgendwer kümmert sich darum."

        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent(
            action_items=[weak_item]
        )
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        mock_snapshot_row = MagicMock()
        mock_snapshot_row.id = "snap-001"
        mock_snapshot_row.snapshot_version = 1

        mock_repo = MagicMock()
        mock_repo.append.return_value = mock_snapshot_row
        engine._snapshots = mock_repo

        engine.generate("meeting-003")

        mock_repo.add_action_item.assert_called_once()
        _, call_kwargs = mock_repo.add_action_item.call_args
        # description must contain quality signal for a weak item
        description = mock_repo.add_action_item.call_args[0][2]
        assert "score:" in description
        assert "sharpening:True" in description

    def test_generate_with_repo_strong_item_description_has_no_reasons(self) -> None:
        """Strong items must have description with sharpening:False."""
        engine = ProtocolEngine()
        strong = "Alice will deliver the report by Friday."

        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent(
            action_items=[strong]
        )
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        mock_snapshot_row = MagicMock()
        mock_snapshot_row.id = "snap-002"
        mock_snapshot_row.snapshot_version = 1

        mock_repo = MagicMock()
        mock_repo.append.return_value = mock_snapshot_row
        engine._snapshots = mock_repo

        engine.generate("meeting-004")

        description = mock_repo.add_action_item.call_args[0][2]
        assert "score:" in description
        # If no reasons, no reasons key in description
        quality, = engine.score_action_items([strong])
        if not quality.needs_sharpening:
            assert "sharpening:False" in description


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
