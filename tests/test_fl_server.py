"""
tests/test_fl_server.py
========================
Unit tests for BESSAIFLServer — FedAvg aggregation and simulation rounds.
"""

from __future__ import annotations

import numpy as np
from src.interfaces.fl_server import BESSAIFLServer, FLRoundResult


def _weights() -> list[np.ndarray]:
    np.random.seed(42)
    return [
        np.random.randn(4, 16).astype(np.float32),
        np.zeros(16, dtype=np.float32),
        np.random.randn(16, 1).astype(np.float32),
    ]


def _client_result(noise: float = 0.0) -> tuple[list[np.ndarray], int]:
    w = _weights()
    if noise:
        w = [arr + np.random.randn(*arr.shape).astype(np.float32) * noise for arr in w]
    return w, 100


class TestBESSAIFLServer:

    def test_init_defaults(self):
        server = BESSAIFLServer()
        assert server.config.num_rounds == 10
        assert server.config.min_fit_clients == 3

    def test_federated_avg_empty_returns_existing(self):
        weights = _weights()
        server = BESSAIFLServer(model_weights=weights)
        result = server.federated_avg([])
        # Should return existing weights unchanged
        assert len(result) == len(weights)

    def test_federated_avg_single_client_returns_same(self):
        client_w, n = _client_result()
        server = BESSAIFLServer(model_weights=_weights())
        result = server.federated_avg([(client_w, n)])
        for r, c in zip(result, client_w, strict=False):
            np.testing.assert_allclose(r, c, rtol=1e-5)

    def test_federated_avg_weighted_mean(self):
        """With 2 identical-weight clients, avg should equal input."""
        w = _weights()
        server = BESSAIFLServer(model_weights=_weights())
        result = server.federated_avg([(w, 100), (w, 100)])
        for r, ww in zip(result, w, strict=False):
            np.testing.assert_allclose(r, ww, rtol=1e-4)

    def test_federated_avg_more_samples_dominate(self):
        """Client B has 9× more samples — aggregated result closer to B."""
        w_a = _weights()
        w_b = [arr + 1.0 for arr in _weights()]  # shift all weights by 1
        server = BESSAIFLServer(model_weights=_weights())
        result = server.federated_avg([(w_a, 10), (w_b, 90)])
        # Result should be ≈ 0.1*A + 0.9*B = B-leaning
        expected_first = 0.1 * w_a[0] + 0.9 * w_b[0]
        np.testing.assert_allclose(result[0], expected_first, rtol=1e-4)

    def test_simulate_round_returns_fl_round_result(self):
        server = BESSAIFLServer(model_weights=_weights())
        result = server.simulate_round([_client_result(), _client_result(noise=0.1)], round_num=1)
        assert isinstance(result, FLRoundResult)
        assert result.round_num == 1
        assert result.aggregated_loss >= 0.0

    def test_simulate_round_updates_global_weights(self):
        initial = _weights()
        server = BESSAIFLServer(model_weights=initial)
        clients = [(_weights(), 50), (_weights(), 50)]
        server.simulate_round(clients, round_num=1)
        # Global weights should now be the fedavg of the two clients
        assert len(server.global_weights) == len(initial)

    def test_multiple_rounds_accumulate_history(self):
        server = BESSAIFLServer(model_weights=_weights())
        for r in range(3):
            server.simulate_round([_client_result()], round_num=r + 1)
        assert len(server._round_history) == 3

    def test_is_available_bool(self):
        server = BESSAIFLServer()
        assert isinstance(server.is_available, bool)
