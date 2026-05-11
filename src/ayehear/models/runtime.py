from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic import model_validator


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
    language: str = "de"
    supported_languages: list[str] = Field(default_factory=lambda: ["de", "en"])

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_language_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        if "language" not in payload and "protocol_language" in payload:
            payload["language"] = payload["protocol_language"]
        if "supported_languages" not in payload and "protocol_language_options" in payload:
            payload["supported_languages"] = payload["protocol_language_options"]
        return payload

    @property
    def protocol_language(self) -> str:
        return self.language

    @protocol_language.setter
    def protocol_language(self, value: str) -> None:
        self.language = value

    @property
    def protocol_language_options(self) -> list[str]:
        return self.supported_languages


class ModelSettings(BaseModel):
    whisper_profile: str = "balanced"
    whisper_model: str = "TheChola/whisper-large-v3-turbo-german-faster-whisper"
    ollama_model: str = "mistral:7b"


class PrivacySettings(BaseModel):
    wav_persistence_enabled: bool = False
    wav_retention_days: int = 7
    wav_delete_on_meeting_end: bool = False
    wav_output_dir: str = "runtime/wav"
    review_retention_days: int = 7
    trace_retention_days: int = 7


class RuntimeConfig(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    speaker_identification: SpeakerSettings = Field(default_factory=SpeakerSettings)
    protocol: ProtocolSettings = Field(default_factory=ProtocolSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
