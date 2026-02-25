# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/agents/test_candidate_generator.py
==========================================
Unit tests for BEP-0303 CandidateGenerator.

Tests cover:
- Baseline candidate has correct parameter values
- Random candidates stay within PARAM_SPACE bounds
- Mutants respect bounds and differ from parent
- Initial population size and composition
- generate_offspring with and without elitism
- PolicyCandidate serialisation round-trip
"""

from __future__ import annotations

import pytest

from src.agents.candidate_generator import (
    PARAM_SPACE,
    CandidateGenerator,
    PolicyCandidate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gen() -> CandidateGenerator:
    """Seeded generator for reproducible tests."""
    return CandidateGenerator(seed=42)


@pytest.fixture
def baseline(gen: CandidateGenerator) -> PolicyCandidate:
    return gen.baseline_candidate()


# ---------------------------------------------------------------------------
# Baseline candidate
# ---------------------------------------------------------------------------


class TestBaselineCandidate:
    def test_has_all_params(self, baseline: PolicyCandidate) -> None:
        for key in PARAM_SPACE:
            assert key in baseline.params, f"Baseline missing param: {key}"

    def test_cmg_low_within_bounds(self, baseline: PolicyCandidate) -> None:
        lo, hi = PARAM_SPACE["cmg_low_threshold_norm"]
        assert lo <= baseline.params["cmg_low_threshold_norm"] <= hi

    def test_battery_cost_within_bounds(self, baseline: PolicyCandidate) -> None:
        lo, hi = PARAM_SPACE["battery_cost_usd_kwh"]
        assert lo <= baseline.params["battery_cost_usd_kwh"] <= hi

    def test_soc_min_less_than_soc_max(self, baseline: PolicyCandidate) -> None:
        assert baseline.params["soc_min"] < baseline.params["soc_max"]

    def test_metadata_source(self, baseline: PolicyCandidate) -> None:
        assert baseline.metadata.get("source") == "baseline"

    def test_parent_id_none(self, baseline: PolicyCandidate) -> None:
        assert baseline.parent_id is None


# ---------------------------------------------------------------------------
# Random candidate
# ---------------------------------------------------------------------------


class TestRandomCandidate:
    def test_all_params_in_bounds(self, gen: CandidateGenerator) -> None:
        for _ in range(20):  # Check multiple random candidates
            cand = gen.random_candidate()
            for key, (lo, hi) in PARAM_SPACE.items():
                assert lo <= cand.params[key] <= hi, (
                    f"Param {key}={cand.params[key]} out of bounds [{lo}, {hi}]"
                )

    def test_has_all_param_keys(self, gen: CandidateGenerator) -> None:
        cand = gen.random_candidate()
        assert set(cand.params.keys()) == set(PARAM_SPACE.keys())

    def test_different_from_baseline(self, gen: CandidateGenerator, baseline: PolicyCandidate) -> None:
        # With high probability, random != baseline for every param
        random_cands = [gen.random_candidate() for _ in range(5)]
        for cand in random_cands:
            diffs = [
                cand.params[k] != baseline.params[k] for k in PARAM_SPACE
            ]
            assert any(diffs), "Random candidate is identical to baseline — suspiciously unlikely"


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------


class TestMutate:
    def test_mutant_in_bounds(self, gen: CandidateGenerator, baseline: PolicyCandidate) -> None:
        for _ in range(50):
            mutant = gen.mutate(baseline, generation=1)
            for key, (lo, hi) in PARAM_SPACE.items():
                assert lo <= mutant.params[key] <= hi, (
                    f"Mutant {key}={mutant.params[key]} out of [{lo}, {hi}]"
                )

    def test_mutant_has_parent_id(self, gen: CandidateGenerator, baseline: PolicyCandidate) -> None:
        mutant = gen.mutate(baseline, generation=1)
        assert mutant.parent_id == baseline.id

    def test_mutant_generation(self, gen: CandidateGenerator, baseline: PolicyCandidate) -> None:
        mutant = gen.mutate(baseline, generation=7)
        assert mutant.generation == 7

    def test_mutant_differs_from_parent(self, gen: CandidateGenerator, baseline: PolicyCandidate) -> None:
        # With sigma=0.1, at least one param should change per mutation
        changed = False
        for _ in range(10):
            mutant = gen.mutate(baseline, generation=1)
            if any(mutant.params[k] != baseline.params[k] for k in PARAM_SPACE):
                changed = True
                break
        assert changed, "Mutant never differed from parent after 10 attempts"

    def test_high_sigma_moves_more(self, baseline: PolicyCandidate) -> None:
        gen_low = CandidateGenerator(seed=123, sigma=0.01)
        gen_high = CandidateGenerator(seed=123, sigma=0.50)

        low_diff = sum(
            abs(gen_low.mutate(baseline, 1).params[k] - baseline.params[k])
            for k in PARAM_SPACE
        )
        high_diff = sum(
            abs(gen_high.mutate(baseline, 1).params[k] - baseline.params[k])
            for k in PARAM_SPACE
        )
        assert high_diff > low_diff, "Higher sigma should produce larger mutations"


# ---------------------------------------------------------------------------
# Initial population
# ---------------------------------------------------------------------------


class TestInitialPopulation:
    def test_size(self, gen: CandidateGenerator) -> None:
        pop = gen.initial_population(size=10, include_baseline=True)
        assert len(pop) == 10

    def test_includes_baseline(self, gen: CandidateGenerator) -> None:
        pop = gen.initial_population(size=5, include_baseline=True)
        sources = [c.metadata.get("source") for c in pop]
        assert "baseline" in sources

    def test_without_baseline(self, gen: CandidateGenerator) -> None:
        pop = gen.initial_population(size=5, include_baseline=False)
        sources = [c.metadata.get("source") for c in pop]
        assert "baseline" not in sources

    def test_all_generation_zero(self, gen: CandidateGenerator) -> None:
        pop = gen.initial_population(size=8)
        assert all(c.generation == 0 for c in pop)


# ---------------------------------------------------------------------------
# generate_offspring
# ---------------------------------------------------------------------------


class TestGenerateOffspring:
    def test_offspring_count(self, gen: CandidateGenerator, baseline: PolicyCandidate) -> None:
        baseline.fitness = 1.0  # needs fitness for elitism
        offspring = gen.generate_offspring([baseline], n_offspring=5, generation=2, elitism=False)
        assert len(offspring) == 5

    def test_elitism_includes_clone(self, gen: CandidateGenerator, baseline: PolicyCandidate) -> None:
        baseline.fitness = 1.0
        offspring = gen.generate_offspring([baseline], n_offspring=5, generation=2, elitism=True)
        # Total should be 5 (1 elite + 4 mutations)
        assert len(offspring) == 5
        elite_sources = [c.metadata.get("source") for c in offspring]
        assert "elitism" in elite_sources

    def test_offspring_generation(self, gen: CandidateGenerator, baseline: PolicyCandidate) -> None:
        baseline.fitness = 1.0
        offspring = gen.generate_offspring([baseline], n_offspring=3, generation=4, elitism=False)
        assert all(c.generation == 4 for c in offspring)


# ---------------------------------------------------------------------------
# PolicyCandidate serialisation
# ---------------------------------------------------------------------------


class TestPolicyCandidateSerialisation:
    def test_round_trip(self, baseline: PolicyCandidate) -> None:
        baseline.fitness = 1.234
        data = baseline.to_dict()
        restored = PolicyCandidate.from_dict(data)

        assert restored.id == baseline.id
        assert restored.fitness == pytest.approx(1.234)
        assert restored.params == baseline.params
        assert restored.generation == baseline.generation

    def test_is_evaluated(self, baseline: PolicyCandidate) -> None:
        assert not baseline.is_evaluated()
        baseline.fitness = 0.9
        assert baseline.is_evaluated()
