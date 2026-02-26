# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
src/agents/bessai_evolve_v2.py
================================
BESSAIEvolve v2 — CMA-ES + NSGA-II + Elite Archive Orchestrator.

Upgrades over v1 (bessai_evolve.py):
    ✅ CMA-ES mutation (replaces scalar Gaussian)   → faster convergence
    ✅ NSGA-II multi-objective (Revenue+Safety+Life) → Pareto-optimal policies
    ✅ Elite Archive (top-50 diverse policies)       → no knowledge loss
    ✅ CMA state persistence across CI runs          → warm-start each Monday

Backwards compatible: still emits models/evolution/promote.json
for the GitHub Actions PR workflow.

Run from CLI::

    python -m src.agents.bessai_evolve_v2 --generations 10 --population 15

    # Compare modes
    python -m src.agents.bessai_evolve_v2 --mode v1  # original Gaussian
    python -m src.agents.bessai_evolve_v2 --mode v2  # CMA-ES + NSGA-II (default)

Exit codes:
    0 — Evolution complete, no promotion
    2 — Evolution complete, promotion candidate ready
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import structlog

from src.agents.candidate_generator import CandidateGenerator, PolicyCandidate
from src.agents.cmaes_mutator import CMAESMutator
from src.agents.elite_archive import EliteArchive
from src.agents.fitness_evaluator import FitnessEvaluator
from src.agents.multi_objective_fitness import MultiObjectiveFitnessEvaluator
from src.agents.population_manager import PopulationManager

__all__ = ["BESSAIEvolveV2", "run_evolution_v2"]

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Hyperparameters
DEFAULT_POPULATION_SIZE = 15   # v2: larger for CMA-ES
DEFAULT_N_GENERATIONS = 10
DEFAULT_N_EVAL_DAYS = 30
DEFAULT_SIGMA0 = 0.30          # CMA-ES initial step size (normalized space)
DEFAULT_ELITE_SIZE = 50        # elite archive capacity
PROMOTION_THRESHOLD = 1.15     # 15% above baseline to trigger promotion

_PROMOTION_PATH = Path("models/evolution/promote.json")
_EVOLUTION_DIR = Path("models/evolution")


