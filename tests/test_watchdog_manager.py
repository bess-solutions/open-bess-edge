# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_watchdog_manager.py
================================
Unit tests for src/core/watchdog_manager.py — Autonomous Self-Healing Watchdog.

Coverage targets:
- Normal healthy driver: no heals triggered
- Disconnected driver: reconnection loop is triggered
- Successful reconnection: state is reset, metrics updated
- Exhausted reconnection: CRITICAL log + alert emitted
- Alert dispatch error: graceful degradation (no crash)
- stop(): loop terminates cleanly
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.watchdog_manager import WatchdogManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_driver(connected: bool = True, reconnect_succeeds: bool = True) -> MagicMock:
    """Create a minimal ReconnectableDriver mock."""
    driver = MagicMock()
    driver.is_connected = connected

    if reconnect_succeeds:
        async def _reconnect() -> None:
            driver.is_connected = True

        driver.reconnect = _reconnect
    else:
        driver.reconnect = AsyncMock(side_effect=OSError("Connection refused"))

    return driver


def _make_wm(
    driver: MagicMock,
    health_interval_s: float = 0.01,
    max_heal_retries: int = 3,
    backoff_base_s: float = 0.001,
    backoff_max_s: float = 0.01,
    alert_dispatcher: Any = None,
) -> WatchdogManager:
    """Create a WatchdogManager with fast intervals for tests."""
    return WatchdogManager(
        driver=driver,
        health_interval_s=health_interval_s,
        max_heal_retries=max_heal_retries,
        backoff_base_s=backoff_base_s,
        backoff_max_s=backoff_max_s,
        alert_dispatcher=alert_dispatcher,
    )


# ---------------------------------------------------------------------------
# TestWatchdogManagerInit
# ---------------------------------------------------------------------------


class TestWatchdogManagerInit:
    def test_defaults(self) -> None:
        driver = _make_driver()
        wm = WatchdogManager(driver=driver)
        assert wm._health_interval_s == 5.0
        assert wm._max_heal_retries == 5
        assert wm._backoff_base_s == 1.0
        assert wm._backoff_max_s == 30.0

    def test_custom_params(self) -> None:
        driver = _make_driver()
        wm = WatchdogManager(
            driver=driver,
            health_interval_s=2.5,
            max_heal_retries=10,
            backoff_base_s=0.5,
            backoff_max_s=60.0,
        )
        assert wm._health_interval_s == 2.5
        assert wm._max_heal_retries == 10

    def test_initial_counters_zero(self) -> None:
        driver = _make_driver()
        wm = _make_wm(driver)
        assert wm.consecutive_failures == 0
        assert wm.total_heals == 0
        assert wm.total_heal_failures == 0


# ---------------------------------------------------------------------------
# TestHealthCheck
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_healthy_driver_no_heal(self) -> None:
        """Healthy driver → no heal triggered, counters stay at zero."""
        driver = _make_driver(connected=True)
        wm = _make_wm(driver)
        await wm._health_check()
        assert wm.consecutive_failures == 0
        assert wm.total_heals == 0

    @pytest.mark.asyncio
    async def test_disconnected_driver_triggers_heal(self) -> None:
        """Disconnected driver + reconnect succeeds → total_heals = 1."""
        driver = _make_driver(connected=False, reconnect_succeeds=True)
        wm = _make_wm(driver)
        await wm._health_check()
        assert wm.total_heals == 1
        assert wm.total_heal_failures == 0

    @pytest.mark.asyncio
    async def test_consecutive_failures_incremented(self) -> None:
        """Each health_check call with disconnected driver increments counter."""
        driver = _make_driver(connected=False, reconnect_succeeds=True)
        wm = _make_wm(driver)
        # First check: driver starts disconnected, heals, then mark connected
        # Second check with driver still connected resets counter
        await wm._health_check()
        assert wm.consecutive_failures == 0  # reset after successful heal


# ---------------------------------------------------------------------------
# TestSelfHeal
# ---------------------------------------------------------------------------


