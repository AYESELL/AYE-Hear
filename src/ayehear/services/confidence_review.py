"""Confidence Review Workflow (HEAR-106 / V2-12).

Builds a ranked review queue of uncertain protocol items before final export.
Signals fed into the queue: low speaker confidence, low transcript confidence,
conflicting extraction evidence, fallback-path usage.

No external service is called. All state is persisted locally as JSON
(ADR-0011: install-root-relative, offline-first ADR-0001).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ayehear.utils.paths import reviews_dir

logger = logging.getLogger(__name__)


def _resolve_review_store_path(path: Path, install_root: Path | None = None) -> Path:
    """Resolve *path* into the approved local runtime/reviews boundary.

    Relative paths are anchored under ``<install_root>/runtime/reviews``.
    Absolute paths must already live inside that directory.
    """
    allowed_root = reviews_dir(install_root).resolve()
    candidate = path if path.is_absolute() else allowed_root / path.name
    resolved = candidate.resolve()
    if resolved.parent != allowed_root:
        raise ValueError(
            "Review queue state must stay within the local runtime/reviews boundary. "
            f"Received path: {resolved}"
        )
    return resolved


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class ReviewReason(str, Enum):
    """Stable reason codes for why a protocol item is flagged."""
    LOW_SPEAKER_CONFIDENCE = "low_speaker_confidence"
    LOW_TRANSCRIPT_CONFIDENCE = "low_transcript_confidence"
    CONFLICTING_EXTRACTION = "conflicting_extraction"
    FALLBACK_PATH = "fallback_path"
    UNRESOLVED_SPEAKER = "unresolved_speaker"


class ReviewSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewAction(str, Enum):
    ACCEPT = "accept"
    EDIT = "edit"
    DISMISS = "dismiss"
    PENDING = "pending"  # initial state – not yet reviewed


class ItemType(str, Enum):
    ACTION_ITEM = "action_item"
    DECISION = "decision"
    OPEN_QUESTION = "open_question"
    SUMMARY = "summary"


@dataclass
class ReviewQueueItem:
    """One flagged protocol item in the confidence review queue."""
    item_id: str
    item_type: ItemType
    item_text: str
    reasons: list[ReviewReason]
    severity: ReviewSeverity
    action: ReviewAction = ReviewAction.PENDING
    edited_text: str | None = None

    def is_reviewed(self) -> bool:
        return self.action != ReviewAction.PENDING

    def effective_text(self) -> str:
        """Return edited text if the item was edited, otherwise original."""
        if self.action == ReviewAction.EDIT and self.edited_text is not None:
            return self.edited_text
        return self.item_text

    def is_dismissed(self) -> bool:
        return self.action == ReviewAction.DISMISS


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

_SEVERITY_MAP: dict[frozenset, ReviewSeverity] = {}

def _severity(reasons: list[ReviewReason]) -> ReviewSeverity:
    """Determine severity from reason set deterministically."""
    if ReviewReason.FALLBACK_PATH in reasons:
        return ReviewSeverity.HIGH
    if ReviewReason.LOW_SPEAKER_CONFIDENCE in reasons or ReviewReason.UNRESOLVED_SPEAKER in reasons:
        return ReviewSeverity.HIGH
    if ReviewReason.CONFLICTING_EXTRACTION in reasons:
        return ReviewSeverity.MEDIUM
    if ReviewReason.LOW_TRANSCRIPT_CONFIDENCE in reasons:
        return ReviewSeverity.MEDIUM
    return ReviewSeverity.LOW


_SEVERITY_ORDER = {ReviewSeverity.HIGH: 0, ReviewSeverity.MEDIUM: 1, ReviewSeverity.LOW: 2}


# ---------------------------------------------------------------------------
# Signal thresholds
# ---------------------------------------------------------------------------

LOW_SPEAKER_CONFIDENCE_THRESHOLD: float = 0.5
LOW_TRANSCRIPT_CONFIDENCE_THRESHOLD: float = 0.6
UNRESOLVED_SPEAKER_LABEL = "Unknown Speaker"


# ---------------------------------------------------------------------------
# Queue builder
# ---------------------------------------------------------------------------

@dataclass
class TranscriptSignals:
    """Aggregated uncertainty signals extracted from transcript segments.

    Attributes:
        min_confidence: lowest confidence_score across all segments
        avg_confidence: mean confidence_score
        has_unresolved_speakers: any segment with 'Unknown Speaker' label
        fallback_used: whether protocol engine used rule-based fallback
        conflicting_segments: number of segments that appear contradictory
            (e.g. corrected but still low-confidence)
    """
    min_confidence: float = 1.0
    avg_confidence: float = 1.0
    has_unresolved_speakers: bool = False
    fallback_used: bool = False
    conflicting_segments: int = 0


class ConfidenceReviewQueue:
    """Ranked queue of uncertain protocol items requiring user review.

    Usage::

        signals = ConfidenceReviewQueue.build_signals(transcript_segments, diagnostics)
        queue = ConfidenceReviewQueue.build(snapshot_content, signals)
        queue.apply_action("item-id-1", ReviewAction.ACCEPT)
        queue.save(Path("runtime/reviews/meeting-abc.json"))
        restored = ConfidenceReviewQueue.load(Path("runtime/reviews/meeting-abc.json"))

    Protocol state integration::

        final_items = queue.get_final_items(ItemType.ACTION_ITEM)
        # returns item texts after review decisions are applied
    """

    def __init__(self, meeting_id: str, snapshot_id: str) -> None:
        self.meeting_id = meeting_id
        self.snapshot_id = snapshot_id
        self._items: list[ReviewQueueItem] = []
        self._all_items_by_type: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Build queue from protocol snapshot
    # ------------------------------------------------------------------

    @classmethod
    def build_signals(
        cls,
        transcript_segments: list[dict[str, Any]],
        engine_diagnostics: dict[str, Any] | None = None,
    ) -> TranscriptSignals:
        """Derive uncertainty signals from raw transcript segment data.

        Args:
            transcript_segments: list of dicts with keys confidence_score,
                speaker_name, manual_correction (matching ORM TranscriptSegment fields)
            engine_diagnostics: dict returned by ProtocolEngine.last_diagnostics
        """
        signals = TranscriptSignals()
        if engine_diagnostics:
            signals.fallback_used = bool(engine_diagnostics.get("fallback_used"))
        if not transcript_segments:
            return signals

        confidences = [
            float(s.get("confidence_score", 1.0)) for s in transcript_segments
        ]
        signals.min_confidence = min(confidences)
        signals.avg_confidence = sum(confidences) / len(confidences)
        signals.has_unresolved_speakers = any(
            s.get("speaker_name", "") == UNRESOLVED_SPEAKER_LABEL
            for s in transcript_segments
        )
        # Conflicting: manually corrected segment but still very low confidence
        signals.conflicting_segments = sum(
            1 for s in transcript_segments
            if s.get("manual_correction") and float(s.get("confidence_score", 1.0)) < LOW_TRANSCRIPT_CONFIDENCE_THRESHOLD
        )

        return signals

    @classmethod
    def build(
        cls,
        meeting_id: str,
        snapshot_id: str,
        snapshot_content: dict[str, list[str]],
        signals: TranscriptSignals,
    ) -> "ConfidenceReviewQueue":
        """Build a ranked review queue from snapshot content and transcript signals.

        Only items that have at least one uncertainty signal are queued.
        The queue is sorted by severity (HIGH first).
        """
        queue = cls(meeting_id=meeting_id, snapshot_id=snapshot_id)
        item_counter = 0

        type_map: list[tuple[ItemType, str]] = [
            (ItemType.DECISION, "decision"),
            (ItemType.ACTION_ITEM, "action_item"),
            (ItemType.OPEN_QUESTION, "open_question"),
        ]
        for item_type, content_key in type_map:
            texts = list(snapshot_content.get(content_key + "s", snapshot_content.get(content_key, [])))
            queue._all_items_by_type[item_type.value] = texts
            for text in texts:
                reasons = cls._derive_reasons(text, signals)
                if not reasons:
                    continue
                item_id = f"{snapshot_id}-{item_type.value}-{item_counter}"
                item_counter += 1
                queue._items.append(
                    ReviewQueueItem(
                        item_id=item_id,
                        item_type=item_type,
                        item_text=text,
                        reasons=reasons,
                        severity=_severity(reasons),
                    )
                )

        # Rank: HIGH first, then MEDIUM, then LOW
        queue._items.sort(key=lambda i: _SEVERITY_ORDER[i.severity])
        return queue

    @staticmethod
    def _derive_reasons(
        text: str,
        signals: TranscriptSignals,
    ) -> list[ReviewReason]:
        """Return reason codes applicable to an item given the transcript signals."""
        reasons: list[ReviewReason] = []

        if signals.fallback_used:
            reasons.append(ReviewReason.FALLBACK_PATH)

        if signals.has_unresolved_speakers:
            reasons.append(ReviewReason.UNRESOLVED_SPEAKER)
        elif signals.min_confidence < LOW_SPEAKER_CONFIDENCE_THRESHOLD:
            reasons.append(ReviewReason.LOW_SPEAKER_CONFIDENCE)

        if signals.avg_confidence < LOW_TRANSCRIPT_CONFIDENCE_THRESHOLD:
            reasons.append(ReviewReason.LOW_TRANSCRIPT_CONFIDENCE)

        if signals.conflicting_segments > 0:
            reasons.append(ReviewReason.CONFLICTING_EXTRACTION)

        return reasons

    # ------------------------------------------------------------------
    # Review actions
    # ------------------------------------------------------------------

    def apply_action(
        self,
        item_id: str,
        action: ReviewAction,
        edited_text: str | None = None,
    ) -> None:
        """Apply a user review decision to a queued item.

        Raises ValueError if item_id is not found or if action=EDIT without text.
        """
        item = self._find(item_id)
        if action == ReviewAction.EDIT and not edited_text:
            raise ValueError(f"edited_text is required when action is EDIT (item {item_id!r})")
        item.action = action
        item.edited_text = edited_text if action == ReviewAction.EDIT else None

    def accept_all(self) -> None:
        """Accept all pending items (convenience method for bulk approval)."""
        for item in self._items:
            if not item.is_reviewed():
                item.action = ReviewAction.ACCEPT

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    @property
    def items(self) -> list[ReviewQueueItem]:
        """All items in severity order (not mutated externally)."""
        return list(self._items)

    @property
    def pending_count(self) -> int:
        return sum(1 for i in self._items if not i.is_reviewed())

    def get_final_items(self, item_type: ItemType) -> list[str]:
        """Return effective item texts after review decisions, excluding dismissed items.

        Items that were never queued (no uncertainty signals) are returned as-is.
        """
        all_texts = self._all_items_by_type.get(item_type.value, [])
        queue_by_text: dict[str, ReviewQueueItem] = {
            i.item_text: i
            for i in self._items
            if i.item_type == item_type
        }
        result = []
        for text in all_texts:
            qi = queue_by_text.get(text)
            if qi is None:
                result.append(text)
            elif not qi.is_dismissed():
                result.append(qi.effective_text())
        return result

    def _find(self, item_id: str) -> ReviewQueueItem:
        for item in self._items:
            if item.item_id == item_id:
                return item
        raise ValueError(f"Review item {item_id!r} not found in queue.")

    # ------------------------------------------------------------------
    # Persistence (local JSON – ADR-0011)
    # ------------------------------------------------------------------

    def save(self, path: Path, *, install_root: Path | None = None) -> None:
        """Persist queue state to a local runtime/reviews JSON file."""
        path = _resolve_review_store_path(path, install_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "meeting_id": self.meeting_id,
            "snapshot_id": self.snapshot_id,
            "all_items_by_type": self._all_items_by_type,
            "items": [
                {
                    "item_id": i.item_id,
                    "item_type": i.item_type.value,
                    "item_text": i.item_text,
                    "reasons": [r.value for r in i.reasons],
                    "severity": i.severity.value,
                    "action": i.action.value,
                    "edited_text": i.edited_text,
                }
                for i in self._items
            ],
        }
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Review queue saved: %s (%d items)", path, len(self._items))

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        install_root: Path | None = None,
    ) -> "ConfidenceReviewQueue":
        """Restore queue state from a local runtime/reviews JSON file."""
        path = _resolve_review_store_path(path, install_root)
        raw = json.loads(path.read_text(encoding="utf-8"))
        queue = cls(meeting_id=raw["meeting_id"], snapshot_id=raw["snapshot_id"])
        queue._all_items_by_type = raw.get("all_items_by_type", {})
        for entry in raw.get("items", []):
            queue._items.append(
                ReviewQueueItem(
                    item_id=entry["item_id"],
                    item_type=ItemType(entry["item_type"]),
                    item_text=entry["item_text"],
                    reasons=[ReviewReason(r) for r in entry["reasons"]],
                    severity=ReviewSeverity(entry["severity"]),
                    action=ReviewAction(entry["action"]),
                    edited_text=entry.get("edited_text"),
                )
            )
        return queue
