"""
HEAR-049: Smoke tests for the installer-managed PostgreSQL runtime path.

Tests validate the logic in:
  - Install-PostgresRuntime.ps1 (indirectly, via contract assertions)
  - Start-AyeHearRuntime.ps1   (post-install health check contract)
  - DatabaseBootstrap           (loopback enforcement, migration run)

These tests run without a live PostgreSQL instance by mocking the
psycopg/SQLAlchemy layer.  They document the expected runtime contract so that
clean-machine validation can verify the same invariants on a real install.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─── Fixtures ─────────────────────────────────────────────────────────────────

DSN_LOOPBACK     = "postgresql://ayehear:secret@127.0.0.1:5433/ayehear"
DSN_LOCALHOST    = "postgresql://ayehear:secret@localhost:5433/ayehear"
DSN_EXPOSED      = "postgresql://ayehear:secret@0.0.0.0:5433/ayehear"
DSN_REMOTE       = "postgresql://ayehear:secret@192.168.1.10:5433/ayehear"


# ─── DSN file path logic ─────────────────────────────────────────────────────

class TestDsnFilePath:
    """The DSN file must live in the protected runtime directory."""

    def test_dsn_path_under_install_root(self):
        install_root = Path("C:\\AyeHear")
        dsn_file = install_root / "runtime" / "pg.dsn"
        assert dsn_file.parts[-2] == "runtime"
        assert dsn_file.name == "pg.dsn"

    def test_dsn_not_in_app_directory(self):
        """DSN must never be co-located with the app bundle (would be world-readable)."""
        install_root = Path("C:\\AyeHear")
        app_dir = install_root / "app"
        dsn_file = install_root / "runtime" / "pg.dsn"
        # pg.dsn must not be a descendant of app/
        assert not str(dsn_file).startswith(str(app_dir))

    def test_dsn_not_in_source_tree(self, tmp_path):
        """Ensure no pg.dsn is present in the source tree (security check)."""
        repo_root = Path(__file__).parent.parent
        dsn_candidates = list(repo_root.rglob("pg.dsn"))
        # Exclude the tmp_path itself if any fixture created one
        dsn_candidates = [p for p in dsn_candidates if not str(p).startswith(str(tmp_path))]
        assert dsn_candidates == [], (
            f"pg.dsn found in source tree: {dsn_candidates}. "
            "DSN files must never be committed (ADR-0006, ADR-0003)."
        )


# ─── DatabaseBootstrap loopback enforcement ──────────────────────────────────

class TestDatabaseBootstrapLoopback:
    """DatabaseBootstrap._is_loopback_address must enforce ADR-0006."""

    @pytest.fixture
    def bootstrap(self):
        from ayehear.storage.database import DatabaseBootstrap, DatabaseConfig
        return DatabaseBootstrap(DatabaseConfig(dsn=DSN_LOOPBACK))

    @pytest.mark.parametrize("addr,expected", [
        ("localhost",       True),
        ("127.0.0.1",      True),
        ("127.0.0.2",      True),   # whole 127/8 block is loopback
        ("::1",            True),
        ("",               True),   # empty = no listener configured
        ("*",              False),
        ("0.0.0.0",        False),
        ("192.168.1.1",    False),
        ("localhost,*",    False),  # mixed — rejected
    ])
    def test_loopback_detection(self, bootstrap, addr, expected):
        from ayehear.storage.database import DatabaseBootstrap
        result = DatabaseBootstrap._is_loopback_address(addr)
        assert result == expected, f"_is_loopback_address({addr!r}) should be {expected}"

    def test_exposed_dsn_raises_on_check(self, bootstrap):
        """Bootstrap must raise RuntimeError when listen_addresses is not loopback."""
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value="0.0.0.0")
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = mock_row

        with pytest.raises(RuntimeError, match="beyond loopback"):
            bootstrap._check_loopback_only(mock_conn)

    def test_loopback_dsn_passes_check(self, bootstrap):
        """Bootstrap must not raise for localhost-only listen_addresses."""
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(return_value="localhost")
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = mock_row

        # Should not raise
        bootstrap._check_loopback_only(mock_conn)


# ─── DatabaseBootstrap migration runner ───────────────────────────────────────

class TestDatabaseBootstrapMigrations:
    """Migrations must run from the correct embedded directory."""

    def test_migrations_directory_exists(self):
        from ayehear.storage import database as db_mod
        migrations_dir = db_mod._MIGRATIONS_DIR
        assert migrations_dir.is_dir(), (
            f"Migrations directory missing: {migrations_dir}"
        )

    def test_migrations_are_ordered_sql_files(self):
        from ayehear.storage import database as db_mod
        files = sorted(db_mod._MIGRATIONS_DIR.glob("*.sql"))
        assert len(files) >= 1, "At least one migration file must exist"
        for f in files:
            assert f.suffix == ".sql"
            # Filename must start with a 3-digit sequence number
            assert f.name[:3].isdigit(), (
                f"Migration filename must start with sequence number: {f.name}"
            )

    def test_migrations_contain_initial_schema(self):
        from ayehear.storage import database as db_mod
        files = sorted(db_mod._MIGRATIONS_DIR.glob("*.sql"))
        first = files[0].read_text(encoding="utf-8").lower()
        assert "create table" in first or "create sequence" in first, (
            "First migration should contain schema DDL (CREATE TABLE or CREATE SEQUENCE)"
        )

    def test_bootstrap_calls_migrations(self):
        """bootstrap() must call _run_migrations."""
        from ayehear.storage.database import DatabaseBootstrap, DatabaseConfig
        db = DatabaseBootstrap(DatabaseConfig(dsn=DSN_LOOPBACK))

        with patch.object(db, "_create_engine") as mock_engine, \
             patch.object(db, "_verify_connection"), \
             patch.object(db, "_run_migrations") as mock_migrate, \
             patch("ayehear.storage.database.sessionmaker"):
            mock_engine.return_value = MagicMock()
            db.bootstrap()
            mock_migrate.assert_called_once()


# ─── Health check contract ────────────────────────────────────────────────────

class TestStartupHealthCheckContract:
    """Documents the contract that Start-AyeHearRuntime.ps1 validates."""

    def test_health_check_script_exists(self):
        script = Path(__file__).parent.parent / "tools" / "scripts" / "Start-AyeHearRuntime.ps1"
        assert script.is_file(), f"Health check script missing: {script}"

    def test_provisioning_script_exists(self):
        script = Path(__file__).parent.parent / "tools" / "scripts" / "Install-PostgresRuntime.ps1"
        assert script.is_file(), f"Provisioning script missing: {script}"

    def test_health_check_script_checks_service(self):
        """Health check script must reference the AyeHearDB service name."""
        script = Path(__file__).parent.parent / "tools" / "scripts" / "Start-AyeHearRuntime.ps1"
        content = script.read_text(encoding="utf-8")
        assert "AyeHearDB" in content

    def test_health_check_script_checks_loopback(self):
        """Health check script must enforce the loopback-only posture."""
        script = Path(__file__).parent.parent / "tools" / "scripts" / "Start-AyeHearRuntime.ps1"
        content = script.read_text(encoding="utf-8")
        assert "listen_addresses" in content.lower() or "loopback" in content.lower()

    def test_health_check_script_checks_schema(self):
        """Health check script must verify the schema baseline (meetings table)."""
        script = Path(__file__).parent.parent / "tools" / "scripts" / "Start-AyeHearRuntime.ps1"
        content = script.read_text(encoding="utf-8")
        assert "meetings" in content

    def test_provisioning_script_generates_password(self):
        """Provisioning script must generate a per-install password, not use a static default."""
        script = Path(__file__).parent.parent / "tools" / "scripts" / "Install-PostgresRuntime.ps1"
        content = script.read_text(encoding="utf-8")
        assert "New-SecurePassword" in content
        # Ensure no static hardcoded credential placeholder
        assert "password123" not in content.lower()
        assert "secret123" not in content.lower()

    def test_provisioning_script_restricts_acl(self):
        """DSN file must have a restricted ACL set after writing (ADR-0009)."""
        script = Path(__file__).parent.parent / "tools" / "scripts" / "Install-PostgresRuntime.ps1"
        content = script.read_text(encoding="utf-8")
        assert "Protect-DsnFile" in content
        assert "SetAccessRuleProtection" in content

    def test_provisioning_script_enforces_loopback_conf(self):
        """Provisioning script must write listen_addresses = 'localhost' to postgresql.conf."""
        script = Path(__file__).parent.parent / "tools" / "scripts" / "Install-PostgresRuntime.ps1"
        content = script.read_text(encoding="utf-8")
        assert "listen_addresses" in content
        assert "localhost" in content

    def test_installer_iss_calls_provisioning_script(self):
        """Inno Setup installer must reference Install-PostgresRuntime.ps1 in [Run]."""
        iss = Path(__file__).parent.parent / "build" / "installer" / "ayehear-installer.iss"
        content = iss.read_text(encoding="utf-8")
        assert "Install-PostgresRuntime.ps1" in content

    def test_installer_iss_calls_health_check(self):
        """Inno Setup installer must run the health check post-install."""
        iss = Path(__file__).parent.parent / "build" / "installer" / "ayehear-installer.iss"
        content = iss.read_text(encoding="utf-8")
        assert "Start-AyeHearRuntime.ps1" in content

    def test_installer_nsi_calls_provisioning_script(self):
        """NSIS installer must reference Install-PostgresRuntime.ps1."""
        nsi = Path(__file__).parent.parent / "build" / "installer" / "ayehear-installer.nsi"
        content = nsi.read_text(encoding="utf-8")
        assert "Install-PostgresRuntime.ps1" in content

    def test_installer_nsi_stops_service_on_uninstall(self):
        """NSIS uninstall section must stop the AyeHearDB service."""
        nsi = Path(__file__).parent.parent / "build" / "installer" / "ayehear-installer.nsi"
        content = nsi.read_text(encoding="utf-8")
        assert "Stop-Service" in content and "AyeHearDB" in content


# ─── DSN environment variable injection ───────────────────────────────────────

class TestDsnEnvironmentInjection:
    """Development / CI path: AYEHEAR_DB_DSN env var must override the default DSN."""

    def test_env_dsn_is_accepted(self):
        """DatabaseConfig must accept a DSN from env var (development / CI path)."""
        from ayehear.storage.database import DatabaseConfig
        cfg = DatabaseConfig(dsn=DSN_LOOPBACK)
        assert cfg.dsn == DSN_LOOPBACK

    def test_empty_dsn_raises(self):
        """DatabaseConfig must reject an empty DSN (fail closed)."""
        from ayehear.storage.database import DatabaseConfig
        with pytest.raises(ValueError, match="must not be empty"):
            DatabaseConfig(dsn="")

    def test_load_runtime_dsn_prefers_env_over_file(self, monkeypatch, tmp_path):
        """AYEHEAR_DB_DSN must override any installer file during dev/CI."""
        from ayehear.storage.database import load_runtime_dsn

        dsn_file = tmp_path / "runtime" / "pg.dsn"
        dsn_file.parent.mkdir(parents=True)
        dsn_file.write_text(DSN_LOCALHOST, encoding="utf-8")
        monkeypatch.setenv("AYEHEAR_DB_DSN", DSN_LOOPBACK)

        assert load_runtime_dsn(tmp_path) == DSN_LOOPBACK

    def test_load_runtime_dsn_reads_installer_file(self, tmp_path):
        """Installer-managed DSN file must be readable from runtime/pg.dsn."""
        from ayehear.storage.database import load_runtime_dsn, runtime_dsn_path

        dsn_file = runtime_dsn_path(tmp_path)
        dsn_file.parent.mkdir(parents=True, exist_ok=True)  # runtime_dir() may create it
        dsn_file.write_text(DSN_LOCALHOST, encoding="utf-8")

        assert load_runtime_dsn(tmp_path) == DSN_LOCALHOST
