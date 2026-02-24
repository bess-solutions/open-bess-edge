"""
src/interfaces/ot_tls_config.py
================================
OT segment mTLS configuration helper.

IEC 62443-3-3 SR 3.1: Communication Integrity
GAP-003 REMEDIATION

Reads environment variables and constructs an ``ssl.SSLContext``
for mutual TLS authentication between the BESSAI Edge Gateway
and the Modbus TCP device.

Environment Variables
---------------------
OT_MTLS_ENABLED : str
    Set to ``"true"`` (case-insensitive) to activate mTLS enforcement.
    Any other value (including absent) → mTLS disabled, plain TCP used.
OT_CA_CERT_PATH : str
    Path to the CA root certificate (``ca.crt``) that signed both the
    gateway client cert and the inverter server cert.
OT_CLIENT_CERT_PATH : str
    Path to the gateway client certificate (``gateway-client.crt``).
OT_CLIENT_KEY_PATH : str
    Path to the gateway client private key (``gateway-client.key``).

Usage
-----
::

    from src.interfaces.ot_tls_config import OtTlsConfig, build_ssl_context

    cfg = OtTlsConfig.from_env()
    if cfg.is_enabled:
        sslctx = build_ssl_context(cfg)
        driver = UniversalDriver(host=IP, port=8502, tls_context=sslctx)
    else:
        driver = UniversalDriver(host=IP, port=502)
"""

from __future__ import annotations

import os
import ssl
from dataclasses import dataclass
from pathlib import Path

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class OtTlsConfig:
    """
    Immutable snapshot of the OT mTLS configuration.

    Parameters
    ----------
    enabled:
        Whether mTLS is requested.
    ca_cert_path:
        Path to the CA root certificate.
    client_cert_path:
        Path to the gateway client certificate.
    client_key_path:
        Path to the gateway client private key.
    """

    enabled: bool
    ca_cert_path: Path | None
    client_cert_path: Path | None
    client_key_path: Path | None

    @property
    def is_enabled(self) -> bool:
        """True only if enabled AND all three cert paths are provided."""
        return (
            self.enabled
            and self.ca_cert_path is not None
            and self.client_cert_path is not None
            and self.client_key_path is not None
        )

    @classmethod
    def from_env(cls) -> OtTlsConfig:
        """
        Build an ``OtTlsConfig`` from environment variables.

        Returns
        -------
        OtTlsConfig
            Ready-to-use config. ``is_enabled`` is False if
            ``OT_MTLS_ENABLED`` is not set to ``"true"``.
        """
        raw_enabled = os.getenv("OT_MTLS_ENABLED", "false").strip().lower()
        enabled = raw_enabled in ("true", "1", "yes")

        ca = os.getenv("OT_CA_CERT_PATH")
        cert = os.getenv("OT_CLIENT_CERT_PATH")
        key = os.getenv("OT_CLIENT_KEY_PATH")

        cfg = cls(
            enabled=enabled,
            ca_cert_path=Path(ca) if ca else None,
            client_cert_path=Path(cert) if cert else None,
            client_key_path=Path(key) if key else None,
        )

        if cfg.enabled and not cfg.is_enabled:
            log.warning(
                "ot_tls.partially_configured",
                hint=(
                    "OT_MTLS_ENABLED=true but one or more of "
                    "OT_CA_CERT_PATH, OT_CLIENT_CERT_PATH, OT_CLIENT_KEY_PATH "
                    "is missing. Falling back to plain TCP."
                ),
                ca_cert_path=str(ca),
                client_cert_path=str(cert),
                client_key_path=str(key),
            )

        log.info(
            "ot_tls.configured",
            mtls_enabled=cfg.is_enabled,
            ca=str(cfg.ca_cert_path) if cfg.ca_cert_path else None,
            cert=str(cfg.client_cert_path) if cfg.client_cert_path else None,
        )

        return cfg


def build_ssl_context(cfg: OtTlsConfig) -> ssl.SSLContext:
    """
    Build a ``ssl.SSLContext`` for mutual TLS from an ``OtTlsConfig``.

    Parameters
    ----------
    cfg:
        Configuration from ``OtTlsConfig.from_env()``.

    Returns
    -------
    ssl.SSLContext
        Configured for TLS 1.2+ with client authentication and server
        certificate verification against the CA.

    Raises
    ------
    FileNotFoundError
        If any certificate file does not exist.
    ssl.SSLError
        If a certificate file is invalid or the key does not match.
    ValueError
        If ``cfg.is_enabled`` is False (caller should check before calling).
    """
    if not cfg.is_enabled:
        raise ValueError(
            "build_ssl_context() called with mTLS not fully configured. "
            "Check OT_MTLS_ENABLED, OT_CA_CERT_PATH, OT_CLIENT_CERT_PATH, "
            "OT_CLIENT_KEY_PATH environment variables."
        )

    # Validate file existence before loading (gives clear FileNotFoundError)
    for label, path in [
        ("CA certificate", cfg.ca_cert_path),
        ("Client certificate", cfg.client_cert_path),
        ("Client private key", cfg.client_key_path),
    ]:
        assert path is not None  # guaranteed by is_enabled
        if not path.is_file():
            raise FileNotFoundError(
                f"{label} not found: {path}. Run: bash infrastructure/certs/gen_certs.sh"
            )

    # Build context: TLS_CLIENT enforces server cert verification by default
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # Minimum TLS 1.2 (IEC 62443 SR 3.1 requirement)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    # Load CA to verify the inverter server certificate
    ctx.load_verify_locations(cafile=str(cfg.ca_cert_path))

    # Load gateway client certificate + private key (mTLS identity)
    ctx.load_cert_chain(
        certfile=str(cfg.client_cert_path),
        keyfile=str(cfg.client_key_path),
    )

    log.info(
        "ot_tls.ssl_context_built",
        tls_min_version="TLSv1.2",
        ca=str(cfg.ca_cert_path),
        client_cert=str(cfg.client_cert_path),
    )

    return ctx
