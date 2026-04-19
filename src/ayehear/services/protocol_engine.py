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

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ayehear.storage.repositories import (
        ProtocolSnapshotRepository,
        TranscriptSegmentRepository,
    )

logger = logging.getLogger(__name__)


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
