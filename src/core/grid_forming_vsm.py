# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/grid_forming_vsm.py
=============================
BESSAI Edge Gateway — Virtual Synchronous Machine (VSM) Grid-Forming Controller.

Implements synthetic inertia (H=3.5s to 6.0s), sub-500ms Fast Frequency Response (FFR),
and primary frequency droop control calibrated to Chilean Grid Code NTSyCS.
"""

from __future__ import annotations
import math
from dataclasses import dataclass

__all__ = ["GridFormingVSM", "VSMConfig", "VSMDispatchResponse"]


@dataclass
class VSMConfig:
    inertia_constant_h: float = 4.5         # Inertia constant in seconds (3.0 - 6.0s)
    droop_r_pct: float = 4.0               # Droop R in % (3.0 - 5.0% under NTSyCS)
    nominal_freq_hz: float = 50.0          # SEN nominal frequency (50.0 Hz)
    rated_power_mw: float = 100.0          # BESS rated active power
    max_ffr_power_mw: float = 100.0        # Max FFR capacity
    deadband_hz: float = 0.02              # NTSyCS deadband (+/- 0.02 Hz)


@dataclass
class VSMDispatchResponse:
    target_power_mw: float
    p_inertia_mw: float
    p_droop_mw: float
    rocof_hz_per_sec: float
    freq_deviation_hz: float
    is_ffr_triggered: bool


class GridFormingVSM:
    """Virtual Synchronous Machine Controller for sub-500ms grid stabilization."""

    def __init__(self, config: VSMConfig | None = None):
        self.config = config or VSMConfig()

    def compute_dispatch(
        self,
        current_freq_hz: float,
        rocof_hz_per_sec: float,
        base_power_mw: float = 0.0,
    ) -> VSMDispatchResponse:
        f_0 = self.config.nominal_freq_hz
        delta_f = current_freq_hz - f_0

        # Synthetic Inertia component: -2 * H * S_base * (df/dt) / f_0
        p_inertia = -2.0 * self.config.inertia_constant_h * self.config.rated_power_mw * (rocof_hz_per_sec / f_0)

        # Primary Droop component with deadband
        if abs(delta_f) > self.config.deadband_hz:
            eff_delta_f = delta_f - math.copysign(self.config.deadband_hz, delta_f)
            droop_factor = 100.0 / self.config.droop_r_pct
            p_droop = -(droop_factor * (eff_delta_f / f_0) * self.config.rated_power_mw)
        else:
            p_droop = 0.0

        total_vsm_power = base_power_mw + p_inertia + p_droop
        clipped_power = max(-self.config.rated_power_mw, min(self.config.rated_power_mw, total_vsm_power))

        is_ffr = abs(rocof_hz_per_sec) > 0.5 or abs(delta_f) > 0.2

        return VSMDispatchResponse(
            target_power_mw=round(clipped_power, 3),
            p_inertia_mw=round(p_inertia, 3),
            p_droop_mw=round(p_droop, 3),
            rocof_hz_per_sec=round(rocof_hz_per_sec, 4),
            freq_deviation_hz=round(delta_f, 4),
            is_ffr_triggered=is_ffr,
        )
