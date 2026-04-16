"""Tests for HEAR-083: Installer install-root handoff to runtime provisioning.

Verifies:
- DSN is written/read from install-root-relative path, not hard-coded C:\\AyeHear
- Non-default install paths (e.g. D:\\CustomInstall) resolve correctly
- App bootstrap picks up DSN from the resolved install root
- AYEHEAR_INSTALL_DIR env var correctly overrides EXE self-discovery
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ayehear.utils.paths import dsn_file_path, resolve_install_root, runtime_dir
from ayehear.storage.database import load_runtime_dsn, runtime_dsn_path


# ---------------------------------------------------------------------------
# AC1/AC2: DSN path resolves to the actual install root, not C:\AyeHear
# ---------------------------------------------------------------------------

class TestDsnResolvesFromInstallRoot:
    def test_dsn_under_non_default_install_root(self, tmp_path: Path) -> None:
        """DSN file path is under the provided install root, not C:\\AyeHear."""
        install_root = tmp_path / "D_CustomInstall" / "AyeHear"
        install_root.mkdir(parents=True)

        dsn_path = dsn_file_path(install_root=install_root)

        assert dsn_path == install_root / "runtime" / "pg.dsn"
        assert "C:" not in str(dsn_path) or str(install_root).startswith("C:")

    def test_dsn_not_under_hardcoded_c_ayehear_when_env_set(self, tmp_path: Path) -> None:
        """When AYEHEAR_INSTALL_DIR points elsewhere, DSN is NOT at C:\\AyeHear."""
        custom_root = tmp_path / "custom_root"
        custom_root.mkdir()

        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(custom_root)}):
            dsn_path = dsn_file_path()

        assert str(dsn_path).startswith(str(custom_root))
        assert "C:\\AyeHear" not in str(dsn_path)

    def test_runtime_dir_created_under_install_root(self, tmp_path: Path) -> None:
        """runtime_dir() creates the runtime/ subdirectory under install root."""
        install_root = tmp_path / "AyeHear"
        install_root.mkdir()

        rt_dir = runtime_dir(install_root=install_root)

        assert rt_dir == install_root / "runtime"
        assert rt_dir.is_dir()

    def test_dsn_path_via_database_module(self, tmp_path: Path) -> None:
        """database.runtime_dsn_path() delegates to utils.paths correctly."""
        install_root = tmp_path / "custom"
        install_root.mkdir()

        dsn_path = runtime_dsn_path(install_root=install_root)

        assert dsn_path == install_root / "runtime" / "pg.dsn"


# ---------------------------------------------------------------------------
# AC2: DSN written and read from same install-root-relative path
# ---------------------------------------------------------------------------

class TestDsnWriteReadRoundtrip:
    DSN_CONTENT = "postgresql://ayehear:secret123@127.0.0.1:5433/ayehear"

    def test_dsn_read_from_non_default_install_root(self, tmp_path: Path) -> None:
        """load_runtime_dsn() reads DSN written at the install-root-relative path."""
        install_root = tmp_path / "NonDefaultPath"
        rt_dir = install_root / "runtime"
        rt_dir.mkdir(parents=True)

        dsn_file = rt_dir / "pg.dsn"
        dsn_file.write_text(self.DSN_CONTENT, encoding="utf-8")

        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(install_root)}):
            loaded = load_runtime_dsn()

        assert loaded == self.DSN_CONTENT

    def test_load_runtime_dsn_returns_none_when_file_absent(self, tmp_path: Path) -> None:
        """load_runtime_dsn() returns None when DSN file does not exist."""
        empty_root = tmp_path / "EmptyInstall"
        empty_root.mkdir()

        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(empty_root)}):
            loaded = load_runtime_dsn()

        assert loaded is None

    def test_dsn_file_at_correct_path_after_write(self, tmp_path: Path) -> None:
        """Verify the absolute DSN path matches the install-root-relative contract."""
        install_root = tmp_path / "E_Drive" / "Programs" / "AyeHear"
        install_root.mkdir(parents=True)

        expected_dsn_path = install_root / "runtime" / "pg.dsn"
        resolved = dsn_file_path(install_root=install_root)

        assert resolved == expected_dsn_path
        assert resolved.parent.name == "runtime"


# ---------------------------------------------------------------------------
# AC3: EXE self-discovery correctly resolves non-default install root
# ---------------------------------------------------------------------------

class TestExeSelfDiscovery:
    def test_frozen_exe_in_app_subdir_resolves_to_parent(self, tmp_path: Path) -> None:
        """Frozen EXE at <root>/app/AyeHear.exe  -> install_root = <root>."""
        install_root = tmp_path / "D_AyeHear"
        app_dir = install_root / "app"
        app_dir.mkdir(parents=True)
        fake_exe = app_dir / "AyeHear.exe"
        fake_exe.touch()

        env = {k: v for k, v in os.environ.items() if k != "AYEHEAR_INSTALL_DIR"}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(fake_exe)):
            resolved = resolve_install_root()

        assert resolved == install_root.resolve()

    def test_frozen_exe_on_different_drive_resolves_correctly(self, tmp_path: Path) -> None:
        """Install root must be EXE's grandparent regardless of drive letter."""
        # Simulate a non-C: path (tmp_path may be C: but the resolution logic
        # is drive-agnostic — we verify the grandparent relationship holds)
        install_root = tmp_path / "custom_drive_sim" / "AyeHear_v2"
        app_dir = install_root / "app"
        app_dir.mkdir(parents=True)
        fake_exe = app_dir / "AyeHear.exe"
        fake_exe.touch()

        env = {k: v for k, v in os.environ.items() if k != "AYEHEAR_INSTALL_DIR"}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(fake_exe)):
            resolved = resolve_install_root()

        assert resolved == install_root.resolve()
        assert resolved.name == "AyeHear_v2"

    def test_env_var_overrides_exe_discovery_on_non_default_path(self, tmp_path: Path) -> None:
        """AYEHEAR_INSTALL_DIR env var has priority over EXE self-discovery."""
        env_root = tmp_path / "env_override_root"
        env_root.mkdir()

        # Set up a fake frozen EXE at a different location
        fake_exe_root = tmp_path / "different_path" / "app"
        fake_exe_root.mkdir(parents=True)
        fake_exe = fake_exe_root / "AyeHear.exe"
        fake_exe.touch()

        with patch.dict(os.environ, {"AYEHEAR_INSTALL_DIR": str(env_root)}), \
             patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(fake_exe)):
            resolved = resolve_install_root()

        # env var wins over EXE discovery
        assert resolved == env_root


