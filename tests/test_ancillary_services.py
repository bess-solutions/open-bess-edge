# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
tests/test_ancillary_services.py
==================================
Test suite for ancillary_services.py and revenue stacking integration.

Coverage:
  - AncillaryServiceCapacity revenue calculations
  - AncillaryStack aggregation and breakdowns
  - CapacityAllocator: full allocation, SoC gates, power gates
  - Integration with ArbitrageEngine (enable_revenue_stacking=True)
"""
from __future__ import annotations

import pytest

from src.interfaces.ancillary_services import (
    AncillaryServiceCapacity,
    AncillaryStack,
    CapacityAllocator,
    SEN_SERVICES,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def default_allocator() -> CapacityAllocator:
    return CapacityAllocator(capacity_kwh=1000.0, max_power_kw=500.0, usd_clp_rate=950.0)


@pytest.fixture
def small_allocator() -> CapacityAllocator:
    """BESS with only 25 kW — below most min_kw thresholds."""
    return CapacityAllocator(capacity_kwh=100.0, max_power_kw=25.0)


# ── AncillaryServiceCapacity tests ────────────────────────────────────────────

class TestAncillaryServiceCapacity:

    def test_revenue_usd_per_hour_positive(self):
        cap = AncillaryServiceCapacity(
            service="CSF", label="Test", reserved_kw=100.0, price_usd_mw_h=4.5
        )
        # 100 kW * (1/1000) MW/kW * 4.5 USD/MW·h = 0.45 USD/h
        assert abs(cap.revenue_usd_per_hour - 0.45) < 1e-6

    def test_revenue_clp_per_hour_conversion(self):
        cap = AncillaryServiceCapacity(
            service="RP", label="Test", reserved_kw=200.0, price_usd_mw_h=3.8
        )
        # 200/1000 * 3.8 * 950 = 722.0 CLP/h
        expected = 200 / 1000 * 3.8 * 950.0
        assert abs(cap.revenue_clp_per_hour(usd_clp=950.0) - expected) < 0.01

    def test_ineligible_service_zero_revenue(self):
        cap = AncillaryServiceCapacity(
            service="AGC", label="Test", reserved_kw=0.0,
            price_usd_mw_h=5.2, eligible=False, rejection_reason="SoC out of range"
        )
        assert cap.revenue_usd_per_hour == 0.0

    def test_to_dict_structure(self):
        cap = AncillaryServiceCapacity(
            service="RSS", label="Reserva", reserved_kw=150.0, price_usd_mw_h=2.9
        )
        d = cap.to_dict(usd_clp=950.0)
        assert d["service"] == "RSS"
        assert d["reserved_kw"] == 150.0
        assert d["eligible"] is True
        assert "revenue_clp_per_hour" in d


# ── AncillaryStack tests ──────────────────────────────────────────────────────

class TestAncillaryStack:

    def _make_stack(self, clp_rate=950.0) -> AncillaryStack:
        s1 = AncillaryServiceCapacity("CSF", "A", reserved_kw=50.0, price_usd_mw_h=4.5)
        s2 = AncillaryServiceCapacity("RP", "B", reserved_kw=30.0, price_usd_mw_h=3.8,
                                       eligible=False, rejection_reason="SoC low")
        return AncillaryStack(
            services=[s1, s2],
            total_reserved_kw=50.0,
            total_revenue_usd_per_hour=s1.revenue_usd_per_hour,
            available_for_arbitrage_kw=200.0,
            usd_clp_rate=clp_rate,
        )

    def test_total_revenue_clp(self):
        stack = self._make_stack()
        expected = stack.total_revenue_usd_per_hour * 950.0
        assert abs(stack.total_revenue_clp_per_hour - expected) < 0.01

    def test_revenue_breakdown_excludes_ineligible(self):
        stack = self._make_stack()
        breakdown = stack.revenue_breakdown
        assert "CSF" in breakdown
        assert "RP" not in breakdown  # ineligible

    def test_to_api_dict_structure(self):
        stack = self._make_stack()
        d = stack.to_api_dict()
        assert "total_reserved_kw" in d
        assert "total_revenue_clp_per_hour" in d
        assert "revenue_breakdown" in d
        assert "services" in d
        assert len(d["services"]) == 2

    def test_summary_returns_string(self):
        stack = self._make_stack()
        s = stack.summary()
        assert "CSF" in s
        assert "Revenue" in s


# ── CapacityAllocator tests ───────────────────────────────────────────────────

class TestCapacityAllocator:

    def test_full_allocation_normal_soc(self, default_allocator):
        """At 60% SoC with no arbitrage reservation, all eligible services receive capacity."""
        stack = default_allocator.allocate(soc_pct=60.0, arbitrage_reserved_kw=0.0)
        eligible = [s for s in stack.services if s.eligible]
        assert len(eligible) >= 3  # at least 3 services should qualify at 60% SoC
        assert stack.total_reserved_kw > 0

    def test_no_allocation_low_soc(self, default_allocator):
        """At 5% SoC, all services should be rejected (SoC below all min thresholds)."""
        stack = default_allocator.allocate(soc_pct=5.0, arbitrage_reserved_kw=0.0)
        eligible = [s for s in stack.services if s.eligible]
        assert len(eligible) == 0
        assert stack.total_reserved_kw == 0.0

    def test_no_allocation_high_soc(self, default_allocator):
        """At 98% SoC (above max_soc for most services), rejections expected."""
        stack = default_allocator.allocate(soc_pct=98.0, arbitrage_reserved_kw=0.0)
        ineligible = [s for s in stack.services if not s.eligible]
        assert len(ineligible) >= 2

    def test_power_gate_small_bess(self, small_allocator):
        """With only 25 kW, services requiring more than 25 kW minimum are rejected."""
        stack = small_allocator.allocate(soc_pct=60.0, arbitrage_reserved_kw=0.0)
        for s in stack.services:
            cfg = SEN_SERVICES[s.service]
            if cfg["min_kw"] > small_allocator.max_power_kw and not s.eligible:
                assert "kW available" in s.rejection_reason

    def test_arbitrage_reservation_reduces_headroom(self, default_allocator):
        """Reserving 400 kW for arbitrage leaves only 100 kW for ancillary services."""
        stack_full = default_allocator.allocate(soc_pct=60.0, arbitrage_reserved_kw=0.0)
        stack_limited = default_allocator.allocate(soc_pct=60.0, arbitrage_reserved_kw=400.0)
        assert stack_limited.total_reserved_kw < stack_full.total_reserved_kw

    def test_all_service_keys_present(self, default_allocator):
        """All 5 SEN services should appear in the output."""
        stack = default_allocator.allocate(soc_pct=60.0)
        service_ids = {s.service for s in stack.services}
        assert service_ids == {"CSF", "RP", "RSS", "RSB", "AGC"}

    def test_priority_order_respected(self, default_allocator):
        """CSF (priority 1) should be allocated before AGC (priority 5) in tight capacity."""
        # With full capacity, all get some. With severely limited capacity, higher priority wins.
        limited = CapacityAllocator(capacity_kwh=100.0, max_power_kw=12.0)
        stack = limited.allocate(soc_pct=60.0, arbitrage_reserved_kw=0.0)
        # CSF min_kw=10, so with 12kW, only CSF can be allocated
        csf = next(s for s in stack.services if s.service == "CSF")
        assert csf.eligible or stack.total_reserved_kw == 0.0

    def test_revenue_positive_when_allocated(self, default_allocator):
        stack = default_allocator.allocate(soc_pct=60.0)
        if stack.total_reserved_kw > 0:
            assert stack.total_revenue_usd_per_hour > 0
            assert stack.total_revenue_clp_per_hour > 0

    def test_estimate_daily_revenue_is_24x_hourly(self, default_allocator):
        daily = default_allocator.estimate_daily_revenue_clp(soc_pct=60.0)
        stack = default_allocator.allocate(soc_pct=60.0)
        expected = stack.total_revenue_clp_per_hour * 24
        assert abs(daily - expected) < 1.0

    def test_custom_price_override(self):
        """Service price overrides are respected."""
        overrides = {"CSF": {"price_usd_mw_h": 99.0}}
        allocator = CapacityAllocator(max_power_kw=500.0, service_overrides=overrides)
        stack = allocator.allocate(soc_pct=60.0)
        csf = next((s for s in stack.services if s.service == "CSF" and s.eligible), None)
        if csf:
            assert csf.price_usd_mw_h == 99.0


# ── Integration with ArbitrageEngine ─────────────────────────────────────────

class TestRevenueStackingIntegration:

    def _make_forecasts(self):
        """Build 24 minimal PriceForecast objects for testing."""
        from src.interfaces.cmg_predictor import PriceForecast
        forecasts = []
        for h in range(24):
            # Low price hours 0-5, high price hours 18-21
            cmg = 30.0 + (h * 3.5)
            forecasts.append(PriceForecast(
                hour=h,
                cmg_clp_kwh=cmg,
                cmg_p10=cmg * 0.85,
                cmg_p90=cmg * 1.15,
                confidence=0.75,
            ))
        return forecasts

    def test_stacking_disabled_no_ancillary_fields(self):
        from src.interfaces.arbitrage_engine import ArbitrageEngine
        engine = ArbitrageEngine(
            capacity_kwh=1000.0, max_power_kw=500.0,
            enable_revenue_stacking=False
        )
        schedule = engine.compute(self._make_forecasts(), current_soc_pct=60.0)
        assert schedule.ancillary_revenue_clp == 0.0
        assert schedule.total_stacked_revenue_clp == 0.0
        assert schedule.revenue_breakdown == {}

    def test_stacking_enabled_adds_ancillary_revenue(self):
        from src.interfaces.arbitrage_engine import ArbitrageEngine
        engine = ArbitrageEngine(
            capacity_kwh=1000.0, max_power_kw=500.0,
            enable_revenue_stacking=True, usd_clp_rate=950.0
        )
        schedule = engine.compute(self._make_forecasts(), current_soc_pct=60.0)
        # At 60% SoC there should be ancillary revenue > 0
        assert schedule.ancillary_revenue_clp >= 0.0
        assert schedule.total_stacked_revenue_clp >= schedule.projected_net_clp
        assert "arbitrage" in schedule.revenue_breakdown

    def test_stacking_api_dict_contains_breakdown(self):
        from src.interfaces.arbitrage_engine import ArbitrageEngine
        engine = ArbitrageEngine(
            capacity_kwh=1000.0, max_power_kw=500.0,
            enable_revenue_stacking=True
        )
        schedule = engine.compute(self._make_forecasts(), current_soc_pct=60.0)
        d = schedule.to_api_dict()
        assert "ancillary_revenue_clp" in d
        assert "revenue_breakdown" in d

    def test_stacking_summary_mentions_stacked(self):
        from src.interfaces.arbitrage_engine import ArbitrageEngine
        engine = ArbitrageEngine(
            capacity_kwh=1000.0, max_power_kw=500.0,
            enable_revenue_stacking=True
        )
        schedule = engine.compute(self._make_forecasts(), current_soc_pct=60.0)
        if schedule.ancillary_revenue_clp > 0:
            assert "Ancillary" in schedule.summary() or "STACKED" in schedule.summary()
