"""
tests/test_arbitrage_engine.py
================================
Unit tests for ArbitrageEngine — BESSAI dispatch schedule optimizer.
"""

from __future__ import annotations

import pytest
from src.interfaces.arbitrage_engine import (
    ArbitrageEngine,
    ArbitrageSchedule,
    DispatchSlot,
)
from src.interfaces.cmg_predictor import _HOURLY_MEAN_CMG, CMgPredictor, PriceForecast

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def flat_forecasts() -> list[PriceForecast]:
    """24 forecasts with identical prices — no arbitrage opportunity."""
    return [PriceForecast(hour=h, cmg_clp_kwh=50.0) for h in range(24)]


@pytest.fixture
def spread_forecasts() -> list[PriceForecast]:
    """24 forecasts with strong day/night spread (realistic Chilean SEN pattern)."""
    return [
        PriceForecast(
            hour=h,
            cmg_clp_kwh=_HOURLY_MEAN_CMG[h],
            confidence=0.85,
            method="exponential_smoothing",
        )
        for h in range(24)
    ]


@pytest.fixture
def engine() -> ArbitrageEngine:
    return ArbitrageEngine(
        capacity_kwh=1000.0,
        max_power_kw=500.0,
        min_soc_pct=10.0,
        max_soc_pct=95.0,
        efficiency=0.92,
        max_charge_hours=6,
        max_discharge_hours=4,
        node="Maitencillo",
    )


@pytest.fixture
def small_engine() -> ArbitrageEngine:
    """500 kWh system for scaled tests."""
    return ArbitrageEngine(
        capacity_kwh=500.0,
        max_power_kw=250.0,
        node="TestNode",
    )


# ── Unit Tests: DispatchSlot ──────────────────────────────────────────────────


class TestDispatchSlot:
    def test_to_dict_keys(self, spread_forecasts: list[PriceForecast]):
        slot = DispatchSlot(
            hour=12,
            action="charge",
            power_kw=300.0,
            forecast=spread_forecasts[12],
            soc_before_pct=30.0,
            soc_after_pct=60.0,
            revenue_clp=-9000.0,
        )
        d = slot.to_dict()
        assert "hour" in d
        assert "action" in d
        assert "power_kw" in d
        assert "cmg_clp_kwh" in d
        assert "soc_before_pct" in d
        assert "soc_after_pct" in d

    def test_net_kwh_equals_power(self, spread_forecasts: list[PriceForecast]):
        slot = DispatchSlot(hour=0, action="charge", power_kw=200.0, forecast=spread_forecasts[0])
        assert slot.net_kwh == 200.0


# ── Unit Tests: ArbitrageSchedule ────────────────────────────────────────────


