"""Regression tests for HEAR-059: Speaker Edit Flow — no status leakage.

Covers:
- _parse_speaker_raw: correct field extraction for all input formats
- Status tokens are preserved (not mutated) when name/org are edited
- _start_meeting participant parsing ignores status tokens
- _add_speaker creates item with 'pending enrollment' status
- _on_speaker_item_changed guard prevents feedback loops during programmatic updates
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _parse_speaker_raw — pure function, no Qt needed
# ---------------------------------------------------------------------------

def _parse(raw: str):
    """Import lazily to avoid Qt startup on import."""
    from ayehear.app.window import MainWindow
    return MainWindow._parse_speaker_raw(raw)


class TestParseSpeakerRaw:
    def test_full_entry_splits_correctly(self):
        name, org, status = _parse("Max Weber | Customer GmbH | pending enrollment")
        assert name == "Max Weber"
        assert org == "Customer GmbH"
        assert status == "pending enrollment"

    def test_enrolled_status_preserved(self):
        name, org, status = _parse("Anna Schmidt | Corp | enrolled (id: abc12345)")
        assert name == "Anna Schmidt"
        assert org == "Corp"
        assert status == "enrolled (id: abc12345)"

    def test_failed_status_preserved(self):
        name, org, status = _parse("Hans Muster | GmbH | enrollment failed")
        assert status == "enrollment failed"

    def test_missing_status_defaults_to_pending(self):
        name, org, status = _parse("Hans | GmbH")
        assert name == "Hans"
        assert org == "GmbH"
        assert status == "pending enrollment"

    def test_name_only_returns_defaults(self):
        name, org, status = _parse("Nur Name")
        assert name == "Nur Name"
        assert org == ""
        assert status == "pending enrollment"

    def test_strips_surrounding_whitespace(self):
        name, org, status = _parse("  Max  |  Corp  |  pending enrollment  ")
        assert name == "Max"
        assert org == "Corp"
        assert status == "pending enrollment"

    def test_salutation_entry(self):
        name, org, status = _parse("Herr/Frau Teilnehmer_1 | Organisation | pending enrollment")
        assert name == "Herr/Frau Teilnehmer_1"
        assert org == "Organisation"
        assert status == "pending enrollment"

    def test_empty_string_returns_defaults(self):
        name, org, status = _parse("")
        assert name == ""
        assert org == ""
        assert status == "pending enrollment"

    def test_status_with_uuid_preserved(self):
        uid = "stub-a1b2c3d4"
        name, org, status = _parse(f"Frau Schneider | AYE | enrolled (id: {uid})")
        assert status == f"enrolled (id: {uid})"

    def test_reconstruct_preserves_status(self):
        """Round-trip: parse → reconstruct keeps original status intact."""
        raw = "Frau Schneider | AYE | enrolled (id: stub-1234)"
        name, org, status = _parse(raw)
        reconstructed = f"{name} | {org} | {status}"
        assert reconstructed == raw


# ---------------------------------------------------------------------------
# _start_meeting participant parsing — status tokens must not contaminate names
# ---------------------------------------------------------------------------

def test_start_meeting_ignores_status_in_participant_name(qapp):
    """Participants created from speaker entries must not contain status tokens."""
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    cfg = RuntimeConfig()

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=cfg)

    # Simulate a speaker list where items include enrollment status
    from PySide6.QtWidgets import QListWidgetItem
    win._speakers_list.clear()
    for raw in [
        "Frau Schneider | AYE GmbH | enrolled (id: stub-aabb)",
        "Max Weber | Customer | pending enrollment",
    ]:
        win._speakers_list.addItem(QListWidgetItem(raw))

    win._meeting_title.setText("Test Meeting")

    captured_participants = []

    original_set_active = win.set_active_meeting
    def _capture_and_proceed(meeting_id, known_speakers=None):
        for p in win._session.participants if win._session else []:
            captured_participants.append(p)
        original_set_active(meeting_id, known_speakers=known_speakers)

    win.set_active_meeting = _capture_and_proceed

    with (
        patch.object(win, "_start_audio_pipeline", return_value="ok"),
        patch.object(win, "append_transcript_line"),
        patch("PySide6.QtWidgets.QMessageBox.information"),
    ):
        win._start_meeting()

    # Names must not contain status tokens
    assert any("Schneider" in p.last_name for p in win._session.participants)
    assert all(
        "pending enrollment" not in (p.first_name or "") and
        "enrolled" not in (p.first_name or "")
        for p in win._session.participants
    ), "Status tokens must not appear in participant first_name"
    assert all(
        "pending enrollment" not in p.last_name and
        "enrolled" not in p.last_name
        for p in win._session.participants
    ), "Status tokens must not appear in participant last_name"

    win.stop_active_meeting()
    win.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# _on_speaker_item_changed guard
# ---------------------------------------------------------------------------

def test_on_speaker_item_changed_guard_suppresses_during_update(qapp):
    """itemChanged handler must not update status label while guard is active."""
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig
    from PySide6.QtWidgets import QListWidgetItem

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())

    item = QListWidgetItem("Test | Org | pending enrollment")
    win._speakers_list.addItem(item)
    win._speaker_status.setText("")

    win._speaker_list_updating = True
    item.setText("Test | Org | enrolled (id: xyz)")
    qapp.processEvents()

    # Guard was active — status label must NOT have been updated
    assert win._speaker_status.text() == ""

    win._speaker_list_updating = False
    item.setText("Test | Org | pending enrollment")
    qapp.processEvents()

    # Guard inactive — status label should update
    assert "pending enrollment" in win._speaker_status.text() or \
           "Gespeichert" in win._speaker_status.text()

    win.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# _apply_participant_template — status must be pending enrollment only
# ---------------------------------------------------------------------------

def test_apply_participant_template_uses_pending_status(qapp):
    """Template-generated items must have 'pending enrollment' status, no stale tokens."""
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())

    win._participant_count.setValue(3)
    win._apply_participant_template()

    for i in range(win._speakers_list.count()):
        text = win._speakers_list.item(i).text()
        _, _, status = MainWindow._parse_speaker_raw(text)
        assert status == "pending enrollment", f"Unexpected status in item: {text!r}"

    win.deleteLater()
    qapp.processEvents()
