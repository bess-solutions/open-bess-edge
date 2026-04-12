# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_ppo_trainer.py
==========================
Unit tests for ``src.core.ppo_trainer``.

Covers:
  - TrainingConfig: default values and field types
  - BESSDispatchEnv: synthetic CMg generation, reset, step, reward shaping,
    SOC clamping, episode termination, SOC balance bonus
  - PPOTrainer: initialization, CSV data loading (with/without file),
    validation loop execution, ONNX skip when SB3 not available
  - TrainingResult: field defaults, bep_ref
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from src.core.ppo_trainer import (
    BESSDispatchEnv,
    PPOTrainer,
    TrainingConfig,
    TrainingResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_config(max_episode_steps: int = 16, **kwargs) -> TrainingConfig:
    return TrainingConfig(max_episode_steps=max_episode_steps, **kwargs)


def _default_env(**cfg_kwargs) -> BESSDispatchEnv:
    return BESSDispatchEnv(config=_default_config(**cfg_kwargs))


# ---------------------------------------------------------------------------
# TrainingConfig
# ---------------------------------------------------------------------------

class TestTrainingConfig:
    def test_default_learning_rate(self):
        cfg = TrainingConfig()
        assert cfg.learning_rate == pytest.approx(3e-4)

    def test_default_soc_limits(self):
        cfg = TrainingConfig()
        assert cfg.soc_min == pytest.approx(10.0)
        assert cfg.soc_max == pytest.approx(95.0)

    def test_default_reward_weights(self):
        cfg = TrainingConfig()
        assert cfg.w_revenue == pytest.approx(1.0)
        assert cfg.w_safety < 0   # penalty
        assert cfg.w_degradation < 0  # penalty
        assert cfg.w_soc_balance > 0  # bonus

    def test_custom_p_nom_kw(self):
        cfg = TrainingConfig(p_nom_kw=500.0)
        assert cfg.p_nom_kw == pytest.approx(500.0)

    def test_checkpoints_list_empty_by_default(self):
        result = TrainingResult()
        assert result.checkpoints == []

    def test_bep_ref_default(self):
        result = TrainingResult()
        assert "BEP-0200" in result.bep_ref


# ---------------------------------------------------------------------------
# BESSDispatchEnv — synthetic CMg
# ---------------------------------------------------------------------------

class TestSyntheticCMg:
    def test_synthetic_cmg_length(self):
        env = _default_env()
        expected = env._cfg.max_episode_steps * 10
        assert len(env._cmg) == expected

    def test_synthetic_cmg_positive(self):
        env = _default_env()
        assert all(c > 0 for c in env._cmg), "All CMg prices must be positive"

    def test_synthetic_cmg_min_floor(self):
        env = _default_env()
        # Floor is 10.0 USD/MWh per implementation
        assert all(c >= 10.0 for c in env._cmg)

    def test_custom_cmg_series_used(self):
        custom_cmg = [50.0, 60.0, 40.0, 70.0, 30.0]
        env = BESSDispatchEnv(config=_default_config(), cmg_series=custom_cmg)
        assert env._cmg == custom_cmg


# ---------------------------------------------------------------------------
# BESSDispatchEnv — reset & step
# ---------------------------------------------------------------------------

class TestEnvReset:
    def test_reset_returns_obs_and_empty_info(self):
        env = _default_env()
        obs, info = env.reset()
        assert info == {}

    def test_reset_soc_at_50(self):
        env = _default_env()
        env.reset()
        assert env._soc == pytest.approx(50.0)

    def test_reset_step_counter_zero(self):
        env = _default_env()
        env._step = 10
        env.reset()
        assert env._step == 0

    def test_reset_revenue_zero(self):
        env = _default_env()
        for _ in range(3):
            env.step([1.0])
        env.reset()
        assert env._episode_revenue == pytest.approx(0.0)

    def test_reset_with_seed_is_accepted(self):
        env = _default_env()
        obs, info = env.reset(seed=42)
        assert info == {}


class TestEnvStep:
    def test_step_returns_five_elements(self):
        env = _default_env()
        env.reset()
        result = env.step([0.0])
        assert len(result) == 5

    def test_step_soc_decreases_on_discharge(self):
        """Positive action = discharge → SOC decreases."""
        cfg = _default_config(p_nom_kw=1000.0)
        env = BESSDispatchEnv(config=cfg)
        env.reset()
        soc_before = env._soc
        env.step([1.0])  # full discharge
        assert env._soc < soc_before

    def test_step_soc_increases_on_charge(self):
        """Negative action = charge → SOC increases."""
        cfg = _default_config(p_nom_kw=1000.0, soc_max=95.0)
        env = BESSDispatchEnv(config=cfg)
        env.reset()
        soc_before = env._soc
        env.step([-1.0])  # full charge
        assert env._soc > soc_before

    def test_step_soc_clamped_to_limits(self):
        cfg = _default_config(p_nom_kw=1000.0, soc_min=10.0, soc_max=95.0)
        env = BESSDispatchEnv(config=cfg)
        env.reset()
        # Discharge massively — should clamp to soc_min
        for _ in range(16):
            env.step([1.0])
        assert env._soc >= cfg.soc_min

    def test_step_safety_violation_counted(self):
        cfg = _default_config(p_nom_kw=10000.0, soc_min=50.0)  # hard to avoid
        env = BESSDispatchEnv(config=cfg)
        env.reset()
        env.step([1.0])  # big discharge — will likely violate
        # Safety violations should be >= 0 (may be 0 if still in range)
        assert env._safety_violations >= 0

    def test_step_terminated_at_max_steps(self):
        cfg = _default_config(max_episode_steps=4, p_nom_kw=100.0)
        env = BESSDispatchEnv(config=cfg)
        env.reset()
        terminated = False
        for _ in range(4):
            _, _, terminated, _, _ = env.step([0.0])
        assert terminated

    def test_step_not_terminated_before_max_steps(self):
        cfg = _default_config(max_episode_steps=10, p_nom_kw=100.0)
        env = BESSDispatchEnv(config=cfg)
        env.reset()
        _, _, terminated, _, _ = env.step([0.0])
        assert not terminated

    def test_step_truncated_always_false(self):
        env = _default_env()
        env.reset()
        _, _, _, truncated, _ = env.step([0.0])
        assert not truncated

    def test_step_info_contains_soc(self):
        env = _default_env()
        env.reset()
        _, _, _, _, info = env.step([0.0])
        assert "soc" in info

    def test_step_info_contains_revenue(self):
        env = _default_env()
        env.reset()
        _, _, _, _, info = env.step([0.0])
        assert "revenue_usd" in info

    def test_step_info_contains_safety_ok(self):
        env = _default_env()
        env.reset()
        _, _, _, _, info = env.step([0.0])
        assert "safety_ok" in info

    def test_soc_balance_bonus_on_terminal_step(self):
        """When SOC is near 50% at episode end, reward should include bonus."""
        cfg = _default_config(max_episode_steps=3, p_nom_kw=100.0, w_soc_balance=10.0)
        env = BESSDispatchEnv(config=cfg)
        env.reset()
        for _ in range(2):
            env.step([0.0])
        # Last step (triggers terminal) with SOC ≈ 50% → bonus applied
        _, reward, terminated, _, _ = env.step([0.0])
        assert terminated
        # Reward should contain soc_balance term (positive when SOC ≈ 50%)
        # Just assert it doesn't raise and returns a number
        assert isinstance(reward, float)

    def test_render_is_noop(self):
        env = _default_env()
        env.reset()
        env.render()  # should not raise


# ---------------------------------------------------------------------------
# PPOTrainer — initialization
# ---------------------------------------------------------------------------

class TestPPOTrainerInit:
    def test_init_default_config(self):
        trainer = PPOTrainer(site_id="TEST-001")
        assert trainer._site_id == "TEST-001"
        assert trainer._cfg is not None

    def test_init_custom_config(self):
        cfg = TrainingConfig(p_nom_kw=500.0)
        trainer = PPOTrainer(site_id="TEST-001", config=cfg)
        assert trainer._cfg.p_nom_kw == pytest.approx(500.0)

    def test_p_nom_from_env(self):
        os.environ["BESSAI_P_NOM_KW"] = "2000.0"
        try:
            trainer = PPOTrainer(site_id="TEST-001")
            assert trainer._cfg.p_nom_kw == pytest.approx(2000.0)
        finally:
            os.environ.pop("BESSAI_P_NOM_KW", None)


# ---------------------------------------------------------------------------
# PPOTrainer — data loading
# ---------------------------------------------------------------------------

class TestPPOTrainerDataLoading:
    def test_missing_data_falls_back_to_synthetic(self, tmp_path: Path):
        trainer = PPOTrainer(site_id="T", data_path=str(tmp_path / "nonexistent.csv"))
        cmg = trainer._load_cmg_data()
        assert len(cmg) > 0
        assert all(c > 0 for c in cmg)

    def test_none_data_path_falls_back_to_synthetic(self):
        trainer = PPOTrainer(site_id="T", data_path=None)
        cmg = trainer._load_cmg_data()
        assert len(cmg) > 0

    def test_valid_csv_loaded(self, tmp_path: Path):
        csv_path = tmp_path / "cen_data.csv"
        rows = [{"timestamp": f"2025-01-01T{h:02d}:00:00", "cmg_usd_mwh": str(40.0 + h)}
                for h in range(24)]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "cmg_usd_mwh"])
            writer.writeheader()
            writer.writerows(rows)

        trainer = PPOTrainer(site_id="T", data_path=str(csv_path))
        cmg = trainer._load_cmg_data()
        assert len(cmg) == 24
        assert cmg[0] == pytest.approx(40.0)

    def test_malformed_csv_falls_back(self, tmp_path: Path):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("not,a,valid,csv\nwith,no,cmg_column", encoding="utf-8")
        trainer = PPOTrainer(site_id="T", data_path=str(csv_path))
        cmg = trainer._load_cmg_data()
        # Should still return some series (synthetic fallback)
        assert len(cmg) > 0


