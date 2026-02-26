# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/population_manager.py
=================================
BESSAI Edge Gateway — BEP-0303: BESSAIEvolve Population Manager.

Handles persistence, history tracking, and tournament selection for the
evolutionary population. Maintains two files:

- ``models/evolution/population.json`` — current generation state
- ``models/evolution/history.jsonl``  — append-only fitness log

Tournament selection + elitism strategy:
    - Pick ``k`` random candidates from the population
    - Return the one with highest fitness
    - Used to select parents for the next generation

Usage::

    mgr = PopulationManager()
    population = mgr.load_or_init(generator)
    winners = mgr.tournament_select(population, n_winners=3, k=4)
    mgr.save(population, generation=1)
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from src.agents.candidate_generator import PolicyCandidate

if TYPE_CHECKING:
    from src.agents.candidate_generator import CandidateGenerator

__all__ = ["PopulationManager"]

log: structlog.BoundLogger = structlog.get_logger(__name__)

_DEFAULT_POPULATION_PATH = Path("models/evolution/population.json")
_DEFAULT_HISTORY_PATH = Path("models/evolution/history.jsonl")
_DEFAULT_BEST_PATH = Path("models/evolution/best_candidate.json")

# Minimum improvement over baseline to trigger PR promotion
PROMOTION_THRESHOLD = 1.05  # 5 % improvement required


class PopulationManager:
    """Manages the BESSAIEvolve evolutionary population on disk.

    Parameters
    ----------
    population_path:
        Path for the JSON file storing the current population.
    history_path:
        Path for the JSONL file storing per-generation fitness history.
    best_path:
        Path for the JSON file storing the all-time best candidate.
    seed:
        Random seed for tournament selection reproducibility.
    """

    def __init__(
        self,
        population_path: Path | str = _DEFAULT_POPULATION_PATH,
        history_path: Path | str = _DEFAULT_HISTORY_PATH,
        best_path: Path | str = _DEFAULT_BEST_PATH,
        seed: int | None = None,
    ) -> None:
        self.population_path = Path(population_path)
        self.history_path = Path(history_path)
        self.best_path = Path(best_path)
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load_or_init(
        self,
        generator: CandidateGenerator,
        population_size: int = 10,
    ) -> list[PolicyCandidate]:
        """Load existing population from disk or initialise a new one.

        Parameters
        ----------
        generator:
            CandidateGenerator used to bootstrap the initial population.
        population_size:
            Target size when creating from scratch.

        Returns
        -------
        list[PolicyCandidate]
            The current population.
        """
        if self.population_path.exists():
            try:
                with self.population_path.open() as f:
                    data = json.load(f)
                population = [PolicyCandidate.from_dict(c) for c in data]
                log.info(
                    "population_manager.loaded",
                    n=len(population),
                    path=str(self.population_path),
                )
                return population
            except (json.JSONDecodeError, KeyError) as exc:
                log.warning(
                    "population_manager.load_failed",
                    error=str(exc),
                    fallback="initialising new population",
                )

        # Fresh start
        population = generator.initial_population(size=population_size)
        log.info("population_manager.initialised", n=len(population))
        return population

    def save(self, population: list[PolicyCandidate], generation: int) -> None:
        """Persist the population and append fitness history.

        Parameters
        ----------
        population:
            Current generation candidates (evaluated).
        generation:
            Current generation index.
        """
        self.population_path.parent.mkdir(parents=True, exist_ok=True)

        # Save population
        with self.population_path.open("w") as f:
            json.dump([c.to_dict() for c in population], f, indent=2)

        # Append history
        evaluated = [c for c in population if c.is_evaluated()]
        if evaluated:
            best = max(evaluated, key=lambda c: c.fitness or 0.0)
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "generation": generation,
                "best_fitness": round(best.fitness or 0.0, 6),
                "best_candidate_id": best.id,
                "mean_fitness": round(
                    sum(c.fitness or 0.0 for c in evaluated) / len(evaluated), 6
                ),
                "population_size": len(population),
            }
            with self.history_path.open("a") as f:
                f.write(json.dumps(record) + "\n")

            log.info(
                "population_manager.saved",
                generation=generation,
                best_fitness=record["best_fitness"],
                mean_fitness=record["mean_fitness"],
            )

    def load_best_ever(self) -> PolicyCandidate | None:
        """Load the all-time best candidate from disk."""
        if not self.best_path.exists():
            return None
        try:
            with self.best_path.open() as f:
                return PolicyCandidate.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("population_manager.best_load_failed", error=str(exc))
            return None

    def update_best_ever(self, candidate: PolicyCandidate) -> bool:
        """Update the all-time best if the candidate improves on it.

        Parameters
        ----------
        candidate:
            The candidate to compare against the current best.

        Returns
        -------
        bool
            True if the best was updated (new record), False otherwise.
        """
        if candidate.fitness is None:
            return False

        current_best = self.load_best_ever()
        current_best_fitness = current_best.fitness or 0.0 if current_best else 0.0

        if candidate.fitness > current_best_fitness:
            self.best_path.parent.mkdir(parents=True, exist_ok=True)
            with self.best_path.open("w") as f:
                json.dump(candidate.to_dict(), f, indent=2)
            log.info(
                "population_manager.new_best",
                fitness=round(candidate.fitness, 6),
                previous_best=round(current_best_fitness, 6),
                candidate_id=candidate.id,
            )
            return True
        return False

    def should_promote(self, candidate: PolicyCandidate) -> bool:
        """Return True if the candidate meets criteria for PR promotion.

        Promotion criteria (all must be met):
        1. fitness >= PROMOTION_THRESHOLD (≥5% improvement over baseline)
        2. Zero safety violations during evaluation
        3. New all-time best fitness record
        """
        if candidate.fitness is None:
            return False

        violations = candidate.metadata.get("total_safety_violations", 1)
        is_new_best = self.update_best_ever(candidate)

        return (
            candidate.fitness >= PROMOTION_THRESHOLD
            and violations == 0
            and is_new_best
        )

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def tournament_select(
        self,
        population: list[PolicyCandidate],
        n_winners: int = 3,
        k: int = 4,
    ) -> list[PolicyCandidate]:
        """Select ``n_winners`` parents via tournament selection.

        Tournament selection: pick ``k`` random candidates, return the one
        with the highest fitness. Repeat ``n_winners`` times (with replacement
        of candidates but not of picks).

        Parameters
        ----------
        population:
            Evaluated population to select from.
        n_winners:
            Number of parents to select.
        k:
            Tournament size. Higher k = more selection pressure.

        Returns
        -------
        list[PolicyCandidate]
            Selected parent candidates (may contain duplicates if population small).
        """
        evaluated = [c for c in population if c.is_evaluated()]
        if not evaluated:
            raise ValueError("Cannot select from population with no evaluated candidates.")

        winners: list[PolicyCandidate] = []
        for _ in range(n_winners):
            tournament = self._rng.choices(evaluated, k=min(k, len(evaluated)))
            winner = max(tournament, key=lambda c: c.fitness or 0.0)
            winners.append(winner)

        log.debug(
            "population_manager.tournament_selected",
            n_winners=n_winners,
            k=k,
            best_winner_fitness=round(max(w.fitness or 0.0 for w in winners), 4),
        )
        return winners
