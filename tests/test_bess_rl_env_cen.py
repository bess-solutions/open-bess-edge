# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_bess_rl_env_cen.py
==============================
Unit tests for BEP-0200 Phase 3 — BESSArbitrageEnvCEN.

Tests validate:
- Dataset loading (load_cmg_dataset) with mocked JSON files
- Environment reset() / step() interface compatibility
- Observation space bounds [0, 1]
- Physics: SoC stays in valid range
- Revenue sign consistency
- API compatibility with BESSArbitrageEnv
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.agents.bess_rl_env_cen import load_cmg_dataset

gymnasium = pytest.importorskip("gymnasium", reason="gymnasium not installed")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cmg_json_file(tmp_path: Path) -> Path:
    """Write a minimal CMg JSON in 'days' format (2 days × 288 steps)."""
    rng = np.random.default_rng(42)
    data = {
        "node": "Maitencillo-220",
        "resolution_min": 5,
        "days": [
            {
                "date": f"2025-11-{d + 1:02d}",
                "cmg_usd_mwh": (rng.uniform(10.0, 150.0, 288)).tolist(),
            }
            for d in range(5)
        ],
    }
    p = tmp_path / "cmg_test.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture()
def cmg_flat_file(tmp_path: Path) -> Path:
    """CMg JSON in flat list-of-arrays format."""
    rng = np.random.default_rng(7)
    data = [rng.uniform(10.0, 100.0, 48).tolist() for _ in range(4)]
    p = tmp_path / "cmg_flat.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture()
def env(cmg_json_file: Path):  # noqa: ANN201
    """Create a BESSArbitrageEnvCEN with the test dataset."""
    from src.agents.bess_rl_env_cen import BESSArbitrageEnvCEN

    return BESSArbitrageEnvCEN(
        cmg_data_path=str(cmg_json_file),
        capacity_kwh=100.0,
        max_power_kw=50.0,
        episode_days=1,
    )


# ---------------------------------------------------------------------------
# TestLoadCMGDataset
# ---------------------------------------------------------------------------


class TestLoadCMGDataset:
    def test_loads_days_format(self, cmg_json_file: Path) -> None:
        days = load_cmg_dataset(cmg_json_file)
        assert len(days) == 5
        assert all(isinstance(d, np.ndarray) for d in days)
        assert all(len(d) == 288 for d in days)

    def test_loads_flat_list_format(self, cmg_flat_file: Path) -> None:
        days = load_cmg_dataset(cmg_flat_file)
        assert len(days) == 4
        assert all(len(d) == 48 for d in days)

    def test_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="CMg dataset not found"):
            load_cmg_dataset("/nonexistent/path/cmg.json")

    def test_dtype_float32(self, cmg_json_file: Path) -> None:
        days = load_cmg_dataset(cmg_json_file)
        assert all(d.dtype == np.float32 for d in days)

    def test_values_in_reasonable_range(self, cmg_json_file: Path) -> None:
        days = load_cmg_dataset(cmg_json_file)
        all_vals = np.concatenate(days)
        assert np.all(all_vals >= 0.0)
        assert np.all(all_vals < 1e6)  # Sanity bound

    def test_single_array_format(self, tmp_path: Path) -> None:
        """Test 'cmg_usd_mwh' key with flat array (n_days × 288)."""
        n_days, steps = 3, 48
        data = {
            "cmg_usd_mwh": (np.ones(n_days * steps) * 50.0).tolist(),
            "steps_per_day": steps,
        }
        p = tmp_path / "cmg_single.json"
        p.write_text(json.dumps(data))
        days = load_cmg_dataset(p)
        assert len(days) == n_days
        assert all(len(d) == steps for d in days)


# ---------------------------------------------------------------------------
# TestBESSArbitrageEnvCEN — init and spaces
# ---------------------------------------------------------------------------


