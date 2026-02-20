"""
src/interfaces/alert_manager.py
=================================
BESSAI Edge Gateway — Alert Manager.

Centralises alarm lifecycle: detection → routing → silencing → escalation.
Integrates with Prometheus Alertmanager webhooks, PagerDuty, and local BEEP.

Alert types (by severity):
  CRITICAL  → BESS overtemp / SOC emergency / AI-IDS high-confidence attack
  WARNING   → AI-IDS elevated score / SOC near limits / comms degraded
  INFO      → FL round complete / VPP event published / P2P credit minted

Usage::

    mgr = AlertManager(site_id="CL-001")
    mgr.fire(AlertLevel.CRITICAL, "OVERTEMP", "Battery temp 58°C > 55°C limit")
    mgr.fire(AlertLevel.WARNING, "IDS_ELEVATED", "Anomaly score 0.72")
    summary = mgr.summary()
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum

import structlog

from .metrics import IDS_ALERTS_TOTAL, SAFETY_BLOCKS_TOTAL

__all__ = ["AlertManager", "Alert", "AlertLevel"]

log = structlog.get_logger(__name__)


class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """Represents one fired alert event."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    level: AlertLevel = AlertLevel.INFO
    name: str = ""
    message: str = ""
    site_id: str = "edge"
    timestamp: float = field(default_factory=time.time)
    resolved: bool = False
    resolved_at: float | None = None

    def resolve(self) -> None:
        self.resolved = True
        self.resolved_at = time.time()

    def age_s(self) -> float:
        return time.time() - self.timestamp

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "name": self.name,
            "message": self.message,
            "site_id": self.site_id,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "age_s": round(self.age_s(), 1),
        }


class AlertManager:
    """Central alert lifecycle manager for a BESSAI edge site.

    Parameters:
        site_id:        Site identifier for Prometheus labels.
        max_history:    Number of resolved alerts to retain.
        dedup_window_s: Seconds within which duplicate alerts are suppressed.
    """

    def __init__(
        self,
        site_id: str = "edge",
        max_history: int = 200,
        dedup_window_s: float = 60.0,
    ) -> None:
        self.site_id = site_id
        self.dedup_window_s = dedup_window_s
        self._active: dict[str, Alert] = {}          # name → Alert
        self._history: deque[Alert] = deque(maxlen=max_history)
        self._fire_times: dict[str, float] = {}      # name → last fired ts

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fire(
        self,
        level: AlertLevel,
        name: str,
        message: str = "",
    ) -> Alert | None:
        """Fire a new alert (with deduplication).

        Args:
            level:   Severity level.
            name:    Short alert identifier (e.g., 'OVERTEMP').
            message: Human-readable detail string.

        Returns:
            Alert if fired (or updated), None if deduplicated.
        """
        now = time.time()
        last = self._fire_times.get(name, 0.0)
        if now - last < self.dedup_window_s and name in self._active:
            log.debug("alert.deduplicated", name=name, age_s=round(now - last, 1))
            return None

        alert = Alert(
            level=level,
            name=name,
            message=message,
            site_id=self.site_id,
        )
        self._active[name] = alert
        self._fire_times[name] = now

        # Prometheus
        if level == AlertLevel.CRITICAL:
            SAFETY_BLOCKS_TOTAL.labels(
                site_id=self.site_id, reason=name
            ).inc()
        elif level == AlertLevel.WARNING and name.startswith("IDS"):
            IDS_ALERTS_TOTAL.labels(
                site_id=self.site_id, reason=name
            ).inc()

        log.warning(
            "alert.fired",
            level=level.value,
            name=name,
            message=message[:80],
        )
        return alert

    def resolve(self, name: str) -> bool:
        """Resolve an active alert by name.

        Returns:
            True if an active alert was found and resolved.
        """
        if name in self._active:
            alert = self._active.pop(name)
            alert.resolve()
            self._history.append(alert)
            log.info("alert.resolved", name=name, age_s=round(alert.age_s(), 1))
            return True
        return False

    def resolve_all(self) -> int:
        """Resolve all active alerts. Returns count resolved."""
        names = list(self._active.keys())
        for name in names:
            self.resolve(name)
        return len(names)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def critical_count(self) -> int:
        return sum(1 for a in self._active.values() if a.level == AlertLevel.CRITICAL)

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0

    def get_active(self) -> list[dict]:
        return [a.to_dict() for a in self._active.values()]

    def summary(self) -> dict:
        counts: dict[str, int] = defaultdict(int)
        for a in self._active.values():
            counts[a.level.value] += 1
        return {
            "site_id": self.site_id,
            "active_total": self.active_count,
            "critical": counts["CRITICAL"],
            "warning": counts["WARNING"],
            "info": counts["INFO"],
            "history_total": len(self._history),
            "active": self.get_active(),
        }
