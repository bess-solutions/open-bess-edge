# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/agents/bessai_evolve.py
============================
BESSAI Edge Gateway — BEP-0303: BESSAIEvolve Evolutionary Orchestrator.

Main entrypoint for the BESSAIEvolve autonomous self-improvement loop.
Implements a (µ + λ) evolution strategy:

    1. Load or initialise population
    2. Evaluate all candidates in parallel sandbox
    3. Tournament-select parents
    4. Generate offspring via Gaussian mutation
    5. Evaluate offspring
    6. Replace population (elitism: keep best of current)
    7. Log + persist results
    8. If winner qualifies → emit promotion signal for GitHub Actions PR

Inspired by AlphaEvolve (DeepMind, 2025):
    - CandidateGenerator ≈ LLM mutation operator
    - FitnessEvaluator   ≈ Automated program evaluator
    - PopulationManager  ≈ Program database
    - BESSAIEvolve       ≈ AlphaEvolve main loop

Run from CLI::

    python -m src.agents.bessai_evolve --generations 5 --population 10

Run from GitHub Actions (see .github/workflows/bessai-evolve.yml).

Exit codes:
    0 — Evolution complete; no promotion triggered
    2 — Evolution complete; promotion candidate written to disk
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import structlog

from src.agents.candidate_generator import CandidateGenerator, PolicyCandidate
from src.agents.fitness_evaluator import FitnessEvaluator
from src.agents.population_manager import PopulationManager

__all__ = ["BESSAIEvolve", "run_evolution"]

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Default hyperparameters for the evolution loop
DEFAULT_POPULATION_SIZE = 10
DEFAULT_N_GENERATIONS = 5
DEFAULT_N_EVAL_DAYS = 30
DEFAULT_N_WINNERS = 3   # parents selected per generation
DEFAULT_TOURNAMENT_K = 4
DEFAULT_N_OFFSPRING = 7
DEFAULT_SIGMA = 0.10    # Gaussian mutation strength

# Output path for promotion signal (read by GitHub Actions)
_PROMOTION_SIGNAL_PATH = Path("models/evolution/promote.json")


