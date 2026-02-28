#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
tests/test_ppo_trainer.py
Tests for BEP-0200 Phase 3 — PPO training pipeline.
"""

from __future__ import annotations

import pytest

from src.core.ppo_trainer import (
    BESSDispatchEnv,
    PPOTrainer,
    TrainingConfig,
)


@pytest.fixture
def cfg() -> TrainingConfig:
    return TrainingConfig(
        p_nom_kw=1000.0,
        max_episode_steps=96,
        total_timesteps=1_000,  # tiny for tests
    )


@pytest.fixture
def env(cfg: TrainingConfig) -> BESSDispatchEnv:
    return BESSDispatchEnv(config=cfg)


# ---------------------------------------------------------------------------
# Environment tests
# ---------------------------------------------------------------------------

class TestBESSDispatchEnv:
    def test_reset_returns_obs_and_info(self, env: BESSDispatchEnv) -> None:
        obs, info = env.reset()
        assert obs is not None
        assert isinstance(info, dict)

    def test_initial_soc_is_50(self, env: BESSDispatchEnv) -> None:
        env.reset()
        assert env._soc == pytest.approx(50.0)

    def test_step_returns_five_tuple(self, env: BESSDispatchEnv) -> None:
        env.reset()
        obs, reward, terminated, truncated, info = env.step([0.5])
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert "soc" in info

    def test_episode_terminates_at_max_steps(self, env: BESSDispatchEnv, cfg: TrainingConfig) -> None:
        env.reset()
        terminated = False
        steps = 0
        while not terminated:
            _, _, terminated, _, _ = env.step([0.0])
            steps += 1
            if steps > cfg.max_episode_steps + 5:
                break
        assert terminated
        assert steps == cfg.max_episode_steps

    def test_soc_clamped_to_limits(self, env: BESSDispatchEnv) -> None:
        env.reset()
        # Apply extreme discharge — SOC should stay within limits
        for _ in range(50):
            env.step([1.0])  # full discharge
        assert env._soc >= env._cfg.soc_min - 1.0  # tolerance for rounding

    def test_synthetic_cmg_positive(self, env: BESSDispatchEnv) -> None:
        assert all(v > 0 for v in env._cmg)
        assert len(env._cmg) > 0


# ---------------------------------------------------------------------------
# Trainer tests
# ---------------------------------------------------------------------------

class TestPPOTrainer:
    def test_train_validation_loop_completes(self, cfg: TrainingConfig) -> None:
        trainer = PPOTrainer(
            site_id="SITE-CL-TEST",
            data_path=None,  # synthetic data
            config=cfg,
        )
        result = trainer.train(total_timesteps=500)
        assert result.total_timesteps == 500
        assert result.training_duration_s > 0
        assert result.bep_ref.startswith("BEP-0200")

    def test_train_with_missing_csv_uses_synthetic(self, cfg: TrainingConfig) -> None:
        trainer = PPOTrainer(
            site_id="SITE-CL-TEST",
            data_path="nonexistent_data.csv",
            config=cfg,
        )
        result = trainer.train(total_timesteps=200)
        assert result is not None  # should not raise

    def test_training_config_defaults_valid(self) -> None:
        cfg = TrainingConfig()
        assert 0 < cfg.learning_rate < 1
        assert cfg.gamma <= 1.0
        assert cfg.total_timesteps > 0
        assert cfg.soc_min < cfg.soc_max
