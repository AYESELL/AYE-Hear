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
from typing import TYPE_CHECKING, Any

from ayehear.services.action_item_quality import ActionItemQuality, ActionItemQualityEngine
from ayehear.services.confidence_review import ConfidenceReviewQueue
from ayehear.services.protocol_traceability import TraceabilityStore

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ayehear.storage.repositories import (
        ProtocolSnapshotRepository,
        TranscriptSegmentRepository,
    )

logger = logging.getLogger(__name__)


def _coerce_str_list(value: Any) -> list[str]:
    """Coerce an LLM-returned value to a list of strings (HEAR-124).

    LLMs sometimes return a plain string or a nested dict instead of
    ``list[str]``.  This helper normalises any such value so that
    downstream code never receives an unexpected type.
    """
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        # Flatten dict values to strings when the LLM wraps items in a nested object.
        return [str(v) for v in value.values() if v]
    return []


def _resource_snapshot() -> dict:
    """Return current CPU% and RAM MB (HEAR-095). Returns empty dict if psutil unavailable."""
    try:
        import psutil  # type: ignore[import-untyped]
        process = psutil.Process()
        return {
            "cpu_pct": psutil.cpu_percent(interval=None),
            "ram_mb": round(process.memory_info().rss / (1024 * 1024), 1),
        }
    except Exception:
        return {}


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
    action_item_quality: list[ActionItemQuality] = field(default_factory=list)
    review_queue: ConfidenceReviewQueue | None = None
    trace_store: TraceabilityStore | None = None


class OllamaModelUnavailableError(RuntimeError):
    """Raised when the configured Ollama model is not available locally."""


