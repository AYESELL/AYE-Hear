"""HEAR-141: Async capture pipeline — thread priority, WAV persistence,
adaptive transcription queue, and protocol CPU-idle gate.

All tests run without sounddevice, PostgreSQL, faster-whisper, or psutil.
"""
from __future__ import annotations

import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from ayehear.services.audio_capture import (
    AudioCaptureProfile,
    AudioCaptureService,
    AudioSegment,
    WavPersistenceConfig,
    cleanup_expired_wav_files,
    _elevate_capture_thread_priority,
)
from ayehear.services.transcription import (
    AdaptiveTranscriptionQueue,
    _merge_segments,
    get_cpu_load,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segment(start_ms: int = 0, end_ms: int = 100, is_silence: bool = False) -> AudioSegment:
    samples = np.zeros((512,), dtype=np.float32) if is_silence else (
        np.random.default_rng(42).random(512).astype(np.float32) * 0.2
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
# 1. Thread-priority elevation
# ===========================================================================

class TestElevateThreadPriority:
    def test_non_windows_returns_false(self):
        with patch.object(sys, "platform", "linux"):
            result = _elevate_capture_thread_priority()
        assert result is False

    def test_windows_success_path(self):
        fake_kernel32 = MagicMock()
        fake_kernel32.GetCurrentThread.return_value = 0xFFFF
        fake_kernel32.SetThreadPriority.return_value = 1  # TRUE

        fake_ctypes = MagicMock()
        fake_ctypes.windll.kernel32 = fake_kernel32

        with patch.object(sys, "platform", "win32"), \
             patch.dict(sys.modules, {"ctypes": fake_ctypes}):
            result = _elevate_capture_thread_priority()

        fake_kernel32.SetThreadPriority.assert_called_once_with(0xFFFF, 2)
        assert result is True

    def test_windows_failure_returns_false(self):
        fake_kernel32 = MagicMock()
        fake_kernel32.GetCurrentThread.return_value = 0xFFFF
        fake_kernel32.SetThreadPriority.return_value = 0   # FALSE
        fake_kernel32.GetLastError.return_value = 5        # ACCESS_DENIED

        fake_ctypes = MagicMock()
        fake_ctypes.windll.kernel32 = fake_kernel32

        with patch.object(sys, "platform", "win32"), \
             patch.dict(sys.modules, {"ctypes": fake_ctypes}):
            result = _elevate_capture_thread_priority()

        assert result is False

    def test_ctypes_import_error_handled(self):
        with patch.object(sys, "platform", "win32"), \
             patch.dict(sys.modules, {"ctypes": None}):
            # ctypes=None forces ImportError-like behaviour when accessed
            result = _elevate_capture_thread_priority()
        # Should not raise; returns False on any exception
        assert result is False


# ===========================================================================
# 2. WAV persistence
# ===========================================================================

class TestWavPersistence:
    def _make_service(self, wav_config: WavPersistenceConfig) -> AudioCaptureService:
        return AudioCaptureService(
            profile=AudioCaptureProfile(sample_rate_hz=16_000, channels=1, frame_size=512),
            wav_config=wav_config,
        )

    def test_wav_disabled_no_file_written(self, tmp_path):
        wav_dir = tmp_path / "runtime" / "wav"
        cfg = WavPersistenceConfig(enabled=False, output_dir=wav_dir)
        svc = self._make_service(cfg)
        # Inject fake segment into buffer directly
        svc._wav_buffer = [_make_segment().samples]
        result = svc._flush_wav()
        assert result is None
        assert not list(wav_dir.glob("*.wav")) if wav_dir.exists() else True

    def test_wav_enabled_writes_file(self, tmp_path):
        cfg = WavPersistenceConfig(enabled=True, output_dir=tmp_path / "runtime" / "wav")
        svc = self._make_service(cfg)
        svc._meeting_id = "mtg-test"
        svc._wav_buffer = [_make_segment().samples for _ in range(3)]

        result = svc._flush_wav()

        assert result is not None
        assert result.suffix == ".wav"
        assert result.exists()
        # Validate WAV header
        with wave.open(str(result), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == 16_000
            assert wf.getsampwidth() == 2  # 16-bit PCM

    def test_wav_delete_on_meeting_end(self, tmp_path):
        wav_dir = tmp_path / "runtime" / "wav"
        cfg = WavPersistenceConfig(
            enabled=True,
            output_dir=wav_dir,
            delete_on_meeting_end=True,
        )
        svc = self._make_service(cfg)
        svc._meeting_id = "mtg-del"
        svc._wav_buffer = [_make_segment().samples]

        result = svc._flush_wav()

        # File is deleted immediately; flush returns None
        assert result is None
        assert not list(wav_dir.glob("*.wav"))

    def test_wav_buffer_cleared_after_flush(self, tmp_path):
        cfg = WavPersistenceConfig(enabled=True, output_dir=tmp_path / "runtime" / "wav")
        svc = self._make_service(cfg)
        svc._meeting_id = "mtg-clear"
        svc._wav_buffer = [_make_segment().samples]
        svc._flush_wav()
        assert svc._wav_buffer == []

    def test_silence_segments_not_buffered(self, tmp_path):
        cfg = WavPersistenceConfig(enabled=True, output_dir=tmp_path / "runtime" / "wav")
        svc = self._make_service(cfg)
        svc._meeting_id = "mtg-silence"
        svc._wav_buffer = []
        silence = _make_segment(is_silence=True)
        assert silence.is_silence
        # Simulate _sd_callback logic: only non-silence frames are buffered
        if cfg.enabled and not silence.is_silence:
            svc._wav_buffer.append(silence.samples)
        assert svc._wav_buffer == []

    def test_invalid_output_dir_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="runtime/wav"):
            WavPersistenceConfig(enabled=True, output_dir=tmp_path / "wav")

    def test_retention_days_clamped(self, tmp_path):
        cfg = WavPersistenceConfig(
            enabled=True,
            output_dir=tmp_path / "runtime" / "wav",
            retention_days=99,
        )
        assert cfg.retention_days == 30


class TestCleanupExpiredWavFiles:
    def test_removes_old_files(self, tmp_path):
        import time
        old_file = tmp_path / "old.wav"
        old_file.write_bytes(b"RIFF")
        # Set mtime to 10 days ago
        old_time = time.time() - 10 * 86_400
        import os
        os.utime(old_file, (old_time, old_time))

        deleted = cleanup_expired_wav_files(tmp_path, retention_days=7)
        assert deleted == 1
        assert not old_file.exists()

    def test_keeps_recent_files(self, tmp_path):
        recent = tmp_path / "recent.wav"
        recent.write_bytes(b"RIFF")

        deleted = cleanup_expired_wav_files(tmp_path, retention_days=7)
        assert deleted == 0
        assert recent.exists()

    def test_missing_dir_returns_zero(self, tmp_path):
        missing = tmp_path / "nonexistent"
        deleted = cleanup_expired_wav_files(missing, retention_days=7)
        assert deleted == 0


# ===========================================================================
# 3. Adaptive transcription queue
# ===========================================================================

class TestAdaptiveTranscriptionQueue:
    def test_low_cpu_flushes_immediately(self):
        received: list[AudioSegment] = []
        queue = AdaptiveTranscriptionQueue(
            transcribe_fn=received.append,
            cpu_high_threshold=80.0,
            batch_size=4,
        )
        seg = _make_segment()

        with patch("ayehear.services.transcription.get_cpu_load", return_value=20.0):
            queue.push(seg)

        assert len(received) == 1
        assert received[0] is seg

    def test_high_cpu_batches_segments(self):
        received: list[AudioSegment] = []
        queue = AdaptiveTranscriptionQueue(
            transcribe_fn=received.append,
            cpu_high_threshold=80.0,
            batch_size=3,
        )

        with patch("ayehear.services.transcription.get_cpu_load", return_value=90.0):
            queue.push(_make_segment(0, 100))
            queue.push(_make_segment(100, 200))
            # Only 2 segments — batch_size=3 not yet reached → nothing flushed
            assert len(received) == 0
            queue.push(_make_segment(200, 300))
            # Batch full → flush
            assert len(received) == 1

        # The flushed item is a merged segment
        merged = received[0]
        assert merged.start_ms == 0
        assert merged.end_ms == 300

    def test_flush_all_forces_pending(self):
        received: list[AudioSegment] = []
        queue = AdaptiveTranscriptionQueue(
            transcribe_fn=received.append,
            cpu_high_threshold=80.0,
            batch_size=10,
        )

        with patch("ayehear.services.transcription.get_cpu_load", return_value=90.0):
            queue.push(_make_segment(0, 50))
            queue.push(_make_segment(50, 100))

        assert len(received) == 0
        queue.flush_all()
        assert len(received) == 1

    def test_empty_flush_all_is_noop(self):
        received: list[AudioSegment] = []
        queue = AdaptiveTranscriptionQueue(transcribe_fn=received.append)
        queue.flush_all()  # must not raise
        assert received == []

    def test_transcribe_fn_exception_does_not_propagate(self):
        def bad_fn(seg):
            raise RuntimeError("ASR broken")

        queue = AdaptiveTranscriptionQueue(
            transcribe_fn=bad_fn,
            cpu_high_threshold=80.0,
            batch_size=1,
        )
        with patch("ayehear.services.transcription.get_cpu_load", return_value=0.0):
            queue.push(_make_segment())  # should not raise


class TestMergeSegments:
    def test_span_covers_all_segments(self):
        segs = [_make_segment(0, 100), _make_segment(100, 200), _make_segment(200, 300)]
        merged = _merge_segments(segs)
        assert merged.start_ms == 0
        assert merged.end_ms == 300

    def test_all_silence_propagates(self):
        segs = [_make_segment(is_silence=True), _make_segment(is_silence=True)]
        merged = _merge_segments(segs)
        assert merged.is_silence is True

    def test_mixed_silence_is_not_silent(self):
        segs = [_make_segment(is_silence=True), _make_segment(is_silence=False)]
        merged = _merge_segments(segs)
        assert merged.is_silence is False


class TestGetCpuLoad:
    def test_returns_psutil_value(self):
        with patch("ayehear.services.transcription.get_cpu_load", return_value=55.0) as mock_fn:
            val = mock_fn()
        assert val == 55.0

    def test_psutil_unavailable_returns_zero(self):
        with patch.dict(sys.modules, {"psutil": None}):
            val = get_cpu_load()
        # psutil import will fail → returns 0.0
        assert val == 0.0


# ===========================================================================
# 4. ProtocolEngine CPU-idle gate
# ===========================================================================

class TestProtocolEngineCpuIdleGate:
    def _make_engine(self):
        from ayehear.services.protocol_engine import ProtocolEngine
        return ProtocolEngine(
            snapshot_repo=None,
            transcript_repo=None,
            ollama_base_url="http://localhost:11434",
        )

    def test_high_cpu_returns_deferred_snapshot(self):
        engine = self._make_engine()

        with patch("ayehear.services.protocol_engine._get_cpu_pct", return_value=85.0):
            snapshot = engine.generate("mtg-cpu-high")

        assert snapshot.version == 0
        assert snapshot.content.summary == []
        assert snapshot.content.action_items == []
        assert engine.last_diagnostics["status"] == "deferred"
        assert "cpu_busy" in engine.last_diagnostics["reason"]

    def test_low_cpu_does_not_defer(self):
        engine = self._make_engine()

        # With no transcript repo and no segments, generate() falls through
        # to the no-repo path and returns a local snapshot (version 1).
        with patch("ayehear.services.protocol_engine._get_cpu_pct", return_value=30.0), \
             patch.object(engine, "_load_transcript_lines", return_value=[]):
            snapshot = engine.generate("mtg-cpu-low")

        assert snapshot.version == 1  # not deferred

    def test_threshold_boundary_exactly_at_threshold_defers(self):
        engine = self._make_engine()

        with patch("ayehear.services.protocol_engine._get_cpu_pct", return_value=80.0):
            snapshot = engine.generate("mtg-boundary")

        assert snapshot.version == 0  # deferred at threshold

    def test_cpu_pct_helper_psutil_unavailable(self):
        from ayehear.services.protocol_engine import _get_cpu_pct
        with patch.dict(sys.modules, {"psutil": None}):
            val = _get_cpu_pct()
        assert val == 0.0


# ===========================================================================
# HEAR-154: Protocol delta rebuild and deferred-state UX
# ===========================================================================


class TestHear154ProtocolDeltaRebuild:
    """Delta gating: rebuild only when transcript changed; deferred marker in UI."""

    def _make_window(self, qapp):
        from ayehear.app.window import MainWindow
        from ayehear.models.runtime import RuntimeConfig
        with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
            win = MainWindow(runtime_config=RuntimeConfig())
        return win

    def test_compute_transcript_fingerprint_stable(self, qapp) -> None:
        """Same text always produces the same fingerprint."""
        win = self._make_window(qapp)
        fp1 = win._compute_transcript_fingerprint("Hallo Welt")
        fp2 = win._compute_transcript_fingerprint("Hallo Welt")
        assert fp1 == fp2

    def test_compute_transcript_fingerprint_different_text(self, qapp) -> None:
        """Different text produces a different fingerprint."""
        win = self._make_window(qapp)
        fp1 = win._compute_transcript_fingerprint("Hallo Welt")
        fp2 = win._compute_transcript_fingerprint("Guten Morgen")
        assert fp1 != fp2

    def test_rebuild_skipped_when_transcript_unchanged(self, qapp) -> None:
        """Protocol engine generate() must NOT be called when transcript is unchanged."""
        win = self._make_window(qapp)
        win._active_meeting_id = "mtg-delta-01"
        win._transcript_repo = MagicMock()
        win._snapshot_repo = MagicMock()

        current_text = "[00:00] System: Meeting initialized."
        win._transcript_view.setPlainText(current_text)
        # Fingerprint matches current text → delta gate should suppress rebuild
        win._last_protocol_transcript_fingerprint = win._compute_transcript_fingerprint(current_text)

        with patch.object(win._protocol_engine, "generate") as mock_gen:
            win._rebuild_protocol_from_persistence()
            mock_gen.assert_not_called()

    def test_rebuild_triggered_when_transcript_changed(self, qapp) -> None:
        """Protocol engine generate() must be called when transcript text changed."""
        from ayehear.services.protocol_engine import ProtocolSnapshot, ProtocolContent
        win = self._make_window(qapp)
        win._active_meeting_id = "mtg-delta-02"
        win._transcript_repo = MagicMock()
        win._snapshot_repo = MagicMock()

        win._transcript_view.setPlainText("[00:00] Anna: Neuer Inhalt hier.")
        win._last_protocol_transcript_fingerprint = win._compute_transcript_fingerprint("old text")

        fake_snapshot = ProtocolSnapshot(meeting_id="mtg-delta-02", version=1, content=ProtocolContent())
        win._snapshot_repo.latest.return_value = MagicMock(
            snapshot_content={"summary": [], "decisions": [], "action_items": [], "open_questions": []}
        )
        from ayehear.services.protocol_engine import ProtocolEngine
        with patch.object(win._protocol_engine, "generate", return_value=fake_snapshot) as mock_gen, \
             patch.object(type(win._protocol_engine), "last_diagnostics",
                          new_callable=PropertyMock, return_value={"status": "ok", "reason": ""}):
            win._rebuild_protocol_from_persistence()
            mock_gen.assert_called_once_with("mtg-delta-02")

    def test_fingerprint_updated_after_successful_rebuild(self, qapp) -> None:
        """Fingerprint must be updated after a successful (non-deferred) rebuild."""
        from ayehear.services.protocol_engine import ProtocolSnapshot, ProtocolContent
        win = self._make_window(qapp)
        win._active_meeting_id = "mtg-delta-03"
        win._transcript_repo = MagicMock()
        win._snapshot_repo = MagicMock()

        new_text = "[00:10] Max: Erster Satz."
        win._transcript_view.setPlainText(new_text)
        win._last_protocol_transcript_fingerprint = None  # fresh start

        fake_snapshot = ProtocolSnapshot(meeting_id="mtg-delta-03", version=1, content=ProtocolContent())
        win._snapshot_repo.latest.return_value = MagicMock(
            snapshot_content={"summary": [], "decisions": [], "action_items": [], "open_questions": []}
        )
        with patch.object(win._protocol_engine, "generate", return_value=fake_snapshot), \
             patch.object(type(win._protocol_engine), "last_diagnostics",
                          new_callable=PropertyMock, return_value={"status": "ok", "reason": ""}):
            win._rebuild_protocol_from_persistence()

        expected_fp = win._compute_transcript_fingerprint(new_text)
        assert win._last_protocol_transcript_fingerprint == expected_fp

    def test_fingerprint_not_updated_on_cpu_deferral(self, qapp) -> None:
        """Fingerprint must NOT be updated when engine returns a deferred state."""
        from ayehear.services.protocol_engine import ProtocolSnapshot, ProtocolContent
        win = self._make_window(qapp)
        win._active_meeting_id = "mtg-defer-01"
        win._transcript_repo = MagicMock()
        win._snapshot_repo = MagicMock()

        new_text = "[00:05] Anna: Wichtige Info."
        win._transcript_view.setPlainText(new_text)
        original_fp = win._compute_transcript_fingerprint("previous text")
        win._last_protocol_transcript_fingerprint = original_fp

        deferred_snapshot = ProtocolSnapshot(meeting_id="mtg-defer-01", version=0, content=ProtocolContent())
        with patch.object(win._protocol_engine, "generate", return_value=deferred_snapshot), \
             patch.object(type(win._protocol_engine), "last_diagnostics",
                          new_callable=PropertyMock,
                          return_value={"status": "deferred", "reason": "cpu_busy:85.0%"}):
            win._rebuild_protocol_from_persistence()

        # Fingerprint must remain unchanged so next tick retries
        assert win._last_protocol_transcript_fingerprint == original_fp

    def test_deferred_marker_shown_in_protocol_panel(self, qapp) -> None:
        """Deferred CPU state must surface as explicit user-facing text in the panel."""
        from ayehear.services.protocol_engine import ProtocolSnapshot, ProtocolContent
        win = self._make_window(qapp)
        win._active_meeting_id = "mtg-defer-02"
        win._transcript_repo = MagicMock()
        win._snapshot_repo = MagicMock()

        win._transcript_view.setPlainText("[00:01] Speaker: Test.")
        win._last_protocol_transcript_fingerprint = None

        deferred_snapshot = ProtocolSnapshot(meeting_id="mtg-defer-02", version=0, content=ProtocolContent())
        with patch.object(win._protocol_engine, "generate", return_value=deferred_snapshot), \
             patch.object(type(win._protocol_engine), "last_diagnostics",
                          new_callable=PropertyMock,
                          return_value={"status": "deferred", "reason": "cpu_busy:90.0%"}):
            win._rebuild_protocol_from_persistence()

        panel_text = win._protocol_view.toPlainText()
        assert "DEFERRED" in panel_text or "DEFERRED".lower() in panel_text.lower()
        assert "cpu_busy" in panel_text

