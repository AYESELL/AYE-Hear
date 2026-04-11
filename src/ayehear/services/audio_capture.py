"""Audio capture and preprocessing pipeline for Windows (ADR-0004).

Uses sounddevice with WASAPI default device (device=None).
Produces AudioSegment events passed to the caller via a callback.

Design:
  AudioCaptureProfile   – static device/format configuration
  AudioSegment          – one preprocessed chunk ready for transcription
  AudioCaptureService   – starts/stops capture, emits segments via callback
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


def enumerate_input_devices() -> list[tuple[int, str]]:
    """Return list of (device_index, device_name) for available audio input devices.

    Uses sounddevice WASAPI query (ADR-0004).  Returns an empty list when
    sounddevice is not installed or no capture devices are present, so callers
    can fall back gracefully to the system default.
    """
    try:
        import sounddevice as sd  # type: ignore[import]

        devices = sd.query_devices()
        return [
            (idx, str(dev["name"]))
            for idx, dev in enumerate(devices)
            if dev.get("max_input_channels", 0) > 0
        ]
    except ImportError:
        logger.warning("sounddevice not installed — device enumeration unavailable.")
        return []
    except Exception as exc:
        logger.error("Failed to enumerate audio input devices: %s", exc)
        return []


# ADR-0004: 16 kHz mono, 512-sample chunks (~32 ms)
_DEFAULT_SAMPLE_RATE = 16_000
_DEFAULT_CHANNELS = 1
_DEFAULT_FRAME_SIZE = 512
_SILENCE_RMS_THRESHOLD = 0.005  # approx -46 dBFS; below = silence


@dataclass(slots=True)
class AudioCaptureProfile:
    sample_rate_hz: int = _DEFAULT_SAMPLE_RATE
    channels: int = _DEFAULT_CHANNELS
    frame_size: int = _DEFAULT_FRAME_SIZE
    device_index: int | None = None  # None = WASAPI default (ADR-0004)


@dataclass
class AudioSegment:
    """One preprocessed audio chunk ready for downstream processing."""
    captured_at: datetime
    start_ms: int
    end_ms: int
    samples: np.ndarray  # shape (frames, channels) float32
    rms: float
    is_silence: bool


SegmentCallback = Callable[[AudioSegment], None]


class _AudioInputStream(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def close(self) -> None: ...


class AudioCaptureService:
    """Captures audio from Windows default device (WASAPI default).

    Usage::

        def on_segment(seg: AudioSegment) -> None:
            print(f"[{seg.start_ms}ms] rms={seg.rms:.4f} silence={seg.is_silence}")

        svc = AudioCaptureService(profile=AudioCaptureProfile())
        svc.start(on_segment)
        # ... meeting in progress ...
        svc.stop()
    """

    def __init__(self, profile: AudioCaptureProfile | None = None) -> None:
        self._profile = profile or AudioCaptureProfile()
        self._stream: _AudioInputStream | None = None
        self._active = False
        self._lock = threading.Lock()
        self._elapsed_ms: int = 0
        self._callback: SegmentCallback | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, segment_callback: SegmentCallback) -> None:
        """Open the WASAPI default capture device and begin streaming."""
        with self._lock:
            if self._active:
                raise RuntimeError("Capture already active.")
            self._callback = segment_callback
            self._elapsed_ms = 0
            self._active = True
            self._open_stream()
        logger.info(
            "Audio capture started: %d Hz, %d ch, frame=%d",
            self._profile.sample_rate_hz,
            self._profile.channels,
            self._profile.frame_size,
        )

    def stop(self) -> None:
        """Stop capture and release device resources."""
        with self._lock:
            if not self._active:
                return
            self._active = False
            self._close_stream()
        logger.info("Audio capture stopped.")

    def describe_input(self) -> str:
        return (
            f"Windows default microphone (WASAPI), "
            f"{self._profile.sample_rate_hz} Hz, "
            f"{self._profile.channels}ch"
        )

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_stream(self) -> None:
        try:
            import sounddevice as sd

            stream = sd.InputStream(
                samplerate=self._profile.sample_rate_hz,
                channels=self._profile.channels,
                dtype="float32",
                blocksize=self._profile.frame_size,
                device=self._profile.device_index,  # None = WASAPI default (ADR-0004)
                callback=self._sd_callback,
                finished_callback=self._on_stream_finished,
            )
            self._stream = stream
            stream.start()
        except ImportError:
            logger.warning("sounddevice not installed — running in stub mode.")
            self._stream = None
        except Exception as exc:
            logger.error("Failed to open audio device: %s", exc)
            self._active = False
            raise RuntimeError(f"Audio device error: {exc}") from exc

    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                logger.warning("Error closing audio stream: %s", exc)
            self._stream = None

    def _sd_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        if status:
            logger.warning("Audio stream status: %s", status)

        chunk = indata.copy()
        duration_ms = int(frames / self._profile.sample_rate_hz * 1000)
        start_ms = self._elapsed_ms
        self._elapsed_ms += duration_ms

        segment = self._preprocess(chunk, start_ms, self._elapsed_ms)

        if self._callback is not None:
            try:
                self._callback(segment)
            except Exception as exc:
                logger.error("Segment callback raised: %s", exc)

    def _on_stream_finished(self) -> None:
        logger.info("Audio stream finished (device closed or error).")
        with self._lock:
            self._active = False

    @staticmethod
    def _preprocess(
        samples: np.ndarray, start_ms: int, end_ms: int
    ) -> AudioSegment:
        """RMS normalization and silence detection (ADR-0004)."""
        rms = float(np.sqrt(np.mean(samples ** 2)))
        is_silence = rms < _SILENCE_RMS_THRESHOLD

        if not is_silence and rms > 0:
            target_rms = 0.1  # -20 dBFS approx
            samples = samples * (target_rms / rms)

        return AudioSegment(
            captured_at=datetime.now(timezone.utc),
            start_ms=start_ms,
            end_ms=end_ms,
            samples=samples,
            rms=rms,
            is_silence=is_silence,
        )
