# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/fl_coordinator.py
============================
BESSAI Edge Gateway — Federated Learning Coordinator (BEP-0600).

Implements the Federated Learning coordination layer for BESSAI, enabling
multiple BESSAI edge sites to collaboratively improve a shared ONNX DRL model
without exchanging raw telemetry data.

Architecture:
  - FLCoordinator acts as a federated server (orchestrator)
  - Each SiteProxy becomes a federated client (sends model weights only)
  - Aggregation uses FedAvg (weighted average by site capacity)
  - No raw data ever leaves the site — only model weight deltas

BEP-0600 spec reference: docs/bep/BEP-0600.md

Flower integration (when available):
    Although designed to be compatible with ``flwr`` (Flower), this module
    provides a self-contained stub that works without it. The stub uses
    in-process simulation for unit testing.

Usage::

    coord = FLCoordinator(min_clients=2, rounds=3)
    coord.register_client("CL-001", capacity_kwh=200.0)
    coord.register_client("CL-002", capacity_kwh=500.0)
    result = coord.run_round(client_updates={
        "CL-001": {"layer0": [1.0, 0.5, -0.3]},
        "CL-002": {"layer0": [0.8, 0.6, -0.1]},
    })
    print(result.global_weights)   # FedAvg aggregated weights
    print(result.round_id)
    print(result.n_clients)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

__all__ = [
    "FLCoordinator",
    "FLClientInfo",
    "FLRoundResult",
    "FedAvgAggregator",
]

log = structlog.get_logger(__name__)

# Type alias: model weights are dict of layer_name → list[float]
WeightDict = dict[str, list[float]]


@dataclass
class FLClientInfo:
    """Metadata for a registered federated learning client (edge site)."""

    client_id: str
    capacity_kwh: float  # Used as weight in FedAvg
    last_update: float = field(default_factory=time.time)
    rounds_participated: int = 0
    is_active: bool = True

    @property
    def weight(self) -> float:
        """Normalized capacity weight for FedAvg (un-normalized)."""
        return self.capacity_kwh


@dataclass
class FLRoundResult:
    """Result of a single federated learning round."""

    round_id: int
    n_clients: int
    global_weights: WeightDict
    aggregation_method: str
    duration_s: float
    convergence_delta: float  # L2 norm of weight change from previous round
    timestamp: float = field(default_factory=time.time)

    @property
    def converged(self) -> bool:
        """True if weight delta is below convergence threshold."""
        return self.convergence_delta < 1e-4


class FedAvgAggregator:
    """Federated Averaging (FedAvg) weight aggregation.

    Computes a capacity-weighted average of client weight updates.
    Each client's contribution is proportional to its BESS capacity (kWh),
    reflecting that larger sites have more representative operational data.

    Reference: McMahan et al. 2017 — Communication-Efficient Learning of
    Deep Networks from Decentralized Data.
    """

    @staticmethod
    def aggregate(
        client_updates: dict[str, WeightDict],
        client_weights: dict[str, float],
    ) -> WeightDict:
        """Compute capacity-weighted FedAvg across all client updates.

        Args:
            client_updates:  Dict of {client_id: WeightDict}.
            client_weights:  Dict of {client_id: capacity_kwh}.

        Returns:
            Aggregated global WeightDict.

        Raises:
            ValueError: If client_updates is empty or weight sum is zero.
        """
        if not client_updates:
            raise ValueError("FedAvg requires at least one client update")

        total_weight = sum(client_weights.get(cid, 1.0) for cid in client_updates)
        if total_weight <= 0:
            raise ValueError("Total client weight must be > 0")

        aggregated: WeightDict = {}
        for client_id, weights in client_updates.items():
            w = client_weights.get(client_id, 1.0) / total_weight
            for layer, values in weights.items():
                if layer not in aggregated:
                    aggregated[layer] = [0.0] * len(values)
                for i, v in enumerate(values):
                    aggregated[layer][i] += w * v

        return aggregated

    @staticmethod
    def l2_delta(prev: WeightDict, curr: WeightDict) -> float:
        """Compute L2 norm of weight delta between two global models."""
        total = 0.0
        for layer in curr:
            prev_vals = prev.get(layer, [0.0] * len(curr[layer]))
            for a, b in zip(prev_vals, curr[layer], strict=False):
                total += (b - a) ** 2
        return total**0.5