# ---------------------------------------------------------------------------
# AC4: Installer script contract (PowerShell-level, validated by Python proxy)
# ---------------------------------------------------------------------------

class TestInstallerScriptContract:
    """Validates the contract that installer scripts must satisfy.

    The actual PowerShell logic is tested via contract assertions.
    """

    def test_iss_run_section_has_no_hardcoded_c_ayehear(self) -> None:
        """ISS [Run] section must not hard-code C:\\AyeHear as -InstallDir."""
        iss_path = Path(__file__).parent.parent / "build" / "installer" / "ayehear-installer.iss"
        content = iss_path.read_text(encoding="utf-8")

        # The [Run] section parameters must not pass the literal C:\AyeHear
        # Instead they should use {code:GetInstallRoot}
        assert '-InstallDir ""C:\\AyeHear""' not in content, (
            "HEAR-083: [Run] section still hard-codes -InstallDir C:\\AyeHear. "
            "Use {code:GetInstallRoot} instead."
        )

    def test_iss_has_get_install_root_function(self) -> None:
        """ISS [Code] section must define GetInstallRoot function.

        HEAR-089 updated the implementation to use a conditional branch that
        handles both paths ending in \\app and custom paths without the suffix.
        """
        iss_path = Path(__file__).parent.parent / "build" / "installer" / "ayehear-installer.iss"
        content = iss_path.read_text(encoding="utf-8")

        assert "function GetInstallRoot" in content, (
            "HEAR-083: ISS [Code] section must define GetInstallRoot(Param) function."
        )
        # HEAR-089: corrected implementation uses WizardDirValue with a conditional
        # branch, not the unconditional ExtractFileDir one-liner.
        assert "WizardDirValue" in content, (
            "HEAR-083/HEAR-089: GetInstallRoot must reference WizardDirValue."
        )

    def test_iss_sets_ayehear_install_dir_registry(self) -> None:
        """ISS must set AYEHEAR_INSTALL_DIR in the machine registry for robustness."""
        iss_path = Path(__file__).parent.parent / "build" / "installer" / "ayehear-installer.iss"
        content = iss_path.read_text(encoding="utf-8")

        assert "AYEHEAR_INSTALL_DIR" in content, (
            "HEAR-083: ISS must set AYEHEAR_INSTALL_DIR env var via [Registry] section."
        )

    def test_install_postgres_script_accepts_install_dir_param(self) -> None:
        """Install-PostgresRuntime.ps1 must accept -InstallDir parameter."""
        ps1_path = Path(__file__).parent.parent / "tools" / "scripts" / "Install-PostgresRuntime.ps1"
        content = ps1_path.read_text(encoding="utf-8")

        assert "[string]$InstallDir" in content, (
            "HEAR-083: Install-PostgresRuntime.ps1 must accept -InstallDir parameter."
        )

    def test_start_runtime_script_accepts_install_dir_param(self) -> None:
        """Start-AyeHearRuntime.ps1 must accept -InstallDir parameter."""
        ps1_path = Path(__file__).parent.parent / "tools" / "scripts" / "Start-AyeHearRuntime.ps1"
        content = ps1_path.read_text(encoding="utf-8")

        assert "[string]$InstallDir" in content, (
            "HEAR-083: Start-AyeHearRuntime.ps1 must accept -InstallDir parameter."
        )

    def test_install_postgres_script_has_no_hardcoded_c_ayehear_in_paths(self) -> None:
        """Install-PostgresRuntime.ps1 must not hard-code C:\\AyeHear in path derivations."""
        ps1_path = Path(__file__).parent.parent / "tools" / "scripts" / "Install-PostgresRuntime.ps1"
        content = ps1_path.read_text(encoding="utf-8")

        # All path constants must reference $InstallDir, not C:\AyeHear literals
        # Skip comments (lines starting with #) and the default parameter value
        code_lines = [
            line for line in content.splitlines()
            if not line.strip().startswith("#") and not line.strip().startswith("[string]$InstallDir")
        ]
        for line in code_lines:
            assert "C:\\\\AyeHear" not in line and "'C:\\AyeHear'" not in line and '"C:\\AyeHear"' not in line, (
                f"HEAR-083: Hard-coded C:\\AyeHear found in non-comment line: {line.strip()!r}"
            )
