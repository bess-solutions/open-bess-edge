# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/security_notifier.py
==============================
BESSAI Security Incident Notifier — Ley 21.663/2024 (Marco Ciberseguridad).

Notifies the Chilean CSIRT Nacional and internal teams within 3 hours of
any cybersecurity incident, as mandated by Ley 21.663 Art. 9 (operadores
de infraestructura crítica, including BESS ≥1 MW).

Severity tiers (CSIRT Chile):
  CRITICAL  → nofity CSIRT within 1h  (e.g. unauthorized command executed)
  HIGH      → notify CSIRT within 3h  (e.g. HMAC verification failed)
  MEDIUM    → internal alert + weekly report  (e.g. rate limit exceeded)
  LOW       → log only

Usage::

    notifier = SecurityNotifier.from_env()
    await notifier.report_incident(
        incident_type="unauthorized_command",
        severity="HIGH",
        details={"role": "read_only", "command": "set_power", "zone": "OT"},
    )
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# CSIRT Nacional Chile endpoint (official)
_CSIRT_URL = "https://csirt.gob.cl/api/report"  # placeholder — register at csirt.gob.cl
_NOTIFICATION_SLA: dict[str, float] = {
    "CRITICAL": 3600.0,   # 1 hour
    "HIGH": 10800.0,      # 3 hours (Ley 21.663 máx)
    "MEDIUM": 86400.0,    # 24 hours (internal)
    "LOW": float("inf"),  # log only
}


@dataclass
class IncidentReport:
    """Structured cybersecurity incident record."""
    incident_id: str
    site_id: str
    timestamp_iso: str
    incident_type: str
    severity: str
    details: dict[str, Any]
    notification_deadline_iso: str
    notified_csirt: bool = False
    notified_at_iso: str = ""
    hash_sha256: str = ""  # integrity fingerprint

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "site_id": self.site_id,
            "timestamp": self.timestamp_iso,
            "type": self.incident_type,
            "severity": self.severity,
            "details": self.details,
            "deadline": self.notification_deadline_iso,
            "notified": self.notified_csirt,
            "hash": self.hash_sha256,
        }


class SecurityNotifier:
    """
    Ley 21.663/2024 — Cybersecurity incident notifier.

    Parameters
    ----------
    site_id         BESSAI site identifier.
    csirt_url       CSIRT API endpoint. Default: csirt.gob.cl (placeholder).
    dry_run         If True, logs but does not POST to CSIRT. For dev/CI.
    alert_email     Optional internal alert email (SMTP config from env).
    """

    def __init__(
        self,
        site_id: str = "BESS-SITE",
        csirt_url: str = _CSIRT_URL,
        dry_run: bool = True,
        alert_email: str | None = None,
    ) -> None:
        self._site_id = site_id
        self._csirt_url = csirt_url
        self._dry_run = dry_run
        self._alert_email = alert_email
        self._incident_log: list[IncidentReport] = []

        log.info(
            "security_notifier.initialized",
            site_id=site_id, dry_run=dry_run,
            norm_ref="Ley 21.663/2024 Art. 9",
        )

    @classmethod
    def from_env(cls) -> "SecurityNotifier":
        return cls(
            site_id=os.getenv("SITE_ID", "BESS-SITE"),
            csirt_url=os.getenv("CSIRT_ENDPOINT_URL", _CSIRT_URL),
            dry_run=os.getenv("CSIRT_DRY_RUN", "true").lower() == "true",
            alert_email=os.getenv("SECURITY_ALERT_EMAIL"),
        )

    async def report_incident(
        self,
        incident_type: str,
        severity: str,
        details: dict[str, Any],
    ) -> IncidentReport:
        """
        Record and report a security incident.

        Parameters
        ----------
        incident_type   : e.g. "unauthorized_command", "hmac_failure", "rate_limit"
        severity        : "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
        details         : Structured context (from SL2SecurityGate.audit_log[-1])

        Returns
        -------
        IncidentReport — with incident_id and notification status.
        """
        now = datetime.now(timezone.utc)
        sla_s = _NOTIFICATION_SLA.get(severity.upper(), float("inf"))

        # Cap deadline to avoid OverflowError on float("inf")
        if sla_s == float("inf"):
            deadline_iso = "N/A"
        else:
            deadline_ts = now.timestamp() + sla_s
            deadline_iso = datetime.fromtimestamp(deadline_ts, tz=timezone.utc).isoformat()

        # Build report
        report_dict = {
            "site_id": self._site_id,
            "timestamp": now.isoformat(),
            "type": incident_type,
            "severity": severity,
            "details": details,
        }
        report_hash = hashlib.sha256(
            json.dumps(report_dict, sort_keys=True).encode()
        ).hexdigest()

        incident = IncidentReport(
            incident_id=f"INC-{self._site_id}-{int(now.timestamp())}",
            site_id=self._site_id,
            timestamp_iso=now.isoformat(),
            incident_type=incident_type,
            severity=severity.upper(),
            details=details,
            notification_deadline_iso=deadline_iso,
            hash_sha256=report_hash,
        )
        self._incident_log.append(incident)

        log.warning(
            "security_incident.recorded",
            incident_id=incident.incident_id,
            severity=severity,
            type=incident_type,
            sla_hours=round(sla_s / 3600, 1),
            norm_ref="Ley 21.663/2024",
        )

        # Notify CSIRT for CRITICAL/HIGH
        if severity.upper() in ("CRITICAL", "HIGH"):
            await self._notify_csirt(incident)

        return incident

    async def _notify_csirt(self, incident: IncidentReport) -> None:
        """POST incident to CSIRT Nacional."""
        if self._dry_run:
            log.info(
                "security_notifier.csirt.dry_run",
                incident_id=incident.incident_id,
                would_post_to=self._csirt_url,
                norm_ref="Ley 21.663/2024 Art. 9",
            )
            incident.notified_csirt = True
            incident.notified_at_iso = datetime.now(timezone.utc).isoformat()
            return

        payload = json.dumps(incident.to_dict()).encode()
        loop = asyncio.get_running_loop()
        try:
            import urllib.request
            import ssl
            ctx = ssl.create_default_context()

            def _post() -> int:
                req = urllib.request.Request(
                    self._csirt_url,
                    data=payload,
                    headers={"Content-Type": "application/json",
                              "X-BESSAI-Site": self._site_id},
                    method="POST",
                )
                with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                    return r.status

            status = await loop.run_in_executor(None, _post)
            incident.notified_csirt = True
            incident.notified_at_iso = datetime.now(timezone.utc).isoformat()
            log.info("security_notifier.csirt.notified",
                     incident_id=incident.incident_id, status=status)
        except Exception as exc:
            log.error("security_notifier.csirt.failed",
                      incident_id=incident.incident_id, error=str(exc))

    @property
    def open_incidents(self) -> list[IncidentReport]:
        """Incidents not yet notified to CSIRT."""
        return [i for i in self._incident_log
                if i.severity in ("CRITICAL", "HIGH") and not i.notified_csirt]

    @property
    def incident_log(self) -> list[IncidentReport]:
        return list(self._incident_log)
