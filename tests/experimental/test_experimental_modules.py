# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/experimental/test_experimental_modules.py
================================================
Unit test suite for experimental Edge AI modules.
"""

import asyncio
import numpy as np
import pytest
from pathlib import Path

from experimental.lite_inference.lite_engine import LiteInferenceEngine, run_benchmark
from experimental.nats_bus.nats_bridge import NatsTelemetryBridge, LocalTelemetryStore
from experimental.local_copilot.copilot_engine import LocalBessCopilot


class TestLiteInference:
    def test_predict_stub_returns_valid_dict(self):
        engine = LiteInferenceEngine("non_existent.onnx")
        input_data = np.array([50.0, 30.0, 100.0, 50.0], dtype=np.float32)
        res = engine.predict(input_data)

        assert "setpoint_pu" in res
        assert "latency_ms" in res
        assert res["latency_ms"] >= 0.0

    def test_run_benchmark(self):
        metrics = run_benchmark(num_runs=10)
        assert metrics["avg_latency_ms"] >= 0.0
        assert metrics["p99_latency_ms"] >= 0.0


class TestNatsBridge:
    def test_store_offline_appends_and_flushes(self, tmp_path: Path):
        store = LocalTelemetryStore(store_dir=tmp_path)
        assert store.count_pending() == 0

        store.append({"soc": 80.0, "power_kw": 100.0})
        store.append({"soc": 81.0, "power_kw": 105.0})

        assert store.count_pending() == 2

        flushed = store.flush_pending(limit=1)
        assert len(flushed) == 1
        assert store.count_pending() == 1

    @pytest.mark.asyncio
    async def test_publish_telemetry_offline(self, tmp_path: Path):
        bridge = NatsTelemetryBridge(site_id="TEST-SITE")
        bridge.store = LocalTelemetryStore(store_dir=tmp_path)

        res = await bridge.publish_telemetry({"soc": 50.0})
        assert "STORED_OFFLINE_COUNT_1" in res


class TestLocalBessCopilot:
    def test_query_compliance(self):
        copilot = LocalBessCopilot(site_id="TEST-SITE")
        res = copilot.query("¿Cuál es el estado de cumplimiento NTSyCS?")
        assert "NTSyCS" in res
        assert "Conforme" in res or "100" in res

    def test_query_soh(self):
        copilot = LocalBessCopilot(site_id="TEST-SITE")
        res = copilot.query("dame la salud SOH de las baterias")
        assert "SOH" in res
        assert "%" in res

    def test_query_operational_state(self):
        copilot = LocalBessCopilot(site_id="TEST-SITE")
        res = copilot.query("cuál es el soc y la potencia activa?")
        assert "SOC" in res
        assert "kW" in res
