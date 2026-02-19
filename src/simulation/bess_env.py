"""
src/simulation/bess_env.py
===========================
BESSAI Edge Gateway — Gymnasium BESS Dispatch Environment.

A single-site BESS dispatch environment compatible with Stable-Baselines3,
Ray RLlib, and any OpenAI Gym-compatible RL framework.

Episode structure:
    - 24-hour day, 15-minute timesteps → 96 steps per episode
    - Exogenous signals: grid_price (€/MWh), solar_irradiance (kW/m²)
    - Continuous action space: dispatch power [-max_kw, +max_kw]

Observation space (8 features):
    [soc, power_kw_norm, temp_c_norm, hour_sin, hour_cos,
     grid_price_norm, solar_irr_norm, degradation_pct]

Reward function:
    revenue (arbitrage) - degradation_cost - thermal_penalty - safety_penalty

Grading:
    render('ansi') → prints episode summary with KPIs
    render('rgb_array') → not implemented (no display needed on edge)
"""

from __future__ import annotations

import math
from typing import Any, Optional, SupportsFloat

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    _GYM_AVAILABLE = True
except ImportError:
    _GYM_AVAILABLE = False
    # Stubs for environments without gymnasium installed
    class gym:  # type: ignore[no-redef]
        class Env:
            pass
    class spaces:  # type: ignore[no-redef]
        class Box:
            pass

from .bess_model import BESSPhysicsModel

__all__ = ["BESSEnv"]

# ---------------------------------------------------------------------------
# Synthetic market price profile (ENTSO-E average day-ahead, normalised)
# ---------------------------------------------------------------------------
_DEFAULT_PRICE_PROFILE = np.array([
    28, 25, 22, 20, 19, 22, 35, 55, 70, 72, 65, 60,
    58, 60, 63, 70, 80, 95, 110, 105, 90, 70, 50, 35,
    28, 25, 22, 20, 19, 22, 35, 55, 70, 72, 65, 60,
    58, 60, 63, 70, 80, 95, 110, 105, 90, 70, 50, 35,
    28, 25, 22, 20, 19, 22, 35, 55, 70, 72, 65, 60,
    58, 60, 63, 70, 80, 95, 110, 105, 90, 70, 50, 35,
    28, 25, 22, 20, 19, 22, 35, 55, 70, 72, 65, 60,
    58, 60, 63, 70, 80, 95, 110, 105, 90, 70, 50, 35,
], dtype=np.float32)  # 96 values (15-min intervals, EUR/MWh)

_DEFAULT_SOLAR_PROFILE = np.array([
    0, 0, 0, 0, 0, 0, 0.02, 0.08, 0.18, 0.32, 0.50, 0.72,
    0.85, 0.90, 0.88, 0.80, 0.65, 0.44, 0.22, 0.06, 0.01, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0.02, 0.08, 0.18, 0.32, 0.50, 0.72,
    0.85, 0.90, 0.88, 0.80, 0.65, 0.44, 0.22, 0.06, 0.01, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0.02, 0.08, 0.18, 0.32, 0.50, 0.72,
    0.85, 0.90, 0.88, 0.80, 0.65, 0.44, 0.22, 0.06, 0.01, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0.02, 0.08, 0.18, 0.32, 0.50, 0.72,
    0.85, 0.90, 0.88, 0.80, 0.65, 0.44, 0.22, 0.06, 0.01, 0, 0, 0,
], dtype=np.float32)


