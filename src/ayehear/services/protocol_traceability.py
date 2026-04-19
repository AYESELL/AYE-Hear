"""Evidence-Linked Protocol Traceability (HEAR-107 / V2-13).

Links protocol items (decisions, action items, open questions) back to their
transcript-source context so users can verify origin before final export.

Each TraceLink stores:
  - transcript excerpt and time range
  - speaker attribution state at the time of protocol generation
  - whether the item has direct transcript backing or was inferred from aggregation

All state is persisted locally as JSON (ADR-0011: install-root-relative).
No outbound data transmission – ADR-0001 offline-first.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ayehear.utils.paths import traces_dir

logger = logging.getLogger(__name__)


def _resolve_trace_store_path(path: Path, install_root: Path | None = None) -> Path:
    """Resolve *path* into the approved local runtime/traces boundary.

    Relative paths are anchored under ``<install_root>/runtime/traces``.
    Absolute paths must already live inside that directory.
    """
    allowed_root = traces_dir(install_root).resolve()
    candidate = path if path.is_absolute() else allowed_root / path.name
    resolved = candidate.resolve()
    if resolved.parent != allowed_root:
        raise ValueError(
            "Traceability state must stay within the local runtime/traces boundary. "
            f"Received path: {resolved}"
        )
    return resolved


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class EvidenceType(str, Enum):
    """Whether the protocol item is directly backed by a transcript quote or inferred."""
    DIRECT = "direct"       # text closely matches a transcript segment
    INFERRED = "inferred"   # synthesised from multiple segments / LLM aggregation


class SpeakerAttributionState(str, Enum):
    """State of speaker attribution for the backing segment."""
    CONFIRMED = "confirmed"        # high confidence or manually corrected
    LOW_CONFIDENCE = "low_confidence"
    UNRESOLVED = "unresolved"      # speaker == "Unknown Speaker"
    CORRECTED = "corrected"        # manual_correction flag was set


@dataclass
class TraceSegmentRef:
    """Reference to one transcript segment contributing to a trace link."""
    segment_id: str
    start_ms: int
    end_ms: int
    speaker_name: str
    speaker_attribution_state: SpeakerAttributionState
    excerpt: str  # up to first 200 chars of the segment text


@dataclass
class TraceLink:
    """One traceability link from a protocol item back to its transcript source(s)."""
    link_id: str
    protocol_snapshot_id: str
    item_type: str          # "decision" | "action_item" | "open_question"
    item_text: str
    evidence_type: EvidenceType
    segments: list[TraceSegmentRef] = field(default_factory=list)

    @property
    def time_range(self) -> tuple[int, int] | None:
        """Return (start_ms, end_ms) spanning all referenced segments, or None."""
        if not self.segments:
            return None
        return (
            min(s.start_ms for s in self.segments),
            max(s.end_ms for s in self.segments),
        )

    @property
    def primary_speaker(self) -> str | None:
        """Speaker name from the first contributing segment."""
        return self.segments[0].speaker_name if self.segments else None

    @property
    def has_unresolved_speaker(self) -> bool:
        return any(
            s.speaker_attribution_state == SpeakerAttributionState.UNRESOLVED
            for s in self.segments
        )

    def to_dict(self) -> dict[str, Any]:
        tr = self.time_range
        return {
            "link_id": self.link_id,
            "protocol_snapshot_id": self.protocol_snapshot_id,
            "item_type": self.item_type,
            "item_text": self.item_text,
            "evidence_type": self.evidence_type.value,
            "time_range": {"start_ms": tr[0], "end_ms": tr[1]} if tr else None,
            "segments": [
                {
                    "segment_id": s.segment_id,
                    "start_ms": s.start_ms,
                    "end_ms": s.end_ms,
                    "speaker_name": s.speaker_name,
                    "speaker_attribution_state": s.speaker_attribution_state.value,
                    "excerpt": s.excerpt,
                }
                for s in self.segments
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TraceLink":
        segments = [
            TraceSegmentRef(
                segment_id=s["segment_id"],
                start_ms=s["start_ms"],
                end_ms=s["end_ms"],
                speaker_name=s["speaker_name"],
                speaker_attribution_state=SpeakerAttributionState(s["speaker_attribution_state"]),
                excerpt=s["excerpt"],
            )
            for s in data.get("segments", [])
        ]
        return cls(
            link_id=data["link_id"],
            protocol_snapshot_id=data["protocol_snapshot_id"],
            item_type=data["item_type"],
            item_text=data["item_text"],
            evidence_type=EvidenceType(data["evidence_type"]),
            segments=segments,
        )


# ---------------------------------------------------------------------------
# Attribution helper
# ---------------------------------------------------------------------------

_UNRESOLVED_LABEL = "Unknown Speaker"


def _attribution_state(
    segment: dict[str, Any],
    *,
    confidence_threshold: float = 0.6,
) -> SpeakerAttributionState:
    """Derive SpeakerAttributionState from a raw segment dict."""
    if segment.get("speaker_name", _UNRESOLVED_LABEL) == _UNRESOLVED_LABEL:
        return SpeakerAttributionState.UNRESOLVED
    if segment.get("manual_correction"):
        return SpeakerAttributionState.CORRECTED
    confidence = float(segment.get("confidence_score", 1.0))
    if confidence < confidence_threshold:
        return SpeakerAttributionState.LOW_CONFIDENCE
    return SpeakerAttributionState.CONFIRMED


# ---------------------------------------------------------------------------
# Trace store
# ---------------------------------------------------------------------------

EXCERPT_MAX_CHARS = 200


class TraceabilityStore:
    """Local store for protocol-item → transcript trace links.

    Usage::

        store = TraceabilityStore(snapshot_id="snap-001")
        store.add_link(link)
        store.save(Path("runtime/traces/meet-abc.json"))
        restored = TraceabilityStore.load(Path("runtime/traces/meet-abc.json"))
        links = restored.get_links_for_item("action_item", "Alice will send the report.")
    """

    def __init__(self, snapshot_id: str) -> None:
        self.snapshot_id = snapshot_id
        self._links: list[TraceLink] = []
        self._counter: int = 0

    # ------------------------------------------------------------------
    # Building trace links
    # ------------------------------------------------------------------

    def build_links(
        self,
        snapshot_content: dict[str, list[str]],
        transcript_segments: list[dict[str, Any]],
        *,
        fallback_used: bool = False,
    ) -> None:
        """Populate trace links from snapshot content and transcript segments.

        Strategy:
        - For each protocol item, search the transcript for segments whose text
          closely contains or overlaps with keywords from the item text.
        - Items with at least one matching segment → EvidenceType.DIRECT
        - Items with no matching segment (LLM synthesis / aggregation) → EvidenceType.INFERRED
        - When fallback was used, all items are INFERRED (rule-based extraction has no
          positional backing).
        """
        self._links = []
        self._counter = 0

        type_map = [
            ("decision", "decisions"),
            ("action_item", "action_items"),
            ("open_question", "open_questions"),
            ("risk", "risk_items"),
        ]

        for item_type, content_key in type_map:
            items = snapshot_content.get(content_key, [])
            for item_text in items:
                link = self._build_single_link(
                    item_type=item_type,
                    item_text=item_text,
                    transcript_segments=transcript_segments,
                    fallback_used=fallback_used,
                )
                self._links.append(link)

    def _build_single_link(
        self,
        *,
        item_type: str,
        item_text: str,
        transcript_segments: list[dict[str, Any]],
        fallback_used: bool,
    ) -> TraceLink:
        self._counter += 1
        link_id = f"{self.snapshot_id}-{item_type}-{self._counter}"

        if fallback_used or not transcript_segments:
            return TraceLink(
                link_id=link_id,
                protocol_snapshot_id=self.snapshot_id,
                item_type=item_type,
                item_text=item_text,
                evidence_type=EvidenceType.INFERRED,
                segments=[],
            )

        matching = self._find_matching_segments(item_text, transcript_segments)
        evidence_type = EvidenceType.DIRECT if matching else EvidenceType.INFERRED

        seg_refs = [
            TraceSegmentRef(
                segment_id=seg.get("id", f"seg-{i}"),
                start_ms=int(seg.get("start_ms", 0)),
                end_ms=int(seg.get("end_ms", 0)),
                speaker_name=seg.get("speaker_name", _UNRESOLVED_LABEL),
                speaker_attribution_state=_attribution_state(seg),
                excerpt=seg.get("text", "")[:EXCERPT_MAX_CHARS],
            )
            for i, seg in enumerate(matching)
        ]

        return TraceLink(
            link_id=link_id,
            protocol_snapshot_id=self.snapshot_id,
            item_type=item_type,
            item_text=item_text,
            evidence_type=evidence_type,
            segments=seg_refs,
        )

    @staticmethod
    def _find_matching_segments(
        item_text: str,
        segments: list[dict[str, Any]],
        *,
        min_overlap_words: int = 2,
    ) -> list[dict[str, Any]]:
        """Find transcript segments whose text shares keywords with item_text.

        Simple keyword-overlap heuristic: extracts significant words (len >= 4)
        from the item text and counts how many appear in each segment.
        """
        words = {
            w.lower().strip(".,!?;:")
            for w in item_text.split()
            if len(w) >= 4
        }
        if not words:
            return []

        matched = []
        for seg in segments:
            seg_text = seg.get("text", "").lower()
            overlap = sum(1 for w in words if w in seg_text)
            if overlap >= min_overlap_words:
                matched.append(seg)
        return matched

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def add_link(self, link: TraceLink) -> None:
        """Add a single pre-built TraceLink to the store."""
        self._links.append(link)

    @property
    def links(self) -> list[TraceLink]:
        return list(self._links)

    def get_links_for_item(
        self, item_type: str, item_text: str
    ) -> list[TraceLink]:
        """Return all trace links matching item_type and item_text exactly."""
        return [
            lk for lk in self._links
            if lk.item_type == item_type and lk.item_text == item_text
        ]

    def get_links_by_snapshot(self, snapshot_id: str) -> list[TraceLink]:
        return [lk for lk in self._links if lk.protocol_snapshot_id == snapshot_id]

    def summary(self) -> dict[str, int]:
        """Return counts: total, direct, inferred."""
        total = len(self._links)
        direct = sum(1 for lk in self._links if lk.evidence_type == EvidenceType.DIRECT)
        return {"total": total, "direct": direct, "inferred": total - direct}

    # ------------------------------------------------------------------
    # Persistence (local JSON – ADR-0011)
    # ------------------------------------------------------------------

    def save(self, path: Path, *, install_root: Path | None = None) -> None:
        """Persist trace store to a local runtime/traces JSON file."""
        path = _resolve_trace_store_path(path, install_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "snapshot_id": self.snapshot_id,
            "links": [lk.to_dict() for lk in self._links],
        }
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("TraceabilityStore saved: %s (%d links)", path, len(self._links))

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        install_root: Path | None = None,
    ) -> "TraceabilityStore":
        """Restore trace store from a local runtime/traces JSON file."""
        path = _resolve_trace_store_path(path, install_root)
        raw = json.loads(path.read_text(encoding="utf-8"))
        store = cls(snapshot_id=raw["snapshot_id"])
        store._links = [TraceLink.from_dict(d) for d in raw.get("links", [])]
        return store
