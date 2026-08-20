# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/liquid_cooling_manager.py
===================================
BESSAI Edge Gateway — Smart Liquid Cooling & HVAC Optimization Engine.

Optimizes chiller staging and coolant flow rate for extreme desert environments
(Atacama ambient temps up to 45°C) to prevent Arrhenius degradation while minimizing
parasitic auxiliary consumption in peak CMg hours.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum

__all__ = ["LiquidCoolingManager", "CoolingState", "ThermalDispatchDecision"]


class CoolingState(IntEnum):
    STANDBY = 0
    NATURAL_CONVECTION = 1
    LOW_PUMP = 2
    HIGH_PUMP = 3
    CHILLER_ACTIVE = 4
    EMERGENCY_COOLING = 5


@dataclass
class ThermalDispatchDecision:
    cooling_state: CoolingState
    coolant_flow_lpm: float
    target_chiller_temp_c: float
    estimated_aux_power_kw: float
    is_derate_required: bool
    max_charge_c_rate: float


class LiquidCoolingManager:
    """Intelligent Liquid Cooling Staging for LFP Utility Containers."""

    def __init__(self, target_cell_temp_c: float = 25.0, high_temp_alarm_c: float = 38.0):
        self.target_cell_temp_c = target_cell_temp_c
        self.high_temp_alarm_c = high_temp_alarm_c

    def compute_thermal_dispatch(
        self,
        max_cell_temp_c: float,
        ambient_temp_c: float,
        current_c_rate: float,
    ) -> ThermalDispatchDecision:
        # 1. Extreme Critical Thermal Trip Prevention
        if max_cell_temp_c >= self.high_temp_alarm_c:
            return ThermalDispatchDecision(
                cooling_state=CoolingState.EMERGENCY_COOLING,
                coolant_flow_lpm=120.0,
                target_chiller_temp_c=18.0,
                estimated_aux_power_kw=15.5,
                is_derate_required=True,
                max_charge_c_rate=0.2,
            )

        # 2. Heavy Duty Chiller Operation (Atacama High Ambient / High C-Rate)
        if max_cell_temp_c > 30.0 or (ambient_temp_c > 35.0 and current_c_rate > 0.5):
            return ThermalDispatchDecision(
                cooling_state=CoolingState.CHILLER_ACTIVE,
                coolant_flow_lpm=90.0,
                target_chiller_temp_c=22.0,
                estimated_aux_power_kw=8.2,
                is_derate_required=False,
                max_charge_c_rate=1.0,
            )

        # 3. Moderate Pumping (Normal Operation 24°C - 30°C)
        if max_cell_temp_c > 24.0:
            return ThermalDispatchDecision(
                cooling_state=CoolingState.LOW_PUMP,
                coolant_flow_lpm=45.0,
                target_chiller_temp_c=25.0,
                estimated_aux_power_kw=1.8,
                is_derate_required=False,
                max_charge_c_rate=1.0,
            )

        # 4. Low Power Standby / Natural Convection
        return ThermalDispatchDecision(
            cooling_state=CoolingState.STANDBY,
            coolant_flow_lpm=0.0,
            target_chiller_temp_c=25.0,
            estimated_aux_power_kw=0.1,
            is_derate_required=False,
            max_charge_c_rate=1.0,
        )
