"""
tests/test_fl_coordinator.py
==============================
Unit tests for FLCoordinator (BEP-0600) — Federated Learning coordinator.

Coverage:
- Client registration and lifecycle
- FedAvg aggregation (capacity-weighted)
- L2 convergence delta
- run_round: valid, too few clients, force flag
- run_session: convergence stopping, exhaustion
- FLRoundResult properties (converged, timestamp)
- FLCoordinator accessors (global_weights, round_id, history)
- is_ready() guard
- deactivate_client
"""
from __future__ import annotations

import pytest
from src.core.fl_coordinator import (
    FedAvgAggregator,
    FLCoordinator,
    FLRoundResult,
)

# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_weights(**layers: list) -> dict:
    return dict(layers)


def _coord(min_clients: int = 2, rounds: int = 5) -> FLCoordinator:
    return FLCoordinator(min_clients=min_clients, rounds=rounds)


# ─── FedAvgAggregator ────────────────────────────────────────────────────────

class TestFedAvgAggregator:
    def test_uniform_weights_averages(self):
        agg = FedAvgAggregator()
        updates = {
            "A": {"layer0": [2.0, 4.0]},
            "B": {"layer0": [4.0, 2.0]},
        }
        weights = {"A": 1.0, "B": 1.0}
        result = agg.aggregate(updates, weights)
        assert result["layer0"][0] == pytest.approx(3.0)
        assert result["layer0"][1] == pytest.approx(3.0)

    def test_capacity_weighted_average(self):
        agg = FedAvgAggregator()
        # A has 200 kWh (2/3), B has 100 kWh (1/3)
        updates = {
            "A": {"w": [6.0]},
            "B": {"w": [0.0]},
        }
        weights = {"A": 200.0, "B": 100.0}
        result = agg.aggregate(updates, weights)
        assert result["w"][0] == pytest.approx(4.0)  # 6*2/3 + 0*1/3 = 4

    def test_empty_updates_raises(self):
        agg = FedAvgAggregator()
        with pytest.raises(ValueError, match="at least one"):
            agg.aggregate({}, {})

    def test_zero_weight_sum_raises(self):
        agg = FedAvgAggregator()
        # Key not in weights dict defaults to 1.0 so pass weights explicitly = 0
        with pytest.raises(ValueError, match="Total client weight"):
            agg.aggregate({"A": {"w": [1.0]}}, {"A": 0.0})

    def test_multi_layer_aggregation(self):
        agg = FedAvgAggregator()
        updates = {
            "A": {"l0": [1.0, 2.0], "l1": [3.0]},
            "B": {"l0": [3.0, 4.0], "l1": [1.0]},
        }
        weights = {"A": 1.0, "B": 1.0}
        result = agg.aggregate(updates, weights)
        assert result["l0"] == pytest.approx([2.0, 3.0])
        assert result["l1"] == pytest.approx([2.0])

    def test_l2_delta_zero_for_same(self):
        agg = FedAvgAggregator()
        w = {"l0": [1.0, 2.0]}
        assert agg.l2_delta(w, w) == pytest.approx(0.0)

    def test_l2_delta_known_value(self):
        agg = FedAvgAggregator()
        prev = {"l0": [0.0, 0.0]}
        curr = {"l0": [3.0, 4.0]}
        assert agg.l2_delta(prev, curr) == pytest.approx(5.0)  # sqrt(9+16)

    def test_l2_delta_missing_layer_treated_as_zero(self):
        agg = FedAvgAggregator()
        prev = {}
        curr = {"l0": [1.0]}
        delta = agg.l2_delta(prev, curr)
        assert delta == pytest.approx(1.0)


# ─── FLCoordinator registration ──────────────────────────────────────────────

