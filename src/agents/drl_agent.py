# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/drl_agent.py
=======================
BESSAI Edge Gateway — BEP-0200: DRL Arbitrage Agent.

Provides:
1. ``train_ppo`` — Train a PPO agent via Ray RLlib on BESSArbitrageEnv.
2. ``export_onnx`` — Export a trained RLlib policy to ONNX for edge inference.
3. ``ONNXArbitrageAgent`` — Edge runtime agent wrapping ONNX Runtime.

Graceful degradation chain (in order):
    ONNXArbitrageAgent  →  ArbitragePolicy (rule-based)  →  safety.py

Dependencies (optional, only needed for training):
    ray[rllib] ≥ 2.9   — install with: pip install "ray[rllib]"
    onnx ≥ 1.15        — install with: pip install onnx
    onnxruntime ≥ 1.17 — install with: pip install onnxruntime

ONNX Runtime is used for edge inference (no training deps needed at runtime).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)  # mypy-friendly fallback ref — not used at runtime

# ---------------------------------------------------------------------------
# Optional Ray RLlib import (only for training, not required at runtime)
# ---------------------------------------------------------------------------
try:
    import ray
    from ray import tune
    from ray.rllib.algorithms.ppo import PPOConfig
    from ray.rllib.policy.policy import Policy

    _RAY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _RAY_AVAILABLE = False
    ray = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Optional ONNX Runtime import (for edge inference)
# ---------------------------------------------------------------------------
try:
    import onnxruntime as ort  # type: ignore[import]

    _ORT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ORT_AVAILABLE = False
    ort = None  # type: ignore[assignment]

__all__ = ["train_ppo", "export_onnx", "ONNXArbitrageAgent"]

# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

_DEFAULT_PPO_CONFIG: dict[str, Any] = {
    # Architecture (small enough for edge inference ≤ 50 MB)
    "model": {
        "fcnet_hiddens": [256, 256],
        "fcnet_activation": "tanh",
    },
    # Training hyperparams (calibrated for BESSArbitrageEnv)
    "lr": 3e-4,
    "gamma": 0.99,
    "lambda_": 0.95,
    "clip_param": 0.2,
    "num_sgd_iter": 10,
    "train_batch_size": 4000,
    "sgd_minibatch_size": 512,
    # Rollout workers
    "num_env_runners": 2,
    "rollout_fragment_length": "auto",
    # Evaluation
    "evaluation_interval": 10,
    "evaluation_duration": 5,
}


def train_ppo(
    cmg_profile: np.ndarray | None = None,
    capacity_kwh: float = 200.0,
    max_power_kw: float = 100.0,
    num_iterations: int = 200,
    checkpoint_dir: str = "models/checkpoints/drl_arbitrage",
    stop_reward: float | None = None,
    extra_config: dict[str, Any] | None = None,
) -> str:
    """Train a PPO agent on BESSArbitrageEnv and return checkpoint path.

    Parameters
    ----------
    cmg_profile:
        Optional 1-D numpy array of CMg prices (USD/MWh) for one day.
        If ``None``, the synthetic Chilean profile is used.
    capacity_kwh, max_power_kw:
        Battery configuration forwarded to BESSArbitrageEnv.
    num_iterations:
        Number of Ray RLlib training iterations.
    checkpoint_dir:
        Directory where RLlib saves checkpoints.
    stop_reward:
        If set, stop training when mean episode reward exceeds this value.
    extra_config:
        Additional RLlib config overrides merged on top of defaults.

    Returns
    -------
    str
        Path to the best checkpoint directory.

    Raises
    ------
    ImportError
        If Ray RLlib is not installed.
    """
    if not _RAY_AVAILABLE:
        raise ImportError(
            "Ray RLlib is required for training. Install with: pip install 'ray[rllib]'"
        )

    # Lazy import to avoid circular dependency at module level
    from src.agents.bess_rl_env import BESSArbitrageEnv

    if not ray.is_initialized():  # type: ignore[union-attr]
        ray.init(ignore_reinit_error=True)  # type: ignore[union-attr]

    env_config: dict[str, Any] = {
        "capacity_kwh": capacity_kwh,
        "max_power_kw": max_power_kw,
    }
    if cmg_profile is not None:
        env_config["cmg_profile"] = cmg_profile.tolist()

    cfg = _DEFAULT_PPO_CONFIG.copy()
    if extra_config:
        cfg.update(extra_config)

    algo_config = (
        PPOConfig()  # type: ignore[union-attr]
        .environment(BESSArbitrageEnv, env_config=env_config)
        .training(**{k: v for k, v in cfg.items() if k not in {"model"}})
        .rl_module(model_config_dict=cfg.get("model", {}))
        .resources(num_gpus=0)
    )

    stop_criteria: dict[str, Any] = {"training_iteration": num_iterations}
    if stop_reward is not None:
        stop_criteria["env_runners/episode_reward_mean"] = stop_reward

    results = tune.run(  # type: ignore[union-attr]
        "PPO",
        config=algo_config.to_dict(),
        stop=stop_criteria,
        storage_path=checkpoint_dir,
        checkpoint_at_end=True,
        verbose=1,
    )

    best = results.get_best_result(metric="env_runners/episode_reward_mean", mode="max")
    checkpoint_path = str(best.checkpoint.path)
    log.info("drl_agent.training_complete", checkpoint=checkpoint_path)
    return checkpoint_path


