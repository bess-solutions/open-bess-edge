# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/fl_client.py
============================
BESSAI Edge Gateway — Federated Learning Client v1.0

Implements a Flower (flwr) FL client for collaborative ONNX model refinement
across multiple BESSAI edge sites without sharing raw energy data.

Each site trains locally on its own CEN price history, then the coordinator
aggregates gradients (FedAvg) to produce a shared global policy.

Activation: Set `BESSAI_FL_ENABLED=true` in `.env` and provide `FL_SERVER_URL`.

Usage::

    from src.interfaces.fl_client import BESSAIFLClient, start_fl_client

    # Direct use
    client = BESSAIFLClient(site_id="SITE-01", model_weights_path="models/policy.npz")

    # Or use the launcher that reads config from env
    start_fl_client()
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
import structlog

log = structlog.get_logger(__name__)

__all__ = ["BESSAIFLClient", "start_fl_client", "FLClientConfig"]

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

class FLClientConfig:
    """FL client configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.enabled: bool = os.getenv("BESSAI_FL_ENABLED", "false").lower() == "true"
        self.server_url: str = os.getenv("FL_SERVER_URL", "localhost:8080")
        self.site_id: str = os.getenv("BESSAI_SITE_ID", "SITE-UNKNOWN")
        self.model_path: Path = Path(
            os.getenv("BESSAI_MODEL_PATH", "models/dispatch_policy.onnx")
        )
        self.weights_path: Path = Path(
            os.getenv("BESSAI_FL_WEIGHTS", "models/federated/fl_weights.npz")
        )
        self.local_epochs: int = int(os.getenv("FL_LOCAL_EPOCHS", "3"))


# ─────────────────────────────────────────────────────────────────────────────
# FL Client
# ─────────────────────────────────────────────────────────────────────────────

class BESSAIFLClient:
    """Federated Learning client for BESSAI edge sites.

    Implements the standard FL interface:
    - `get_parameters()` — returns local model weights as numpy arrays.
    - `fit(parameters, config)` — runs local training epochs and returns updated weights.
    - `evaluate(parameters, config)` — evaluates the global model locally.

    Parameters:
        site_id:            Identifier for this edge site.
        model_weights_path: Path to .npz file with policy weights.
        local_epochs:       Number of local gradient steps per FL round.
    """

    def __init__(
        self,
        site_id: str = "SITE-UNKNOWN",
        model_weights_path: str | Path = "models/federated/fl_weights.npz",
        local_epochs: int = 3,
    ) -> None:
        self.site_id = site_id
        self.weights_path = Path(model_weights_path)
        self.local_epochs = local_epochs
        self._weights: list[np.ndarray] = []
        self._round_metrics: dict[str, float] = {}

    # ── Parameters ────────────────────────────────────────────────────────────

    def get_parameters(self) -> list[np.ndarray]:
        """Return current local model parameters as numpy arrays."""
        if self._weights:
            return self._weights
        if self.weights_path.exists():
            loaded = np.load(str(self.weights_path), allow_pickle=True)
            self._weights = [loaded[k] for k in loaded.files]
            log.info("fl_client.params_loaded", site_id=self.site_id,
                     n_layers=len(self._weights), path=str(self.weights_path))
        else:
            log.warning("fl_client.no_weights_found", site_id=self.site_id,
                        path=str(self.weights_path))
            self._weights = []
        return self._weights

    def set_parameters(self, parameters: list[np.ndarray]) -> None:
        """Apply global parameters received from the FL server."""
        self._weights = parameters
        log.debug("fl_client.params_received", site_id=self.site_id,
                  n_layers=len(parameters))

    # ── Fit (local training) ──────────────────────────────────────────────────

    def fit(
        self,
        parameters: list[np.ndarray],
        config: dict[str, Any],
    ) -> tuple[list[np.ndarray], int, dict[str, float]]:
        """Run local training and return updated parameters.

        This stub simulates gradient steps by applying a small random
        perturbation to demonstrate the FL round mechanic. In production,
        this would load real CEN price data and run RL policy gradient updates.

        Returns:
            (updated_parameters, num_samples, metrics)
        """
        self.set_parameters(parameters)

        n_samples = config.get("n_samples", 100)
        learning_rate = float(config.get("learning_rate", 0.01))

        # Simulated local gradient steps
        updated: list[np.ndarray] = []
        for epoch in range(self.local_epochs):
            for layer in self._weights:
                # Placeholder: in production, compute real policy gradient
                noise = np.random.randn(*layer.shape) * learning_rate * 0.1
                layer = layer + noise
            log.debug("fl_client.epoch", site_id=self.site_id,
                      epoch=epoch + 1, total=self.local_epochs)

        for layer in self._weights:
            noise = np.random.randn(*layer.shape) * learning_rate * 0.1
            updated.append(layer + noise)

        self._weights = updated
        metrics = {
            "loss": float(np.random.uniform(0.1, 0.4)),
            "policy_entropy": float(np.random.uniform(0.5, 1.5)),
        }
        self._round_metrics = metrics

        log.info("fl_client.fit_complete", site_id=self.site_id,
                 n_samples=n_samples, metrics=metrics)
        return updated, n_samples, metrics

    # ── Evaluate ──────────────────────────────────────────────────────────────

    def evaluate(
        self,
        parameters: list[np.ndarray],
        config: dict[str, Any],
    ) -> tuple[float, int, dict[str, float]]:
        """Evaluate global parameters locally and return loss + metrics.

        Returns:
            (loss, num_samples, metrics)
        """
        self.set_parameters(parameters)
        n_samples = config.get("n_samples", 100)
        # Simulated evaluation — in production: run ONNX inference on local data
        loss = float(np.random.uniform(0.08, 0.35))
        accuracy = float(np.random.uniform(0.65, 0.92))
        metrics = {"accuracy": accuracy, "site_id": self.site_id}
        log.info("fl_client.evaluate_complete", site_id=self.site_id,
                 loss=round(loss, 4), accuracy=round(accuracy, 3))
        return loss, n_samples, metrics

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_weights(self, path: str | Path | None = None) -> Path:
        """Persist current weights to disk as .npz archive."""
        target = Path(path) if path else self.weights_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if self._weights:
            np.savez(str(target), *self._weights)
            log.info("fl_client.weights_saved", path=str(target))
        return target

    def as_flower_client(self):
        """Return a Flower NumPyClient wrapper if flwr is installed."""
        try:
            import flwr as fl

            client = self

            class _FlowerAdapter(fl.client.NumPyClient):
                def get_parameters(self, config):
                    return client.get_parameters()

                def fit(self, parameters, config):
                    return client.fit(parameters, config)

                def evaluate(self, parameters, config):
                    return client.evaluate(parameters, config)

            return _FlowerAdapter()
        except ImportError:
            log.warning("fl_client.flwr_not_installed",
                        msg="Install flwr to use Flower federation")
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Launcher
# ─────────────────────────────────────────────────────────────────────────────

def start_fl_client() -> None:
    """Launch the FL client based on environment config.

    Reads BESSAI_FL_ENABLED, FL_SERVER_URL, BESSAI_SITE_ID from env.
    If flwr is installed, starts a Flower client. Otherwise logs a warning.
    """
    cfg = FLClientConfig()

    if not cfg.enabled:
        log.info("fl_client.disabled", msg="Set BESSAI_FL_ENABLED=true to enable")
        return

    client = BESSAIFLClient(
        site_id=cfg.site_id,
        model_weights_path=cfg.weights_path,
        local_epochs=cfg.local_epochs,
    )
    flower_client = client.as_flower_client()

    if flower_client is None:
        log.warning("fl_client.cannot_start", reason="flwr not installed")
        return

    try:
        import flwr as fl
        log.info("fl_client.starting", server_url=cfg.server_url,
                 site_id=cfg.site_id)
        fl.client.start_numpy_client(server_address=cfg.server_url,
                                      client=flower_client)
    except Exception as e:
        log.error("fl_client.start_failed", error=str(e))
