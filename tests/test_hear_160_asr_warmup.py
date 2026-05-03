"""HEAR-160: Background ASR model warm-up in TranscriptionService.

WhisperModel (1.5 GB) was loaded lazily on the first audio chunk, causing
10–30 s of poor quality / nonsense output at the start of every meeting.

Fix: warmup() loads the model in a background daemon thread at app start.
Subsequent calls to transcribe_segment() find the model already ready.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch, call

import pytest

from ayehear.services.transcription import TranscriptionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(**kwargs) -> TranscriptionService:
    defaults = dict(model_name="small", profile="balanced", language="de")
    defaults.update(kwargs)
    return TranscriptionService(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWarmup:
    """HEAR-160: warmup() and is_ready behaviour."""

    def test_is_ready_false_before_warmup(self):
        """is_ready must be False until warmup completes."""
        svc = _make_service()
        assert svc.is_ready is False

    def test_warmup_sets_is_ready_true(self):
        """warmup() must set is_ready=True after model load (mocked)."""
        svc = _make_service()

        fake_model = MagicMock()
        with patch("ayehear.services.transcription._resolve_model_source", return_value=("small", {})), \
             patch("ayehear.services.transcription._PROFILES", {"balanced": {"compute_type": "int8", "beam_size": 3}}), \
             patch("faster_whisper.WhisperModel", return_value=fake_model, create=True):
            # Patch the import inside the method
            with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=MagicMock(return_value=fake_model))}):
                svc.warmup()
                # Give the background thread up to 3 s to complete
                svc._model_ready.wait(timeout=3.0)

        assert svc.is_ready is True

    def test_warmup_idempotent_when_model_already_set(self):
        """Calling warmup() again when model is loaded is a no-op."""
        svc = _make_service()
        fake_model = MagicMock()
        svc._model = fake_model  # simulate already loaded

        svc.warmup()  # should not start a thread or crash

        assert svc.is_ready is True
        assert svc._model is fake_model

    def test_warmup_sets_ready_even_on_import_error(self):
        """If faster-whisper is missing, is_ready is still set (no forever-block)."""
        svc = _make_service()

        with patch.dict("sys.modules", {"faster_whisper": None}):
            svc.warmup()
            # Wait up to 3 s for the background thread to finish (and fail gracefully)
            svc._model_ready.wait(timeout=3.0)

        # is_ready must be True even though model load failed, so callers don't block
        assert svc.is_ready is True
        # _model stays None — will be retried lazily on first chunk
        assert svc._model is None

    def test_multiple_warmup_calls_do_not_spawn_multiple_threads(self):
        """Rapid repeated warmup() calls must not spawn redundant threads."""
        svc = _make_service()
        fake_model = MagicMock()
        svc._model = fake_model  # already loaded
        svc._model_ready.set()

        # All of these should be instant no-ops
        for _ in range(5):
            svc.warmup()

        assert svc.is_ready is True

    def test_lock_and_event_are_per_instance(self):
        """Each TranscriptionService instance has its own lock and event."""
        svc1 = _make_service()
        svc2 = _make_service()

        assert svc1._model_load_lock is not svc2._model_load_lock
        assert svc1._model_ready is not svc2._model_ready


class TestRunAsrDoubleCheckedLocking:
    """HEAR-160: _run_asr() uses double-checked locking for thread-safe model load."""

    def test_run_asr_loads_model_once_under_concurrency(self):
        """Two threads calling _run_asr() must not create two model instances."""
        svc = _make_service()
        created = []

        def fake_whisper_model(model_path, device, compute_type, **kwargs):
            time.sleep(0.05)  # simulate load latency
            m = MagicMock()
            m.transcribe = MagicMock(return_value=(iter([]), MagicMock(language="de")))
            created.append(m)
            return m

        dummy_samples = [0.0] * 16000

        import sys
        fake_fw = MagicMock()
        fake_fw.WhisperModel.side_effect = fake_whisper_model

        with patch.dict(sys.modules, {"faster_whisper": fake_fw}), \
             patch("ayehear.services.transcription._resolve_model_source", return_value=("small", {})):

            results = []
            errors = []

            def worker():
                try:
                    r = svc._run_asr(dummy_samples)
                    results.append(r)
                except Exception as e:
                    errors.append(e)

            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start(); t2.start()
            t1.join(timeout=5); t2.join(timeout=5)

        assert not errors, f"Unexpected errors: {errors}"
        # Model must have been created exactly once despite two concurrent calls
        assert len(created) == 1, f"Expected 1 model instance, got {len(created)}"
