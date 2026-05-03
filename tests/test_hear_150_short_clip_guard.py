from __future__ import annotations

import sys
from unittest.mock import patch

import numpy as np


def _make_window(qapp, whisper_model: str):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    cfg = RuntimeConfig()
    cfg.models.whisper_model = whisper_model

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        return MainWindow(runtime_config=cfg)


def _seed_pending_audio(win, duration_ms: int = 2000):
    win._pending_audio_chunks = [np.ones((512,), dtype=np.float32)]
    win._pending_start_ms = 0
    win._pending_end_ms = duration_ms
    win._pending_duration_ms = duration_ms


def test_large_turbo_requires_longer_window_before_asr(qapp):
    win = _make_window(qapp, "TheChola/whisper-large-v3-turbo-german-faster-whisper")
    _seed_pending_audio(win, duration_ms=2000)

    payload = win._consume_audio_buffer(force=False)

    assert payload is None
    win.deleteLater()
    qapp.processEvents()


def test_small_model_uses_default_window(qapp):
    win = _make_window(qapp, "small")
    _seed_pending_audio(win, duration_ms=2000)

    payload = win._consume_audio_buffer(force=False)

    assert payload is not None
    start_ms, end_ms, samples = payload
    assert start_ms == 0
    assert end_ms == 2000
    assert samples.shape[0] == 512

    win.deleteLater()
    qapp.processEvents()