# ---------------------------------------------------------------------------
# ONNX Export
# ---------------------------------------------------------------------------


def export_onnx(
    checkpoint_path: str,
    output_path: str = "models/drl_arbitrage_v1.onnx",
    obs_dim: int = 8,
) -> Path:
    """Export an RLlib PPO policy to ONNX format for edge inference.

    Parameters
    ----------
    checkpoint_path:
        Path to the RLlib checkpoint directory returned by ``train_ppo``.
    output_path:
        Where to save the ONNX model.
    obs_dim:
        Observation space dimension (must match BESSArbitrageEnv).

    Returns
    -------
    Path
        Absolute path of the saved ONNX file.

    Raises
    ------
    ImportError
        If Ray RLlib or onnx is not installed.
    """
    if not _RAY_AVAILABLE:
        raise ImportError("Ray RLlib required for export.")

    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise ImportError("PyTorch required for ONNX export.") from exc

    policy: Policy = Policy.from_checkpoint(checkpoint_path)  # type: ignore[union-attr]

    # Extract PyTorch model from the policy
    model = policy.model  # type: ignore[attr-defined]
    model.eval()

    dummy_obs = torch.zeros(1, obs_dim, dtype=torch.float32)
    state = [torch.zeros(1, 1, dtype=torch.float32)]  # dummy LSTM state

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with torch.no_grad():
        torch.onnx.export(
            model,
            (dummy_obs, state, [1]),
            str(out_path),
            opset_version=17,
            input_names=["obs", "state_ins", "seq_lens"],
            output_names=["action_dist_inputs", "state_outs"],
            dynamic_axes={"obs": {0: "batch_size"}},
        )

    log.info(
        "drl_agent.onnx_exported",
        path=str(out_path),
        size_mb=round(out_path.stat().st_size / 1e6, 2),
    )
    return out_path


# ---------------------------------------------------------------------------
# Edge Inference — ONNX Runtime Agent
# ---------------------------------------------------------------------------


class ONNXArbitrageAgent:
    """Edge runtime DRL agent using ONNX Runtime for inference.

    Loads a pre-exported ONNX model and provides a ``predict`` method
    compatible with the ``ArbitragePolicy`` interface.

    This class requires only ``onnxruntime`` — no Ray, no PyTorch needed.

    Parameters
    ----------
    model_path:
        Path to the ONNX model file.
    fallback:
        Optional fallback policy to use if ONNX inference fails.
        Should implement ``predict(obs) -> tuple[float, dict]``.

    Usage::

        agent = ONNXArbitrageAgent("models/drl_arbitrage_v1.onnx")
        p_pu, info = agent.predict(observation)
        power_kw = p_pu * max_power_kw
    """

    def __init__(
        self,
        model_path: str | Path,
        fallback: Any | None = None,
    ) -> None:
        self._model_path = Path(model_path)
        self._fallback = fallback
        self._session: Any | None = None

        if not _ORT_AVAILABLE:  # pragma: no cover
            log.warning(
                "drl_agent.ort_unavailable",
                reason="onnxruntime not installed — agent will always use fallback",
            )
            return

        if not self._model_path.exists():
            log.warning(
                "drl_agent.model_not_found",
                path=str(self._model_path),
                reason="ONNX model not found — using fallback",
            )
            return

        try:
            session_opts = ort.SessionOptions()  # type: ignore[union-attr]
            session_opts.intra_op_num_threads = 1  # edge: single-threaded
            session_opts.inter_op_num_threads = 1
            self._session = ort.InferenceSession(  # type: ignore[union-attr]
                str(self._model_path),
                sess_options=session_opts,
                providers=["CPUExecutionProvider"],
            )
            log.info("drl_agent.onnx_loaded", path=str(self._model_path))
        except Exception as exc:  # noqa: BLE001
            log.error("drl_agent.onnx_load_failed", error=str(exc))
            self._session = None

    @property
    def is_available(self) -> bool:
        """Return True if the ONNX session is loaded and ready."""
        return self._session is not None

    def predict(self, obs: np.ndarray) -> tuple[float, dict[str, Any]]:
        """Compute action from observation.

        Parameters
        ----------
        obs:
            1-D float32 array of shape ``(8,)`` — BESSArbitrageEnv observation.

        Returns
        -------
        p_pu : float
            Per-unit power setpoint ∈ [-1, 1].
        info : dict
            Metadata dict with ``source`` key indicating which agent responded.
        """
        if self._session is not None:
            try:
                obs_2d = obs.reshape(1, -1).astype(np.float32)
                feeds = {self._session.get_inputs()[0].name: obs_2d}
                outputs = self._session.run(None, feeds)
                # RLlib PPO output: action_dist_inputs (logits for continuous: [mean, std_log])
                # For Box action: first half of logits = mean, second = log_std
                action_logits = outputs[0][0]  # shape: [2] for 1-d action
                p_pu = float(np.tanh(action_logits[0]))  # squash to [-1, 1]
                return p_pu, {"source": "onnx_drl"}
            except Exception as exc:  # noqa: BLE001
                log.warning("drl_agent.onnx_inference_failed", error=str(exc))

        # Fallback
        if self._fallback is not None:
            return self._fallback.predict(obs)

        # Last resort: hold (no dispatch)
        return 0.0, {"source": "hold_fallback"}