class BESSAIEvolve:
    """Orchestrates the BESSAIEvolve evolutionary loop.

    Parameters
    ----------
    population_size:
        Number of candidates per generation.
    n_generations:
        Number of evolutionary generations per run.
    n_eval_days:
        Days of CMg data for fitness evaluation.
    n_winners:
        Parents selected per generation via tournament.
    tournament_k:
        Tournament size for parent selection.
    n_offspring:
        Offspring generated per generation.
    sigma:
        Gaussian mutation strength.
    seed:
        Random seed for reproducibility.
    population_dir:
        Directory for population persistence files.
    """

    def __init__(
        self,
        population_size: int = DEFAULT_POPULATION_SIZE,
        n_generations: int = DEFAULT_N_GENERATIONS,
        n_eval_days: int = DEFAULT_N_EVAL_DAYS,
        n_winners: int = DEFAULT_N_WINNERS,
        tournament_k: int = DEFAULT_TOURNAMENT_K,
        n_offspring: int = DEFAULT_N_OFFSPRING,
        sigma: float = DEFAULT_SIGMA,
        seed: int | None = None,
        population_dir: Path | str = "models/evolution",
    ) -> None:
        self.population_size = population_size
        self.n_generations = n_generations
        self.n_winners = n_winners
        self.tournament_k = tournament_k
        self.n_offspring = n_offspring
        self.sigma = sigma

        base = Path(population_dir)
        self.generator = CandidateGenerator(seed=seed, sigma=sigma)
        self.evaluator = FitnessEvaluator(n_eval_days=n_eval_days)
        self.manager = PopulationManager(
            population_path=base / "population.json",
            history_path=base / "history.jsonl",
            best_path=base / "best_candidate.json",
            seed=seed,
        )

    def run(self) -> dict[str, Any]:
        """Execute the full evolutionary loop.

        Returns
        -------
        dict
            Summary of the run: best fitness, generation count, promotion status.
        """
        log.info(
            "bessai_evolve.run_start",
            population_size=self.population_size,
            n_generations=self.n_generations,
        )

        # ----------------------------------------------------------------
        # Step 1: Bootstrap population
        # ----------------------------------------------------------------
        population = self.manager.load_or_init(
            self.generator, population_size=self.population_size
        )

        # ----------------------------------------------------------------
        # Step 2: Pre-compute baseline fitness (cache for all generations)
        # ----------------------------------------------------------------
        baseline_fitness = self.evaluator.evaluate_baseline()
        log.info("bessai_evolve.baseline", baseline_usd_per_day=round(baseline_fitness, 4))

        best_candidate: PolicyCandidate | None = self.manager.load_best_ever()
        promoted = False

        for gen in range(self.n_generations):
            log.info("bessai_evolve.generation_start", generation=gen)

            # ----------------------------------------------------------------
            # Step 3: Evaluate unevaluated candidates
            # ----------------------------------------------------------------
            unevaluated = [c for c in population if not c.is_evaluated()]
            if unevaluated:
                evaluated = self.evaluator.evaluate_population(
                    unevaluated, baseline_fitness=baseline_fitness
                )
                # Merge back
                population = [
                    *[c for c in population if c.is_evaluated()],
                    *evaluated,
                ]

            # ----------------------------------------------------------------
            # Step 4: Tournament selection
            # ----------------------------------------------------------------
            parents = self.manager.tournament_select(
                population,
                n_winners=self.n_winners,
                k=self.tournament_k,
            )

            # Identify the current generation's best
            gen_best = max(
                (c for c in population if c.is_evaluated()),
                key=lambda c: c.fitness or 0.0,
            )
            log.info(
                "bessai_evolve.generation_best",
                generation=gen,
                best_fitness=round(gen_best.fitness or 0.0, 4),
                candidate_id=gen_best.id,
            )

            # Update all-time best + check promotion eligibility
            if self.manager.should_promote(gen_best):
                best_candidate = gen_best
                promoted = True
                log.info(
                    "bessai_evolve.promotion_candidate",
                    fitness=round(gen_best.fitness or 0.0, 4),
                    candidate_id=gen_best.id,
                )

            # Persist this generation
            self.manager.save(population, generation=gen)

            # ----------------------------------------------------------------
            # Step 5: Generate next generation (skip on last iteration)
            # ----------------------------------------------------------------
            if gen < self.n_generations - 1:
                offspring = self.generator.generate_offspring(
                    parents=parents,
                    n_offspring=self.n_offspring,
                    generation=gen + 1,
                    elitism=True,
                )
                population = offspring

        # ----------------------------------------------------------------
        # Step 6: Write promotion signal if warranted
        # ----------------------------------------------------------------
        if promoted and best_candidate is not None:
            self._write_promotion_signal(best_candidate)

        summary: dict[str, Any] = {
            "n_generations": self.n_generations,
            "baseline_fitness": round(baseline_fitness, 4),
            "best_ever_fitness": round(best_candidate.fitness or 0.0, 4)
            if best_candidate
            else None,
            "promoted": promoted,
            "best_candidate_id": best_candidate.id if best_candidate else None,
        }
        log.info("bessai_evolve.run_complete", **summary)
        return summary

    def _write_promotion_signal(self, candidate: PolicyCandidate) -> None:
        """Write a promotion signal file for GitHub Actions to detect.

        The CI workflow reads this file and opens a PR with the new policy.
        """
        _PROMOTION_SIGNAL_PATH.parent.mkdir(parents=True, exist_ok=True)
        signal = {
            "promote": True,
            "candidate_id": candidate.id,
            "fitness": round(candidate.fitness or 0.0, 6),
            "params": candidate.params,
            "metadata": candidate.metadata,
        }
        with _PROMOTION_SIGNAL_PATH.open("w") as f:
            json.dump(signal, f, indent=2)
        log.info(
            "bessai_evolve.promotion_signal_written",
            path=str(_PROMOTION_SIGNAL_PATH),
            fitness=signal["fitness"],
        )


def run_evolution(
    generations: int = DEFAULT_N_GENERATIONS,
    population: int = DEFAULT_POPULATION_SIZE,
    eval_days: int = DEFAULT_N_EVAL_DAYS,
    sigma: float = DEFAULT_SIGMA,
    seed: int | None = None,
) -> int:
    """Convenience wrapper for CLI and GitHub Actions.

    Returns
    -------
    int
        Exit code: 0 = no promotion, 2 = promotion ready.
    """
    engine = BESSAIEvolve(
        population_size=population,
        n_generations=generations,
        n_eval_days=eval_days,
        sigma=sigma,
        seed=seed,
    )
    summary = engine.run()
    return 2 if summary.get("promoted") else 0


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BESSAIEvolve — autonomous policy evolution loop (BEP-0303)"
    )
    parser.add_argument("--generations", type=int, default=DEFAULT_N_GENERATIONS)
    parser.add_argument("--population", type=int, default=DEFAULT_POPULATION_SIZE)
    parser.add_argument("--eval-days", type=int, default=DEFAULT_N_EVAL_DAYS)
    parser.add_argument("--sigma", type=float, default=DEFAULT_SIGMA)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    sys.exit(
        run_evolution(
            generations=args.generations,
            population=args.population,
            eval_days=args.eval_days,
            sigma=args.sigma,
            seed=args.seed,
        )
    )
