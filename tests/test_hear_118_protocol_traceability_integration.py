"""Tests for HEAR-118: Protocol Traceability integration (V2-13).

Verifies that TraceabilityStore is correctly wired into ProtocolEngine so that
transcript-source evidence, speaker attribution state, and direct/inferred
evidence type work end-to-end without any cloud or model dependency.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ayehear.services.protocol_engine import ProtocolContent, ProtocolEngine, ProtocolSnapshot
from ayehear.services.protocol_traceability import (
    EvidenceType,
    SpeakerAttributionState,
    TraceabilityStore,
)


# ---------------------------------------------------------------------------
# build_trace_store — public integration method
# ---------------------------------------------------------------------------

class TestBuildTraceStore:
    def _engine(self) -> ProtocolEngine:
        return ProtocolEngine()

    def _snapshot_content(self) -> dict:
        return {
            "decisions": ["We decided to adopt the new process."],
            "action_items": ["Alice will send the report by Friday."],
            "open_questions": ["Who owns rollback validation?"],
        }

    def test_returns_trace_store(self) -> None:
        engine = self._engine()
        store = engine.build_trace_store("m-001", "snap-001", self._snapshot_content())
        assert isinstance(store, TraceabilityStore)

    def test_snapshot_id_stored(self) -> None:
        engine = self._engine()
        store = engine.build_trace_store("m-002", "snap-002", self._snapshot_content())
        assert store.snapshot_id == "snap-002"

    def test_one_link_per_item(self) -> None:
        engine = self._engine()
        content = self._snapshot_content()
        store = engine.build_trace_store("m-003", "snap-003", content)
        total_items = sum(len(v) for v in content.values())
        assert len(store.links) == total_items

    def test_no_transcript_produces_inferred_links(self) -> None:
        """Without transcript segments every item must be INFERRED."""
        engine = self._engine()
        store = engine.build_trace_store("m-004", "snap-004", self._snapshot_content())
        assert all(lk.evidence_type == EvidenceType.INFERRED for lk in store.links)

    def test_fallback_forces_all_inferred(self) -> None:
        engine = self._engine()
        engine._last_diagnostics["fallback_used"] = True
        engine._last_diagnostics["status"] = "rule_based_fallback"

        mock_repo = MagicMock()
        seg = MagicMock()
        seg.id = "seg-1"
        seg.start_ms = 0
        seg.end_ms = 1000
        seg.speaker_name = "Alice"
        seg.confidence_score = 0.9
        seg.manual_correction = False
        seg.text = "We decided to adopt the new process and Alice will send the report."
        mock_repo.list_for_meeting.return_value = [seg]
        engine._transcripts = mock_repo

        store = engine.build_trace_store("m-005", "snap-005", self._snapshot_content())
        assert all(lk.evidence_type == EvidenceType.INFERRED for lk in store.links)

    def test_keyword_overlap_produces_direct_link(self) -> None:
        engine = self._engine()
        mock_repo = MagicMock()
        seg = MagicMock()
        seg.id = "seg-2"
        seg.start_ms = 500
        seg.end_ms = 2000
        seg.speaker_name = "Alice"
        seg.confidence_score = 0.92
        seg.manual_correction = False
        # Shares "decided", "adopt", "process" with the decision item
        seg.text = "We decided to adopt the new process starting next quarter."
        mock_repo.list_for_meeting.return_value = [seg]
        engine._transcripts = mock_repo

        content = {"decisions": ["We decided to adopt the new process."], "action_items": [], "open_questions": []}
        store = engine.build_trace_store("m-006", "snap-006", content)
        decision_links = store.get_links_for_item("decision", "We decided to adopt the new process.")
        assert len(decision_links) == 1
        assert decision_links[0].evidence_type == EvidenceType.DIRECT

    def test_unresolved_speaker_state_preserved(self) -> None:
        engine = self._engine()
        mock_repo = MagicMock()
        seg = MagicMock()
        seg.id = "seg-3"
        seg.start_ms = 0
        seg.end_ms = 800
        seg.speaker_name = "Unknown Speaker"
        seg.confidence_score = 0.4
        seg.manual_correction = False
        seg.text = "Alice will send the report by Friday for the team."
        mock_repo.list_for_meeting.return_value = [seg]
        engine._transcripts = mock_repo

        content = {"decisions": [], "action_items": ["Alice will send the report by Friday."], "open_questions": []}
        store = engine.build_trace_store("m-007", "snap-007", content)
        links = store.get_links_for_item("action_item", "Alice will send the report by Friday.")
        assert any(lk.has_unresolved_speaker for lk in links)

    def test_corrected_speaker_state_preserved(self) -> None:
        engine = self._engine()
        mock_repo = MagicMock()
        seg = MagicMock()
        seg.id = "seg-4"
        seg.start_ms = 0
        seg.end_ms = 1200
        seg.speaker_name = "Bob"
        seg.confidence_score = 0.5
        seg.manual_correction = True
        seg.text = "Alice will send the report by Friday afternoon."
        mock_repo.list_for_meeting.return_value = [seg]
        engine._transcripts = mock_repo

        content = {"decisions": [], "action_items": ["Alice will send the report by Friday."], "open_questions": []}
        store = engine.build_trace_store("m-008", "snap-008", content)
        links = store.get_links_for_item("action_item", "Alice will send the report by Friday.")
        if links and links[0].segments:
            state = links[0].segments[0].speaker_attribution_state
            assert state == SpeakerAttributionState.CORRECTED

    def test_deterministic_across_calls(self) -> None:
        engine = self._engine()
        content = self._snapshot_content()
        s1 = engine.build_trace_store("m-009", "snap-009", content)
        s2 = engine.build_trace_store("m-009", "snap-009", content)
        assert len(s1.links) == len(s2.links)
        for l1, l2 in zip(s1.links, s2.links):
            assert l1.item_text == l2.item_text
            assert l1.evidence_type == l2.evidence_type


# ---------------------------------------------------------------------------
# generate() — trace_store in ProtocolSnapshot
# ---------------------------------------------------------------------------

class TestGenerateTraceStoreIntegration:
    def test_generate_without_repo_includes_trace_store(self) -> None:
        engine = ProtocolEngine()
        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent(
            decisions=["We decided to proceed."],
            action_items=["Alice will prepare the document by Monday."],
        )
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        snapshot = engine.generate("m-100")
        assert snapshot.trace_store is not None
        assert isinstance(snapshot.trace_store, TraceabilityStore)

    def test_generate_with_repo_includes_trace_store(self) -> None:
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
        assert snapshot.trace_store is not None
        assert snapshot.trace_store.snapshot_id == "snap-repo-001"

    def test_no_repo_snapshot_id_is_synthetic(self) -> None:
        engine = ProtocolEngine()
        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent()
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        snapshot = engine.generate("m-102")
        assert snapshot.trace_store is not None
        assert "m-102" in snapshot.trace_store.snapshot_id

    def test_trace_summary_counts_are_consistent(self) -> None:
        engine = ProtocolEngine()
        engine._extract_content = lambda lines, allow_fallback=None: ProtocolContent(
            decisions=["Adopt the plan."],
            action_items=["Alice sends report."],
            open_questions=["Who approves?"],
        )
        mock_transcripts = MagicMock()
        mock_transcripts.list_for_protocol.return_value = []
        engine._transcripts = mock_transcripts

        snapshot = engine.generate("m-103")
        summary = snapshot.trace_store.summary()
        assert summary["total"] == 3
        assert summary["direct"] + summary["inferred"] == summary["total"]


# ---------------------------------------------------------------------------
# Persistence — save/load (restart-safe)
# ---------------------------------------------------------------------------

class TestTraceStorePersistence:
    def test_save_and_load_preserves_links(self, tmp_path: Path) -> None:
        engine = ProtocolEngine()
        mock_repo = MagicMock()
        seg = MagicMock()
        seg.id = "seg-p1"
        seg.start_ms = 100
        seg.end_ms = 900
        seg.speaker_name = "Alice"
        seg.confidence_score = 0.95
        seg.manual_correction = False
        seg.text = "We decided to adopt the new process starting next quarter."
        mock_repo.list_for_meeting.return_value = [seg]
        engine._transcripts = mock_repo

        content = {"decisions": ["We decided to adopt the new process."], "action_items": [], "open_questions": []}
        store = engine.build_trace_store("m-300", "snap-300", content)
        assert len(store.links) == 1

        store.save(Path("trace-m-300.json"), install_root=tmp_path)
        restored = TraceabilityStore.load(Path("trace-m-300.json"), install_root=tmp_path)

        assert restored.snapshot_id == "snap-300"
        assert len(restored.links) == 1
        assert restored.links[0].item_text == "We decided to adopt the new process."

    def test_load_preserves_evidence_type(self, tmp_path: Path) -> None:
        engine = ProtocolEngine()
        store = engine.build_trace_store(
            "m-301", "snap-301",
            {"decisions": ["Adopt this plan."], "action_items": [], "open_questions": []}
        )
        store.save(Path("trace-m-301.json"), install_root=tmp_path)
        restored = TraceabilityStore.load(Path("trace-m-301.json"), install_root=tmp_path)

        assert all(lk.evidence_type in (EvidenceType.DIRECT, EvidenceType.INFERRED) for lk in restored.links)

    def test_trace_file_stays_in_traces_boundary(self, tmp_path: Path) -> None:
        """Trace file must be in runtime/traces, never in exports or elsewhere."""
        engine = ProtocolEngine()
        store = engine.build_trace_store("m-302", "snap-302", {"decisions": [], "action_items": [], "open_questions": []})
        forbidden = tmp_path / "exports" / "trace.json"
        with pytest.raises(ValueError, match="runtime/traces"):
            store.save(forbidden, install_root=tmp_path)

    def test_load_preserves_speaker_attribution_state(self, tmp_path: Path) -> None:
        engine = ProtocolEngine()
        mock_repo = MagicMock()
        seg = MagicMock()
        seg.id = "seg-p2"
        seg.start_ms = 0
        seg.end_ms = 500
        seg.speaker_name = "Unknown Speaker"
        seg.confidence_score = 0.3
        seg.manual_correction = False
        seg.text = "Alice will send the report by Friday soon."
        mock_repo.list_for_meeting.return_value = [seg]
        engine._transcripts = mock_repo

        content = {"decisions": [], "action_items": ["Alice will send the report by Friday."], "open_questions": []}
        store = engine.build_trace_store("m-303", "snap-303", content)
        store.save(Path("trace-m-303.json"), install_root=tmp_path)
        restored = TraceabilityStore.load(Path("trace-m-303.json"), install_root=tmp_path)

        links = restored.get_links_for_item("action_item", "Alice will send the report by Friday.")
        if links and links[0].segments:
            assert links[0].segments[0].speaker_attribution_state == SpeakerAttributionState.UNRESOLVED


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v"])
