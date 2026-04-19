"""Tests for HEAR-115: ASR profile tuning — benchmark-backed small/balanced decision.

HEAR-113 benchmark (2026-04-19, i9-12900K, CPU-only, int8/beam=3):
  small: 74.29% accuracy, 11.7 s, 585.9 MB RAM  <- best_accuracy_model
  base:  71.43% accuracy,  3.9 s, 337.0 MB RAM

Decision: keep whisper-small / balanced as the default profile.
"""
import unittest

from ayehear.models.runtime import ModelSettings, RuntimeConfig
from ayehear.services.transcription import TranscriptionService, _PROFILES


class TestHEAR115ProfileDecision(unittest.TestCase):

    def test_transcription_service_default_model_is_small(self):
        svc = TranscriptionService()
        assert svc.model_name == "small"

    def test_transcription_service_default_profile_is_balanced(self):
        svc = TranscriptionService()
        assert svc.active_profile() == "balanced"

    def test_config_and_service_defaults_are_coherent(self):
        cfg = RuntimeConfig()
        svc = TranscriptionService()
        assert cfg.models.whisper_model == svc.model_name
        assert cfg.models.whisper_profile == svc.active_profile()

    def test_window_wiring_delivers_small_balanced(self):
        """Simulate the window.py injection path: config drives TranscriptionService."""
        cfg = RuntimeConfig()
        svc = TranscriptionService(
            model_name=cfg.models.whisper_model,
            profile=cfg.models.whisper_profile,
        )
        assert svc.model_name == "small"
        assert svc.active_profile() == "balanced"

    def test_balanced_profile_uses_int8_cpu_safe(self):
        """balanced profile must use int8 compute — CPU-safe per ADR-0008."""
        assert _PROFILES["balanced"]["compute_type"] == "int8"

    def test_can_override_to_base_for_lower_resource_targets(self):
        svc = TranscriptionService(model_name="base")
        assert svc.model_name == "base"


if __name__ == "__main__":
    unittest.main()
