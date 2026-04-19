"""Integrated QA validation for HEAR-108 short-term quality wave.

Validates end-to-end behavior across HEAR-105, HEAR-106 and HEAR-107:
- deterministic action-item scoring
- review queue ordering and persistence
- traceability integrity across restart and revision change
- export-facing markdown correctness after review edits
"""
from __future__ import annotations

from pathlib import Path

from ayehear.app.window import MainWindow
from ayehear.services.action_item_quality import ActionItemQualityEngine
from ayehear.services.confidence_review import (
    ConfidenceReviewQueue,
    ItemType,
    ReviewAction,
    ReviewSeverity,
)
from ayehear.services.protocol_traceability import EvidenceType, TraceabilityStore


MEETING_ID = "meeting-hear-108"
SNAPSHOT_V1 = "snap-108-v1"
SNAPSHOT_V2 = "snap-108-v2"


def _snapshot_content() -> dict[str, list[str]]:
    return {
        "decisions": ["We decided to adopt the staged rollout plan."],
        "action_items": ["Alice will deliver the migration script by Friday."],
        "open_questions": ["Who owns rollback validation?"],
    }


def _segments() -> list[dict[str, object]]:
    return [
        {
            "id": "seg-108-1",
            "start_ms": 1000,
            "end_ms": 4500,
            "speaker_name": "Alice",
            "confidence_score": 0.95,
            "manual_correction": False,
            "text": "We decided to adopt the staged rollout plan for deployment.",
        },
        {
            "id": "seg-108-2",
            "start_ms": 5000,
            "end_ms": 9000,
            "speaker_name": "Alice",
            "confidence_score": 0.91,
            "manual_correction": False,
            "text": "Alice will deliver the migration script by Friday.",
        },
        {
            "id": "seg-108-3",
            "start_ms": 9100,
            "end_ms": 12000,
            "speaker_name": "Unknown Speaker",
            "confidence_score": 0.45,
            "manual_correction": False,
            "text": "Who owns rollback validation for this release?",
        },
    ]


def _assert_severity_order(queue: ConfidenceReviewQueue) -> None:
    order = {ReviewSeverity.HIGH: 0, ReviewSeverity.MEDIUM: 1, ReviewSeverity.LOW: 2}
    severities = [order[item.severity] for item in queue.items]
    assert severities == sorted(severities)


def test_hear_108_integrated_quality_wave(tmp_path: Path) -> None:
    # HEAR-105 deterministic scoring contract
    engine = ActionItemQualityEngine(language="English")
    action_text = _snapshot_content()["action_items"][0]
    score_1 = engine.score(action_text)
    score_2 = engine.score(action_text)
    assert score_1.score == score_2.score
    assert score_1.reasons == score_2.reasons

    # HEAR-106 queue build: deterministic ranking + persistence
    signals = ConfidenceReviewQueue.build_signals(
        transcript_segments=_segments(),
        engine_diagnostics={"fallback_used": False},
    )
    queue = ConfidenceReviewQueue.build(
        meeting_id=MEETING_ID,
        snapshot_id=SNAPSHOT_V1,
        snapshot_content=_snapshot_content(),
        signals=signals,
    )
    assert len(queue.items) >= 1
    _assert_severity_order(queue)

    action_item = next(item for item in queue.items if item.item_type == ItemType.ACTION_ITEM)
    edited_action = "Alice will deliver migration script v2 by Friday 17:00."
    queue.apply_action(action_item.item_id, ReviewAction.EDIT, edited_text=edited_action)

    review_file = Path("hear-108-queue.json")
    queue.save(review_file, install_root=tmp_path)
    restored_queue = ConfidenceReviewQueue.load(review_file, install_root=tmp_path)
    restored_action = restored_queue._find(action_item.item_id)
    assert restored_action.action == ReviewAction.EDIT
    assert restored_action.effective_text() == edited_action

    final_content = {
        "decisions": restored_queue.get_final_items(ItemType.DECISION),
        "action_items": restored_queue.get_final_items(ItemType.ACTION_ITEM),
        "open_questions": restored_queue.get_final_items(ItemType.OPEN_QUESTION),
    }
    assert edited_action in final_content["action_items"]

    # HEAR-107 traceability: restart-safe and revision-safe behavior
    trace_v1 = TraceabilityStore(snapshot_id=SNAPSHOT_V1)
    trace_v1.build_links(final_content, _segments(), fallback_used=False)
    assert trace_v1.summary()["total"] >= 3

    action_links_v1 = trace_v1.get_links_for_item("action_item", edited_action)
    assert len(action_links_v1) == 1
    assert action_links_v1[0].evidence_type == EvidenceType.DIRECT
    assert action_links_v1[0].segments[0].segment_id == "seg-108-2"

    trace_file = Path("hear-108-trace-v1.json")
    trace_v1.save(trace_file, install_root=tmp_path)
    restored_trace_v1 = TraceabilityStore.load(trace_file, install_root=tmp_path)
    restored_action_links = restored_trace_v1.get_links_for_item("action_item", edited_action)
    assert len(restored_action_links) == 1
    assert restored_action_links[0].segments[0].segment_id == "seg-108-2"

    # Revision change must preserve content-level mapping for unchanged items.
    revised_content = {
        **final_content,
        "decisions": final_content["decisions"] + ["Decision update: QA sign-off required."],
    }
    trace_v2 = TraceabilityStore(snapshot_id=SNAPSHOT_V2)
    trace_v2.build_links(revised_content, _segments(), fallback_used=False)

    action_links_v2 = trace_v2.get_links_for_item("action_item", edited_action)
    assert len(action_links_v2) == 1
    assert action_links_v2[0].evidence_type == EvidenceType.DIRECT
    assert action_links_v2[0].segments[0].segment_id == "seg-108-2"

    # Export-facing markdown should reflect reviewed (edited) final content.
    draft = (
        "Summary\n- QA integrated wave validation passed\n\n"
        f"Decisions\n- {revised_content['decisions'][0]}\n\n"
        f"Action Items\n- {edited_action}\n\n"
        f"Open Questions\n- {final_content['open_questions'][0]}"
    )
    markdown = MainWindow._format_as_markdown(draft, "HEAR-108 Validation", "internal")
    assert "## Action Items" in markdown
    assert edited_action in markdown
    assert "## Open Questions" in markdown
