# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
src/agents/multi_objective_fitness.py
=======================================
BESSAIEvolve v2 — NSGA-II Multi-Objective Fitness Evaluator.

Extends the single-objective FitnessEvaluator to a 3-objective Pareto front:

    Objective 1 (maximise): Revenue         — USD/day arbitrage profit
    Objective 2 (maximise): Safety Score    — 1 - (violations / total_steps)
    Objective 3 (maximise): Battery Life    — degradation-adjusted efficiency

NSGA-II is used for selection: candidates are ranked by Pareto dominance
and then crowding distance within each Pareto front.

Usage::

    mof = MultiObjectiveFitnessEvaluator(n_eval_days=30)
    baseline = mof.evaluate_baseline()
    ranked = mof.evaluate_and_rank(candidates, baseline)
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

from src.agents.arbitrage_policy import ArbitragePolicy
from src.agents.bess_rl_env import BESSArbitrageEnv, _build_synthetic_cmg_profile
from src.agents.candidate_generator import PolicyCandidate
from src.agents.fitness_evaluator import FitnessEvaluator

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Degradation cost per cycle (fraction of capacity per cycle, Arrhenius-calibrated)
_CYCLE_DEGRADATION_RATE = 0.00015  # ~0.015% per full cycle → ≈6600 cycles to 80% SoH
_REPLACEMENT_COST_USD = 40_000.0   # replacement cost for 200 kWh battery


@dataclass
class MOFitnessVector:
    """3-objective fitness vector for one candidate."""
    candidate_id: str
    revenue_usd_day: float      # Objective 1: max
    safety_score: float          # Objective 2: max (0-1)
    battery_life_score: float    # Objective 3: max (0-1, higher = less degradation)
    n_cycles: float              # full equivalent cycles per day
    n_violations: int
    n_steps: int
    elapsed_s: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def objectives(self) -> np.ndarray:
        """Return objectives as maximization vector."""
        return np.array([self.revenue_usd_day, self.safety_score, self.battery_life_score])

    def dominates(self, other: "MOFitnessVector") -> bool:
        """Return True if self Pareto-dominates other."""
        o_self = self.objectives
        o_other = other.objectives
        return bool(np.all(o_self >= o_other) and np.any(o_self > o_other))

    def scalar_fitness(
        self,
        w_revenue: float = 0.60,
        w_safety: float = 0.25,
        w_battery: float = 0.15,
    ) -> float:
        """Weighted scalarization for compatibility with PopulationManager."""
        return (
            w_revenue * self.revenue_usd_day / 200.0
            + w_safety * self.safety_score
            + w_battery * self.battery_life_score
        )