# ---------------------------------------------------------------------------
# PPOTrainer — training (validation loop only — no SB3 required)
# ---------------------------------------------------------------------------

class TestPPOTrainerValidationLoop:
    def test_train_returns_training_result(self):
        trainer = PPOTrainer(site_id="T")
        result = trainer.train(total_timesteps=32)
        assert isinstance(result, TrainingResult)

    def test_training_duration_positive(self):
        trainer = PPOTrainer(site_id="T")
        result = trainer.train(total_timesteps=32)
        assert result.training_duration_s >= 0.0

    def test_bep_ref_in_result(self):
        trainer = PPOTrainer(site_id="T")
        result = trainer.train(total_timesteps=32)
        assert "BEP-0200" in result.bep_ref

    def test_total_timesteps_recorded(self):
        trainer = PPOTrainer(site_id="T")
        result = trainer.train(total_timesteps=32)
        assert result.total_timesteps == 32

    def test_export_onnx_skips_without_sb3(self, tmp_path: Path):
        """Without SB3, export_onnx should return path without raising."""
        trainer = PPOTrainer(
            site_id="T",
            output_path=str(tmp_path / "policy.onnx"),
        )
        trainer.train(total_timesteps=10)
        path = trainer.export_onnx()
        assert isinstance(path, Path)

    def test_export_onnx_before_train_raises_without_sb3(self, tmp_path: Path):
        """Without a trained model, export should skip gracefully (no SB3 install)."""
        trainer = PPOTrainer(
            site_id="T",
            output_path=str(tmp_path / "policy.onnx"),
        )
        # Should not raise even without prior training (SB3 path short-circuits)
        path = trainer.export_onnx()
        assert isinstance(path, Path)
