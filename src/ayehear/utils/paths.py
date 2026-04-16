"""Install-root relative path resolution for AYE Hear (ADR-0011).

All runtime and artifact paths derive from a single *install root* resolved
in this module.  Call :func:`resolve_install_root` once and derive every
child path from its result — do NOT hard-code ``C:/AyeHear`` or any other
absolute production path elsewhere in the codebase.

Resolution priority (per ADR-0011 §1):

1. ``AYEHEAR_INSTALL_DIR`` environment variable (set by installer or launcher)
2. ``install_root`` explicit parameter (injected by tests or launcher)
3. Packaged-runtime self-discovery: parent of the directory that contains the
   frozen EXE (``sys.executable`` when ``sys.frozen`` is True)
4. Development / CI fallback: repository working directory

Normative subdirectory layout (ADR-0011 §2):

- ``app/``      — packaged application bundle
- ``runtime/``  — installer-managed DSN, runtime state files
- ``logs/``     — application + PostgreSQL + helper-script logs
- ``exports/``  — user-generated meeting artifacts (surfaced by UI)
- ``pgsql/``    — PostgreSQL binaries managed by installer
- ``data/``     — PostgreSQL data directory and service state
- ``scripts/``  — post-install operational scripts

Security note (ADR-0011 §6):
- Paths remain local-only; no cloud-backed path dependencies.
- Logs must not contain transcript text, speaker embeddings or raw audio.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Environment variable name used by the installer / launcher
_INSTALL_DIR_ENV = "AYEHEAR_INSTALL_DIR"


def resolve_install_root(install_root: Path | None = None) -> Path:
    """Return the canonical install root as a :class:`~pathlib.Path`.

    Resolution order (ADR-0011 §1):

    1. Explicit *install_root* parameter
    2. ``AYEHEAR_INSTALL_DIR`` environment variable
    3. Packaged-runtime self-discovery (EXE location)
    4. Dev / CI fallback (current working directory)

    Args:
        install_root: Optional explicit override (tests or launcher).

    Returns:
        Resolved install root.  Never raises; falls back to ``cwd`` on error.
    """
    # 1. Explicit parameter
    if install_root is not None:
        return install_root

    # 2. Environment variable
    env_val = os.environ.get(_INSTALL_DIR_ENV, "").strip()
    if env_val:
        return Path(env_val)

    # 3. Packaged EXE self-discovery
    #    sys.frozen is True when running inside a PyInstaller bundle.
    #    Layout: <install_root>/app/AyeHear.exe  → install_root = exe.parent.parent
    if getattr(sys, "frozen", False):
        try:
            exe_path = Path(sys.executable).resolve()
            # exe is in app/ — install root is one level up
            candidate = exe_path.parent.parent
            if candidate.exists():
                return candidate
        except Exception:
            pass  # fall through to dev fallback

    # 4. Dev / CI fallback
    return Path.cwd()


def log_dir(install_root: Path | None = None) -> Path:
    """Return ``<install_root>/logs``, creating it if necessary."""
    path = resolve_install_root(install_root) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def runtime_dir(install_root: Path | None = None) -> Path:
    """Return ``<install_root>/runtime``, creating it if necessary."""
    path = resolve_install_root(install_root) / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def exports_dir(install_root: Path | None = None) -> Path:
    """Return ``<install_root>/exports``, creating it if necessary."""
    path = resolve_install_root(install_root) / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def dsn_file_path(install_root: Path | None = None) -> Path:
    """Return the canonical DSN file path ``<install_root>/runtime/pg.dsn``."""
    return runtime_dir(install_root) / "pg.dsn"
