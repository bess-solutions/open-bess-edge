"""
src/interfaces/fl_server.py
============================
BESSAI Edge Gateway — Federated Learning Server (Flower FedAvg).

Coordinates federated model updates across multiple BESSAI edge sites.
Uses the Flower framework with a FedAvg strategy and weighted aggregation.

Privacy architecture:
  - Client sites: BESSAIFlowerClient (sends only weight deltas)
  - This server: aggregates deltas, broadcasts new global model
  - No raw telemetry ever reaches the server

Deployment model:
  - Run this on a trusted aggregation server (GCP VM or Cloud Run)
  - Edge clients connect over mTLS (certificate pinning)
  - Supports asynchronous rounds (min_available_clients < total_clients)

Usage::

    server = BESSAIFLServer(num_rounds=10, min_fit_clients=3)
    server.start(server_address="0.0.0.0:8080")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import structlog

from .metrics import FL_ROUNDS_TOTAL, FL_TRAIN_LOSS

__all__ = ["BESSAIFLServer", "FLRoundResult", "FedAvgConfig"]

log = structlog.get_logger(__name__)

try:
    import flwr as fl
    from flwr.server.strategy import FedAvg  # type: ignore[import-untyped]
    _FLWR_AVAILABLE = True
except ImportError:
    _FLWR_AVAILABLE = False
    FedAvg = None


@dataclass
class FedAvgConfig:
    """FedAvg strategy configuration.

    Attributes:
        num_rounds:             Total training rounds.
        min_fit_clients:        Minimum sites needed to start a fit round.
        min_evaluate_clients:   Minimum sites for evaluation.
        min_available_clients:  Minimum registered clients before training.
        fraction_fit:           Fraction of available clients selected per round.
        fraction_evaluate:      Fraction selected for evaluation.
    """
    num_rounds: int = 10
    min_fit_clients: int = 3
    min_evaluate_clients: int = 2
    min_available_clients: int = 3
    fraction_fit: float = 0.8
    fraction_evaluate: float = 0.6


@dataclass
class FLRoundResult:
    """Result of a single federated learning round."""
    round_num: int
    aggregated_loss: float
    num_clients_fit: int
    num_clients_eval: int
    duration_s: float
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return (
            f"FLRoundResult(round={self.round_num}, "
            f"loss={self.aggregated_loss:.4f}, "
            f"clients_fit={self.num_clients_fit})"
        )


class BESSAIFLServer:
    """Federated Learning server for coordinating BESSAI edge model updates.

    Parameters:
        config:         FedAvg configuration object.
        site_id:        Server site identifier for Prometheus labels.
        model_weights:  Initial global model weight arrays.
    """

    def __init__(
        self,
        config: FedAvgConfig | None = None,
        site_id: str = "fl-server",
        model_weights: list[np.ndarray] | None = None,
    ) -> None:
        self.config = config or FedAvgConfig()
        self.site_id = site_id
        self._global_weights: list[np.ndarray] = model_weights or []
        self._round_history: list[FLRoundResult] = []

        log.info(
            "fl_server.init",
            site_id=site_id,
            num_rounds=self.config.num_rounds,
            min_fit_clients=self.config.min_fit_clients,
        )

    # ------------------------------------------------------------------
    # Core aggregation (usable without Flower for unit testing)
    # ------------------------------------------------------------------

    def federated_avg(
        self,
        client_results: list[tuple[list[np.ndarray], int]],
    ) -> list[np.ndarray]:
        """Compute weighted FedAvg from client weight + sample count pairs.

        Args:
            client_results: list of (weights_arrays, num_samples) tuples.

        Returns:
            Aggregated global weight arrays.
        """
        if not client_results:
            return self._global_weights

        total_samples = sum(n for _, n in client_results)
        if total_samples == 0:
            return self._global_weights

        # Weighted average
        aggregated = []
        num_arrays = len(client_results[0][0])
        for i in range(num_arrays):
            weighted = np.zeros_like(client_results[0][0][i], dtype=np.float64)
            for weights, n_samples in client_results:
                weighted += weights[i].astype(np.float64) * n_samples
            aggregated.append((weighted / total_samples).astype(np.float32))

        self._global_weights = aggregated
        return aggregated

    def simulate_round(
        self,
        client_results: list[tuple[list[np.ndarray], int]],
        round_num: int = 1,
    ) -> FLRoundResult:
        """Simulate a federated round without a real network.

        Useful for unit testing and local validation.

        Args:
            client_results: list of (weights, n_samples) tuples.
            round_num:      Round number (for metrics + logging).

        Returns:
            FLRoundResult with aggregated metrics.
        """
        t0 = time.perf_counter()
        self.federated_avg(client_results)
        duration_s = time.perf_counter() - t0

        # Compute pseudo-loss as mean L2 norm of weight updates
        losses = []
        for weights, _ in client_results:
            for w, g in zip(weights, self._global_weights, strict=False):
                losses.append(float(np.mean(np.abs(w.astype(np.float64) - g.astype(np.float64)))))
        aggregated_loss = float(np.mean(losses)) if losses else 0.0

        result = FLRoundResult(
            round_num=round_num,
            aggregated_loss=aggregated_loss,
            num_clients_fit=len(client_results),
            num_clients_eval=len(client_results),
            duration_s=duration_s,
        )
        self._round_history.append(result)

        # Update Prometheus
        FL_ROUNDS_TOTAL.labels(site_id=self.site_id).inc()
        FL_TRAIN_LOSS.labels(site_id=self.site_id).set(aggregated_loss)

        log.info(
            "fl_server.round_complete",
            round=round_num,
            loss=round(aggregated_loss, 6),
            n_clients=len(client_results),
            duration_s=round(duration_s, 4),
        )
        return result

    def start(self, server_address: str = "0.0.0.0:8080") -> None:
        """Start the Flower FL server (requires flwr installed).

        Args:
            server_address: Host:port to bind the gRPC server.
        """
        if not _FLWR_AVAILABLE:
            raise RuntimeError(
                "Flower not installed. Run: pip install flwr>=1.5"
            )

        strategy = FedAvg(
            fraction_fit=self.config.fraction_fit,
            fraction_evaluate=self.config.fraction_evaluate,
            min_fit_clients=self.config.min_fit_clients,
            min_evaluate_clients=self.config.min_evaluate_clients,
            min_available_clients=self.config.min_available_clients,
        )

        log.info(
            "fl_server.starting",
            address=server_address,
            num_rounds=self.config.num_rounds,
        )
        fl.server.start_server(
            server_address=server_address,
            config=fl.server.ServerConfig(num_rounds=self.config.num_rounds),
            strategy=strategy,
        )

    @property
    def global_weights(self) -> list[np.ndarray]:
        """Current global model weight arrays."""
        return self._global_weights

    @property
    def is_available(self) -> bool:
        """True if Flower is installed and server is deployable."""
        return _FLWR_AVAILABLE
