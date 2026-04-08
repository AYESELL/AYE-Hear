from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SpeakerMatch:
    speaker_name: str
    confidence: float
    status: str


class SpeakerManager:
    def score_match(self, speaker_name: str, confidence: float) -> SpeakerMatch:
        if confidence >= 0.85:
            status = "high"
        elif confidence >= 0.65:
            status = "medium"
        else:
            status = "low"
        return SpeakerMatch(speaker_name=speaker_name, confidence=confidence, status=status)
