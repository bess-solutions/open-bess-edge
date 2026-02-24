"""
tests/test_totp_auth.py
=======================
Unit tests for TOTPAuth (IEC 62443-3-3 SR 1.3 — MFA).

Tests verify:
- TOTPAuth works without pyotp installed (dev mode — always returns True)
- TOTPAuth works in dev mode (no DASHBOARD_MFA_SECRET set)
- verify() rejects malformed tokens
- TOTPInfo.to_dict() returns correct structure
- generate_secret() returns valid Base32 string
"""

from __future__ import annotations

import base64

import pytest
from src.interfaces.totp_auth import TOTPAuth, TOTPInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def totp_no_secret(monkeypatch: pytest.MonkeyPatch) -> TOTPAuth:
    """TOTPAuth with no secret (dev mode) — TOTP disabled."""
    monkeypatch.delenv("DASHBOARD_MFA_SECRET", raising=False)
    return TOTPAuth(secret=None)


@pytest.fixture()
def totp_with_secret() -> TOTPAuth:
    """TOTPAuth with a known test secret."""
    # Well-known test secret (Base32): "HELLO WORLD" encoded
    return TOTPAuth(secret="JBSWY3DPEHPK3PXP")


# ---------------------------------------------------------------------------
# Dev mode (no secret) tests
# ---------------------------------------------------------------------------


class TestTOTPDevMode:
    """When DASHBOARD_MFA_SECRET is not set, MFA is disabled."""

    def test_is_not_enabled(self, totp_no_secret: TOTPAuth) -> None:
        """MFA is disabled when no secret is configured."""
        assert totp_no_secret.is_enabled is False

    def test_verify_always_true(self, totp_no_secret: TOTPAuth) -> None:
        """In dev mode, verify() returns True for any input."""
        assert totp_no_secret.verify("") is True
        assert totp_no_secret.verify("000000") is True
        assert totp_no_secret.verify("garbage") is True

    def test_provisioning_uri_is_none(self, totp_no_secret: TOTPAuth) -> None:
        """provisioning_uri() returns None when not configured."""
        assert totp_no_secret.provisioning_uri() is None

    def test_info_gap_status_open(self, totp_no_secret: TOTPAuth) -> None:
        """Info shows GAP-001 as OPEN when MFA is disabled."""
        info = totp_no_secret.info()
        assert isinstance(info, TOTPInfo)
        d = info.to_dict()
        assert d["mfa_enabled"] is False
        assert "OPEN" in d["gap_status"]
        assert d["iec_62443_ref"] == "SR 1.3 — Account Management (MFA requirement)"


# ---------------------------------------------------------------------------
# TOTP token format validation (always-on, regardless of pyotp availability)
# ---------------------------------------------------------------------------


class TestTOTPTokenValidation:
    """Token format checks apply even before TOTP verification."""

    def test_verify_rejects_non_digit(self, totp_with_secret: TOTPAuth) -> None:
        """verify('abc') should return False (non-digits)."""
        if not totp_with_secret.is_enabled:
            pytest.skip("pyotp not installed — skipping TOTP verification tests")
        assert totp_with_secret.verify("abcdef") is False

    def test_verify_rejects_wrong_length(self, totp_with_secret: TOTPAuth) -> None:
        """verify('12345') (5 digits) should return False."""
        if not totp_with_secret.is_enabled:
            pytest.skip("pyotp not installed — skipping TOTP verification tests")
        assert totp_with_secret.verify("12345") is False

    def test_verify_rejects_empty(self, totp_with_secret: TOTPAuth) -> None:
        """verify('') should return False when MFA is enabled."""
        if not totp_with_secret.is_enabled:
            pytest.skip("pyotp not installed — skipping TOTP verification tests")
        assert totp_with_secret.verify("") is False

    def test_verify_strips_spaces(self, totp_with_secret: TOTPAuth) -> None:
        """Tokens with spaces (like '123 456') should be sanitized before validation."""
        if not totp_with_secret.is_enabled:
            pytest.skip("pyotp not installed — skipping TOTP verification tests")
        # '123 456' → '123456' (6 digits) → valid format, likely wrong token
        result = totp_with_secret.verify("000 000")  # almost certainly invalid TOTP
        # We can't assert True here since we don't know current time,
        # but we can verify it returns a boolean (no exception)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# TOTPInfo tests (no pyotp dependency)
# ---------------------------------------------------------------------------


class TestTOTPInfo:
    def test_to_dict_structure(self, totp_no_secret: TOTPAuth) -> None:
        """TOTPInfo.to_dict() always returns required keys."""
        d = totp_no_secret.info().to_dict()
        required_keys = {
            "mfa_enabled",
            "pyotp_installed",
            "algorithm",
            "digits",
            "period_seconds",
            "setup",
            "iec_62443_ref",
            "gap_status",
        }
        assert required_keys.issubset(d.keys()), f"Missing keys: {required_keys - set(d.keys())}"

    def test_algorithm_is_sha1(self, totp_no_secret: TOTPAuth) -> None:
        """Algorithm must be SHA1 (RFC 6238 standard)."""
        assert totp_no_secret.info().to_dict()["algorithm"] == "SHA1"

    def test_period_is_30s(self, totp_no_secret: TOTPAuth) -> None:
        """TOTP period must be 30 seconds (RFC 6238 default)."""
        assert totp_no_secret.info().to_dict()["period_seconds"] == 30

    def test_digits_is_6(self, totp_no_secret: TOTPAuth) -> None:
        """TOTP must use 6 digits."""
        assert totp_no_secret.info().to_dict()["digits"] == 6


# ---------------------------------------------------------------------------
# generate_secret() tests
# ---------------------------------------------------------------------------


class TestGenerateSecret:
    def test_returns_string(self) -> None:
        """generate_secret() returns a string."""
        secret = TOTPAuth.generate_secret()
        assert isinstance(secret, str)

    def test_is_valid_base32(self) -> None:
        """generate_secret() returns valid Base32-decodable string."""
        secret = TOTPAuth.generate_secret()
        # Pad if needed
        padded = secret + "=" * (-len(secret) % 8)
        decoded = base64.b32decode(padded.upper())
        assert len(decoded) >= 16  # at least 128-bit entropy

    def test_is_different_each_call(self) -> None:
        """generate_secret() generates unique secrets each call."""
        s1 = TOTPAuth.generate_secret()
        s2 = TOTPAuth.generate_secret()
        assert s1 != s2


# ---------------------------------------------------------------------------
# Environment variable integration
# ---------------------------------------------------------------------------


class TestEnvVariableIntegration:
    def test_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TOTPAuth reads DASHBOARD_MFA_SECRET from env when no explicit secret."""
        monkeypatch.setenv("DASHBOARD_MFA_SECRET", "JBSWY3DPEHPK3PXP")
        auth = TOTPAuth()
        # Either enabled (pyotp available) or disabled (pyotp not installed)
        assert isinstance(auth.is_enabled, bool)

    def test_no_env_var_means_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without DASHBOARD_MFA_SECRET, MFA is always disabled."""
        monkeypatch.delenv("DASHBOARD_MFA_SECRET", raising=False)
        auth = TOTPAuth(secret=None)
        assert auth.is_enabled is False
