"""
tests/test_reconnect_chaos.py
==============================
BESSAI Edge Gateway — Chaos / Resilience tests for auto-reconnect.

Simulates hostile network conditions to validate that:
  1. ModbusDriver reconnects automatically when TCP drops mid-session.
  2. The retry limit is respected (no infinite loop).
  3. Safety-critical writes succeed after a transparent reconnect.
  4. Consecutive failures escalate properly to the caller.

These tests use pytest-asyncio + unittest.mock (stdlib).
No real hardware or network required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from pymodbus.exceptions import ConnectionException, ModbusIOException
from src.drivers.modbus_driver import (
    ModbusReadError,
    UniversalDriver,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROFILE_PATH = "registry/huawei_sun2000.json"


@pytest_asyncio.fixture
async def driver() -> UniversalDriver:
    """Return a driver instance with the Huawei profile but no real connection."""
    return UniversalDriver(
        host="127.0.0.1",
        port=502,
        profile_path=PROFILE_PATH,
    )


def _make_mock_result(value: int = 1000) -> MagicMock:
    """Return a mock Modbus response with a single holding register."""
    result = MagicMock()
    result.isError.return_value = False
    result.registers = [value]
    return result


# ---------------------------------------------------------------------------
# 1. Auto-reconnect on read (single drop)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_tag_reconnects_after_single_tcp_drop(driver: UniversalDriver) -> None:
    """
    If read_holding_registers raises ConnectionException once, the driver
    reconnects and succeeds on the second attempt.
    """
    good_result = _make_mock_result(value=720)  # SOC = 720 * 0.1 = 72.0%

    with (
        patch.object(driver, "connect", new_callable=AsyncMock) as mock_connect,
        patch.object(driver, "_client") as mock_client,
    ):
        mock_client.read_holding_registers = AsyncMock(
            side_effect=[
                ConnectionException("TCP reset"),  # first call → drop
                good_result,  # second call → success after reconnect
            ]
        )
        mock_client.close = MagicMock()

        # Simulate pre-connected state
        driver._client.connected = True  # type: ignore[attr-defined]

        value = await driver.read_tag("luna_soc")

    assert value == pytest.approx(72.0, abs=0.1)
    mock_connect.assert_awaited_once()  # one reconnect attempt


# ---------------------------------------------------------------------------
# 2. Auto-reconnect on write (single drop)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_tag_reconnects_after_single_tcp_drop(driver: UniversalDriver) -> None:
    """
    If write_registers raises ConnectionException once, the driver reconnects
    and the write succeeds on the second attempt.
    """
    good_write = MagicMock()
    good_write.isError.return_value = False

    with (
        patch.object(driver, "connect", new_callable=AsyncMock) as mock_connect,
        patch.object(driver, "_client") as mock_client,
    ):
        mock_client.write_registers = AsyncMock(
            side_effect=[
                ConnectionException("Broken pipe"),
                good_write,
            ]
        )
        mock_client.close = MagicMock()
        driver._client.connected = True  # type: ignore[attr-defined]

        # Should not raise
        await driver.write_tag("luna_charge_target_soc", 80.0)

    mock_connect.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. Second attempt also fails → escalate (no infinite loop)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_tag_raises_after_reconnect_also_fails(driver: UniversalDriver) -> None:
    """
    If both the original call and the post-reconnect call fail,
    ModbusReadError must be raised — never an infinite retry loop.
    """
    with (
        patch.object(driver, "connect", new_callable=AsyncMock),
        patch.object(driver, "_client") as mock_client,
    ):
        mock_client.read_holding_registers = AsyncMock(
            side_effect=ConnectionException("Network unreachable")
        )
        mock_client.close = MagicMock()
        driver._client.connected = True  # type: ignore[attr-defined]

        with pytest.raises(ModbusReadError, match="after reconnect"):
            await driver.read_tag("luna_soc")

    # Only 2 calls: original + 1 retry (not 3, not infinite)
    assert mock_client.read_holding_registers.call_count == 2


# ---------------------------------------------------------------------------
# 4. Simultaneous drops on multiple sequential reads
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_sequential_reads_each_recover(driver: UniversalDriver) -> None:
    """
    Simulate network blip that affects every read on a cycle.
    Each read should reconnect once and succeed.
    """
    good_result = _make_mock_result(value=500)

    reconnect_calls = [0]

    async def _fake_connect() -> None:
        reconnect_calls[0] += 1

    with (
        patch.object(driver, "connect", side_effect=_fake_connect),
        patch.object(driver, "_client") as mock_client,
    ):
        # Every call: first attempt fails, second succeeds
        mock_client.read_holding_registers = AsyncMock(
            side_effect=[
                ConnectionException("Drop #1"),
                good_result,
                ConnectionException("Drop #2"),
                good_result,
                ConnectionException("Drop #3"),
                good_result,
            ]
        )
        mock_client.close = MagicMock()
        driver._client.connected = True  # type: ignore[attr-defined]

        results = []
        for tag in ["luna_soc", "internal_temperature", "luna_soc"]:
            v = await driver.read_tag(tag)
            results.append(v)

    assert len(results) == 3
    assert reconnect_calls[0] == 3  # one reconnect per dropped read


# ---------------------------------------------------------------------------
# 5. Read recovers but reconnect itself fails → ConnectionException propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconnect_itself_fails_raises_connection_exception(driver: UniversalDriver) -> None:
    """
    If _reconnect() raises ConnectionException (all retries exhausted),
    ModbusReadError should propagate with clear message.
    """

    async def _failing_connect() -> None:
        raise ConnectionException("All 3 retries exhausted")

    with (
        patch.object(driver, "connect", side_effect=_failing_connect),
        patch.object(driver, "_client") as mock_client,
    ):
        mock_client.read_holding_registers = AsyncMock(
            side_effect=ConnectionException("Initial drop")
        )
        mock_client.close = MagicMock()
        driver._client.connected = True  # type: ignore[attr-defined]

        with pytest.raises((ModbusReadError, ConnectionException)):
            await driver.read_tag("luna_soc")


# ---------------------------------------------------------------------------
# 6. Safety write: critical tag must succeed after reconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_safety_write_succeeds_after_reconnect(driver: UniversalDriver) -> None:
    """
    Safety-critical write (watchdog_heartbeat) must not be silently lost.
    After one TCP drop the write must complete.
    """
    good_write = MagicMock()
    good_write.isError.return_value = False

    with (
        patch.object(driver, "connect", new_callable=AsyncMock) as mock_connect,
        patch.object(driver, "_client") as mock_client,
    ):
        mock_client.write_registers = AsyncMock(
            side_effect=[
                ModbusIOException("Modbus IO timeout"),
                good_write,
            ]
        )
        mock_client.close = MagicMock()
        driver._client.connected = True  # type: ignore[attr-defined]

        # Must not raise
        await driver.write_tag("watchdog_heartbeat", 1)

    mock_connect.assert_awaited_once()
    assert mock_client.write_registers.call_count == 2
