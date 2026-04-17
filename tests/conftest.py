"""pytest configuration and shared fixtures for AYE Hear test suite.

Provides a session-scoped QApplication fixture that keeps a module-level
reference to prevent premature garbage collection on Windows (PySide6
access-violation mitigation during pytest shutdown).

Automatically patches all modal Qt dialogs (QDialog.exec) to auto-accept by
default, with automatic population of QLineEdit fields to avoid empty-string
rejections. Tests can override by explicitly patching QDialog.exec.
"""
from __future__ import annotations

import gc
import sys
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox

# Module-level reference so Python's GC cannot collect the QApplication
# while the test session is active.  Without this, Windows raises a native
# access violation in Qt's event-dispatcher thread during pytest teardown.
_QAPP: QApplication | None = None


def _auto_fill_dialog_fields(dialog_instance: QDialog) -> None:
    """Fill empty QLineEdit fields with placeholder text so validation passes.

    When a modal dialog is auto-accepted in tests, QLineEdit fields that are
    empty may trigger validation checks and prevent the action. This function
    pre-fills any empty QLineEdit with generic placeholder text.
    """
    for line_edit in dialog_instance.findChildren(QLineEdit):
        if not line_edit.text():
            # Use placeholder if available, otherwise generic text
            placeholder = line_edit.placeholderText()
            if placeholder:
                line_edit.setText(placeholder)
            else:
                # Fallback: use field name or generic text
                line_edit.setText(f"Testuser {id(line_edit) % 1000}")


def _patched_dialog_exec(dialog_instance: QDialog) -> int:
    """Auto-accept dialogs after filling empty fields.

    This allows tests to run without modal dialog blocking, while ensuring
    validation checks in the dialog handler (e.g., empty-name rejection) don't
    prevent the tested action from occurring.
    """
    _auto_fill_dialog_fields(dialog_instance)
    return QDialog.DialogCode.Accepted


@pytest.fixture(scope="session", autouse=True)
def patch_qt_dialogs():
    """Auto-patch all QDialog.exec() to accept by default.

    This prevents modal dialogs from blocking tests waiting for user input.
    Individual tests can override by explicitly patching QDialog.exec.
    """
    with patch.object(QDialog, "exec", _patched_dialog_exec):
        yield


@pytest.fixture(scope="session", autouse=True)
def patch_qt_messageboxes():
    """Auto-patch QMessageBox static convenience methods to prevent modal blocking.

    QMessageBox static methods (information, warning, critical, question) call
    the underlying C++ implementation directly, bypassing the QDialog.exec patch.
    This fixture suppresses them globally so no blocking dialog appears during
    the test session.

    - information / warning / critical → return Ok (no-op, return value unused)
    - question → return Yes (auto-confirm all confirmation prompts)

    Individual tests that need to assert on calls or control the return value
    can shadow this patch with an explicit ``with patch(...) as mock:`` block.
    """
    with (
        patch.object(QMessageBox, "information", return_value=QMessageBox.StandardButton.Ok),
        patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok),
        patch.object(QMessageBox, "critical", return_value=QMessageBox.StandardButton.Ok),
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
    ):
        yield


@pytest.fixture(scope="session")
def qapp() -> QApplication:  # type: ignore[return]
    """Single QApplication for the entire test session.

    The module-level ``_QAPP`` reference ensures the C++ object outlives
    the last test and is only released after Python's atexit handlers run,
    giving Qt's event dispatcher time to exit cleanly.
    """
    global _QAPP
    existing = QApplication.instance()
    if existing is not None:
        _QAPP = existing  # type: ignore[assignment]
    else:
        _QAPP = QApplication(sys.argv[:1])
    yield _QAPP  # type: ignore[misc]
    # Flush remaining Qt events and force GC of Qt objects before QApplication
    # is released. Without this, Windows raises a native access violation in
    # Qt's event-dispatcher thread during pytest teardown.
    gc.collect()
    for _ in range(5):
        _QAPP.processEvents()
    gc.collect()
