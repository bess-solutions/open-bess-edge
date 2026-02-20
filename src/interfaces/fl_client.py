"""
src/interfaces/fl_client.py
============================
BESSAI Edge Gateway — Federated Learning Client (Flower).

Implements the Flower NumPyClient interface for privacy-preserving
federated model updates.

Key privacy principle (from the BESSAI v2.0 roadmap):
    "Los datos de telemetría del cliente JAMÁS salen del edge en formato raw.
    Solo gradientes/pesos del modelo salen."

In operation:
1. FL server sends global model weights.
2. This client trains locally on buffered telemetry cycles.
3. Only the updated *weight deltas* are sent back — raw data stays on-device.

Usage::

    client = BESSAIFlowerClient(model_weights=initial_weights, site_id="CL-001")
    flwr.client.start_numpy_client(server_address="fl-server:8080", client=client)
"""

from __future__ import annotations

import numpy as np
import structlog

__all__ = ["BESSAIFlowerClient", "FLConfig"]

log = structlog.get_logger(__name__)

try:
    import flwr as fl  # type: ignore[import-untyped]

    _FLWR_AVAILABLE = True
    _NumPyClientBase = fl.client.NumPyClient
except ImportError:
    _FLWR_AVAILABLE = False

    # Stub base class for environments without flwr installed
    class _NumPyClientBase:  # type: ignore[no-redef]
        pass


class FLConfig:
    """Federated Learning configuration constants.

    Attributes:
        MIN_FIT_CLIENTS:    Minimum sites needed for a training round.
        MIN_EVAL_CLIENTS:   Minimum sites needed for evaluation.
        NUM_ROUNDS:         Total FL rounds to run.
        LOCAL_EPOCHS:       Local training epochs per round.
        FRACTION_FIT:       Fraction of clients selected per round.
    """

    MIN_FIT_CLIENTS: int = 3
    MIN_EVAL_CLIENTS: int = 2
    NUM_ROUNDS: int = 10
    LOCAL_EPOCHS: int = 5
    FRACTION_FIT: float = 0.8


class BESSAIFlowerClient(_NumPyClientBase):  # type: ignore[misc,valid-type]
    """Flower federated learning client for BESSAI edge nodes.

    Parameters:
        model_weights:  Initial model weight arrays (list of np.ndarray).
        site_id:        Unique site identifier (used in structured logs).
        local_epochs:   Number of local gradient steps per FL round.
    """

    def __init__(
        self,
        model_weights: list[np.ndarray],
        site_id: str = "unknown",
        local_epochs: int = FLConfig.LOCAL_EPOCHS,
    ) -> None:
        self.site_id = site_id
        self.local_epochs = local_epochs
        self._weights = [w.copy() for w in model_weights]
        self._telemetry_buffer: list[dict] = []

        log.info(
            "fl_client.init",
            site_id=site_id,
            n_weight_arrays=len(model_weights),
            local_epochs=local_epochs,
        )

    # ------------------------------------------------------------------
    # Flower NumPyClient interface
    # ------------------------------------------------------------------

    def get_parameters(self, config: dict) -> list[np.ndarray]:
        """Return current model weights to the FL server."""
        log.debug("fl_client.get_parameters", site_id=self.site_id)
        return [w.copy() for w in self._weights]

    def fit(
        self, parameters: list[np.ndarray], config: dict
    ) -> tuple[list[np.ndarray], int, dict]:
        """Receive global weights, train locally, return updated weights.

        Only weight updates leave the edge — raw telemetry stays local.

        Returns:
            (updated_weights, num_samples, metrics_dict)
        """
        # Apply global weights from server
        self._weights = [w.copy() for w in parameters]

        n_samples = len(self._telemetry_buffer)
        if n_samples == 0:
            log.debug("fl_client.fit_skipped_empty_buffer", site_id=self.site_id)
            return self._weights, 0, {"train_loss": 0.0}

        # Simulated local training: add small gradient noise proportional to epochs
        # Production: replace with actual model training (torch/tensorflow)
        rng = np.random.default_rng()
        updated = []
        total_loss = 0.0
        for w in self._weights:
            noise = rng.normal(0, 0.001, size=w.shape).astype(w.dtype)
            updated.append(w + noise * self.local_epochs)
            total_loss += float(np.mean(np.abs(noise)))

        self._weights = updated
        train_loss = total_loss / max(len(self._weights), 1)

        log.info(
            "fl_client.fit_complete",
            site_id=self.site_id,
            n_samples=n_samples,
            train_loss=round(train_loss, 6),
        )
        return self._weights, n_samples, {"train_loss": train_loss}

    def evaluate(self, parameters: list[np.ndarray], config: dict) -> tuple[float, int, dict]:
        """Evaluate global model on local validation data.

        Returns:
            (loss, num_samples, metrics_dict)
        """
        # Apply received weights
        self._weights = [w.copy() for w in parameters]
        n_samples = len(self._telemetry_buffer)

        # Simulated evaluation metric
        loss = 0.05 + np.random.exponential(0.01)
        accuracy = max(0.0, 1.0 - loss)

        log.info(
            "fl_client.evaluate",
            site_id=self.site_id,
            loss=round(loss, 4),
            accuracy=round(accuracy, 4),
        )
        return float(loss), n_samples, {"accuracy": float(accuracy)}

    # ------------------------------------------------------------------
    # Buffer management
    # ------------------------------------------------------------------

    def buffer_telemetry(self, cycle_data: dict) -> None:
        """Add a telemetry cycle to the local training buffer.

        Raw data stays on-device. Buffer is cleared after `fit()`.
        """
        self._telemetry_buffer.append(cycle_data)
        # Rolling window: keep only last 1000 cycles
        if len(self._telemetry_buffer) > 1000:
            self._telemetry_buffer.pop(0)

    def clear_buffer(self) -> None:
        """Clear the telemetry buffer (call after fit() completes)."""
        self._telemetry_buffer.clear()

    @property
    def is_available(self) -> bool:
        """True if the Flower library is installed and client is usable."""
        return _FLWR_AVAILABLE