class ProtocolEngine:
    """Generates protocol snapshots from transcript data.

    Pass snapshot_repo / transcript_repo=None to use in unit tests or without a DB.
    """

    def __init__(
        self,
        snapshot_repo: "ProtocolSnapshotRepository | None" = None,
        transcript_repo: "TranscriptSegmentRepository | None" = None,
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "mistral:7b",
        language: str = "Deutsch",
        fallback_enabled: bool = True,
    ) -> None:
        self._snapshots = snapshot_repo
        self._transcripts = transcript_repo
        self._ollama_base_url = self._validate_loopback_url(ollama_base_url)
        self._ollama_model = ollama_model
        self._language = language
        self._fallback_enabled = fallback_enabled
        self._quality_engine = ActionItemQualityEngine(language=language)
        self._last_diagnostics: dict[str, Any] = {
            "status": "idle",
            "reason": "",
            "fallback_used": False,
            "model": self._ollama_model,
            "available_models": [],
        }

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

    @property
    def last_diagnostics(self) -> dict[str, Any]:
        return {
            "status": self._last_diagnostics["status"],
            "reason": self._last_diagnostics["reason"],
            "fallback_used": self._last_diagnostics["fallback_used"],
            "model": self._last_diagnostics["model"],
            "available_models": list(self._last_diagnostics["available_models"]),
        }

    def generate(
        self,
        meeting_id: str,
        db_session: "Session | None" = None,
        *,
        allow_fallback: bool | None = None,
    ) -> ProtocolSnapshot:
        """Generate a new immutable protocol snapshot for the given meeting.

        Reads all non-silence, reviewed transcript segments, extracts structured
        content via LLM (or rule-based fallback), then appends a new versioned
        snapshot to the repository.
        """
        lines = self._load_transcript_lines(meeting_id)
        content = self._extract_content(lines, allow_fallback=allow_fallback)

        # V2-01 / HEAR-116: deterministic quality scoring — no model or network call
        qualities = self._quality_engine.score_many(content.action_items)

        _snapshot_content_dict: dict[str, list[str]] = {
            "decisions": content.decisions,
            "action_items": content.action_items,
            "open_questions": content.open_questions,
        }

        if self._snapshots is None:
            _local_snapshot_id = f"{meeting_id}-local"
            review_queue = self.build_review_queue(
                meeting_id=meeting_id,
                snapshot_id=_local_snapshot_id,
                snapshot_content=_snapshot_content_dict,
            )
            trace_store = self.build_trace_store(
                meeting_id=meeting_id,
                snapshot_id=_local_snapshot_id,
                snapshot_content=_snapshot_content_dict,
            )
            return ProtocolSnapshot(
                meeting_id=meeting_id,
                version=1,
                content=content,
                action_item_quality=qualities,
                review_queue=review_queue,
                trace_store=trace_store,
            )

        snapshot_row = self._snapshots.append(
            meeting_id=meeting_id,
            content={
                "summary": content.summary,
                **_snapshot_content_dict,
            },
        )

        for item_text, quality in zip(content.action_items, qualities):
            try:
                description = (
                    f"score:{quality.score} sharpening:{quality.needs_sharpening}"
                    + (f" reasons:{','.join(r.value for r in quality.reasons)}" if quality.reasons else "")
                )
                self._snapshots.add_action_item(snapshot_row.id, item_text, description)
            except Exception as exc:
                logger.warning("Could not persist action item: %s", exc)

        review_queue = self.build_review_queue(
            meeting_id=meeting_id,
            snapshot_id=snapshot_row.id,
            snapshot_content=_snapshot_content_dict,
        )
        trace_store = self.build_trace_store(
            meeting_id=meeting_id,
            snapshot_id=snapshot_row.id,
            snapshot_content=_snapshot_content_dict,
        )

        return ProtocolSnapshot(
            meeting_id=meeting_id,
            version=snapshot_row.snapshot_version,
            content=content,
            snapshot_id=snapshot_row.id,
            action_item_quality=qualities,
            review_queue=review_queue,
            trace_store=trace_store,
        )

    def summarize_window(
        self,
        transcript_window: list[str],
        *,
        allow_fallback: bool | None = None,
    ) -> dict[str, list[str]]:
        """Backward-compatible method used by existing tests and UI callers."""
        content = self._extract_content(transcript_window, allow_fallback=allow_fallback)
        return {
            "decisions": content.decisions,
            "action_items": content.action_items,
            "open_questions": content.open_questions,
            "summary": content.summary,
        }

    def available_models(self) -> list[str]:
        """Return the locally available Ollama model names."""
        req = urllib.request.Request(
            f"{self._ollama_base_url}/api/tags",
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())

        models: list[str] = []
        for entry in body.get("models", []):
            if not isinstance(entry, dict):
                continue
            model_name = entry.get("model") or entry.get("name")
            if isinstance(model_name, str) and model_name and model_name not in models:
                models.append(model_name)
        return models

    # ------------------------------------------------------------------
    # V2-01 / HEAR-116: Action-Item Quality Engine integration
    # ------------------------------------------------------------------

    def score_action_items(self, texts: list[str]) -> list[ActionItemQuality]:
        """Score action items deterministically. No network or model call."""
        return self._quality_engine.score_many(texts)

    @staticmethod
    def annotate_weak_items(
        items: list[str],
        qualities: list[ActionItemQuality],
    ) -> list[str]:
        """Return items with a sharpening annotation appended for weak items.

        Items that pass the sharpening threshold are returned unchanged.
        Reason codes use stable English enum values so annotations remain
        consistent across language settings.
        """
        result: list[str] = []
        for item, quality in zip(items, qualities):
            if quality.needs_sharpening and quality.reasons:
                codes = ", ".join(r.value for r in quality.reasons)
                result.append(f"{item} [⚠ needs sharpening: {codes}]")
            else:
                result.append(item)
        return result

    # ------------------------------------------------------------------
    # V2-12 / HEAR-117: Confidence Review Queue integration
    # ------------------------------------------------------------------

    def build_review_queue(
        self,
        meeting_id: str,
        snapshot_id: str,
        snapshot_content: dict[str, list[str]],
    ) -> ConfidenceReviewQueue:
        """Build a ranked confidence review queue for a protocol snapshot.

        Derives uncertainty signals from the meeting's transcript segments and
        the most recent engine diagnostics, then builds a severity-ranked queue
        of uncertain decisions, action items, and open questions.

        No network or model call is made. State must be persisted by the caller.
        """
        segment_dicts: list[dict[str, Any]] = []
        if self._transcripts is not None:
            try:
                segs = self._transcripts.list_for_meeting(meeting_id)
                segment_dicts = [
                    {
                        "id": s.id,
                        "confidence_score": s.confidence_score,
                        "speaker_name": s.speaker_name,
                        "manual_correction": s.manual_correction,
                    }
                    for s in segs
                ]
            except Exception as exc:
                logger.warning("Could not load segments for review queue: %s", exc)

        signals = ConfidenceReviewQueue.build_signals(
            segment_dicts, self.last_diagnostics
        )
        return ConfidenceReviewQueue.build(
            meeting_id=meeting_id,
            snapshot_id=snapshot_id,
            snapshot_content=snapshot_content,
            signals=signals,
        )

    def build_trace_store(
        self,
        meeting_id: str,
        snapshot_id: str,
        snapshot_content: dict[str, list[str]],
    ) -> TraceabilityStore:
        """Build a traceability store linking protocol items to transcript sources.

        Derives evidence type (DIRECT / INFERRED) from keyword overlap between each
        protocol item and the meeting's transcript segments.  Falls back to INFERRED
        for all items when the rule-based extractor was used.

        No network or model call is made. State must be persisted by the caller.
        """
        segment_dicts: list[dict[str, Any]] = []
        if self._transcripts is not None:
            try:
                segs = self._transcripts.list_for_meeting(meeting_id)
                segment_dicts = [
                    {
                        "id": s.id,
                        "start_ms": getattr(s, "start_ms", 0),
                        "end_ms": getattr(s, "end_ms", 0),
                        "speaker_name": s.speaker_name,
                        "confidence_score": s.confidence_score,
                        "manual_correction": s.manual_correction,
                        "text": getattr(s, "text", ""),
                    }
                    for s in segs
                ]
            except Exception as exc:
                logger.warning("Could not load segments for trace store: %s", exc)

        fallback_used = bool(self._last_diagnostics.get("fallback_used", False))
        store = TraceabilityStore(snapshot_id=snapshot_id)
        store.build_links(snapshot_content, segment_dicts, fallback_used=fallback_used)
        return store

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

    def _set_diagnostics(
        self,
        *,
        status: str,
        reason: str,
        fallback_used: bool,
        available_models: list[str] | None = None,
    ) -> None:
        self._last_diagnostics = {
            "status": status,
            "reason": reason,
            "fallback_used": fallback_used,
            "model": self._ollama_model,
            "available_models": list(available_models or []),
        }

    def _ensure_model_available(self) -> list[str]:
        available_models = self.available_models()
        if not available_models:
            raise OllamaModelUnavailableError("No local Ollama models are available.")
        if self._ollama_model not in available_models:
            available = ", ".join(available_models)
            raise OllamaModelUnavailableError(
                f"Configured Ollama model '{self._ollama_model}' is unavailable. "
                f"Available models: {available}."
            )
        return available_models

    def _extract_content(
        self,
        lines: list[str],
        *,
        allow_fallback: bool | None = None,
    ) -> ProtocolContent:
        if not lines:
            return ProtocolContent(
                summary=["No transcript content available."],
            )

        use_fallback = self._fallback_enabled if allow_fallback is None else allow_fallback

        try:
            available_models = self._ensure_model_available()
            content = self._extract_via_ollama(lines)
            self._set_diagnostics(
                status="ollama",
                reason="Structured extraction completed.",
                fallback_used=False,
                available_models=available_models,
            )
            return content
        except Exception as exc:
            available_models = self._last_diagnostics.get("available_models", [])
            self._set_diagnostics(
                status="failed",
                reason=str(exc),
                fallback_used=False,
                available_models=available_models,
            )
            if not use_fallback:
                raise
            self._set_diagnostics(
                status="rule_based_fallback",
                reason=str(exc),
                fallback_used=True,
                available_models=available_models,
            )
            logger.info("Ollama unavailable (%s), using rule-based extraction.", exc)
            return self._extract_rule_based(lines)

    # Language → prompt instruction mapping (HEAR-093)
    _LANGUAGE_INSTRUCTIONS: dict[str, str] = {
        "Deutsch": (
            "Du bist ein Meeting-Assistent. Extrahiere ein strukturiertes Protokoll "
            "aus dem folgenden Transkript. Antworte ausschließlich mit JSON (kein Markdown). "
            "Schreibe alle Inhalte auf Deutsch."
        ),
        "English": (
            "You are a meeting assistant. Extract a structured protocol from the following "
            "transcript. Reply exclusively with JSON (no Markdown). "
            "Write all content in English."
        ),
        "Francais": (
            "Tu es un assistant de réunion. Extrais un protocole structuré du transcript "
            "suivant. Réponds uniquement avec du JSON (pas de Markdown). "
            "Rédige tout le contenu en français."
        ),
    }
    _DEFAULT_LANGUAGE_INSTRUCTION = _LANGUAGE_INSTRUCTIONS["Deutsch"]

    def _extract_via_ollama(self, lines: list[str]) -> ProtocolContent:
        """Call local Ollama API for structured extraction."""
        transcript_text = "\n".join(lines)
        instruction = self._LANGUAGE_INSTRUCTIONS.get(
            self._language, self._DEFAULT_LANGUAGE_INSTRUCTION
        )
        prompt = (
            f"{instruction}\n"
            "Schema: {\"summary\": [...], \"decisions\": [...], \"action_items\": [...], \"open_questions\": []}\n\n"
            f"Transkript:\n{transcript_text}"
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

        # HEAR-095: resource telemetry at LLM inference boundaries
        res_before = _resource_snapshot()
        if res_before:
            logger.debug(
                "LLM inference start — cpu_pct=%.1f ram_mb=%.1f model=%s",
                res_before.get("cpu_pct", 0), res_before.get("ram_mb", 0), self._ollama_model,
            )

        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            raw = body.get("response", "{}")

        res_after = _resource_snapshot()
        if res_after:
            logger.debug(
                "LLM inference end   — cpu_pct=%.1f ram_mb=%.1f",
                res_after.get("cpu_pct", 0), res_after.get("ram_mb", 0),
            )

        data = json.loads(raw)
        return ProtocolContent(
            summary=_coerce_str_list(data.get("summary")),
            decisions=_coerce_str_list(data.get("decisions")),
            action_items=_coerce_str_list(data.get("action_items")),
            open_questions=_coerce_str_list(data.get("open_questions")),
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
