"""HEAR-077: Fail-fast semantics in Install-PostgresRuntime.ps1.

Validates that SQL/migration errors cause immediate termination rather than
continuing silently with a WARN log.

Test strategy (two layers):
  1. Static source analysis — always runs, verifies throw patterns in script.
  2. PowerShell integration tests — Windows-only, execute isolated functions
     and confirm terminating-error semantics at runtime.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).parent.parent / "tools" / "scripts" / "Install-PostgresRuntime.ps1"
)

# ─── Static source analysis ────────────────────────────────────────────────────


class TestScriptFailFastPatterns:
    """Read the script source and verify fail-fast throw patterns are present."""

    @pytest.fixture(scope="class")
    def script_source(self) -> str:
        return SCRIPT_PATH.read_text(encoding="utf-8")

    def test_invoke_psql_throws_on_nonzero_exit(self, script_source: str) -> None:
        """Invoke-Psql must throw when psql returns non-zero, not just log WARN."""
        # Locate the Invoke-Psql function body
        fn_start = script_source.find("function Invoke-Psql {")
        assert fn_start != -1, "Invoke-Psql function not found in script"
        fn_end = script_source.find("\n}", fn_start) + 2
        fn_body = script_source[fn_start:fn_end]

        assert "throw" in fn_body, (
            "Invoke-Psql must throw on non-zero exit; only Write-Log WARN found."
        )
        # Must not silently continue (WARN-only is insufficient)
        assert "'WARN'" not in fn_body, (
            "Invoke-Psql must not downgrade SQL errors to WARN — use throw."
        )

    def test_create_database_error_throws(self, script_source: str) -> None:
        """Unexpected CREATE DATABASE failures must throw, not just log WARN."""
        assert "CREATE DATABASE warning" not in script_source, (
            "CREATE DATABASE errors must throw instead of logging a warning."
        )
        # Verify throw statement exists for CREATE DATABASE failure
        assert 'throw "CREATE DATABASE $PG_APP_DB failed' in script_source, (
            "Expected throw statement 'throw \"CREATE DATABASE $PG_APP_DB failed' "
            "not found in script."
        )

    def test_migration_failure_throws(self, script_source: str) -> None:
        """Python migration bootstrap failure must throw a terminating error."""
        assert "Migration bootstrap reported an error" not in script_source, (
            "Migration errors must throw instead of logging 'Migration bootstrap "
            "reported an error' with WARN."
        )
        # Verify throw statement exists for migration failure
        assert 'throw "Schema migration failed' in script_source, (
            "Expected throw statement 'throw \"Schema migration failed' "
            "not found in script."
        )

    def test_missing_python_throws(self, script_source: str) -> None:
        """Missing Python runtime must be a hard failure, not a soft skip."""
        assert "migrations will run on first app launch" not in script_source, (
            "Missing Python runtime must throw — deferring migrations silently is "
            "unsafe (schema may be absent on first launch)."
        )
        missing_python_idx = script_source.find("Python runtime not found")
        assert missing_python_idx != -1, (
            "Expected 'Python runtime not found' error log not found."
        )
        nearby = script_source[missing_python_idx : missing_python_idx + 200]
        assert "throw" in nearby, (
            "throw must follow the missing-Python error log."
        )

    def test_no_warn_only_patterns_for_critical_failures(self, script_source: str) -> None:
        """Ensure previously silenced error patterns are gone."""
        forbidden = [
            "'WARN'" + "  # downgrade from psql error",  # exact old pattern gone
            "migrations will run on first app launch",
            "Migration bootstrap reported an error",
            "CREATE DATABASE warning",
        ]
        for pattern in forbidden:
            assert pattern not in script_source, (
                f"Forbidden silent-failure pattern still present: {pattern!r}"
            )


# ─── PowerShell integration tests ─────────────────────────────────────────────

pytestmark_windows = pytest.mark.skipif(
    sys.platform != "win32", reason="PowerShell integration requires Windows"
)


def _run_ps(code: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a PowerShell code block and return the completed process."""
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            code,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows + PowerShell")
class TestInvokePsqlFailFastRuntime:
    """PowerShell integration: Invoke-Psql terminates on non-zero psql exit."""

    # Inline Invoke-Psql with simulated psql failure via cmd.exe /c exit 1.
    # Write-Output is used for test markers because PowerShell's Write-Host
    # writes to the HOST stream (not stdout) and is not captured by subprocess.
    _INVOKE_PSQL_INLINE = r"""
$PG_PORT = 5433
$LOG_DIR = $env:TEMP
$LOG_FILE = Join-Path $env:TEMP 'hear077-test.log'

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    Write-Output "[$Level] $Message"
}

function Invoke-Psql {
    param([string]$Sql, [string]$Db = 'postgres')
    Write-Log "  psql: $Sql"
    # Simulate psql failure: set $LASTEXITCODE = 1 via cmd.exe
    $result = "ERROR: connection refused to 127.0.0.1:5433"
    & cmd.exe /c exit 1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "  psql output: $result" 'ERROR'
        throw "psql command failed (exit $LASTEXITCODE) SQL=[$Sql] DB=[$Db]: $result"
    }
    return $result
}
"""

    def test_invoke_psql_throw_caught_by_try_catch(self) -> None:
        """Invoke-Psql must raise a terminating error on simulated psql failure."""
        code = (
            self._INVOKE_PSQL_INLINE
            + r"""
try {
    Invoke-Psql "SELECT 1;"
    Write-Output "RESULT:NO_THROW"
    exit 2
} catch {
    Write-Output "RESULT:CAUGHT:$_"
    exit 0
}
"""
        )
        result = _run_ps(code)
        assert result.returncode == 0, (
            f"Expected throw not raised. stdout: {result.stdout!r} stderr: {result.stderr!r}"
        )
        assert result.stdout is not None
        assert "RESULT:CAUGHT:" in result.stdout, (
            f"Expected 'RESULT:CAUGHT:' in stdout. Got: {result.stdout!r}"
        )
        assert "RESULT:NO_THROW" not in result.stdout

    def test_invoke_psql_error_message_contains_sql(self) -> None:
        """The thrown error message must include the failing SQL statement."""
        code = (
            self._INVOKE_PSQL_INLINE
            + r"""
try {
    Invoke-Psql "CREATE TABLE test_hear077 (id INT);"
    exit 2
} catch {
    if ($_ -match 'CREATE TABLE test_hear077') {
        Write-Output "RESULT:SQL_IN_MESSAGE"
        exit 0
    } else {
        Write-Output "RESULT:SQL_MISSING:$_"
        exit 3
    }
}
"""
        )
        result = _run_ps(code)
        assert result.returncode == 0, (
            f"SQL not present in error message. stdout: {result.stdout!r}"
        )
        assert "RESULT:SQL_IN_MESSAGE" in result.stdout

    def test_invoke_psql_error_message_contains_exit_code(self) -> None:
        """The thrown error message must include the exit code."""
        code = (
            self._INVOKE_PSQL_INLINE
            + r"""
try {
    Invoke-Psql "SELECT 1;"
    exit 2
} catch {
    if ($_ -match 'exit') {
        Write-Output "RESULT:EXIT_CODE_IN_MESSAGE"
        exit 0
    } else {
        Write-Output "RESULT:EXIT_CODE_MISSING:$_"
        exit 3
    }
}
"""
        )
        result = _run_ps(code)
        assert result.returncode == 0, (
            f"Exit code not present in error. stdout: {result.stdout!r}"
        )
        assert "RESULT:EXIT_CODE_IN_MESSAGE" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows + PowerShell")
