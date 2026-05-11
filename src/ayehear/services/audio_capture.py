"""Audio capture and preprocessing pipeline for Windows (ADR-0004).

Uses sounddevice with WASAPI default device (device=None).
Produces AudioSegment events passed to the caller via a callback.

Design:
  AudioCaptureProfile   – static device/format configuration
  AudioSegment          – one preprocessed chunk ready for transcription
  WavPersistenceConfig  – opt-in WAV-on-disk settings (HEAR-141, ADR-0015)
  AudioCaptureService   – starts/stops capture, emits segments via callback
"""
from __future__ import annotations

import logging
import sys
import threading
import wave
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Windows thread-priority helpers (HEAR-141)
# ---------------------------------------------------------------------------

_THREAD_PRIORITY_HIGHEST = 2  # THREAD_PRIORITY_HIGHEST from winbase.h
_MIN_RETENTION_DAYS = 1
_MAX_RETENTION_DAYS = 30


def _elevate_capture_thread_priority() -> bool:
    """Raise the calling thread to THREAD_PRIORITY_HIGHEST on Windows.

    This is a best-effort call: non-Windows platforms and permission failures
    are silently ignored so the capture pipeline always starts regardless.

    Returns True if the priority was raised successfully.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        handle = ctypes.windll.kernel32.GetCurrentThread()
        ok = ctypes.windll.kernel32.SetThreadPriority(handle, _THREAD_PRIORITY_HIGHEST)
        if ok:
            logger.debug("Capture thread priority elevated to THREAD_PRIORITY_HIGHEST.")
        else:
            error = ctypes.windll.kernel32.GetLastError()
            logger.warning("SetThreadPriority failed (error %d); continuing at normal priority.", error)
        return bool(ok)
    except Exception as exc:
        logger.warning("Could not elevate capture thread priority: %s", exc)
        return False


def enumerate_input_devices() -> list[tuple[int, str]]:
    """Return list of (device_index, device_name) for available audio input devices.

    Uses sounddevice WASAPI query (ADR-0004).  Returns an empty list when
    sounddevice is not installed or no capture devices are present, so callers
    can fall back gracefully to the system default.
    """
    try:
        import sounddevice as sd  # type: ignore[import-untyped]

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
class WavPersistenceConfig:
    """Opt-in WAV-on-disk settings (ADR-0015, HEAR-141, HEAR-142).

    All fields default to the *disabled / secure* state.  Enabling WAV
    persistence requires explicit operator opt-in and HEAR-142 sign-off.

    Security constraints (HEAR-142, BEFUND-3):
    - ``output_dir`` MUST be under ``runtime/wav/``; never inside ``exports/``.
    - TTL is clamped to 1–30 days.
    - Files never leave the local machine (no upload code).
    """

    enabled: bool = False
    output_dir: Path = field(default_factory=lambda: Path("runtime/wav"))
    delete_on_meeting_end: bool = False
    retention_days: int = 7

    def __post_init__(self) -> None:
        """Apply security guardrails from HEAR-142.

        - Clamp retention to 1-30 days.
        - Restrict output directory to runtime/wav (or a subdirectory).
        """
        clamped = max(_MIN_RETENTION_DAYS, min(_MAX_RETENTION_DAYS, int(self.retention_days)))
        object.__setattr__(self, "retention_days", clamped)
        object.__setattr__(self, "output_dir", _validate_wav_output_dir(self.output_dir))


def _validate_wav_output_dir(output_dir: Path) -> Path:
    """Allow only runtime/wav (or subdirectories) as WAV output path."""
    raw = output_dir.as_posix().replace("\\", "/")
    lowered = raw.lower()

    if output_dir.is_absolute():
        if "/exports/" in lowered or lowered.endswith("/exports"):
            raise ValueError("WAV output_dir must never point into exports/.")
        if "/runtime/wav" not in lowered:
            raise ValueError("WAV output_dir must be under runtime/wav.")
        return output_dir

    cleaned = lowered.strip("./")
    if not (cleaned == "runtime/wav" or cleaned.startswith("runtime/wav/")):
        raise ValueError("WAV output_dir must be runtime/wav or a subdirectory.")
    if cleaned.startswith("exports/") or cleaned == "exports":
        raise ValueError("WAV output_dir must never point into exports/.")
    return Path(cleaned)


def cleanup_expired_wav_files(wav_dir: Path, retention_days: int) -> int:
    """Delete WAV files older than *retention_days* from *wav_dir*.

    Returns the number of files deleted.  Silently skips missing directories
    or files that cannot be removed.
    """
    if not wav_dir.is_dir():
        return 0
    import time

    cutoff = time.time() - retention_days * 86_400
    deleted = 0
    for wav_file in wav_dir.glob("*.wav"):
        try:
            if wav_file.stat().st_mtime < cutoff:
                wav_file.unlink()
                deleted += 1
                logger.info("WAV TTL cleanup: removed %s", wav_file.name)
        except Exception as exc:
            logger.warning("Could not remove expired WAV %s: %s", wav_file.name, exc)
    return deleted


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

        svc = AudioCaptureService(
            profile=AudioCaptureProfile(),
            wav_config=WavPersistenceConfig(enabled=False),
        )
        svc.start(on_segment, meeting_id="mtg-001")
        # ... meeting in progress ...
        svc.stop()  # flushes WAV if persistence is enabled
    """

    def __init__(
        self,
        profile: AudioCaptureProfile | None = None,
        wav_config: WavPersistenceConfig | None = None,
    ) -> None:
        self._profile = profile or AudioCaptureProfile()
        self._wav_config = wav_config or WavPersistenceConfig()
        self._stream: _AudioInputStream | None = None
        self._active = False
        self._lock = threading.Lock()
        self._elapsed_ms: int = 0
        self._callback: SegmentCallback | None = None
        self._meeting_id: str | None = None
        self._wav_buffer: list[np.ndarray] = []  # accumulates non-silence float32 frames

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, segment_callback: SegmentCallback, meeting_id: str | None = None) -> None:
        """Open the WASAPI default capture device and begin streaming.

        *meeting_id* is used as the WAV file name stem when WAV persistence
        is enabled (ADR-0015, HEAR-141).
        """
        with self._lock:
            if self._active:
                raise RuntimeError("Capture already active.")
            self._callback = segment_callback
            self._elapsed_ms = 0
            self._active = True
            self._meeting_id = meeting_id
            self._wav_buffer = []
            self._open_stream()
        logger.info(
            "Audio capture started: %d Hz, %d ch, frame=%d",
            self._profile.sample_rate_hz,
            self._profile.channels,
            self._profile.frame_size,
        )

    def stop(self) -> None:
        """Stop capture, flush optional WAV file, and release device resources."""
        with self._lock:
            # Stream-finished callbacks can set _active=False before callers invoke
            # stop(); still close any remaining stream handle and flush buffered WAV.
            was_active = self._active
            has_stream = self._stream is not None
            self._active = False

        if has_stream:
            self._close_stream()

        if not was_active and self._wav_config.enabled and self._wav_buffer:
            logger.debug(
                "Audio capture stop called after stream-finished callback; flushing buffered WAV."
            )

        self._flush_wav()
        if self._wav_config.enabled and not self._wav_config.delete_on_meeting_end:
            cleanup_expired_wav_files(self._wav_config.output_dir, self._wav_config.retention_days)
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
            # HEAR-141: elevate thread priority after stream starts so the
            # callback thread (created by sounddevice/PortAudio) inherits
            # the elevated priority indirectly.  We elevate the *calling*
            # thread here; PortAudio's internal thread cannot be reached via
            # Python, but this still benefits any processing we do inline.
            _elevate_capture_thread_priority()
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

        # HEAR-141: accumulate non-silence frames for optional WAV persistence
        if self._wav_config.enabled and not segment.is_silence:
            self._wav_buffer.append(segment.samples)

        if self._callback is not None:
            try:
                self._callback(segment)
            except Exception as exc:
                logger.error("Segment callback raised: %s", exc)

    def _flush_wav(self) -> Path | None:
        """Write accumulated audio frames to a WAV file if persistence is enabled.

        Returns the path of the written file, or None when persistence is
        disabled or the buffer is empty.

        Security (HEAR-142, BEFUND-3):
        - Files are written inside ``wav_config.output_dir`` only.
        - When ``delete_on_meeting_end`` is True the file is removed
          immediately after writing (useful for end-to-end tests).
        - No file is ever written outside ``runtime/wav/``.
        """
        if not self._wav_config.enabled or not self._wav_buffer:
            return None

        try:
            out_dir = self._wav_config.output_dir
            out_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            stem = self._meeting_id or "unknown"
            wav_path = out_dir / f"{stem}_{timestamp}.wav"

            combined = np.concatenate(self._wav_buffer, axis=0)
            # Ensure mono; take first channel if stereo
            if combined.ndim > 1:
                combined = combined[:, 0]

            # Convert float32 → int16 (PCM) for standard WAV compatibility
            pcm = (np.clip(combined, -1.0, 1.0) * 32767).astype(np.int16)

            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self._profile.sample_rate_hz)
                wf.writeframes(pcm.tobytes())

            logger.info("WAV persistence: wrote %s (%d frames)", wav_path.name, len(pcm))

            if self._wav_config.delete_on_meeting_end:
                wav_path.unlink(missing_ok=True)
                logger.info("WAV persistence: deleted on meeting-end per policy (%s)", wav_path.name)
                return None

            return wav_path
        except Exception as exc:
            logger.error("WAV persistence flush failed: %s", exc)
            return None
        finally:
            self._wav_buffer = []

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
