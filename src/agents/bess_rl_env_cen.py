# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
src/agents/bess_rl_env_cen.py
==============================
BEP-0200 Phase 3 — BESS Arbitrage Gymnasium Environment with Real CEN/SEN CMg Data.
v2.1: Weather-enriched observation space (12 features, ERA5 Open-Meteo).

Observation space (12-dim, all normalized to [-1, 1]):
    [0]  soc           - State of charge (0=empty, 1=full)
    [1]  cmg_norm      - Current CMg price (normalized by max_price)
    [2]  cmg_delta     - Price change from previous step (normalized)
    [3]  hour_sin      - Hour of day, sin component
    [4]  hour_cos      - Hour of day, cos component
    [5]  step_frac     - Fraction of episode completed
    [6]  energy_left   - Approximate charge available for discharge
    [7]  capacity_left - Headroom for charging
    --- ERA5 weather features (Pearson rad↔CMg=-0.59, duck_delta=70 USD/MWh) ---
    [8]  radiation     - Direct solar radiation (W/m², normed)
    [9]  wind_speed    - Wind speed 10m (km/h, normed)
    [10] cloud_cover   - Cloud cover % (normed)
    [11] cmg_lag1h     - CMg 1h lag (early momentum signal, normed)

Action space (Box, 1-dim, [-1, 1]):
    -1.0 → full discharge at max_power_kw
     0.0 → idle
    +1.0 → full charge at max_power_kw

Reward: net revenue in USD
    = (power_kw * dt_h * cmg_usd_mwh / 1000)
      - degradation_penalty
      - safety_penalty

