"""
scripts/train_drl_agent.py
==========================
BESSAI Edge Gateway — BEP-0200: DRL Arbitrage Agent Training CLI.

Usage
-----
Basic training with synthetic CMg profile:
    python scripts/train_drl_agent.py

Training with real CMg data from bessai-cen-data:
    python scripts/train_drl_agent.py \\
        --cmg-csv path/to/cmg_data.csv \\
        --capacity-kwh 200 \\
        --max-power-kw 100 \\
        --iterations 300 \\
        --out models/drl_arbitrage_v2.onnx

Benchmark mode (compare DRL vs rule-based on test day):
    python scripts/train_drl_agent.py --benchmark-only \\
        --cmg-csv path/to/cmg_test.csv

CSV format for --cmg-csv:
    One column of CMg values in USD/MWh, 5-minute intervals, 288 rows per day.
    Header optional. Example:
        cmg_usd_mwh
        12.5
        14.2
        ...

Environment:
    This script requires Ray RLlib for training.
    Install: pip install "ray[rllib]" onnx torch onnxruntime
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Add project root to path for src.* imports
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def _load_cmg_csv(path: str) -> np.ndarray:
    """Load CMg prices from CSV file.

    Accepts files with or without headers. Returns a 1-D float32 array.
    """
    import csv

    prices: list[float] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            cell = row[0].strip()
            try:
                prices.append(float(cell))
            except ValueError:
                # Skip header row or non-numeric lines
                continue

    if not prices:
        raise ValueError(f"No numeric data found in {path}")

    return np.array(prices, dtype=np.float32)


def _run_benchmark(
    cmg_profile: np.ndarray | None,
    capacity_kwh: float,
    max_power_kw: float,
    onnx_path: str | None,
) -> None:
    """Run A/B benchmark: DRL vs. rule-based policy for one trading day."""
    from src.agents.arbitrage_policy import ArbitragePolicy
    from src.agents.bess_rl_env import BESSArbitrageEnv
    from src.agents.drl_agent import ONNXArbitrageAgent

    env_kwargs = {
        "capacity_kwh": capacity_kwh,
        "max_power_kw": max_power_kw,
        "noise_std": 0.0,  # deterministic eval
    }
    if cmg_profile is not None:
        env_kwargs["cmg_profile"] = cmg_profile

    results: dict[str, float] = {}

    # Rule-based policy
    policy = ArbitragePolicy()
    env = BESSArbitrageEnv(**env_kwargs)
    obs, _ = env.reset(seed=42)
    total_reward = 0.0
    step = 0
    while True:
        action, _ = policy.predict(obs)
        obs, reward, done, _, _ = env.step(np.array([action], dtype=np.float32))
        total_reward += float(reward)
        step += 1
        if done:
            break
    results["rule_based"] = total_reward

    # ONNX DRL agent (if available)
    if onnx_path and Path(onnx_path).exists():
        agent = ONNXArbitrageAgent(onnx_path, fallback=policy)
        env2 = BESSArbitrageEnv(**env_kwargs)
        obs2, _ = env2.reset(seed=42)
        total_reward_drl = 0.0
        while True:
            action_drl, _ = agent.predict(obs2)
            obs2, reward2, done2, _, _ = env2.step(np.array([action_drl], dtype=np.float32))
            total_reward_drl += float(reward2)
            if done2:
                break
        results["drl_onnx"] = total_reward_drl
    else:
        print(f"[WARN] ONNX model not found at {onnx_path!r} — skipping DRL eval.")

    # Print results
    print("\n" + "=" * 60)
    print("BESSAI BEP-0200 — DRL vs. Rule-Based Benchmark")
    print("=" * 60)
    for name, reward in results.items():
        print(f"  {name:<20s}  Total reward: {reward:+.4f} USD")

    if "drl_onnx" in results and "rule_based" in results:
        rb = results["rule_based"]
        drl = results["drl_onnx"]
        uplift = ((drl - rb) / abs(rb) * 100) if rb != 0 else 0.0
        print(f"\n  DRL uplift vs rule-based: {uplift:+.1f}%")
        print("  Target: +25 to +35%")
    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate BESSAI DRL Arbitrage Agent (BEP-0200)"
    )
    parser.add_argument(
        "--cmg-csv",
        default=None,
        help="Path to CSV file with CMg prices (USD/MWh, 5-min intervals)",
    )
    parser.add_argument("--capacity-kwh", type=float, default=200.0, help="Battery capacity (kWh)")
    parser.add_argument("--max-power-kw", type=float, default=100.0, help="Max power (kW)")
    parser.add_argument("--iterations", type=int, default=200, help="RLlib training iterations")
    parser.add_argument(
        "--out",
        default="models/drl_arbitrage_v1.onnx",
        help="Output path for ONNX model",
    )
    parser.add_argument(
        "--checkpoint-dir",
        default="models/checkpoints/drl_arbitrage",
        help="Directory for RLlib checkpoints",
    )
    parser.add_argument(
        "--benchmark-only",
        action="store_true",
        help="Skip training — run benchmark with existing ONNX model",
    )
    parser.add_argument(
        "--stop-reward",
        type=float,
        default=None,
        help="Stop training when mean episode reward exceeds this value",
    )
    args = parser.parse_args()

    # Load CMg data
    cmg_profile: np.ndarray | None = None
    if args.cmg_csv:
        print(f"[INFO] Loading CMg data from: {args.cmg_csv}")
        cmg_profile = _load_cmg_csv(args.cmg_csv)
        print(f"[INFO] Loaded {len(cmg_profile)} steps | "
              f"CMg range: {cmg_profile.min():.1f} – {cmg_profile.max():.1f} USD/MWh | "
              f"mean: {cmg_profile.mean():.1f}")

    if args.benchmark_only:
        _run_benchmark(cmg_profile, args.capacity_kwh, args.max_power_kw, args.out)
        return

    # Training
    try:
        from src.agents.drl_agent import export_onnx, train_ppo
    except ImportError as exc:
        print(f"[ERROR] Missing dependency: {exc}")
        print("[INFO]  Install with: pip install 'ray[rllib]' onnx torch onnxruntime")
        sys.exit(1)

    print(f"[INFO] Starting PPO training — {args.iterations} iterations")
    checkpoint = train_ppo(
        cmg_profile=cmg_profile,
        capacity_kwh=args.capacity_kwh,
        max_power_kw=args.max_power_kw,
        num_iterations=args.iterations,
        checkpoint_dir=args.checkpoint_dir,
        stop_reward=args.stop_reward,
    )
    print(f"[INFO] Training complete. Checkpoint: {checkpoint}")

    # Export to ONNX
    print(f"[INFO] Exporting to ONNX: {args.out}")
    onnx_path = export_onnx(checkpoint, output_path=args.out)
    print(f"[INFO] ONNX model saved: {onnx_path}")

    # Benchmark after training
    _run_benchmark(cmg_profile, args.capacity_kwh, args.max_power_kw, str(onnx_path))


if __name__ == "__main__":
    main()
