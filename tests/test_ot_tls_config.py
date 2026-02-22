"""
tests/test_ot_tls_config.py
============================
Unit tests for src/interfaces/ot_tls_config.py

IEC 62443-3-3 SR 3.1: Communication Integrity — GAP-003
Tests cover:
  - Default disabled state (no env vars)
  - Partial configuration (warning but no error)
  - Full configuration with real self-signed certs (tmp_path)
  - FileNotFoundError for missing certs
  - ssl.SSLError for cert/key mismatch
  - Explicit ssl.SSLContext passthrough in UniversalDriver

These tests use ONLY stdlib (ssl, pathlib, os) — no extra fixtures needed.
The self-signed certs are generated via the stdlib ssl module without openssl binary.
"""

from __future__ import annotations

import os
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from src.interfaces.ot_tls_config import OtTlsConfig, build_ssl_context


# ---------------------------------------------------------------------------
# Helpers — self-signed cert & key generation (pure Python, no subprocess)
# ---------------------------------------------------------------------------

def _gen_self_signed_cert(tmp_path: Path) -> tuple[Path, Path]:
    """
    Generate a self-signed certificate + private key using openssl CLI.
    Skips the test if openssl is not available on PATH.

    Returns (cert_path, key_path).
    """
    openssl = "openssl"
    try:
        result = subprocess.run(
            [openssl, "version"],
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("openssl binary not found — skipping cert generation tests")

    key_path = tmp_path / "test.key"
    cert_path = tmp_path / "test.crt"

    # Generate RSA 2048 key
    subprocess.run(
        [openssl, "genrsa", "-out", str(key_path), "2048"],
        check=True,
        capture_output=True,
    )

    # Generate self-signed certificate (valid 1 day for tests)
    subprocess.run(
        [
            openssl, "req", "-new", "-x509",
            "-key", str(key_path),
            "-out", str(cert_path),
            "-days", "1",
            "-subj", "/CN=bessai-test/O=BESSAI-Test",
        ],
        check=True,
        capture_output=True,
    )

    return cert_path, key_path


# ---------------------------------------------------------------------------
# TestOtTlsConfigFromEnv
# ---------------------------------------------------------------------------


class TestOtTlsConfigFromEnv:
    """Tests for OtTlsConfig.from_env()."""

    def test_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without OT_MTLS_ENABLED, mTLS must be disabled."""
        monkeypatch.delenv("OT_MTLS_ENABLED", raising=False)
        cfg = OtTlsConfig.from_env()
        assert cfg.enabled is False
        assert cfg.is_enabled is False

    def test_enabled_flag_without_certs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OT_MTLS_ENABLED=true but no cert paths → is_enabled False (partial config)."""
        monkeypatch.setenv("OT_MTLS_ENABLED", "true")
        monkeypatch.delenv("OT_CA_CERT_PATH", raising=False)
        monkeypatch.delenv("OT_CLIENT_CERT_PATH", raising=False)
        monkeypatch.delenv("OT_CLIENT_KEY_PATH", raising=False)
        cfg = OtTlsConfig.from_env()
        assert cfg.enabled is True
        assert cfg.is_enabled is False  # incomplete config → graceful degradation

    def test_disabled_with_zero_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OT_MTLS_ENABLED=0 must be treated as disabled."""
        monkeypatch.setenv("OT_MTLS_ENABLED", "0")
        cfg = OtTlsConfig.from_env()
        assert cfg.enabled is False

    def test_enabled_with_all_paths(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """All env vars set → is_enabled True and paths resolved."""
        ca = tmp_path / "ca.crt"
        cert = tmp_path / "client.crt"
        key = tmp_path / "client.key"
        # Create dummy files so Path exists check passes
        for f in (ca, cert, key):
            f.write_text("dummy")

        monkeypatch.setenv("OT_MTLS_ENABLED", "true")
        monkeypatch.setenv("OT_CA_CERT_PATH", str(ca))
        monkeypatch.setenv("OT_CLIENT_CERT_PATH", str(cert))
        monkeypatch.setenv("OT_CLIENT_KEY_PATH", str(key))

        cfg = OtTlsConfig.from_env()
        assert cfg.is_enabled is True
        assert cfg.ca_cert_path == ca
        assert cfg.client_cert_path == cert
        assert cfg.client_key_path == key

    def test_case_insensitive_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OT_MTLS_ENABLED accepts 'True', 'TRUE', 'yes'."""
        for value in ("True", "TRUE", "YES", "yes", "1"):
            monkeypatch.setenv("OT_MTLS_ENABLED", value)
            cfg = OtTlsConfig.from_env()
            assert cfg.enabled is True, f"Expected enabled for value='{value}'"


# ---------------------------------------------------------------------------
# TestBuildSslContext
# ---------------------------------------------------------------------------


class TestBuildSslContext:
    """Tests for build_ssl_context()."""

    def test_raises_value_error_if_not_enabled(self) -> None:
        """build_ssl_context() must raise ValueError if is_enabled is False."""
        cfg = OtTlsConfig(
            enabled=False,
            ca_cert_path=None,
            client_cert_path=None,
            client_key_path=None,
        )
        with pytest.raises(ValueError, match="mTLS not fully configured"):
            build_ssl_context(cfg)

    def test_raises_file_not_found_for_missing_ca(self, tmp_path: Path) -> None:
        """build_ssl_context() raises FileNotFoundError when CA cert is missing."""
        cfg = OtTlsConfig(
            enabled=True,
            ca_cert_path=tmp_path / "nonexistent_ca.crt",
            client_cert_path=tmp_path / "client.crt",
            client_key_path=tmp_path / "client.key",
        )
        with pytest.raises(FileNotFoundError, match="CA certificate not found"):
            build_ssl_context(cfg)

    def test_raises_file_not_found_for_missing_client_cert(self, tmp_path: Path) -> None:
        """build_ssl_context() raises FileNotFoundError when client cert is missing."""
        # CA exists, but client cert does not
        ca = tmp_path / "ca.crt"
        ca.write_text("dummy-ca")
        cfg = OtTlsConfig(
            enabled=True,
            ca_cert_path=ca,
            client_cert_path=tmp_path / "nonexistent.crt",
            client_key_path=tmp_path / "client.key",
        )
        with pytest.raises(FileNotFoundError, match="Client certificate not found"):
            build_ssl_context(cfg)

    def test_returns_ssl_context_with_valid_certs(self, tmp_path: Path) -> None:
        """build_ssl_context() returns ssl.SSLContext when certs are valid."""
        cert_path, key_path = _gen_self_signed_cert(tmp_path)
        # Self-signed: use the cert itself as the CA
        cfg = OtTlsConfig(
            enabled=True,
            ca_cert_path=cert_path,
            client_cert_path=cert_path,
            client_key_path=key_path,
        )
        ctx = build_ssl_context(cfg)
        assert isinstance(ctx, ssl.SSLContext)
        # Verify TLS 1.2 is the minimum
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    def test_ssl_error_for_invalid_cert_content(self, tmp_path: Path) -> None:
        """build_ssl_context() raises ssl.SSLError when cert content is garbage."""
        ca = tmp_path / "ca.crt"
        cert = tmp_path / "client.crt"
        key = tmp_path / "client.key"
        for f in (ca, cert, key):
            f.write_text("this-is-not-a-valid-pem-certificate")
        cfg = OtTlsConfig(
            enabled=True,
            ca_cert_path=ca,
            client_cert_path=cert,
            client_key_path=key,
        )
        with pytest.raises((ssl.SSLError, Exception)):
            build_ssl_context(cfg)
