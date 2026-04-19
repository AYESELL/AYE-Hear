from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ayehear.services.protocol_engine import ProtocolEngine


@dataclass
class ProtocolReplayResult:
    model: str
    status: str
    started_at: str
    duration_ms: int
    output_path: Path
    error: str | None = None


class ProtocolReplayService:
    """Replay one persisted transcript baseline across multiple Ollama models."""

    def __init__(
        self,
        *,
        ollama_base_url: str = "http://localhost:11434",
        language: str = "Deutsch",
    ) -> None:
        self._ollama_base_url = ollama_base_url
        self._language = language

    def discover_models(self, configured_models: Sequence[str] = ()) -> list[str]:
        """Return configured and locally installed models without duplicates."""
        ordered: list[str] = []
        for model in configured_models:
            if model and model not in ordered:
                ordered.append(model)

        probe_model = ordered[0] if ordered else "mistral:7b"
        engine = ProtocolEngine(
            ollama_base_url=self._ollama_base_url,
            ollama_model=probe_model,
            language=self._language,
            fallback_enabled=False,
        )
        try:
            local_models = engine.available_models()
        except Exception:
            local_models = []

        for model in local_models:
            if model and model not in ordered:
                ordered.append(model)
        return ordered

    def replay_baseline(
        self,
        baseline_path: Path,
        output_dir: Path,
        *,
        meeting_title: str,
        configured_models: Sequence[str] = (),
        models: Sequence[str] | None = None,
    ) -> list[ProtocolReplayResult]:
        baseline_lines = self._load_baseline_lines(baseline_path)
        if not baseline_lines:
            raise ValueError("Baseline transcript is empty.")

        selected_models = list(models) if models is not None else self.discover_models(configured_models)
        if not selected_models:
            raise ValueError("No Ollama models available for replay.")

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = self._slugify(meeting_title) or "replay"
        results: list[ProtocolReplayResult] = []

        for model in selected_models:
            engine = ProtocolEngine(
                ollama_base_url=self._ollama_base_url,
                ollama_model=model,
                language=self._language,
                fallback_enabled=False,
            )
            started_at = datetime.now().isoformat(timespec="seconds")
            started = time.perf_counter()
            error: str | None = None
            status = "success"
            draft_sections: dict[str, list[str]] | None = None

            try:
                draft_sections = engine.summarize_window(
                    baseline_lines,
                    allow_fallback=False,
                )
            except Exception as exc:
                status = "failed"
                error = str(exc)

            duration_ms = round((time.perf_counter() - started) * 1000)
            model_tag = self._slugify(model) or "model"
            output_path = output_dir / f"{safe_title}_{timestamp_tag}_{model_tag}-protocol.md"
            output_path.write_text(
                self._render_markdown(
                    meeting_title=meeting_title,
                    baseline_name=baseline_path.name,
                    model=model,
                    status=status,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    draft_sections=draft_sections,
                    error=error,
                ),
                encoding="utf-8",
            )
            results.append(
                ProtocolReplayResult(
                    model=model,
                    status=status,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    output_path=output_path,
                    error=error,
                )
            )

        manifest_path = output_dir / f"{safe_title}_{timestamp_tag}_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "baseline": str(baseline_path),
                    "language": self._language,
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "results": [self._result_to_dict(result) for result in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return results

    @staticmethod
    def _load_baseline_lines(baseline_path: Path) -> list[str]:
        text = baseline_path.read_text(encoding="utf-8")
        lines: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("Meeting Transcript") or line.startswith("Exported:"):
                continue
            lines.append(raw)
        return lines

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.strip().replace(":", "-")
        value = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
        return value.strip("_")[:60]

    @staticmethod
    def _result_to_dict(result: ProtocolReplayResult) -> dict[str, str | int | None]:
        data = asdict(result)
        data["output_path"] = str(result.output_path)
        return data

    def _render_markdown(
        self,
        *,
        meeting_title: str,
        baseline_name: str,
        model: str,
        status: str,
        started_at: str,
        duration_ms: int,
        draft_sections: dict[str, list[str]] | None,
        error: str | None,
    ) -> str:
        lines = [
            f"# Replay Protocol - {meeting_title}",
            "",
            f"- Baseline: {baseline_name}",
            f"- Model: {model}",
            f"- Language: {self._language}",
            f"- Started: {started_at}",
            f"- Duration Ms: {duration_ms}",
            f"- Status: {status}",
            "- Fallback Used: no",
            "",
        ]

        if error is not None:
            lines.extend([
                "## Error",
                error,
                "",
            ])
            return "\n".join(lines).strip() + "\n"

        assert draft_sections is not None
        for title, items in (
            ("Summary", draft_sections.get("summary", [])),
            ("Decisions", draft_sections.get("decisions", [])),
            ("Action Items", draft_sections.get("action_items", [])),
            ("Open Questions", draft_sections.get("open_questions", [])),
        ):
            lines.append(f"## {title}")
            if items:
                lines.extend(f"- {item}" for item in items)
            else:
                lines.append("- none")
            lines.append("")

        return "\n".join(lines).strip() + "\n"