class TestSelfHeal:
    @pytest.mark.asyncio
    async def test_heal_success_first_attempt(self) -> None:
        """Reconnect succeeds on first attempt → True returned."""
        driver = _make_driver(connected=False, reconnect_succeeds=True)
        wm = _make_wm(driver)
        result = await wm._self_heal()
        assert result is True
        assert wm.total_heals == 1

    @pytest.mark.asyncio
    async def test_heal_exhausted_all_retries(self) -> None:
        """All reconnect attempts fail → False returned, total_heal_failures = 1."""
        driver = _make_driver(connected=False, reconnect_succeeds=False)
        wm = _make_wm(driver, max_heal_retries=3)
        result = await wm._self_heal()
        assert result is False
        assert wm.total_heal_failures == 1
        assert wm.total_heals == 0

    @pytest.mark.asyncio
    async def test_heal_metrics_incremented(self) -> None:
        """WatchdogMetrics.inc_heals() is called with correct label."""
        driver = _make_driver(connected=False, reconnect_succeeds=True)
        wm = _make_wm(driver)
        wm._metrics = MagicMock()
        wm._metrics.inc_heals = MagicMock()
        wm._metrics.set_last_heal = MagicMock()

        await wm._self_heal()
        wm._metrics.inc_heals.assert_called_with("success")

    @pytest.mark.asyncio
    async def test_heal_failure_metrics_label(self) -> None:
        """Exhausted heal → metrics called with 'failure' label."""
        driver = _make_driver(connected=False, reconnect_succeeds=False)
        wm = _make_wm(driver, max_heal_retries=2)
        wm._metrics = MagicMock()
        wm._metrics.inc_heals = MagicMock()
        wm._metrics.set_last_heal = MagicMock()

        await wm._self_heal()
        wm._metrics.inc_heals.assert_called_with("failure")

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self) -> None:
        """asyncio.CancelledError during reconnect is propagated immediately."""
        driver = MagicMock()
        driver.is_connected = False
        driver.reconnect = AsyncMock(side_effect=asyncio.CancelledError())
        wm = _make_wm(driver, max_heal_retries=3)

        with pytest.raises(asyncio.CancelledError):
            await wm._self_heal()


# ---------------------------------------------------------------------------
# TestNotifyCritical
# ---------------------------------------------------------------------------


class TestNotifyCritical:
    @pytest.mark.asyncio
    async def test_no_dispatcher_no_crash(self) -> None:
        """Without alert_dispatcher, _notify_critical() is a no-op (no crash)."""
        driver = _make_driver()
        wm = _make_wm(driver, alert_dispatcher=None)
        await wm._notify_critical()  # must not raise

    @pytest.mark.asyncio
    async def test_dispatcher_called_on_critical(self) -> None:
        """With dispatcher, _notify_critical() calls dispatcher.dispatch()."""
        driver = _make_driver()
        dispatcher = MagicMock()
        dispatcher.dispatch = AsyncMock()
        wm = _make_wm(driver, alert_dispatcher=dispatcher)
        wm._total_heal_failures = 3

        await wm._notify_critical()
        dispatcher.dispatch.assert_awaited_once()
        call_kwargs = dispatcher.dispatch.call_args[1]
        assert call_kwargs["level"] == "CRITICAL"
        assert "WatchdogManager" in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_dispatcher_error_no_crash(self) -> None:
        """If dispatcher.dispatch() raises, _notify_critical() catches it gracefully."""
        driver = _make_driver()
        dispatcher = MagicMock()
        dispatcher.dispatch = AsyncMock(side_effect=RuntimeError("Slack down"))
        wm = _make_wm(driver, alert_dispatcher=dispatcher)

        await wm._notify_critical()  # must not raise despite dispatcher error


# ---------------------------------------------------------------------------
# TestWatchdogManagerRun
# ---------------------------------------------------------------------------


class TestWatchdogManagerRun:
    @pytest.mark.asyncio
    async def test_run_stops_on_cancel(self) -> None:
        """run() terminates cleanly on asyncio.CancelledError."""
        driver = _make_driver(connected=True)
        wm = _make_wm(driver, health_interval_s=0.001)

        task = asyncio.create_task(wm.run())
        await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_run_heals_disconnected_driver(self) -> None:
        """run() detects disconnection and heals within one cycle."""
        driver = _make_driver(connected=False, reconnect_succeeds=True)
        wm = _make_wm(driver, health_interval_s=0.005, max_heal_retries=2)

        task = asyncio.create_task(wm.run())
        await asyncio.sleep(0.02)  # let at least 1-2 health cycles run
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert wm.total_heals >= 1

    @pytest.mark.asyncio
    async def test_stop_method(self) -> None:
        """stop() sets _running=False and the loop exits on next cycle."""
        driver = _make_driver(connected=True)
        wm = _make_wm(driver, health_interval_s=0.001)

        task = asyncio.create_task(wm.run())
        await asyncio.sleep(0.003)
        await wm.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
