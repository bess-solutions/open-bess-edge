"""
tests/test_luna2000_driver_async.py
======================================
Async tests for LUNADriver: read_telemetry, set_mode,
set_charge_target_soc, __aenter__ / __aexit__ lifecycle.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.drivers.luna2000_driver import BatteryMode, LUNADriver, LUNATelemetry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_register_mock(values: dict[int, list[int]]) -> MagicMock:
    mock = MagicMock()

    def _read(address, count, slave=3):
        result = MagicMock()
        result.isError.return_value = False
        result.registers = values.get(address, [0] * count)
        return result

    mock.read_holding_registers.side_effect = _read
    mock.write_register.return_value = MagicMock(isError=lambda: False)
    mock.connect.return_value = True
    return mock


# Register map for a LUNA2000 at 60% SOC, discharging 10 kW
_LUNA_REGS: dict[int, list[int]] = {
    37752: [0x0106],       # temp = 262 → 26.2°C
    37760: [600],          # SOC = 600 → 60.0%
    37761: [980],          # SOH = 980 → 98.0%
    37762: [123],          # cycles
    37758: [0, 10000],     # capacity = 10.0 kWh
    37765: [0xFFFF, 0xD8F0],  # power = -10000 → -10.0 kW
    37800: [4800],         # voltage = 480 V
    37801: [0xFFD2],       # current = -46 → -4.6 A
    47086: [0],            # mode = MAX_SELF_CONSUMPTION
}


def _driver_with_mock() -> tuple[LUNADriver, MagicMock]:
    drv = LUNADriver(host="127.0.0.1", slave_id=3)
    mock_client = _make_register_mock(_LUNA_REGS)
    drv._client = mock_client
    return drv, mock_client


# ---------------------------------------------------------------------------
# read_telemetry
# ---------------------------------------------------------------------------


class TestReadTelemetry:
    @pytest.mark.asyncio
    async def test_reads_soc_60_percent(self):
        drv, _ = _driver_with_mock()
        tel = await drv.read_telemetry()
        assert tel.soc_pct == pytest.approx(60.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_reads_temperature(self):
        drv, _ = _driver_with_mock()
        tel = await drv.read_telemetry()
        assert tel.temperature_c == pytest.approx(26.2, abs=0.01)

    @pytest.mark.asyncio
    async def test_reads_negative_power_discharging(self):
        drv, _ = _driver_with_mock()
        tel = await drv.read_telemetry()
        assert tel.power_kw < 0
        assert tel.is_discharging

    @pytest.mark.asyncio
    async def test_reads_cycle_count(self):
        drv, _ = _driver_with_mock()
        tel = await drv.read_telemetry()
        assert tel.cycle_count == 123

    @pytest.mark.asyncio
    async def test_reads_capacity_kwh(self):
        drv, _ = _driver_with_mock()
        tel = await drv.read_telemetry()
        assert tel.capacity_kwh == pytest.approx(10.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_working_mode_resolved_to_enum(self):
        drv, _ = _driver_with_mock()
        tel = await drv.read_telemetry()
        assert tel.working_mode == BatteryMode.MAX_SELF_CONSUMPTION

    @pytest.mark.asyncio
    async def test_returns_luna_telemetry_instance(self):
        drv, _ = _driver_with_mock()
        tel = await drv.read_telemetry()
        assert isinstance(tel, LUNATelemetry)


# ---------------------------------------------------------------------------
# set_mode
# ---------------------------------------------------------------------------


class TestSetMode:
    @pytest.mark.asyncio
    async def test_set_mode_writes_correct_register(self):
        drv, mock_client = _driver_with_mock()
        mock_client.write_register.return_value = MagicMock(isError=lambda: False)

        await drv.set_mode(BatteryMode.TIME_OF_USE)

        # REG_LUNA_MODE = 47086
        mock_client.write_register.assert_called_once_with(
            address=47086, value=int(BatteryMode.TIME_OF_USE), slave=3
        )

    @pytest.mark.asyncio
    async def test_set_mode_fully_charged(self):
        drv, mock_client = _driver_with_mock()
        await drv.set_mode(BatteryMode.FULLY_CHARGED)
        mock_client.write_register.assert_called_once_with(
            address=47086, value=1, slave=3
        )

    @pytest.mark.asyncio
    async def test_set_mode_remote_dispatch(self):
        drv, mock_client = _driver_with_mock()
        await drv.set_mode(BatteryMode.REMOTE_DISPATCH)
        mock_client.write_register.assert_called_once_with(
            address=47086, value=3, slave=3
        )


# ---------------------------------------------------------------------------
# set_charge_target_soc
# ---------------------------------------------------------------------------


class TestSetChargeTargetSOC:
    @pytest.mark.asyncio
    async def test_valid_target_80_pct(self):
        drv, mock_client = _driver_with_mock()
        await drv.set_charge_target_soc(80.0)
        # REG_LUNA_TARGET_SOC = 47087 (registro contiguo al modo 47086)
        mock_client.write_register.assert_called_once_with(
            address=47087, value=800, slave=3
        )

    @pytest.mark.asyncio
    async def test_valid_target_100_pct(self):
        drv, mock_client = _driver_with_mock()
        await drv.set_charge_target_soc(100.0)
        mock_client.write_register.assert_called_once_with(
            address=47087, value=1000, slave=3
        )

    @pytest.mark.asyncio
    async def test_valid_target_0_pct(self):
        drv, mock_client = _driver_with_mock()
        await drv.set_charge_target_soc(0.0)
        mock_client.write_register.assert_called_once_with(
            address=47087, value=0, slave=3
        )

    @pytest.mark.asyncio
    async def test_raises_on_negative_target(self):
        drv, _ = _driver_with_mock()
        with pytest.raises(ValueError, match="0–100"):
            await drv.set_charge_target_soc(-1.0)

    @pytest.mark.asyncio
    async def test_raises_on_target_above_100(self):
        drv, _ = _driver_with_mock()
        with pytest.raises(ValueError, match="0–100"):
            await drv.set_charge_target_soc(101.0)


# ---------------------------------------------------------------------------
# __aenter__ / __aexit__
# ---------------------------------------------------------------------------


class TestLUNADriverLifecycle:
    @pytest.mark.asyncio
    async def test_aenter_sets_client_and_connects(self):
        mock_client = _make_register_mock(_LUNA_REGS)
        drv = LUNADriver(host="127.0.0.1", slave_id=3)

        with patch.object(drv, "_make_client", return_value=mock_client):
            result = await drv.__aenter__()

        assert result is drv
        mock_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_aenter_raises_on_failed_connect(self):
        mock_client = _make_register_mock({})
        mock_client.connect.return_value = False
        drv = LUNADriver(host="10.0.0.1", slave_id=3)

        with patch.object(drv, "_make_client", return_value=mock_client):
            with pytest.raises(ConnectionError):
                await drv.__aenter__()

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        drv, mock_client = _driver_with_mock()
        await drv.__aexit__(None, None, None)
        mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_noop_when_no_client(self):
        drv = LUNADriver(host="127.0.0.1")
        drv._client = None
        await drv.__aexit__(None, None, None)  # should not raise


# ---------------------------------------------------------------------------
# _read_regs error handling
# ---------------------------------------------------------------------------


class TestReadRegsErrorHandling:
    def test_read_regs_raises_on_modbus_error(self):
        drv, mock_client = _driver_with_mock()
        error_result = MagicMock()
        error_result.isError = MagicMock(return_value=True)
        # side_effect tiene prioridad — lo limpiamos para que return_value funcione
        mock_client.read_holding_registers.side_effect = None
        mock_client.read_holding_registers.return_value = error_result

        with pytest.raises(OSError, match="Modbus read error"):
            drv._read_regs(37760, 1)

    def test_write_reg_raises_on_modbus_error(self):
        drv, mock_client = _driver_with_mock()
        error_result = MagicMock()
        error_result.isError = MagicMock(return_value=True)
        mock_client.write_register.side_effect = None
        mock_client.write_register.return_value = error_result

        with pytest.raises(OSError, match="Modbus write error"):
            drv._write_reg(47086, 0)
