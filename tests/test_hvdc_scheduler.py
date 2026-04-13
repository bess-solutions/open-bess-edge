"""
tests/test_hvdc_scheduler.py
==============================
Unit tests for HVDCScheduler (BEP-0700) — HVDC inter-regional dispatch.

Coverage:
- IDLE when spread below threshold
- A→B and B→A direction selection
- Link capacity constraint (constrained=True)
- Loss calculation
- Arbitrage revenue computation
- Setpoint signs (export=neg, receive=pos)
- Accessors: dispatch_count, history, total_arbitrage, average_spread
- HVDCResult properties: is_active, net_benefit_usd
- HVDCFlowDirection enum values
"""
from __future__ import annotations

import pytest
from src.core.hvdc_scheduler import HVDCFlowDirection, HVDCScheduler

# ─── Helpers ────────────────────────────────────────────────────────────────

def _sched(link_mw: float = 500.0, min_spread: float = 5.0) -> HVDCScheduler:
    return HVDCScheduler(link_capacity_mw=link_mw, min_spread_usd_mwh=min_spread)


# ─── IDLE tests ───────────────────────────────────────────────────────────────

class TestIdle:
    def test_idle_when_spread_zero(self):
        s = _sched()
        r = s.schedule(price_a=60.0, price_b=60.0, available_a_kw=1000, available_b_kw=1000)
        assert r.direction == HVDCFlowDirection.IDLE

    def test_idle_when_spread_below_threshold(self):
        s = _sched(min_spread=10.0)
        r = s.schedule(price_a=60.0, price_b=65.0, available_a_kw=1000, available_b_kw=1000)
        assert r.direction == HVDCFlowDirection.IDLE

    def test_idle_flow_is_zero(self):
        s = _sched()
        r = s.schedule(60.0, 62.0, 1000, 1000)
        assert r.flow_kw == pytest.approx(0.0)

    def test_idle_arbitrage_is_zero(self):
        s = _sched()
        r = s.schedule(60.0, 62.0, 1000, 1000)
        assert r.arbitrage_usd == pytest.approx(0.0)

    def test_idle_is_not_active(self):
        s = _sched()
        r = s.schedule(60.0, 62.0, 1000, 1000)
        assert not r.is_active


# ─── Direction ────────────────────────────────────────────────────────────────

class TestDirection:
    def test_a_to_b_when_a_cheaper(self):
        s = _sched()
        r = s.schedule(price_a=40.0, price_b=90.0, available_a_kw=5000, available_b_kw=5000)
        assert r.direction == HVDCFlowDirection.A_TO_B

    def test_b_to_a_when_b_cheaper(self):
        s = _sched()
        r = s.schedule(price_a=90.0, price_b=40.0, available_a_kw=5000, available_b_kw=5000)
        assert r.direction == HVDCFlowDirection.B_TO_A

    def test_a_to_b_positive_flow(self):
        s = _sched()
        r = s.schedule(40.0, 90.0, 5000, 5000)
        assert r.flow_kw > 0

    def test_b_to_a_negative_flow(self):
        s = _sched()
        r = s.schedule(90.0, 40.0, 5000, 5000)
        assert r.flow_kw < 0


# ─── Setpoints ───────────────────────────────────────────────────────────────

class TestSetpoints:
    def test_a_exports_negative_setpoint(self):
        s = _sched()
        r = s.schedule(40.0, 90.0, 5000, 5000)
        # Region A exports → negative setpoint (discharge to grid)
        assert r.region_a_setpoint_kw < 0

    def test_b_receives_positive_setpoint(self):
        s = _sched()
        r = s.schedule(40.0, 90.0, 5000, 5000)
        # Region B receives → positive setpoint
        assert r.region_b_setpoint_kw > 0

    def test_b_exports_negative_setpoint(self):
        s = _sched()
        r = s.schedule(90.0, 40.0, 5000, 5000)
        assert r.region_b_setpoint_kw < 0

    def test_a_receives_positive_setpoint(self):
        s = _sched()
        r = s.schedule(90.0, 40.0, 5000, 5000)
        assert r.region_a_setpoint_kw > 0


