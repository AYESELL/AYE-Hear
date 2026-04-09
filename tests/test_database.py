"""Tests for DatabaseBootstrap (HEAR-008, HEAR-026, HEAR-027) — without a live PostgreSQL connection."""
from __future__ import annotations

import pytest

from ayehear.storage.database import DatabaseConfig, DatabaseBootstrap


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
