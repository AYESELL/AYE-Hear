"""Application-level logging setup for AYE Hear.

Configures a RotatingFileHandler so all logger.* calls from every
subsystem are persisted to disk — critical for diagnosing installer
and runtime failures in the packaged (no-console) EXE.

Log location: <install_root>/logs/ayehear.log  (ADR-0011)
Install root resolution: AYEHEAR_INSTALL_DIR env → packaged EXE discovery → cwd
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ayehear.utils.paths import log_dir as _resolve_log_dir_from_root

_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 5 * 1024 * 1024   # 5 MB per file
_BACKUP_COUNT = 3               # keep ayehear.log, .1, .2, .3


def _resolve_log_dir(install_root: Path | None = None) -> Path:
    """Return the log directory using install-root-relative resolution (ADR-0011)."""
    return _resolve_log_dir_from_root(install_root)


def setup_logging(level: int = logging.DEBUG) -> Path:
    """Configure root logger with console + rotating file handlers.

    Returns the resolved log file path (useful for surfacing in the UI).
    Safe to call multiple times — skips setup if already configured.
    """
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. pytest or second call)
        for h in root.handlers:
            if isinstance(h, RotatingFileHandler):
                return Path(h.baseFilename)
        # Has handlers but no file handler — add one
    else:
        root.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # ── Console handler (stdout) ─────────────────────────────────────────────
    # Suppressed in packaged EXE (console=False), but useful in dev/CI.
    if not getattr(sys, "frozen", False):
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        root.addHandler(console)

    # ── Rotating file handler (ADR-0011: install-root-relative, not fixed) ─────
    log_dir = _resolve_log_dir()
    log_path = log_dir / "ayehear.log"

    try:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        root.setLevel(level)

        # First log entry — easy to find in the file
        logging.getLogger(__name__).info(
            "AYE Hear logging initialised  |  log=%s  |  frozen=%s",
            log_path,
            getattr(sys, "frozen", False),
        )
    except OSError as exc:
        # Never crash the app because of a logging failure
        logging.getLogger(__name__).warning(
            "Could not open log file %s: %s — file logging disabled.", log_path, exc
        )
        log_path = Path("<unavailable>")

    return log_path
