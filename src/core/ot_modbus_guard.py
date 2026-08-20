# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/ot_modbus_guard.py
============================
BESSAI Edge Gateway — IEC 62443 Security Level 2 (SL-2) Modbus Integrity Guard.

Inspects, sanitizes, and enforces cryptographic rate-limiting & register boundaries
on all OT Modbus TCP writes to prevent unauthorized setpoint manipulation.
"""

from __future__ import annotations
import hmac
import hashlib
import time
from dataclasses import dataclass, field

__all__ = ["OTModbusGuard", "SecurityInspectionResult", "GuardPolicy"]


@dataclass
class GuardPolicy:
    max_charge_kw: float = 5000.0
    max_discharge_kw: float = 5000.0
    max_writes_per_minute: int = 120
    allowed_slave_ids: tuple[int, ...] = (1, 2, 3)
    require_hmac_for_critical: bool = True


@dataclass
class SecurityInspectionResult:
    allowed: bool
    reason: str
    violation_code: str | None = None
    sanitized_value: float | None = None


class OTModbusGuard:
    """Zero-Trust OT Modbus Packet & Command Inspector."""

    def __init__(self, shared_secret: str = "bessai-default-secret", policy: GuardPolicy | None = None):
        self.secret = shared_secret.encode("utf-8")
        self.policy = policy or GuardPolicy()
        self._write_timestamps: list[float] = []

    def inspect_power_setpoint(
        self,
        power_kw: float,
        slave_id: int,
        client_ip: str,
        auth_token: str | None = None,
    ) -> SecurityInspectionResult:
        now = time.time()
        # 1. Rate Limiting Check
        self._write_timestamps = [t for t in self._write_timestamps if now - t < 60.0]
        if len(self._write_timestamps) >= self.policy.max_writes_per_minute:
            return SecurityInspectionResult(allowed=False, reason="Rate limit exceeded", violation_code="DOS_RATE_LIMIT")

        # 2. Slave ID Whitelist
        if slave_id not in self.policy.allowed_slave_ids:
            return SecurityInspectionResult(allowed=False, reason=f"Unauthorized slave {slave_id}", violation_code="INVALID_SLAVE_ID")

        # 3. Physical Invariant Safety Bounds
        if power_kw > self.policy.max_charge_kw:
            return SecurityInspectionResult(allowed=False, reason="Charge power exceeds inverter limit", violation_code="OVER_CAPACITY_ATTACK")
        if power_kw < -self.policy.max_discharge_kw:
            return SecurityInspectionResult(allowed=False, reason="Discharge power exceeds rating", violation_code="OVER_DISCHARGE_ATTACK")

        # 4. Critical Signature Check if power change > 2.5 MW
        if self.policy.require_hmac_for_critical and abs(power_kw) > 2500.0:
            if not auth_token or not self._verify_hmac(power_kw, auth_token):
                return SecurityInspectionResult(allowed=False, reason="Missing or invalid HMAC signature for >2.5MW dispatch", violation_code="UNAUTHENTICATED_DISPATCH")

        self._write_timestamps.append(now)
        return SecurityInspectionResult(allowed=True, reason="Command validated and authorized", sanitized_value=power_kw)

    def generate_hmac(self, power_kw: float) -> str:
        msg = f"{power_kw:.2f}".encode("utf-8")
        return hmac.new(self.secret, msg, hashlib.sha256).hexdigest()

    def _verify_hmac(self, power_kw: float, token: str) -> bool:
        expected = self.generate_hmac(power_kw)
        return hmac.compare_digest(expected, token)
