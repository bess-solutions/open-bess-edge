# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_sungrow_driver.py
============================
Unit tests for Sungrow PowerTitan 1500V Utility BESS Driver.
All tests use mock Modbus registers — zero physical hardware required.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from src.drivers.sungrow_driver import (
    SungrowDriver,
    SungrowTelemetry,
    SungrowWorkingMode,
    SungrowAlarmState,
)


def _make_sungrow_registers():
    # 22 registers starting at 5000:
    # 5000: DC Voltage = 13500 (1350.0 V)
    # 5001: DC Current = -1850 (-185.0 A discharging) -> 0xFF46
    # 5002-5003: Active Power = -25000 (-2500.0 kW) -> 0xFFFF, 0x9E58
    # 5004-5005: Reactive Power = 2000 (200.0 kVAR) -> 0x0000, 0x07D0
    # 5006: SOC = 750 (75.0%)
    # 5007: SOH = 990 (99.0%)
    # 5008: Max Cell Temp = 285 (28.5 °C)
    # 5009: Min Cell Temp = 260 (26.0 °C)
    # 5010: Max Cell Volt = 3350 mV
    # 5011: Min Cell Volt = 3315 mV
    # 5012-5013: Cycle count = 450 -> 0x0000, 0x01C2
    # 5014-5015: Rated capacity = 27520 (2752.0 kWh) -> 0x0000, 0x6B80
    # 5016: Liquid Pump = 1 (Running)
    # 5017: HVAC status = 1 (Cooling)
    # 5018-5019: Alarm code = 0 (No alarms)
    # 5020: Working mode = 2 (DISCHARGING)
    return [
        13500,
        0xFF46,
        0xFFFF, 0x9E58,
        0x0000, 0x07D0,
        750,
        990,
        285,
        260,
        3350,
        3315,
        0x0000, 0x01C2,
        0x0000, 0x6B80,
        1,
        1,
        0x0000, 0x0000,
        2,
    ]


def test_sungrow_telemetry_properties():
    tel = SungrowTelemetry(
        soc_pct=75.0,
        soh_pct=99.0,
        active_power_kw=-2500.0,
        reactive_power_kvar=200.0,
        dc_voltage_v=1350.0,
        dc_current_a=-185.0,
        max_cell_temp_c=28.5,
        min_cell_temp_c=26.0,
        max_cell_volt_mv=3350,
        min_cell_volt_mv=3315,
        cycle_count=450,
        capacity_kwh=2752.0,
        liquid_pump_running=True,
        hvac_status=1,
        alarm_code=0,
        working_mode=SungrowWorkingMode.DISCHARGING,
    )

    assert tel.is_discharging
    assert not tel.is_charging
    assert not tel.is_idle
    assert tel.delta_cell_temp == 2.5
    assert tel.delta_cell_volt_mv == 35
    assert len(tel.active_alarms) == 0

    d = tel.to_dict()
    assert d["soc_pct"] == 75.0
    assert d["dc_voltage_v"] == 1350.0
    assert d["active_power_kw"] == -2500.0
    assert d["liquid_pump_running"] is True


def test_sungrow_alarm_bitmap_decoding():
    # Test bitfield decoding: Over temp (bit 0) + Liquid leak (bit 4)
    code = SungrowAlarmState.OVER_TEMP | SungrowAlarmState.LIQUID_LEAK
    alarms = SungrowAlarmState.get_active_alarms(code)
    assert "OVER_TEMPERATURE" in alarms
    assert "LIQUID_COOLING_LEAKAGE" in alarms
    assert len(alarms) == 2


@pytest.mark.asyncio
async def test_sungrow_driver_read_telemetry_mock():
    driver = SungrowDriver(host="192.168.1.150", port=502, slave_id=1)
    
    mock_client = AsyncMock()
    mock_res = MagicMock()
    mock_res.isError.return_value = False
    mock_res.registers = _make_sungrow_registers()
    mock_client.read_holding_registers.return_value = mock_res
    mock_client.connect.return_value = True

    driver._client = mock_client
    driver._connected = True

    tel = await driver.read_telemetry()

    assert tel.soc_pct == 75.0
    assert tel.soh_pct == 99.0
    assert tel.dc_voltage_v == 1350.0
    assert tel.active_power_kw == -2500.0
    assert tel.reactive_power_kvar == 200.0
    assert tel.max_cell_temp_c == 28.5
    assert tel.min_cell_temp_c == 26.0
    assert tel.max_cell_volt_mv == 3350
    assert tel.min_cell_volt_mv == 3315
    assert tel.cycle_count == 450
    assert tel.capacity_kwh == 2752.0
    assert tel.liquid_pump_running is True
    assert tel.working_mode == SungrowWorkingMode.DISCHARGING


@pytest.mark.asyncio
async def test_sungrow_driver_control_commands():
    driver = SungrowDriver(host="192.168.1.150", port=502, slave_id=1)
    
    mock_client = AsyncMock()
    mock_write_res = MagicMock()
    mock_write_res.isError.return_value = False
    mock_client.write_registers.return_value = mock_write_res
    mock_client.write_register.return_value = mock_write_res

    driver._client = mock_client
    driver._connected = True

    # Test Active Power Setpoint (e.g. -2000 kW discharge)
    success = await driver.set_active_power(-2000.0)
    assert success is True
    assert mock_client.write_registers.called

    # Test Reactive Power Setpoint
    success_q = await driver.set_reactive_power(500.0)
    assert success_q is True

    # Test Emergency Stop
    success_trip = await driver.emergency_stop()
    assert success_trip is True
    assert mock_client.write_register.called
