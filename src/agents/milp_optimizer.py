# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/milp_optimizer.py
=============================
BESSAI Edge Gateway — BEP-0215: MILP Day-Ahead Dispatch Optimizer.

A Mixed-Integer Linear Program (MILP) formulation for 24-hour ahead
BESS dispatch scheduling. This module serves two purposes:

1. **Fallback planner** — when the DRL ONNX model is unavailable, the MILP
   provides an optimal daily schedule (updated every hour with rolling horizon).
2. **Benchmark baseline** — MILP gives the theoretical optimum for a given
   price scenario, allowing us to measure the DRL's *optimality gap*.

Solver: PuLP + HiGHS (open-source, available via pip, no license fees).
Typical solve time for 288 timesteps (24h at 5-min): <500 ms on RPi 5.

Dependencies::
    pip install pulp highspy   # HiGHS solver (open-source MILP)

Competitor comparison:
    - Rule-based BEMS platforms: use fixed charge/discharge thresholds. Not optimal.
    - Cloud-based scheduling platforms: MILP-based but require connectivity, not edge-native.
    - **BESSAI MILP**: Runs locally in <500ms, fallback for edge DRL. Unique.

Model formulation
-----------------
Decision variables:
    p_ch[t]   ∈ [0, P_max]  — charge power (kW)
    p_dis[t]  ∈ [0, P_max]  — discharge power (kW)
    u[t]      ∈ {0, 1}      — charge/discharge mode (binary)
    e[t]      ≥ 0           — energy stored (kWh)

Objective (maximize revenue − degradation cost):
    max Σ_t (p_dis[t] − p_ch[t]) × CMg[t] × dt_h / 1000
        − λ_deg × (p_ch[t] + p_dis[t]) × dt_h × deg_cost

Constraints:
    Energy balance:       e[t+1] = e[t] + η_ch×p_ch[t]×dt_h − p_dis[t]×dt_h/η_dis
    SoC bounds:           E_min ≤ e[t] ≤ E_max
    Power bounds:         p_ch ≤ P_max × u;  p_dis ≤ P_max × (1−u)
    Complementarity:      u[t]∈{0,1} enforces no simultaneous charge+discharge
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import numpy as np

log = logging.getLogger(__name__)

__all__ = ["MILPOptimizer", "MILPSchedule", "solve_milp_schedule"]

# Check optional dependency
try:
    import pulp  # type: ignore[import]
    _PULP_AVAILABLE = True
except ImportError:
    _PULP_AVAILABLE = False
    pulp = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class MILPSchedule:
    """Result of a MILP optimization run.

    Attributes
    ----------
    p_charge_kw:
        Charge power profile (kW) — positive when charging.
    p_discharge_kw:
        Discharge power profile (kW) — positive when discharging.
    p_net_kw:
        Net dispatch (kW): positive = discharge, negative = charge.
    soc_profile:
        State-of-charge trajectory ∈ [0, 1] at each timestep.
    energy_kwh:
        Stored energy (kWh) trajectory.
    revenue_usd:
        Total projected revenue (USD) for the schedule horizon.
    degradation_cost_usd:
        Total projected degradation cost (USD).
    net_profit_usd:
        Net profit after degradation costs.
    status:
        PuLP solver status string ('Optimal', 'Infeasible', etc.).
    solve_time_ms:
        Approximate solve time in milliseconds.
    n_steps:
        Number of timesteps in the schedule.
    """

    p_charge_kw: np.ndarray
    p_discharge_kw: np.ndarray
    p_net_kw: np.ndarray
    soc_profile: np.ndarray
    energy_kwh: np.ndarray
    revenue_usd: float
    degradation_cost_usd: float
    net_profit_usd: float
    status: str
    solve_time_ms: float
    n_steps: int

    def get_setpoint_at(self, step: int) -> float:
        """Return net dispatch setpoint (kW) for a given step index.

        Positive = discharge, negative = charge.
        """
        if step >= self.n_steps:
            return 0.0
        return float(self.p_net_kw[step])


# ---------------------------------------------------------------------------
# MILP Solver
# ---------------------------------------------------------------------------


