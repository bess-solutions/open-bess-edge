# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
src/agents/elite_archive.py
============================
BESSAIEvolve v2 — Elite Population Archive.

Maintains a rolling archive of the top-N policies ever found across all
evolutionary runs. Provides:
  - Persistent elite storage (JSON + JSONL)
  - Diversity-aware insertion (rejects near-duplicates by parameter distance)
  - Pareto-front tracking for multi-objective runs
  - Archive statistics for reporting and monitoring

The archive persists across GitHub Actions runs via artifact caching,
so good solutions discovered weeks ago are never lost.

Usage::

    archive = EliteArchive(max_size=50)
    archive.maybe_insert(candidate, fitness_vector)
    best_50 = archive.get_elite(n=50)
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import structlog

from src.agents.candidate_generator import PolicyCandidate

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Minimum L2 distance in normalised param space to consider candidates distinct
_MIN_DIVERSITY_DISTANCE = 0.05

_PARAM_NAMES = [
    "cmg_low_threshold_norm",
    "cmg_high_threshold_norm",
    "soc_min",
    "soc_max",
    "battery_cost_usd_kwh",
    "noise_std",
]

_PARAM_RANGES = {
    "cmg_low_threshold_norm":  (0.01, 0.45),
    "cmg_high_threshold_norm": (0.15, 0.95),
    "soc_min":                 (0.05, 0.35),
    "soc_max":                 (0.65, 0.99),
    "battery_cost_usd_kwh":    (100.0, 500.0),
    "noise_std":               (0.0, 10.0),
}


def _to_norm_vec(params: dict[str, float]) -> np.ndarray:
    v = []
    for name in _PARAM_NAMES:
        lo, hi = _PARAM_RANGES.get(name, (0.0, 1.0))
        v.append((params.get(name, (lo + hi) / 2) - lo) / (hi - lo))
    return np.clip(np.array(v), 0.0, 1.0)


@dataclass
class ArchivedCandidate:
    """A candidate stored in the elite archive."""
    candidate_id: str
    generation: int
    params: dict[str, float]
    fitness: float
    revenue_usd_day: float = 0.0
    safety_score: float = 0.0
    battery_life_score: float = 0.0
    archived_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    run_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_policy_candidate(self) -> PolicyCandidate:
        c = PolicyCandidate(
            id=self.candidate_id,
            generation=self.generation,
            params=self.params,
            metadata=self.metadata,
        )
        c.fitness = self.fitness
        return c

    def norm_vec(self) -> np.ndarray:
        return _to_norm_vec(self.params)