class MultiObjectiveFitnessEvaluator:
    """
    NSGA-II multi-objective fitness evaluator for BESSAIEvolve v2.

    Evaluates each candidate on 3 objectives: Revenue, Safety, Battery Life.
    Returns candidates ranked by Pareto front + crowding distance.

    Parameters
    ----------
    n_eval_days:
        Days of data per evaluation.
    cmg_profiles:
        Optional real CMg profiles. Synthetic if None.
    capacity_kwh / max_power_kw:
        BESS parameters.
    max_workers:
        Thread pool size.
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

        if cmg_profiles is not None:
            self._profiles = cmg_profiles[:n_eval_days]
        else:
            base = _build_synthetic_cmg_profile()
            rng = np.random.default_rng(42)
            self._profiles = [
                np.clip(base + rng.normal(0, 3.0, size=len(base)).astype(np.float32), 5.0, 300.0)
                for _ in range(n_eval_days)
            ]

        # Also keep the classic evaluator for compatibility
        self._classic = FitnessEvaluator(
            n_eval_days=n_eval_days,
            cmg_profiles=cmg_profiles,
            capacity_kwh=capacity_kwh,
            max_power_kw=max_power_kw,
            max_workers=max_workers,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def evaluate_baseline(self) -> float:
        """Return scalar baseline for backwards compatibility."""
        return self._classic.evaluate_baseline()

    def evaluate_mo(self, candidate: PolicyCandidate) -> MOFitnessVector:
        """Evaluate one candidate across all 3 objectives."""
        t0 = time.perf_counter()
        revenues, violations, steps, cycles = [], [], [], []

        for day_idx, profile in enumerate(self._profiles):
            day = self._run_one_day(candidate, day_idx, profile)
            revenues.append(day["revenue"])
            violations.append(day["violations"])
            steps.append(day["steps"])
            cycles.append(day["eq_cycles"])

        total_steps = sum(steps)
        total_violations = sum(violations)
        total_cycles = sum(cycles)

        rev_day = float(np.mean(revenues))
        safety = 1.0 - (total_violations / max(total_steps, 1))
        # Battery life: degradation cost as fraction of replacement cost
        degradation_usd_day = total_cycles / self.n_eval_days * _CYCLE_DEGRADATION_RATE * _REPLACEMENT_COST_USD
        battery_score = float(np.clip(1.0 - degradation_usd_day / 100.0, 0.0, 1.0))

        vec = MOFitnessVector(
            candidate_id=candidate.id,
            revenue_usd_day=rev_day,
            safety_score=float(np.clip(safety, 0.0, 1.0)),
            battery_life_score=battery_score,
            n_cycles=total_cycles / self.n_eval_days,
            n_violations=total_violations,
            n_steps=total_steps,
            elapsed_s=time.perf_counter() - t0,
            metadata={"n_days": self.n_eval_days},
        )

        # Also set scalar fitness on candidate for PopulationManager compat
        candidate.fitness = vec.scalar_fitness()
        candidate.metadata.update({
            "mo_revenue_usd_day": round(rev_day, 4),
            "mo_safety_score": round(vec.safety_score, 4),
            "mo_battery_life": round(battery_score, 4),
            "mo_cycles_day": round(vec.n_cycles, 4),
        })

        log.info(
            "mo_fitness.evaluated",
            id=candidate.id[:12],
            revenue=round(rev_day, 2),
            safety=round(vec.safety_score, 3),
            battery=round(battery_score, 3),
        )
        return vec

    def evaluate_and_rank(
        self,
        candidates: list[PolicyCandidate],
        baseline_fitness: float | None = None,
    ) -> tuple[list[PolicyCandidate], list[list[int]]]:
        """
        Evaluate all candidates and rank by NSGA-II (Pareto fronts + crowding distance).

        Returns
        -------
        candidates_ranked:
            Same candidates, sorted by NSGA-II rank (best first).
        pareto_fronts:
            List of fronts (each front is a list of candidate indices in the ranked list).
        """
        log.info("mo_fitness.population_eval", n_candidates=len(candidates))

        vectors: list[MOFitnessVector] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(candidates))) as pool:
            futures = {pool.submit(self.evaluate_mo, c): c for c in candidates}
            for fut in as_completed(futures):
                try:
                    vectors.append(fut.result())
                except Exception as exc:
                    cand = futures[fut]
                    log.error("mo_fitness.eval_failed", id=cand.id, error=str(exc))
                    cand.fitness = 0.0
                    vectors.append(MOFitnessVector(
                        candidate_id=cand.id, revenue_usd_day=0.0, safety_score=0.0,
                        battery_life_score=0.0, n_cycles=0.0, n_violations=0, n_steps=0, elapsed_s=0.0
                    ))

        # NSGA-II ranking
        fronts = self._fast_non_dominating_sort(vectors)
        ranked_indices: list[int] = []
        for front in fronts:
            crowd = self._crowding_distance(vectors, front)
            # Sort front by crowding distance (higher = more diverse = better)
            front_sorted = sorted(front, key=lambda i: crowd[i], reverse=True)
            ranked_indices.extend(front_sorted)

        # Map back to candidates (need to align by candidate_id)
        id_to_candidate = {c.id: c for c in candidates}
        ranked_candidates = [id_to_candidate[vectors[i].candidate_id] for i in ranked_indices]

        log.info(
            "mo_fitness.nsga2_complete",
            n_fronts=len(fronts),
            pareto_front_size=len(fronts[0]) if fronts else 0,
        )
        return ranked_candidates, fronts

    # ──────────────────────────────────────────────────────────────────────
    # NSGA-II core algorithms
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _fast_non_dominating_sort(vectors: list[MOFitnessVector]) -> list[list[int]]:
        """O(MN²) fast non-dominated sort from Deb et al. (2002)."""
        n = len(vectors)
        sp: list[list[int]] = [[] for _ in range(n)]
        np_count = [0] * n
        fronts: list[list[int]] = [[]]

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                if vectors[i].dominates(vectors[j]):
                    sp[i].append(j)
                elif vectors[j].dominates(vectors[i]):
                    np_count[i] += 1
            if np_count[i] == 0:
                fronts[0].append(i)

        k = 0
        while fronts[k]:
            next_front: list[int] = []
            for i in fronts[k]:
                for j in sp[i]:
                    np_count[j] -= 1
                    if np_count[j] == 0:
                        next_front.append(j)
            k += 1
            fronts.append(next_front)

        return [f for f in fronts if f]

    @staticmethod
    def _crowding_distance(vectors: list[MOFitnessVector], front: list[int]) -> dict[int, float]:
        """Compute crowding distance for candidates in a front."""
        dist: dict[int, float] = {i: 0.0 for i in front}
        n_obj = len(vectors[0].objectives)

        for m in range(n_obj):
            sorted_front = sorted(front, key=lambda i: vectors[i].objectives[m])
            dist[sorted_front[0]] = float("inf")
            dist[sorted_front[-1]] = float("inf")
            obj_range = (
                vectors[sorted_front[-1]].objectives[m]
                - vectors[sorted_front[0]].objectives[m]
            )
            if obj_range == 0:
                continue
            for k in range(1, len(sorted_front) - 1):
                dist[sorted_front[k]] += (
                    vectors[sorted_front[k + 1]].objectives[m]
                    - vectors[sorted_front[k - 1]].objectives[m]
                ) / obj_range

        return dist

    # ──────────────────────────────────────────────────────────────────────
    # Single-day evaluation
    # ──────────────────────────────────────────────────────────────────────

    def _run_one_day(
        self, candidate: PolicyCandidate, day_idx: int, cmg_profile: np.ndarray
    ) -> dict[str, float]:
        params = candidate.params
        env = BESSArbitrageEnv(
            capacity_kwh=self.capacity_kwh,
            max_power_kw=self.max_power_kw,
            cmg_profile=cmg_profile,
            noise_std=params.get("noise_std", 2.0),
            battery_cost_usd_kwh=params.get("battery_cost_usd_kwh", 250.0),
        )
        policy = ArbitragePolicy(
            cmg_low_threshold_norm=params.get("cmg_low_threshold_norm", 0.1),
            cmg_high_threshold_norm=params.get("cmg_high_threshold_norm", 0.27),
            soc_min=params.get("soc_min", 0.15),
            soc_max=params.get("soc_max", 0.95),
        )

        obs, _ = env.reset(seed=day_idx)
        revenue = violations = steps = 0
        prev_soc = 0.5
        eq_cycles = 0.0

        while True:
            p_pu, _ = policy.predict(obs)
            action = np.array([p_pu], dtype=np.float32)
            obs, _reward, terminated, truncated, info = env.step(action)
            revenue += float(info.get("revenue_usd", 0.0))
            if not info.get("is_safe", True):
                violations += 1
            # Count equivalent full cycles (|ΔSOC| / 2)
            current_soc = float(obs[0]) if len(obs) > 0 else prev_soc
            eq_cycles += abs(current_soc - prev_soc) / 2.0
            prev_soc = current_soc
            steps += 1
            if terminated or truncated:
                break

        return {"revenue": revenue, "violations": violations, "steps": steps, "eq_cycles": eq_cycles}
