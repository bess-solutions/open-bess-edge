# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/bess_rl_env_cen.py
==============================
BESSAI BEP-0200 Phase 3 — Gymnasium environment powered by real CEN/SEN
CMg (Costo Marginal) data from the Maitencillo 220 kV node.

This replaces the synthetic duck-curve CMg profile used in Phase 1/2 with
48 days × 288 steps (5-min) of real price data captured from the Chilean
National Electricity Coordinator public API.

Usage::

    from src.agents.bess_rl_env_cen import BESSArbitrageEnvCEN

    env = BESSArbitrageEnvCEN(
        cmg_data_path="dashboard/data/cmg_maitencillo.json",
        episode_days=1,
    )
    obs, info = env.reset(seed=42)

The environment is 100% compatible with BESSArbitrageEnv — same observation
and action spaces — so existing DRL training scripts work drop-in.

Data format (dashboard/data/cmg_maitencillo.json)::

    {
        "node": "Maitencillo-220",
        "resolution_min": 5,
        "days": [
            {
                "date": "2025-11-01",
                "cmg_usd_mwh": [12.5, 11.8, ..., 98.2]  # 288 values
            },
            ...
        ]
    }
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

try:
    import gymnasium as gym
    from gymnasium import spaces
    _GYM_AVAILABLE = True
except ImportError:
    _GYM_AVAILABLE = False
    gym = None  # type: ignore[assignment]
    spaces = None  # type: ignore[assignment]


__all__ = ["BESSArbitrageEnvCEN", "load_cmg_dataset"]


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def load_cmg_dataset(data_path: str | Path) -> list[np.ndarray]:
    """Load CMg price profiles from the CEN/SEN JSON file.

    Parameters
    ----------
    data_path:
        Path to ``cmg_maitencillo.json`` (or compatible format).

    Returns
    -------
    list of np.ndarray
        One array per trading day (shape: [n_steps], dtype=float32).
        Values are in USD/MWh.

    Raises
    ------
    FileNotFoundError
        If the JSON file does not exist.
    ValueError
        If the file format is invalid.
    """
    data_path = Path(data_path)
    if not data_path.exists():
        raise FileNotFoundError(
            f"CMg dataset not found: {data_path}\n"
            "Fetch it with: python scripts/fetch_cmg_maitencillo.py"
        )

    with data_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    days: list[np.ndarray] = []

    if "days" in raw:
        # Structured format: {"node": ..., "days": [{"date": ..., "cmg_usd_mwh": [...]}, ...]}
        for entry in raw["days"]:
            vals = np.asarray(entry["cmg_usd_mwh"], dtype=np.float32)
            days.append(vals)
    elif isinstance(raw, list):
        # Flat format: [[288 values], [288 values], ...]
        for entry in raw:
            days.append(np.asarray(entry, dtype=np.float32))
    elif "cmg_usd_mwh" in raw:
        # Single-array format: {"cmg_usd_mwh": [flat array of N × 288 values]}
        flat = np.asarray(raw["cmg_usd_mwh"], dtype=np.float32)
        steps_per_day = raw.get("steps_per_day", 288)
        n_days = len(flat) // steps_per_day
        for i in range(n_days):
            days.append(flat[i * steps_per_day : (i + 1) * steps_per_day])
    else:
        raise ValueError(
            f"Unrecognized CMg JSON format in {data_path}. "
            "Expected 'days' key or flat list of arrays."
        )

    if not days:
        raise ValueError(f"No CMg profiles found in {data_path}")

    log.info(
        "cmg_dataset.loaded",
        extra={"n_days": len(days), "steps_per_day": len(days[0]), "path": str(data_path)},
    )
    return days


# ---------------------------------------------------------------------------
# BESSArbitrageEnvCEN
# ---------------------------------------------------------------------------

