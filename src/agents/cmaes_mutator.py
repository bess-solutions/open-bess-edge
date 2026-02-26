# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
src/agents/cmaes_mutator.py
============================
BESSAIEvolve v2 — CMA-ES (Covariance Matrix Adaptation Evolution Strategy) Mutator.

Replaces the scalar Gaussian mutation with a full CMA-ES update that adapts
the covariance structure of the parameter search space each generation.

This is the key upgrade from v1 (σ·N(0,I)) → v2 (CMA-ES), analogous to
what AlphaEvolve uses for continuous parameter spaces.

Reference:
    Hansen (2016) "The CMA Evolution Strategy: A Tutorial"
    https://arxiv.org/abs/1604.00772

Usage::

    mutator = CMAESMutator(param_bounds=POLICY_PARAM_BOUNDS)
    offspring = mutator.ask(n=7)
    mutator.tell(offspring, fitnesses)  # updates distribution
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import structlog

from src.agents.candidate_generator import PolicyCandidate

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Canonical policy parameter space
POLICY_PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "cmg_low_threshold_norm":  (0.01, 0.45),
    "cmg_high_threshold_norm": (0.15, 0.95),
    "soc_min":                 (0.05, 0.35),
    "soc_max":                 (0.65, 0.99),
    "battery_cost_usd_kwh":    (100.0, 500.0),
    "noise_std":               (0.0, 10.0),
}

_PARAM_NAMES = list(POLICY_PARAM_BOUNDS.keys())
_N_PARAMS = len(_PARAM_NAMES)


def _normalize(params: dict[str, float]) -> np.ndarray:
    """Map params from [lo, hi] → [0, 1] for CMA-ES."""
    x = np.zeros(_N_PARAMS)
    for i, name in enumerate(_PARAM_NAMES):
        lo, hi = POLICY_PARAM_BOUNDS[name]
        x[i] = (params.get(name, (lo + hi) / 2) - lo) / (hi - lo)
    return np.clip(x, 0.0, 1.0)


def _denormalize(x: np.ndarray) -> dict[str, float]:
    """Map normalized [0,1]^n → original param space."""
    params = {}
    for i, name in enumerate(_PARAM_NAMES):
        lo, hi = POLICY_PARAM_BOUNDS[name]
        params[name] = float(np.clip(lo + x[i] * (hi - lo), lo, hi))
    return params