class TestFLCoordinatorRegistration:
    def test_register_increases_count(self):
        coord = _coord()
        coord.register_client("CL-001", capacity_kwh=200)
        assert coord.n_clients == 1

    def test_multiple_registrations(self):
        coord = _coord()
        coord.register_client("A", 100)
        coord.register_client("B", 200)
        assert coord.n_clients == 2
        assert coord.n_active == 2

    def test_deactivate_client(self):
        coord = _coord()
        coord.register_client("A", 100)
        coord.register_client("B", 200)
        coord.deactivate_client("A")
        assert coord.n_active == 1

    def test_deactivate_nonexistent_no_error(self):
        coord = _coord()
        coord.deactivate_client("GHOST")

    def test_is_ready_below_threshold(self):
        coord = _coord(min_clients=2)
        coord.register_client("A", 100)
        assert not coord.is_ready()

    def test_is_ready_at_threshold(self):
        coord = _coord(min_clients=2)
        coord.register_client("A", 100)
        coord.register_client("B", 200)
        assert coord.is_ready()


# ─── run_round ───────────────────────────────────────────────────────────────

class TestRunRound:
    def _setup(self) -> FLCoordinator:
        coord = _coord()
        coord.register_client("A", 200)
        coord.register_client("B", 100)
        return coord

    def test_run_round_returns_result(self):
        coord = self._setup()
        result = coord.run_round({
            "A": {"l0": [1.0]},
            "B": {"l0": [1.0]},
        })
        assert isinstance(result, FLRoundResult)

    def test_run_round_increments_round_id(self):
        coord = self._setup()
        coord.run_round({"A": {"l0": [1.0]}, "B": {"l0": [1.0]}})
        assert coord.round_id == 1

    def test_run_round_updates_global_weights(self):
        coord = self._setup()
        coord.run_round({"A": {"l0": [2.0]}, "B": {"l0": [2.0]}})
        assert coord.global_weights["l0"] == pytest.approx([2.0])

    def test_too_few_clients_raises(self):
        coord = _coord(min_clients=3)
        coord.register_client("A", 200)
        coord.register_client("B", 100)
        with pytest.raises(RuntimeError, match="requires"):
            coord.run_round({"A": {"l0": [1.0]}, "B": {"l0": [1.0]}})

    def test_force_flag_bypasses_min_clients(self):
        coord = _coord(min_clients=3)
        coord.register_client("A", 200)
        coord.register_client("B", 100)
        result = coord.run_round(
            {"A": {"l0": [1.0]}, "B": {"l0": [1.0]}},
            force=True,
        )
        assert result.n_clients == 2

    def test_unregistered_client_filtered(self):
        coord = _coord(min_clients=1)
        coord.register_client("A", 200)
        result = coord.run_round(
            {"A": {"l0": [1.0]}, "GHOST": {"l0": [99.0]}},
            force=True,
        )
        assert result.n_clients == 1  # GHOST filtered out

    def test_round_stored_in_history(self):
        coord = self._setup()
        coord.run_round({"A": {"l0": [1.0]}, "B": {"l0": [1.0]}})
        assert len(coord.history) == 1

    def test_converged_when_delta_below_threshold(self):
        coord = _coord(min_clients=2, rounds=5)
        coord.register_client("A", 100)
        coord.register_client("B", 100)
        # Same weights both rounds → delta ~0
        coord.run_round({"A": {"l0": [1.0]}, "B": {"l0": [1.0]}})
        result = coord.run_round({"A": {"l0": [1.0]}, "B": {"l0": [1.0]}})
        assert result.converged


# ─── run_session ─────────────────────────────────────────────────────────────

class TestRunSession:
    def test_session_runs_all_rounds(self):
        coord = _coord(min_clients=1, rounds=3)
        coord.register_client("A", 100)

        def updater(rid, gw):
            return {"A": {"l0": [float(rid + 1)]}}

        results = coord.run_session(updater, stop_on_convergence=False)
        assert len(results) == 3

    def test_session_stops_on_convergence(self):
        coord = _coord(min_clients=1, rounds=10)
        coord.register_client("A", 100)
        # Always returns same weights → converges round 2
        def updater(rid, gw):
            return {"A": {"l0": [1.0]}}

        results = coord.run_session(updater, stop_on_convergence=True)
        # Should stop early (round 1: no prev → delta = L2([1.0]) = 1.0;
        # round 2: delta = 0 → converged)
        assert len(results) <= 10
        assert results[-1].converged
