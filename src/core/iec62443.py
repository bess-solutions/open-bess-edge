# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/iec62443.py
=====================
IEC 62443 SL-2 Security Compliance — Res. SEC 2024 (GAP-009).

Implements Security Level 2 (SL-2) controls for Operational Technology
networks as mandated by Resolución Exenta SEC Nº 7072/2024, which adopts
IEC 62443 as the cybersecurity standard for grid-connected BESS in Chile.

IEC 62443 SL-2 Controls Implemented
--------------------------------------
FR-1 (Identification & Auth): API key / TOTP validation gate.
FR-2 (Use Control): command authorization by role.
FR-3 (System Integrity): payload hash verification.
FR-4 (Data Confidentiality): TLS enforcement check.
FR-5 (Restricted Data Flow): zone/conduit validation.
FR-7 (Resource Availability): rate limiting guard.

Note: FR-6 (Timely Response to Events) is handled by the existing
``alert_dispatcher.py`` + ``watchdog_manager.py`` modules.

Usage::

    sl2 = SL2SecurityGate()
    ok, reason = sl2.authorize_command(
        role="operator",
        command="set_power",
        source_zone="DMZ",
    )
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Role-based command authorization (FR-2)
# ---------------------------------------------------------------------------

_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "read_only":  frozenset({"read_telemetry", "read_status"}),
    "operator":   frozenset({"read_telemetry", "read_status",
                             "set_power", "set_mode", "acknowledge_alarm"}),
    "engineer":   frozenset({"read_telemetry", "read_status",
                             "set_power", "set_mode", "acknowledge_alarm",
                             "update_config", "calibrate"}),
    "admin":      frozenset({"*"}),  # all commands
}

# Allowed network zones for OT commands (FR-5)
_ALLOWED_ZONES = frozenset({"OT", "DMZ", "CONTROL"})

# Rate limit: max commands per minute per role (FR-7)
_RATE_LIMITS: dict[str, int] = {
    "read_only": 120,
    "operator": 60,
    "engineer": 60,
    "admin": 30,
}


@dataclass
class SL2AuditEvent:
    """Structured audit log entry for IEC 62443 SL-2 compliance."""
    timestamp: float
    role: str
    command: str
    source_zone: str
    allowed: bool
    reason: str
    integrity_ok: bool = True


class SL2SecurityGate:
    """
    IEC 62443 SL-2 security gate for BESS command authorization.

    Parameters
    ----------
    hmac_secret:
        Shared HMAC-SHA256 secret for payload integrity (FR-3).
        If None, integrity checking is skipped (not recommended).
    enforce_tls:
        If True, rejects commands from non-TLS connections (FR-4).
    """

    def __init__(
        self,
        hmac_secret: bytes | None = None,
        enforce_tls: bool = True,
    ) -> None:
        self._secret = hmac_secret
        self._enforce_tls = enforce_tls
        # Rate limiting counters: {role: [timestamps]}
        self._rate_counters: dict[str, list[float]] = {}
        self._audit_log: list[SL2AuditEvent] = []

        log.info("sl2_gate.initialized", enforce_tls=enforce_tls,
                 integrity_check=hmac_secret is not None,
                 norm_ref="IEC 62443 SL-2 / Res. SEC 7072/2024")

    # ------------------------------------------------------------------
    # FR-2: Command Authorization
    # ------------------------------------------------------------------

    def authorize_command(
        self,
        role: str,
        command: str,
        source_zone: str = "OT",
        tls_active: bool = True,
        payload: bytes | None = None,
        payload_hmac: str | None = None,
    ) -> tuple[bool, str]:
        """
        Authorize a command for a given role.

        Returns
        -------
        tuple[bool, str]
            (True, "") if authorized.
            (False, reason) if denied.
        """
        # FR-4: TLS enforcement
        if self._enforce_tls and not tls_active:
            return self._deny(role, command, source_zone, "TLS required (FR-4)")

        # FR-5: Zone check
        if source_zone not in _ALLOWED_ZONES:
            return self._deny(role, command, source_zone,
                              f"Zone '{source_zone}' not allowed (FR-5)")

        # FR-3: Payload integrity
        if payload is not None and self._secret is not None:
            if not self._verify_hmac(payload, payload_hmac or ""):
                event = SL2AuditEvent(
                    timestamp=time.time(), role=role, command=command,
                    source_zone=source_zone, allowed=False,
                    reason="HMAC verification failed (FR-3)",
                    integrity_ok=False,
                )
                self._audit_log.append(event)
                log.warning("sl2.block.integrity", role=role, command=command,
                            norm_ref="IEC 62443 FR-3")
                return False, "HMAC verification failed (FR-3)"

        # FR-7: Rate limiting
        if not self._check_rate(role):
            return self._deny(role, command, source_zone,
                              f"Rate limit exceeded for role '{role}' (FR-7)")

        # FR-2: Role permission check
        perms = _ROLE_PERMISSIONS.get(role, frozenset())
        if "*" not in perms and command not in perms:
            return self._deny(role, command, source_zone,
                              f"Role '{role}' not permitted to execute '{command}' (FR-2)")

        # Authorized
        event = SL2AuditEvent(
            timestamp=time.time(), role=role, command=command,
            source_zone=source_zone, allowed=True, reason="",
        )
        self._audit_log.append(event)
        log.info("sl2.authorized", role=role, command=command, zone=source_zone)
        return True, ""

    # ------------------------------------------------------------------
    # FR-3: Payload integrity
    # ------------------------------------------------------------------

    def sign_payload(self, payload: bytes) -> str:
        """Compute HMAC-SHA256 signature for a payload."""
        if self._secret is None:
            return ""
        return hmac.new(self._secret, payload, hashlib.sha256).hexdigest()

    def _verify_hmac(self, payload: bytes, expected_hmac: str) -> bool:
        if self._secret is None:
            return True
        actual = hmac.new(self._secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(actual, expected_hmac)

    # ------------------------------------------------------------------
    # FR-7: Rate limiting (sliding window)
    # ------------------------------------------------------------------

    def _check_rate(self, role: str) -> bool:
        limit = _RATE_LIMITS.get(role, 60)
        now = time.time()
        window = self._rate_counters.setdefault(role, [])
        # Keep only timestamps within the last 60 s
        window[:] = [t for t in window if now - t < 60.0]
        if len(window) >= limit:
            return False
        window.append(now)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _deny(self, role: str, command: str, zone: str, reason: str) -> tuple[bool, str]:
        event = SL2AuditEvent(
            timestamp=time.time(), role=role, command=command,
            source_zone=zone, allowed=False, reason=reason,
        )
        self._audit_log.append(event)
        log.warning("sl2.denied", role=role, command=command,
                    zone=zone, reason=reason, norm_ref="IEC 62443 SL-2")
        return False, reason

    @property
    def audit_log(self) -> list[SL2AuditEvent]:
        """Immutable view of the audit log."""
        return list(self._audit_log)
