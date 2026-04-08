from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AudioCaptureProfile:
    sample_rate_hz: int
    channels: int
    frame_size: int


class AudioCaptureService:
    def __init__(self, profile: AudioCaptureProfile) -> None:
        self.profile = profile

    def describe_input(self) -> str:
        return "Windows default microphone"
