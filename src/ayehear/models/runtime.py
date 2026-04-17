from __future__ import annotations

from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    name: str = "AYE Hear"
    environment: str = "development"
    autosave_interval_seconds: int = 30


class AudioSettings(BaseModel):
    sample_rate_hz: int = 16000
    channels: int = 1
    frame_size: int = 512
    use_windows_default_input: bool = True


class SpeakerSettings(BaseModel):
    enrollment_seconds: int = 8
    high_confidence_threshold: float = 0.85
    medium_confidence_threshold: float = 0.65


class ProtocolSettings(BaseModel):
    update_interval_seconds: int = 45
    minimum_confidence: float = 0.65
    meeting_modes: list[str] = Field(default_factory=lambda: ["internal", "external"])
    protocol_language: str = "Deutsch"
    protocol_language_options: list[str] = Field(
        default_factory=lambda: ["Deutsch", "English", "Francais"]
    )


class ModelSettings(BaseModel):
    whisper_profile: str = "balanced"
    ollama_model: str = "mistral:7b"


class RuntimeConfig(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    speaker_identification: SpeakerSettings = Field(default_factory=SpeakerSettings)
    protocol: ProtocolSettings = Field(default_factory=ProtocolSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
