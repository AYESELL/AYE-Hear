"""Tests for HEAR-107: Evidence-Linked Protocol Traceability (V2-13).

Verifies:
- TraceLink direct/inferred labeling
- build_links populates all content types
- Fallback-used forces all links to INFERRED
- Keyword-overlap matching (DIRECT when segments match)
- No matching segments → INFERRED
- time_range derived from segments
- primary_speaker
- has_unresolved_speaker
- Speaker attribution state derivation
- Persistence: save → load restores full state (restart-safe)
- get_links_for_item filter
- get_links_by_snapshot filter
- summary counts
- add_link manual usage
- Empty transcript → all INFERRED
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ayehear.services.protocol_traceability import (
    EvidenceType,
    SpeakerAttributionState,
    TraceLink,
    TraceSegmentRef,
    TraceabilityStore,
    _attribution_state,
)
from ayehear.utils.paths import traces_dir


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SNAPSHOT_ID = "snap-001"

SNAPSHOT_CONTENT = {
    "decisions": ["We decided to adopt the new CI pipeline."],
    "action_items": ["Alice will create the migration script by Friday."],
    "open_questions": ["Who owns the rollback plan?"],
}

MATCHING_SEGMENTS = [
    {
        "id": "seg-1",
        "start_ms": 1000,
        "end_ms": 5000,
        "speaker_name": "Alice",
        "confidence_score": 0.92,
        "manual_correction": False,
        "text": "We decided to adopt the new CI pipeline for our release process.",
    },
    {
        "id": "seg-2",
        "start_ms": 5100,
        "end_ms": 9000,
        "speaker_name": "Bob",
        "confidence_score": 0.85,
        "manual_correction": False,
        "text": "Alice will create the migration script and deliver it by Friday.",
    },
    {
        "id": "seg-3",
        "start_ms": 9100,
        "end_ms": 12000,
        "speaker_name": "Unknown Speaker",
        "confidence_score": 0.4,
        "manual_correction": False,
        "text": "Who owns the rollback plan for this migration?",
    },
]


# ---------------------------------------------------------------------------
# Attribution state derivation
# ---------------------------------------------------------------------------

class TestAttributionState:
    def test_unknown_speaker_gives_unresolved(self) -> None:
        seg = {"speaker_name": "Unknown Speaker", "confidence_score": 0.9, "manual_correction": False}
        assert _attribution_state(seg) == SpeakerAttributionState.UNRESOLVED

    def test_manual_correction_gives_corrected(self) -> None:
        seg = {"speaker_name": "Alice", "confidence_score": 0.9, "manual_correction": True}
        assert _attribution_state(seg) == SpeakerAttributionState.CORRECTED

    def test_low_confidence_gives_low(self) -> None:
        seg = {"speaker_name": "Alice", "confidence_score": 0.3, "manual_correction": False}
        assert _attribution_state(seg) == SpeakerAttributionState.LOW_CONFIDENCE

    def test_high_confidence_gives_confirmed(self) -> None:
        seg = {"speaker_name": "Alice", "confidence_score": 0.95, "manual_correction": False}
        assert _attribution_state(seg) == SpeakerAttributionState.CONFIRMED


# ---------------------------------------------------------------------------
# TraceLink helpers
# ---------------------------------------------------------------------------

class TestTraceLinkHelpers:
    def _make_link_with_segments(self) -> TraceLink:
        return TraceLink(
            link_id="link-1",
            protocol_snapshot_id=SNAPSHOT_ID,
            item_type="decision",
            item_text="Test decision.",
            evidence_type=EvidenceType.DIRECT,
            segments=[
                TraceSegmentRef(
                    segment_id="seg-1",
                    start_ms=1000,
                    end_ms=5000,
                    speaker_name="Alice",
                    speaker_attribution_state=SpeakerAttributionState.CONFIRMED,
                    excerpt="We decided to do it.",
                ),
                TraceSegmentRef(
                    segment_id="seg-2",
                    start_ms=5100,
                    end_ms=8000,
                    speaker_name="Bob",
                    speaker_attribution_state=SpeakerAttributionState.CONFIRMED,
                    excerpt="Bob agreed as well.",
                ),
            ],
        )

    def test_time_range_spans_all_segments(self) -> None:
        link = self._make_link_with_segments()
        assert link.time_range == (1000, 8000)

    def test_time_range_none_when_no_segments(self) -> None:
        link = TraceLink(
            link_id="l", protocol_snapshot_id="s", item_type="decision",
            item_text="x", evidence_type=EvidenceType.INFERRED
        )
        assert link.time_range is None

    def test_primary_speaker_is_first_segment(self) -> None:
        link = self._make_link_with_segments()
        assert link.primary_speaker == "Alice"

    def test_primary_speaker_none_without_segments(self) -> None:
        link = TraceLink(
            link_id="l", protocol_snapshot_id="s", item_type="decision",
            item_text="x", evidence_type=EvidenceType.INFERRED
        )
        assert link.primary_speaker is None

    def test_has_unresolved_speaker_true(self) -> None:
        link = TraceLink(
            link_id="l", protocol_snapshot_id="s", item_type="decision",
            item_text="x", evidence_type=EvidenceType.DIRECT,
            segments=[
                TraceSegmentRef(
                    segment_id="seg-u", start_ms=0, end_ms=1000,
                    speaker_name="Unknown Speaker",
                    speaker_attribution_state=SpeakerAttributionState.UNRESOLVED,
                    excerpt="Who knows?",
                )
            ],
        )
        assert link.has_unresolved_speaker is True

    def test_has_unresolved_speaker_false(self) -> None:
        link = self._make_link_with_segments()
        assert link.has_unresolved_speaker is False


# ---------------------------------------------------------------------------
# build_links
# ---------------------------------------------------------------------------

class TestBuildLinks:
    def test_all_content_types_traced(self) -> None:
        store = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        store.build_links(SNAPSHOT_CONTENT, MATCHING_SEGMENTS)
        types = {lk.item_type for lk in store.links}
        assert "decision" in types
        assert "action_item" in types
        assert "open_question" in types

    def test_matching_segment_gives_direct_evidence(self) -> None:
        store = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        store.build_links(SNAPSHOT_CONTENT, MATCHING_SEGMENTS)
        decisions = [lk for lk in store.links if lk.item_type == "decision"]
        assert any(lk.evidence_type == EvidenceType.DIRECT for lk in decisions)

    def test_fallback_forces_all_inferred(self) -> None:
        store = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        store.build_links(SNAPSHOT_CONTENT, MATCHING_SEGMENTS, fallback_used=True)
        assert all(lk.evidence_type == EvidenceType.INFERRED for lk in store.links)
        assert all(lk.segments == [] for lk in store.links)

    def test_empty_transcript_gives_inferred(self) -> None:
        store = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        store.build_links(SNAPSHOT_CONTENT, [])
        assert all(lk.evidence_type == EvidenceType.INFERRED for lk in store.links)

    def test_segment_excerpt_truncated_to_200_chars(self) -> None:
        long_text = "x" * 500
        segments = [
            {
                "id": "seg-long",
                "start_ms": 0, "end_ms": 1000,
                "speaker_name": "Alice",
                "confidence_score": 0.95,
                "manual_correction": False,
                "text": long_text,
            }
        ]
        content = {"decisions": ["some x word that overlaps with long"]}
        store = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        store.build_links(content, segments)
        for lk in store.links:
            for seg_ref in lk.segments:
                assert len(seg_ref.excerpt) <= 200

    def test_unresolved_speaker_state_carried_through(self) -> None:
        store = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        store.build_links(SNAPSHOT_CONTENT, MATCHING_SEGMENTS)
        aq_links = [lk for lk in store.links if lk.item_type == "open_question"]
        # seg-3 has Unknown Speaker and should be reflected
        for lk in aq_links:
            for seg in lk.segments:
                if seg.speaker_name == "Unknown Speaker":
                    assert seg.speaker_attribution_state == SpeakerAttributionState.UNRESOLVED

    def test_risk_items_traced(self) -> None:
        """V2-13 requires 'risks' to be traced alongside decisions/tasks (Finding #2)."""
        content_with_risk = {
            **SNAPSHOT_CONTENT,
            "risk_items": ["Risk: database migration may cause downtime."],
        }
        store = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        store.build_links(content_with_risk, MATCHING_SEGMENTS)
        types = {lk.item_type for lk in store.links}
        assert "risk" in types


# ---------------------------------------------------------------------------
# Querying
# ---------------------------------------------------------------------------

class TestQuerying:
    def _store(self) -> TraceabilityStore:
        s = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        s.build_links(SNAPSHOT_CONTENT, MATCHING_SEGMENTS)
        return s

    def test_get_links_for_item(self) -> None:
        s = self._store()
        links = s.get_links_for_item("decision", "We decided to adopt the new CI pipeline.")
        assert len(links) >= 1
        assert all(lk.item_type == "decision" for lk in links)

    def test_get_links_for_unknown_item_returns_empty(self) -> None:
        s = self._store()
        links = s.get_links_for_item("decision", "nonexistent item text")
        assert links == []

    def test_get_links_by_snapshot(self) -> None:
        s = self._store()
        links = s.get_links_by_snapshot(SNAPSHOT_ID)
        assert len(links) == len(s.links)

    def test_get_links_by_wrong_snapshot_returns_empty(self) -> None:
        s = self._store()
        links = s.get_links_by_snapshot("other-snap")
        assert links == []

    def test_summary_totals(self) -> None:
        s = self._store()
        summ = s.summary()
        assert summ["total"] == len(s.links)
        assert summ["direct"] + summ["inferred"] == summ["total"]


# ---------------------------------------------------------------------------
# Persistence (save / load) – restart-safe
# ---------------------------------------------------------------------------

class TestPersistence:
    def _store(self) -> TraceabilityStore:
        s = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        s.build_links(SNAPSHOT_CONTENT, MATCHING_SEGMENTS)
        return s

    def test_save_creates_file(self, tmp_path: Path) -> None:
        s = self._store()
        s.save(Path("snap.json"), install_root=tmp_path)
        assert (traces_dir(tmp_path) / "snap.json").exists()

    def test_load_restores_link_count(self, tmp_path: Path) -> None:
        s = self._store()
        p = Path("snap.json")
        s.save(p, install_root=tmp_path)
        restored = TraceabilityStore.load(p, install_root=tmp_path)
        assert len(restored.links) == len(s.links)

    def test_load_preserves_snapshot_id(self, tmp_path: Path) -> None:
        s = self._store()
        p = Path("snap.json")
        s.save(p, install_root=tmp_path)
        restored = TraceabilityStore.load(p, install_root=tmp_path)
        assert restored.snapshot_id == SNAPSHOT_ID

    def test_load_preserves_evidence_type(self, tmp_path: Path) -> None:
        s = self._store()
        p = Path("snap.json")
        s.save(p, install_root=tmp_path)
        restored = TraceabilityStore.load(p, install_root=tmp_path)
        for orig, rest in zip(s.links, restored.links):
            assert orig.evidence_type == rest.evidence_type

    def test_load_preserves_segments(self, tmp_path: Path) -> None:
        s = self._store()
        p = Path("snap.json")
        s.save(p, install_root=tmp_path)
        restored = TraceabilityStore.load(p, install_root=tmp_path)
        for orig, rest in zip(s.links, restored.links):
            assert len(orig.segments) == len(rest.segments)

    def test_load_preserves_speaker_attribution_state(self, tmp_path: Path) -> None:
        s = self._store()
        p = Path("snap.json")
        s.save(p, install_root=tmp_path)
        restored = TraceabilityStore.load(p, install_root=tmp_path)
        for orig, rest in zip(s.links, restored.links):
            for o_seg, r_seg in zip(orig.segments, rest.segments):
                assert o_seg.speaker_attribution_state == r_seg.speaker_attribution_state

    def test_time_range_survives_roundtrip(self, tmp_path: Path) -> None:
        s = self._store()
        p = Path("snap.json")
        s.save(p, install_root=tmp_path)
        restored = TraceabilityStore.load(p, install_root=tmp_path)
        for orig, rest in zip(s.links, restored.links):
            assert orig.time_range == rest.time_range

    def test_save_rejects_export_boundary(self, tmp_path: Path) -> None:
        s = self._store()
        forbidden = tmp_path / "exports" / "trace.json"
        with pytest.raises(ValueError, match="runtime/traces"):
            s.save(forbidden, install_root=tmp_path)

    def test_load_rejects_outside_runtime_traces(self, tmp_path: Path) -> None:
        forbidden = tmp_path / "exports" / "trace.json"
        forbidden.parent.mkdir(parents=True, exist_ok=True)
        forbidden.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="runtime/traces"):
            TraceabilityStore.load(forbidden, install_root=tmp_path)


# ---------------------------------------------------------------------------
# add_link manual usage
# ---------------------------------------------------------------------------

class TestAddLink:
    def test_add_link_appended(self) -> None:
        store = TraceabilityStore(snapshot_id=SNAPSHOT_ID)
        link = TraceLink(
            link_id="manual-1",
            protocol_snapshot_id=SNAPSHOT_ID,
            item_type="decision",
            item_text="Manual decision.",
            evidence_type=EvidenceType.INFERRED,
        )
        store.add_link(link)
        assert len(store.links) == 1
        assert store.links[0].link_id == "manual-1"
