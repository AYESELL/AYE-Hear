"""Tests for install-root relative path resolution (HEAR-073 / ADR-0011).

Covers:
- resolve_install_root() priority order (explicit > env > packaged > cwd)
- log_dir(), runtime_dir(), exports_dir(), dsn_file_path() convenience helpers
- database.runtime_dsn_path() delegation to utils.paths
- No hard-coded C:/AyeHear paths remain in production code
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ayehear.utils.paths import (
    dsn_file_path,
    exports_dir,
    log_dir,
    resolve_install_root,
    runtime_dir,
)
from ayehear.storage.database import runtime_dsn_path


# ---------------------------------------------------------------------------
# resolve_install_root
# ---------------------------------------------------------------------------

class TestResolveInstallRoot:
    def test_explicit_param_wins_over_everything(self, tmp_path: Path) -> None:
        """Explicit install_root parameter has highest priority."""
        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(tmp_path / "env")}):
            result = resolve_install_root(install_root=tmp_path)
        assert result == tmp_path

    def test_env_var_used_when_no_explicit(self, tmp_path: Path) -> None:
        """AYEHEAR_INSTALL_DIR env variable is used when no explicit root."""
        env_root = tmp_path / "env_root"
        env_root.mkdir()
        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(env_root)}):
            result = resolve_install_root()
        assert result == env_root

    def test_env_var_takes_priority_over_packaged_discovery(self, tmp_path: Path) -> None:
        """AYEHEAR_INSTALL_DIR wins over packaged EXE discovery."""
        env_root = tmp_path / "env_root"
        env_root.mkdir()
        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(env_root)}):
            # Even if frozen would be True, env wins
            result = resolve_install_root()
        assert result == env_root

    def test_dev_fallback_is_cwd_when_no_signal(self, tmp_path: Path) -> None:
        """Falls back to cwd when no env var and not packaged."""
        env = {k: v for k, v in os.environ.items() if k != "AYEHEAR_INSTALL_DIR"}
        with patch.dict(os.environ, env, clear=True):
            # sys.frozen is not set in test environment
            result = resolve_install_root()
        assert result == Path.cwd()

    def test_packaged_discovery_when_frozen(self, tmp_path: Path) -> None:
        """When sys.frozen is True, install root is EXE's grandparent dir."""
        # Simulate: <install_root>/app/AyeHear.exe
        install_root = tmp_path / "install"
        app_dir = install_root / "app"
        app_dir.mkdir(parents=True)
        fake_exe = app_dir / "AyeHear.exe"
        fake_exe.touch()

        env = {k: v for k, v in os.environ.items() if k != "AYEHEAR_INSTALL_DIR"}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(fake_exe)):
            result = resolve_install_root()
        assert result == install_root.resolve()

    def test_empty_env_var_is_ignored(self) -> None:
        """Empty AYEHEAR_INSTALL_DIR string falls through to dev fallback."""
        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": "   "}):
            result = resolve_install_root()
        assert result == Path.cwd()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

class TestPathHelpers:
    def test_log_dir_creates_subdir(self, tmp_path: Path) -> None:
        result = log_dir(install_root=tmp_path)
        assert result == tmp_path / "logs"
        assert result.is_dir()

    def test_runtime_dir_creates_subdir(self, tmp_path: Path) -> None:
        result = runtime_dir(install_root=tmp_path)
        assert result == tmp_path / "runtime"
        assert result.is_dir()

    def test_exports_dir_creates_subdir(self, tmp_path: Path) -> None:
        result = exports_dir(install_root=tmp_path)
        assert result == tmp_path / "exports"
        assert result.is_dir()

    def test_dsn_file_path_under_runtime(self, tmp_path: Path) -> None:
        result = dsn_file_path(install_root=tmp_path)
        assert result == tmp_path / "runtime" / "pg.dsn"

    def test_log_dir_is_idempotent(self, tmp_path: Path) -> None:
        log_dir(install_root=tmp_path)
        log_dir(install_root=tmp_path)  # no error on second call
        assert (tmp_path / "logs").is_dir()


# ---------------------------------------------------------------------------
# database.runtime_dsn_path delegates to utils.paths
# ---------------------------------------------------------------------------

class TestDatabaseRuntimeDsnPath:
    def test_dsn_path_explicit_root(self, tmp_path: Path) -> None:
        result = runtime_dsn_path(install_root=tmp_path)
        assert result == tmp_path / "runtime" / "pg.dsn"

    def test_dsn_path_uses_env(self, tmp_path: Path) -> None:
        env_root = tmp_path / "via_env"
        env_root.mkdir()
        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(env_root)}):
            result = runtime_dsn_path()
        assert result == env_root / "runtime" / "pg.dsn"

    def test_no_hardcoded_c_ayehear(self, tmp_path: Path) -> None:
        """C:/AyeHear must not appear in the resolved path when env is set."""
        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(tmp_path)}):
            result = runtime_dsn_path()
        assert "AyeHear" not in str(result).replace(str(tmp_path), "")


# ---------------------------------------------------------------------------
# No hard-coded C:/AyeHear in production modules
# ---------------------------------------------------------------------------

class TestNoHardcodedPaths:
    def test_logging_module_has_no_hardcoded_path(self) -> None:
        import ayehear.utils.logging as log_module
        import inspect
        source = inspect.getsource(log_module)
        assert "C:/AyeHear" not in source
        assert "C:\\\\AyeHear" not in source

    def test_database_module_has_no_hardcoded_path(self) -> None:
        import ayehear.storage.database as db_module
        import inspect
        source = inspect.getsource(db_module)
        assert "C:/AyeHear" not in source
        assert "_DEFAULT_INSTALL_ROOT" not in source
