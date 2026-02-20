"""
tests/test_modbus_driver.py
============================
Unit tests for ``src.drivers.modbus_driver.UniversalDriver``.

All Modbus I/O is mocked — no real device is required.

Covers:
* Profile loading (missing file, invalid JSON, missing keys).
* UniversalDriver instantiation from a valid profile.
* read_tag: success path for UINT16 and INT32.
* read_tag: ConnectionException → ModbusReadError.
* read_tag: Modbus error response → ModbusReadError.
* read_tag: unknown tag → TagNotFoundError.
* write_tag: success path.
* write_tag: read-only tag → PermissionError.
* write_tag: ConnectionException → ModbusWriteError.
* connect: success after retries.
* connect: fails after max retries → ConnectionException.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from src.drivers.modbus_driver import (
    DriverConfigError,
    ModbusReadError,
    ModbusWriteError,
    TagNotFoundError,
    UniversalDriver,
)

# ---------------------------------------------------------------------------
# Minimal valid profile (in-memory — no disk I/O in tests)
# ---------------------------------------------------------------------------

_VALID_PROFILE: dict[str, Any] = {
    "profile_version": "1.0.0",
    "device": {"manufacturer": "Test", "model": "Mock"},
    "connection": {"byte_order": "BIG", "word_order": "BIG"},
    "registers": {
        "soc": {
            "address": 37004,
            "count": 1,
            "type": "UINT16",
            "access": "RO",
            "scale": 0.1,
        },
        "active_power": {
            "address": 32080,
            "count": 2,
            "type": "INT32",
            "access": "RO",
            "scale": 0.001,
        },
        "watchdog_heartbeat": {
            "address": 40900,
            "count": 1,
            "type": "UINT16",
            "access": "RW",
            "scale": 1,
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_driver(tmp_path: Path) -> UniversalDriver:
    """Write the valid profile to a temp file and return a driver instance."""
    profile_file = tmp_path / "test_profile.json"
    profile_file.write_text(json.dumps(_VALID_PROFILE))
    return UniversalDriver(host="127.0.0.1", port=502, profile_path=profile_file)


def _mock_register_result(words: list[int]) -> MagicMock:
    """Return a mock Modbus response with given register words."""
    result = MagicMock()
    result.isError.return_value = False
    result.registers = words
    return result


def _mock_error_result() -> MagicMock:
    """Return a mock Modbus error response."""
    result = MagicMock()
    result.isError.return_value = True
    return result


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------

class TestProfileLoading:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DriverConfigError, match="not found"):
            UniversalDriver(
                host="127.0.0.1",
                profile_path=tmp_path / "nonexistent.json",
            )

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{ not valid json }")
        with pytest.raises(DriverConfigError, match="invalid"):
            UniversalDriver(host="127.0.0.1", profile_path=bad)

    def test_missing_registers_key_raises(self, tmp_path: Path) -> None:
        incomplete = {"connection": {"byte_order": "BIG", "word_order": "BIG"}}
        f = tmp_path / "incomplete.json"
        f.write_text(json.dumps(incomplete))
        with pytest.raises(DriverConfigError, match="registers"):
            UniversalDriver(host="127.0.0.1", profile_path=f)

    def test_valid_profile_loads(self, tmp_path: Path) -> None:
        profile_file = tmp_path / "test_profile.json"
        profile_file.write_text(json.dumps(_VALID_PROFILE))
        # AsyncModbusTcpClient requires a running loop in pymodbus 3.12+
        async def _inner() -> None:
            driver = await _make_driver(tmp_path)
            assert "soc" in driver._registers
        asyncio.run(_inner())


# ---------------------------------------------------------------------------
# read_tag
# ---------------------------------------------------------------------------

class TestReadTag:
    @pytest.mark.asyncio
    async def test_read_uint16_success(self, tmp_path: Path) -> None:
        driver = await _make_driver(tmp_path)
        # 850 raw → 850 * 0.1 = 85.0 %
        driver._client.read_holding_registers = AsyncMock(
            return_value=_mock_register_result([850])
        )
        value = await driver.read_tag("soc")
        assert pytest.approx(value, rel=1e-3) == 85.0

    @pytest.mark.asyncio
    async def test_read_int32_success(self, tmp_path: Path) -> None:
        driver = await _make_driver(tmp_path)
        # INT32 of 120000 raw → 120000 * 0.001 = 120.0 kW
        # Encoded as two 16-bit words: 0x0001D4C0 → [0x0001, 0xD4C0]
        driver._client.read_holding_registers = AsyncMock(
            return_value=_mock_register_result([0x0001, 0xD4C0])
        )
        value = await driver.read_tag("active_power")
        assert isinstance(value, float)

    @pytest.mark.asyncio
    async def test_unknown_tag_raises(self, tmp_path: Path) -> None:
        driver = await _make_driver(tmp_path)
        with pytest.raises(TagNotFoundError, match="undefined_tag"):
            await driver.read_tag("undefined_tag")

    @pytest.mark.asyncio
    async def test_connection_error_raises_modbus_read_error(
        self, tmp_path: Path
    ) -> None:
        from pymodbus.exceptions import ConnectionException

        driver = await _make_driver(tmp_path)
        driver._client.read_holding_registers = AsyncMock(
            side_effect=ConnectionException("timeout")
        )
        with pytest.raises(ModbusReadError):
            await driver.read_tag("soc")

    @pytest.mark.asyncio
    async def test_error_response_raises_modbus_read_error(
        self, tmp_path: Path
    ) -> None:
        driver = await _make_driver(tmp_path)
        driver._client.read_holding_registers = AsyncMock(
            return_value=_mock_error_result()
        )
        with pytest.raises(ModbusReadError):
            await driver.read_tag("soc")


# ---------------------------------------------------------------------------
# write_tag
# ---------------------------------------------------------------------------

class TestWriteTag:
    @pytest.mark.asyncio
    async def test_write_rw_tag_success(self, tmp_path: Path) -> None:
        driver = await _make_driver(tmp_path)
        write_result = MagicMock()
        write_result.isError.return_value = False
        driver._client.write_registers = AsyncMock(return_value=write_result)
        # Should not raise
        await driver.write_tag("watchdog_heartbeat", 42.0)
        driver._client.write_registers.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_ro_tag_raises_permission_error(
        self, tmp_path: Path
    ) -> None:
        driver = await _make_driver(tmp_path)
        with pytest.raises(PermissionError, match="read-only"):
            await driver.write_tag("soc", 50.0)

    @pytest.mark.asyncio
    async def test_write_connection_error_raises_modbus_write_error(
        self, tmp_path: Path
    ) -> None:
        from pymodbus.exceptions import ConnectionException

        driver = await _make_driver(tmp_path)
        driver._client.write_registers = AsyncMock(
            side_effect=ConnectionException("broken pipe")
        )
        with pytest.raises(ModbusWriteError):
            await driver.write_tag("watchdog_heartbeat", 1.0)


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------

class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_success_on_first_try(self, tmp_path: Path) -> None:
        driver = await _make_driver(tmp_path)
        driver._client.connect = AsyncMock()
        type(driver._client).connected = PropertyMock(return_value=True)
        await driver.connect()
        driver._client.connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_retries_then_succeeds(self, tmp_path: Path) -> None:
        driver = await _make_driver(tmp_path)
        call_count = 0

        async def flaky_connect() -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("refused")
            # 3rd call succeeds (no exception)

        driver._client.connect = flaky_connect
        # connected always returns True — the check only runs after a successful connect()
        type(driver._client).connected = PropertyMock(return_value=True)
        await asyncio.wait_for(driver.connect(), timeout=30.0)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_connect_exhausts_retries(self, tmp_path: Path) -> None:
        from pymodbus.exceptions import ConnectionException

        driver = await _make_driver(tmp_path)
        driver._client.connect = AsyncMock(side_effect=OSError("refused"))
        type(driver._client).connected = PropertyMock(return_value=False)

        with pytest.raises(ConnectionException):
            await asyncio.wait_for(driver.connect(), timeout=10.0)
