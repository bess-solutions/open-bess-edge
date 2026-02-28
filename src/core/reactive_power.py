# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/reactive_power.py
===========================
Reactive Power Controller — NTSyCS Cap. 4.4 (GAP-011).

Implements Q/V droop control for BESS units, enabling reactive power
injection/absorption to support voltage at the point of common coupling.

NTSyCS Cap. 4.4 Requirements
------------------------------
* BESS ≥ 1 MW must provide reactive power support within ±0.9 pf range.
* Q/V droop: ΔQ = -(ΔV / (droop% · Vnom)) · Qmax
* Response: < 1 cycle (< 20 ms at 50 Hz)
* Qmax: at least 44 % of Pnom (0.9 pf → tan(arccos(0.9)) ≈ 0.484)

Usage::

    qv = ReactiveController(v_nominal_pu=1.0, droop_pct=5.0, q_max_kvar=484.0)
    q_cmd = qv.compute_q_setpoint(v_pu=0.96)
    # q_cmd > 0 → inject reactive (undervoltage support)
"""

from __future__ import annotations

import math

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# NTSyCS minimum: 0.9 pf → Q/P = tan(arccos(0.9))
_MIN_PF: float = 0.9
_Q_P_RATIO_MIN: float = math.tan(math.acos(_MIN_PF))  # ≈ 0.4843


class ReactiveController:
    """
    Q/V droop reactive power controller.

    Parameters
    ----------
    v_nominal_pu:
        Nominal voltage at PCC in per-unit (default 1.0 pu).
    v_deadband_pu:
        Voltage deadband in pu (default 0.01 pu = ±1%).
    droop_pct:
        Q/V droop in % (default 5 %).
    q_max_kvar:
        Maximum reactive power capacity in kVAr.
    p_nom_kw:
        Nominal active power in kW (used to verify NTSyCS min Q/P ratio).
    """

    def __init__(
        self,
        v_nominal_pu: float = 1.0,
        v_deadband_pu: float = 0.01,
        droop_pct: float = 5.0,
        q_max_kvar: float = 484.0,
        p_nom_kw: float = 1000.0,
    ) -> None:
        if q_max_kvar <= 0:
            raise ValueError(f"q_max_kvar must be positive, got {q_max_kvar}")
        self._v_nom = v_nominal_pu
        self._deadband = v_deadband_pu
        self._droop_pct = droop_pct
        self._q_max = q_max_kvar
        self._p_nom = p_nom_kw

        q_p_ratio = q_max_kvar / p_nom_kw if p_nom_kw > 0 else 0
        if q_p_ratio < _Q_P_RATIO_MIN:
            log.warning(
                "reactive.q_p_ratio_below_ntsycs",
                q_p_ratio=round(q_p_ratio, 4),
                ntsycs_min=round(_Q_P_RATIO_MIN, 4),
                norm_ref="NTSyCS Cap. 4.4",
            )

        log.info(
            "reactive_controller.initialized",
            v_nom=v_nominal_pu, deadband=v_deadband_pu,
            droop_pct=droop_pct, q_max_kvar=q_max_kvar,
            norm_ref="NTSyCS Cap. 4.4",
        )

    def compute_q_setpoint(self, v_pu: float) -> float:
        """
        Compute the Q setpoint for the given measured voltage.

        Parameters
        ----------
        v_pu:
            Measured voltage at PCC in per-unit.

        Returns
        -------
        float
            Q setpoint in kVAr.
            Positive = inject reactive (undervoltage support).
            Negative = absorb reactive (overvoltage support).
            Clamped to [-q_max, +q_max].
        """
        delta_v = v_pu - self._v_nom
        _EPS = 1e-9

        if abs(delta_v) <= self._deadband + _EPS:
            log.debug("reactive.within_deadband", v_pu=v_pu, delta_v=delta_v)
            return 0.0

        droop_ref = (self._droop_pct / 100.0) * self._v_nom
        # Undervoltage (delta_v < 0) → inject Q (positive)
        q_cmd = -(delta_v / droop_ref) * self._q_max
        clamped = max(-self._q_max, min(self._q_max, q_cmd))

        log.info(
            "reactive.setpoint",
            v_pu=v_pu, delta_v=delta_v,
            q_cmd_kvar=round(q_cmd, 2),
            clamped_kvar=round(clamped, 2),
            norm_ref="NTSyCS Cap. 4.4",
        )
        return clamped

    @property
    def q_max_kvar(self) -> float:
        return self._q_max

    @property
    def power_factor_capability(self) -> float:
        """Minimum pf achievable given q_max and p_nom."""
        s = math.sqrt(self._p_nom**2 + self._q_max**2)
        return self._p_nom / s if s > 0 else 1.0
