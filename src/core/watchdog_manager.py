# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/watchdog_manager.py
==============================
BESSAI Edge Gateway — Autonomous Self-Healing Watchdog Manager.

**BESSAI Plan de Inmortalidad — Eje 1: El código se defiende solo**

This module implements a proactive self-healing watchdog that monitors the
DataProvider health and autonomously attempts reconnection when failures are
detected, without human intervention.

Architecture
------------
The WatchdogManager sits above the SafetyGuard (reactive) and below main.py
(coordinator). It provides the "immune system" layer of the gateway:

::

    main.py
      └─ WatchdogManager  ─── monitors ──► DataProvider (ModbusDriver)
           │                              │
           ├─ _health_check()             └─ is_connected, .read_tag()
           ├─ _self_heal()  ──── reconnects ──► DataProvider.reconnect()
           └─ _notify_critical()  ── alert ──► AlertDispatcher (optional)

Design principles
-----------------
* **Fail-safe**: if reconnection fails after all retries, emits a CRITICAL log
  and alert but does NOT crash the process — safety must remain operational.
* **Exponential backoff**: reconnection delays grow: 1s → 2s → 4s (capped at 30s).
* **Prometheus metrics**: `bess_watchdog_heals_total` and
  `bess_watchdog_last_heal_timestamp_seconds` for observability.
* **Pluggable**: works with any DataProvider implementing is_connected + reconnect().

Environment Variables
---------------------
WATCHDOG_HEALTH_INTERVAL_S = 5     (seconds between health checks; default: 5)
WATCHDOG_MAX_HEAL_RETRIES   = 5    (max reconnection attempts; default: 5)
WATCHDOG_BACKOFF_BASE_S     = 1.0  (initial backoff seconds; default: 1.0)
WATCHDOG_BACKOFF_MAX_S      = 30.0 (max backoff seconds; default: 30.0)

Usage
-----
::

    manager = WatchdogManager(driver=driver)
    asyncio.create_task(manager.run(), name="watchdog_manager")
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    from src.drivers.base import DataProvider

__all__ = ["WatchdogManager", "WatchdogMetrics", "ReconnectableDriver"]

log = structlog.get_logger(__name__)


@runtime_checkable
class ReconnectableDriver(Protocol):
    """Protocol for drivers that support autonomous reconnection.

    Any DataProvider that implements ``is_connected`` and ``reconnect()``
    satisfies this protocol.
    """

    @property
    def is_connected(self) -> bool: ...

    async def reconnect(self) -> None: ...

    async def read_tag(self, tag: str) -> float: ...


class WatchdogMetrics:
    """Lightweight Prometheus metrics wrapper for the WatchdogManager.

    Uses prometheus_client if available; silently degrades otherwise.
    """

    def __init__(self) -> None:
        self._heals_total: Any | None = None
        self._last_heal_ts: Any | None = None
        self._available: bool = False

        try:
            from prometheus_client import Counter, Gauge

            self._heals_total = Counter(
                "bess_watchdog_heals_total",
                "Total autonomous self-heal reconnection attempts by the WatchdogManager",
                ["outcome"],  # labels: success | failure
            )
            self._last_heal_ts = Gauge(
                "bess_watchdog_last_heal_timestamp_seconds",
                "Unix timestamp of the last self-heal attempt",
            )
            self._available = True
        except (ImportError, Exception):
            pass  # prometheus_client not installed → graceful degradation

    def inc_heals(self, outcome: str) -> None:
        """Increment heal counter. outcome: 'success' | 'failure'"""
        if self._available and self._heals_total is not None:
            try:
                self._heals_total.labels(outcome=outcome).inc()
            except Exception:
                pass

    def set_last_heal(self, ts: float | None = None) -> None:
        """Record the timestamp of the latest heal attempt."""
        if self._available and self._last_heal_ts is not None:
            try:
                self._last_heal_ts.set(ts if ts is not None else time.time())
            except Exception:
                pass


