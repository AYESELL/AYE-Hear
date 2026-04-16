"""Tests for HEAR-079: Stable participant identity for enrollment mapping.

Verifies that enrollment mapping uses a stable UUID (participant_id) instead of
the display name so that:
  - Name collisions do not cause mapping ambiguity
  - Display-name changes do not break the enrollment linkage
  - No data loss or orphaned records on enrollment update

Acceptance Criteria:
  AC1 – Enrollment mapping uses stable participant_id, not display_name.
  AC2 – Display-name changes do not break enrollment linkage.
  AC3 – Name-collision scenarios produce correct independent enrollments.
  AC4 – No data loss / orphaned records on enrollment update.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidgetItem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_window(qapp):
    from ayehear.app.window import MainWindow
    from ayehear.models.runtime import RuntimeConfig

    with patch.dict(sys.modules, {"sounddevice": None, "faster_whisper": None}):
        win = MainWindow(runtime_config=RuntimeConfig())
    return win


def _set_item(list_widget, text: str, participant_id: str) -> QListWidgetItem:
    """Add a list item with a stable participant_id in UserRole."""
    item = QListWidgetItem(text)
    item.setData(Qt.ItemDataRole.UserRole, participant_id)
    list_widget.addItem(item)
    return item


# ===========================================================================
# AC1 – _enrolled_results keyed by participant_id, not display_name
# ===========================================================================


def test_enrolled_results_keyed_by_participant_id(qapp) -> None:
    """get_enrolled_results() must return participant_id as key, not display_name."""
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import EnrollmentResult, SpeakerManager

    mock_sm = MagicMock(spec=SpeakerManager)
    mock_sm.enroll.return_value = EnrollmentResult(
        participant_id="stable-uuid-001",
        display_name="Max Muster",
        profile_id="profile-abc123",
        embedding_dim=768,
        success=True,
    )
    dlg = EnrollmentDialog(
        pending_speakers=[("Max Muster", "Corp", "stable-uuid-001")],
        speaker_manager=mock_sm,
    )
    item = dlg._speaker_list.item(0)
    import numpy as np
    dlg._do_enroll(item, "Max Muster", "Corp", "stable-uuid-001", [0.1] * 4000)

    results = dlg.get_enrolled_results()
    # Key must be participant_id, not display_name
    assert "stable-uuid-001" in results
    assert "Max Muster" not in results
    assert results["stable-uuid-001"] == "profile-abc123"
    dlg.deleteLater()
    qapp.processEvents()


def test_window_enrolled_speakers_keyed_by_participant_id(qapp) -> None:
    """_enrolled_speakers in MainWindow must be keyed by participant_id after enrollment."""
    win = _make_window(qapp)
    win._speakers_list.clear()
    _set_item(win._speakers_list, "Anna Meier | Corp | pending enrollment", "pid-anna-001")

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Accepted
        mock_instance.get_enrolled_results.return_value = {"pid-anna-001": "prof-xyz"}
        MockDlg.return_value = mock_instance
        win._start_enrollment()

    assert "pid-anna-001" in win._enrolled_speakers
    assert "Anna Meier" not in win._enrolled_speakers
    win.deleteLater()
    qapp.processEvents()


# ===========================================================================
# AC2 – Display-name change does not break enrollment linkage
# ===========================================================================


def test_display_name_change_does_not_break_linkage(qapp) -> None:
    """Renaming a speaker's display name must not orphan the enrollment entry."""
    win = _make_window(qapp)
    win._speakers_list.clear()
    item = _set_item(win._speakers_list, "OldName | Corp | pending enrollment", "pid-stable-002")

    # First enrollment under original name
    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Accepted
        mock_instance.get_enrolled_results.return_value = {"pid-stable-002": "profile-001"}
        MockDlg.return_value = mock_instance
        win._start_enrollment()

    assert win._enrolled_speakers.get("pid-stable-002") == "profile-001"

    # Simulate a display-name change (inline edit) — UserRole UUID stays the same
    item.setText("NewName | Corp | enrolled (id: profile-001[:8])")

    # The UUID-based enrollment entry must still be intact
    assert win._enrolled_speakers.get("pid-stable-002") == "profile-001", (
        "Enrollment linkage must survive a display-name change"
    )
    win.deleteLater()
    qapp.processEvents()