Termination: after episode_days * 24 steps.
"""

from __future__ import annotations

import json
import math
import os
import random
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

_DEFAULT_CMG_PATH  = Path(__file__).parents[3] / "bessai-web" / "data" / "cmg_data.json"
_DEFAULT_FEAT_PATH = Path(__file__).parents[3] / "bessai-web" / "data" / "cmg_weather_features.json"
_FALLBACK_CMG_PATH = Path(
    os.environ.get("CEN_CMG_DATA_PATH", str(_DEFAULT_CMG_PATH))
)

# Observation dimensions
OBS_DIM_BASE    = 8    # original features
OBS_DIM_WEATHER = 12   # + radiation, wind, cloud, cmg_lag1h


# ---------------------------------------------------------------------------
# Weather feature cache (lazy-loaded singleton per process)
# ---------------------------------------------------------------------------

class _WeatherCache:
    """Lazy loader for cmg_weather_features.json indexed by node/timestamp."""
    _instance: _WeatherCache | None = None
    _index: dict = {}
    _loaded: bool = False

    @classmethod
    def get_instance(cls) -> _WeatherCache:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self, path: Path | None = None) -> None:
        if self._loaded:
            return
        p = path or _DEFAULT_FEAT_PATH
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for row in data.get("features", []):
                key = f"{row.get('node','')}/{row.get('ts','')}"
                self._index[key] = row
            self._loaded = True
        except Exception:
            pass

    def get(self, node: str, timestamp: str) -> dict | None:
        return self._index.get(f"{node}/{timestamp}")

    @property
    def available(self) -> bool:
        return self._loaded

# Nodes available in the CEN dataset
CEN_NODES = [
    "Maitencillo", "Polpaico", "Lo_Aguirre", "Cardones",
    "Crucero", "Charrua", "Quillota", "Hualpen",
]


def load_cmg_dataset(
    data_path: str | Path | None = None,
    node: str = "Maitencillo",
) -> list[np.ndarray]:
    """
    Load CMg price time series from cmg_data.json and return a list of
    daily price arrays (each array = list of hourly prices for one calendar day).

    Parameters
    ----------
    data_path : path to cmg_data.json (defaults to bessai-web/data/cmg_data.json)
    node      : CEN node name (must be one of CEN_NODES)

    Returns
    -------
    List of 1-D np.float32 arrays, one per day; each array has between 1 and 24 elements.
    """
    path = Path(data_path) if data_path else _FALLBACK_CMG_PATH
    if not path.exists():
        # Try relative resolution from the scripts directory
        alt = Path(__file__).parents[3] / "bessai-web" / "data" / "cmg_data.json"
        if alt.exists():
            path = alt
        else:
            raise FileNotFoundError(
                f"CMg dataset not found at {path}. "
                "Set CEN_CMG_DATA_PATH env var or pass data_path explicitly."
            )

    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    series = raw.get("series", {})
    if node not in series:
        available = list(series.keys())
        raise KeyError(f"Node '{node}' not found. Available: {available}")

    points = series[node]  # list of {"t": "...", "v": float}

    # Group by calendar date (first 10 chars of ISO timestamp)
    from collections import defaultdict
    by_day: dict[str, list[float]] = defaultdict(list)
    for pt in points:
        date_key = pt["t"][:10]
        by_day[date_key].append(float(pt["v"]))

    # Sort days and convert to arrays
    days = [np.array(prices, dtype=np.float32) for _, prices in sorted(by_day.items())]
    return days


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

class BESSArbitrageEnvCEN:
    """
    Gymnasium-compatible BESS arbitrage environment trained on real CEN/SEN CMg data.

    Parameters
    ----------
    cmg_data_path : str | Path
        Path to the cmg_data.json file. Defaults to the bessai-web data directory.
    node : str
        CEN node to use for training. Default: "Maitencillo".
    capacity_kwh : float
        BESS energy capacity in kWh.
    max_power_kw : float
        Maximum charge/discharge power in kW.
    initial_soc : float
        Starting state of charge (0–1). None → random.
    episode_days : int
        Number of calendar days per training episode.
    efficiency : float
        Round-trip efficiency fraction (0–1).
    degradation_cost_per_kwh : float
        Degradation penalty in USD per kWh throughput.
    safety_penalty : float
        Per-step penalty if unsafe conditions detected.
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(
        self,
        cmg_data_path: str | Path | None = None,
        node: str = "Maitencillo",
        capacity_kwh: float = 200.0,
        max_power_kw: float = 100.0,
        initial_soc: float | None = None,
        episode_days: int = 1,
        efficiency: float = 0.92,
        degradation_cost_per_kwh: float = 0.003,
        safety_penalty: float = 0.5,
        render_mode: str | None = None,
        use_weather: bool = True,    # enable 12-dim weather-enriched obs
    ) -> None:
        # Lazy gymnasium import (optional dep for non-training code)
        try:
            import gymnasium as gym
            self._gym = gym
        except ImportError as exc:
            raise ImportError(
                "gymnasium is required for the RL environment. "
                "Install with: pip install gymnasium"
            ) from exc

        self.capacity_kwh = float(capacity_kwh)
        self.max_power_kw = float(max_power_kw)
        self.initial_soc = initial_soc
        self.episode_days = int(episode_days)
        self.efficiency = float(efficiency)
        self.degradation_cost = float(degradation_cost_per_kwh)
        self.safety_penalty = float(safety_penalty)
        self.render_mode = render_mode
        self.node = node
        self.use_weather = use_weather

        # Load CMg dataset
        self._days = load_cmg_dataset(cmg_data_path, node=node)
        self._max_price = max(p for day in self._days for p in day)
        if self._max_price <= 0:
            self._max_price = 1.0

        # Load timestamps for weather lookup
        self._timestamps: list[str] = self._load_timestamps(cmg_data_path or _FALLBACK_CMG_PATH)

        # Pre-load weather cache (non-fatal)
        if use_weather:
            _WeatherCache.get_instance().load()
            obs_dim = OBS_DIM_WEATHER if _WeatherCache.get_instance().available else OBS_DIM_BASE
        else:
            obs_dim = OBS_DIM_BASE
        self._obs_dim = obs_dim

        # Build observation & action spaces
        self.observation_space = gym.spaces.Box(
            low=np.full(obs_dim, -1.0, dtype=np.float32),
            high=np.full(obs_dim, 1.0, dtype=np.float32),
            shape=(obs_dim,),
            dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(
            low=np.array([-1.0], dtype=np.float32),
            high=np.array([1.0], dtype=np.float32),
            shape=(1,),
            dtype=np.float32,
        )

        # Internal state (populated on reset)
        self._soc: float = 0.5
        self._step: int = 0
        self._prices: list[float] = []
        self._price_timestamps: list[str] = []  # timestamps for weather lookup
        self._total_steps: int = 0
        self._prev_price: float = 0.0
        self._episode_revenue: float = 0.0
        self._episode_start_idx: int = 0

        self.np_random = np.random.default_rng(42)

    def _load_timestamps(self, cmg_data_path: str | Path) -> list[str]:
        """Load timestamps from cmg_data.json for weather feature lookup."""
        try:
            path = Path(cmg_data_path)
            if not path.exists():
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
            series = data.get("series", {}).get(self.node, [])
            return [pt["t"] for pt in series]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Gymnasium API
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        if seed is not None:
            self.np_random = np.random.default_rng(seed)

        # Pick episode_days consecutive days randomly
        max_start = len(self._days) - self.episode_days
        if max_start <= 0:
            start = 0
        else:
            start = int(self.np_random.integers(0, max_start))

        self._prices = []
        self._price_timestamps = []
        # Compute the flat index offset for timestamp lookup
        flat_idx = 0
        for day_idx in range(start):
            flat_idx += len(self._days[day_idx % len(self._days)])
        self._episode_start_idx = flat_idx

        for day_idx in range(start, start + self.episode_days):
            day_prices = self._days[day_idx % len(self._days)].tolist()
            self._prices.extend(day_prices)
            # Map to timestamps
            n = len(day_prices)
            ts_slice = self._timestamps[flat_idx:flat_idx + n] if self._timestamps else []
            self._price_timestamps.extend(ts_slice)
            flat_idx += n

        self._total_steps = len(self._prices)
        self._step = 0
        self._soc = (
            float(self.np_random.uniform(0.2, 0.8))
            if self.initial_soc is None
            else float(self.initial_soc)
        )
        self._prev_price = self._prices[0] if self._prices else 0.0
        self._episode_revenue = 0.0

        return self._get_obs(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        action_scalar = float(np.clip(action, -1.0, 1.0).flat[0])

        power_kw = action_scalar * self.max_power_kw  # + = charge, - = discharge
        dt_h = 1.0  # 1-hour time steps

        cmg = self._prices[self._step]

        # Apply efficiency
        if power_kw > 0:
            energy_in = power_kw * dt_h * self.efficiency
        else:
            energy_in = power_kw * dt_h / self.efficiency

        # SOC dynamics
        new_soc = self._soc + energy_in / self.capacity_kwh
        new_soc = float(np.clip(new_soc, 0.0, 1.0))

        # Actual power (limited by SOC bounds)
        actual_energy = (new_soc - self._soc) * self.capacity_kwh
        actual_power_kw = actual_energy / dt_h * self.efficiency if power_kw > 0 else actual_energy / dt_h

        # Revenue (discharge = negative power → sell at CMg)
        energy_traded_mwh = -actual_energy / 1000.0  # MWh sold (positive when discharging)
        revenue = energy_traded_mwh * cmg  # USD

        # Degradation cost
        throughput_kwh = abs(actual_energy)
        deg_penalty = throughput_kwh * self.degradation_cost

        # Safety (SOC within [0.05, 0.95])
        safety = 0.0
        if new_soc < 0.05 or new_soc > 0.95:
            safety = self.safety_penalty

        reward = float(revenue - deg_penalty - safety)
        self._episode_revenue += reward

        self._soc = new_soc
        self._prev_price = cmg
        self._step += 1

        terminated = (self._step >= self._total_steps)
        truncated = False

        info = {
            "soc": self._soc,
            "cmg_usd_mwh": cmg,
            "power_kw": actual_power_kw,
            "revenue_usd": revenue,
            "episode_revenue_usd": self._episode_revenue,
            "data_source": f"CEN/{self.node}",
        }

        return self._get_obs(), reward, terminated, truncated, info

    def render(self) -> str | None:
        if self.render_mode == "ansi":
            price = self._prices[min(self._step, len(self._prices) - 1)]
            return (
                f"[BESSEnvCEN | {self.node}] "
                f"SOC={self._soc:.2f} | CMg={price:.1f} USD/MWh | "
                f"Step={self._step}/{self._total_steps} | "
                f"Rev={self._episode_revenue:.2f} USD"
            )
        return None

    def close(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_obs(self) -> np.ndarray:
        step_idx = min(self._step, self._total_steps - 1)
        cmg = self._prices[step_idx]
        prev_cmg = self._prices[max(0, step_idx - 1)]

        # Hour of day (from position in sequence; 1 step = 1 hour)
        hour = step_idx % 24
        hour_sin = math.sin(2 * math.pi * hour / 24.0)
        hour_cos = math.cos(2 * math.pi * hour / 24.0)

        cmg_norm  = float(np.clip(cmg / self._max_price, 0.0, 1.0))
        cmg_delta = float(np.clip((cmg - self._prev_price) / (self._max_price + 1e-6), -1.0, 1.0))
        step_frac  = float(step_idx / max(self._total_steps - 1, 1))
        energy_left = float(self._soc)
        cap_left    = float(1.0 - self._soc)

        base_obs = np.array([
            self._soc,
            cmg_norm,
            cmg_delta,
            hour_sin,
            hour_cos,
            step_frac,
            energy_left,
            cap_left,
        ], dtype=np.float32)

        if self._obs_dim == OBS_DIM_BASE:
            return base_obs

        # ── Weather features (ERA5) ───────────────────────────────────
        w_cache = _WeatherCache.get_instance()
        ts = self._price_timestamps[step_idx] if step_idx < len(self._price_timestamps) else ""
        row = w_cache.get(self.node, ts) if ts else None

        def _norm_w(key: str, lo: float, hi: float) -> float:
            if row is None:
                return 0.0
            v = row.get(key)
            return 0.0 if v is None else float(np.clip(2.0 * (v - lo) / (hi - lo) - 1.0, -1.0, 1.0))

        radiation  = _norm_w("radiation",  0.0,   1000.0)
        wind       = _norm_w("wind",       0.0,   80.0)
        cloud      = _norm_w("cloud",      0.0,   100.0)
        # cmg_lag1h from prev step price (normalised; same as cmg_delta but absolute)
        cmg_lag1h  = float(np.clip(prev_cmg / self._max_price, 0.0, 1.0)) * 2.0 - 1.0

        return np.concatenate([base_obs, [radiation, wind, cloud, cmg_lag1h]]).astype(np.float32)