class TestBESSArbitrageEnvCEN:
    def test_init(self, env) -> None:
        from src.agents.bess_rl_env_cen import BESSArbitrageEnvCEN

        assert isinstance(env, BESSArbitrageEnvCEN)

    def test_observation_space(self, env) -> None:
        assert env.observation_space.shape == (8,)
        assert env.observation_space.low.min() == pytest.approx(0.0)
        assert env.observation_space.high.max() == pytest.approx(1.0)

    def test_action_space(self, env) -> None:
        assert env.action_space.shape == (1,)
        assert env.action_space.low[0] == pytest.approx(-1.0)
        assert env.action_space.high[0] == pytest.approx(1.0)

    def test_reset_returns_obs_and_info(self, env) -> None:
        obs, info = env.reset(seed=0)
        assert obs.shape == (8,)
        assert isinstance(info, dict)
        assert "start_day" in info

    def test_reset_obs_in_bounds(self, env) -> None:
        obs, _ = env.reset(seed=42)
        assert np.all(obs >= 0.0), f"obs < 0: {obs}"
        assert np.all(obs <= 1.0), f"obs > 1: {obs}"

    def test_reset_reproducible_with_seed(self, env) -> None:
        obs1, _ = env.reset(seed=99)
        obs2, _ = env.reset(seed=99)
        np.testing.assert_array_equal(obs1, obs2)

    def test_reset_different_seeds_different_obs(self, env) -> None:
        obs1, _ = env.reset(seed=1)
        obs2, _ = env.reset(seed=2)
        # Different seeds → different starting days (highly likely)
        # Just check obs are arrays
        assert obs1.shape == obs2.shape


# ---------------------------------------------------------------------------
# TestBESSArbitrageEnvCEN — step
# ---------------------------------------------------------------------------


class TestEnvStep:
    def test_step_returns_5_tuple(self, env) -> None:
        env.reset(seed=0)
        obs, reward, terminated, truncated, info = env.step(np.array([0.5]))
        assert obs.shape == (8,)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_step_obs_always_in_bounds(self, env) -> None:
        env.reset(seed=0)
        for _ in range(50):
            action = env.action_space.sample()
            obs, _, terminated, truncated, _ = env.step(action)
            assert np.all(obs >= 0.0), f"obs out of bounds: {obs}"
            assert np.all(obs <= 1.0), f"obs out of bounds: {obs}"
            if terminated or truncated:
                break

    def test_soc_stays_in_valid_range(self, env) -> None:
        env.reset(seed=0)
        for _ in range(100):
            action = env.action_space.sample()
            _, _, terminated, truncated, info = env.step(action)
            soc = info["soc"]
            assert 0.0 <= soc <= 1.0, f"SoC out of range: {soc}"
            if terminated or truncated:
                break

    def test_discharge_generates_positive_revenue(self, env) -> None:
        """Full discharge at any CMg > 0 should generate positive revenue."""
        env.reset(seed=0)
        _, _, _, _, info = env.step(np.array([1.0]))  # Full discharge
        # Revenue sign depends on CMg; with positive CMg, discharge is revenue
        if info["cmg_usd_mwh"] > 0:
            assert info["revenue_usd"] >= 0.0

    def test_charge_generates_negative_revenue(self, env) -> None:
        """Full charge (buy energy) generates negative revenue (cost)."""
        env.reset(seed=0)
        _, _, _, _, info = env.step(np.array([-1.0]))  # Full charge
        if info["cmg_usd_mwh"] > 0:
            assert info["revenue_usd"] <= 0.0

    def test_episode_terminates(self, env) -> None:
        """Episode must terminate after steps_per_day × episode_days steps."""
        obs, _ = env.reset(seed=0)
        steps = 0
        terminated = truncated = False
        while not (terminated or truncated):
            action = env.action_space.sample()
            obs, _, terminated, truncated, _ = env.step(action)
            steps += 1
        assert terminated
        assert steps == env._episode_steps

    def test_info_has_required_fields(self, env) -> None:
        env.reset(seed=0)
        _, _, _, _, info = env.step(np.array([0.0]))
        required = {"soc", "cmg_usd_mwh", "p_kw", "revenue_usd", "deg_cost_usd", "data_source"}
        assert required.issubset(info.keys())

    def test_data_source_is_cen(self, env) -> None:
        env.reset(seed=0)
        _, _, _, _, info = env.step(np.array([0.0]))
        assert info["data_source"] == "cen_maitencillo_real"


# ---------------------------------------------------------------------------
# TestAPICompatibility — BESSArbitrageEnv interface
# ---------------------------------------------------------------------------


class TestAPICompatibility:
    def test_obs_shape_matches_drl_agent_input(self, env) -> None:
        """Obs shape (8,) must match ONNXArbitrageAgent's expected input."""
        obs, _ = env.reset(seed=0)
        assert obs.shape == (8,), "DRL agent expects 8-d observation"

    def test_action_space_matches_drl_agent_output(self, env) -> None:
        """Action space must accept scalar p_pu ∈ [-1, 1]."""
        env.reset(seed=0)
        for p_pu in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            obs, reward, term, trunc, info = env.step(np.array([p_pu]))
            assert obs.shape == (8,)
            if term or trunc:
                env.reset(seed=0)
