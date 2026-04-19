"""System Readiness Indicators for AYE Hear (HEAR-087).

Implements the UX contract from docs/architecture/SYSTEM_READINESS_INDICATORS_SPEC.md.

Components evaluated:
  1. Database / Runtime Persistence
  2. Transcript Persistence + Review Queue Backend
  3. Speaker Enrollment Persistence
  4. Local LLM / Protocol Engine Path
  5. Audio Input Availability
  6. Export Target Availability

Each component reports one of: READY, DEGRADED, BLOCKED, UNKNOWN.
An aggregate top-line state is derived per the spec aggregation rule.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ayehear.models.runtime import RuntimeConfig
    from ayehear.storage.repositories import (
        MeetingRepository,
        ParticipantRepository,
        TranscriptSegmentRepository,
        ProtocolSnapshotRepository,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State model
# ---------------------------------------------------------------------------

class ReadinessState(Enum):
    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass
class ComponentStatus:
    name: str
    state: ReadinessState
    reason: str = ""


# ---------------------------------------------------------------------------
# Readiness checker (pure logic — no Qt)
# ---------------------------------------------------------------------------

# Components that trigger a BLOCKED aggregate if they are BLOCKED
_BLOCKING_COMPONENTS = {
    "Database / Runtime Persistence",
    "Transcript Persistence",
    "Speaker Enrollment Persistence",
}

# TTL for the Ollama model-list probe.  Avoids re-probing on every periodic
# refresh call, which would block the Qt main thread for up to timeout seconds.
_OLLAMA_MODEL_CACHE_TTL = 30  # seconds


class ReadinessChecker:
    """Evaluates the runtime readiness of each system component.

    All checks are synchronous and must return quickly.  Long-running probes
    (e.g. TCP to Ollama) are best attempted off the UI thread via
    check_all_async(), but a direct check_all() is provided for simplicity in
    tests and startup.
    """

    def __init__(self) -> None:
        # Cache: configured_model -> (model_list, expires_at)
        self._model_probe_cache: dict[str, tuple[list[str], float]] = {}

    def _cached_available_models(self, configured_model: str) -> list[str]:
        """Return available Ollama models, caching the result for TTL seconds.

        This avoids a synchronous HTTP probe on every Qt-timer-triggered
        readiness refresh, which would block the UI thread.
        """
        now = time.monotonic()
        if configured_model in self._model_probe_cache:
            cached_models, expires_at = self._model_probe_cache[configured_model]
            if now < expires_at:
                return cached_models
        try:
            from ayehear.services.protocol_engine import ProtocolEngine  # noqa: PLC0415

            models = ProtocolEngine(ollama_model=configured_model).available_models()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Ollama model probe failed: %s", exc)
            models = []
        self._model_probe_cache[configured_model] = (models, now + _OLLAMA_MODEL_CACHE_TTL)
        return models

    def check_database(
        self,
        meeting_repo: "MeetingRepository | None",
        participant_repo: "ParticipantRepository | None",
    ) -> ComponentStatus:
        if meeting_repo is not None and participant_repo is not None:
            # Explicit DSN check: verify the packaged runtime DSN path was used,
            # not just that repositories are non-null (spec AC2 requirement).
            try:
                from ayehear.storage.database import load_runtime_dsn
                dsn = load_runtime_dsn()
            except Exception:  # noqa: BLE001
                dsn = None
            if dsn:
                return ComponentStatus(
                    name="Database / Runtime Persistence",
                    state=ReadinessState.READY,
                    reason="Database connected",
                )
            return ComponentStatus(
                name="Database / Runtime Persistence",
                state=ReadinessState.DEGRADED,
                reason="Repositories connected but no runtime DSN \u2014 development or in-memory mode",
            )
        return ComponentStatus(
            name="Database / Runtime Persistence",
            state=ReadinessState.BLOCKED,
            reason="Database unavailable \u2014 product workflow degraded",
        )

    def check_transcript_persistence(
        self,
        transcript_repo: "TranscriptSegmentRepository | None",
    ) -> ComponentStatus:
        if transcript_repo is not None:
            return ComponentStatus(
                name="Transcript Persistence",
                state=ReadinessState.READY,
                reason="Review queue backend ready",
            )
        return ComponentStatus(
            name="Transcript Persistence",
            state=ReadinessState.BLOCKED,
            reason="Review queue not available",
        )

    def check_enrollment_persistence(
        self,
        participant_repo: "ParticipantRepository | None",
        speaker_profile_repo: "object | None" = None,
    ) -> ComponentStatus:
        """Check enrollment persistence readiness.

        READY requires both participant_repo AND speaker_profile_repo per spec:
        'speaker profile repository and participant repository are both connected'.
        DEGRADED when only participant_repo is available (recording works but
        speaker profiles cannot be persisted).
        BLOCKED when neither is available.
        """
        if participant_repo is not None and speaker_profile_repo is not None:
            return ComponentStatus(
                name="Speaker Enrollment Persistence",
                state=ReadinessState.READY,
                reason="Enrollment persistence ready",
            )
        if participant_repo is not None:
            return ComponentStatus(
                name="Speaker Enrollment Persistence",
                state=ReadinessState.DEGRADED,
                reason="Enrollment recording only \u2014 speaker profile persistence unavailable",
            )
        return ComponentStatus(
            name="Speaker Enrollment Persistence",
            state=ReadinessState.BLOCKED,
            reason="Enrollment cannot produce persistent V1 speaker profiles",
        )

    def check_llm_path(
        self,
        snapshot_repo: "ProtocolSnapshotRepository | None",
        runtime_config: "RuntimeConfig | None" = None,
    ) -> ComponentStatus:
        """Probe the local Ollama loopback endpoint and verify the configured model."""
        import socket

        ollama_host = "127.0.0.1"
        ollama_port = 11434
        configured_model = "mistral:7b"
        if runtime_config is not None:
            configured_model = runtime_config.models.ollama_model

        try:
            with socket.create_connection((ollama_host, ollama_port), timeout=0.5):
                reachable = True
        except OSError:
            reachable = False

        if reachable:
            available_models = self._cached_available_models(configured_model)

            if not available_models:
                return ComponentStatus(
                    name="Local LLM / Protocol Engine",
                    state=ReadinessState.DEGRADED,
                    reason="Ollama reachable but no local models installed — rule-based fallback",
                )
            if configured_model not in available_models:
                available = ", ".join(available_models)
                return ComponentStatus(
                    name="Local LLM / Protocol Engine",
                    state=ReadinessState.DEGRADED,
                    reason=(
                        f"Configured Ollama model '{configured_model}' unavailable — "
                        f"available: {available}"
                    ),
                )

        if reachable and snapshot_repo is not None:
            return ComponentStatus(
                name="Local LLM / Protocol Engine",
                state=ReadinessState.READY,
                reason=f"Local protocol engine ready ({configured_model})",
            )
        if reachable and snapshot_repo is None:
            return ComponentStatus(
                name="Local LLM / Protocol Engine",
                state=ReadinessState.DEGRADED,
                reason=(
                    f"Ollama reachable and model '{configured_model}' available but "
                    "protocol persistence unavailable — rule-based fallback"
                ),
            )
        return ComponentStatus(
            name="Local LLM / Protocol Engine",
            state=ReadinessState.DEGRADED,
            reason="Ollama unavailable — rule-based protocol fallback",
        )

    def check_audio_input(self) -> ComponentStatus:
        """Check whether at least one audio capture device is enumerable.

        Per spec: Audio is BLOCKED when no usable capture path can be opened.
        This is distinct from the mic-level widget's no-signal state.
        """
        try:
            from ayehear.services.audio_capture import enumerate_input_devices
            devices = enumerate_input_devices()
            if devices:
                return ComponentStatus(
                    name="Audio Input",
                    state=ReadinessState.READY,
                    reason=f"{len(devices)} capture device(s) available",
                )
        except Exception:  # noqa: BLE001
            pass
        # No usable capture path found — spec requires BLOCKED (not DEGRADED)
        return ComponentStatus(
            name="Audio Input",
            state=ReadinessState.BLOCKED,
            reason="No audio capture device found \u2014 microphone access required",
        )

    def check_export_target(self, runtime_config: "RuntimeConfig | None") -> ComponentStatus:
        """Check whether the exports directory can be resolved and written."""
        try:
            from ayehear.utils.paths import exports_dir
            out_dir = exports_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            # Verify writability
            test_file = out_dir / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
            return ComponentStatus(
                name="Export Target",
                state=ReadinessState.READY,
                reason=f"Export ready: {out_dir}",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Export target check failed: %s", exc)
        return ComponentStatus(
            name="Export Target",
            state=ReadinessState.BLOCKED,
            reason="Export target not writable \u2014 check install root",
        )

    def check_all(
        self,
        meeting_repo: "MeetingRepository | None" = None,
        participant_repo: "ParticipantRepository | None" = None,
        transcript_repo: "TranscriptSegmentRepository | None" = None,
        snapshot_repo: "ProtocolSnapshotRepository | None" = None,
        speaker_profile_repo: "object | None" = None,
        runtime_config: "RuntimeConfig | None" = None,
    ) -> tuple[list[ComponentStatus], ReadinessState]:
        """Run all component checks and return (components, aggregate_state)."""
        components = [
            self.check_database(meeting_repo, participant_repo),
            self.check_transcript_persistence(transcript_repo),
            self.check_enrollment_persistence(participant_repo, speaker_profile_repo),
            self.check_llm_path(snapshot_repo, runtime_config),
            self.check_audio_input(),
            self.check_export_target(runtime_config),
        ]
        aggregate = _aggregate_state(components)
        return components, aggregate


def _aggregate_state(components: list[ComponentStatus]) -> ReadinessState:
    """Derive aggregate status per spec aggregation rule.

    BLOCKED if any blocking component is BLOCKED.
    DEGRADED if any component is DEGRADED.
    READY otherwise.
    """
    any_blocked = any(
        c.state == ReadinessState.BLOCKED and c.name in _BLOCKING_COMPONENTS
        for c in components
    )
    if any_blocked:
        return ReadinessState.BLOCKED
    if any(c.state in (ReadinessState.DEGRADED, ReadinessState.BLOCKED) for c in components):
        return ReadinessState.DEGRADED
    return ReadinessState.READY


# ---------------------------------------------------------------------------
# Qt Widget
# ---------------------------------------------------------------------------

_STATE_COLORS = {
    ReadinessState.READY: ("#1a7a1a", "\u2705"),     # green + tick
    ReadinessState.DEGRADED: ("#b86e00", "\u26a0\ufe0f"),  # amber + warning
    ReadinessState.BLOCKED: ("#c0392b", "\u274c"),    # red + X
    ReadinessState.UNKNOWN: ("#666666", "\u23f3"),    # grey + hourglass
}

_AGGREGATE_TEXTS = {
    ReadinessState.READY: "Product Path Ready",
    ReadinessState.DEGRADED: "Product Path Degraded",
    ReadinessState.BLOCKED: "Product Path Blocked \u2014 stop product-complete testing",
    ReadinessState.UNKNOWN: "Readiness Unknown",
}


class SystemReadinessWidget(QGroupBox):
    """Compact status panel showing per-component and aggregate readiness.

    Usage:
        widget = SystemReadinessWidget()
        widget.update_status(components, aggregate)
        layout.addWidget(widget)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("System Readiness", parent)
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(8, 8, 8, 8)

        # Aggregate top-line
        self._aggregate_label = QLabel("\u23f3 Checking readiness\u2026")
        self._aggregate_label.setStyleSheet("font-weight: 700; font-size: 12px;")
        self._layout.addWidget(self._aggregate_label)

        # Per-component rows (populated by update_status)
        self._component_rows: list[QLabel] = []

        # Refresh button
        self._refresh_btn = QPushButton("Refresh Status")
        self._refresh_btn.setFixedHeight(24)
        self._layout.addWidget(self._refresh_btn)

    # Public API ----------------------------------------------------------------

    def set_refresh_callback(self, callback) -> None:  # type: ignore[type-arg]
        """Connect the Refresh button to an external callback."""
        self._refresh_btn.clicked.connect(callback)

    def update_status(
        self,
        components: list[ComponentStatus],
        aggregate: ReadinessState,
    ) -> None:
        """Rebuild the widget display from fresh check results."""
        # Remove old component rows
        for lbl in self._component_rows:
            self._layout.removeWidget(lbl)
            lbl.deleteLater()
        self._component_rows.clear()

        # Insert component rows above the refresh button (before the last item)
        insert_idx = self._layout.count() - 1  # before refresh btn

        for comp in components:
            color, icon = _STATE_COLORS[comp.state]
            reason_snippet = f" — {comp.reason}" if comp.reason else ""
            text = f"{icon} {comp.name}{reason_snippet}"
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
            lbl.setWordWrap(True)
            self._layout.insertWidget(insert_idx, lbl)
            self._component_rows.append(lbl)
            insert_idx += 1

        # Update aggregate
        agg_color, agg_icon = _STATE_COLORS[aggregate]
        agg_text = _AGGREGATE_TEXTS[aggregate]
        self._aggregate_label.setText(f"{agg_icon} {agg_text}")
        self._aggregate_label.setStyleSheet(
            f"font-weight: 700; font-size: 12px; color: {agg_color};"
        )

        # Stop-test warning (hard stop)
        if aggregate == ReadinessState.BLOCKED:
            self._aggregate_label.setToolTip(
                "Critical backend missing \u2014 stop product-complete test and inspect runtime setup."
            )
        elif aggregate == ReadinessState.DEGRADED:
            # Check if LLM is degraded specifically
            llm_degraded = any(
                c.name == "Local LLM / Protocol Engine" and c.state == ReadinessState.DEGRADED
                for c in components
            )
            if llm_degraded:
                self._aggregate_label.setToolTip(
                    "Protocol fallback active \u2014 do not treat protocol results as product-complete evidence."
                )
            else:
                self._aggregate_label.setToolTip("")
        else:
            self._aggregate_label.setToolTip("")

    def set_unknown(self) -> None:
        """Reset to UNKNOWN state (shown at startup before first check)."""
        color, icon = _STATE_COLORS[ReadinessState.UNKNOWN]
        self._aggregate_label.setText(f"{icon} Readiness Unknown")
        self._aggregate_label.setStyleSheet(
            f"font-weight: 700; font-size: 12px; color: {color};"
        )
        for lbl in self._component_rows:
            self._layout.removeWidget(lbl)
            lbl.deleteLater()
        self._component_rows.clear()
