"""
tests/test_cmg_predictor.py
============================
Unit tests for CMgPredictor — BESSAI price forecasting module.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from src.interfaces.cmg_predictor import (
    _HOURLY_MEAN_CMG,
    _PEAK_HOURS,
    _SOLAR_TROUGH_HOURS,
    CMgPredictor,
    PriceForecast,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def predictor() -> CMgPredictor:
    p = CMgPredictor(node="TestNode", model_path="nonexistent.onnx")
    p.load()  # Falls back gracefully — no ONNX model
    return p


@pytest.fixture
def seeded_predictor(predictor: CMgPredictor) -> CMgPredictor:
    """Predictor with 48h of synthetic history."""
    for _day in range(2):
        for hour in range(24):
            price = _HOURLY_MEAN_CMG[hour] + (5.0 if hour in _PEAK_HOURS else -3.0)
            predictor.update(hour, price)
    return predictor


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    csv_file = tmp_path / "cmg_test.csv"
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["fecha", "hora", "cmg_clp_kwh"])
        writer.writeheader()
        for h in range(24):
            writer.writerow({"fecha": "2025-01-01", "hora": h, "cmg_clp_kwh": 40.0 + h})
    return csv_file


# ── Unit Tests: PriceForecast ─────────────────────────────────────────────────


class TestPriceForecast:
    def test_peak_hours_flagged(self):
        for h in _PEAK_HOURS:
            f = PriceForecast(hour=h, cmg_clp_kwh=80.0)
            assert f.is_peak is True

    def test_solar_trough_flagged(self):
        for h in _SOLAR_TROUGH_HOURS:
            f = PriceForecast(hour=h, cmg_clp_kwh=20.0)
            assert f.is_solar_trough is True

    def test_dispatch_priority_discharge_peak(self):
        f = PriceForecast(hour=19, cmg_clp_kwh=75.0)
        assert f.dispatch_priority == "discharge"

    def test_dispatch_priority_charge_trough(self):
        f = PriceForecast(hour=13, cmg_clp_kwh=22.0)
        assert f.dispatch_priority == "charge"

    def test_dispatch_priority_hold(self):
        f = PriceForecast(hour=8, cmg_clp_kwh=45.0)
        assert f.dispatch_priority == "hold"


# ── Unit Tests: CMgPredictor ──────────────────────────────────────────────────


class TestCMgPredictor:
    def test_init_defaults(self, predictor: CMgPredictor):
        assert predictor.node == "TestNode"
        assert not predictor.is_onnx_loaded
        assert predictor.history_size == 0

    def test_update_increases_history(self, predictor: CMgPredictor):
        predictor.update(12, 35.0)
        assert predictor.history_size == 1

    def test_history_capped_at_window(self):
        p = CMgPredictor(history_window=5)
        for i in range(10):
            p.update(i % 24, 40.0)
        assert p.history_size == 5

    def test_predict_returns_24_slots(self, predictor: CMgPredictor):
        forecasts = predictor.predict_next_24h(current_hour=10)
        assert len(forecasts) == 24

    def test_predict_all_hours_covered(self, predictor: CMgPredictor):
        forecasts = predictor.predict_next_24h(current_hour=10)
        hours = {f.hour for f in forecasts}
        assert hours == set(range(24))

    def test_predict_prices_positive(self, seeded_predictor: CMgPredictor):
        forecasts = seeded_predictor.predict_next_24h(current_hour=8, current_cmg=50.0)
        for f in forecasts:
            assert f.cmg_clp_kwh >= 0

    def test_predict_confidence_in_range(self, seeded_predictor: CMgPredictor):
        forecasts = seeded_predictor.predict_next_24h(current_hour=8, current_cmg=50.0)
        for f in forecasts:
            assert 0.0 <= f.confidence <= 1.0

    def test_predict_confidence_decays_with_horizon(self, seeded_predictor: CMgPredictor):
        forecasts = seeded_predictor.predict_next_24h(current_hour=0, current_cmg=40.0)
        # Confidence should generally be higher in early hours vs later
        # (not strictly monotone, but mean of first 8 > mean of last 8)
        conf_early = sum(f.confidence for f in forecasts[:8]) / 8
        conf_late = sum(f.confidence for f in forecasts[16:]) / 8
        assert conf_early >= conf_late

    def test_predict_method_smoothing(self, predictor: CMgPredictor):
        forecasts = predictor.predict_next_24h(current_hour=12)
        for f in forecasts:
            assert f.method == "exponential_smoothing"

    def test_update_feeds_current_cmg(self, predictor: CMgPredictor):
        predictor.predict_next_24h(current_hour=10, current_cmg=55.5)
        assert predictor.history_size == 1

    def test_load_history_from_csv(self, predictor: CMgPredictor, sample_csv: Path):
        n = predictor.load_history_from_csv(sample_csv)
        assert n == 24
        assert predictor.history_size == 24

    def test_load_history_missing_file(self, predictor: CMgPredictor, tmp_path: Path):
        n = predictor.load_history_from_csv(tmp_path / "nonexistent.csv")
        assert n == 0

    def test_best_charge_window(self, seeded_predictor: CMgPredictor):
        forecasts = seeded_predictor.predict_next_24h(current_hour=0)
        charge_hours = seeded_predictor.best_charge_window(forecasts)
        assert isinstance(charge_hours, list)
        assert len(charge_hours) <= 4

    def test_best_discharge_window(self, seeded_predictor: CMgPredictor):
        forecasts = seeded_predictor.predict_next_24h(current_hour=0)
        discharge_hours = seeded_predictor.best_discharge_window(forecasts)
        assert isinstance(discharge_hours, list)
        assert len(discharge_hours) <= 4

    def test_projected_arbitrage_revenue(self, seeded_predictor: CMgPredictor):
        forecasts = seeded_predictor.predict_next_24h(current_hour=0)
        revenue = seeded_predictor.projected_arbitrage_revenue(forecasts, capacity_kwh=1000.0)
        assert revenue >= 0

    def test_projected_revenue_scales_with_capacity(self, seeded_predictor: CMgPredictor):
        forecasts = seeded_predictor.predict_next_24h(current_hour=0)
        rev_1mwh = seeded_predictor.projected_arbitrage_revenue(forecasts, capacity_kwh=1000.0)
        rev_2mwh = seeded_predictor.projected_arbitrage_revenue(forecasts, capacity_kwh=2000.0)
        # 2 MWh should yield roughly double (not exactly due to rounding)
        assert rev_2mwh > rev_1mwh

    def test_exponential_smoothing_adapts(self):
        """Verify that high observed prices shift predictions upward."""
        p1 = CMgPredictor(alpha=0.9)  # High alpha = very reactive
        p2 = CMgPredictor(alpha=0.9)
        # Feed extreme high prices to p1 at hour 20
        for _ in range(10):
            p1.update(20, 200.0)
        for _ in range(10):
            p2.update(20, 20.0)
        f1 = p1.predict_next_24h(current_hour=19)
        f2 = p2.predict_next_24h(current_hour=19)
        # Next hour (20) prediction from p1 should be higher than p2
        h20_p1 = next(f.cmg_clp_kwh for f in f1 if f.hour == 20)
        h20_p2 = next(f.cmg_clp_kwh for f in f2 if f.hour == 20)
        assert h20_p1 > h20_p2
