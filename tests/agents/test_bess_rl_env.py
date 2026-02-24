"""
tests/agents/test_bess_rl_env.py
=================================
Tests for BESSArbitrageEnv (BEP-0200).
"""
from __future__ import annotations

import numpy as np
import pytest

from src.agents.bess_rl_env import BESSArbitrageEnv, _build_synthetic_cmg_profile, clamp01


# -----------------------------------------------------------------------
# Synthetic profile
# -----------------------------------------------------------------------

def test_synthetic_cmg_profile_shape():
    profile = _build_synthetic_cmg_profile()
    assert profile.shape == (288,), "Profile must be 288 steps (5-min, 24h)"


def test_synthetic_cmg_profile_bounds():
    profile = _build_synthetic_cmg_profile()
    assert profile.min() >= 5.0
    assert profile.max() <= 300.0


def test_synthetic_cmg_duck_curve():
    """Evening peak should be higher than solar dump window."""
    profile = _build_synthetic_cmg_profile()
    # Solar dump: steps 132–192 (11:00–16:00)
    solar_dump_mean = profile[132:192].mean()
    # Evening peak: steps 216–264 (18:00–22:00)
    evening_peak_mean = profile[216:264].mean()
    assert evening_peak_mean > solar_dump_mean * 2, \
        "Evening peak should be at least 2× solar dump"


# -----------------------------------------------------------------------
# Environment initialisation
# -----------------------------------------------------------------------

def test_env_init_default():
    env = BESSArbitrageEnv()
    assert env.capacity_kwh == 200.0
    assert env.max_power_kw == 100.0
    assert env._n_steps == 288


def test_env_init_custom_profile():
    profile = np.ones(96, dtype=np.float32) * 50.0
    env = BESSArbitrageEnv(cmg_profile=profile)
    assert env._n_steps == 96


def test_env_observation_space_shape():
    env = BESSArbitrageEnv()
    assert env.observation_space.shape == (8,)  # type: ignore[union-attr]


def test_env_action_space_shape():
    env = BESSArbitrageEnv()
    assert env.action_space.shape == (1,)  # type: ignore[union-attr]


# -----------------------------------------------------------------------
# Reset
# -----------------------------------------------------------------------

def test_reset_returns_valid_obs():
    env = BESSArbitrageEnv()
    obs, info = env.reset(seed=42)
    assert obs.shape == (8,)
    assert np.all(obs >= env.observation_space.low), "Obs below lower bound"  # type: ignore[union-attr]
    assert np.all(obs <= env.observation_space.high), "Obs above upper bound"  # type: ignore[union-attr]
    assert isinstance(info, dict)


def test_reset_deterministic():
    """Same seed should produce same initial observation (before any step)."""
    env = BESSArbitrageEnv()
    obs1, _ = env.reset(seed=0)
    obs2, _ = env.reset(seed=0)
    # First 4 obs are deterministic (soc, temp, degradation, cmg_now).
    # Indices 4,5 are CMg forecasts with np_random noise — check they match.
    np.testing.assert_array_equal(obs1, obs2)


# -----------------------------------------------------------------------
# Step
# -----------------------------------------------------------------------

def test_step_returns_correct_types():
    env = BESSArbitrageEnv(noise_std=0.0)
    env.reset(seed=0)
    obs, reward, done, truncated, info = env.step(np.array([0.0], dtype=np.float32))
    assert obs.shape == (8,)
    assert isinstance(float(reward), float)
    assert isinstance(done, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)


def test_step_obs_valid_bounds():
    env = BESSArbitrageEnv(noise_std=0.0)
    env.reset(seed=0)
    for _ in range(20):
        action = env.action_space.sample()  # type: ignore[union-attr]
        obs, _, done, _, _ = env.step(action)
        assert np.all(obs >= -1.01), f"Obs below lower bound: {obs}"
        assert np.all(obs <= 1.01), f"Obs above upper bound: {obs}"
        if done:
            break


def test_episode_terminates():
    env = BESSArbitrageEnv()
    env.reset(seed=0)
    done = False
    steps = 0
    while not done:
        _, _, done, _, _ = env.step(np.array([0.0], dtype=np.float32))
        steps += 1
        assert steps <= 290, "Episode did not terminate after 290 steps"
    assert steps == 288


def test_discharge_generates_revenue():
    """Discharging during high CMg period should yield positive revenue.
    Convention: action=+1 → p_pu=+1 → DISCHARGE (physics gets -kW).
    """
    # Build profile with only high CMg
    profile = np.full(10, 200.0, dtype=np.float32)
    env = BESSArbitrageEnv(cmg_profile=profile, noise_std=0.0)
    env.reset(seed=0)
    # Force SOC to 80% so discharge is possible
    env._bess._soc = 0.80  # type: ignore[attr-defined]
    _, reward, _, _, info = env.step(np.array([1.0], dtype=np.float32))  # discharge (p_pu=+1)
    assert info["revenue_usd"] > 0, (
        f"Discharging at high CMg should generate revenue, got {info['revenue_usd']}"
    )


def test_charge_costs_money():
    """Charging during high CMg should yield negative revenue.
    Convention: action=-1 → p_pu=-1 → CHARGE (physics gets +kW).
    """
    profile = np.full(10, 200.0, dtype=np.float32)
    env = BESSArbitrageEnv(cmg_profile=profile, noise_std=0.0)
    env.reset(seed=0)
    _, _, _, _, info = env.step(np.array([-1.0], dtype=np.float32))  # charge (p_pu=-1)
    assert info["revenue_usd"] < 0, (
        f"Charging at high CMg should cost money, got {info['revenue_usd']}"
    )


def test_info_keys():
    env = BESSArbitrageEnv()
    env.reset()
    _, _, _, _, info = env.step(np.array([0.0], dtype=np.float32))
    expected_keys = {
        "soc", "temp_c", "clipped_power_kw", "cmg_usd_mwh",
        "revenue_usd", "degradation_pct", "episode_revenue_usd",
        "episode_degradation_pct", "is_safe",
    }
    assert expected_keys.issubset(info.keys()), f"Missing keys: {expected_keys - info.keys()}"


# -----------------------------------------------------------------------
# Render
# -----------------------------------------------------------------------

def test_render_ansi():
    env = BESSArbitrageEnv(render_mode="ansi")
    env.reset()
    env.step(np.array([0.0], dtype=np.float32))
    rendered = env.render()
    assert rendered is not None
    assert "SOC" in rendered


def test_render_none_mode():
    env = BESSArbitrageEnv(render_mode=None)
    env.reset()
    env.step(np.array([0.0], dtype=np.float32))
    assert env.render() is None


# -----------------------------------------------------------------------
# Utility
# -----------------------------------------------------------------------

def test_clamp01():
    assert clamp01(-1.0) == 0.0
    assert clamp01(2.0) == 1.0
    assert clamp01(0.5) == pytest.approx(0.5)
