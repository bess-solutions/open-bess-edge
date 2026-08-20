# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

import pytest
from src.core.grid_forming_vsm import GridFormingVSM, VSMConfig


def test_vsm_nominal_steady_state():
    vsm = GridFormingVSM(VSMConfig(rated_power_mw=50.0))
    res = vsm.compute_dispatch(current_freq_hz=50.0, rocof_hz_per_sec=0.0)
    assert res.target_power_mw == 0.0
    assert res.p_inertia_mw == 0.0
    assert res.p_droop_mw == 0.0
    assert res.is_ffr_triggered is False


def test_vsm_underfrequency_inertia_injection():
    # Frequency drop: 49.5 Hz, RoCoF = -1.2 Hz/s
    vsm = GridFormingVSM(VSMConfig(rated_power_mw=100.0, inertia_constant_h=5.0))
    res = vsm.compute_dispatch(current_freq_hz=49.5, rocof_hz_per_sec=-1.2)
    # Inertia must inject positive active power (+MW)
    assert res.p_inertia_mw > 0.0
    assert res.p_droop_mw > 0.0
    assert res.is_ffr_triggered is True
    assert res.target_power_mw > 20.0
