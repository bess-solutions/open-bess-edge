# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/fitness_evaluator.py
================================
BESSAI Edge Gateway — BEP-0303: BESSAIEvolve Fitness Evaluator.

Evaluates a ``PolicyCandidate`` by running its parameterised ArbitragePolicy
against ``BESSArbitrageEnv`` over N days of CMg data and computing a fitness
score (revenue ratio vs. the baseline policy).

AlphaEvolve analogy: this is the "evaluator" module that assigns a fitness
score to each candidate program. It runs exclusively in sandbox — never
touches production hardware.

Key design decisions:
- Uses BESSArbitrageEnv directly (no ONNX runtime needed for evolution)
- SafetyGuard violations during evaluation → candidate is penalised
- Supports both synthetic profile and real CMg arrays
- Thread-safe: each evaluation is stateless (no shared mutable state)

Usage::

    evaluator = FitnessEvaluator(n_eval_days=30)
    baseline_fitness = evaluator.evaluate_baseline()
    candidate_fitness = evaluator.evaluate(candidate, baseline_fitness)
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import numpy as np
import structlog

from src.agents.arbitrage_policy import ArbitragePolicy
from src.agents.bess_rl_env import BESSArbitrageEnv, _build_synthetic_cmg_profile
from src.agents.candidate_generator import PolicyCandidate

__all__ = ["FitnessEvaluator", "EvaluationResult"]

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Penalty applied per SafetyGuard violation (USD/event)
_SAFETY_VIOLATION_PENALTY_USD = 50.0

# Minimum fitness ratio below which a candidate is considered harmful
_MIN_ACCEPTABLE_FITNESS = 0.80  # 80% of baseline


class EvaluationResult:
    """Result of evaluating one candidate on one day of data.

    Attributes
    ----------
    candidate_id:
        ID of the evaluated candidate.
    day_idx:
        Day index in the evaluation dataset.
    revenue_usd:
        Total revenue for this day (USD).
    safety_violations:
        Number of steps where SafetyGuard triggered.
    episode_steps:
        Total steps in the episode.
    elapsed_s:
        Wall-clock time for this evaluation (seconds).
    """

    def __init__(
        self,
        candidate_id: str,
        day_idx: int,
        revenue_usd: float,
        safety_violations: int,
        episode_steps: int,
        elapsed_s: float,
    ) -> None:
        self.candidate_id = candidate_id
        self.day_idx = day_idx
        self.revenue_usd = revenue_usd
        self.safety_violations = safety_violations
        self.episode_steps = episode_steps
        self.elapsed_s = elapsed_s

    def penalised_revenue(self) -> float:
        """Revenue with safety violation penalties applied."""
        return self.revenue_usd - (self.safety_violations * _SAFETY_VIOLATION_PENALTY_USD)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "day_idx": self.day_idx,
            "revenue_usd": self.revenue_usd,
            "safety_violations": self.safety_violations,
            "episode_steps": self.episode_steps,
            "elapsed_s": self.elapsed_s,
            "penalised_revenue_usd": self.penalised_revenue(),
        }


