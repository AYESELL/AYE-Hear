"""Tests for HEAR-094 / HEAR-139: Whisper model defaults."""
import unittest

from ayehear.models.runtime import ModelSettings, RuntimeConfig
from ayehear.services.transcription import TranscriptionService

THECHOLA_MODEL = "TheChola/whisper-large-v3-turbo-german-faster-whisper"


class TestModelSettingsSmall(unittest.TestCase):
    """ModelSettings defaults now use TheChola DE-optimized model as whisper_model (HEAR-139)."""

    def test_default_whisper_model_is_thechola_german(self):
        s = ModelSettings()
        assert s.whisper_model == THECHOLA_MODEL

    def test_runtime_config_default_whisper_model_is_thechola_german(self):
        cfg = RuntimeConfig()
        assert cfg.models.whisper_model == THECHOLA_MODEL

    def test_default_language_model_map_contains_de_and_en(self):
        s = ModelSettings()
        assert s.whisper_model_by_language["de"] == THECHOLA_MODEL
        assert s.whisper_model_by_language["en"] == "small"

    def test_runtime_config_default_language_model_map_contains_de_and_en(self):
        cfg = RuntimeConfig()
        assert cfg.models.whisper_model_by_language["de"] == THECHOLA_MODEL
        assert cfg.models.whisper_model_by_language["en"] == "small"

    def test_can_override_to_base(self):
        s = ModelSettings(whisper_model="base")
        assert s.whisper_model == "base"

    def test_whisper_profile_default_unchanged(self):
        s = ModelSettings()
        assert s.whisper_profile == "balanced"


class TestTranscriptionServiceModelName(unittest.TestCase):
    """TranscriptionService uses injected model_name."""

    def test_default_model_name_is_thechola_german(self):
        # HEAR-139: default aligned to TheChola/whisper-large-v3-turbo-german-faster-whisper
        svc = TranscriptionService()
        assert svc.model_name == THECHOLA_MODEL

    def test_override_model_name_to_small(self):
        svc = TranscriptionService(model_name="small")
        assert svc.model_name == "small"

    def test_runtime_config_drives_model_name(self):
        """Simulate window.py passing whisper_model from RuntimeConfig."""
        cfg = RuntimeConfig()
        svc = TranscriptionService(model_name=cfg.models.whisper_model)
        assert svc.model_name == THECHOLA_MODEL


if __name__ == "__main__":
    unittest.main()
