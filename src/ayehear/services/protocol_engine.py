"""Protocol Engine — snapshot versioning and LLM-based extraction (HEAR-015).

Reads confirmed (high-confidence or manually-corrected) transcript segments
for a given meeting and produces an immutable protocol snapshot via
ProtocolSnapshotRepository.append(). Each call increments the snapshot version.

LLM integration uses the local Ollama runtime (offline-first, ADR-0006).
Falls back to a rule-based extractor when Ollama is not available.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ayehear.storage.repositories import (
        ProtocolSnapshotRepository,
        TranscriptSegmentRepository,
    )

logger = logging.getLogger(__name__)


@dataclass
class ProtocolContent:
    summary: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass
class ProtocolSnapshot:
    meeting_id: str
    version: int
    content: ProtocolContent
    snapshot_id: str | None = None


class ProtocolEngine:
    """Generates protocol snapshots from transcript data.

    Pass snapshot_repo / transcript_repo=None to use in unit tests or without a DB.
    """

    def __init__(
        self,
        snapshot_repo: "ProtocolSnapshotRepository | None" = None,
        transcript_repo: "TranscriptSegmentRepository | None" = None,
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "mistral",
    ) -> None:
        self._snapshots = snapshot_repo
        self._transcripts = transcript_repo
        self._ollama_base_url = self._validate_loopback_url(ollama_base_url)
        self._ollama_model = ollama_model

    @staticmethod
    def _validate_loopback_url(url: str) -> str:
        """Enforce that the Ollama URL points to a loopback address only (offline-first).

        AYE Hear must never transmit meeting data to external services.
        Raises ValueError if the hostname resolves to a non-loopback address.
        """
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        _LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}
        if host not in _LOOPBACK_HOSTS and not host.startswith("127."):
            raise ValueError(
                f"Ollama URL hostname {host!r} is not a loopback address. "
                "AYE Hear requires all LLM calls to remain local (offline-first, ADR-0006)."
            )
        return url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, meeting_id: str, db_session: "Session | None" = None) -> ProtocolSnapshot:
        """Generate a new immutable protocol snapshot for the given meeting.

        Reads all non-silence, reviewed transcript segments, extracts structured
        content via LLM (or rule-based fallback), then appends a new versioned
        snapshot to the repository.
        """
        lines = self._load_transcript_lines(meeting_id)
        content = self._extract_content(lines)

        if self._snapshots is None:
            return ProtocolSnapshot(
                meeting_id=meeting_id,
                version=1,
                content=content,
            )

        snapshot_row = self._snapshots.append(
            meeting_id=meeting_id,
            content={
                "summary": content.summary,
                "decisions": content.decisions,
                "action_items": content.action_items,
                "open_questions": content.open_questions,
            },
        )

        for item_text in content.action_items:
            try:
                self._snapshots.add_action_item(snapshot_row.id, item_text, "")
            except Exception as exc:
                logger.warning("Could not persist action item: %s", exc)

        return ProtocolSnapshot(
            meeting_id=meeting_id,
            version=snapshot_row.snapshot_version,
            content=content,
            snapshot_id=snapshot_row.id,
        )

    def summarize_window(self, transcript_window: list[str]) -> dict[str, list[str]]:
        """Backward-compatible method used by existing tests and UI callers."""
        content = self._extract_content(transcript_window)
        return {
            "decisions": content.decisions,
            "action_items": content.action_items,
            "open_questions": content.open_questions,
            "summary": content.summary,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_transcript_lines(self, meeting_id: str) -> list[str]:
        if self._transcripts is None:
            return []
        try:
            # list_for_protocol() excludes silence and returns segments in
            # chronological order; speaker_name already reflects any manual
            # corrections applied via apply_correction() (HEAR-022 / ADR-0007).
            segments = self._transcripts.list_for_protocol(meeting_id)
            return [
                f"[{s.start_ms}ms] {s.speaker_name}: {s.text}"
                for s in segments
                if s.text
            ]
        except Exception as exc:
            logger.error("Failed to load transcript for %s: %s", meeting_id, exc)
            return []

    def _extract_content(self, lines: list[str]) -> ProtocolContent:
        if not lines:
            return ProtocolContent(
                summary=["No transcript content available."],
            )

        try:
            return self._extract_via_ollama(lines)
        except Exception as exc:
            logger.info("Ollama unavailable (%s), using rule-based extraction.", exc)
            return self._extract_rule_based(lines)

    def _extract_via_ollama(self, lines: list[str]) -> ProtocolContent:
        """Call local Ollama API for structured extraction."""
        transcript_text = "\n".join(lines)
        prompt = (
            "You are a meeting assistant. Extract a structured protocol from the "
            "following transcript. Reply with JSON only (no markdown).\n"
            "Schema: {\"summary\": [...], \"decisions\": [...], \"action_items\": [...], \"open_questions\": [...]}\n\n"
            f"Transcript:\n{transcript_text}"
        )

        payload = json.dumps({
            "model": self._ollama_model,
            "prompt": prompt,
            "stream": False,
        }).encode()

        req = urllib.request.Request(
            f"{self._ollama_base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            raw = body.get("response", "{}")

        data = json.loads(raw)
        return ProtocolContent(
            summary=data.get("summary", []),
            decisions=data.get("decisions", []),
            action_items=data.get("action_items", []),
            open_questions=data.get("open_questions", []),
        )

    @staticmethod
    def _extract_rule_based(lines: list[str]) -> ProtocolContent:
        """Minimal rule-based extractor used as Ollama fallback."""
        decisions: list[str] = []
        action_items: list[str] = []
        open_questions: list[str] = []

        decision_keywords = re.compile(
            r"\b(wir entscheiden|entschieden|beschlossen|agreed|decided)\b", re.IGNORECASE
        )
        action_keywords = re.compile(
            r"\b(bitte|todo|action item|aufgabe|should|must|will)\b", re.IGNORECASE
        )
        question_keywords = re.compile(r"\?$|offen|unklar|zu klaeren", re.IGNORECASE)

        for line in lines:
            text = line.split(": ", 1)[-1] if ": " in line else line
            if decision_keywords.search(text):
                decisions.append(text)
            elif action_keywords.search(text):
                action_items.append(text)
            elif question_keywords.search(text):
                open_questions.append(text)

        summary = [f"Meeting recorded: {len(lines)} transcript segment(s)."]
        return ProtocolContent(
            summary=summary,
            decisions=decisions,
            action_items=action_items,
            open_questions=open_questions,
        )