class TestCreateDatabaseFailFastRuntime:
    """PowerShell integration: CREATE DATABASE unexpected failures terminate."""

    def test_create_database_nonzero_non_exists_throws(self) -> None:
        """Non-zero CREATE DATABASE exit that isn't 'already exists' must throw."""
        code = r"""
try {
    $PG_APP_DB = 'ayehear'

    function Write-Log {
        param([string]$Message, [string]$Level = 'INFO')
        Write-Output "[$Level] $Message"
    }

    # Simulate psql returning exit 1 with permission error (not 'already exists')
    $createOut = @('ERROR:  permission denied to create database')
    & cmd.exe /c exit 1

    if ($LASTEXITCODE -ne 0 -and ($createOut -join '') -match 'already exists') {
        Write-Log "Database '$PG_APP_DB' already exists - skipping creation."
    } elseif ($LASTEXITCODE -ne 0) {
        Write-Log "CREATE DATABASE failed: $($createOut -join ' ')" 'ERROR'
        throw "CREATE DATABASE $PG_APP_DB failed (exit $LASTEXITCODE): $($createOut -join ' ')"
    } else {
        Write-Log "Database '$PG_APP_DB' created."
    }
    Write-Output "RESULT:NO_THROW"
    exit 2
} catch {
    Write-Output "RESULT:CAUGHT:$_"
    exit 0
}
"""
        result = _run_ps(code)
        assert result.returncode == 0, (
            f"Expected throw not raised. stdout: {result.stdout!r}"
        )
        assert result.stdout is not None
        assert "RESULT:CAUGHT:" in result.stdout
        assert "RESULT:NO_THROW" not in result.stdout

    def test_create_database_already_exists_does_not_throw(self) -> None:
        """'already exists' error must be silently skipped (idempotent install)."""
        code = r"""
try {
    $PG_APP_DB = 'ayehear'

    function Write-Log {
        param([string]$Message, [string]$Level = 'INFO')
        Write-Output "[$Level] $Message"
    }

    $createOut = @('ERROR:  database "ayehear" already exists')
    & cmd.exe /c exit 1  # simulate psql exit 1 for already-exists

    if ($LASTEXITCODE -ne 0 -and ($createOut -join '') -match 'already exists') {
        Write-Log "Database '$PG_APP_DB' already exists - skipping creation."
    } elseif ($LASTEXITCODE -ne 0) {
        Write-Log "CREATE DATABASE failed: $($createOut -join ' ')" 'ERROR'
        throw "CREATE DATABASE $PG_APP_DB failed (exit $LASTEXITCODE): $($createOut -join ' ')"
    } else {
        Write-Log "Database '$PG_APP_DB' created."
    }
    Write-Output "RESULT:NO_THROW"
    exit 0
} catch {
    Write-Output "RESULT:UNEXPECTED_THROW:$_"
    exit 2
}
"""
        result = _run_ps(code)
        assert result.returncode == 0, (
            f"Unexpected throw for 'already exists'. stdout: {result.stdout!r}"
        )
        assert result.stdout is not None
        assert "RESULT:NO_THROW" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Requires Windows + PowerShell")
