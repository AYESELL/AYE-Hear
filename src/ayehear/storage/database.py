"""PostgreSQL bootstrap, connection management and schema migration runner.

ADR-0006: installer-managed local PostgreSQL; loopback-only.
ADR-0007: canonical persistence entities.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_RUNTIME_DSN_ENV = "AYEHEAR_DB_DSN"

# Fail-fast guards for startup bootstrap/migrations.
# Prevents indefinite waiting on blocked DDL/locks during app launch.
_PG_CONNECT_TIMEOUT_SECONDS = 5
_PG_LOCK_TIMEOUT_MS = 5000
_PG_STATEMENT_TIMEOUT_MS = 30000
_PG_IDLE_TX_TIMEOUT_MS = 30000

# Addresses that are unambiguously loopback-only.
_LOOPBACK_LITERALS = frozenset({"localhost", "127.0.0.1", "::1", ""})


def runtime_dsn_path(install_root: Path | None = None) -> Path:
    """Return the canonical installer-managed DSN file path (ADR-0011).

    Delegates to ``ayehear.utils.paths.dsn_file_path`` so the resolution
    strategy is centralised in one module per ADR-0011 §4.
    Development/CI may override the install root for testability.
    """
    from ayehear.utils.paths import dsn_file_path
    return dsn_file_path(install_root)


def load_runtime_dsn(install_root: Path | None = None) -> str | None:
    """Load the runtime DSN from env first, then the installer-managed file.

    Returns None when no usable DSN is available.
    """
    env_dsn = os.environ.get(_RUNTIME_DSN_ENV, "").strip()
    if env_dsn:
        return env_dsn

    dsn_file = runtime_dsn_path(install_root)
    if not dsn_file.exists():
        return None

    try:
        dsn = dsn_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("Could not read runtime DSN file %s: %s", dsn_file, exc)
        return None

    return dsn or None


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
        # Normalise legacy scheme → psycopg3 (SQLAlchemy dialect).
        # pg.dsn files written by the installer use the plain postgresql:// or
        # postgres:// scheme; SQLAlchemy needs postgresql+psycopg:// to select
        # the psycopg3 driver that is bundled in the frozen exe.
        for plain in ("postgresql://", "postgres://"):
            if dsn.startswith(plain):
                dsn = "postgresql+psycopg://" + dsn[len(plain):]
                break
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
            pool_recycle=3600,  # Recycle connections every hour to prevent stale connections
            connect_args={
                "connect_timeout": _PG_CONNECT_TIMEOUT_SECONDS,
                "options": (
                    f"-c lock_timeout={_PG_LOCK_TIMEOUT_MS} "
                    f"-c statement_timeout={_PG_STATEMENT_TIMEOUT_MS} "
                    f"-c idle_in_transaction_session_timeout={_PG_IDLE_TX_TIMEOUT_MS}"
                ),
            },
        )
        # Disable automatic schema creation — migrations own the schema
        # Add event listener for disconnect events to prevent cascading failures
        try:
            @event.listens_for(engine, "disconnect")
            def receive_disconnect(dbapi_conn, connection_record):
                """Handle premature disconnections (e.g. server restart, network failure)."""
                logger.debug("Database connection lost; will reconnect on next access.")
        except Exception as exc:
            # Skip event registration if engine doesn't support it (e.g. mocked in tests)
            logger.debug("Could not register disconnect event listener: %s", exc)
        
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
        """Apply SQL migration files in order with tracking to prevent re-runs.

        A ``schema_migrations`` table is created on first use to record which
        files have already been applied.  Migrations are only executed once;
        subsequent bootstrap calls skip already-applied files entirely, avoiding
        DDL lock contention when multiple bootstrap attempts run concurrently
        (e.g. startup + "Refresh Status").

        For existing installs where the schema was deployed before tracking was
        introduced, all pending migration files are pre-marked as applied if the
        core schema tables already exist — so no DDL is re-executed.
        """
        assert self._engine is not None
        migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            logger.warning("No migration files found in %s", _MIGRATIONS_DIR)
            return

        with self._engine.begin() as conn:
            # Ensure tracking table exists.
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "  filename   TEXT        PRIMARY KEY,"
                "  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
                ")"
            ))
            applied: set[str] = {
                row[0]
                for row in conn.execute(
                    text("SELECT filename FROM schema_migrations")
                )
            }

            # Detect existing-install scenario: schema deployed before tracking.
            # If the core 'meetings' table exists but no migrations are recorded,
            # pre-mark all files as applied without re-executing DDL.
            if not applied:
                schema_exists = conn.execute(text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'meetings'"
                )).fetchone()
                if schema_exists:
                    logger.info(
                        "Existing schema detected without migration records; "
                        "pre-marking %d migration(s) as applied.",
                        len(migration_files),
                    )
                    for mf in migration_files:
                        conn.execute(
                            text(
                                "INSERT INTO schema_migrations (filename) VALUES (:fn) "
                                "ON CONFLICT (filename) DO NOTHING"
                            ),
                            {"fn": mf.name},
                        )
                    logger.info("Schema up to date (pre-existing install).")
                    return

        applied_count = 0
        for migration_path in migration_files:
            if migration_path.name in applied:
                logger.debug(
                    "Skipping already-applied migration: %s", migration_path.name
                )
                continue

            logger.info("Applying migration: %s", migration_path.name)
            sql = migration_path.read_text(encoding="utf-8")
            statements = self._split_sql_statements(sql)
            logger.debug(
                "Migration %s: executing %d statement(s).",
                migration_path.name,
                len(statements),
            )
            with self._engine.begin() as conn:
                for stmt in statements:
                    conn.execute(text(stmt))
                conn.execute(
                    text(
                        "INSERT INTO schema_migrations (filename) VALUES (:fn) "
                        "ON CONFLICT (filename) DO NOTHING"
                    ),
                    {"fn": migration_path.name},
                )
            applied_count += 1

        if applied_count:
            logger.info("Migrations applied: %d file(s).", applied_count)
        else:
            logger.info("All migrations already applied; schema up to date.")

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