def solve_milp_schedule(
    cmg_profile: Sequence[float] | np.ndarray,
    capacity_kwh: float = 200.0,
    max_power_kw: float = 100.0,
    soc_init: float = 0.5,
    soc_min: float = 0.10,
    soc_max: float = 0.95,
    eta_charge: float = 0.95,
    eta_discharge: float = 0.95,
    dt_minutes: float = 5.0,
    degradation_cost_usd_kwh: float = 0.015,  # $/kWh throughput
    solver_time_limit_s: float = 10.0,
) -> MILPSchedule:
    """Solve the BESS day-ahead dispatch MILP.

    Parameters
    ----------
    cmg_profile:
        Array of CMg prices (USD/MWh) for the planning horizon.
        Length determines number of timesteps (e.g., 288 for 24h at 5-min).
    capacity_kwh:
        Usable battery capacity (kWh).
    max_power_kw:
        Maximum charge/discharge power (kW).
    soc_init:
        Initial state-of-charge ∈ [0, 1].
    soc_min, soc_max:
        SoC operating bounds ∈ [0, 1].
    eta_charge, eta_discharge:
        Round-trip efficiency components (typical: 0.95 each → 0.9025 RT).
    dt_minutes:
        Timestep duration in minutes.
    degradation_cost_usd_kwh:
        Degradation cost in USD per kWh of throughput.
        Typical for LFP: $250/kWh pack ÷ 3000 cycles ÷ 200 kWh = $0.00042/kWh
        but we use a higher value to account for partial cycle effects.
    solver_time_limit_s:
        Maximum MILP solve time (HiGHS will return best-found solution).

    Returns
    -------
    MILPSchedule

    Raises
    ------
    ImportError
        If PuLP is not installed.
    """
    import time

    if not _PULP_AVAILABLE:
        raise ImportError(
            "PuLP is required for MILP optimization. "
            "Install with: pip install pulp highspy"
        )

    cmg = np.asarray(cmg_profile, dtype=float)
    n = len(cmg)
    dt_h = dt_minutes / 60.0
    e_min = soc_min * capacity_kwh
    e_max = soc_max * capacity_kwh
    e_init = soc_init * capacity_kwh

    t0 = time.perf_counter()

    # ----------------------------------------------------------------
    # Build PuLP model
    # ----------------------------------------------------------------
    prob = pulp.LpProblem("BESS_DayAhead_Dispatch", pulp.LpMaximize)

    # Decision variables
    p_ch = [pulp.LpVariable(f"p_ch_{t}", 0, max_power_kw) for t in range(n)]
    p_dis = [pulp.LpVariable(f"p_dis_{t}", 0, max_power_kw) for t in range(n)]
    u = [pulp.LpVariable(f"u_{t}", cat="Binary") for t in range(n)]
    e = [pulp.LpVariable(f"e_{t}", e_min, e_max) for t in range(n + 1)]

    # Initial energy state
    prob += (e[0] == e_init), "InitialEnergy"

    # Energy balance constraints
    for t in range(n):
        prob += (
            e[t + 1] == e[t]
            + eta_charge * p_ch[t] * dt_h
            - (1.0 / eta_discharge) * p_dis[t] * dt_h
        ), f"EnergyBalance_{t}"

    # Power mode constraints (no simultaneous charge + discharge)
    for t in range(n):
        prob += (p_ch[t] <= max_power_kw * u[t]), f"ChargeBound_{t}"
        prob += (p_dis[t] <= max_power_kw * (1 - u[t])), f"DischargeBound_{t}"

    # Objective: max revenue - degradation cost
    revenue_terms = [
        (p_dis[t] - p_ch[t]) * cmg[t] * dt_h / 1000.0
        for t in range(n)
    ]
    deg_terms = [
        -(p_ch[t] + p_dis[t]) * dt_h * degradation_cost_usd_kwh
        for t in range(n)
    ]
    prob += pulp.lpSum(revenue_terms) + pulp.lpSum(deg_terms)

    # ----------------------------------------------------------------
    # Solve with HiGHS (preferred) or CBC fallback
    # ----------------------------------------------------------------
    try:
        solver = pulp.HiGHS_CMD(
            msg=False,
            timeLimit=solver_time_limit_s,
        )
    except AttributeError:
        # Fallback to CBC if HiGHS not available
        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=solver_time_limit_s)

    prob.solve(solver)
    solve_time_ms = (time.perf_counter() - t0) * 1000.0

    status = pulp.LpStatus[prob.status]

    # ----------------------------------------------------------------
    # Extract results
    # ----------------------------------------------------------------
    p_ch_vals = np.array([pulp.value(p_ch[t]) or 0.0 for t in range(n)])
    p_dis_vals = np.array([pulp.value(p_dis[t]) or 0.0 for t in range(n)])
    e_vals = np.array([pulp.value(e[t]) or e_init for t in range(n + 1)])

    p_net = p_dis_vals - p_ch_vals  # + = discharge, - = charge
    soc_profile = np.clip(e_vals[:-1] / capacity_kwh, 0.0, 1.0)

    revenue_usd = float(
        sum(
            (p_dis_vals[t] - p_ch_vals[t]) * cmg[t] * dt_h / 1000.0
            for t in range(n)
        )
    )
    deg_cost_usd = float(
        sum(
            (p_ch_vals[t] + p_dis_vals[t]) * dt_h * degradation_cost_usd_kwh
            for t in range(n)
        )
    )

    log.info(
        "milp_optimizer.solved",
        extra={
            "status": status,
            "revenue_usd": round(revenue_usd, 2),
            "deg_cost_usd": round(deg_cost_usd, 2),
            "solve_time_ms": round(solve_time_ms, 1),
        },
    )

    return MILPSchedule(
        p_charge_kw=p_ch_vals,
        p_discharge_kw=p_dis_vals,
        p_net_kw=p_net,
        soc_profile=soc_profile,
        energy_kwh=e_vals[:-1],
        revenue_usd=revenue_usd,
        degradation_cost_usd=deg_cost_usd,
        net_profit_usd=revenue_usd - deg_cost_usd,
        status=status,
        solve_time_ms=solve_time_ms,
        n_steps=n,
    )


