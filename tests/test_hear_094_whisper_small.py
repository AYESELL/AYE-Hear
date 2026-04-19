"""Tests for HEAR-094: Whisper small model upgrade."""
import unittest

from ayehear.models.runtime import ModelSettings, RuntimeConfig
from ayehear.services.transcription import TranscriptionService


class TestModelSettingsSmall(unittest.TestCase):
    """ModelSettings defaults now use 'small' as whisper_model."""

    def test_default_whisper_model_is_small(self):
        s = ModelSettings()
        assert s.whisper_model == "small"

    def test_runtime_config_default_whisper_model_is_small(self):
        cfg = RuntimeConfig()
        assert cfg.models.whisper_model == "small"

    def test_can_override_to_base(self):
        s = ModelSettings(whisper_model="base")
        assert s.whisper_model == "base"

    def test_whisper_profile_default_unchanged(self):
        s = ModelSettings()
        assert s.whisper_profile == "balanced"


class TestTranscriptionServiceModelName(unittest.TestCase):
    """TranscriptionService uses injected model_name."""

    def test_default_model_name_is_small(self):
        # HEAR-115: default aligned to benchmark-backed 'small' decision (HEAR-113)
        svc = TranscriptionService()
        assert svc.model_name == "small"

    def test_override_model_name_to_small(self):
        svc = TranscriptionService(model_name="small")
        assert svc.model_name == "small"

    def test_runtime_config_drives_model_name(self):
        """Simulate window.py passing whisper_model from RuntimeConfig."""
        cfg = RuntimeConfig()
        svc = TranscriptionService(model_name=cfg.models.whisper_model)
        assert svc.model_name == "small"


if __name__ == "__main__":
    unittest.main()