class CMAESMutator:
    """
    Full CMA-ES mutation operator for BESSAIEvolve v2.

    Maintains the full covariance matrix and adapts step sizes per generation.
    Falls back to diagonal CMA if the full ``cma`` package is unavailable.

    Parameters
    ----------
    param_bounds:
        Dict of param_name → (lo, hi) for the search space.
    sigma0:
        Initial step size (in normalized [0,1] space).
    seed:
        RNG seed.
    state_path:
        Optional path to persist/restore CMA state across runs.
    """

    def __init__(
        self,
        param_bounds: dict[str, tuple[float, float]] = POLICY_PARAM_BOUNDS,
        sigma0: float = 0.3,
        seed: int | None = None,
        state_path: Path | str | None = None,
    ) -> None:
        self.param_bounds = param_bounds
        self.sigma0 = sigma0
        self.state_path = Path(state_path) if state_path else None
        self._rng = np.random.default_rng(seed)
        self._generation = 0
        self._use_cma_lib = False

        # Try to load the `cma` library (Hansen's official Python package)
        try:
            import cma  # type: ignore[import]
            self._cma = cma
            self._use_cma_lib = True
            log.info("cmaes_mutator.init", backend="cma-library", sigma0=sigma0)
        except ImportError:
            log.info("cmaes_mutator.init", backend="numpy-fallback", sigma0=sigma0)

        # CMA internal state (used in numpy fallback)
        n = _N_PARAMS
        self._mean = np.full(n, 0.5)   # start at center of normalized space
        self._sigma = sigma0

        # Full CMA-ES state variables
        self._pc = np.zeros(n)         # evolution path for C
        self._ps = np.zeros(n)         # evolution path for σ
        self._C = np.eye(n)            # covariance matrix
        self._D = np.ones(n)           # eigenvalues
        self._B = np.eye(n)            # eigenvectors

        self._chiN = n ** 0.5 * (1 - 1 / (4 * n) + 1 / (21 * n ** 2))
        self._mueff: float = 0.0

        # Restore state if available
        if self.state_path and self.state_path.exists():
            self._load_state()

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def ask(self, n: int = 7, generation: int = 0) -> list[PolicyCandidate]:
        """Sample n offspring from the current CMA distribution."""
        self._generation = generation

        if self._use_cma_lib:
            return self._ask_cma_lib(n, generation)
        return self._ask_numpy(n, generation)

    def tell(
        self,
        candidates: list[PolicyCandidate],
        fitnesses: list[float],
    ) -> None:
        """Update CMA distribution given fitness results (higher = better)."""
        if not candidates or not fitnesses:
            return

        # Sort by fitness descending
        pairs = sorted(zip(fitnesses, candidates, strict=False), reverse=True)
        sorted_cands = [c for _, c in pairs]

        if self._use_cma_lib:
            self._tell_cma_lib(sorted_cands, [f for f, _ in pairs])
        else:
            self._tell_numpy(sorted_cands)

        if self.state_path:
            self._save_state()

        log.info(
            "cmaes_mutator.tell",
            generation=self._generation,
            best_fitness=round(max(fitnesses), 4),
            sigma=round(float(self._sigma), 4),
        )

    # ──────────────────────────────────────────────────────────────────────
    # CMA library backend (when `pip install cma` is available)
    # ──────────────────────────────────────────────────────────────────────

    def _ask_cma_lib(self, n: int, generation: int) -> list[PolicyCandidate]:
        """Use Hansen's cma library for exact CMA-ES."""
        if not hasattr(self, "_es"):
            opts = self._cma.CMAOptions()
            opts["seed"] = int(self._rng.integers(0, 2**31))
            opts["maxiter"] = 10000
            opts["verbose"] = -9  # silent
            self._es = self._cma.CMAEvolutionStrategy(
                self._mean.tolist(),
                self.sigma0,
                opts,
            )

        solutions = self._es.ask(n)
        offspring = []
        for i, x in enumerate(solutions):
            x_clipped = np.clip(x, 0.0, 1.0)
            cand = PolicyCandidate(
                id=f"cmaes_g{generation}_i{i}_{int(time.time()*1000) % 100000}",
                generation=generation,
                params=_denormalize(x_clipped),
                metadata={"source": "cmaes_lib", "x_normalized": x_clipped.tolist()},
            )
            offspring.append(cand)
        return offspring

    def _tell_cma_lib(
        self,
        sorted_cands: list[PolicyCandidate],
        sorted_fitnesses: list[float],
    ) -> None:
        if not hasattr(self, "_es"):
            return
        solutions = [
            c.metadata.get("x_normalized", _normalize(c.params).tolist())
            for c in sorted_cands
        ]
        # cma minimizes, so negate fitness
        self._es.tell(solutions, [-f for f in sorted_fitnesses])
        self._mean = np.array(self._es.result.xbest)
        self._sigma = float(self._es.sigma)

    # ──────────────────────────────────────────────────────────────────────
    # Pure NumPy CMA-ES fallback (no external dependencies)
    # ──────────────────────────────────────────────────────────────────────

    def _ask_numpy(self, n: int, generation: int) -> list[PolicyCandidate]:
        """Sample from N(mean, σ² C) using eigendecomposition."""
        try:
            eigvals, B = np.linalg.eigh(self._C)
            eigvals = np.maximum(eigvals, 1e-10)
            D = np.sqrt(eigvals)
            self._B = B
            self._D = D
        except np.linalg.LinAlgError:
            self._B = np.eye(_N_PARAMS)
            self._D = np.ones(_N_PARAMS)

        offspring = []
        for i in range(n):
            z = self._rng.standard_normal(_N_PARAMS)
            x = self._mean + self._sigma * (self._B @ (self._D * z))
            x = np.clip(x, 0.0, 1.0)
            cand = PolicyCandidate(
                id=f"cmaes_np_g{generation}_i{i}_{int(time.time()*1000) % 100000}",
                generation=generation,
                params=_denormalize(x),
                metadata={
                    "source": "cmaes_numpy",
                    "x_normalized": x.tolist(),
                    "sigma": float(self._sigma),
                },
            )
            offspring.append(cand)
        return offspring

    def _tell_numpy(self, sorted_cands: list[PolicyCandidate]) -> None:
        """CMA-ES update: update mean, σ, and C from ranked offspring."""
        mu = max(1, len(sorted_cands) // 2)
        weights = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
        weights /= weights.sum()
        mueff = 1.0 / (weights ** 2).sum()
        self._mueff = mueff

        n = _N_PARAMS
        cc  = (4 + mueff / n) / (n + 4 + 2 * mueff / n)
        cs  = (mueff + 2) / (n + mueff + 5)
        c1  = 2 / ((n + 1.3) ** 2 + mueff)
        cmu = min(1 - c1, 2 * (mueff - 2 + 1 / mueff) / ((n + 2) ** 2 + mueff))
        damps = 1 + 2 * max(0, np.sqrt((mueff - 1) / (n + 1)) - 1) + cs

        # Weighted mean of top-mu solutions
        xs = np.array([
            c.metadata.get("x_normalized", _normalize(c.params).tolist())
            for c in sorted_cands[:mu]
        ])
        old_mean = self._mean.copy()
        self._mean = weights @ xs

        # Step-size control (CSA)
        invsqrtC = self._B @ np.diag(1.0 / np.maximum(self._D, 1e-10)) @ self._B.T
        self._ps = (1 - cs) * self._ps + np.sqrt(cs * (2 - cs) * mueff) * (
            invsqrtC @ (self._mean - old_mean) / self._sigma
        )
        hsig = (
            np.linalg.norm(self._ps) / np.sqrt(1 - (1 - cs) ** (2 * (self._generation + 1)))
            / self._chiN < 1.4 + 2 / (n + 1)
        )

        # Covariance matrix adaptation (CMA)
        self._pc = (1 - cc) * self._pc + hsig * np.sqrt(cc * (2 - cc) * mueff) * (
            (self._mean - old_mean) / self._sigma
        )
        artmp = (xs[:mu] - old_mean) / self._sigma
        self._C = (
            (1 - c1 - cmu) * self._C
            + c1 * (np.outer(self._pc, self._pc) + (1 - int(hsig)) * cc * (2 - cc) * self._C)
            + cmu * (weights[:mu] * artmp.T @ artmp)
        )

        # σ update
        self._sigma *= np.exp((cs / damps) * (np.linalg.norm(self._ps) / self._chiN - 1))
        self._sigma = float(np.clip(self._sigma, 1e-4, 1.0))

    # ──────────────────────────────────────────────────────────────────────
    # State persistence
    # ──────────────────────────────────────────────────────────────────────

    def _save_state(self) -> None:
        state: dict[str, Any] = {
            "generation": self._generation,
            "mean": self._mean.tolist(),
            "sigma": float(self._sigma),
            "pc": self._pc.tolist(),
            "ps": self._ps.tolist(),
            "C": self._C.tolist(),
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        self.state_path.write_text(json.dumps(state, indent=2))  # type: ignore[union-attr]

    def _load_state(self) -> None:
        try:
            state = json.loads(self.state_path.read_text())  # type: ignore[union-attr]
            self._generation = state.get("generation", 0)
            self._mean = np.array(state["mean"])
            self._sigma = float(state["sigma"])
            self._pc = np.array(state["pc"])
            self._ps = np.array(state["ps"])
            self._C = np.array(state["C"])
            log.info("cmaes_mutator.state_restored", generation=self._generation)
        except Exception as e:
            log.warning("cmaes_mutator.state_load_failed", error=str(e))