class BESSEnv(gym.Env):
    """BESS dispatch environment for DRL training.

    Attributes:
        capacity_kwh:   Battery usable capacity in kWh.
        max_power_kw:   Maximum charge/discharge power in kW.
        dt_minutes:     Timestep duration in minutes (default: 15).
        price_profile:  Array of 96 grid prices (EUR/MWh) for one day.
        solar_profile:  Array of 96 solar irradiance values (0-1 normalised).
        noise_std:      Gaussian noise std added to prices (market uncertainty).
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        capacity_kwh: float = 100.0,
        max_power_kw: float = 50.0,
        dt_minutes: float = 15.0,
        price_profile: Optional[np.ndarray] = None,
        solar_profile: Optional[np.ndarray] = None,
        noise_std: float = 3.0,
        render_mode: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self.dt_minutes = dt_minutes
        self.noise_std = noise_std
        self.render_mode = render_mode

        self._price_profile = price_profile if price_profile is not None else _DEFAULT_PRICE_PROFILE.copy()
        self._solar_profile = solar_profile if solar_profile is not None else _DEFAULT_SOLAR_PROFILE.copy()
        self._episode_steps = len(self._price_profile)  # 96

        # Physics model
        self._bess = BESSPhysicsModel(capacity_kwh=capacity_kwh, max_power_kw=max_power_kw)

        # Action space: continuous dispatch power [-max_kw, +max_kw]
        self.action_space = spaces.Box(
            low=-max_power_kw,
            high=max_power_kw,
            shape=(1,),
            dtype=np.float32,
        )

        # Observation space: 8 features, all normalised to [-1, 1] / [0, 1]
        self.observation_space = spaces.Box(
            low=np.array([0.0, -1.0, 0.0, -1.0, -1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            high=np.array([1.0,  1.0, 1.0,  1.0,  1.0, 1.0, 1.0, 1.0], dtype=np.float32),
            dtype=np.float32,
        )

        # Runtime state
        self._step_idx: int = 0
        self._episode_revenue: float = 0.0
        self._episode_degradation: float = 0.0

    # ------------------------------------------------------------------
    # Gymnasium interface
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> tuple[np.ndarray, dict]:
        """Reset environment to start of a new episode."""
        super().reset(seed=seed)
        self._bess.reset()
        self._step_idx = 0
        self._episode_revenue = 0.0
        self._episode_degradation = 0.0
        return self._observe(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, SupportsFloat, bool, bool, dict]:
        """Execute one 15-minute dispatch timestep.

        Returns:
            observation, reward, terminated, truncated, info
        """
        power_kw = float(np.clip(action[0], -self.max_power_kw, self.max_power_kw))
        price = self._noisy_price(self._step_idx)

        # Physics step
        physics = self._bess.step(power_kw, self.dt_minutes)
        clipped_kw = physics["clipped_power_kw"]

        # Revenue: discharge = sell at current price, charge = buy at current price
        dt_h = self.dt_minutes / 60.0
        energy_kwh = clipped_kw * dt_h  # + = charging (cost), - = discharging (revenue)
        revenue = -energy_kwh * price / 1000.0  # EUR (sell when negative kW)

        # Costs
        degradation_cost = physics["degradation"] * self.capacity_kwh * 200.0  # 200 EUR/kWh replacement
        thermal_penalty = max(0.0, physics["temp_c"] - 45.0) * 5.0  # EUR per °C above 45
        safety_penalty = 0.0 if self._bess.is_safe else 50.0

        reward = revenue - degradation_cost - thermal_penalty - safety_penalty

        self._episode_revenue += revenue
        self._episode_degradation += physics["degradation"]
        self._step_idx += 1
        terminated = self._step_idx >= self._episode_steps
        truncated = False

        info = {
            "soc": physics["soc"],
            "temp_c": physics["temp_c"],
            "price_eur_mwh": price,
            "revenue_eur": revenue,
            "degradation_pct": physics["degradation"] * 100,
            "episode_revenue": self._episode_revenue,
            "episode_degradation_pct": self._episode_degradation * 100,
        }
        return self._observe(), reward, terminated, truncated, info

    def render(self) -> Optional[str]:
        if self.render_mode == "ansi":
            return (
                f"Step {self._step_idx:03d}/096 | "
                f"SOC={self._bess.soc:.1%} | "
                f"Temp={self._bess.temp_c:.1f}C | "
                f"Revenue={self._episode_revenue:.2f} EUR"
            )
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _observe(self) -> np.ndarray:
        hour_frac = (self._step_idx * self.dt_minutes / 60.0) % 24.0
        angle = 2.0 * math.pi * hour_frac / 24.0
        price = self._price_profile[min(self._step_idx, self._episode_steps - 1)]
        solar = self._solar_profile[min(self._step_idx, self._episode_steps - 1)]

        return np.array([
            self._bess.soc,                                # [0, 1]
            self._bess.temp_c / self._bess.max_temp_c,    # [0, 1]
            self._bess.cumulative_degradation,             # [0, ~0.05]
            math.sin(angle),                               # [-1, 1]
            math.cos(angle),                               # [-1, 1]
            price / 200.0,                                 # normalised ~[0, 1]
            solar,                                         # [0, 1]
            min(self._step_idx / self._episode_steps, 1.0),  # [0, 1] progress
        ], dtype=np.float32)

    def _noisy_price(self, idx: int) -> float:
        price = self._price_profile[min(idx, self._episode_steps - 1)]
        noise = float(np.random.normal(0, self.noise_std))
        return max(0.0, price + noise)
