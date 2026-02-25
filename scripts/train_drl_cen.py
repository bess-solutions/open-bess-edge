"""
scripts/train_drl_cen.py
=========================
BESSAI BEP-0200 Phase 3 — Train DRL Dispatch Policy with Real CEN/SEN CMg Data.

Trains a PPO agent on BESSArbitrageEnvCEN using 48+ days of real price data
from the Chilean Electricity Coordinator (CEN/SEN), Nodo Maitencillo 220 kV.

This script produces a policy capable of scheduling real-market arbitrage
operations, as opposed to the synthetic duck-curve policy from Phase 1/2.

Modes
-----
--dry-run:
    Load dataset, validate env, and exit (for CI, no Ray/PyTorch required).
--iterations N:
    Run N PPO training iterations (default: 200).
--out PATH:
    Export trained ONNX model to PATH (default: models/drl_arbitrage_cen_v1.onnx).

Usage::

    # CI integration test (fast, no Ray):
    python scripts/train_drl_cen.py --dry-run

    # Full training (Ray + PyTorch required):
    python scripts/train_drl_cen.py --iterations 200 --out models/drl_arbitrage_cen_v1.onnx

Output::

    models/drl_arbitrage_cen_v1.onnx          — deployable edge model
    reports/bep0200_phase3_results.json        — training metrics
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BEP-0200 Phase 3: Train BESSAI DRL policy with real CEN/SEN CMg data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate dataset and env only (no Ray/PyTorch required)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Number of PPO training iterations",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="models/drl_arbitrage_cen_v1.onnx",
        help="Output path for the ONNX edge model",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default="runs/drl_cen",
        help="Ray checkpoint directory",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Ray rollout worker count",
    )
    parser.add_argument(
        "--capacity-kwh",
        type=float,
        default=200.0,
        help="BESS capacity (kWh)",
    )
    parser.add_argument(
        "--max-power-kw",
        type=float,
        default=100.0,
        help="Maximum BESS power (kW)",
    )
    parser.add_argument(
        "--episode-days",
        type=int,
        default=1,
        help="Trading days per episode",
    )
    parser.add_argument(
        "--cmg-data",
        type=str,
        default="dashboard/data/cmg_maitencillo.json",
        help="Path to CEN/SEN CMg JSON dataset",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default="reports",
        help="Directory for training metrics output",
    )
    return parser.parse_args()


def validate_dataset(cmg_data_path: str) -> dict:
    """Load and validate the CMg dataset; returns summary statistics."""
    from src.agents.bess_rl_env_cen import load_cmg_dataset

    print(f"[BEP-0200 F3] Loading CMg dataset: {cmg_data_path}")
    days = load_cmg_dataset(cmg_data_path)

    import numpy as np

    all_prices = np.concatenate(days)
    stats = {
        "n_days": len(days),
        "steps_per_day": len(days[0]),
        "total_steps": len(all_prices),
        "cmg_mean_usd_mwh": float(np.mean(all_prices)),
        "cmg_std_usd_mwh": float(np.std(all_prices)),
        "cmg_min_usd_mwh": float(np.min(all_prices)),
        "cmg_max_usd_mwh": float(np.max(all_prices)),
        "cmg_spread_usd_mwh": float(np.max(all_prices) - np.min(all_prices)),
    }

    print(
        f"[BEP-0200 F3] Dataset OK: {stats['n_days']} days × {stats['steps_per_day']} steps "
        f"| CMg: {stats['cmg_min_usd_mwh']:.1f}–{stats['cmg_max_usd_mwh']:.1f} USD/MWh "
        f"(spread: {stats['cmg_spread_usd_mwh']:.1f} USD/MWh)"
    )
    return stats


def validate_env(args: argparse.Namespace) -> None:
    """Run one episode of BESSArbitrageEnvCEN to validate environment."""
    try:
        import gymnasium  # noqa: F401
    except ImportError:
        print("[BEP-0200 F3] --dry-run: gymnasium not installed (skipping env step).")
        return

    from src.agents.bess_rl_env_cen import BESSArbitrageEnvCEN

    env = BESSArbitrageEnvCEN(
        cmg_data_path=args.cmg_data,
        capacity_kwh=args.capacity_kwh,
        max_power_kw=args.max_power_kw,
        episode_days=args.episode_days,
    )

    obs, info = env.reset(seed=42)
    assert obs.shape == (8,), f"Unexpected obs shape: {obs.shape}"
    assert all(0.0 <= v <= 1.0 for v in obs), "Observation out of [0, 1] bounds"

    total_reward = 0.0
    n_steps = 0
    terminated = truncated = False

    while not (terminated or truncated):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        n_steps += 1

    print(
        f"[BEP-0200 F3] Env OK: {n_steps} steps/episode | "
        f"total_reward={total_reward:.2f} USD | "
        f"final_soc={info['soc']:.2f} | "
        f"data_source={info.get('data_source', 'unknown')}"
    )


def dry_run(args: argparse.Namespace) -> None:
    """Validate dataset and environment without training."""
    print("[BEP-0200 F3] ── DRY RUN MODE (CI) ──────────────────────────────")
    stats = validate_dataset(args.cmg_data)
    validate_env(args)

    # Save summary
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "mode": "dry_run",
        "phase": "BEP-0200-Phase3",
        "dataset_stats": stats,
        "status": "PASS",
    }
    out_path = reports_dir / "bep0200_phase3_results.json"
    with out_path.open("w") as fh:
        json.dump(summary, fh, indent=2)

    print(f"[BEP-0200 F3] ✅ Dry run passed. Report: {out_path}")


def check_training_deps() -> bool:
    """Verify Ray + PyTorch + ONNX are available."""
    missing = []
    for pkg in ["ray", "torch", "onnx"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[ERROR] Missing training deps: {', '.join(missing)}")
        print("Install with: pip install ray[rllib] torch onnx")
        return False
    return True


def train(args: argparse.Namespace) -> None:
    """Run PPO training and export ONNX model."""
    import ray
    from ray.rllib.algorithms.ppo import PPOConfig

    from src.agents.bess_rl_env_cen import BESSArbitrageEnvCEN

    # Pre-validate dataset
    stats = validate_dataset(args.cmg_data)

    ray.init(ignore_reinit_error=True)

    config = (
        PPOConfig()
        .environment(
            env=BESSArbitrageEnvCEN,
            env_config={
                "cmg_data_path": args.cmg_data,
                "capacity_kwh": args.capacity_kwh,
                "max_power_kw": args.max_power_kw,
                "episode_days": args.episode_days,
            },
        )
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

    print(
        f"[BEP-0200 F3] ── PPO TRAINING START ─────────────────────────────\n"
        f"  Dataset:    {stats['n_days']} days × {stats['steps_per_day']} steps (real CEN data)\n"
        f"  CMg spread: {stats['cmg_spread_usd_mwh']:.1f} USD/MWh\n"
        f"  Iterations: {args.iterations} | Workers: {args.workers}"
    )

    t0 = time.monotonic()
    best_reward = float("-inf")
    rewards_per_iter = []

    for i in range(1, args.iterations + 1):
        result = algo.train()
        reward = result.get("episode_reward_mean", float("-inf"))
        rewards_per_iter.append(reward)

        if i % 20 == 0:
            elapsed = time.monotonic() - t0
            print(
                f"  [Iter {i:04d}/{args.iterations}] "
                f"mean_reward={reward:.2f} USD | elapsed={elapsed:.0f}s"
            )

        if reward > best_reward:
            best_reward = reward
            algo.save(str(checkpoint_dir / f"checkpoint_{i:04d}"))

    elapsed_total = time.monotonic() - t0
    print(
        f"[BEP-0200 F3] Training complete in {elapsed_total:.0f}s | "
        f"Best reward: {best_reward:.2f} USD"
    )

    # Export ONNX
    _export_to_onnx(algo, args.out)
    algo.stop()
    ray.shutdown()

    # Save training report
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "mode": "training",
        "phase": "BEP-0200-Phase3",
        "dataset_stats": stats,
        "training": {
            "iterations": args.iterations,
            "workers": args.workers,
            "best_reward_usd": best_reward,
            "elapsed_s": round(elapsed_total, 1),
            "rewards_per_iter": rewards_per_iter,
        },
        "output_model": args.out,
        "status": "COMPLETE",
    }
    report_path = reports_dir / "bep0200_phase3_results.json"
    with report_path.open("w") as fh:
        json.dump(report, fh, indent=2)

    print(f"[BEP-0200 F3] ✅ Report saved: {report_path}")


def _export_to_onnx(algo, output_path: str) -> None:
    """Export trained PPO policy to ONNX for edge deployment."""
    import torch
    import onnx

    policy = algo.get_policy()
    model = policy.model
    dummy_input = torch.zeros(1, 8, dtype=torch.float32)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        (dummy_input, []),
        str(out),
        opset_version=17,
        input_names=["obs"],
        output_names=["action"],
        dynamic_axes={"obs": {0: "batch"}, "action": {0: "batch"}},
    )
    onnx.checker.check_model(str(out))
    print(f"[BEP-0200 F3] ONNX model exported: {out}")
    print("[BEP-0200 F3] Deploy: cp models/drl_arbitrage_cen_v1.onnx /edge/models/")


def main() -> None:
    args = parse_args()

    if args.dry_run:
        dry_run(args)
        return

    if not check_training_deps():
        sys.exit(1)

    train(args)


if __name__ == "__main__":
    main()