# ===========================================================================
# AC3 – Name collisions: two participants with identical display names
# ===========================================================================


def test_two_speakers_same_name_enrolled_independently(qapp) -> None:
    """Two participants sharing a display name must receive independent enrollment entries."""
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import EnrollmentResult, SpeakerManager

    call_count = 0

    def mock_enroll(participant_id, display_name, audio_samples):
        nonlocal call_count
        call_count += 1
        return EnrollmentResult(
            participant_id=participant_id,
            display_name=display_name,
            profile_id=f"profile-{participant_id}",
            embedding_dim=768,
            success=True,
        )

    mock_sm = MagicMock(spec=SpeakerManager)
    mock_sm.enroll.side_effect = mock_enroll

    dlg = EnrollmentDialog(
        pending_speakers=[
            ("Max Muster", "CompA", "pid-max-alpha"),
            ("Max Muster", "CompB", "pid-max-beta"),  # same display name, different ID
        ],
        speaker_manager=mock_sm,
    )

    import numpy as np
    samples = [0.1] * 4000

    item_a = dlg._speaker_list.item(0)
    item_b = dlg._speaker_list.item(1)
    dlg._do_enroll(item_a, "Max Muster", "CompA", "pid-max-alpha", samples)
    dlg._do_enroll(item_b, "Max Muster", "CompB", "pid-max-beta", samples)

    results = dlg.get_enrolled_results()
    # Both entries must exist independently
    assert "pid-max-alpha" in results
    assert "pid-max-beta" in results
    assert results["pid-max-alpha"] != results["pid-max-beta"], "Different IDs must yield different profiles"
    dlg.deleteLater()
    qapp.processEvents()


def test_window_two_same_name_items_enrolled_independently(qapp) -> None:
    """In MainWindow, two list items with the same display name enroll under separate IDs."""
    win = _make_window(qapp)
    win._speakers_list.clear()
    _set_item(win._speakers_list, "Hans Müller | Corp | pending enrollment", "pid-hans-1")
    _set_item(win._speakers_list, "Hans Müller | AYE | pending enrollment", "pid-hans-2")

    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Accepted
        mock_instance.get_enrolled_results.return_value = {
            "pid-hans-1": "prof-h1",
            "pid-hans-2": "prof-h2",
        }
        MockDlg.return_value = mock_instance
        win._start_enrollment()

    assert win._enrolled_speakers.get("pid-hans-1") == "prof-h1"
    assert win._enrolled_speakers.get("pid-hans-2") == "prof-h2"
    # Both list items must show enrolled status
    for i in range(win._speakers_list.count()):
        assert "enrolled" in win._speakers_list.item(i).text()
    win.deleteLater()
    qapp.processEvents()


# ===========================================================================
# AC4 – No data loss on enrollment update (second run over already-enrolled)
# ===========================================================================


