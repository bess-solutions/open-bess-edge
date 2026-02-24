"""
scripts/train_drl.py
=====================
BESSAI Edge Gateway — DRL Training Entry Point.

Training a PPO agent on BESSArbitrageEnv (Chilean CMg, 5-min intervals)
and exporting the policy to ONNX for edge deployment.

Usage::

    # Train with synthetic Chilean CMg profile (default):
    python scripts/train_drl.py

    # Train with real CMg data from CSV:
    python scripts/train_drl.py --cmg-csv data/cmg_2025.csv

    # Quick smoke test (10 iterations):
    python scripts/train_drl.py --iterations 10 --output models/drl_test.onnx

    # Full training run:
    python scripts/train_drl.py --iterations 500 --stop-reward 5.0

Environment::
    pip install "ray[rllib]" torch onnx gymnasium numpy

The script will:
1. Build or load the CMg price profile.
2. Train a PPO agent via Ray RLlib.
3. Export the best checkpoint to ONNX.
4. Run the BenchmarkSuite to compare DRL vs rule-based vs MILP.
5. Print the benchmark report.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("train_drl")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train BESSAI DRL arbitrage agent and benchmark vs baselines"
    )
    p.add_argument(
        "--cmg-csv",
        type=Path,
        help="CSV with CMg price profile. Columns: timestamp,cmg_usd_mwh",
        default=None,
    )
    p.add_argument(
        "--capacity-kwh",
        type=float,
        default=200.0,
        help="Battery capacity in kWh (default: 200)",
    )
    p.add_argument(
        "--max-power-kw",
        type=float,
        default=100.0,
        help="Maximum power in kW (default: 100)",
    )
    p.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Number of PPO training iterations (default: 200)",
    )
    p.add_argument(
        "--stop-reward",
        type=float,
        default=None,
        help="Early stopping reward threshold (default: None)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("models/drl_arbitrage_v2.onnx"),
        help="Output ONNX model path (default: models/drl_arbitrage_v2.onnx)",
    )
    p.add_argument(
        "--benchmark-episodes",
        type=int,
        default=10,
        help="Number of benchmark episodes (default: 10)",
    )
    p.add_argument(
        "--skip-training",
        action="store_true",
        help="Skip training and only run benchmark (requires existing ONNX model)",
    )
    p.add_argument(
        "--benchmark-only",
        action="store_true",
        help="Run benchmark with rule-based and MILP only (no DRL)",
    )
    return p.parse_args()


def _load_cmg_profile(csv_path: Path | None) -> np.ndarray:
    """Load or generate CMg profile."""
    if csv_path is None:
        from src.agents.bess_rl_env import _build_synthetic_cmg_profile
        profile = _build_synthetic_cmg_profile()
        log.info(
            "Using synthetic Chilean CMg profile "
            f"({len(profile)} steps = {len(profile)*5//60:.0f}h at 5-min)"
        )
        return profile

    try:
        import csv
        prices = []
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            col = "cmg_usd_mwh"
            for row in reader:
                prices.append(float(row.get(col, row.get("price", 0.0))))
        profile = np.array(prices, dtype=np.float32)
        log.info(
            f"Loaded real CMg profile from {csv_path}: "
            f"{len(profile)} steps, "
            f"avg={float(np.mean(profile)):.1f} USD/MWh, "
            f"max={float(np.max(profile)):.1f} USD/MWh"
        )
        return profile
    except Exception as exc:
        log.warning(f"Failed to load CMg CSV ({exc}), using synthetic profile")
        from src.agents.bess_rl_env import _build_synthetic_cmg_profile
        return _build_synthetic_cmg_profile()


def _train(args: argparse.Namespace, cmg_profile: np.ndarray) -> str | None:
    """Train PPO agent and return checkpoint path."""
    log.info("=" * 60)
    log.info("BESSAI DRL Training — Phase 1: Edge DRL Killer")
    log.info(f"  Battery: {args.capacity_kwh} kWh / {args.max_power_kw} kW")
    log.info(f"  Iterations: {args.iterations}")
    log.info(f"  Output: {args.output}")
    log.info("=" * 60)

    try:
        from src.agents.drl_agent import train_ppo
    except ImportError as exc:
        log.error(f"Ray RLlib not available: {exc}")
        log.error("Install: pip install 'ray[rllib]'")
        return None

    checkpoint_path = train_ppo(
        cmg_profile=cmg_profile,
        capacity_kwh=args.capacity_kwh,
        max_power_kw=args.max_power_kw,
        num_iterations=args.iterations,
        checkpoint_dir=str(args.output.parent / "checkpoints"),
        stop_reward=args.stop_reward,
    )
    log.info(f"✅ Training complete. Checkpoint: {checkpoint_path}")
    return checkpoint_path


def _export_onnx(checkpoint_path: str, output: Path) -> Path | None:
    """Export PPO policy to ONNX."""
    try:
        from src.agents.drl_agent import export_onnx
        onnx_path = export_onnx(checkpoint_path=checkpoint_path, output_path=str(output))
        log.info(f"✅ ONNX model exported: {onnx_path} ({onnx_path.stat().st_size/1024:.0f} KB)")
        return onnx_path
    except Exception as exc:
        log.error(f"ONNX export failed: {exc}")
        return None


def _run_benchmark(
    args: argparse.Namespace,
    cmg_profile: np.ndarray,
    drl_onnx_path: Path | None = None,
) -> None:
    """Run benchmark suite and print report."""
    from src.agents.benchmark_suite import BenchmarkSuite

    log.info("=" * 60)
    log.info("BESSAI Open Benchmark Suite — BESS Dispatch Strategies")
    log.info("=" * 60)

    suite = BenchmarkSuite(
        capacity_kwh=args.capacity_kwh,
        max_power_kw=args.max_power_kw,
        cmg_profile=cmg_profile,
    )

    extra_agents = {}
    if drl_onnx_path and drl_onnx_path.exists():
        try:
            from src.agents.drl_agent import ONNXArbitrageAgent
            drl_agent = ONNXArbitrageAgent(model_path=drl_onnx_path)
            drl_agent.name = "drl_bessai_v2"  # type: ignore[attr-defined]
            extra_agents["drl_bessai_v2"] = drl_agent
            log.info(f"DRL agent loaded from {drl_onnx_path}")
        except Exception as exc:
            log.warning(f"Could not load DRL agent: {exc}")

    report = suite.run(
        n_episodes=args.benchmark_episodes,
        agents=extra_agents,
        include_milp=True,
    )

    print("\n" + str(report))

    # Save as JSON for CI artifacts
    output_json = args.output.parent / "benchmark_results.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w") as f:
        json.dump(report.summary(), f, indent=2)
    log.info(f"Benchmark results saved to {output_json}")

    # Compute and log optimality gaps
    gaps = report.optimality_gap(baseline_strategy="milp")
    if "drl_bessai_v2" in gaps:
        drl_gap = gaps["drl_bessai_v2"]
        rb_gap = gaps.get("rule_based", 100.0)
        improvement = rb_gap - drl_gap
        log.info(f"\n🎯 DRL optimality gap vs MILP: {drl_gap:.1f}%")
        log.info(f"📈 DRL improvement over rule-based: +{improvement:.1f}%")
        if drl_gap < 20.0:
            log.info("✅ TARGET ACHIEVED: DRL within 20% of MILP optimum!")
        else:
            log.info("⚠️  Train more iterations to close the gap further.")


def main() -> int:
    args = _parse_args()
    cmg_profile = _load_cmg_profile(args.cmg_csv)

    checkpoint_path = None
    onnx_path = None

    if not args.skip_training and not args.benchmark_only:
        checkpoint_path = _train(args, cmg_profile)
        if checkpoint_path:
            onnx_path = _export_onnx(checkpoint_path, args.output)

    elif args.output.exists():
        onnx_path = args.output
        log.info(f"Using existing ONNX model: {onnx_path}")

    _run_benchmark(args, cmg_profile, drl_onnx_path=onnx_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