if _GYM_AVAILABLE:
    class BESSArbitrageEnvCEN(gym.Env):  # type: ignore[misc]
        """BESS arbitrage Gymnasium env powered by real CEN/SEN price data.

        Compatible with ``BESSArbitrageEnv`` — same obs/action spaces.

        Observation space (8-d, all ∈ [0, 1])::

            [soc, temp_norm, cumulative_deg, cmg_now_norm,
             cmg_1h_norm, cmg_4h_norm, hour_sin_norm, hour_cos_norm]

        Action space: Box(-1, 1, shape=(1,)) — per-unit dispatch setpoint.
            +1.0 = full discharge (P_max kW), -1.0 = full charge.

        Parameters
        ----------
        cmg_data_path:
            Path to the CEN/SEN CMg JSON dataset.
        capacity_kwh:
            Battery capacity (kWh).
        max_power_kw:
            Maximum charge/discharge power (kW).
        episode_days:
            Number of consecutive days per episode (default: 1).
        soc_init:
            Initial SoC [0, 1] (default: 0.5). Set to None for random init.
        eta_rt:
            Round-trip efficiency (default: 0.90).
        degradation_cost_usd_kwh:
            Degradation cost per kWh throughput (USD).
        cmg_norm_scale:
            Scale factor to normalise CMg values (USD/MWh → [0, 1]).
            Default 200.0 → 200 USD/MWh maps to 1.0.
        """

        metadata = {"render_modes": []}

        def __init__(
            self,
            cmg_data_path: str | Path = "dashboard/data/cmg_maitencillo.json",
            capacity_kwh: float = 200.0,
            max_power_kw: float = 100.0,
            episode_days: int = 1,
            soc_init: float | None = 0.5,
            eta_rt: float = 0.90,
            degradation_cost_usd_kwh: float = 0.015,
            cmg_norm_scale: float = 200.0,
            dt_minutes: float = 5.0,
        ) -> None:
            if not _GYM_AVAILABLE:
                raise ImportError("gymnasium is required. pip install gymnasium")

            super().__init__()

            self._capacity_kwh = capacity_kwh
            self._max_power_kw = max_power_kw
            self._episode_days = episode_days
            self._soc_init = soc_init
            self._eta_rt = eta_rt
            self._deg_cost = degradation_cost_usd_kwh
            self._cmg_scale = cmg_norm_scale
            self._dt_h = dt_minutes / 60.0
            self._dt_minutes = dt_minutes

            # Load dataset (raises FileNotFoundError if missing)
            self._cmg_days = load_cmg_dataset(cmg_data_path)
            self._steps_per_day = len(self._cmg_days[0])
            self._episode_steps = self._steps_per_day * episode_days

            # State
            self._soc: float = 0.5
            self._step_idx: int = 0
            self._cmg_profile: np.ndarray = np.zeros(self._episode_steps, dtype=np.float32)
            self._total_revenue: float = 0.0
            self._total_deg: float = 0.0

            # Gymnasium spaces (identical to BESSArbitrageEnv)
            self.observation_space = spaces.Box(  # type: ignore[union-attr]
                low=0.0, high=1.0, shape=(8,), dtype=np.float32
            )
            self.action_space = spaces.Box(  # type: ignore[union-attr]
                low=-1.0, high=1.0, shape=(1,), dtype=np.float32
            )

        def reset(
            self,
            *,
            seed: int | None = None,
            options: dict | None = None,
        ) -> tuple[np.ndarray, dict]:
            super().reset(seed=seed)

            # Select random starting day
            n_days = len(self._cmg_days)
            start_day = int(self.np_random.integers(0, max(1, n_days - self._episode_days)))
            episode_cmg_arrays = [
                self._cmg_days[(start_day + d) % n_days]
                for d in range(self._episode_days)
            ]
            self._cmg_profile = np.concatenate(episode_cmg_arrays)

            # Initial SoC
            if self._soc_init is None:
                self._soc = float(self.np_random.uniform(0.1, 0.9))
            else:
                self._soc = self._soc_init

            self._step_idx = 0
            self._total_revenue = 0.0
            self._total_deg = 0.0

            return self._get_obs(), {"start_day": start_day}

        def step(
            self, action: np.ndarray
        ) -> tuple[np.ndarray, float, bool, bool, dict]:
            p_pu = float(np.clip(action if np.isscalar(action) else action[0], -1.0, 1.0))
            p_kw = p_pu * self._max_power_kw

            # BESS physics
            cmg = float(self._cmg_profile[self._step_idx])
            dt_h = self._dt_h

            if p_kw >= 0:  # Discharge
                energy_delta_kwh = -p_kw * dt_h / self._eta_rt
                revenue = p_kw * cmg * dt_h / 1000.0  # USD
            else:  # Charge
                energy_delta_kwh = -p_kw * dt_h * self._eta_rt
                revenue = p_kw * cmg * dt_h / 1000.0  # negative (cost)

            new_energy = self._soc * self._capacity_kwh + energy_delta_kwh
            self._soc = float(np.clip(new_energy / self._capacity_kwh, 0.05, 0.95))

            # Degradation cost
            deg_cost = abs(p_kw) * dt_h * self._deg_cost
            self._total_deg += deg_cost
            self._total_revenue += revenue

            reward = float(revenue - deg_cost)

            self._step_idx += 1
            terminated = self._step_idx >= self._episode_steps
            truncated = False

            info = {
                "soc": self._soc,
                "cmg_usd_mwh": cmg,
                "p_kw": p_kw,
                "revenue_usd": revenue,
                "deg_cost_usd": deg_cost,
                "total_revenue_usd": self._total_revenue,
                "data_source": "cen_maitencillo_real",
            }

            return self._get_obs(), reward, terminated, truncated, info

        def _get_obs(self) -> np.ndarray:
            """Build 8-d normalised observation vector."""
            t = self._step_idx
            n = self._episode_steps
            cmg_now = float(self._cmg_profile[min(t, n - 1)])
            cmg_1h = float(self._cmg_profile[min(t + 12, n - 1)])
            cmg_4h = float(self._cmg_profile[min(t + 48, n - 1)])

            # Hour-of-day encoding
            step_in_day = t % self._steps_per_day
            frac_day = step_in_day / self._steps_per_day
            hour_angle = frac_day * 2 * math.pi

            deg_frac = min(self._total_deg / max(1.0, self._capacity_kwh * 0.5), 1.0)

            obs = np.array([
                self._soc,
                0.4,  # Nominal 25°C / 60°C norm
                deg_frac,
                min(cmg_now / self._cmg_scale, 1.0),
                min(cmg_1h / self._cmg_scale, 1.0),
                min(cmg_4h / self._cmg_scale, 1.0),
                (math.sin(hour_angle) + 1.0) / 2.0,
                (math.cos(hour_angle) + 1.0) / 2.0,
            ], dtype=np.float32)

            return obs

        def render(self) -> None:
            pass  # No rendering needed for training

else:
    # Stub when gymnasium is not available
    class BESSArbitrageEnvCEN:  # type: ignore[no-redef]
        """Stub: gymnasium not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "BESSArbitrageEnvCEN requires gymnasium. "
                "Install with: pip install 'open-bess-edge[sim]'"
            )
