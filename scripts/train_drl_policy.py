"""
scripts/train_drl_policy.py
============================
BESSAI Edge Gateway — DRL Dispatch Policy Training (Ray RLlib PPO).

Trains a Proximal Policy Optimization (PPO) agent on the BESSEnv
Gymnasium environment. After training, exports the policy to ONNX format
so it can be deployed to the ONNXDispatcher on edge devices.

Requirements (training environment only):
    pip install ray[rllib] gymnasium torch onnx

Usage:
    python scripts/train_drl_policy.py --iterations 100 --out models/dispatch_policy.onnx
    python scripts/train_drl_policy.py --iterations 200 --checkpoint-dir runs/

Notes:
    - Training runs on the host (not on the edge device).
    - The resulting ONNX model is loaded by ONNXDispatcher at the edge.
    - Edge devices have no Ray/PyTorch dependency at inference time.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train BESSAI DRL dispatch policy with Ray RLlib PPO."
    )
    parser.add_argument(
        "--iterations", type=int, default=100,
        help="Number of PPO training iterations (default: 100)"
    )
    parser.add_argument(
        "--out", type=str, default="models/dispatch_policy.onnx",
        help="Output path for the exported ONNX model"
    )
    parser.add_argument(
        "--checkpoint-dir", type=str, default="runs/drl",
        help="Directory to save Ray RLlib checkpoints"
    )
    parser.add_argument(
        "--workers", type=int, default=2,
        help="Number of Ray rollout workers (default: 2)"
    )
    parser.add_argument(
        "--capacity-kwh", type=float, default=100.0,
        help="BESS capacity in kWh for simulation (default: 100)"
    )
    parser.add_argument(
        "--max-power-kw", type=float, default=50.0,
        help="Maximum BESS power in kW (default: 50)"
    )
    return parser.parse_args()


def check_deps() -> bool:
    """Check that all training dependencies are available."""
    missing = []
    for pkg in ["ray", "torch", "gymnasium", "onnx"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[ERROR] Missing training dependencies: {', '.join(missing)}")
        print("Install with: pip install ray[rllib] torch gymnasium onnx")
        return False
    return True


def train(args: argparse.Namespace) -> None:
    """Run PPO training loop and export ONNX model."""
    import ray
    from ray.rllib.algorithms.ppo import PPOConfig
    import torch

    # Register the BESSEnv with Ray
    from src.simulation.bess_env import BESSEnv

    ray.init(ignore_reinit_error=True)

    config = (
        PPOConfig()
        .environment(env=BESSEnv, env_config={
            "capacity_kwh": args.capacity_kwh,
            "max_power_kw": args.max_power_kw,
        })
        .rollouts(num_rollout_workers=args.workers)
        .training(
            lr=3e-4,
            gamma=0.99,
            lambda_=0.95,
            clip_param=0.2,
            train_batch_size=4096,
            sgd_minibatch_size=256,
            num_sgd_iter=10,
        )
        .framework("torch")
    )

    algo = config.build()
    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    print(f"[BESSAI] Starting PPO training: {args.iterations} iterations, "
          f"{args.workers} workers, capacity={args.capacity_kwh}kWh")

    best_reward = float("-inf")
    for i in range(1, args.iterations + 1):
        result = algo.train()
        reward = result["episode_reward_mean"]
        if i % 10 == 0:
            print(f"  [Iter {i:04d}] mean_reward={reward:.2f}")
        if reward > best_reward:
            best_reward = reward
            algo.save(str(checkpoint_dir / f"checkpoint_{i:04d}"))

    print(f"[BESSAI] Training complete. Best reward: {best_reward:.2f}")

    # Export policy network to ONNX
    _export_to_onnx(algo, args.out)
    algo.stop()
    ray.shutdown()


def _export_to_onnx(algo, output_path: str) -> None:
    """Export the trained policy to ONNX format for edge deployment."""
    import torch
    import onnx

    policy = algo.get_policy()
    model = policy.model

    dummy_input = torch.zeros(1, 8, dtype=torch.float32)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        (dummy_input, []),
        str(output_file),
        opset_version=17,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    )

    onnx.checker.check_model(str(output_file))
    print(f"[BESSAI] ONNX model exported: {output_file}")
    print("[BESSAI] Deploy with: cp models/dispatch_policy.onnx /edge/models/")


def main() -> None:
    args = parse_args()
    if not check_deps():
        sys.exit(1)
    train(args)


if __name__ == "__main__":
    main()