class FitnessEvaluator:
    """Evaluates PolicyCandidates in a sandbox using BESSArbitrageEnv.

    Parameters
    ----------
    n_eval_days:
        Number of CMg daily profiles to evaluate each candidate on.
        Higher values yield more stable fitness estimates at the cost of
        compute time.
    cmg_profiles:
        Optional list of 1-D numpy arrays (one per day). If ``None``,
        the synthetic Chilean CMg profile is replicated ``n_eval_days`` times
        with different random seeds for noise diversity.
    capacity_kwh:
        Battery capacity forwarded to BESSArbitrageEnv.
    max_power_kw:
        Maximum power forwarded to BESSArbitrageEnv.
    max_workers:
        Thread pool size for parallel day-evaluation.
    """

    def __init__(
        self,
        n_eval_days: int = 30,
        cmg_profiles: list[np.ndarray] | None = None,
        capacity_kwh: float = 200.0,
        max_power_kw: float = 100.0,
        max_workers: int = 4,
    ) -> None:
        self.n_eval_days = n_eval_days
        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self.max_workers = max_workers

        # Build profile pool
        if cmg_profiles is not None:
            self._profiles = cmg_profiles[:n_eval_days]
        else:
            base = _build_synthetic_cmg_profile()
            rng = np.random.default_rng(seed=42)
            self._profiles = [
                np.clip(
                    base + rng.normal(0, 3.0, size=len(base)).astype(np.float32),
                    5.0,
                    300.0,
                )
                for _ in range(n_eval_days)
            ]

        # Cache baseline fitness to avoid recomputing every generation
        self._baseline_fitness: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_baseline(self, force: bool = False) -> float:
        """Evaluate the baseline ArbitragePolicy and cache the result.

        Parameters
        ----------
        force:
            If True, recompute even if already cached.

        Returns
        -------
        float
            Mean penalised revenue per day (USD) for the baseline policy.
        """
        if self._baseline_fitness is not None and not force:
            return self._baseline_fitness

        baseline_params = {
            "cmg_low_threshold_norm": 30.0 / 300.0,
            "cmg_high_threshold_norm": 80.0 / 300.0,
            "soc_min": 0.15,
            "soc_max": 0.95,
            "battery_cost_usd_kwh": 250.0,
            "noise_std": 2.0,
        }
        baseline_candidate = PolicyCandidate(
            id="baseline",
            generation=0,
            params=baseline_params,
            metadata={"source": "baseline"},
        )
        results = self._run_all_days(baseline_candidate)
        mean_rev = float(np.mean([r.penalised_revenue() for r in results]))
        self._baseline_fitness = mean_rev
        log.info("fitness_evaluator.baseline_computed", baseline_revenue_usd=mean_rev)
        return mean_rev

    def evaluate(
        self,
        candidate: PolicyCandidate,
        baseline_fitness: float | None = None,
    ) -> float:
        """Evaluate a candidate and return its fitness score.

        Fitness = mean_penalised_revenue / baseline_mean_penalised_revenue

        Values > 1.0 mean the candidate outperforms the baseline.
        Values < ``_MIN_ACCEPTABLE_FITNESS`` → candidate automatically rejected.

        Parameters
        ----------
        candidate:
            The PolicyCandidate to evaluate.
        baseline_fitness:
            Pre-computed baseline fitness. If ``None``, it is computed (expensive).

        Returns
        -------
        float
            Fitness ratio (> 1.0 is better than baseline).
        """
        t0 = time.perf_counter()
        results = self._run_all_days(candidate)
        elapsed = time.perf_counter() - t0

        mean_rev = float(np.mean([r.penalised_revenue() for r in results]))
        total_violations = sum(r.safety_violations for r in results)

        if baseline_fitness is None:
            baseline_fitness = self.evaluate_baseline()

        if baseline_fitness <= 0.0:
            fitness = 0.0
        else:
            fitness = mean_rev / baseline_fitness

        candidate.fitness = fitness
        candidate.metadata.update(
            {
                "mean_revenue_usd": round(mean_rev, 4),
                "total_safety_violations": total_violations,
                "baseline_revenue_usd": round(baseline_fitness, 4),
                "eval_elapsed_s": round(elapsed, 2),
                "n_days_evaluated": len(results),
            }
        )

        log.info(
            "fitness_evaluator.evaluated",
            candidate_id=candidate.id,
            fitness=round(fitness, 4),
            mean_revenue_usd=round(mean_rev, 4),
            safety_violations=total_violations,
            elapsed_s=round(elapsed, 2),
        )
        return fitness

    def evaluate_population(
        self,
        candidates: list[PolicyCandidate],
        baseline_fitness: float | None = None,
    ) -> list[PolicyCandidate]:
        """Evaluate all candidates in a population (parallel across candidates).

        Parameters
        ----------
        candidates:
            List of candidates to evaluate.
        baseline_fitness:
            Pre-computed baseline fitness. Computed once if not provided.

        Returns
        -------
        list[PolicyCandidate]
            Same list with ``fitness`` field populated. Sorted best-first.
        """
        if baseline_fitness is None:
            baseline_fitness = self.evaluate_baseline()

        log.info(
            "fitness_evaluator.population_eval_start",
            n_candidates=len(candidates),
            baseline=round(baseline_fitness, 4),
        )

        # Evaluate candidates in parallel (each candidate runs sequentially per day,
        # but candidates are evaluated concurrently)
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(candidates))) as pool:
            futures = {
                pool.submit(self.evaluate, c, baseline_fitness): c
                for c in candidates
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:  # noqa: BLE001
                    cand = futures[future]
                    log.error(
                        "fitness_evaluator.candidate_failed",
                        candidate_id=cand.id,
                        error=str(exc),
                    )
                    cand.fitness = 0.0  # penalise crashed candidates

        # Sort best-first
        evaluated = sorted(
            [c for c in candidates if c.is_evaluated()],
            key=lambda c: c.fitness or 0.0,
            reverse=True,
        )
        log.info(
            "fitness_evaluator.population_eval_complete",
            best_fitness=round((evaluated[0].fitness or 0.0), 4) if evaluated else None,
        )
        return evaluated

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_all_days(self, candidate: PolicyCandidate) -> list[EvaluationResult]:
        """Run the candidate policy over all evaluation days sequentially."""
        results: list[EvaluationResult] = []
        for day_idx, profile in enumerate(self._profiles):
            result = self._run_one_day(candidate, day_idx, profile)
            results.append(result)
        return results

    def _run_one_day(
        self,
        candidate: PolicyCandidate,
        day_idx: int,
        cmg_profile: np.ndarray,
    ) -> EvaluationResult:
        """Run the candidate policy for one trading day (288 steps = 24 h)."""
        t0 = time.perf_counter()
        params = candidate.params

        # Build environment with candidate's reward shaping params
        env = BESSArbitrageEnv(
            capacity_kwh=self.capacity_kwh,
            max_power_kw=self.max_power_kw,
            cmg_profile=cmg_profile,
            noise_std=params.get("noise_std", 2.0),
            battery_cost_usd_kwh=params.get("battery_cost_usd_kwh", 250.0),
        )

        # Build policy with candidate's threshold params
        policy = ArbitragePolicy(
            cmg_low_threshold_norm=params.get("cmg_low_threshold_norm", 30.0 / 300.0),
            cmg_high_threshold_norm=params.get("cmg_high_threshold_norm", 80.0 / 300.0),
            soc_min=params.get("soc_min", 0.15),
            soc_max=params.get("soc_max", 0.95),
        )

        obs, _ = env.reset(seed=day_idx)
        total_revenue = 0.0
        safety_violations = 0
        step_count = 0

        while True:
            p_pu, _ = policy.predict(obs)
            action = np.array([p_pu], dtype=np.float32)
            obs, _reward, terminated, truncated, info = env.step(action)
            total_revenue += float(info.get("revenue_usd", 0.0))

            # Count safety violations (is_safe=False = out-of-spec operation)
            if not info.get("is_safe", True):
                safety_violations += 1

            step_count += 1
            if terminated or truncated:
                break

        elapsed = time.perf_counter() - t0
        return EvaluationResult(
            candidate_id=candidate.id,
            day_idx=day_idx,
            revenue_usd=total_revenue,
            safety_violations=safety_violations,
            episode_steps=step_count,
            elapsed_s=elapsed,
        )
