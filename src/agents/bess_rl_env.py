# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/bess_rl_env.py
=========================
BESSAI Edge Gateway — BEP-0200: DRL Arbitrage Gymnasium Environment.

Extends ``BESSEnv`` (src/simulation/bess_env.py) with:

1. **Real CMg price data** (Costo Marginal, Chile CEN) in USD/MWh instead
   of the synthetic ENTSO-E profile.  When real data is unavailable, falls
   back to a realistic synthetic Chilean CMg profile.
2. **5-minute timesteps** (288 per day) matching CEN settlement intervals.
3. **CMg forecast observations** — 1-hour and 4-hour ahead price signals,
   simulating a CMg Predictor v2 output.
4. **Graceful degradation** — env works without real data; synthetic profile
   captures Atacama solar duck curve and peak price patterns.

Observation space (8-d, all ∈ [0, 1] or [-1, 1]):
    [soc, power_norm, temp_norm, cmg_actual_norm,
     cmg_fcast_1h_norm, cmg_fcast_4h_norm, hour_sin, hour_cos]

Action space (continuous, shape=[1]):
    p_setpoint_pu ∈ [-1, +1]   (−1 = max charge, +1 = max discharge)

Reward:
    revenue_usd - degradation_cost_usd - thermal_penalty - safety_penalty

Usage::

    from src.agents.bess_rl_env import BESSArbitrageEnv

    env = BESSArbitrageEnv(capacity_kwh=200, max_power_kw=100)
    obs, _ = env.reset()
    obs, reward, done, truncated, info = env.step(env.action_space.sample())
