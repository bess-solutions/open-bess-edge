# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

import pytest
from unittest.mock import MagicMock, AsyncMock
from src.drivers.catl_enerone_driver import CATLEnerOneDriver, CATLTelemetry, CATLBmsState


def test_catl_telemetry_properties():
    tel = CATLTelemetry(
        soc_pct=82.0,
        soh_pct=99.5,
        active_power_kw=-1500.0,
        dc_voltage_v=1280.0,
        dc_current_a=-117.2,
        max_cell_temp_c=26.5,
        min_cell_temp_c=24.5,
        max_cell_volt_mv=3340,
        min_cell_volt_mv=3320,
        insulation_kohm=5000,
        active_racks=8,
        coolant_in_c=22.0,
        coolant_out_c=25.0,
        coolant_pressure_bar=1.5,
        alarm_code=0,
    )
    assert tel.delta_temp_coolant == 3.0
    assert tel.is_thermal_balanced is True
    d = tel.to_dict()
    assert d["active_racks"] == 8
    assert d["coolant_pressure_bar"] == 1.5


@pytest.mark.asyncio
async def test_catl_read_telemetry_mock():
    driver = CATLEnerOneDriver()
    mock_client = AsyncMock()
    mock_res = MagicMock()
    mock_res.isError.return_value = False
    # 17 registers
    mock_res.registers = [
        12800, 0xFEF0, 0xFFFF, 0xC568, 820, 995, 265, 245, 3340, 3320, 5000, 8, 220, 250, 150, 0, 0
    ]
    mock_client.read_holding_registers.return_value = mock_res
    driver._client = mock_client
    driver._connected = True

    tel = await driver.read_telemetry()
    assert tel.dc_voltage_v == 1280.0
    assert tel.soc_pct == 82.0
    assert tel.active_racks == 8
    assert tel.coolant_pressure_bar == 1.5
