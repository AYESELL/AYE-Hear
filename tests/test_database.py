"""Tests for DatabaseBootstrap (HEAR-008, HEAR-026, HEAR-027) — without a live PostgreSQL connection."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ayehear.storage.database import DatabaseConfig, DatabaseBootstrap, _addr_is_loopback_safe


def test_database_config_stores_dsn() -> None:
    config = DatabaseConfig(dsn="postgresql://installer-provided@localhost/test")
    assert "localhost" in config.dsn


def test_database_config_empty_dsn_raises() -> None:
    with pytest.raises(ValueError, match="DSN"):
        DatabaseConfig(dsn="")


def test_database_bootstrap_describe_backend() -> None:
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    assert "PostgreSQL" in bootstrap.describe_backend()


def test_database_bootstrap_requires_bootstrap_before_session() -> None:
    """session() must raise RuntimeError when bootstrap() has not been called."""
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    with pytest.raises(RuntimeError, match="bootstrap"):
        bootstrap.session()


def test_database_bootstrap_requires_bootstrap_before_engine() -> None:
    """engine property must raise RuntimeError when bootstrap() has not been called."""
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    with pytest.raises(RuntimeError, match="bootstrap"):
        _ = bootstrap.engine


def test_create_engine_configures_fail_fast_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap engine must set connection/statement timeouts to avoid startup hangs."""
    captured: dict[str, object] = {}

    def fake_create_engine(dsn: str, **kwargs):
        captured["dsn"] = dsn
        captured["kwargs"] = kwargs
        return MagicMock(name="engine")

    monkeypatch.setattr("ayehear.storage.database.create_engine", fake_create_engine)

    config = DatabaseConfig(dsn="postgresql://installer-provided@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    _ = bootstrap._create_engine()

    kwargs = captured["kwargs"]
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10

    connect_args = kwargs["connect_args"]
    assert connect_args["connect_timeout"] == 5
    assert "lock_timeout=5000" in connect_args["options"]
    assert "statement_timeout=30000" in connect_args["options"]
    assert "idle_in_transaction_session_timeout=30000" in connect_args["options"]


def test_split_sql_statements_simple() -> None:
    """Verify statement splitter handles basic DDL correctly."""
    sql = "CREATE TABLE foo (id INT);\nCREATE TABLE bar (id INT);"
    stmts = DatabaseBootstrap._split_sql_statements(sql)
    assert len(stmts) == 2


def test_split_sql_statements_dollar_quote_preserved() -> None:
    """Dollar-quoted blocks (PL/pgSQL functions) must not be split at internal semicolons."""
    sql = (
        "CREATE FUNCTION f() RETURNS TRIGGER AS $$\n"
        "BEGIN\n"
        "    NEW.updated_at = NOW();\n"
        "    RETURN NEW;\n"
        "END;\n"
        "$$ LANGUAGE plpgsql;\n"
    )
    stmts = DatabaseBootstrap._split_sql_statements(sql)
    assert len(stmts) == 1
    assert "NOW()" in stmts[0]


def test_split_sql_statements_do_block_preserved() -> None:
    """DO $$ ... $$ blocks must not be fragmented by internal semicolons."""
    sql = (
        "DO $$\n"
        "DECLARE\n"
        "    t TEXT;\n"
        "BEGIN\n"
        "    EXECUTE 'CREATE TABLE IF NOT EXISTS x (id INT);';\n"
        "END;\n"
        "$$;\n"
    )
    stmts = DatabaseBootstrap._split_sql_statements(sql)
    assert len(stmts) == 1


# ---------------------------------------------------------------------------
# HEAR-027: Loopback-only address helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("addr", [
    "localhost",
    "127.0.0.1",
    "127.0.0.2",
    "127.1.2.3",
    "::1",
    "",
])
def test_addr_is_loopback_safe_accepts_loopback(addr: str) -> None:
    assert _addr_is_loopback_safe(addr) is True


@pytest.mark.parametrize("addr", [
    "*",
    "0.0.0.0",
    "192.168.1.1",
    "10.0.0.1",
    "172.16.0.1",
    "0.0.0.0/0",
])
def test_addr_is_loopback_safe_rejects_non_loopback(addr: str) -> None:
    assert _addr_is_loopback_safe(addr) is False


# ---------------------------------------------------------------------------
# HEAR-027: DatabaseBootstrap._is_loopback_address (comma-separated list)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [
    "localhost",
    "127.0.0.1",
    "::1",
    "",
    "localhost,127.0.0.1",
    "127.0.0.1, ::1",
])
def test_is_loopback_address_accepts(value: str) -> None:
    assert DatabaseBootstrap._is_loopback_address(value) is True


