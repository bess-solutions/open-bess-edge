# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

import pytest
from unittest.mock import MagicMock, AsyncMock
from src.drivers.ingeteam_driver import IngeteamDriver, IngeteamTelemetry, IngeteamOperatingState


def test_ingeteam_telemetry_properties():
    tel = IngeteamTelemetry(
        status=IngeteamOperatingState.RUNNING,
        active_power_kw=-2450.0,
        reactive_power_kvar=150.0,
        grid_frequency_hz=50.02,
        dc_voltage_v=1420.0,
        dc_current_a=-172.5,
        soc_pct=78.5,
        soh_pct=99.2,
        cabinet_temp_c=29.0,
        igbt_temp_c=45.5,
        alarm_code=0,
    )
    assert tel.is_discharging is True
    assert tel.is_charging is False
    d = tel.to_dict()
    assert d["status"] == "RUNNING"
    assert d["grid_frequency_hz"] == 50.02


@pytest.mark.asyncio
async def test_ingeteam_read_telemetry_mock():
    driver = IngeteamDriver()
    mock_client = AsyncMock()
    mock_res = MagicMock()
    mock_res.isError.return_value = False
    # 14 registers
    # Power -2450.0 kW -> -245000 -> 0xFFFC, 0x62C8
    # Reactive 150.0 kVAR -> 15000 -> 0x0000, 0x3A98
    mock_res.registers = [
        2, 0, 0, 0xFFFC, 0x62C8, 0x0000, 0x3A98, 5002, 14200, 0xFF53, 785, 992, 290, 455
    ]
    mock_client.read_holding_registers.return_value = mock_res
    driver._client = mock_client
    driver._connected = True

    tel = await driver.read_telemetry()
    assert tel.status == IngeteamOperatingState.RUNNING
    assert tel.dc_voltage_v == 1420.0
    assert tel.soc_pct == 78.5
    assert tel.grid_frequency_hz == 50.02
