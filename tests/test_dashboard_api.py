"""
tests/test_dashboard_api.py
============================
Unit tests for DashboardState and DashboardAPI.
Tests run without an actual aiohttp server (pure state serialization tests).
"""

from __future__ import annotations

import time

import pytest

from src.interfaces.dashboard_api import DashboardState


class TestDashboardState:

    def _state(self) -> DashboardState:
        s = DashboardState(site_id="test-001")
        s.soc_pct = 72.5
        s.power_kw = -25.0
        s.temp_c = 30.0
        s.is_safe = True
        s.ids_score = 0.12
        s.ids_trained = True
        s.onnx_available = True
        s.onnx_dispatch_kw = 30.0
        s.onnx_inference_ms = 4.5
        s.co2_avoided_kg = 1200.5
        s.fleet_n_sites = 5
        s.fleet_avg_soc_pct = 65.0
        s.p2p_credits_minted = 42
        s.p2p_credits_kwh = 210.0
        return s

    def test_to_status_dict_has_required_keys(self):
        d = self._state().to_status_dict()
        for key in ("site_id", "version", "uptime_s", "is_safe", "telemetry", "ids", "onnx"):
            assert key in d, f"Missing key: {key}"

    def test_to_status_soc_rounded(self):
        d = self._state().to_status_dict()
        assert d["telemetry"]["soc_pct"] == pytest.approx(72.5, abs=0.01)

    def test_to_status_ids_status_nominal(self):
        s = self._state()
        s.ids_score = 0.3
        d = s.to_status_dict()
        assert d["ids"]["status"] == "nominal"

    def test_to_status_ids_status_alarm(self):
        s = self._state()
        s.ids_score = 0.85
        d = s.to_status_dict()
        assert d["ids"]["status"] == "alarm"

    def test_to_fleet_dict_has_n_sites(self):
        d = self._state().to_fleet_dict()
        assert d["n_sites"] == 5

    def test_to_carbon_dict_has_co2(self):
        d = self._state().to_carbon_dict()
        assert d["co2_avoided_kg"] == pytest.approx(1200.5, abs=0.01)
        assert "methodology" in d

    def test_to_p2p_dict_has_credits(self):
        d = self._state().to_p2p_dict()
        assert d["credits_minted"] == 42
        assert d["credits_kwh"] == pytest.approx(210.0)

    def test_uptime_is_positive(self):
        import time as _time
        s = DashboardState()
        s.started_at = _time.time() - 1.0  # force 1 second of uptime
        d = s.to_status_dict()
        assert d["uptime_s"] >= 0.9

    def test_version_string_present(self):
        d = self._state().to_status_dict()
        assert d["version"] != ""
        # Semver-ish format
        parts = d["version"].split(".")
        assert len(parts) == 3

    def test_onnx_dispatch_kw_in_status(self):
        d = self._state().to_status_dict()
        assert d["onnx"]["dispatch_kw"] == pytest.approx(30.0)
