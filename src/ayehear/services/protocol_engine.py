from __future__ import annotations


class ProtocolEngine:
    def summarize_window(self, transcript_window: list[str]) -> dict[str, list[str]]:
        return {
            "decisions": [],
            "action_items": [],
            "open_questions": [],
            "summary": ["Protocol engine scaffold is ready for local LLM integration."],
        }
