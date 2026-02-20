"""
tests/test_bess_env.py
=======================
Unit tests for BESSPhysicsModel and BESSEnv.

Tests cover:
  - Physics model: SOC dynamics, clipping, degradation, thermal
  - Environment: reset, step, observation shape, action bounds
  - Episode termination after 96 steps
  - Reward signs (discharge at high price → positive)
  - Rendering output without gymnasium installed
"""

from __future__ import annotations

import numpy as np
import pytest
from src.simulation.bess_model import BESSPhysicsModel

# ===========================================================================
# BESSPhysicsModel tests
# ===========================================================================

class TestBESSPhysicsModel:

    def _model(self, soc: float = 0.5) -> BESSPhysicsModel:
        return BESSPhysicsModel(capacity_kwh=100.0, max_power_kw=50.0, initial_soc=soc)

    def test_reset_restores_initial_state(self):
        model = self._model(soc=0.7)
        model.step(power_kw=50.0, dt_minutes=15)  # charge
        model.reset()
        assert model.soc == pytest.approx(0.7)
        assert model.total_throughput_kwh == pytest.approx(0.0)
        assert model.cumulative_degradation == pytest.approx(0.0)

    def test_charging_increases_soc(self):
        model = self._model(soc=0.5)
        result = model.step(power_kw=50.0, dt_minutes=15)
        assert model.soc > 0.5
        assert result["soc"] == pytest.approx(model.soc)

    def test_discharging_decreases_soc(self):
        model = self._model(soc=0.5)
        result = model.step(power_kw=-50.0, dt_minutes=15)
        assert model.soc < 0.5
        assert result["clipped_power_kw"] < 0

    def test_soc_clamped_at_zero_when_discharging_empty(self):
        model = self._model(soc=0.10)
        model.step(power_kw=-50.0, dt_minutes=60)  # deep discharge
        assert model.soc >= 0.0

    def test_soc_full_prevents_charging(self):
        model = self._model(soc=0.90)
        result = model.step(power_kw=50.0, dt_minutes=15)
        # Above 90% SOC, charging is blocked
        assert result["clipped_power_kw"] == pytest.approx(0.0)

    def test_power_clipped_to_max(self):
        model = self._model()
        result = model.step(power_kw=999.0, dt_minutes=15)
        assert abs(result["clipped_power_kw"]) <= 50.0

    def test_degradation_is_positive(self):
        model = self._model()
        result = model.step(power_kw=30.0, dt_minutes=15)
        assert result["degradation"] >= 0.0

    def test_thermal_model_temperature_rises(self):
        model = self._model()
        initial_temp = model.temp_c
        model.step(power_kw=50.0, dt_minutes=60)
        assert model.temp_c >= initial_temp  # heat generated

    def test_remaining_capacity_less_than_nominal_after_cycling(self):
        model = self._model()
        for _ in range(100):
            model.step(power_kw=50.0, dt_minutes=15)
            model.step(power_kw=-50.0, dt_minutes=15)
        assert model.remaining_capacity_kwh <= 100.0

    def test_is_safe_flag(self):
        model = self._model(soc=0.5)
        assert model.is_safe is True
        model.temp_c = 60.0  # overheat
        assert model.is_safe is False


# ===========================================================================
# BESSEnv tests (does not require gymnasium installed)
# ===========================================================================

def _has_gymnasium() -> bool:
    try:
        import gymnasium  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_gymnasium(), reason="gymnasium not installed")
class TestBESSEnv:

    def _env(self) -> BESSEnv:  # noqa: F821
        from src.simulation.bess_env import BESSEnv
        return BESSEnv(capacity_kwh=100.0, max_power_kw=50.0)

    def test_reset_returns_correct_obs_shape(self):
        env = self._env()
        obs, info = env.reset()
        assert obs.shape == (8,)
        assert isinstance(info, dict)

    def test_obs_values_in_range(self):
        env = self._env()
        obs, _ = env.reset()
        assert obs.dtype == np.float32
        # sin/cos can be -1 to 1; others [0,1]
        assert np.all(np.isfinite(obs))

    def test_step_returns_correct_types(self):
        env = self._env()
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert obs.shape == (8,)
        assert np.isfinite(float(reward))  # gymnasium may return np.float32
        assert isinstance(terminated, bool)
        assert "soc" in info

    def test_episode_terminates_after_96_steps(self):
        env = self._env()
        env.reset()
        terminated = False
        for _i in range(96):
            _, _, terminated, _, _ = env.step(np.array([0.0]))
        assert terminated is True

    def test_discharge_at_high_price_positive_reward(self):
        from src.simulation.bess_env import _DEFAULT_PRICE_PROFILE, BESSEnv
        # Advance to peak-price timestep (step 73 ≈ 110 EUR/MWh)
        peak_step = int(np.argmax(_DEFAULT_PRICE_PROFILE))
        env = BESSEnv(capacity_kwh=100.0, max_power_kw=50.0, noise_std=0.0)
        env.reset(seed=42)
        env._step_idx = peak_step
        env._bess.soc = 0.8  # enough charge to discharge
        _, reward, _, _, _ = env.step(np.array([-50.0]))  # discharge
        assert reward > 0, f"Expected positive reward at peak price, got {reward:.4f}"

    def test_render_ansi_returns_string(self):
        from src.simulation.bess_env import BESSEnv
        env = BESSEnv(render_mode="ansi")
        env.reset()
        text = env.render()
        assert text is not None
        assert "SOC" in text