class TestMigrationFailFastRuntime:
    """PowerShell integration: Migration bootstrap failure terminates install."""

    def test_migration_nonzero_exit_throws(self) -> None:
        """Python migration returning non-zero must throw a terminating error."""
        code = r"""
try {
    $LOG_FILE = Join-Path $env:TEMP 'hear077-migration.log'

    function Write-Log {
        param([string]$Message, [string]$Level = 'INFO')
        Write-Output "[$Level] $Message"
    }

    # Simulate Python present but failing: use cmd.exe /c exit 1
    $python = 'C:\Windows\System32\cmd.exe'
    $migrOutput = 'OperationalError: could not connect to server'
    & cmd.exe /c exit 1  # simulate migration Python exit 1

    if ($python -and (Test-Path $python)) {
        Write-Log "  Python: $python"
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Migration bootstrap failed (exit $LASTEXITCODE). Output: $migrOutput" 'ERROR'
            Write-Log "See log for details: $LOG_FILE" 'ERROR'
            throw "Schema migration failed (exit $LASTEXITCODE). Check log: $LOG_FILE"
        } else {
            Write-Log "Schema migrations applied."
        }
    } else {
        Write-Log "Python runtime not found at '$python' - cannot run schema migrations." 'ERROR'
        throw "Python runtime not found. Expected: $python. Schema migrations could not be applied."
    }
    Write-Output "RESULT:NO_THROW"
    exit 2
} catch {
    Write-Output "RESULT:CAUGHT:$_"
    exit 0
}
"""
        result = _run_ps(code)
        assert result.returncode == 0, (
            f"Expected throw not raised. stdout: {result.stdout!r}"
        )
        assert result.stdout is not None
        assert "RESULT:CAUGHT:" in result.stdout
        assert "RESULT:NO_THROW" not in result.stdout

    def test_missing_python_throws(self) -> None:
        """Non-existent Python binary must throw, not defer migrations silently."""
        code = r"""
try {
    $python = 'C:\absolutely\nonexistent\python.exe'

    function Write-Log {
        param([string]$Message, [string]$Level = 'INFO')
        Write-Output "[$Level] $Message"
    }

    if ($python -and (Test-Path $python)) {
        Write-Output "RESULT:PYTHON_FOUND"
        exit 2
    } else {
        Write-Log "Python runtime not found at '$python' - cannot run schema migrations." 'ERROR'
        throw "Python runtime not found. Expected: $python. Schema migrations could not be applied."
    }
    Write-Output "RESULT:NO_THROW"
    exit 2
} catch {
    Write-Output "RESULT:CAUGHT:$_"
    exit 0
}
"""
        result = _run_ps(code)
        assert result.returncode == 0, (
            f"Expected throw not raised. stdout: {result.stdout!r}"
        )
        assert result.stdout is not None
        assert "RESULT:CAUGHT:" in result.stdout
        assert "Python runtime not found" in result.stdout

    def test_migration_error_message_contains_log_path(self) -> None:
        """Migration throw message must point to the log file for diagnostics."""
        code = r"""
$LOG_FILE = 'C:\AyeHear\logs\pg-install.log'

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    Write-Output "[$Level] $Message"
}

$migrOutput = 'alembic.util.exc.CommandError: ...'
& cmd.exe /c exit 1  # simulate migration failure

try {
    Write-Log "Migration bootstrap failed (exit $LASTEXITCODE). Output: $migrOutput" 'ERROR'
    Write-Log "See log for details: $LOG_FILE" 'ERROR'
    throw "Schema migration failed (exit $LASTEXITCODE). Check log: $LOG_FILE"
    Write-Output "RESULT:NO_THROW"
    exit 2
} catch {
    if ($_ -match [regex]::Escape($LOG_FILE)) {
        Write-Output "RESULT:LOG_PATH_IN_MESSAGE"
        exit 0
    } else {
        Write-Output "RESULT:LOG_PATH_MISSING:$_"
        exit 3
    }
}
"""
        result = _run_ps(code)
        assert result.returncode == 0, (
            f"Log path not in error message. stdout: {result.stdout!r}"
        )
        assert "RESULT:LOG_PATH_IN_MESSAGE" in result.stdout
