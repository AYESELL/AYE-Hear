from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        return MainWindow(runtime_config=RuntimeConfig())


def test_disable_persistence_clears_live_repo_bindings(qapp):
    """HEAR-149: disabling persistence must clear the actually used repo fields."""
    win = _make_window(qapp)
    win._active_meeting_id = "mtg-149"

    win._transcription_service.transcript_repo = MagicMock()
    win._protocol_engine._snapshots = MagicMock()
    win._protocol_engine._transcripts = MagicMock()

    with patch.object(win, "_refresh_protocol_display"):
        win._disable_persistence("HEAR-149 regression test")

    assert win._transcription_service.transcript_repo is None
    assert win._protocol_engine._snapshots is None
    assert win._protocol_engine._transcripts is None

    win.deleteLater()
    qapp.processEvents()