def test_re_enrollment_updates_profile_without_data_loss(qapp) -> None:
    """A second enrollment run must update the profile_id without orphaning the first entry."""
    win = _make_window(qapp)
    win._speakers_list.clear()
    _set_item(win._speakers_list, "Speaker | Org | pending enrollment", "pid-stable-re")

    # First enrollment
    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg:
        mock_instance = MagicMock()
        mock_instance.exec.return_value = QDialog.DialogCode.Accepted
        mock_instance.get_enrolled_results.return_value = {"pid-stable-re": "profile-v1"}
        MockDlg.return_value = mock_instance
        win._start_enrollment()

    assert win._enrolled_speakers["pid-stable-re"] == "profile-v1"

    # Change item back to pending to allow re-enrollment
    win._speakers_list.item(0).setText("Speaker | Org | pending enrollment")

    # Second enrollment with updated profile
    with patch("ayehear.app.window.EnrollmentDialog") as MockDlg2:
        mock_instance2 = MagicMock()
        mock_instance2.exec.return_value = QDialog.DialogCode.Accepted
        mock_instance2.get_enrolled_results.return_value = {"pid-stable-re": "profile-v2"}
        MockDlg2.return_value = mock_instance2
        win._start_enrollment()

    # Profile updated, same key — no orphan
    assert win._enrolled_speakers["pid-stable-re"] == "profile-v2"
    assert len([k for k in win._enrolled_speakers if k == "pid-stable-re"]) == 1
    win.deleteLater()
    qapp.processEvents()


# ===========================================================================
# EnrollmentDialog structural: pending_speakers now requires 3-tuple
# ===========================================================================


def test_enrollment_dialog_accepts_3_tuple_pending_speakers(qapp) -> None:
    """EnrollmentDialog must accept (name, org, participant_id) tuples."""
    from ayehear.app.enrollment_dialog import EnrollmentDialog
    from ayehear.services.speaker_manager import SpeakerManager

    dlg = EnrollmentDialog(
        pending_speakers=[("Alice", "Corp", "uuid-alice"), ("Bob", "AYE", "uuid-bob")],
        speaker_manager=MagicMock(spec=SpeakerManager),
    )
    assert dlg._speaker_list.count() == 2
    # UserRole must store all 3 components
    data0 = dlg._speaker_list.item(0).data(Qt.ItemDataRole.UserRole)
    assert data0 == ("Alice", "Corp", "uuid-alice")
    data1 = dlg._speaker_list.item(1).data(Qt.ItemDataRole.UserRole)
    assert data1 == ("Bob", "AYE", "uuid-bob")
    dlg.deleteLater()
    qapp.processEvents()


def test_window_initial_items_have_stable_uuids(qapp) -> None:
    """Items created during window init must carry a UUID in UserRole."""
    import re
    win = _make_window(qapp)
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    for i in range(win._speakers_list.count()):
        uid = win._speakers_list.item(i).data(Qt.ItemDataRole.UserRole)
        assert uid is not None, f"Item {i} has no UserRole UUID"
        assert uuid_pattern.match(str(uid)), f"Item {i} UserRole is not a valid UUID: {uid!r}"
    win.deleteLater()
    qapp.processEvents()


def test_add_speaker_assigns_uuid(qapp) -> None:
    """_add_speaker() must assign a stable UUID to the new item."""
    import re
    win = _make_window(qapp)
    initial_count = win._speakers_list.count()
    win._add_speaker()
    assert win._speakers_list.count() == initial_count + 1
    new_item = win._speakers_list.item(win._speakers_list.count() - 1)
    uid = new_item.data(Qt.ItemDataRole.UserRole)
    assert uid is not None
    assert re.match(r"^[0-9a-f-]{36}$", str(uid))
    win.deleteLater()
    qapp.processEvents()


def test_apply_participant_template_assigns_uuids(qapp) -> None:
    """_apply_participant_template() must assign a unique UUID to each item."""
    import re
    win = _make_window(qapp)
    win._participant_count.setValue(3)
    win._apply_participant_template()
    assert win._speakers_list.count() == 3
    uuids = []
    for i in range(win._speakers_list.count()):
        uid = win._speakers_list.item(i).data(Qt.ItemDataRole.UserRole)
        assert uid is not None
        assert re.match(r"^[0-9a-f-]{36}$", str(uid))
        uuids.append(uid)
    # All UUIDs must be unique
    assert len(set(uuids)) == 3, "Each item must receive a distinct UUID"
    win.deleteLater()
    qapp.processEvents()
