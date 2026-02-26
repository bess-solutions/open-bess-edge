# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/candidate_generator.py
==================================
BESSAI Edge Gateway — BEP-0303: BESSAIEvolve Candidate Generator.

Generates mutated ``PolicyCandidate`` objects for the evolutionary loop.
Inspired by AlphaEvolve (DeepMind, 2025): uses an LLM-like mutation
operator, implemented in v1 as Gaussian perturbation over a typed
parameter space.

In v2, ``generate_from_llm()`` will call Gemini API for semantically
guided mutations.

Usage::

    gen = CandidateGenerator(seed=42)
    parent = gen.baseline_candidate()
    children = gen.generate_offspring(parent, n=5)
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

__all__ = ["PARAM_SPACE", "PolicyCandidate", "CandidateGenerator"]

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Parameter Space — the "chromosome" of a policy candidate
# ---------------------------------------------------------------------------
# Each entry: param_name -> (min_value, max_value)
# These are the mutable knobs that BESSAIEvolve optimises.
# ---------------------------------------------------------------------------
PARAM_SPACE: dict[str, tuple[float, float]] = {
    # ArbitragePolicy thresholds (normalised CMg, i.e., USD/MWh / 300)
    "cmg_low_threshold_norm": (0.05, 0.20),   # baseline: 30/300 = 0.100
    "cmg_high_threshold_norm": (0.15, 0.45),  # baseline: 80/300 = 0.267
    "soc_min": (0.08, 0.25),                  # baseline: 0.15
    "soc_max": (0.85, 0.98),                  # baseline: 0.95
    # Reward shaping weights (forwarded to BESSArbitrageEnv)
    "battery_cost_usd_kwh": (150.0, 450.0),   # degradation penalty weight; baseline: 250.0
    "noise_std": (0.5, 5.0),                  # CMg observation noise (USD/MWh); baseline: 2.0
}

# Baseline values (the current production ArbitragePolicy configuration)
_BASELINE_PARAMS: dict[str, float] = {
    "cmg_low_threshold_norm": 30.0 / 300.0,
    "cmg_high_threshold_norm": 80.0 / 300.0,
    "soc_min": 0.15,
    "soc_max": 0.95,
    "battery_cost_usd_kwh": 250.0,
    "noise_std": 2.0,
}


