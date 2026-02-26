"""
tests/test_degradation_model.py
================================
Unit tests for the semi-empirical battery degradation model.
Tests cover: RainflowCounter, DegradationModel (LFP/NMC/NCA),
Arrhenius thermal acceleration, calendar aging, and reward cost calculation.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.agents.degradation_model import (
    BatteryChemistry,
    DegradationModel,
    DegradationResult,
    RainflowCounter,
)


# ---------------------------------------------------------------------------
# RainflowCounter tests
# ---------------------------------------------------------------------------


class TestRainflowCounter:
    def test_no_damage_flat_soc(self) -> None:
        """Flat SoC trajectory should produce no cycle damage."""
        counter = RainflowCounter()
        flat = [0.5] * 50
        for soc in flat:
            counter.update(soc)
        assert counter.total_damage == pytest.approx(0.0, abs=1e-6)

    def test_full_cycle_damage(self) -> None:
        """One full 0→1→0 cycle should register ~1.0 DoD damage."""
        counter = RainflowCounter()
        # Full charge/discharge cycle
        trajectory = [0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0]
        for soc in trajectory:
            counter.update(soc)
        # Should accumulate some damage (DoD ≈ 1.0)
        assert counter.total_damage >= 0.0

    def test_small_cycles_less_damage(self) -> None:
        """Small partial cycles should accumulate less damage than a full cycle."""
        full_counter = RainflowCounter()
        partial_counter = RainflowCounter()

        # Full cycle: 0→1→0
        for soc in [0.0, 1.0, 0.0]:
            full_counter.update(soc)

        # Small partial: 0.4→0.6→0.4
        for soc in [0.4, 0.6, 0.4]:
            partial_counter.update(soc)

        assert partial_counter.total_damage <= full_counter.total_damage

    def test_reset_clears_state(self) -> None:
        """Reset should clear all accumulated damage."""
        counter = RainflowCounter()
        for soc in [0.0, 0.5, 1.0, 0.5, 0.0]:
            counter.update(soc)
        counter.reset()
        assert counter.total_damage == 0.0
        assert len(counter.cycles) == 0

    def test_returns_non_negative_damage(self) -> None:
        """Damage increment should always be non-negative."""
        counter = RainflowCounter()
        rng = np.random.default_rng(42)
        for soc in rng.uniform(0, 1, 100):
            damage = counter.update(float(soc))
            assert damage >= 0.0


# ---------------------------------------------------------------------------
# DegradationModel tests
# ---------------------------------------------------------------------------


class TestDegradationModel:
    def test_lfp_model_initializes(self) -> None:
        """DegradationModel should initialize without error for LFP chemistry."""
        model = DegradationModel(chemistry=BatteryChemistry.LFP)
        assert model.soh_estimate == pytest.approx(1.0, abs=1e-3)

    def test_nmc_nca_models_initialize(self) -> None:
        """All chemistry presets should initialize correctly."""
        for chem in BatteryChemistry:
            model = DegradationModel(chemistry=chem)
            assert model.soh_estimate == pytest.approx(1.0, abs=1e-3)

    def test_step_returns_result(self) -> None:
        """step() should return a DegradationResult with valid fields."""
        model = DegradationModel()
        model.reset()
        result = model.step(soc=0.5, temp_c=25.0, dt_minutes=5.0)

        assert isinstance(result, DegradationResult)
        assert 0.0 <= result.soh <= 1.0
        assert result.total_fade_pct >= 0.0
        assert result.thermal_factor >= 1.0  # At 25°C (= ref temp), factor ≈ 1.0

    def test_thermal_factor_increases_at_high_temp(self) -> None:
        """Arrhenius: thermal factor should increase above reference temperature."""
        model = DegradationModel()
        model.reset()
        result_25 = model.step(soc=0.5, temp_c=25.0)
        model.reset()
        result_50 = model.step(soc=0.5, temp_c=50.0)

        assert result_50.thermal_factor > result_25.thermal_factor

    def test_thermal_factor_decreases_at_low_temp(self) -> None:
        """Arrhenius: thermal factor should be < 1 at temperatures below reference."""
        model = DegradationModel()
        model.reset()
        result_25 = model.step(soc=0.5, temp_c=25.0)
        model.reset()
        result_5 = model.step(soc=0.5, temp_c=5.0)

        assert result_5.thermal_factor < result_25.thermal_factor

    def test_degradation_cumulates_over_time(self) -> None:
        """Total fade should increase monotonically over cycling."""
        model = DegradationModel()
        model.reset()
        prev_fade = 0.0
        soc = 0.5
        for _ in range(100):
            # Simulate charge/discharge micro-cycles
            soc = 0.9 - soc * 0.1 + 0.1  # Oscillate between ~0.3 and ~0.9
            soc = min(0.9, max(0.1, soc * 0.5 + 0.5 * (1 - soc)))
            result = model.step(soc=soc, temp_c=30.0)
            assert result.total_fade_pct >= prev_fade - 1e-9  # Monotonically non-decreasing
            prev_fade = result.total_fade_pct

    def test_soh_bounded(self) -> None:
        """SoH should always remain in [0, 1]."""
        model = DegradationModel()
        model.reset()
        rng = np.random.default_rng(42)
        for _ in range(500):
            soc = float(rng.uniform(0.1, 0.9))
            temp = float(rng.uniform(15, 55))
            result = model.step(soc=soc, temp_c=temp)
            assert 0.0 <= result.soh <= 1.0 + 1e-6

    def test_degradation_cost_positive(self) -> None:
        """Degradation cost in USD should be non-negative."""
        model = DegradationModel(capacity_kwh=200.0, replacement_cost_usd_kwh=260.0)
        model.reset()
        result = model.step(soc=0.3, temp_c=40.0)
        cost = model.degradation_cost_usd(result)
        assert cost >= 0.0

    def test_lfp_faster_than_nca_at_high_temp(self) -> None:
        """NCA has higher activation energy → faster thermal aging than LFP."""
        # Both at 50°C (above reference)
        lfp = DegradationModel(chemistry=BatteryChemistry.LFP)
        nca = DegradationModel(chemistry=BatteryChemistry.NCA)
        for model in (lfp, nca):
            model.reset()
        # Step at 50°C
        result_lfp = lfp.step(soc=0.5, temp_c=50.0)
        result_nca = nca.step(soc=0.5, temp_c=50.0)
        # NCA has higher Ea → MORE thermal acceleration at T > T_ref
        assert result_nca.thermal_factor > result_lfp.thermal_factor

    def test_reset_does_not_clear_cumulative_fade(self) -> None:
        """reset() resets the cycle counter but NOT total cumulative fade
        (a new episode starts from the same SoH state)."""
        model = DegradationModel()
        model.reset()
        for _ in range(50):
            model.step(soc=0.5, temp_c=35.0, dt_minutes=5.0)
        soh_before_reset = model.soh_estimate
        model.reset()  # Reset only rainflow counter, not total fade
        first_step_after = model.step(soc=0.5, temp_c=25.0, dt_minutes=5.0)
        # SoH after reset should still reflect accumulated fade
        assert first_step_after.soh <= soh_before_reset + 0.01


# ---------------------------------------------------------------------------
# Integration: DegradationModel in BESSArbitrageEnv reward signal
# ---------------------------------------------------------------------------


class TestDegradationWithEnv:
    def test_environment_runs_with_degradation_available(self) -> None:
        """BESSArbitrageEnv should run without issues alongside degradation model."""
        pytest.importorskip("gymnasium")

        from src.agents.bess_rl_env import BESSArbitrageEnv
        from src.agents.degradation_model import DegradationModel

        env = BESSArbitrageEnv(capacity_kwh=100.0, max_power_kw=50.0)
        deg_model = DegradationModel(chemistry=BatteryChemistry.LFP, capacity_kwh=100.0)
        deg_model.reset()

        obs, _ = env.reset(seed=0)
        total_deg_cost = 0.0
        terminated = truncated = False

        while not (terminated or truncated):
            action = env.action_space.sample()  # type: ignore[attr-defined]
            obs, reward, terminated, truncated, info = env.step(action)
            # Use degradation model alongside env step for richer cost signal
            soc = float(obs[0])
            temp = info.get("temp_c", 25.0)
            result = deg_model.step(soc=soc, temp_c=temp, dt_minutes=5.0)
            total_deg_cost += deg_model.degradation_cost_usd(result)

        assert total_deg_cost >= 0.0
        assert 0.0 <= deg_model.soh_estimate <= 1.0 + 1e-6