class WatchdogManager:
    """Autonomous self-healing watchdog for BESSAI DataProvider connections.

    Monitors driver health at a configurable interval and attempts reconnection
    using exponential backoff when connectivity is lost.

    Parameters
    ----------
    driver:
        A ReconnectableDriver instance (any DataProvider with reconnect()).
    health_interval_s:
        Seconds between health checks (default: from WATCHDOG_HEALTH_INTERVAL_S env).
    max_heal_retries:
        Maximum reconnection attempts before giving up (default: 5).
    backoff_base_s:
        Initial backoff seconds for reconnection (default: 1.0, doubles each retry).
    backoff_max_s:
        Maximum backoff cap in seconds (default: 30.0).
    alert_dispatcher:
        Optional AlertDispatcher-compatible object with .dispatch() method.
    """

    def __init__(
        self,
        driver: ReconnectableDriver,
        health_interval_s: float | None = None,
        max_heal_retries: int | None = None,
        backoff_base_s: float | None = None,
        backoff_max_s: float | None = None,
        alert_dispatcher: Any | None = None,
    ) -> None:
        self._driver = driver
        self._health_interval_s = health_interval_s or float(
            os.getenv("WATCHDOG_HEALTH_INTERVAL_S", "5")
        )
        self._max_heal_retries = max_heal_retries or int(
            os.getenv("WATCHDOG_MAX_HEAL_RETRIES", "5")
        )
        self._backoff_base_s = backoff_base_s or float(
            os.getenv("WATCHDOG_BACKOFF_BASE_S", "1.0")
        )
        self._backoff_max_s = backoff_max_s or float(
            os.getenv("WATCHDOG_BACKOFF_MAX_S", "30.0")
        )
        self._alert_dispatcher = alert_dispatcher
        self._metrics = WatchdogMetrics()

        # State
        self._running: bool = False
        self._consecutive_failures: int = 0
        self._total_heals: int = 0
        self._total_heal_failures: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the autonomous watchdog loop.

        Runs until cancelled. Re-raises CancelledError for clean shutdown.
        """
        self._running = True
        log.info(
            "watchdog_manager.started",
            health_interval_s=self._health_interval_s,
            max_heal_retries=self._max_heal_retries,
            backoff_base_s=self._backoff_base_s,
        )

        try:
            while self._running:
                await asyncio.sleep(self._health_interval_s)
                await self._health_check()
        except asyncio.CancelledError:
            log.info(
                "watchdog_manager.stopped",
                total_heals=self._total_heals,
                total_heal_failures=self._total_heal_failures,
            )
            raise

    async def stop(self) -> None:
        """Stop the watchdog loop gracefully."""
        self._running = False

    # ------------------------------------------------------------------
    # Internal — health check
    # ------------------------------------------------------------------

    async def _health_check(self) -> None:
        """Check driver health and trigger self-heal if needed."""
        if self._driver.is_connected:
            self._consecutive_failures = 0
            log.debug("watchdog_manager.health_ok")
            return

        self._consecutive_failures += 1
        log.warning(
            "watchdog_manager.driver_disconnected",
            consecutive_failures=self._consecutive_failures,
            action="initiating_self_heal",
        )

        healed = await self._self_heal()
        if not healed:
            await self._notify_critical()

    # ------------------------------------------------------------------
    # Internal — self-healing loop
    # ------------------------------------------------------------------

    async def _self_heal(self) -> bool:
        """Attempt to reconnect the driver using exponential backoff.

        Returns
        -------
        bool
            True if reconnection succeeded, False after all retries exhausted.
        """
        self._metrics.set_last_heal()

        for attempt in range(1, self._max_heal_retries + 1):
            backoff = min(
                self._backoff_base_s * (2 ** (attempt - 1)),
                self._backoff_max_s,
            )
            log.info(
                "watchdog_manager.heal_attempt",
                attempt=attempt,
                max_retries=self._max_heal_retries,
                backoff_s=backoff,
            )

            try:
                await self._driver.reconnect()

                if self._driver.is_connected:
                    self._total_heals += 1
                    self._consecutive_failures = 0
                    self._metrics.inc_heals("success")
                    log.info(
                        "watchdog_manager.heal_success",
                        attempt=attempt,
                        total_heals=self._total_heals,
                    )
                    return True
                else:
                    log.warning(
                        "watchdog_manager.heal_reconnect_returned_but_not_connected",
                        attempt=attempt,
                    )

            except asyncio.CancelledError:
                raise  # propagate clean shutdown

            except Exception as exc:
                log.warning(
                    "watchdog_manager.heal_attempt_failed",
                    attempt=attempt,
                    error=str(exc),
                )

            # Wait before next retry
            await asyncio.sleep(backoff)

        # All retries exhausted
        self._total_heal_failures += 1
        self._metrics.inc_heals("failure")
        log.critical(
            "watchdog_manager.heal_EXHAUSTED",
            max_retries=self._max_heal_retries,
            total_heal_failures=self._total_heal_failures,
            action="driver_remains_disconnected_system_continues_in_safe_mode",
        )
        return False

    # ------------------------------------------------------------------
    # Internal — critical alert
    # ------------------------------------------------------------------

    async def _notify_critical(self) -> None:
        """Notify AlertDispatcher of a critical watchdog failure."""
        if self._alert_dispatcher is None:
            return

        try:
            await self._alert_dispatcher.dispatch(
                level="CRITICAL",
                title="BESSAI WatchdogManager — Driver Reconnection Exhausted",
                message=(
                    f"The WatchdogManager has exhausted {self._max_heal_retries} "
                    "reconnection attempts. The DataProvider remains disconnected. "
                    "Manual intervention required."
                ),
                tags={
                    "component": "watchdog_manager",
                    "total_heal_failures": str(self._total_heal_failures),
                },
            )
        except Exception as exc:
            log.error(
                "watchdog_manager.alert_dispatch_failed",
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Properties (for testing / monitoring)
    # ------------------------------------------------------------------

    @property
    def consecutive_failures(self) -> int:
        """Current count of consecutive health-check failures."""
        return self._consecutive_failures

    @property
    def total_heals(self) -> int:
        """Total successful self-heal reconnections since start."""
        return self._total_heals

    @property
    def total_heal_failures(self) -> int:
        """Total exhausted heal sequences (all retries failed)."""
        return self._total_heal_failures
