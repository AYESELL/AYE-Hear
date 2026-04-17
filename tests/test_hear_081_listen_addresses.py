"""HEAR-081: Harden listen_addresses parsing in PostgreSQL health check.

Validates that the multi-value listen_addresses parsing logic in
Start-AyeHearRuntime.ps1 (Check 4) correctly handles:

  - Single safe values    (localhost, 127.x.x.x, ::1, empty)
  - Comma-separated safe  (localhost,127.0.0.1 etc.)
  - Quoted token values   ('localhost', 'localhost','127.0.0.1')
  - Whitespace around     ( localhost , 127.0.0.1 )
  - Unsafe values         (*, 0.0.0.0, external IPs)
  - Mixed safe/unsafe     (localhost,0.0.0.0 → FAIL)

Test strategy (two layers):
  1. Static source analysis — always runs; verifies the new splitting pattern
     is present in the script source.
  2. Python-equivalent logic tests — port the PowerShell token-splitting and
     loopback validation logic to Python so tests are cross-platform and fast.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).parent.parent
    / "tools"
    / "scripts"
    / "Start-AyeHearRuntime.ps1"
)


# ─── Python mirror of the PowerShell parsing logic ───────────────────────────

def _parse_listen_tokens(raw: str) -> list[str]:
    """
    Mirror the PowerShell token-splitting logic added by HEAR-081.

    Steps applied per token:
      1. Split on comma
      2. Strip outer whitespace
      3. Strip surrounding single or double quotes
      4. Lowercase
      5. Discard empty tokens
    """
    tokens: list[str] = []
    for part in raw.split(","):
        token = part.strip().strip("'").strip('"').lower()
        if token:
            tokens.append(token)
    return tokens


def _is_loopback_safe(raw: str) -> bool:
    """
    Return True when all parsed tokens are loopback-only addresses.

    Safe values: localhost, ::1, 127.x.x.x
    An empty token list (empty listen_addresses setting) is also safe.
    """
    tokens = _parse_listen_tokens(raw)
    if not tokens:
        return True
    for token in tokens:
        if token not in ("localhost", "::1") and not token.startswith("127."):
            return False
    return True


# ─── Layer 1: Static source analysis ─────────────────────────────────────────


class TestStaticSourceAnalysis:
    """Verify that Start-AyeHearRuntime.ps1 contains the HEAR-081 hardened logic."""

    @pytest.fixture(scope="class")
    def source(self) -> str:
        return SCRIPT_PATH.read_text(encoding="utf-8")

    def test_script_exists(self, source: str) -> None:
        """Health check script must be present."""
        assert SCRIPT_PATH.is_file(), f"Script missing: {SCRIPT_PATH}"

    def test_splits_on_comma(self, source: str) -> None:
        """Parser must split the raw value on commas to handle multi-value configs."""
        assert "-split ','" in source, (
            "listen_addresses parsing must split on ',' to handle multi-value "
            "configurations such as 'localhost,127.0.0.1'."
        )

    def test_strips_quotes_per_token(self, source: str) -> None:
        """Each token must have surrounding quotes stripped."""
        assert "Trim(\"'\")" in source or "Trim('''')" in source, (
            "listen_addresses parsing must strip quotes from each token to handle "
            "PostgreSQL quoted return values such as \"'localhost'\"."
        )

    def test_uses_nonloopback_filter(self, source: str) -> None:
        """Non-loopback detection must use a per-token filter, not whole-string match."""
        assert "$nonLoopback" in source or "nonLoopback" in source, (
            "listen_addresses parsing must identify non-loopback tokens individually "
            "rather than comparing the whole raw string."
        )

    def test_empty_token_list_is_safe(self, source: str) -> None:
        """An empty address list (no tokens after splitting) must evaluate as safe."""
        assert "addrTokens.Count -eq 0" in source, (
            "When addrTokens is empty, $loopbackSafe must be set to $true."
        )

    def test_loopback_safe_variable_set(self, source: str) -> None:
        """$loopbackSafe variable must be set from the new logic."""
        assert "$loopbackSafe = ($addrTokens.Count -eq 0)" in source, (
            "$loopbackSafe must combine empty-token-list check with per-token "
            "non-loopback filter."
        )

    def test_write_check_called_with_loopback_safe(self, source: str) -> None:
        """Write-Check must be called with the $loopbackSafe result."""
        assert (
            "Write-Check 'listen_addresses loopback-only (ADR-0006)' $loopbackSafe"
            in source
        ), "Write-Check must receive $loopbackSafe as the pass/fail argument."


# ─── Layer 2: Python-equivalent parsing logic tests ──────────────────────────


class TestSingleValueSafe:
    """Single safe address values must be accepted."""

    def test_empty_string_is_safe(self) -> None:
        assert _is_loopback_safe("") is True

    def test_localhost_is_safe(self) -> None:
        assert _is_loopback_safe("localhost") is True

    def test_ipv4_loopback_is_safe(self) -> None:
        assert _is_loopback_safe("127.0.0.1") is True

    def test_ipv4_loopback_range_is_safe(self) -> None:
        assert _is_loopback_safe("127.1.2.3") is True

    def test_ipv6_loopback_is_safe(self) -> None:
        assert _is_loopback_safe("::1") is True


class TestQuotedValues:
    """PostgreSQL may return single-quoted values; quotes must be stripped."""

    def test_quoted_localhost_is_safe(self) -> None:
        assert _is_loopback_safe("'localhost'") is True

    def test_quoted_127_is_safe(self) -> None:
        assert _is_loopback_safe("'127.0.0.1'") is True

    def test_double_quoted_localhost_is_safe(self) -> None:
        assert _is_loopback_safe('"localhost"') is True


class TestMultiValueSafe:
    """Comma-separated values that are all loopback must be accepted."""

    def test_localhost_comma_127_is_safe(self) -> None:
        assert _is_loopback_safe("localhost,127.0.0.1") is True

    def test_127_comma_ipv6_is_safe(self) -> None:
        assert _is_loopback_safe("127.0.0.1,::1") is True

    def test_three_safe_tokens_are_safe(self) -> None:
        assert _is_loopback_safe("localhost,127.0.0.1,::1") is True

    def test_whitespace_around_tokens_is_safe(self) -> None:
        assert _is_loopback_safe(" localhost , 127.0.0.1 ") is True

    def test_quoted_comma_separated_safe_tokens(self) -> None:
        assert _is_loopback_safe("'localhost','127.0.0.1'") is True


class TestUnsafeValues:
    """Non-loopback or wildcard addresses must be rejected."""

    def test_wildcard_star_is_unsafe(self) -> None:
        assert _is_loopback_safe("*") is False

    def test_zero_zero_is_unsafe(self) -> None:
        assert _is_loopback_safe("0.0.0.0") is False

    def test_external_ip_is_unsafe(self) -> None:
        assert _is_loopback_safe("192.168.1.1") is False

    def test_all_addresses_keyword_is_unsafe(self) -> None:
        # PostgreSQL also accepts 'all' as a special value — must be rejected
        assert _is_loopback_safe("all") is False

    def test_non_loopback_ipv6_is_unsafe(self) -> None:
        assert _is_loopback_safe("::") is False

    def test_routable_ip_is_unsafe(self) -> None:
        assert _is_loopback_safe("10.0.0.1") is False


class TestMixedValues:
    """Any single unsafe token in a comma-separated list must cause rejection."""

    def test_safe_plus_wildcard_is_unsafe(self) -> None:
        assert _is_loopback_safe("localhost,*") is False

    def test_safe_plus_external_is_unsafe(self) -> None:
        assert _is_loopback_safe("localhost,0.0.0.0") is False

    def test_loopback_plus_routable_is_unsafe(self) -> None:
        assert _is_loopback_safe("127.0.0.1,192.168.1.100") is False

    def test_all_safe_except_last_is_unsafe(self) -> None:
        assert _is_loopback_safe("localhost,127.0.0.1,::1,10.0.0.1") is False

    def test_quoted_safe_plus_unquoted_unsafe(self) -> None:
        assert _is_loopback_safe("'localhost',0.0.0.0") is False