@dataclass
class PolicyCandidate:
    """A single candidate in the evolutionary population.

    Parameters
    ----------
    id:
        UUID4 string identifying this candidate uniquely.
    generation:
        Generation index (0 = initial population).
    parent_id:
        ID of the parent candidate used to generate this one.
        ``None`` for the baseline and random initial candidates.
    params:
        Dictionary mapping each parameter name to its value.
        Must contain all keys defined in ``PARAM_SPACE``.
    fitness:
        Fitness score assigned after sandbox evaluation.
        ``None`` until evaluated.
    metadata:
        Optional additional metadata (e.g. evaluation timestamps).
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    generation: int = 0
    parent_id: str | None = None
    params: dict[str, float] = field(default_factory=dict)
    fitness: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_evaluated(self) -> bool:
        """Return True if fitness has been assigned."""
        return self.fitness is not None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-compatible dict."""
        return {
            "id": self.id,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "params": self.params,
            "fitness": self.fitness,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyCandidate:
        """Deserialise from JSON-compatible dict."""
        return cls(
            id=data["id"],
            generation=data.get("generation", 0),
            parent_id=data.get("parent_id"),
            params=data["params"],
            fitness=data.get("fitness"),
            metadata=data.get("metadata", {}),
        )


class CandidateGenerator:
    """Generates mutation candidates for the BESSAIEvolve evolutionary loop.

    Implements Gaussian perturbation as the mutation operator — analogous to
    the LLM-driven code mutation in AlphaEvolve, but without external API
    dependencies in v1. The perturbation respects parameter bounds defined in
    ``PARAM_SPACE``.

    Parameters
    ----------
    seed:
        Random seed for reproducibility. Set to ``None`` for non-deterministic
        runs (recommended for production evolution cycles).
    sigma:
        Default standard deviation for Gaussian mutation, expressed as a
        fraction of the parameter range. 0.10 = 10% of range per step.
    """

    def __init__(self, seed: int | None = None, sigma: float = 0.10) -> None:
        self._rng = random.Random(seed)
        self.sigma = sigma

    def baseline_candidate(self) -> PolicyCandidate:
        """Return the baseline candidate (current production configuration)."""
        return PolicyCandidate(
            id=str(uuid.uuid4()),
            generation=0,
            parent_id=None,
            params=_BASELINE_PARAMS.copy(),
            metadata={"source": "baseline"},
        )

    def random_candidate(self, generation: int = 0) -> PolicyCandidate:
        """Return a candidate with uniformly random parameters within PARAM_SPACE.

        Used to seed the initial population with diversity.
        """
        params = {
            key: self._rng.uniform(lo, hi)
            for key, (lo, hi) in PARAM_SPACE.items()
        }
        cand = PolicyCandidate(
            generation=generation,
            params=params,
            metadata={"source": "random_init"},
        )
        log.debug("candidate_generator.random_created", candidate_id=cand.id)
        return cand

    def mutate(
        self,
        parent: PolicyCandidate,
        generation: int,
        sigma: float | None = None,
    ) -> PolicyCandidate:
        """Generate a single mutant from a parent candidate.

        Each parameter is perturbed by Gaussian noise proportional to the
        parameter's range. The result is clamped to ``PARAM_SPACE`` bounds.

        Parameters
        ----------
        parent:
            The parent candidate to mutate.
        generation:
            Generation index for the new candidate.
        sigma:
            Override the default mutation strength. ``None`` uses ``self.sigma``.

        Returns
        -------
        PolicyCandidate
            A new candidate with mutated parameters.
        """
        _sigma = sigma if sigma is not None else self.sigma
        child_params: dict[str, float] = {}

        for key, val in parent.params.items():
            lo, hi = PARAM_SPACE.get(key, (val, val))
            param_range = hi - lo
            noise = self._rng.gauss(0.0, _sigma * param_range)
            child_params[key] = max(lo, min(hi, val + noise))

        child = PolicyCandidate(
            generation=generation,
            parent_id=parent.id,
            params=child_params,
            metadata={"source": "gaussian_mutation", "sigma": _sigma},
        )
        log.debug(
            "candidate_generator.mutant_created",
            parent_id=parent.id,
            child_id=child.id,
            generation=generation,
        )
        return child

    def generate_offspring(
        self,
        parents: list[PolicyCandidate],
        n_offspring: int,
        generation: int,
        elitism: bool = True,
    ) -> list[PolicyCandidate]:
        """Generate a new generation from a list of parents.

        Alternates between parents round-robin to maximise diversity.

        Parameters
        ----------
        parents:
            List of parent candidates selected by tournament.
        n_offspring:
            Number of offspring to generate.
        generation:
            Target generation index for all offspring.
        elitism:
            If True, the best parent is included unchanged in the offspring
            list (elitism strategy — preserves the best solution).

        Returns
        -------
        list[PolicyCandidate]
            List of ``n_offspring`` new candidates.
        """
        offspring: list[PolicyCandidate] = []

        if elitism and parents:
            # Clone the best parent (highest fitness) unchanged
            best_parent = max(
                (p for p in parents if p.fitness is not None),
                key=lambda c: c.fitness or 0.0,
                default=parents[0],
            )
            elite = PolicyCandidate(
                generation=generation,
                parent_id=best_parent.id,
                params=best_parent.params.copy(),
                metadata={"source": "elitism"},
            )
            offspring.append(elite)
            n_offspring -= 1

        for i in range(n_offspring):
            parent = parents[i % len(parents)]
            offspring.append(self.mutate(parent, generation=generation))

        log.info(
            "candidate_generator.offspring_generated",
            n=len(offspring),
            generation=generation,
            elitism=elitism,
        )
        return offspring

    def initial_population(
        self,
        size: int = 10,
        include_baseline: bool = True,
    ) -> list[PolicyCandidate]:
        """Bootstrap the initial population for generation 0.

        Parameters
        ----------
        size:
            Total population size.
        include_baseline:
            If True, the first candidate is the production baseline.
            Remaining are random. This ensures AlphaEvolve principle:
            start with the best known solution in the population.

        Returns
        -------
        list[PolicyCandidate]
            List of ``size`` candidates for generation 0.
        """
        population: list[PolicyCandidate] = []
        if include_baseline:
            population.append(self.baseline_candidate())
        while len(population) < size:
            population.append(self.random_candidate(generation=0))
        log.info(
            "candidate_generator.initial_population",
            n=len(population),
            include_baseline=include_baseline,
        )
        return population
