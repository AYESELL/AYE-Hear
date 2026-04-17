"""QA Runtime Evidence Tests — HEAR-033 / HEAR-034.

Covers the three Phase-1A manually-waived QA items that must be executed
before General Availability.  These automated tests document the code-level
guarantees; the evidence comments describe what each test proves.

QA-TX-02  Device interruption during active session
          Evidence: AudioCaptureService graceful error handling, no crash.

QA-PV-01  Full offline run — no outbound dependencies permitted
          Evidence: ProtocolEngine and DatabaseBootstrap enforce loopback-only
          at construction/bootstrap time; the violation path raises immediately.

QA-PV-02  Network boundary — PostgreSQL binds to loopback interfaces only
          Evidence: _check_loopback_only logic fails-closed for any non-
          loopback listen_addresses value; wildcard/remote addresses are
          rejected.  Captures ``SHOW listen_addresses`` via mock equivalent.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ayehear.services.audio_capture import AudioCaptureService
from ayehear.services.protocol_engine import ProtocolEngine
from ayehear.storage.database import DatabaseBootstrap, DatabaseConfig


# ===========================================================================
# QA-TX-02 — Device interruption / graceful error handling (ADR-0004)
# ===========================================================================


class TestQATX02DeviceInterruption:
    """AudioCaptureService must handle all device failure modes without crashing."""

    def test_device_open_failure_raises_runtime_error_and_deactivates(self) -> None:
        """When the audio device cannot be opened the service raises RuntimeError
        and resets _active to False so the caller can detect the failure.
        """
        svc = AudioCaptureService()

        mock_sd = MagicMock()
        mock_sd.InputStream.side_effect = OSError("No such device")

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            with pytest.raises(RuntimeError, match="Audio device error"):
                svc.start(lambda seg: None)

        assert svc.is_active is False

    def test_stream_finished_callback_deactivates_service(self) -> None:
        """When the audio stream ends (device disconnected or OS event) the
        _on_stream_finished callback sets is_active to False — no crash.
        """
        svc = AudioCaptureService()
        # Bypass device open — set internal state as if already started
        svc._active = True

        svc._on_stream_finished()

        assert svc.is_active is False

    def test_sd_callback_with_status_logs_warning_and_continues(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """WASAPI status flags (buffer overrun, etc.) are logged as warnings;
        segment processing still completes — capture continues.
        """
        svc = AudioCaptureService()
        received: list = []
        svc._callback = received.append
        fake_status = MagicMock()
        fake_status.__bool__ = lambda s: True
        fake_status.__str__ = lambda s: "InputOverflow"

        indata = np.zeros((512, 1), dtype="float32")
        with caplog.at_level(logging.WARNING, logger="ayehear.services.audio_capture"):
            svc._sd_callback(indata, 512, object(), fake_status)

        assert any("InputOverflow" in r.message for r in caplog.records)
        assert len(received) == 1

    def test_sd_callback_exception_in_user_callback_is_logged_not_raised(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If the caller-supplied segment callback raises, the error is logged
        but not re-raised so the audio pipeline remains alive.
        """
        def bad_callback(seg):
            raise ValueError("downstream processing error")

        svc = AudioCaptureService()
        svc._callback = bad_callback

        indata = np.zeros((512, 1), dtype="float32")
        with caplog.at_level(logging.ERROR, logger="ayehear.services.audio_capture"):
            # Must not raise
            svc._sd_callback(indata, 512, object(), None)

        assert any("downstream processing error" in r.message for r in caplog.records)

    def test_stop_on_inactive_service_is_no_op(self) -> None:
        """Calling stop() when not active must not raise (idempotent)."""
        svc = AudioCaptureService()
        assert svc.is_active is False
        svc.stop()  # must not raise

    def test_close_stream_handles_close_error_gracefully(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If stream.close() raises, the error is caught and logged as a warning."""
        svc = AudioCaptureService()
        mock_stream = MagicMock()
        mock_stream.stop.return_value = None
        mock_stream.close.side_effect = OSError("close failed")
        svc._stream = mock_stream

        with caplog.at_level(logging.WARNING, logger="ayehear.services.audio_capture"):
            svc._close_stream()

        assert svc._stream is None
        assert any("close failed" in r.message for r in caplog.records)

    def test_start_while_already_active_raises_runtime_error(self) -> None:
        """Starting capture twice must raise immediately — no resource leak."""
        svc = AudioCaptureService()
        svc._active = True
        with pytest.raises(RuntimeError, match="Capture already active"):
            svc.start(lambda seg: None)


# ===========================================================================
# QA-PV-01 — Full offline run: no outbound dependencies (ADR-0006 / ADR-0003)
# ===========================================================================


class TestQAPV01OfflineEnforcement:
    """ProtocolEngine and DatabaseBootstrap must prevent any non-loopback connection."""

    def test_protocol_engine_default_url_is_loopback(self) -> None:
        """Default Ollama URL is loopback — ProtocolEngine can be instantiated
        safely in an offline environment.
        """
        engine = ProtocolEngine()
        assert "localhost" in engine._ollama_base_url or "127." in engine._ollama_base_url

    @pytest.mark.parametrize("loopback_url", [
        "http://localhost:11434",
        "http://127.0.0.1:11434",
        "http://127.0.0.2:11434",
    ])
    def test_protocol_engine_accepts_loopback_urls(self, loopback_url: str) -> None:
        """Loopback Ollama URLs are accepted — offline-first guarantee holds."""
        engine = ProtocolEngine(ollama_base_url=loopback_url)
        assert engine._ollama_base_url == loopback_url

    @pytest.mark.parametrize("external_url", [
        "http://api.openai.com/v1",
        "http://192.168.1.100:11434",
        "http://10.0.0.1:11434",
        "https://cloud-llm.example.com/api",
        "http://0.0.0.0:11434",
    ])
    def test_protocol_engine_rejects_external_urls_at_construction(
        self, external_url: str
    ) -> None:
        """External URLs are rejected with ValueError at construction time —
        no meeting data can ever be sent to a remote LLM service.
        """
        with pytest.raises(ValueError, match="loopback"):
            ProtocolEngine(ollama_base_url=external_url)

    def test_database_bootstrap_rejects_non_loopback_listen_address(self) -> None:
        """DatabaseBootstrap._check_loopback_only rejects wildcard listen_addresses —
        PostgreSQL cannot be reconfigured to accept remote connections at runtime.
        """
        config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
        bootstrap = DatabaseBootstrap(config)
        conn = _make_mock_conn("*")
        with pytest.raises(RuntimeError, match="loopback"):
            bootstrap._check_loopback_only(conn)

    def test_database_bootstrap_rejects_remote_ip_listen_address(self) -> None:
        """A specific remote IP in listen_addresses also fails closed."""
        config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
        bootstrap = DatabaseBootstrap(config)
        conn = _make_mock_conn("0.0.0.0")
        with pytest.raises(RuntimeError, match="loopback"):
            bootstrap._check_loopback_only(conn)

    def test_database_bootstrap_accepts_loopback_listen_address(self) -> None:
        """Loopback listen_addresses passes the offline-first check without error."""
        config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
        bootstrap = DatabaseBootstrap(config)
        conn = _make_mock_conn("localhost")
        bootstrap._check_loopback_only(conn)  # must not raise


# ===========================================================================
# QA-PV-02 — Network boundary: loopback enforcement at runtime (ADR-0006)
# ===========================================================================


class TestQAPV02NetworkBoundary:
    """Simulates the ``SHOW listen_addresses`` check that DatabaseBootstrap
    performs during every bootstrap() call.  This is the code-equivalent of
    the netstat/runtime capture required as operational evidence.
    """

    @pytest.mark.parametrize("listen_val,expected_pass", [
        ("localhost", True),
        ("127.0.0.1", True),
        ("::1", True),
        ("127.0.0.1, ::1", True),
        ("localhost,127.0.0.1", True),
        ("*", False),
        ("0.0.0.0", False),
        ("192.168.1.1", False),
        ("localhost,0.0.0.0", False),   # mixed — must fail-closed
        ("127.0.0.1,*", False),         # mixed — must fail-closed
    ])
    def test_loopback_check_for_listen_addresses_value(
        self, listen_val: str, expected_pass: bool
    ) -> None:
        """Exhaustive table test for _check_loopback_only against the values
        PostgreSQL can return for SHOW listen_addresses.  Verifies that the
        fail-closed behaviour matches ADR-0006 requirements.
        """
        config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
        bootstrap = DatabaseBootstrap(config)
        conn = _make_mock_conn(listen_val)

        if expected_pass:
            bootstrap._check_loopback_only(conn)  # must not raise
        else:
            with pytest.raises(RuntimeError, match="loopback"):
                bootstrap._check_loopback_only(conn)

    def test_loopback_check_emits_debug_log_on_pass(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A passing loopback check emits a DEBUG log with the listen_addresses value
        so that the runtime evidence log contains the PostgreSQL server response.
        """
        config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
        bootstrap = DatabaseBootstrap(config)
        conn = _make_mock_conn("localhost")

        with caplog.at_level(logging.DEBUG, logger="ayehear.storage.database"):
            bootstrap._check_loopback_only(conn)

        assert any(
            "loopback" in r.message.lower() and "localhost" in r.message
            for r in caplog.records
        )

    def test_loopback_check_error_message_contains_listen_addresses(self) -> None:
        """The RuntimeError message includes the offending listen_addresses value
        so that field engineers can identify the misconfigured PostgreSQL setting.
        """
        config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
        bootstrap = DatabaseBootstrap(config)
        conn = _make_mock_conn("192.168.99.1")

        with pytest.raises(RuntimeError) as exc_info:
            bootstrap._check_loopback_only(conn)

        assert "192.168.99.1" in str(exc_info.value)


# ===========================================================================
# Shared helpers
# ===========================================================================


def _make_mock_conn(listen_addresses: str) -> MagicMock:
    """Return a SQLAlchemy-like mock connection that reports listen_addresses."""
    result = MagicMock()
    result.fetchone.return_value = (listen_addresses,)
    conn = MagicMock()
    conn.execute.return_value = result
    return conn