class BESSAIEvolveV2:
    """
    BESSAIEvolve v2 — Full evolutionary loop with CMA-ES + NSGA-II + EliteArchive.

    Parameters
    ----------
    population_size:
        Candidates per generation (recommend ≥ 15 for CMA-ES).
    n_generations:
        Evolutionary generations to run.
    n_eval_days:
        CMg days for fitness evaluation.
    sigma0:
        CMA-ES initial step size (0-1 normalized space, default 0.3).
    elite_size:
        Max candidates in the elite archive.
    seed:
        RNG seed for reproducibility.
    population_dir:
        Directory for all evolution persistence files.
    use_mo:
        If True, use NSGA-II multi-objective evaluator (v2 default).
        If False, use single-objective for speed (v1 compat).
    """

    def __init__(
        self,
        population_size: int = DEFAULT_POPULATION_SIZE,
        n_generations: int = DEFAULT_N_GENERATIONS,
        n_eval_days: int = DEFAULT_N_EVAL_DAYS,
        sigma0: float = DEFAULT_SIGMA0,
        elite_size: int = DEFAULT_ELITE_SIZE,
        seed: int | None = None,
        population_dir: Path | str = _EVOLUTION_DIR,
        use_mo: bool = True,
    ) -> None:
        self.population_size = population_size
        self.n_generations = n_generations
        self.use_mo = use_mo

        base = Path(population_dir)
        base.mkdir(parents=True, exist_ok=True)

        # v2 components
        self.cmaes = CMAESMutator(
            sigma0=sigma0,
            seed=seed,
            state_path=base / "cmaes_state.json",
        )
        self.archive = EliteArchive(
            archive_dir=base / "archive",
            max_size=elite_size,
        )

        # Evaluators
        if use_mo:
            self.mo_evaluator = MultiObjectiveFitnessEvaluator(n_eval_days=n_eval_days)
            self.evaluator: FitnessEvaluator | None = None
        else:
            self.evaluator = FitnessEvaluator(n_eval_days=n_eval_days)
            self.mo_evaluator = None

        # v1 compat components (used for warm-start from existing population)
        self.generator = CandidateGenerator(seed=seed, sigma=0.10)
        self.manager = PopulationManager(
            population_path=base / "population.json",
            history_path=base / "history.jsonl",
            best_path=base / "best_candidate.json",
            seed=seed,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Execute V2 evolutionary loop. Returns summary dict."""
        log.info(
            "bessai_evolve_v2.run_start",
            population_size=self.population_size,
            n_generations=self.n_generations,
            use_multi_objective=self.use_mo,
        )

        # Step 1: Load existing population or bootstrap via CMA-ES
        existing = self.manager.load_or_init(self.generator, population_size=self.population_size)
        # Add elite candidates to seed the initial population
        elite = self.archive.get_elite(n=min(3, self.population_size // 3))
        seed_pool = (elite + existing)[:self.population_size]

        # Also seed CMA-ES mean from best known candidate
        best_ever = self.archive.best() or self.manager.load_best_ever()

        # Step 2: Baseline fitness
        if self.use_mo and self.mo_evaluator:
            baseline_fitness = self.mo_evaluator.evaluate_baseline()
        else:
            baseline_fitness = self.evaluator.evaluate_baseline()  # type: ignore[union-attr]
        log.info("bessai_evolve_v2.baseline", baseline_usd_day=round(baseline_fitness, 4))

        promoted = False
        best_candidate: PolicyCandidate | None = best_ever
        generation_stats: list[dict[str, Any]] = []

        for gen in range(self.n_generations):
            log.info("bessai_evolve_v2.generation_start", generation=gen)

            # Step 3: Generate offspring via CMA-ES
            if gen == 0 and seed_pool:
                # Warm-start: use existing candidates + CMA-ES offspring
                n_cmaes = max(self.population_size - len(seed_pool), self.population_size // 2)
                cmaes_offspring = self.cmaes.ask(n=n_cmaes, generation=gen)
                population = seed_pool + cmaes_offspring
            else:
                population = self.cmaes.ask(n=self.population_size, generation=gen)

            # Step 4: Evaluate (multi-objective or single)
            if self.use_mo and self.mo_evaluator:
                ranked_pop, pareto_fronts = self.mo_evaluator.evaluate_and_rank(
                    population, baseline_fitness
                )
                fitnesses = [c.fitness or 0.0 for c in ranked_pop]
            else:
                evaluated = self.evaluator.evaluate_population(  # type: ignore[union-attr]
                    population, baseline_fitness
                )
                ranked_pop = evaluated
                fitnesses = [c.fitness or 0.0 for c in ranked_pop]
                pareto_fronts = [list(range(len(ranked_pop)))]

            # Step 5: Update CMA-ES distribution from ranked results
            self.cmaes.tell(ranked_pop, fitnesses)

            # Step 6: Update elite archive
            for cand in ranked_pop:
                fit = cand.fitness or 0.0
                rev = float(cand.metadata.get("mo_revenue_usd_day", fit * baseline_fitness))
                safety = float(cand.metadata.get("mo_safety_score", 0.95))
                bat = float(cand.metadata.get("mo_battery_life", 0.85))
                self.archive.maybe_insert(
                    cand, fitness=fit,
                    revenue_usd_day=rev, safety_score=safety, battery_life_score=bat
                )

            # Step 7: Check promotion
            gen_best = ranked_pop[0] if ranked_pop else None
            if gen_best and (gen_best.fitness or 0.0) > PROMOTION_THRESHOLD:
                if best_candidate is None or (gen_best.fitness or 0.0) > (best_candidate.fitness or 0.0):
                    best_candidate = gen_best
                    promoted = True
                    log.info(
                        "bessai_evolve_v2.promotion_candidate",
                        fitness=round(gen_best.fitness or 0.0, 4),
                        candidate_id=gen_best.id,
                    )

            # Stats
            gen_stat = {
                "generation": gen,
                "best_fitness": round(gen_best.fitness or 0.0, 4) if gen_best else None,
                "pareto_front_size": len(pareto_fronts[0]) if pareto_fronts else 0,
                "archive_size": self.archive.stats()["size"],
            }
            generation_stats.append(gen_stat)
            log.info("bessai_evolve_v2.generation_complete", **gen_stat)

            # Persist
            self.manager.save(ranked_pop[:self.population_size], generation=gen)

        # Step 8: Write promotion signal
        if promoted and best_candidate is not None:
            self._write_promotion_signal(best_candidate)

        archive_stats = self.archive.stats()
        summary: dict[str, Any] = {
            "version": "v2",
            "n_generations": self.n_generations,
            "use_multi_objective": self.use_mo,
            "baseline_fitness": round(baseline_fitness, 4),
            "best_fitness": round(best_candidate.fitness or 0.0, 4) if best_candidate else None,
            "promoted": promoted,
            "best_candidate_id": best_candidate.id if best_candidate else None,
            "archive": archive_stats,
            "generations": generation_stats,
        }
        log.info("bessai_evolve_v2.run_complete", **{k: v for k, v in summary.items() if k != "generations"})

        # Write summary to disk for GitHub Actions summary
        summary_path = _EVOLUTION_DIR / "evolution_summary_v2.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2))

        return summary

    def _write_promotion_signal(self, candidate: PolicyCandidate) -> None:
        _PROMOTION_PATH.parent.mkdir(parents=True, exist_ok=True)
        signal = {
            "promote": True,
            "version": "v2",
            "candidate_id": candidate.id,
            "fitness": round(candidate.fitness or 0.0, 6),
            "params": candidate.params,
            "metadata": candidate.metadata,
            "archive_best": self.archive.stats(),
        }
        _PROMOTION_PATH.write_text(json.dumps(signal, indent=2))
        log.info(
            "bessai_evolve_v2.promotion_signal",
            path=str(_PROMOTION_PATH),
            fitness=signal["fitness"],
        )


# ──────────────────────────────────────────────────────────────────────────────
# Convenience wrapper + CLI
# ──────────────────────────────────────────────────────────────────────────────

def run_evolution_v2(
    generations: int = DEFAULT_N_GENERATIONS,
    population: int = DEFAULT_POPULATION_SIZE,
    eval_days: int = DEFAULT_N_EVAL_DAYS,
    sigma: float = DEFAULT_SIGMA0,
    seed: int | None = None,
    use_mo: bool = True,
) -> int:
    """
    Convenience entry point for GitHub Actions and CLI.

    Returns 0 (no promotion) or 2 (promotion ready).
    """
    engine = BESSAIEvolveV2(
        population_size=population,
        n_generations=generations,
        n_eval_days=eval_days,
        sigma0=sigma,
        seed=seed,
        use_mo=use_mo,
    )
    summary = engine.run()

    # Print GitHub Actions summary
    print("\n## 🧬 BESSAIEvolve v2 Summary\n")
    print(f"| Metric | Value |")
    print(f"|--------|-------|")
    print(f"| Generations | {summary['n_generations']} |")
    print(f"| Mode | {'NSGA-II Multi-Objective' if summary['use_multi_objective'] else 'Single-Objective'} |")
    print(f"| Best Fitness | {summary['best_fitness']} |")
    print(f"| Baseline | {summary['baseline_fitness']} |")
    print(f"| Elite Archive | {summary['archive']['size']}/{summary['archive']['max_size']} |")
    print(f"| Promoted | {'✅ Yes' if summary['promoted'] else '—'} |")
    if summary["archive"].get("best_revenue_usd_day"):
        print(f"| Best Revenue | ${summary['archive']['best_revenue_usd_day']:.2f}/day |")

    return 2 if summary.get("promoted") else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BESSAIEvolve v2 — CMA-ES + NSGA-II + Elite Archive (BEP-0304)"
    )
    parser.add_argument("--generations", type=int, default=DEFAULT_N_GENERATIONS)
    parser.add_argument("--population", type=int, default=DEFAULT_POPULATION_SIZE)
    parser.add_argument("--eval-days", type=int, default=DEFAULT_N_EVAL_DAYS)
    parser.add_argument("--sigma", type=float, default=DEFAULT_SIGMA0,
                        help="CMA-ES initial step size (default 0.30)")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--mode", choices=["v1", "v2"], default="v2",
                        help="v1=Gaussian+single-obj, v2=CMA-ES+NSGA-II (default)")
    args = parser.parse_args()

    use_mo = args.mode == "v2"
    sys.exit(run_evolution_v2(
        generations=args.generations,
        population=args.population,
        eval_days=args.eval_days,
        sigma=args.sigma,
        seed=args.seed,
        use_mo=use_mo,
    ))
