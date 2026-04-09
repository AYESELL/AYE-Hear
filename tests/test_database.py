"""Tests for DatabaseBootstrap (HEAR-008, HEAR-026, HEAR-027) — without a live PostgreSQL connection."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
    row = SimpleNamespace(**{"0": listen_addresses, "__getitem__": lambda s, i: listen_addresses})
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
