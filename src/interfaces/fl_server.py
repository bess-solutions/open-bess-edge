# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/fl_server.py
============================
BESSAI Edge Gateway — Federated Learning Server v1.0

Implements FedAvg aggregation across BESSAI edge sites. Sites submit their
local model updates after each training round; the server aggregates them
and returns the improved global policy weights.

Activation: Run on the central coordinator node (not on the edge sites).

Usage::

    from src.interfaces.fl_server import BESSAIFLServer

    server = BESSAIFLServer(min_clients=2)
    server.start(server_address="0.0.0.0:8080", num_rounds=5)
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import structlog

__all__ = ["BESSAIFLServer", "FLRoundResult", "FedAvgAggregator"]

log = structlog.get_logger(__name__)

FEDERATED_MODELS_DIR = Path("models/federated")


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

class FLRoundResult:
    """Result from one federated learning aggregation round.

    Attributes:
        round_num:          FL round index.
        n_clients:          Number of contributing sites.
        aggregated_loss:    Weighted average loss across sites.
        aggregated_weights: FedAvg-merged global parameters.
        duration_s:         Round wall-clock time.
    """

    def __init__(
        self,
        round_num: int,
        n_clients: int,
        aggregated_loss: float,
        aggregated_weights: list[np.ndarray],
        duration_s: float,
    ) -> None:
        self.round_num = round_num
        self.n_clients = n_clients
        self.aggregated_loss = aggregated_loss
        self.aggregated_weights = aggregated_weights
        self.duration_s = duration_s

    def to_dict(self) -> dict:
        return {
            "round_num": self.round_num,
            "n_clients": self.n_clients,
            "aggregated_loss": round(self.aggregated_loss, 4),
            "n_weight_layers": len(self.aggregated_weights),
            "duration_s": round(self.duration_s, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# FedAvg Aggregator (pure Python, no flwr dependency)
# ─────────────────────────────────────────────────────────────────────────────

class FedAvgAggregator:
    """Weighted Federated Averaging (FedAvg) algorithm.

    Given N client updates each with associated sample counts, computes:
        global_w = Σ(n_i / N_total) * w_i

    Reference: McMahan et al., "Communication-Efficient Learning of Deep
    Networks from Decentralized Data", AISTATS 2017.
    """

    @staticmethod
    def aggregate(
        client_weights: list[list[np.ndarray]],
        client_samples: list[int],
    ) -> list[np.ndarray]:
        """Aggregate weight updates from multiple clients.

        Args:
            client_weights: List of per-client weight lists (each a list of np arrays).
            client_samples: Number of training samples for each client.

        Returns:
            Aggregated global weights (same structure as each client's weights).
        """
        if not client_weights:
            return []

        total_samples = sum(client_samples)
        if total_samples == 0:
            return client_weights[0]

        n_layers = len(client_weights[0])
        aggregated: list[np.ndarray] = []

        for layer_idx in range(n_layers):
            weighted_sum = np.zeros_like(client_weights[0][layer_idx], dtype=np.float64)
            for client_w, n_samples in zip(client_weights, client_samples, strict=False):
                if layer_idx < len(client_w):
                    weight = n_samples / total_samples
                    weighted_sum += weight * client_w[layer_idx].astype(np.float64)
            aggregated.append(weighted_sum.astype(client_weights[0][layer_idx].dtype))

        return aggregated


# ─────────────────────────────────────────────────────────────────────────────
# FL Server
# ─────────────────────────────────────────────────────────────────────────────

class BESSAIFLServer:
    """Federated Learning server for BESSAI multi-site policy aggregation.

    Parameters:
        min_clients:        Minimum sites required to start an FL round.
        output_dir:         Directory to save aggregated model weights.
        max_rounds:         Maximum FL rounds before auto-stopping.
    """

    def __init__(
        self,
        min_clients: int = 2,
        output_dir: str | Path = FEDERATED_MODELS_DIR,
        max_rounds: int = 10,
    ) -> None:
        self.min_clients = min_clients
        self.output_dir = Path(output_dir)
        self.max_rounds = max_rounds
        self._global_weights: list[np.ndarray] = []
        self._round_history: list[FLRoundResult] = []
        self._current_round = 0

    # ── Round management ──────────────────────────────────────────────────────

    def get_global_parameters(self) -> list[np.ndarray]:
        """Return current global model parameters to send to clients."""
        return self._global_weights

    def aggregate_round(
        self,
        client_updates: list[dict[str, Any]],
    ) -> FLRoundResult:
        """Process one FL round from client updates.

        Args:
            client_updates: List of dicts, each containing:
                - 'site_id': str
                - 'weights': list[np.ndarray]
                - 'n_samples': int
                - 'metrics': dict

        Returns:
            FLRoundResult with aggregated weights and metrics.
        """
        t0 = time.time()
        self._current_round += 1

        client_weights = [u["weights"] for u in client_updates]
        client_samples = [u.get("n_samples", 1) for u in client_updates]
        client_losses = [u.get("metrics", {}).get("loss", 0.0) for u in client_updates]

        # FedAvg aggregation
        self._global_weights = FedAvgAggregator.aggregate(client_weights, client_samples)

        # Weighted average loss
        total = sum(client_samples) or 1
        avg_loss = sum(loss_i * n_i for loss_i, n_i in zip(client_losses, client_samples, strict=False)) / total

        result = FLRoundResult(
            round_num=self._current_round,
            n_clients=len(client_updates),
            aggregated_loss=avg_loss,
            aggregated_weights=self._global_weights,
            duration_s=time.time() - t0,
        )
        self._round_history.append(result)

        log.info(
            "fl_server.round_complete",
            round_num=self._current_round,
            n_clients=len(client_updates),
            avg_loss=round(avg_loss, 4),
            duration_s=round(result.duration_s, 2),
        )

        # Auto-save aggregated weights
        self._save_global_weights()
        return result

    def _save_global_weights(self) -> Path:
        """Save global weights to disk after each round."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"policy_fedavg_r{self._current_round:03d}.npz"
        latest = self.output_dir / "policy_fedavg_latest.npz"
        if self._global_weights:
            np.savez(str(path), *self._global_weights)
            np.savez(str(latest), *self._global_weights)
            log.info("fl_server.weights_saved", path=str(latest),
                     round_num=self._current_round)
        return latest

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return server status for /fl/status API endpoint."""
        return {
            "current_round": self._current_round,
            "max_rounds": self.max_rounds,
            "min_clients_required": self.min_clients,
            "rounds_completed": len(self._round_history),
            "last_round": self._round_history[-1].to_dict() if self._round_history else None,
            "global_weights_layers": len(self._global_weights),
        }

    # ── Flower integration ────────────────────────────────────────────────────

    def start(self, server_address: str = "0.0.0.0:8080", num_rounds: int | None = None) -> None:
        """Launch Flower FL server if flwr is installed."""
        try:
            import flwr as fl

            class _FedAvgStrategy(fl.server.strategy.FedAvg):
                def aggregate_fit(self, server_round, results, failures):
                    agg, metrics = super().aggregate_fit(server_round, results, failures)
                    log.info("fl_server.flower_round", round_num=server_round,
                             n_results=len(results), n_failures=len(failures))
                    return agg, metrics

            rounds = num_rounds or self.max_rounds
            log.info("fl_server.starting", address=server_address, rounds=rounds,
                     min_clients=self.min_clients)
            fl.server.start_server(
                server_address=server_address,
                config=fl.server.ServerConfig(num_rounds=rounds),
                strategy=_FedAvgStrategy(
                    min_fit_clients=self.min_clients,
                    min_evaluate_clients=self.min_clients,
                    min_available_clients=self.min_clients,
                ),
            )
        except ImportError:
            log.warning("fl_server.flwr_not_installed",
                        msg="Install flwr to use Flower server. Using standalone mode.")
