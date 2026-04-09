"""PostgreSQL bootstrap, connection management and schema migration runner.

ADR-0006: installer-managed local PostgreSQL; loopback-only.
ADR-0007: canonical persistence entities.
"""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ayehear.storage.orm import Base

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Addresses that are unambiguously loopback-only.
_LOOPBACK_LITERALS = frozenset({"localhost", "127.0.0.1", "::1", ""})


def _addr_is_loopback_safe(addr: str) -> bool:
    """Return True if *addr* resolves exclusively to a loopback interface.

    Accepts lower-cased, stripped address strings.
    """
    if addr in _LOOPBACK_LITERALS:
        return True
    # The full 127.0.0.0/8 range is loopback on Linux/macOS/Windows.
    if addr.startswith("127."):
        return True
    return False


class DatabaseConfig:
    """Minimal DSN configuration for the local PostgreSQL connection."""

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgreSQL DSN must not be empty.")
        self.dsn = dsn


class DatabaseBootstrap:
    """Handles engine creation, connection verification and schema migrations.

    Usage::

        config = DatabaseConfig(dsn="<installer-provided-or-env-loaded-dsn>")
        db = DatabaseBootstrap(config)
        db.bootstrap()
        session = db.session()
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._engine: Engine | None = None
        self._SessionFactory: sessionmaker | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bootstrap(self) -> None:
        """Create engine, verify connectivity and run pending migrations."""
        self._engine = self._create_engine()
        self._verify_connection()
        self._run_migrations()
        self._SessionFactory = sessionmaker(bind=self._engine, expire_on_commit=False)
        logger.info("Database bootstrap completed.")

    def session(self) -> Session:
        """Return a new SQLAlchemy Session. Caller owns the lifecycle."""
        if self._SessionFactory is None:
            raise RuntimeError("Call bootstrap() before requesting sessions.")
        return self._SessionFactory()

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            raise RuntimeError("Call bootstrap() first.")
        return self._engine

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_engine(self) -> Engine:
        engine = create_engine(
            self._config.dsn,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        # Disable automatic schema creation — migrations own the schema
        return engine

    def _verify_connection(self) -> None:
        """Raise RuntimeError if the database cannot be reached or is not loopback-only."""
        assert self._engine is not None
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                self._check_loopback_only(conn)
            logger.debug("PostgreSQL connection verified (loopback-only check passed).")
        except RuntimeError:
            raise  # loopback violations propagate directly
        except Exception as exc:
            raise RuntimeError(
                f"Cannot connect to PostgreSQL: {exc}\n"
                "Ensure local PostgreSQL (ADR-0006) is running and the DSN is correct."
            ) from exc

    def _check_loopback_only(self, conn) -> None:
        """Verify that PostgreSQL binds to loopback interfaces only (ADR-0006).

        AYE Hear requires the local PostgreSQL instance to be inaccessible from
        remote network addresses.  Reads ``listen_addresses`` from the running
        server and raises RuntimeError when any non-loopback address is present.
        """
        result = conn.execute(text("SHOW listen_addresses"))
        row = result.fetchone()
        listen_addresses: str = (row[0] if row else "") or ""
        if not self._is_loopback_address(listen_addresses):
            raise RuntimeError(
                f"PostgreSQL listen_addresses={listen_addresses!r} exposes the database "
                "beyond loopback.  AYE Hear requires PostgreSQL to bind to localhost only "
                "(ADR-0006).  Review your PostgreSQL configuration and restart the service."
            )
        logger.debug(
            "PostgreSQL loopback-only check passed: listen_addresses=%r", listen_addresses
        )

    @staticmethod
    def _is_loopback_address(listen_addresses: str) -> bool:
        """Return True iff every address in *listen_addresses* is loopback-safe.

        Loopback-safe values: ``localhost``, ``127.x.x.x``, ``::1``, empty string.
        Non-loopback examples that will fail: ``*``, ``0.0.0.0``, ``192.168.x.y``.

        PostgreSQL allows a comma-separated list; all parts are checked.
        """
        parts = [p.strip().lower() for p in listen_addresses.split(",")]
        # If every part is empty the server reports no explicit listener; treat as safe.
        if not any(parts):
            return True
        return all(_addr_is_loopback_safe(addr) for addr in parts)

    def _run_migrations(self) -> None:
        """Apply SQL migration files in order. Idempotent via IF NOT EXISTS.

        Each file is split into individual statements before execution so that
        multi-statement migration scripts (DDL + triggers + DO blocks) work
        correctly with PostgreSQL / psycopg via SQLAlchemy, which does not
        support passing multiple statements to a single text() call.
        """
        assert self._engine is not None
        migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            logger.warning("No migration files found in %s", _MIGRATIONS_DIR)
            return

        with self._engine.begin() as conn:
            for migration_path in migration_files:
                logger.info("Applying migration: %s", migration_path.name)
                sql = migration_path.read_text(encoding="utf-8")
                statements = self._split_sql_statements(sql)
                logger.debug(
                    "Migration %s: executing %d statement(s).",
                    migration_path.name,
                    len(statements),
                )
                for stmt in statements:
                    conn.execute(text(stmt))

        logger.info("Migrations applied: %d file(s).", len(migration_files))

    @staticmethod
    def _split_sql_statements(sql: str) -> list[str]:
        """Split a multi-statement SQL script into individual executable statements.

        Handles PostgreSQL dollar-quoted blocks (``$$...$$``) correctly so that
        semicolons inside PL/pgSQL function bodies and DO blocks are NOT treated
        as statement boundaries.  Comments-only lines and empty fragments are
        discarded.
        """
        statements: list[str] = []
        current_lines: list[str] = []
        in_dollar_quote = False

        for line in sql.splitlines(keepends=True):
            stripped = line.strip()

            # Count $$ occurrences on this line; an odd count means we enter
            # or exit a dollar-quoted block.
            dollar_pairs = stripped.count("$$")
            if dollar_pairs % 2 != 0:
                in_dollar_quote = not in_dollar_quote

            current_lines.append(line)

            # A statement boundary is a line ending with ";" that is outside
            # any dollar-quoted block and not a pure comment line.
            if (
                not in_dollar_quote
                and stripped.endswith(";")
                and not stripped.startswith("--")
            ):
                stmt = "".join(current_lines).strip()
                if stmt:
                    statements.append(stmt)
                current_lines = []

        # Flush any trailing content that has no trailing semicolon.
        remaining = "".join(current_lines).strip()
        if remaining and not remaining.startswith("--"):
            statements.append(remaining)

        return statements

    def describe_backend(self) -> str:
        return "PostgreSQL (ADR-0006)"
