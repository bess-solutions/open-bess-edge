# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
tests/test_fl_client.py
=========================
Test suite for BESSAIFLClient and FedAvg aggregation (Phase 2 — FL).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.interfaces.fl_client import BESSAIFLClient, FLClientConfig
from src.interfaces.fl_server import BESSAIFLServer, FedAvgAggregator


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def dummy_weights() -> list[np.ndarray]:
    """3-layer neural network stub weights."""
    return [
        np.random.randn(32, 8).astype(np.float32),
        np.random.randn(32).astype(np.float32),
        np.random.randn(4, 32).astype(np.float32),
    ]


@pytest.fixture
def client(tmp_path, dummy_weights) -> BESSAIFLClient:
    weights_file = tmp_path / "fl_weights.npz"
    np.savez(str(weights_file), *dummy_weights)
    return BESSAIFLClient(
        site_id="TEST-SITE",
        model_weights_path=weights_file,
        local_epochs=2,
    )


# ── FLClientConfig tests ──────────────────────────────────────────────────────

class TestFLClientConfig:

    def test_default_disabled(self):
        cfg = FLClientConfig()
        assert cfg.enabled is False

    def test_site_id_from_env(self, monkeypatch):
        monkeypatch.setenv("BESSAI_SITE_ID", "MY-SITE")
        cfg = FLClientConfig()
        assert cfg.site_id == "MY-SITE"

    def test_enabled_from_env(self, monkeypatch):
        monkeypatch.setenv("BESSAI_FL_ENABLED", "true")
        cfg = FLClientConfig()
        assert cfg.enabled is True


# ── BESSAIFLClient tests ──────────────────────────────────────────────────────

class TestBESSAIFLClient:

    def test_get_parameters_loads_from_file(self, client):
        params = client.get_parameters()
        assert len(params) == 3
        assert all(isinstance(p, np.ndarray) for p in params)

    def test_get_parameters_empty_if_no_file(self, tmp_path):
        c = BESSAIFLClient(site_id="X", model_weights_path=tmp_path / "nonexistent.npz")
        params = c.get_parameters()
        assert params == []

    def test_set_parameters_updates_internal_state(self, client, dummy_weights):
        new_weights = [np.zeros_like(w) for w in dummy_weights]
        client.set_parameters(new_weights)
        for a, b in zip(client._weights, new_weights):
            assert np.allclose(a, b)

    def test_fit_returns_correct_types(self, client, dummy_weights):
        params, n_samples, metrics = client.fit(dummy_weights, {"n_samples": 50})
        assert isinstance(params, list)
        assert isinstance(n_samples, int)
        assert isinstance(metrics, dict)
        assert "loss" in metrics

    def test_fit_returns_same_layer_shapes(self, client, dummy_weights):
        updated, _, _ = client.fit(dummy_weights, {})
        for orig, upd in zip(dummy_weights, updated):
            assert orig.shape == upd.shape

    def test_evaluate_returns_float_loss(self, client, dummy_weights):
        loss, n, metrics = client.evaluate(dummy_weights, {"n_samples": 30})
        assert isinstance(loss, float)
        assert 0 <= loss <= 1.0
        assert isinstance(n, int)

    def test_save_weights_creates_file(self, client, tmp_path, dummy_weights):
        client.set_parameters(dummy_weights)
        saved = client.save_weights(tmp_path / "saved.npz")
        assert saved.exists()

    def test_as_flower_client_returns_none_without_flwr(self, client):
        # In test env, flwr is likely not installed
        flower = client.as_flower_client()
        # Either None (not installed) or a valid adapter
        assert flower is None or hasattr(flower, "fit")


# ── FedAvgAggregator tests ────────────────────────────────────────────────────

class TestFedAvgAggregator:

    def test_aggregate_two_clients_equal_samples(self):
        w1 = [np.ones((4, 2)) * 1.0, np.ones(4) * 1.0]
        w2 = [np.ones((4, 2)) * 3.0, np.ones(4) * 3.0]
        result = FedAvgAggregator.aggregate([w1, w2], [100, 100])
        # Should be average: 2.0
        assert np.allclose(result[0], np.ones((4, 2)) * 2.0)
        assert np.allclose(result[1], np.ones(4) * 2.0)

    def test_aggregate_weighted_by_samples(self):
        w1 = [np.ones((2, 2)) * 1.0]
        w2 = [np.ones((2, 2)) * 3.0]
        # 25% w1, 75% w2 → 2.5
        result = FedAvgAggregator.aggregate([w1, w2], [25, 75])
        expected = 1.0 * 0.25 + 3.0 * 0.75
        assert np.allclose(result[0], np.full((2, 2), expected))

    def test_aggregate_empty_returns_empty(self):
        result = FedAvgAggregator.aggregate([], [])
        assert result == []

    def test_aggregate_single_client(self):
        w = [np.array([1.0, 2.0, 3.0])]
        result = FedAvgAggregator.aggregate([w], [50])
        assert np.allclose(result[0], w[0])

    def test_output_shape_preserved(self):
        shapes = [(16, 8), (16,), (4, 16)]
        w1 = [np.random.randn(*s).astype(np.float32) for s in shapes]
        w2 = [np.random.randn(*s).astype(np.float32) for s in shapes]
        result = FedAvgAggregator.aggregate([w1, w2], [50, 50])
        for r, s in zip(result, shapes):
            assert r.shape == s


# ── BESSAIFLServer tests ──────────────────────────────────────────────────────

class TestBESSAIFLServer:

    def _make_update(self, n_layers=3, n_samples=100) -> dict:
        return {
            "site_id": f"SITE-{n_samples}",
            "weights": [np.random.randn(8, 4).astype(np.float32) for _ in range(n_layers)],
            "n_samples": n_samples,
            "metrics": {"loss": 0.25},
        }

    def test_aggregate_round_returns_result(self, tmp_path):
        server = BESSAIFLServer(min_clients=2, output_dir=tmp_path)
        updates = [self._make_update(), self._make_update(n_samples=80)]
        result = server.aggregate_round(updates)
        assert result.n_clients == 2
        assert 0 <= result.aggregated_loss <= 1.0
        assert len(result.aggregated_weights) == 3

    def test_round_counter_increments(self, tmp_path):
        server = BESSAIFLServer(output_dir=tmp_path)
        server.aggregate_round([self._make_update()])
        server.aggregate_round([self._make_update()])
        assert server._current_round == 2

    def test_weights_saved_to_disk(self, tmp_path):
        server = BESSAIFLServer(output_dir=tmp_path)
        server.aggregate_round([self._make_update(), self._make_update(n_samples=80)])
        assert (tmp_path / "policy_fedavg_latest.npz").exists()

    def test_status_dict_structure(self, tmp_path):
        server = BESSAIFLServer(output_dir=tmp_path)
        status = server.status()
        assert "current_round" in status
        assert "min_clients_required" in status
        assert "global_weights_layers" in status