class EliteArchive:
    """
    Rolling elite archive — stores the top-N most diverse, high-fitness policies.

    Insertion policy:
        1. If archive has room → always insert.
        2. If new candidate is better than worst in archive AND diverse enough → replace.
        3. Otherwise → reject.

    Persistence:
        - ``archive.json``  : current top-N archive (overwritten each time)
        - ``archive.jsonl`` : append-only full history (never deleted)

    Parameters
    ----------
    archive_dir:
        Directory for persistence files.
    max_size:
        Maximum number of candidates in the archive (default 50).
    min_diversity:
        Minimum L2 distance in normalised param space for insertion.
    """

    def __init__(
        self,
        archive_dir: str | Path = "models/evolution/archive",
        max_size: int = 50,
        min_diversity: float = _MIN_DIVERSITY_DISTANCE,
    ) -> None:
        self.archive_dir = Path(archive_dir)
        self.max_size = max_size
        self.min_diversity = min_diversity
        self._archive: list[ArchivedCandidate] = []

        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def maybe_insert(
        self,
        candidate: PolicyCandidate,
        fitness: float | None = None,
        revenue_usd_day: float = 0.0,
        safety_score: float = 0.0,
        battery_life_score: float = 0.0,
        run_id: str = "",
    ) -> bool:
        """
        Try to insert a candidate into the archive.

        Returns True if inserted, False if rejected.
        """
        fit = fitness if fitness is not None else (candidate.fitness or 0.0)

        archived = ArchivedCandidate(
            candidate_id=candidate.id,
            generation=candidate.generation,
            params=dict(candidate.params),
            fitness=fit,
            revenue_usd_day=revenue_usd_day,
            safety_score=safety_score,
            battery_life_score=battery_life_score,
            run_id=run_id,
            metadata={k: v for k, v in candidate.metadata.items() if isinstance(v, (int, float, str, bool))},
        )

        inserted = False

        if len(self._archive) < self.max_size:
            if self._is_diverse_enough(archived):
                self._archive.append(archived)
                inserted = True
                log.info("elite_archive.inserted", id=candidate.id[:12], fitness=round(fit, 4), size=len(self._archive))
        else:
            # Replace worst if new is better and diverse
            worst_idx = min(range(len(self._archive)), key=lambda i: self._archive[i].fitness)
            worst = self._archive[worst_idx]
            if fit > worst.fitness and self._is_diverse_enough(archived):
                self._archive[worst_idx] = archived
                inserted = True
                log.info(
                    "elite_archive.replaced",
                    replaced_id=worst.candidate_id[:12],
                    new_id=candidate.id[:12],
                    fitness_gain=round(fit - worst.fitness, 4),
                )

        if inserted:
            self._append_history(archived)
            self._save()

        return inserted

    def get_elite(self, n: int | None = None) -> list[PolicyCandidate]:
        """Return top-N archived candidates as PolicyCandidate objects, best first."""
        sorted_archive = sorted(self._archive, key=lambda c: c.fitness, reverse=True)
        if n is not None:
            sorted_archive = sorted_archive[:n]
        return [c.to_policy_candidate() for c in sorted_archive]

    def best(self) -> PolicyCandidate | None:
        """Return the single best archived candidate."""
        if not self._archive:
            return None
        best = max(self._archive, key=lambda c: c.fitness)
        return best.to_policy_candidate()

    def stats(self) -> dict[str, Any]:
        """Archive statistics for reporting."""
        if not self._archive:
            return {"size": 0, "best_fitness": None, "mean_fitness": None}
        fitnesses = [c.fitness for c in self._archive]
        return {
            "size": len(self._archive),
            "max_size": self.max_size,
            "best_fitness": round(max(fitnesses), 4),
            "mean_fitness": round(float(np.mean(fitnesses)), 4),
            "worst_fitness": round(min(fitnesses), 4),
            "std_fitness": round(float(np.std(fitnesses)), 4),
            "best_revenue_usd_day": round(
                max(c.revenue_usd_day for c in self._archive), 2
            ),
            "best_safety_score": round(
                max(c.safety_score for c in self._archive), 4
            ),
        }

    def pareto_front(self) -> list[ArchivedCandidate]:
        """Return the Pareto-optimal subset of the archive (3-objective)."""
        front = []
        for i, c in enumerate(self._archive):
            dominated = False
            for j, other in enumerate(self._archive):
                if i == j:
                    continue
                if _dominates_archive(other, c):
                    dominated = True
                    break
            if not dominated:
                front.append(c)
        return sorted(front, key=lambda c: c.fitness, reverse=True)

    # ──────────────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────────────

    def _is_diverse_enough(self, new: ArchivedCandidate) -> bool:
        """True if new candidate is at least min_diversity away from all archived."""
        if not self._archive:
            return True
        new_vec = new.norm_vec()
        for existing in self._archive:
            dist = float(np.linalg.norm(new_vec - existing.norm_vec()))
            if dist < self.min_diversity:
                return False
        return True

    def _save(self) -> None:
        path = self.archive_dir / "archive.json"
        data = [
            {**asdict(c), "archived_at": c.archived_at}
            for c in sorted(self._archive, key=lambda c: c.fitness, reverse=True)
        ]
        path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        path = self.archive_dir / "archive.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self._archive = [ArchivedCandidate(**d) for d in data]
            log.info("elite_archive.loaded", size=len(self._archive))
        except Exception as e:
            log.warning("elite_archive.load_failed", error=str(e))

    def _append_history(self, archived: ArchivedCandidate) -> None:
        path = self.archive_dir / "archive_history.jsonl"
        with path.open("a") as f:
            f.write(json.dumps(asdict(archived)) + "\n")


def _dominates_archive(a: ArchivedCandidate, b: ArchivedCandidate) -> bool:
    """True if ArchivedCandidate a Pareto-dominates b on 3 objectives."""
    a_obj = np.array([a.revenue_usd_day, a.safety_score, a.battery_life_score])
    b_obj = np.array([b.revenue_usd_day, b.safety_score, b.battery_life_score])
    return bool(np.all(a_obj >= b_obj) and np.any(a_obj > b_obj))
