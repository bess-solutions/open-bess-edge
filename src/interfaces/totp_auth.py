# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/totp_auth.py
============================
BESSAI Edge Gateway — TOTP Multi-Factor Authentication (MFA).

Implements Time-based One-Time Password (TOTP / RFC 6238) verification
for the admin dashboard API, closing IEC 62443-3-3 GAP-001 (SR 1.3 — MFA).

Design
------
- **Soft dependency**: ``pyotp`` is optional. If not installed, TOTP check
  is skipped with a warning (Bearer-only auth remains active).
- **Env-driven**: configure via ``DASHBOARD_MFA_SECRET`` (Base32 TOTP secret).
  If not set → TOTP is not enforced (dev mode).
- **Window tolerance**: ±1 step (30s × 3 = 90s window) to allow clock skew
  between client and gateway.

Usage (environment variables)::

    # Generate a secret (one-time, store securely):
    python -c "import pyotp; print(pyotp.random_base32())"

    # Set in config/.env or GitHub Secret:
    DASHBOARD_MFA_SECRET=JBSWY3DPEHPK3PXP

    # Clients send the 6-digit token in header:
    X-TOTP-Token: 123456

IEC 62443-3-3 mapping:
    SR 1.3 — Account Management: MFA required for human users.
    This module satisfies the MFA requirement for the admin REST API.
"""

from __future__ import annotations

import base64
import os
from typing import Any

import structlog

__all__ = ["TOTPAuth", "TOTPInfo"]

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# pyotp soft import
# ---------------------------------------------------------------------------

try:
    import pyotp as _pyotp  # type: ignore[import]

    _PYOTP_AVAILABLE = True
except ImportError:
    _pyotp = None  # type: ignore[assignment]
    _PYOTP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_TOTP_STEP_SECONDS = 30  # RFC 6238 standard
_TOTP_DIGITS = 6
_TOTP_WINDOW = 1  # ±1 step (±30s) allowed for clock skew
_TOTP_ISSUER = "BESSAI Edge Gateway"


# ---------------------------------------------------------------------------
# TOTPInfo — response DTO
# ---------------------------------------------------------------------------


class TOTPInfo:
    """Response data for the /api/v1/auth/totp-info endpoint."""

    def __init__(
        self,
        enabled: bool,
        pyotp_available: bool,
        algorithm: str = "SHA1",
        digits: int = _TOTP_DIGITS,
        period: int = _TOTP_STEP_SECONDS,
    ) -> None:
        self.enabled = enabled
        self.pyotp_available = pyotp_available
        self.algorithm = algorithm
        self.digits = digits
        self.period = period

    def to_dict(self) -> dict[str, Any]:
        return {
            "mfa_enabled": self.enabled,
            "pyotp_installed": self.pyotp_available,
            "algorithm": self.algorithm,
            "digits": self.digits,
            "period_seconds": self.period,
            "setup": (
                "Set DASHBOARD_MFA_SECRET env var with a Base32 secret. "
                "Clients must send X-TOTP-Token header with every request."
            )
            if not self.enabled
            else (
                "MFA active. Clients must send a valid 6-digit TOTP token "
                "in the X-TOTP-Token header alongside the Bearer token."
            ),
            "iec_62443_ref": "SR 1.3 — Account Management (MFA requirement)",
            "gap_status": "CLOSED" if self.enabled else "OPEN — set DASHBOARD_MFA_SECRET to close",
        }


# ---------------------------------------------------------------------------
# TOTPAuth — main class
# ---------------------------------------------------------------------------


class TOTPAuth:
    """
    TOTP verifier for the BESSAI Dashboard API.

    Parameters
    ----------
    secret:
        Base32-encoded TOTP shared secret. If ``None``, reads from the
        ``DASHBOARD_MFA_SECRET`` environment variable. If neither is set,
        TOTP enforcement is disabled (dev mode).
    site_id:
        Used to build the TOTP URI label (shown in authenticator apps).
    """

    def __init__(
        self,
        secret: str | None = None,
        site_id: str = "edge-001",
    ) -> None:
        self._secret: str | None = secret or os.getenv("DASHBOARD_MFA_SECRET") or None
        self._site_id = site_id
        self._totp: Any | None = None

        if self._secret and _PYOTP_AVAILABLE:
            try:
                self._totp = _pyotp.TOTP(
                    self._secret,
                    digits=_TOTP_DIGITS,
                    interval=_TOTP_STEP_SECONDS,
                )
                log.info(
                    "totp_auth.initialized",
                    site_id=site_id,
                    mfa_enabled=True,
                )
            except Exception as exc:
                log.error(
                    "totp_auth.init_failed",
                    error=str(exc),
                    hint="Check that DASHBOARD_MFA_SECRET is valid Base32.",
                )
                self._totp = None
        elif self._secret and not _PYOTP_AVAILABLE:
            log.warning(
                "totp_auth.pyotp_not_installed",
                hint="Run: pip install pyotp>=2.9.0 to enable MFA enforcement.",
            )
        else:
            log.info("totp_auth.disabled", reason="DASHBOARD_MFA_SECRET not set — dev mode")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_enabled(self) -> bool:
        """True if TOTP enforcement is active (secret configured + pyotp installed)."""
        return self._totp is not None

    def verify(self, token: str) -> bool:
        """
        Verify a TOTP token.

        Parameters
        ----------
        token:
            6-digit TOTP token from the client (string with possible spaces/hyphens).

        Returns
        -------
        bool
            True if the token is valid within the allowed clock window.
            Always True if TOTP is not enabled (dev mode).
        """
        if not self.is_enabled:
            return True  # dev mode — no MFA enforced

        # Sanitize: remove spaces and hyphens (some apps add them for readability)
        token = token.replace(" ", "").replace("-", "")

        if not token.isdigit() or len(token) != _TOTP_DIGITS:
            log.warning("totp_auth.invalid_token_format", length=len(token))
            return False

        valid = self._totp.verify(token, valid_window=_TOTP_WINDOW)
        log.info("totp_auth.verify", valid=valid)
        return bool(valid)

    def provisioning_uri(self, account_name: str = "admin") -> str | None:
        """
        Generate the TOTP provisioning URI (for QR code generation).

        Returns None if TOTP is not configured.
        """
        if not self._totp:
            return None
        return self._totp.provisioning_uri(
            name=f"{account_name}@{self._site_id}",
            issuer_name=_TOTP_ISSUER,
        )

    def info(self) -> TOTPInfo:
        """Return metadata about the current TOTP configuration."""
        return TOTPInfo(
            enabled=self.is_enabled,
            pyotp_available=_PYOTP_AVAILABLE,
        )

    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new random Base32 TOTP secret suitable for a TOTP app.

        Returns the secret as a Base32 string (e.g. for storing in GitHub Secrets).
        """
        if _PYOTP_AVAILABLE:
            return _pyotp.random_base32()  # type: ignore[union-attr]
        # Fallback: generate 20 random bytes encoded as Base32
        raw = os.urandom(20)
        return base64.b32encode(raw).decode("ascii")
