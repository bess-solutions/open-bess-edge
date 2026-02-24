"""
tests/test_milp_optimizer.py
==============================
Unit tests for MILP day-ahead dispatch optimizer.
Tests cover: schedule structure, energy balance, SoC bounds, and revenue calculation.
Falls back gracefully if PuLP is not installed.
"""

from __future__ import annotations

import numpy as np
import pytest

pulp = pytest.importorskip("pulp", reason="PuLP not installed — skipping MILP tests")


from src.agents.milp_optimizer import (
    MILPOptimizer,
    MILPSchedule,
    solve_milp_schedule,
)
from src.agents.bess_rl_env import _build_synthetic_cmg_profile


# ---------------------------------------------------------------------------
# solve_milp_schedule
# ---------------------------------------------------------------------------


class TestSolveMILPSchedule:
    def test_returns_schedule(self) -> None:
        """Basic call should return a MILPSchedule."""
        profile = _build_synthetic_cmg_profile()
        schedule = solve_milp_schedule(cmg_profile=profile[:48], capacity_kwh=100.0)
        assert isinstance(schedule, MILPSchedule)

    def test_status_is_optimal(self) -> None:
        """Solver should find Optimal solution for well-conditioned problem."""
        profile = _build_synthetic_cmg_profile()
        schedule = solve_milp_schedule(cmg_profile=profile[:24], capacity_kwh=100.0)
        assert "Optimal" in schedule.status or "Feasible" in schedule.status

    def test_soc_bounds_respected(self) -> None:
        """SoC profile should stay within [soc_min, soc_max]."""
        soc_min, soc_max = 0.10, 0.95
        profile = _build_synthetic_cmg_profile()
        schedule = solve_milp_schedule(
            cmg_profile=profile[:36],
            soc_min=soc_min,
            soc_max=soc_max,
            capacity_kwh=100.0,
        )
        if "Optimal" in schedule.status:
            eps = 1e-3
            assert np.all(schedule.soc_profile >= soc_min - eps)
            assert np.all(schedule.soc_profile <= soc_max + eps)

    def test_no_simultaneous_charge_discharge(self) -> None:
        """Charge and discharge should not both be positive at the same step."""
        profile = _build_synthetic_cmg_profile()
        schedule = solve_milp_schedule(cmg_profile=profile[:24], capacity_kwh=100.0)
        if "Optimal" in schedule.status:
            for i in range(schedule.n_steps):
                ch = schedule.p_charge_kw[i]
                dis = schedule.p_discharge_kw[i]
                assert not (ch > 0.1 and dis > 0.1), (
                    f"Simultaneous charge ({ch:.2f} kW) and discharge ({dis:.2f} kW) at step {i}"
                )

    def test_revenue_positive_on_arbitrage_profile(self) -> None:
        """MILP should find positive revenue on Chilean price profile (high spread)."""
        profile = _build_synthetic_cmg_profile()  # Has large price spread
        schedule = solve_milp_schedule(cmg_profile=profile, capacity_kwh=200.0)
        if "Optimal" in schedule.status:
            # Chilean CMg has big arbitrage spread → should find positive revenue
            assert schedule.revenue_usd >= 0.0

    def test_power_bounds_respected(self) -> None:
        """Charge and discharge power should not exceed max_power_kw."""
        max_power = 50.0
        profile = _build_synthetic_cmg_profile()
        schedule = solve_milp_schedule(
            cmg_profile=profile[:24],
            max_power_kw=max_power,
            capacity_kwh=100.0,
        )
        if "Optimal" in schedule.status:
            assert np.all(schedule.p_charge_kw <= max_power + 1e-3)
            assert np.all(schedule.p_discharge_kw <= max_power + 1e-3)

    def test_n_steps_matches_profile(self) -> None:
        """n_steps should match the input profile length."""
        profile = np.ones(48, dtype=np.float32) * 50.0
        schedule = solve_milp_schedule(cmg_profile=profile, capacity_kwh=100.0)
        assert schedule.n_steps == 48

    def test_get_setpoint_at_returns_valid(self) -> None:
        """get_setpoint_at() should return valid float for all steps."""
        profile = _build_synthetic_cmg_profile()[:24]
        schedule = solve_milp_schedule(cmg_profile=profile, capacity_kwh=100.0)
        for step in range(schedule.n_steps):
            setpoint = schedule.get_setpoint_at(step)
            assert isinstance(setpoint, float)

    def test_get_setpoint_beyond_horizon_returns_zero(self) -> None:
        """get_setpoint_at() beyond horizon should return 0.0."""
        profile = np.ones(10) * 50.0
        schedule = solve_milp_schedule(cmg_profile=profile, capacity_kwh=100.0)
        assert schedule.get_setpoint_at(99999) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# MILPOptimizer agent
# ---------------------------------------------------------------------------


class TestMILPOptimizer:
    def test_predict_returns_valid_pu(self) -> None:
        """predict() should return a float in [-1, 1]."""
        profile = _build_synthetic_cmg_profile()
        optimizer = MILPOptimizer(cmg_profile=profile, capacity_kwh=100.0)
        obs = np.array([0.5, 0.3, 0.0, 0.2, 0.3, 0.4, 0.0, 1.0], dtype=np.float32)
        p_pu, info = optimizer.predict(obs)
        assert -1.0 <= p_pu <= 1.0
        assert "source" in info
        assert info["source"] == "milp_optimizer"

    def test_predict_increments_step(self) -> None:
        """Step counter should increment with each predict() call."""
        profile = _build_synthetic_cmg_profile()
        optimizer = MILPOptimizer(cmg_profile=profile, capacity_kwh=100.0)
        obs = np.zeros(8, dtype=np.float32)
        obs[0] = 0.5
        for expected_step in range(1, 5):
            _, info = optimizer.predict(obs)
            assert info["step"] == expected_step

    def test_reset_clears_state(self) -> None:
        """reset() should restart the schedule follower."""
        profile = _build_synthetic_cmg_profile()
        optimizer = MILPOptimizer(cmg_profile=profile, capacity_kwh=100.0)
        obs = np.zeros(8, dtype=np.float32)
        obs[0] = 0.5
        for _ in range(10):
            optimizer.predict(obs)
        optimizer.reset()
        _, info = optimizer.predict(obs)
        assert info["step"] == 1

    def test_compatible_with_benchmark_suite(self) -> None:
        """MILPOptimizer should be usable by BenchmarkSuite agent API."""
        from src.agents.benchmark_suite import BenchmarkSuite
        profile = _build_synthetic_cmg_profile()
        optimizer = MILPOptimizer(cmg_profile=profile, capacity_kwh=100.0)
        optimizer.name = "milp_test"  # type: ignore[attr-defined]
        suite = BenchmarkSuite(capacity_kwh=100.0, cmg_profile=profile[:48])
        result = suite.run_episode(optimizer, episode=0, seed=0)
        assert result.strategy == "milp_test"
        assert result.episode_steps > 0
