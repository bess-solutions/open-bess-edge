"""
tests/test_safety.py
=====================
Unit tests for ``src.core.safety.SafetyGuard``.

Covers:
* SOC below minimum → blocked.
* SOC above maximum → blocked.
* Temperature above maximum → blocked.
* All values in range → allowed.
* Missing keys are skipped (partial telemetry).
* Watchdog loop increments counter and calls write_tag.
* Watchdog loop raises RuntimeError after 2 consecutive write failures.
* Watchdog loop handles CancelledError cleanly.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.core.safety import SafetyGuard

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def guard() -> SafetyGuard:
    """Return a SafetyGuard with 0.01 s watchdog interval for fast tests."""
    return SafetyGuard(watchdog_interval_s=0.01)


# ---------------------------------------------------------------------------
# check_safety — happy path
# ---------------------------------------------------------------------------

class TestCheckSafetyPass:
    def test_nominal_values(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"soc": 50.0, "temp": 30.0}) is True

    def test_soc_at_lower_boundary(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"soc": 5.0}) is True

    def test_soc_at_upper_boundary(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"soc": 98.0}) is True

    def test_temp_at_boundary(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"temp": 45.0}) is True

    def test_empty_telemetry(self, guard: SafetyGuard) -> None:
        """Empty dict — nothing to check, must pass."""
        assert guard.check_safety({}) is True

    def test_unknown_keys_ignored(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"voltage": 400.0}) is True


# ---------------------------------------------------------------------------
# check_safety — blocked conditions
# ---------------------------------------------------------------------------

class TestCheckSafetyBlock:
    def test_soc_below_min(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"soc": 4.99}) is False

    def test_soc_above_max(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"soc": 98.01}) is False

    def test_temp_above_max(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"temp": 45.01}) is False

    def test_soc_ok_but_temp_bad(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"soc": 50.0, "temp": 50.0}) is False

    def test_soc_bad_temp_ok(self, guard: SafetyGuard) -> None:
        assert guard.check_safety({"soc": 1.0, "temp": 30.0}) is False


# ---------------------------------------------------------------------------
# watchdog_loop
# ---------------------------------------------------------------------------

class TestWatchdogLoop:
    @pytest.mark.asyncio
    async def test_counter_increments(self, guard: SafetyGuard) -> None:
        """Watchdog writes an increasing counter to write_tag."""
        driver = MagicMock()
        driver.write_tag = AsyncMock()

        task = asyncio.create_task(guard.watchdog_loop(driver))
        await asyncio.sleep(0.08)  # allow ~5-8 ticks at 0.01 s interval
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert driver.write_tag.call_count >= 3
        # All calls target the heartbeat tag
        for c in driver.write_tag.call_args_list:
            assert c.args[0] == "watchdog_heartbeat"

    @pytest.mark.asyncio
    async def test_raises_after_two_consecutive_failures(
        self, guard: SafetyGuard
    ) -> None:
        """RuntimeError must be raised after 2 consecutive write failures."""
        driver = MagicMock()
        driver.write_tag = AsyncMock(side_effect=OSError("Modbus error"))

        with pytest.raises(RuntimeError, match="consecutive"):
            await guard.watchdog_loop(driver)

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(
        self, guard: SafetyGuard
    ) -> None:
        """CancelledError from task cancellation must not be swallowed."""
        driver = MagicMock()
        driver.write_tag = AsyncMock()

        task = asyncio.create_task(guard.watchdog_loop(driver))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_counter_wraps_at_uint16_max(
        self, guard: SafetyGuard
    ) -> None:
        """Counter must wrap to 0 after reaching 65535."""
        guard._heartbeat_counter = 65534
        driver = MagicMock()
        written: list[float] = []

        async def capture_write(tag: str, value: float) -> None:
            written.append(value)

        driver.write_tag = capture_write
        task = asyncio.create_task(guard.watchdog_loop(driver))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Sequence must pass through 65535 and then wrap to 0
        assert 65535 in written
        assert 0 in written
