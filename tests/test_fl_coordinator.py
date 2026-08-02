# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_fl_coordinator.py
=============================
Unit test suite for ``src.core.fl_coordinator``.

Covers:
- BESSFlowerClient parameter initialization and Ed25519 cryptographic signing
- get_parameters, fit, and evaluate lifecycle
- FLCoordinator initialization and local simulation start
"""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip(
    "flwr", reason="flwr no instalado (dependencia opcional, ver requirements-federated.txt)"
)

from src.core.fl_coordinator import BESSFlowerClient, FLCoordinator


@pytest.fixture()
def key_path(tmp_path: Path) -> str:
    return str(tmp_path / "ed25519_node.pem")


class TestBESSFlowerClient:
    def test_init_creates_key_file(self, key_path: str):
        client = BESSFlowerClient(node_id="TEST-NODE-001", private_key_path=key_path)
        assert Path(key_path).exists()
        assert len(client.parameters) == 3

    def test_get_parameters(self, key_path: str):
        client = BESSFlowerClient(node_id="TEST-NODE-001", private_key_path=key_path)
        params = client.get_parameters({})
        assert len(params) == 3
        assert isinstance(params[0], np.ndarray)

    def test_fit_and_evaluate(self, key_path: str):
        client = BESSFlowerClient(node_id="TEST-NODE-001", private_key_path=key_path)
        initial_params = client.get_parameters({})

        updated_params, n_fit, fit_metrics = client.fit(initial_params, {})
        assert n_fit == 1000
        assert fit_metrics["status"] == "success"
        assert "signature_hex" in fit_metrics
        assert "pub_key_pem" in fit_metrics

        loss, n_eval, eval_metrics = client.evaluate(updated_params, {})
        assert n_eval == 250
        assert loss >= 0.0
        assert eval_metrics["accuracy"] == 0.94
        assert "loss_signature_hex" in eval_metrics


class TestFLCoordinator:
    def test_start_local_simulation(self, tmp_path: Path):
        coordinator = FLCoordinator(
            server_address="localhost:8080",
            node_id="TEST-NODE-001",
            certs_dir=str(tmp_path),
        )
        success = coordinator.start(insecure=True)
        assert success is True
