# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/benchmark_suite.py
==============================
BESSAI Edge Gateway — BEP-0225: Open Benchmark Suite for DRL vs Baselines.

This module provides the definitive benchmark comparing BESSAI's DRL dispatch
agent against all competitor strategies on the SAME price/conditions:

Strategies compared:
    1. **Rule-Based (Threshold)**  — common threshold strategy: charge when price < threshold,
       discharge when price > threshold. Simple but suboptimal.
    2. **MILP Optimal**            — Mathematical optimum for given price profile
       (solving LP relaxation). Theoretical ceiling for any agent.
    3. **DRL Agent (PPO/ONNX)**    — BESSAI's edge ML agent. Goal: >90% of MILP.
    4. **Buy-and-Hold**            — Never dispatch. Zero revenue (baseline).
    5. **Random**                  — Random dispatch. Sanity check / noise floor.

Publication target:
    "BESSAI: Edge DRL for BESS arbitrage in LatAm electricity markets"
    Target: 25-30% revenue improvement over rule-based, <80% of MILP gap.

Usage::

    from src.agents.benchmark_suite import BenchmarkSuite

    suite = BenchmarkSuite(capacity_kwh=200, max_power_kw=100)
    results = suite.run(n_episodes=10)
    report = suite.report(results)
    print(report)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .bess_rl_env import BESSArbitrageEnv, _build_synthetic_cmg_profile

log = logging.getLogger(__name__)

__all__ = [
    "BenchmarkSuite",
    "BenchmarkResult",
    "BenchmarkReport",
    "RuleBasedAgent",
    "RandomAgent",
    "HoldAgent",
]


