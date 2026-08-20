# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

import pytest
from src.core.liquid_cooling_manager import LiquidCoolingManager, CoolingState


def test_liquid_cooling_standby_cool_conditions():
    mgr = LiquidCoolingManager()
    res = mgr.compute_thermal_dispatch(max_cell_temp_c=21.0, ambient_temp_c=18.0, current_c_rate=0.1)
    assert res.cooling_state == CoolingState.STANDBY
    assert res.estimated_aux_power_kw < 0.5
    assert res.is_derate_required is False


def test_liquid_cooling_atacama_high_ambient_activation():
    mgr = LiquidCoolingManager()
    # Atacama 38°C ambient, discharging at 0.8C
    res = mgr.compute_thermal_dispatch(max_cell_temp_c=31.5, ambient_temp_c=38.0, current_c_rate=0.8)
    assert res.cooling_state == CoolingState.CHILLER_ACTIVE
    assert res.coolant_flow_lpm == 90.0
    assert res.target_chiller_temp_c == 22.0


def test_liquid_cooling_emergency_thermal_derate():
    mgr = LiquidCoolingManager()
    # Cell temp hits 39.0°C (above 38°C threshold)
    res = mgr.compute_thermal_dispatch(max_cell_temp_c=39.0, ambient_temp_c=42.0, current_c_rate=1.0)
    assert res.cooling_state == CoolingState.EMERGENCY_COOLING
    assert res.is_derate_required is True
    assert res.max_charge_c_rate == 0.2
