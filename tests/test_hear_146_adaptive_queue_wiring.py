"""HEAR-146: AdaptiveTranscriptionQueue wiring in MainWindow runtime loop.

Tests cover:
- Queue is instantiated in _start_audio_pipeline
- Queue is flushed and cleared in _stop_audio_pipeline
- Segments pushed when CPU is high are batched (not immediately transcribed)
- Segments pushed when CPU is normal are immediately processed
- flush_all is called on meeting stop to drain remaining segments
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())
    return win


def _make_segment(start_ms: int = 0, end_ms: int = 1000, is_silence: bool = False):
    from ayehear.services.audio_capture import AudioSegment
    samples = np.zeros((512,), dtype=np.float32) if is_silence else (
        np.random.default_rng(seed=99).random(512).astype(np.float32) * 0.3
    )
    rms = float(np.sqrt(np.mean(samples ** 2)))
    return AudioSegment(
        captured_at=datetime.now(timezone.utc),
        start_ms=start_ms,
        end_ms=end_ms,
        samples=samples,
        rms=rms,
        is_silence=is_silence,
    )


# ===========================================================================
# Queue lifecycle: start / stop
# ===========================================================================

class TestAdaptiveQueueLifecycle:
    def test_queue_is_none_before_pipeline_start(self, qapp):
        win = _make_window(qapp)
        assert win._adaptive_queue is None
        win.deleteLater()
        qapp.processEvents()

    def test_queue_created_on_start_audio_pipeline(self, qapp):
        win = _make_window(qapp)
        win._active_meeting_id = "mtg-queue-001"

        with (
            patch("ayehear.services.audio_capture.AudioCaptureService.start"),
            patch("ayehear.services.audio_capture.AudioCaptureService.stop"),
            patch.object(win._asr_timer, "start"),
            patch.object(win._mic_level_widget, "set_active"),
        ):
            win._start_audio_pipeline()

        assert win._adaptive_queue is not None

        win.deleteLater()
        qapp.processEvents()

    def test_queue_flushed_and_cleared_on_stop_pipeline(self, qapp):
        """_stop_audio_pipeline must flush and clear the adaptive queue."""
        win = _make_window(qapp)
        win._active_meeting_id = "mtg-queue-002"

        mock_queue = MagicMock()
        win._adaptive_queue = mock_queue

        with (
            patch.object(win._asr_timer, "stop"),
            patch.object(win._mic_level_widget, "reset"),
        ):
            win._stop_audio_pipeline()

        mock_queue.flush_all.assert_called_once()
        assert win._adaptive_queue is None

        win.deleteLater()
        qapp.processEvents()


# ===========================================================================
# Queue batching behavior
# ===========================================================================

class TestAdaptiveQueueBatching:
    def test_segment_pushed_to_queue_in_transcribe_buffer(self, qapp):
        """_transcribe_pending_buffer must push segment to queue when queue is active."""
        win = _make_window(qapp)
        win._active_meeting_id = "mtg-batch-001"

        # Seed the audio buffer with enough audio to trigger processing
        samples = np.random.default_rng(42).random(512).astype(np.float32)
        win._pending_audio_chunks = [samples]
        win._pending_start_ms = 0
        win._pending_end_ms = 2000
        win._pending_duration_ms = 2000

        mock_queue = MagicMock()
        win._adaptive_queue = mock_queue

        win._transcribe_pending_buffer(force=True)

        mock_queue.push.assert_called_once()
        pushed_segment = mock_queue.push.call_args[0][0]
        assert pushed_segment.start_ms == 0
        assert pushed_segment.end_ms == 2000

        win.deleteLater()
        qapp.processEvents()

    def test_segment_transcribed_directly_when_no_queue(self, qapp):
        """When no adaptive queue is active, _do_transcribe_segment must be called directly."""
        win = _make_window(qapp)
        win._active_meeting_id = "mtg-direct-001"
        win._adaptive_queue = None

        samples = np.random.default_rng(43).random(512).astype(np.float32)
        win._pending_audio_chunks = [samples]
        win._pending_start_ms = 0
        win._pending_end_ms = 2000
        win._pending_duration_ms = 2000

        with patch.object(win, "_do_transcribe_segment") as mock_transcribe:
            win._transcribe_pending_buffer(force=True)

        mock_transcribe.assert_called_once()

        win.deleteLater()
        qapp.processEvents()

    def test_high_cpu_batches_segments(self, qapp):
        """Under high CPU, AdaptiveTranscriptionQueue must defer calls to transcribe_fn."""
        from ayehear.services.transcription import AdaptiveTranscriptionQueue

        call_log: list = []
        queue = AdaptiveTranscriptionQueue(
            transcribe_fn=lambda seg: call_log.append(seg),
            cpu_high_threshold=10.0,   # very low threshold so any CPU qualifies as "high"
            batch_size=3,
        )

        seg1 = _make_segment(0, 500)
        seg2 = _make_segment(500, 1000)

        with patch("ayehear.services.transcription.get_cpu_load", return_value=95.0):
            queue.push(seg1)
            queue.push(seg2)

        # Under high CPU, not enough segments to flush batch_size=3
        assert len(call_log) == 0

    def test_high_cpu_flushes_on_batch_size(self, qapp):
        """When batch_size segments are accumulated under high CPU, queue flushes."""
        from ayehear.services.transcription import AdaptiveTranscriptionQueue

        call_log: list = []
        queue = AdaptiveTranscriptionQueue(
            transcribe_fn=lambda seg: call_log.append(seg),
            cpu_high_threshold=10.0,
            batch_size=2,
        )

        with patch("ayehear.services.transcription.get_cpu_load", return_value=95.0):
            queue.push(_make_segment(0, 500))
            queue.push(_make_segment(500, 1000))

        assert len(call_log) == 1  # merged segment

    def test_flush_all_drains_buffer(self, qapp):
        """flush_all must process any remaining buffered segments."""
        from ayehear.services.transcription import AdaptiveTranscriptionQueue

        call_log: list = []
        queue = AdaptiveTranscriptionQueue(
            transcribe_fn=lambda seg: call_log.append(seg),
            cpu_high_threshold=10.0,
            batch_size=5,
        )

        with patch("ayehear.services.transcription.get_cpu_load", return_value=95.0):
            queue.push(_make_segment(0, 500))
            queue.push(_make_segment(500, 1000))

        assert len(call_log) == 0
        queue.flush_all()
        assert len(call_log) == 1  # merged and processed