# ─── Capacity constraint ─────────────────────────────────────────────────────

class TestCapacity:
    def test_constrained_when_available_exceeds_link(self):
        s = _sched(link_mw=1.0)  # 1 MW = 1000 kW
        r = s.schedule(40.0, 90.0, available_a_kw=5000, available_b_kw=5000)
        assert r.constrained

    def test_not_constrained_when_available_below_link(self):
        s = _sched(link_mw=500.0)
        r = s.schedule(40.0, 90.0, available_a_kw=100, available_b_kw=5000)
        assert not r.constrained

    def test_flow_capped_at_capacity(self):
        s = _sched(link_mw=1.0, min_spread=1.0)
        r = s.schedule(40.0, 90.0, available_a_kw=9999, available_b_kw=9999)
        max_kw = 1000.0 * 0.95
        assert abs(r.flow_kw) <= max_kw + 1.0


# ─── Losses ──────────────────────────────────────────────────────────────────

class TestLosses:
    def test_losses_positive(self):
        s = _sched()
        r = s.schedule(40.0, 90.0, 5000, 5000)
        assert r.losses_kw > 0

    def test_received_less_than_sent(self):
        s = _sched()
        r = s.schedule(40.0, 90.0, 5000, 5000)
        # B receives less than A sends
        assert r.region_b_setpoint_kw < abs(r.region_a_setpoint_kw)

    def test_losses_scale_with_losses_pct(self):
        s1 = HVDCScheduler(losses_pct=0.01, min_spread_usd_mwh=1.0)
        s2 = HVDCScheduler(losses_pct=0.05, min_spread_usd_mwh=1.0)
        r1 = s1.schedule(40.0, 90.0, 5000, 5000)
        r2 = s2.schedule(40.0, 90.0, 5000, 5000)
        assert r2.losses_kw > r1.losses_kw


# ─── Arbitrage revenue ────────────────────────────────────────────────────────

class TestArbitrage:
    def test_higher_spread_higher_revenue(self):
        s = _sched()
        r1 = s.schedule(40.0, 60.0, 5000, 5000)  # spread=20
        r2 = s.schedule(40.0, 90.0, 5000, 5000)  # spread=50
        assert r2.arbitrage_usd > r1.arbitrage_usd

    def test_arbitrage_positive_on_active(self):
        s = _sched()
        r = s.schedule(40.0, 90.0, 5000, 5000)
        assert r.arbitrage_usd > 0


# ─── Accessors ───────────────────────────────────────────────────────────────

class TestAccessors:
    def test_dispatch_count_increments(self):
        s = _sched()
        s.schedule(40.0, 90.0, 5000, 5000)
        s.schedule(40.0, 90.0, 5000, 5000)
        assert s.dispatch_count == 2

    def test_idle_does_not_increment_dispatch(self):
        # IDLE results are NOT counted in _history via _idle_result (no append)
        s = _sched(min_spread=100.0)
        s.schedule(40.0, 90.0, 5000, 5000)
        assert s.dispatch_count == 0

    def test_history_grows(self):
        s = _sched()
        s.schedule(40.0, 90.0, 500, 500)
        s.schedule(90.0, 40.0, 500, 500)
        assert len(s.history) == 2

    def test_total_arbitrage_sums(self):
        s = _sched()
        r1 = s.schedule(40.0, 90.0, 500, 500)
        r2 = s.schedule(40.0, 90.0, 500, 500)
        assert s.total_arbitrage_usd() == pytest.approx(r1.arbitrage_usd + r2.arbitrage_usd)

    def test_average_spread(self):
        s = _sched()
        s.schedule(40.0, 90.0, 500, 500)  # spread=50
        s.schedule(40.0, 70.0, 500, 500)  # spread=30
        avg = s.average_spread_usd_mwh()
        assert avg == pytest.approx(40.0)