class FLCoordinator:
    """Federated Learning Coordinator for BESSAI multi-site fleet.

    Orchestrates federated learning rounds across registered edge sites.
    Uses FedAvg aggregation weighted by site BESS capacity.

    Parameters:
        min_clients:        Minimum number of active clients to start a round.
        rounds:             Total number of FL rounds to run (per session).
        aggregator:         FedAvg aggregator instance (injectable for testing).
        convergence_threshold: L2 delta below which training is considered converged.
    """

    def __init__(
        self,
        min_clients: int = 2,
        rounds: int = 10,
        aggregator: FedAvgAggregator | None = None,
        convergence_threshold: float = 1e-4,
    ) -> None:
        self.min_clients = min_clients
        self.rounds = rounds
        self.convergence_threshold = convergence_threshold
        self._aggregator = aggregator or FedAvgAggregator()
        self._clients: dict[str, FLClientInfo] = {}
        self._global_weights: WeightDict = {}
        self._round_id: int = 0
        self._history: list[FLRoundResult] = []

    # ------------------------------------------------------------------
    # Client registration
    # ------------------------------------------------------------------

    def register_client(self, client_id: str, capacity_kwh: float = 100.0) -> None:
        """Register an edge site as a federated learning client."""
        self._clients[client_id] = FLClientInfo(
            client_id=client_id,
            capacity_kwh=capacity_kwh,
        )
        log.info("fl.client_registered", client_id=client_id, capacity_kwh=capacity_kwh)

    def deactivate_client(self, client_id: str) -> None:
        """Mark a client as inactive (excluded from future rounds)."""
        if client_id in self._clients:
            self._clients[client_id].is_active = False
            log.info("fl.client_deactivated", client_id=client_id)

    @property
    def active_clients(self) -> list[FLClientInfo]:
        """List of currently active clients."""
        return [c for c in self._clients.values() if c.is_active]

    @property
    def n_clients(self) -> int:
        return len(self._clients)

    @property
    def n_active(self) -> int:
        return len(self.active_clients)

    # ------------------------------------------------------------------
    # FL round execution
    # ------------------------------------------------------------------

    def run_round(
        self,
        client_updates: dict[str, WeightDict],
        force: bool = False,
    ) -> FLRoundResult:
        """Execute one federated learning round.

        Args:
            client_updates: Dict of {client_id: WeightDict} from participating clients.
            force:          If True, run even if fewer than min_clients respond.

        Returns:
            FLRoundResult with aggregated global weights.

        Raises:
            RuntimeError: If fewer than min_clients respond and force=False.
        """
        t0 = time.perf_counter()

        # Filter to only updates from registered active clients
        valid_updates = {
            cid: w
            for cid, w in client_updates.items()
            if cid in self._clients and self._clients[cid].is_active
        }

        if len(valid_updates) < self.min_clients and not force:
            raise RuntimeError(
                f"FL round {self._round_id + 1} requires ≥ {self.min_clients} clients, "
                f"got {len(valid_updates)}: {list(valid_updates.keys())}"
            )

        # Build weight map (capacity → FedAvg weight)
        capacity_map = {cid: self._clients[cid].capacity_kwh for cid in valid_updates}

        # Aggregate
        prev_weights = dict(self._global_weights)
        self._global_weights = self._aggregator.aggregate(valid_updates, capacity_map)

        # Compute convergence delta
        delta = self._aggregator.l2_delta(prev_weights, self._global_weights)

        self._round_id += 1

        # Update client participation counters
        for cid in valid_updates:
            self._clients[cid].rounds_participated += 1
            self._clients[cid].last_update = time.time()

        result = FLRoundResult(
            round_id=self._round_id,
            n_clients=len(valid_updates),
            global_weights=dict(self._global_weights),
            aggregation_method="FedAvg",
            duration_s=time.perf_counter() - t0,
            convergence_delta=delta,
        )
        self._history.append(result)

        log.info(
            "fl.round_complete",
            round_id=self._round_id,
            n_clients=len(valid_updates),
            delta=round(delta, 6),
            converged=result.converged,
            duration_s=round(result.duration_s, 4),
        )
        return result

    def run_session(
        self,
        client_update_fn: Any,
        stop_on_convergence: bool = True,
    ) -> list[FLRoundResult]:
        """Run multiple FL rounds until convergence or ``rounds`` exhausted.

        Args:
            client_update_fn:   Callable(round_id, global_weights) → dict[str, WeightDict].
                                Called each round to get client updates.
            stop_on_convergence: Stop early if ``converged`` is True.

        Returns:
            List of FLRoundResult per completed round.
        """
        results: list[FLRoundResult] = []
        for _ in range(self.rounds):
            updates = client_update_fn(self._round_id, self._global_weights)
            result = self.run_round(updates)
            results.append(result)
            if stop_on_convergence and result.converged:
                log.info("fl.converged_early", round_id=result.round_id)
                break
        return results

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def global_weights(self) -> WeightDict:
        return dict(self._global_weights)

    @property
    def round_id(self) -> int:
        return self._round_id

    @property
    def history(self) -> list[FLRoundResult]:
        return list(self._history)

    def is_ready(self) -> bool:
        """True if enough active clients are registered to start a round."""
        return self.n_active >= self.min_clients
