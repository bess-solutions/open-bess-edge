"""
tests/test_fl_client.py
========================
Unit tests for BESSAIFlowerClient.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.interfaces.fl_client import BESSAIFlowerClient, FLConfig


def _initial_weights() -> list[np.ndarray]:
    """Simple 4-layer weight init matching a dispatch policy network."""
    return [
        np.random.randn(4, 16).astype(np.float32),    # layer 0 weights
        np.zeros(16, dtype=np.float32),                # layer 0 bias
        np.random.randn(16, 8).astype(np.float32),     # layer 1 weights
        np.zeros(8, dtype=np.float32),                 # layer 1 bias
        np.random.randn(8, 1).astype(np.float32),      # layer 2 weights
        np.zeros(1, dtype=np.float32),                 # layer 2 bias
    ]


class TestBESSAIFlowerClient:

    def test_get_parameters_returns_copies(self):
        weights = _initial_weights()
        client = BESSAIFlowerClient(weights, site_id="test-001")
        params = client.get_parameters({})
        assert len(params) == len(weights)
        # Should be copies, not references
        params[0][0, 0] = 9999.0
        assert client._weights[0][0, 0] != 9999.0

    def test_fit_empty_buffer_returns_zero_samples(self):
        client = BESSAIFlowerClient(_initial_weights(), site_id="test-002")
        updated_params, n_samples, metrics = client.fit(_initial_weights(), {})
        assert n_samples == 0
        assert "train_loss" in metrics

    def test_fit_with_buffered_data_returns_positive_samples(self):
        client = BESSAIFlowerClient(_initial_weights(), site_id="test-003")
        for i in range(10):
            client.buffer_telemetry({"soc": 0.5 + i * 0.01, "power_kw": 10.0})
        _, n_samples, metrics = client.fit(_initial_weights(), {})
        assert n_samples == 10
        assert metrics["train_loss"] >= 0.0

    def test_fit_updates_weights(self):
        weights = _initial_weights()
        client = BESSAIFlowerClient(weights, site_id="test-004")
        client.buffer_telemetry({"soc": 0.7})
        original_w0 = weights[0].copy()
        updated_params, _, _ = client.fit(weights, {})
        # Weights should differ after local training
        assert not np.allclose(updated_params[0], original_w0)

    def test_evaluate_returns_loss_and_accuracy(self):
        client = BESSAIFlowerClient(_initial_weights(), site_id="test-005")
        loss, n_samples, metrics = client.evaluate(_initial_weights(), {})
        assert loss >= 0.0
        assert "accuracy" in metrics
        assert 0.0 <= metrics["accuracy"] <= 1.0

    def test_buffer_telemetry_rolling_window(self):
        client = BESSAIFlowerClient(_initial_weights(), site_id="test-006")
        for i in range(1100):
            client.buffer_telemetry({"step": i})
        assert len(client._telemetry_buffer) <= 1000

    def test_clear_buffer_empties_data(self):
        client = BESSAIFlowerClient(_initial_weights(), site_id="test-007")
        client.buffer_telemetry({"x": 1})
        client.clear_buffer()
        assert len(client._telemetry_buffer) == 0

    def test_fl_config_constants(self):
        assert FLConfig.MIN_FIT_CLIENTS >= 1
        assert FLConfig.NUM_ROUNDS >= 1
        assert 0.0 < FLConfig.FRACTION_FIT <= 1.0
