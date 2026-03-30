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
from src.core.safety import SafetyGuard
from src.core.config import get_settings, settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SITE_ID", "TEST-SITE")
    monkeypatch.setenv("INVERTER_IP", "127.0.0.1")
    get_settings.cache_clear()
    settings._instance = None
    yield
    get_settings.cache_clear()
    settings._instance = None


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
# check_safety — dynamic limits (configuration injection)
# ---------------------------------------------------------------------------

class TestDynamicSafetyLimits:
    def test_custom_soc_min(self) -> None:
        guard = SafetyGuard(watchdog_interval_s=0.01, soc_min=10.0)
        assert guard.check_safety({"soc": 15.0}) is True
        assert guard.check_safety({"soc": 9.99}) is False

    def test_custom_soc_max(self) -> None:
        guard = SafetyGuard(watchdog_interval_s=0.01, soc_max=90.0)
        assert guard.check_safety({"soc": 89.0}) is True
        assert guard.check_safety({"soc": 90.1}) is False

    def test_custom_temp_max(self) -> None:
        guard = SafetyGuard(watchdog_interval_s=0.01, temp_max=50.0)
        assert guard.check_safety({"temp": 49.0}) is True
        assert guard.check_safety({"temp": 50.1}) is False


class TestPydanticSafetySettings:
    def test_settings_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SAFETY_SOC_MIN", "12.5")
        monkeypatch.setenv("SAFETY_SOC_MAX", "95.0")
        monkeypatch.setenv("SAFETY_TEMP_MAX", "40.0")
        get_settings.cache_clear()
        settings._instance = None
        
        guard = SafetyGuard(watchdog_interval_s=0.01)
        assert guard.SOC_MIN == 12.5
        assert guard.SOC_MAX == 95.0
        assert guard.TEMP_MAX == 40.0
        assert guard.check_safety({"soc": 13.0}) is True
        assert guard.check_safety({"soc": 12.0}) is False
        assert guard.check_safety({"soc": 94.0}) is True
        assert guard.check_safety({"soc": 96.0}) is False
        assert guard.check_safety({"temp": 39.0}) is True
        assert guard.check_safety({"temp": 41.0}) is False
    
    def test_settings_fallback_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        get_settings.cache_clear()
        settings._instance = None
        guard = SafetyGuard(watchdog_interval_s=0.01)
        assert guard.SOC_MIN == 5.0
        assert guard.SOC_MAX == 98.0
        assert guard.TEMP_MAX == 45.0




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
    async def test_raises_after_two_consecutive_failures(self, guard: SafetyGuard) -> None:
        """RuntimeError must be raised after 2 consecutive write failures."""
        driver = MagicMock()
        driver.write_tag = AsyncMock(side_effect=OSError("Modbus error"))

        with pytest.raises(RuntimeError, match="consecutive"):
            await guard.watchdog_loop(driver)

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self, guard: SafetyGuard) -> None:
        """CancelledError from task cancellation must not be swallowed."""
        driver = MagicMock()
        driver.write_tag = AsyncMock()

        task = asyncio.create_task(guard.watchdog_loop(driver))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_counter_wraps_at_uint16_max(self, guard: SafetyGuard) -> None:
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