class TestArbitrageSchedule:
    def test_summary_returns_string(self):
        sched = ArbitrageSchedule(
            node="Test",
            projected_revenue_clp=100_000,
            projected_cost_clp=30_000,
            projected_net_clp=70_000,
        )
        s = sched.summary()
        assert "Test" in s
        assert "100" in s

    def test_to_api_dict_structure(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        d = sched.to_api_dict()
        assert "node" in d
        assert "projected_net_clp" in d
        assert "hourly_schedule" in d
        assert len(d["hourly_schedule"]) == 24


# ── Unit Tests: ArbitrageEngine ───────────────────────────────────────────────


class TestArbitrageEngine:
    def test_compute_returns_schedule(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        assert isinstance(sched, ArbitrageSchedule)

    def test_compute_24_slots(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        assert len(sched.slots) == 24

    def test_all_hours_present(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts)
        hours = {s.hour for s in sched.slots}
        assert hours == set(range(24))

    def test_soc_never_below_min(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        for slot in sched.slots:
            assert slot.soc_after_pct >= engine.min_soc_pct - 0.1  # float tolerance

    def test_soc_never_above_max(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        for slot in sched.slots:
            assert slot.soc_after_pct <= engine.max_soc_pct + 0.1

    def test_no_discharge_below_min_soc(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        # Start at minimum SOC — no discharge should happen
        sched = engine.compute(spread_forecasts, current_soc_pct=engine.min_soc_pct)
        discharge_slots = [s for s in sched.slots if s.action == "discharge"]
        # If discharge happens it must be because SOC had increased from charging first
        for slot in discharge_slots:
            assert slot.soc_before_pct > engine.min_soc_pct

    def test_charge_discharge_max_hours_respected(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        assert sched.n_charge_hours <= engine.max_charge_hours
        assert sched.n_discharge_hours <= engine.max_discharge_hours

    def test_flat_prices_no_arbitrage(
        self, engine: ArbitrageEngine, flat_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(flat_forecasts, current_soc_pct=50.0)
        # With uniform prices, spread is zero → no charge/discharge threshold met
        assert sched.n_discharge_hours == 0 or sched.projected_net_clp <= 0

    def test_spread_prices_positive_net(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        # SEN has strong enough spread to generate net positive revenue
        assert sched.projected_net_clp >= 0

    def test_compute_empty_forecast_returns_empty(self, engine: ArbitrageEngine):
        sched = engine.compute([])
        assert sched.slots == []

    def test_revenue_larger_capacity_yields_more(self, spread_forecasts: list[PriceForecast]):
        engine_1mwh = ArbitrageEngine(capacity_kwh=1000.0, max_power_kw=500.0)
        engine_2mwh = ArbitrageEngine(capacity_kwh=2000.0, max_power_kw=1000.0)
        sched_1 = engine_1mwh.compute(spread_forecasts, current_soc_pct=50.0)
        sched_2 = engine_2mwh.compute(spread_forecasts, current_soc_pct=50.0)
        assert sched_2.projected_net_clp >= sched_1.projected_net_clp

    def test_high_initial_soc_enables_immediate_discharge(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        # Start full → should be able to discharge from hour 1
        sched_full = engine.compute(spread_forecasts, current_soc_pct=90.0)
        sched_empty = engine.compute(spread_forecasts, current_soc_pct=15.0)
        # Full battery should have more discharge revenue than starting empty
        assert sched_full.projected_revenue_clp >= sched_empty.projected_revenue_clp

    def test_daily_roe_estimate_reasonable(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        roe = engine.daily_roe_estimate(sched)
        # ROE should be between 0% and 100% per year for a sensible schedule
        assert -0.5 <= roe <= 1.0

    def test_dispatch_slot_actions_valid(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=50.0)
        valid_actions = {"charge", "discharge", "hold"}
        for slot in sched.slots:
            assert slot.action in valid_actions

    def test_charge_slots_positive_power(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=30.0)
        for slot in sched.slots:
            if slot.action == "charge":
                assert slot.power_kw > 0

    def test_discharge_slots_negative_power(
        self, engine: ArbitrageEngine, spread_forecasts: list[PriceForecast]
    ):
        sched = engine.compute(spread_forecasts, current_soc_pct=80.0)
        for slot in sched.slots:
            if slot.action == "discharge":
                assert slot.power_kw < 0


# ── Integration test: Predictor → Engine pipeline ────────────────────────────


class TestArbitrageIntegration:
    def test_full_pipeline(self):
        """End-to-end: CMgPredictor → ArbitrageEngine → valid schedule."""
        predictor = CMgPredictor(node="Maitencillo", model_path="nonexistent.onnx")
        predictor.load()

        # Seed with realistic Chilean prices
        for _day in range(3):
            for h in range(24):
                predictor.update(h, _HOURLY_MEAN_CMG[h])

        forecasts = predictor.predict_next_24h(current_hour=8, current_cmg=45.0)
        assert len(forecasts) == 24

        engine = ArbitrageEngine(
            capacity_kwh=1000.0,
            max_power_kw=500.0,
            node="Maitencillo",
        )
        schedule = engine.compute(forecasts, current_soc_pct=50.0)

        assert len(schedule.slots) == 24
        assert schedule.n_charge_hours + schedule.n_discharge_hours <= 10
        assert all(s.soc_after_pct >= engine.min_soc_pct for s in schedule.slots)

        # API serialization works
        d = schedule.to_api_dict()
        assert d["node"] == "Maitencillo"
        assert len(d["hourly_schedule"]) == 24