# ---------------------------------------------------------------------------
# MILPOptimizer wrapper class (compatible with ONNXArbitrageAgent interface)
# ---------------------------------------------------------------------------


class MILPOptimizer:
    """MILP-based BESS dispatch agent — edge planning mode.

    Wraps ``solve_milp_schedule`` with a schedule-following interface
    compatible with the BESSAI agent interface (``predict(obs) -> (p_pu, info)``).

    The optimizer solves the 24h schedule once, then follows it step-by-step.
    Every N steps (default: 12 = 1 hour) it re-solves with updated SoC and
    a fresh rolling horizon (MPC-style).

    Parameters
    ----------
    cmg_profile:
        CMg price profile for the planning horizon.
    capacity_kwh, max_power_kw:
        BESS specifications.
    replan_every_steps:
        Re-optimize every N steps (rolling horizon MPC).
    """

    def __init__(
        self,
        cmg_profile: np.ndarray,
        capacity_kwh: float = 200.0,
        max_power_kw: float = 100.0,
        replan_every_steps: int = 12,  # 12 × 5 min = 1h
    ) -> None:
        self._cmg = cmg_profile
        self._capacity_kwh = capacity_kwh
        self._max_power_kw = max_power_kw
        self._replan_every = replan_every_steps
        self._schedule: MILPSchedule | None = None
        self._step: int = 0

    def predict(self, obs: np.ndarray) -> tuple[float, dict]:
        """Return per-unit setpoint from MILP schedule.

        Parameters
        ----------
        obs:
            Observation from BESSArbitrageEnv — used to extract current SoC.

        Returns
        -------
        p_pu : float
            Per-unit power ∈ [-1, +1].
        info : dict
        """
        soc = float(obs[0])  # obs[0] = SOC

        # (Re-)plan if needed
        if self._schedule is None or self._step % self._replan_every == 0:
            remaining_steps = len(self._cmg) - self._step
            if remaining_steps > 0:
                horizon = min(remaining_steps, max(self._replan_every * 24, 12))  # up to 24 replan-windows ahead
                future_cmg = self._cmg[self._step: self._step + horizon]
                try:
                    self._schedule = solve_milp_schedule(
                        cmg_profile=future_cmg,
                        capacity_kwh=self._capacity_kwh,
                        max_power_kw=self._max_power_kw,
                        soc_init=soc,
                    )
                except Exception as exc:
                    log.warning("milp_optimizer.solve_failed: %s", exc)
                    self._schedule = None

        # Follow schedule
        if self._schedule is not None:
            local_step = self._step % self._replan_every
            p_kw = self._schedule.get_setpoint_at(min(local_step, self._schedule.n_steps - 1))
            p_pu = float(np.clip(p_kw / self._max_power_kw, -1.0, 1.0))
        else:
            p_pu = 0.0  # Hold

        self._step += 1
        return p_pu, {"source": "milp_optimizer", "step": self._step}

    def reset(self) -> None:
        """Reset for a new episode."""
        self._schedule = None
        self._step = 0