@pytest.mark.parametrize("value", [
    "*",
    "0.0.0.0",
    "192.168.1.100",
    "localhost,0.0.0.0",
    "127.0.0.1,*",
])
def test_is_loopback_address_rejects(value: str) -> None:
    assert DatabaseBootstrap._is_loopback_address(value) is False


# ---------------------------------------------------------------------------
# HEAR-027: _check_loopback_only with mock connections
# ---------------------------------------------------------------------------


def _make_conn(listen_addresses: str):
    """Build a minimal mock connection that returns listen_addresses for SHOW."""
    result = MagicMock()
    result.fetchone.return_value = (listen_addresses,)
    conn = MagicMock()
    conn.execute.return_value = result
    return conn


def test_check_loopback_only_passes_for_localhost() -> None:
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    conn = _make_conn("localhost")
    bootstrap._check_loopback_only(conn)  # must not raise


def test_check_loopback_only_passes_for_127() -> None:
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    conn = _make_conn("127.0.0.1")
    bootstrap._check_loopback_only(conn)  # must not raise


def test_check_loopback_only_raises_for_wildcard() -> None:
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    conn = _make_conn("*")
    with pytest.raises(RuntimeError, match="loopback"):
        bootstrap._check_loopback_only(conn)


def test_check_loopback_only_raises_for_network_ip() -> None:
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    conn = _make_conn("192.168.1.100")
    with pytest.raises(RuntimeError, match="loopback"):
        bootstrap._check_loopback_only(conn)


def test_check_loopback_only_raises_when_mixed_with_non_loopback() -> None:
    """Even if localhost is in the list, a non-loopback sibling must fail-closed."""
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    conn = _make_conn("localhost,0.0.0.0")
    with pytest.raises(RuntimeError, match="loopback"):
        bootstrap._check_loopback_only(conn)


# ---------------------------------------------------------------------------
# Migration tracking: _run_migrations must skip already-applied files
# ---------------------------------------------------------------------------

def _make_migration_engine(applied_filenames: list[str], meetings_exists: bool = True):
    """Build a minimal mock engine whose connections simulate migration tracking state."""
    from unittest.mock import patch, call
    from sqlalchemy import text as _text

    executed_sqls: list[str] = []

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def fetchone(self):
            return self._rows[0] if self._rows else None

    class _FakeConn:
        def __init__(self):
            self.executed = []

        def execute(self, stmt, params=None):
            sql = str(stmt)
            self.executed.append(sql)
            executed_sqls.append(sql)
            if "SELECT filename FROM schema_migrations" in sql:
                return _FakeResult([(fn,) for fn in applied_filenames])
            if "information_schema.tables" in sql:
                return _FakeResult([(1,)] if meetings_exists else [])
            return _FakeResult([])

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class _FakeEngine:
        def begin(self):
            return _FakeConn()

    return _FakeEngine(), executed_sqls


def test_run_migrations_skips_already_applied(tmp_path, monkeypatch) -> None:
    """_run_migrations must not re-execute a migration that is already tracked."""
    sql_file = tmp_path / "001_initial_schema.sql"
    sql_file.write_text("CREATE TABLE IF NOT EXISTS meetings (id TEXT PRIMARY KEY);")

    monkeypatch.setattr(
        "ayehear.storage.database._MIGRATIONS_DIR", tmp_path
    )

    engine, executed = _make_migration_engine(applied_filenames=["001_initial_schema.sql"])
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    bootstrap._engine = engine

    bootstrap._run_migrations()

    # The CREATE TABLE from the migration file must NOT appear in executed SQL
    assert not any("CREATE TABLE IF NOT EXISTS meetings" in s for s in executed), \
        "Already-tracked migration was re-executed"


def test_run_migrations_premarks_existing_install(tmp_path, monkeypatch) -> None:
    """On existing installs (schema present, no tracking records), migrations are pre-marked."""
    sql_file = tmp_path / "001_initial_schema.sql"
    sql_file.write_text("CREATE TABLE IF NOT EXISTS meetings (id TEXT PRIMARY KEY);")

    monkeypatch.setattr(
        "ayehear.storage.database._MIGRATIONS_DIR", tmp_path
    )

    # No migrations tracked yet, but 'meetings' table exists
    engine, executed = _make_migration_engine(applied_filenames=[], meetings_exists=True)
    config = DatabaseConfig(dsn="postgresql://placeholder@localhost/ayehear")
    bootstrap = DatabaseBootstrap(config)
    bootstrap._engine = engine

    bootstrap._run_migrations()

    # Pre-mark INSERT must have been executed
    assert any("INSERT INTO schema_migrations" in s for s in executed), \
        "Pre-mark INSERT not issued for existing install"
    # Actual DDL migration must NOT have been executed
    assert not any("CREATE TABLE IF NOT EXISTS meetings" in s for s in executed), \
        "Migration DDL was re-executed on existing install"