"""

from __future__ import annotations

import math
from typing import Any, SupportsFloat

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces

    _GYM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _GYM_AVAILABLE = False

    class gym:  # type: ignore[no-redef]
        class Env:
            pass

    class spaces:  # type: ignore[no-redef]
        class Box:
            pass


from src.simulation.bess_model import BESSPhysicsModel

__all__ = ["BESSArbitrageEnv"]


# ---------------------------------------------------------------------------
# Synthetic Chilean CMg profile (5-min, 288 steps/day, USD/MWh)
# Calibrated on CEN data 2023-2025 — Atacama solar duck curve:
#   - Off-peak night:  ~15-25 USD/MWh
#   - Morning ramp:    ~60-90 USD/MWh (07:00-09:00)
#   - Solar dump:      ~5-15 USD/MWh (11:00-15:00, Atacama peak)
#   - Evening peak:    ~80-150 USD/MWh (18:00-22:00)
# ---------------------------------------------------------------------------
def _build_synthetic_cmg_profile() -> np.ndarray:
    """Return a 288-step (5-min) CMg profile in USD/MWh mimicking CEN 2024."""
    hours = np.linspace(0, 24, 288, endpoint=False)
    # Base off-peak price
    base = 20.0
    # Morning ramp (06:00–09:00)
    morning = 70.0 * np.exp(-0.5 * ((hours - 7.5) / 1.0) ** 2)
    # Solar dump (11:00–16:00): negative duck
    solar_dump = -12.0 * np.exp(-0.5 * ((hours - 13.0) / 2.0) ** 2)
    # Evening peak (18:00–22:00)
    evening = 120.0 * np.exp(-0.5 * ((hours - 20.0) / 1.5) ** 2)
    profile = base + morning + solar_dump + evening
    return np.clip(profile, 5.0, 300.0).astype(np.float32)


_SYNTHETIC_CMG_PROFILE = _build_synthetic_cmg_profile()

# Price normalisation constant (USD/MWh) — clips > this are treated as 1.0
_CMG_MAX_NORM = 300.0


class BESSArbitrageEnv(gym.Env):  # type: ignore[misc]
    """Gymnasium BESS dispatch environment driven by Chilean CMg price data.

    Parameters
    ----------
    capacity_kwh:
        Usable battery capacity in kWh.
    max_power_kw:
        Maximum charge/discharge power in kW.
    cmg_profile:
        Optional 1-D numpy array of CMg prices (USD/MWh) for one trading day.
        Length determines number of steps per episode.
        If ``None``, falls back to the synthetic Chilean CMg profile (288 steps).
    noise_std:
        Standard deviation of Gaussian noise added to observed CMg price (USD/MWh).
        Simulates real-time price uncertainty.
    battery_cost_usd_kwh:
        Replacement cost in USD/kWh, used to penalise degradation.
    render_mode:
        ``"ansi"`` for text render output, ``None`` to disable.
    """

    metadata = {"render_modes": ["ansi"]}

    # Timestep in minutes matching CEN 5-min settlement interval
    DT_MINUTES: float = 5.0

    # Forecast horizons (number of steps ahead)
    FCAST_1H_STEPS: int = 12  # 12 × 5 min = 60 min
    FCAST_4H_STEPS: int = 48  # 48 × 5 min = 240 min

    def __init__(
        self,
        capacity_kwh: float = 200.0,
        max_power_kw: float = 100.0,
        cmg_profile: np.ndarray | None = None,
        noise_std: float = 2.0,
        battery_cost_usd_kwh: float = 250.0,
        render_mode: str | None = None,
    ) -> None:
        super().__init__()

        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self.noise_std = noise_std
        self.battery_cost_usd_kwh = battery_cost_usd_kwh
        self.render_mode = render_mode

        self._cmg_profile: np.ndarray = (
            cmg_profile if cmg_profile is not None else _SYNTHETIC_CMG_PROFILE.copy()
        )
        self._n_steps = len(self._cmg_profile)

        # Physics model (same as BESSEnv)
        self._bess = BESSPhysicsModel(capacity_kwh=capacity_kwh, max_power_kw=max_power_kw)

        # Action space: per-unit setpoint ∈ [-1, 1]
        #   -1.0 → max charge (−max_power_kw)
        #   +1.0 → max discharge (+max_power_kw)
        self.action_space = spaces.Box(  # type: ignore[union-attr]
            low=np.array([-1.0], dtype=np.float32),
            high=np.array([1.0], dtype=np.float32),
            dtype=np.float32,
        )

        # Observation space: 8-d, all in [-1, 1] or [0, 1]
        # [soc, power_norm, temp_norm, cmg_now_norm,
        #  cmg_1h_norm, cmg_4h_norm, hour_sin, hour_cos]
        self.observation_space = spaces.Box(  # type: ignore[union-attr]
            low=np.array([0.0, -1.0, 0.0, 0.0, 0.0, 0.0, -1.0, -1.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )

        # Runtime state
        self._step_idx: int = 0
        self._episode_revenue: float = 0.0
        self._episode_degradation: float = 0.0
        self._episode_n_cycles: float = 0.0

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset to start of a new trading day."""
        super().reset(seed=seed)
        self._bess.reset()
        self._step_idx = 0
        self._episode_revenue = 0.0
        self._episode_degradation = 0.0
        self._episode_n_cycles = 0.0
        return self._observe(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, SupportsFloat, bool, bool, dict[str, Any]]:
        """Execute one 5-minute dispatch timestep.

        Parameters
        ----------
        action:
            1-D array with a single value ∈ [-1, 1] (per-unit setpoint).

        Returns
        -------
        observation, reward, terminated, truncated, info
        """
        # Convert per-unit action to kW
        p_pu = float(np.clip(action[0], -1.0, 1.0))
        # Convention: p_pu = +1 → max DISCHARGE (−kW in physics model)
        #             p_pu = −1 → max CHARGE   (+kW in physics model)
        power_kw = -p_pu * self.max_power_kw

        # Observed CMg (add noise to simulate real-time measurement uncertainty)
        cmg = self._cmg_at(self._step_idx) + float(
            self.np_random.normal(0.0, self.noise_std)  # use gym-seeded RNG
        )
        cmg = max(0.0, cmg)

        # Physics step
        physics = self._bess.step(power_kw, self.DT_MINUTES)
        clipped_kw = physics["clipped_power_kw"]

        # ----------------------------------------------------------------
        # Reward components (all in USD)
        # ----------------------------------------------------------------
        dt_h = self.DT_MINUTES / 60.0
        energy_kwh = clipped_kw * dt_h  # + = charging, − = discharging
        revenue = -energy_kwh * cmg / 1000.0  # USD (positive when discharging)

        # Degradation penalty: replace_cost × SoH loss
        deg = physics["degradation"]
        degradation_cost = deg * self.capacity_kwh * self.battery_cost_usd_kwh

        # Thermal penalty: quadratic above 45 °C
        temp_excess = max(0.0, physics["temp_c"] - 45.0)
        thermal_penalty = temp_excess**2 * 0.05

        # Safety guard: hard penalty for out-of-spec operation
        safety_penalty = 0.0 if self._bess.is_safe else 25.0

        reward = revenue - degradation_cost - thermal_penalty - safety_penalty

        # Bookkeeping
        self._episode_revenue += revenue
        self._episode_degradation += deg
        self._step_idx += 1
        terminated = self._step_idx >= self._n_steps
        truncated = False

        info: dict[str, Any] = {
            "soc": physics["soc"],
            "temp_c": physics["temp_c"],
            "clipped_power_kw": clipped_kw,
            "cmg_usd_mwh": cmg,
            "revenue_usd": revenue,
            "degradation_pct": deg * 100.0,
            "episode_revenue_usd": self._episode_revenue,
            "episode_degradation_pct": self._episode_degradation * 100.0,
            "is_safe": self._bess.is_safe,
        }
        return self._observe(), reward, terminated, truncated, info

    def render(self) -> str | None:  # type: ignore[override]
        if self.render_mode == "ansi":
            cmg = self._cmg_at(max(0, self._step_idx - 1))
            return (
                f"Step {self._step_idx:03d}/{self._n_steps:03d} | "
                f"SOC={self._bess.soc:.1%} | "
                f"Temp={self._bess.temp_c:.1f}°C | "
                f"CMg={cmg:.1f} USD/MWh | "
                f"Revenue={self._episode_revenue:.3f} USD"
            )
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cmg_at(self, idx: int) -> float:
        """Return CMg price at a given step, clamped to valid range."""
        clamped = min(idx, self._n_steps - 1)
        return float(self._cmg_profile[clamped])

    def _cmg_forecast(self, idx: int, horizon_steps: int) -> float:
        """Return a CMg forecast ``horizon_steps`` steps ahead.

        In production this would come from CMg Predictor v2. During training
        we use the actual future price + noise to simulate forecast error
        (MAPE ~8 % typical for neural CMg predictors). Uses gym-seeded RNG
        for reproducibility.
        """
        fcast_idx = min(idx + horizon_steps, self._n_steps - 1)
        forecast_noise = float(self.np_random.normal(0.0, self._cmg_at(fcast_idx) * 0.08))
        return max(0.0, self._cmg_at(fcast_idx) + forecast_noise)

    def _observe(self) -> np.ndarray:
        idx = self._step_idx
        # Time encoding (cyclic)
        minutes_elapsed = idx * self.DT_MINUTES
        hour_frac = (minutes_elapsed / 60.0) % 24.0
        angle = 2.0 * math.pi * hour_frac / 24.0

        cmg_now = self._cmg_at(idx)
        cmg_1h = self._cmg_forecast(idx, self.FCAST_1H_STEPS)
        cmg_4h = self._cmg_forecast(idx, self.FCAST_4H_STEPS)

        return np.array(
            [
                self._bess.soc,  # [0, 1]
                self._bess.temp_c / self._bess.max_temp_c,  # [0, 1]
                clamp01(self._bess.cumulative_degradation / 0.2),  # [0, 1]
                clamp01(cmg_now / _CMG_MAX_NORM),  # [0, 1]
                clamp01(cmg_1h / _CMG_MAX_NORM),  # [0, 1]
                clamp01(cmg_4h / _CMG_MAX_NORM),  # [0, 1]
                math.sin(angle),  # [-1, 1]
                math.cos(angle),  # [-1, 1]
            ],
            dtype=np.float32,
        )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def clamp01(x: float) -> float:
    """Clamp value to [0, 1]."""
    return max(0.0, min(1.0, x))
