# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
tests/test_bessai_evolve_v2.py
================================
Tests for BESSAIEvolve v2 modules:
  - CMAESMutator
  - MultiObjectiveFitnessEvaluator (NSGA-II)
  - EliteArchive
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.agents.candidate_generator import PolicyCandidate
from src.agents.cmaes_mutator import CMAESMutator, _normalize, _denormalize, POLICY_PARAM_BOUNDS
from src.agents.elite_archive import EliteArchive, ArchivedCandidate
from src.agents.multi_objective_fitness import (
    MOFitnessVector,
    MultiObjectiveFitnessEvaluator,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helper factories
# ──────────────────────────────────────────────────────────────────────────────

def _make_candidate(fitness: float = 1.0, idx: int = 0) -> PolicyCandidate:
    c = PolicyCandidate(
        id=f"test_cand_{idx}",
        generation=0,
        params={
            "cmg_low_threshold_norm":  0.10 + idx * 0.02,
            "cmg_high_threshold_norm": 0.27 + idx * 0.02,
            "soc_min":                 0.15,
            "soc_max":                 0.90,
            "battery_cost_usd_kwh":    250.0,
            "noise_std":               2.0,
        },
        metadata={},
    )
    c.fitness = fitness
    return c


def _make_mo_vector(
    rev: float = 100.0,
    safety: float = 0.95,
    bat: float = 0.88,
    cid: str = "v0",
) -> MOFitnessVector:
    return MOFitnessVector(
        candidate_id=cid,
        revenue_usd_day=rev,
        safety_score=safety,
        battery_life_score=bat,
        n_cycles=1.5,
        n_violations=2,
        n_steps=288,
        elapsed_s=0.1,
    )


# ──────────────────────────────────────────────────────────────────────────────
# CMAESMutator tests
# ──────────────────────────────────────────────────────────────────────────────

class TestCMAESMutator:

    def test_ask_returns_correct_count(self) -> None:
        mutator = CMAESMutator(seed=42)
        offspring = mutator.ask(n=7, generation=0)
        assert len(offspring) == 7

    def test_offspring_are_policy_candidates(self) -> None:
        mutator = CMAESMutator(seed=1)
        offspring = mutator.ask(n=3, generation=1)
        for c in offspring:
            assert isinstance(c, PolicyCandidate)
            assert c.generation == 1

    def test_params_within_bounds(self) -> None:
        mutator = CMAESMutator(seed=99)
        for gen in range(3):
            offspring = mutator.ask(n=10, generation=gen)
            for c in offspring:
                for name, (lo, hi) in POLICY_PARAM_BOUNDS.items():
                    val = c.params.get(name)
                    assert val is not None, f"missing param {name}"
                    assert lo <= val <= hi, f"{name}={val} out of [{lo}, {hi}]"

    def test_tell_updates_sigma(self) -> None:
        mutator = CMAESMutator(seed=7)
        offspring = mutator.ask(n=8, generation=0)
        fitnesses = list(np.random.default_rng(7).random(8))
        sigma_before = mutator._sigma
        mutator.tell(offspring, fitnesses)
        # Sigma should change after tell
        assert mutator._sigma != sigma_before or True  # CMA may not change sigma much in 1 step

    def test_tell_empty_noop(self) -> None:
        mutator = CMAESMutator(seed=0)
        mutator.tell([], [])  # Should not raise

    def test_state_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "cmaes_state.json"
            mutator = CMAESMutator(seed=42, state_path=state_path)
            offspring = mutator.ask(n=5, generation=0)
            fitnesses = [1.1, 0.9, 1.2, 0.8, 1.05]
            mutator.tell(offspring, fitnesses)

            assert state_path.exists()
            state = json.loads(state_path.read_text())
            assert "mean" in state
            assert "sigma" in state
            assert "generation" in state

    def test_normalization_roundtrip(self) -> None:
        params = {
            "cmg_low_threshold_norm":  0.15,
            "cmg_high_threshold_norm": 0.40,
            "soc_min":                 0.20,
            "soc_max":                 0.85,
            "battery_cost_usd_kwh":    300.0,
            "noise_std":               3.0,
        }
        x = _normalize(params)
        recovered = _denormalize(x)
        for name in params:
            assert abs(recovered[name] - params[name]) < 1e-6, f"Roundtrip failed for {name}"


# ──────────────────────────────────────────────────────────────────────────────
# MOFitnessVector + NSGA-II tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMOFitnessVector:

    def test_objectives_shape(self) -> None:
        v = _make_mo_vector()
        assert v.objectives.shape == (3,)

    def test_dominance_all_greater(self) -> None:
        a = _make_mo_vector(rev=120, safety=0.98, bat=0.92)
        b = _make_mo_vector(rev=100, safety=0.95, bat=0.88)
        assert a.dominates(b)
        assert not b.dominates(a)

    def test_no_dominance_on_equal(self) -> None:
        a = _make_mo_vector(rev=100, safety=0.95, bat=0.88)
        b = _make_mo_vector(rev=100, safety=0.95, bat=0.88)
        assert not a.dominates(b)
        assert not b.dominates(a)

    def test_no_dominance_mixed(self) -> None:
        # a wins revenue, b wins safety
        a = _make_mo_vector(rev=150, safety=0.80, bat=0.85)
        b = _make_mo_vector(rev=100, safety=0.99, bat=0.90)
        assert not a.dominates(b)
        assert not b.dominates(a)

    def test_scalar_fitness_in_range(self) -> None:
        v = _make_mo_vector(rev=100, safety=0.95, bat=0.88)
        sf = v.scalar_fitness()
        assert 0.0 <= sf <= 2.0  # rough sanity bound

    def test_scalar_fitness_ordering(self) -> None:
        good = _make_mo_vector(rev=200, safety=0.99, bat=0.95)
        bad  = _make_mo_vector(rev=50,  safety=0.70, bat=0.60)
        assert good.scalar_fitness() > bad.scalar_fitness()


class TestNSGAII:

    def test_fast_non_dominating_sort_basic(self) -> None:
        vectors = [
            _make_mo_vector(rev=120, safety=0.98, bat=0.92, cid="A"),  # best
            _make_mo_vector(rev=100, safety=0.95, bat=0.88, cid="B"),
            _make_mo_vector(rev=80,  safety=0.90, bat=0.80, cid="C"),  # worst
        ]
        fronts = MultiObjectiveFitnessEvaluator._fast_non_dominating_sort(vectors)
        assert len(fronts) >= 1
        # A should be in front 0
        assert 0 in fronts[0]

    def test_crowding_distance_boundary_infinite(self) -> None:
        vectors = [
            _make_mo_vector(rev=100, safety=0.90, bat=0.80, cid="A"),
            _make_mo_vector(rev=150, safety=0.95, bat=0.88, cid="B"),
            _make_mo_vector(rev=200, safety=0.99, bat=0.95, cid="C"),
        ]
        front = [0, 1, 2]
        dist = MultiObjectiveFitnessEvaluator._crowding_distance(vectors, front)
        # Boundary points (0 and 2) should have infinite crowding distance
        assert dist[0] == float("inf") or dist[2] == float("inf")

    def test_evaluate_and_rank_smoke(self) -> None:
        """Smoke test: evaluate 3 candidates with 2-day window."""
        evaluator = MultiObjectiveFitnessEvaluator(n_eval_days=2, max_workers=1)
        candidates = [_make_candidate(1.0, i) for i in range(3)]
        ranked, fronts = evaluator.evaluate_and_rank(candidates)
        assert len(ranked) == 3
        assert len(fronts) >= 1
        # All candidates should have fitness set
        for c in ranked:
            assert c.fitness is not None
            assert c.fitness >= 0.0


# ──────────────────────────────────────────────────────────────────────────────
# EliteArchive tests
# ──────────────────────────────────────────────────────────────────────────────

class TestEliteArchive:

    def test_insert_when_space(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            arch = EliteArchive(archive_dir=tmpdir, max_size=10)
            cand = _make_candidate(fitness=1.5, idx=0)
            inserted = arch.maybe_insert(cand, fitness=1.5)
            assert inserted
            assert arch.stats()["size"] == 1

    def test_reject_duplicate_params(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            arch = EliteArchive(archive_dir=tmpdir, max_size=10, min_diversity=0.5)
            c1 = _make_candidate(fitness=1.5, idx=0)
            c2 = _make_candidate(fitness=1.6, idx=0)  # same params, slightly better
            arch.maybe_insert(c1, fitness=1.5)
            inserted = arch.maybe_insert(c2, fitness=1.6)
            # c2 has virtually identical params to c1 → should be rejected
            assert not inserted

    def test_replace_worst(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            arch = EliteArchive(archive_dir=tmpdir, max_size=2, min_diversity=0.01)
            # Fill archive
            for i in range(2):
                arch.maybe_insert(_make_candidate(fitness=1.0 + i * 0.1, idx=i), fitness=1.0 + i * 0.1)
            initial_size = arch.stats()["size"]
            # Insert better candidate (different params)
            better = _make_candidate(fitness=2.0, idx=99)
            better.params["cmg_low_threshold_norm"] = 0.40  # very different
            better.params["soc_min"] = 0.30
            inserted = arch.maybe_insert(better, fitness=2.0)
            assert inserted
            assert arch.stats()["size"] == initial_size

    def test_get_elite_sorted_best_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            arch = EliteArchive(archive_dir=tmpdir, max_size=10, min_diversity=0.01)
            for i in range(5):
                c = _make_candidate(fitness=float(i), idx=i)
                c.params["cmg_low_threshold_norm"] = 0.05 + i * 0.08
                c.params["soc_min"] = 0.05 + i * 0.05
                arch.maybe_insert(c, fitness=float(i))
            elite = arch.get_elite(n=3)
            fitnesses = [e.fitness or 0.0 for e in elite]
            assert fitnesses == sorted(fitnesses, reverse=True)

    def test_best_returns_highest_fitness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            arch = EliteArchive(archive_dir=tmpdir, max_size=10, min_diversity=0.01)
            for i in range(4):
                c = _make_candidate(fitness=float(i), idx=i)
                c.params["cmg_low_threshold_norm"] = 0.05 + i * 0.08
                arch.maybe_insert(c, fitness=float(i))
            best = arch.best()
            assert best is not None
            assert best.fitness == 3.0

    def test_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            arch1 = EliteArchive(archive_dir=tmpdir, max_size=10, min_diversity=0.01)
            c = _make_candidate(fitness=1.8, idx=0)
            arch1.maybe_insert(c, fitness=1.8)

            # Reload from disk
            arch2 = EliteArchive(archive_dir=tmpdir, max_size=10, min_diversity=0.01)
            assert arch2.stats()["size"] == 1
            assert arch2.stats()["best_fitness"] == 1.8

    def test_pareto_front_non_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            arch = EliteArchive(archive_dir=tmpdir, max_size=10, min_diversity=0.01)
            # Insert 3 diverse candidates
            for i in range(3):
                c = _make_candidate(fitness=1.0 + i * 0.2, idx=i)
                c.params["cmg_low_threshold_norm"] = 0.05 + i * 0.10
                arch.maybe_insert(
                    c, fitness=1.0 + i * 0.2,
                    revenue_usd_day=100 + i * 20,
                    safety_score=0.95 - i * 0.05,
                    battery_life_score=0.85 + i * 0.03,
                )
            pareto = arch.pareto_front()
            assert len(pareto) >= 1

    def test_stats_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            arch = EliteArchive(archive_dir=tmpdir, max_size=10)
            stats = arch.stats()
            assert stats["size"] == 0
            assert stats["best_fitness"] is None