# ---------------------------------------------------------------------------
# Benchmark Data Structures
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Result of a single episode for one strategy."""

    strategy: str
    episode: int
    total_revenue_usd: float
    total_degradation_pct: float
    episode_steps: int
    avg_soc: float
    runtime_ms: float
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def revenue_per_step(self) -> float:
        return self.total_revenue_usd / max(1, self.episode_steps)


@dataclass
class BenchmarkReport:
    """Aggregated benchmark report across all strategies and episodes."""

    results: dict[str, list[BenchmarkResult]]
    n_episodes: int
    capacity_kwh: float
    max_power_kw: float

    def summary(self) -> dict[str, dict[str, float]]:
        """Return summary statistics per strategy."""
        summary: dict[str, dict[str, float]] = {}
        for strategy, eps in self.results.items():
            revenues = [r.total_revenue_usd for r in eps]
            degs = [r.total_degradation_pct for r in eps]
            summary[strategy] = {
                "revenue_mean_usd": float(np.mean(revenues)),
                "revenue_std_usd": float(np.std(revenues)),
                "revenue_min_usd": float(np.min(revenues)),
                "revenue_max_usd": float(np.max(revenues)),
                "degradation_mean_pct": float(np.mean(degs)),
                "avg_runtime_ms": float(np.mean([r.runtime_ms for r in eps])),
            }
        return summary

    def optimality_gap(self, baseline_strategy: str = "milp") -> dict[str, float]:
        """Return optimality gap vs MILP for each strategy (0% = optimal)."""
        summary = self.summary()
        if baseline_strategy not in summary:
            return {}
        milp_revenue = summary[baseline_strategy]["revenue_mean_usd"]
        gaps: dict[str, float] = {}
        for strategy, stats in summary.items():
            if milp_revenue != 0:
                gaps[strategy] = (1.0 - stats["revenue_mean_usd"] / milp_revenue) * 100.0
            else:
                gaps[strategy] = 0.0
        return gaps

    def __str__(self) -> str:
        return BenchmarkSuite.format_report(self)


# ---------------------------------------------------------------------------
# Baseline Agents
# ---------------------------------------------------------------------------


class RuleBasedAgent:
    """Rule-based dispatch agent using price threshold logic.

    Strategy: charge when CMg < low_threshold, discharge when CMg > high_threshold.
    This represents a common rule-based approach used in many commercial BEMS platforms
    for price arbitrage — simple but systematically suboptimal vs MILP.

    Parameters
    ----------
    low_threshold_usd_mwh:
        Charge when price is below this threshold.
    high_threshold_usd_mwh:
        Discharge when price is above this threshold.
    """

    def __init__(
        self,
        low_threshold_usd_mwh: float = 30.0,
        high_threshold_usd_mwh: float = 80.0,
    ) -> None:
        self.low_thresh = low_threshold_usd_mwh
        self.high_thresh = high_threshold_usd_mwh

    def predict(self, obs: np.ndarray) -> tuple[float, dict]:
        """Predict dispatch action from observation.

        obs[3] = cmg_now_norm (normalized CMg price ∈ [0, 1], max=300 USD/MWh)
        """
        cmg_usd_mwh = float(obs[3]) * 300.0  # Denormalize
        soc = float(obs[0])

        if cmg_usd_mwh < self.low_thresh and soc < 0.9:
            # Charge at max rate
            return -1.0, {"source": "rule_based_charge"}
        elif cmg_usd_mwh > self.high_thresh and soc > 0.15:
            # Discharge at max rate
            return 1.0, {"source": "rule_based_discharge"}
        else:
            # Hold (no dispatch)
            return 0.0, {"source": "rule_based_hold"}

    def reset(self) -> None:
        pass


class RandomAgent:
    """Random dispatch agent (sanity check baseline)."""

    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)

    def predict(self, obs: np.ndarray) -> tuple[float, dict]:
        return float(self._rng.uniform(-1, 1)), {"source": "random"}

    def reset(self) -> None:
        pass


class HoldAgent:
    """Hold agent — never dispatches (zero revenue baseline)."""

    def predict(self, obs: np.ndarray) -> tuple[float, dict]:
        return 0.0, {"source": "hold"}

    def reset(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Benchmark Suite
# ---------------------------------------------------------------------------


class BenchmarkSuite:
    """Run and report comparative benchmarks across dispatch strategies.

    Parameters
    ----------
    capacity_kwh:
        Battery capacity (kWh).
    max_power_kw:
        Maximum dispatch power (kW).
    cmg_profile:
        Optional fixed CMg profile for reproducible benchmarks.
        If None, uses the synthetic Chilean CMg profile.
    """

    def __init__(
        self,
        capacity_kwh: float = 200.0,
        max_power_kw: float = 100.0,
        cmg_profile: np.ndarray | None = None,
    ) -> None:
        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self._cmg_profile = (
            cmg_profile if cmg_profile is not None else _build_synthetic_cmg_profile()
        )

    def _make_env(self, seed: int | None = None) -> BESSArbitrageEnv:
        return BESSArbitrageEnv(
            capacity_kwh=self.capacity_kwh,
            max_power_kw=self.max_power_kw,
            cmg_profile=self._cmg_profile.copy(),
            noise_std=2.0,
        )

    def run_episode(
        self,
        agent: Any,
        episode: int = 0,
        seed: int | None = None,
    ) -> BenchmarkResult:
        """Run one full episode with a given agent and return results."""
        strategy_name = getattr(agent, "name", type(agent).__name__)
        env = self._make_env(seed=seed)
        obs, _ = env.reset(seed=seed)
        agent.reset() if hasattr(agent, "reset") else None

        t0 = time.perf_counter()
        total_revenue = 0.0
        total_deg = 0.0
        total_soc = 0.0
        steps = 0

        terminated = truncated = False
        while not (terminated or truncated):
            action_pu, _info = agent.predict(obs)
            action = np.array([action_pu], dtype=np.float32)
            obs, reward, terminated, truncated, info = env.step(action)
            total_revenue += info.get("revenue_usd", 0.0)
            total_deg += info.get("degradation_pct", 0.0)
            total_soc += info.get("soc", 0.5)
            steps += 1

        runtime_ms = (time.perf_counter() - t0) * 1000.0

        return BenchmarkResult(
            strategy=strategy_name,
            episode=episode,
            total_revenue_usd=total_revenue,
            total_degradation_pct=total_deg,
            episode_steps=steps,
            avg_soc=total_soc / max(1, steps),
            runtime_ms=runtime_ms,
        )

    def run(
        self,
        n_episodes: int = 10,
        agents: dict[str, Any] | None = None,
        seed_base: int = 0,
        include_milp: bool = True,
    ) -> BenchmarkReport:
        """Run full benchmark suite across all strategies.

        Parameters
        ----------
        n_episodes:
            Number of episodes per strategy.
        agents:
            Optional dict of {name: agent} to include additional agents
            (e.g., a pre-trained DRL agent). Set ``agent.name`` attribute for labels.
        seed_base:
            Starting random seed for reproducibility.
        include_milp:
            Whether to include MILP solver (requires PuLP). Slower but essential.

        Returns
        -------
        BenchmarkReport
        """
        # Default agents
        default_agents: dict[str, Any] = {
            "rule_based": RuleBasedAgent(low_threshold_usd_mwh=30.0, high_threshold_usd_mwh=80.0),
            "rule_based_tight": RuleBasedAgent(low_threshold_usd_mwh=20.0, high_threshold_usd_mwh=100.0),
            "random": RandomAgent(),
            "hold": HoldAgent(),
        }

        if include_milp:
            try:
                from .milp_optimizer import MILPOptimizer
                milp_agent = MILPOptimizer(
                    cmg_profile=self._cmg_profile,
                    capacity_kwh=self.capacity_kwh,
                    max_power_kw=self.max_power_kw,
                )
                milp_agent.name = "milp"  # type: ignore[attr-defined]
                default_agents["milp"] = milp_agent
            except ImportError:
                log.warning("benchmark_suite.milp_unavailable: PuLP not installed (pip install pulp highspy)")

        if agents:
            default_agents.update(agents)

        all_results: dict[str, list[BenchmarkResult]] = {name: [] for name in default_agents}

        for ep in range(n_episodes):
            seed = seed_base + ep
            for name, agent in default_agents.items():
                if name == "milp" and hasattr(agent, "reset"):
                    agent.reset()
                try:
                    result = self.run_episode(agent, episode=ep, seed=seed)
                    result.strategy = name
                    all_results[name].append(result)
                    log.info(
                        "benchmark_suite.episode",
                        extra={
                            "strategy": name,
                            "ep": ep,
                            "revenue": round(result.total_revenue_usd, 3),
                        },
                    )
                except Exception as exc:
                    log.error(
                        "benchmark_suite.episode_failed strategy=%s ep=%d: %s",
                        name, ep, exc,
                    )

        return BenchmarkReport(
            results=all_results,
            n_episodes=n_episodes,
            capacity_kwh=self.capacity_kwh,
            max_power_kw=self.max_power_kw,
        )

    @staticmethod
    def format_report(report: BenchmarkReport) -> str:
        """Format a human-readable benchmark report."""
        summary = report.summary()
        gaps = report.optimality_gap(baseline_strategy="milp")

        lines = [
            "=" * 70,
            f"BESSAI OPEN BENCHMARK SUITE — {report.n_episodes} episodes",
            f"BESS: {report.capacity_kwh} kWh / {report.max_power_kw} kW | Profile: Chilean CMg",
            "=" * 70,
            f"{'Strategy':<22} {'Revenue (USD)':>14} {'±Std':>8} {'Deg%':>6} {'Gap%':>7} {'ms/ep':>7}",
            "-" * 70,
        ]

        # Sort by revenue descending
        sorted_strats = sorted(
            summary.keys(),
            key=lambda s: summary[s]["revenue_mean_usd"],
            reverse=True,
        )

        for strat in sorted_strats:
            stats = summary[strat]
            gap = gaps.get(strat, 0.0)
            gap_str = f"{gap:+.1f}%" if strat != "milp" else "  0.0%"
            lines.append(
                f"  {strat:<20} "
                f"${stats['revenue_mean_usd']:>12.3f} "
                f"±{stats['revenue_std_usd']:>6.3f} "
                f"{stats['degradation_mean_pct']:>6.3f} "
                f"{gap_str:>7} "
                f"{stats['avg_runtime_ms']:>6.0f}"
            )

        lines += [
            "=" * 70,
            "Gap% = deviation from MILP optimum (0% = optimal, + = worse)",
            "Target: DRL < 20% gap vs MILP | Rule-based typically 35-50% gap",
        ]

        return "\n".join(lines)
