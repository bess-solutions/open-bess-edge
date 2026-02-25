# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/agents/test_fitness_evaluator.py
========================================
Unit + integration tests for BEP-0303 FitnessEvaluator.

Uses the synthetic CMg profile (no external data required).
Tests cover:
- Baseline fitness is computed and cached
- Candidate evaluation assigns fitness
- Safety violations are penalised
- evaluate_population sorts best-first
- EvaluationResult penalised_revenue
"""

from __future__ import annotations

import numpy as np
import pytest

from src.agents.candidate_generator import CandidateGenerator, PolicyCandidate
from src.agents.fitness_evaluator import (
    EvaluationResult,
    FitnessEvaluator,
    _SAFETY_VIOLATION_PENALTY_USD,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def evaluator() -> FitnessEvaluator:
    """Evaluator using 3 eval days (fast) with seeded synthetic profiles."""
    return FitnessEvaluator(n_eval_days=3, max_workers=2)


@pytest.fixture(scope="module")
def gen() -> CandidateGenerator:
    return CandidateGenerator(seed=0)


@pytest.fixture(scope="module")
def baseline_fitness(evaluator: FitnessEvaluator) -> float:
    return evaluator.evaluate_baseline()


# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------


class TestEvaluationResult:
    def test_penalised_revenue_no_violations(self) -> None:
        r = EvaluationResult("c1", 0, revenue_usd=100.0, safety_violations=0, episode_steps=288, elapsed_s=0.1)
        assert r.penalised_revenue() == pytest.approx(100.0)

    def test_penalised_revenue_with_violations(self) -> None:
        r = EvaluationResult("c1", 0, revenue_usd=100.0, safety_violations=2, episode_steps=288, elapsed_s=0.1)
        expected = 100.0 - 2 * _SAFETY_VIOLATION_PENALTY_USD
        assert r.penalised_revenue() == pytest.approx(expected)

    def test_to_dict_keys(self) -> None:
        r = EvaluationResult("c1", 0, 50.0, 1, 288, 0.5)
        d = r.to_dict()
        assert "candidate_id" in d
        assert "penalised_revenue_usd" in d
        assert d["safety_violations"] == 1


# ---------------------------------------------------------------------------
# Baseline evaluation
# ---------------------------------------------------------------------------


class TestBaseline:
    def test_baseline_is_positive(self, baseline_fitness: float) -> None:
        """Baseline policy should earn positive revenue on synthetic CMg profile."""
        assert baseline_fitness > 0.0, "Baseline should earn positive revenue"

    def test_baseline_cached(self, evaluator: FitnessEvaluator, baseline_fitness: float) -> None:
        """Second call must return the same value (cached)."""
        result2 = evaluator.evaluate_baseline()
        assert result2 == pytest.approx(baseline_fitness)

    def test_baseline_force_refresh(self, evaluator: FitnessEvaluator) -> None:
        """Force=True must recompute without error."""
        fresh = evaluator.evaluate_baseline(force=True)
        assert fresh > 0.0


# ---------------------------------------------------------------------------
# Candidate evaluation
# ---------------------------------------------------------------------------


class TestCandidateEvaluation:
    def test_evaluate_assigns_fitness(
        self, evaluator: FitnessEvaluator, gen: CandidateGenerator, baseline_fitness: float
    ) -> None:
        cand = gen.baseline_candidate()
        assert cand.fitness is None
        fitness = evaluator.evaluate(cand, baseline_fitness)
        assert cand.fitness is not None
        assert cand.fitness == pytest.approx(fitness)

    def test_baseline_fitness_approx_one(
        self, evaluator: FitnessEvaluator, gen: CandidateGenerator, baseline_fitness: float
    ) -> None:
        """The baseline candidate should have fitness ≈ 1.0."""
        cand = gen.baseline_candidate()
        fitness = evaluator.evaluate(cand, baseline_fitness)
        # Allow ±15% due to env noise
        assert 0.80 <= fitness <= 1.20, f"Baseline fitness far from 1.0: {fitness}"

    def test_metadata_populated(
        self, evaluator: FitnessEvaluator, gen: CandidateGenerator, baseline_fitness: float
    ) -> None:
        cand = gen.random_candidate()
        evaluator.evaluate(cand, baseline_fitness)
        assert "mean_revenue_usd" in cand.metadata
        assert "total_safety_violations" in cand.metadata
        assert "eval_elapsed_s" in cand.metadata

    def test_safety_violations_propagated(
        self, evaluator: FitnessEvaluator, gen: CandidateGenerator, baseline_fitness: float
    ) -> None:
        """A candidate with extreme SOC thresholds may trigger more violations."""
        cand = gen.random_candidate()
        evaluator.evaluate(cand, baseline_fitness)
        # Violations count must be a non-negative integer
        violations = cand.metadata.get("total_safety_violations", -1)
        assert violations >= 0


# ---------------------------------------------------------------------------
# Population evaluation
# ---------------------------------------------------------------------------


class TestPopulationEvaluation:
    def test_sorted_best_first(
        self, evaluator: FitnessEvaluator, gen: CandidateGenerator, baseline_fitness: float
    ) -> None:
        population = [gen.random_candidate() for _ in range(4)]
        evaluated = evaluator.evaluate_population(population, baseline_fitness)

        fitnesses = [c.fitness or 0.0 for c in evaluated]
        assert fitnesses == sorted(fitnesses, reverse=True), "Population not sorted best-first"

    def test_all_evaluated(
        self, evaluator: FitnessEvaluator, gen: CandidateGenerator, baseline_fitness: float
    ) -> None:
        population = [gen.random_candidate() for _ in range(3)]
        evaluated = evaluator.evaluate_population(population, baseline_fitness)
        assert all(c.is_evaluated() for c in evaluated)

    def test_population_size_preserved(
        self, evaluator: FitnessEvaluator, gen: CandidateGenerator, baseline_fitness: float
    ) -> None:
        population = [gen.random_candidate() for _ in range(5)]
        evaluated = evaluator.evaluate_population(population, baseline_fitness)
        assert len(evaluated) == 5
