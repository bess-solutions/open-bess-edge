"""
tests/test_dashboard_api.py
============================
Unit tests for DashboardState and DashboardAPI.
Tests run without an actual aiohttp server (pure state serialization tests).
"""

from __future__ import annotations

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

    def test_schedule_fields_initialized(self):
        s = DashboardState(site_id="sched-test")
        assert s.schedule_net_clp == 0.0
        assert s.schedule_charge_hours == 0
        assert s.schedule_discharge_hours == 0
        assert s._schedule_dict is None

    def test_schedule_fields_updatable(self):
        s = DashboardState()
        s.schedule_net_clp = 45_000.0
        s.schedule_charge_hours = 5
        s.schedule_discharge_hours = 3
        assert s.schedule_net_clp == 45_000.0
        assert s.schedule_charge_hours == 5


class TestArbitrageIntegrationWithState:
    """Tests verifying CMgPredictor + ArbitrageEngine produce valid outputs."""

    def test_schedule_dict_structure(self):
        from src.interfaces.arbitrage_engine import ArbitrageEngine
        from src.interfaces.cmg_predictor import _HOURLY_MEAN_CMG, CMgPredictor

        predictor = CMgPredictor(node="Maitencillo", model_path="nonexistent.onnx")
        predictor.load()
        for h in range(24):
            predictor.update(h, _HOURLY_MEAN_CMG[h])
        forecasts = predictor.predict_next_24h(current_hour=10)

        engine = ArbitrageEngine(capacity_kwh=1000.0, node="Maitencillo")
        schedule = engine.compute(forecasts, current_soc_pct=50.0)
        d = schedule.to_api_dict()

        assert "node" in d
        assert "projected_net_clp" in d
        assert "hourly_schedule" in d
        assert len(d["hourly_schedule"]) == 24
        for slot in d["hourly_schedule"]:
            assert slot["action"] in ("charge", "discharge", "hold")

    def test_scheduler_roe_estimate(self):
        from src.interfaces.arbitrage_engine import ArbitrageEngine
        from src.interfaces.cmg_predictor import _HOURLY_MEAN_CMG, CMgPredictor

        predictor = CMgPredictor(node="Polpaico")
        for _day in range(7):
            for h in range(24):
                predictor.update(h, _HOURLY_MEAN_CMG[h])
        forecasts = predictor.predict_next_24h(current_hour=8)
        engine = ArbitrageEngine(capacity_kwh=1000.0, max_power_kw=500.0, node="Polpaico")
        schedule = engine.compute(forecasts, current_soc_pct=50.0)
        roe = engine.daily_roe_estimate(schedule)
        assert isinstance(roe, float)
        assert roe >= -0.5

