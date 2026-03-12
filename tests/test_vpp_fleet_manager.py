"""
tests/test_vpp_fleet_manager.py
=================================
Unit tests for VPPFleetManager (BEP-0400).

Covers:
- Site add/remove delegation to FleetOrchestrator
- Strategy selection: price arbitrage, hold, forced hold on alarm
- Setpoint computation: discharge / charge / hold / alarm-hold
- SOC boundary guards (floor / ceiling)
- VPP event publishing via publish_event()
- Full run_cycle() integration (price scenarios)
- Insufficient fleet sites guard
- CycleResult properties
- Cycle counter increment
- Strategy override
"""

from __future__ import annotations

import pytest
from src.core.fleet_orchestrator import SiteProxy, SiteTelemetry
from src.core.vpp_fleet_manager import (
    CycleResult,
    DispatchStrategy,
    SiteSetpoint,
    VPPFleetManager,
)

# ─── Helpers ────────────────────────────────────────────────────────────────


def _make_proxy(
    site_id: str,
    soc: float = 70.0,
    cap: float = 100.0,
    avail: float = 50.0,
    anomaly: float = 0.0,
) -> SiteProxy:
    def fn(sid: str) -> SiteTelemetry:
        return SiteTelemetry(
            site_id=sid,
            soc_pct=soc,
            power_kw=0.0,
            temp_c=25.0,
            capacity_kwh=cap,
            available_kw=avail,
            anomaly_score=anomaly,
        )

    return SiteProxy(host="127.0.0.1", site_id=site_id, capacity_kwh=cap, telemetry_fn=fn)


def _make_mgr(**kw) -> VPPFleetManager:
    return VPPFleetManager(**kw)


# ─── Site management ────────────────────────────────────────────────────────


class TestSiteManagement:
    def test_add_site_increments_count(self):
        mgr = _make_mgr()
        mgr.add_site("A", _make_proxy("A"))
        assert mgr.n_sites == 1

    def test_add_multiple_sites(self):
        mgr = _make_mgr()
        mgr.add_site("A", _make_proxy("A"))
        mgr.add_site("B", _make_proxy("B"))
        assert mgr.n_sites == 2

    def test_remove_site_decrements_count(self):
        mgr = _make_mgr()
        mgr.add_site("A", _make_proxy("A"))
        mgr.remove_site("A")
        assert mgr.n_sites == 0

    def test_remove_nonexistent_site_no_error(self):
        mgr = _make_mgr()
        mgr.remove_site("GHOST")  # should not raise


# ─── Strategy selection ─────────────────────────────────────────────────────


class TestStrategySelection:
    def test_high_price_returns_arbitrage(self):
        mgr = _make_mgr(discharge_threshold=80.0)
        import time

        from src.core.fleet_orchestrator import FleetSummary

        summary = FleetSummary(
            n_sites=1,
            total_capacity_kwh=100,
            fleet_soc_pct=70,
            total_power_kw=0,
            total_available_kw=50,
            sites_in_alarm=0,
            cycle_duration_s=0.01,
            timestamp=time.time(),
        )
        strategy = mgr._select_strategy(95.0, summary)
        assert strategy == DispatchStrategy.PRICE_ARBITRAGE

    def test_low_price_returns_arbitrage(self):
        mgr = _make_mgr(charge_threshold=40.0)
        import time

        from src.core.fleet_orchestrator import FleetSummary

        summary = FleetSummary(
            n_sites=1,
            total_capacity_kwh=100,
            fleet_soc_pct=70,
            total_power_kw=0,
            total_available_kw=50,
            sites_in_alarm=0,
            cycle_duration_s=0.01,
            timestamp=time.time(),
        )
        strategy = mgr._select_strategy(30.0, summary)
        assert strategy == DispatchStrategy.PRICE_ARBITRAGE

    def test_neutral_price_returns_hold(self):
        mgr = _make_mgr(discharge_threshold=80.0, charge_threshold=40.0)
        import time

        from src.core.fleet_orchestrator import FleetSummary

        summary = FleetSummary(
            n_sites=2,
            total_capacity_kwh=200,
            fleet_soc_pct=60,
            total_power_kw=0,
            total_available_kw=100,
            sites_in_alarm=0,
            cycle_duration_s=0.01,
            timestamp=time.time(),
        )
        strategy = mgr._select_strategy(60.0, summary)
        assert strategy == DispatchStrategy.HOLD

    def test_majority_alarms_forces_hold(self):
        mgr = _make_mgr(discharge_threshold=80.0)
        import time

        from src.core.fleet_orchestrator import FleetSummary

        # 2 sites, 2 in alarm → majority
        summary = FleetSummary(
            n_sites=2,
            total_capacity_kwh=200,
            fleet_soc_pct=60,
            total_power_kw=0,
            total_available_kw=100,
            sites_in_alarm=2,
            cycle_duration_s=0.01,
            timestamp=time.time(),
        )
        strategy = mgr._select_strategy(95.0, summary)
        assert strategy == DispatchStrategy.HOLD


# ─── Setpoint computation ────────────────────────────────────────────────────


class TestSetpointComputation:
    def _make_telemetry(self, site_id="A", soc=70.0, avail=50.0, anomaly=0.0) -> SiteTelemetry:
        return SiteTelemetry(
            site_id=site_id,
            soc_pct=soc,
            power_kw=0.0,
            temp_c=25.0,
            capacity_kwh=100.0,
            available_kw=avail,
            anomaly_score=anomaly,
        )

    def test_hold_strategy_returns_zero_setpoints(self):
        mgr = _make_mgr()
        tel = [self._make_telemetry()]
        setpoints, total = mgr._compute_setpoints(tel, DispatchStrategy.HOLD, 60.0)
        assert total == pytest.approx(0.0)
        assert setpoints[0].target_kw == pytest.approx(0.0)

    def test_discharge_above_price_threshold(self):
        mgr = _make_mgr(discharge_threshold=80.0, max_discharge_pct=1.0)
        tel = [self._make_telemetry(soc=70, avail=50.0)]
        setpoints, total = mgr._compute_setpoints(tel, DispatchStrategy.PRICE_ARBITRAGE, 95.0)
        assert total == pytest.approx(50.0)
        assert setpoints[0].target_kw == pytest.approx(50.0)

    def test_charge_below_price_threshold(self):
        mgr = _make_mgr(charge_threshold=40.0)
        tel = [self._make_telemetry(soc=50, avail=50.0)]
        setpoints, total = mgr._compute_setpoints(tel, DispatchStrategy.PRICE_ARBITRAGE, 30.0)
        assert total < 0  # charging → negative kW

    def test_soc_floor_prevents_discharge(self):
        mgr = _make_mgr(min_soc_pct=15.0, discharge_threshold=80.0)
        tel = [self._make_telemetry(soc=10.0, avail=50.0)]  # below floor
        setpoints, total = mgr._compute_setpoints(tel, DispatchStrategy.PRICE_ARBITRAGE, 95.0)
        assert setpoints[0].target_kw == pytest.approx(0.0)

    def test_soc_ceiling_prevents_charging(self):
        mgr = _make_mgr(max_soc_pct=95.0, charge_threshold=40.0)
        tel = [self._make_telemetry(soc=98.0, avail=50.0)]  # above ceiling
        setpoints, total = mgr._compute_setpoints(tel, DispatchStrategy.PRICE_ARBITRAGE, 30.0)
        assert setpoints[0].target_kw == pytest.approx(0.0)

    def test_site_in_alarm_always_holds(self):
        mgr = _make_mgr(discharge_threshold=80.0)
        tel = [self._make_telemetry(anomaly=0.9)]  # in alarm
        setpoints, total = mgr._compute_setpoints(tel, DispatchStrategy.PRICE_ARBITRAGE, 95.0)
        assert setpoints[0].target_kw == pytest.approx(0.0)
        assert setpoints[0].strategy == DispatchStrategy.HOLD

    def test_empty_telemetry_returns_zero(self):
        mgr = _make_mgr()
        setpoints, total = mgr._compute_setpoints([], DispatchStrategy.PRICE_ARBITRAGE, 95.0)
        assert total == pytest.approx(0.0)
        assert setpoints == []


# ─── Run cycle integration ───────────────────────────────────────────────────


class TestRunCycle:
    def test_cycle_returns_cycle_result(self):
        mgr = _make_mgr()
        mgr.add_site("A", _make_proxy("A"))
        result = mgr.run_cycle(market_price_usd_mwh=95.0)
        assert isinstance(result, CycleResult)

    def test_high_price_publishes_event(self):
        mgr = _make_mgr(discharge_threshold=80.0)
        mgr.add_site("A", _make_proxy("A", soc=70, avail=50.0))
        result = mgr.run_cycle(market_price_usd_mwh=95.0)
        assert result.dispatching  # event is not None
        assert result.total_dispatch_kw > 0

    def test_hold_price_no_event(self):
        mgr = _make_mgr(discharge_threshold=80.0, charge_threshold=40.0)
        mgr.add_site("A", _make_proxy("A"))
        result = mgr.run_cycle(market_price_usd_mwh=60.0)  # neutral band
        assert result.strategy == DispatchStrategy.HOLD
        assert result.event is None

    def test_insufficient_sites_returns_hold(self):
        mgr = _make_mgr(min_fleet_sites=2)  # requires 2 sites
        mgr.add_site("A", _make_proxy("A"))  # only 1 available but min_fleet_sites=2
        result = mgr.run_cycle(market_price_usd_mwh=95.0)
        # FleetOrchestrator will report n_sites=1 which is < min 2
        assert result.strategy == DispatchStrategy.HOLD

    def test_cycle_counter_increments(self):
        mgr = _make_mgr()
        mgr.add_site("A", _make_proxy("A"))
        mgr.run_cycle(market_price_usd_mwh=95.0)
        mgr.run_cycle(market_price_usd_mwh=95.0)
        assert mgr.cycle_count == 2

    def test_last_result_is_stored(self):
        mgr = _make_mgr()
        mgr.add_site("A", _make_proxy("A"))
        assert mgr.last_result is None
        mgr.run_cycle()
        assert mgr.last_result is not None

    def test_strategy_override_forces_hold(self):
        mgr = _make_mgr(discharge_threshold=80.0)
        mgr.add_site("A", _make_proxy("A", soc=70, avail=50))
        result = mgr.run_cycle(
            market_price_usd_mwh=95.0,
            strategy_override=DispatchStrategy.HOLD,
        )
        assert result.strategy == DispatchStrategy.HOLD
        assert result.event is None

    def test_cycle_result_n_sites_property(self):
        mgr = _make_mgr()
        mgr.add_site("A", _make_proxy("A"))
        mgr.add_site("B", _make_proxy("B"))
        result = mgr.run_cycle()
        assert result.n_sites == 2

    def test_cycle_duration_positive(self):
        mgr = _make_mgr()
        mgr.add_site("A", _make_proxy("A"))
        result = mgr.run_cycle()
        assert result.cycle_duration_s >= 0.0


# ─── SiteSetpoint & CycleResult ──────────────────────────────────────────────


class TestDataclasses:
    def test_site_setpoint_fields(self):
        sp = SiteSetpoint(
            site_id="CL-001", target_kw=45.0, strategy=DispatchStrategy.PRICE_ARBITRAGE
        )
        assert sp.site_id == "CL-001"
        assert sp.target_kw == pytest.approx(45.0)
        assert sp.strategy == DispatchStrategy.PRICE_ARBITRAGE

    def test_dispatch_strategy_enum_values(self):
        assert DispatchStrategy.PRICE_ARBITRAGE.value == "price_arbitrage"
        assert DispatchStrategy.HOLD.value == "hold"
        assert DispatchStrategy.DRL.value == "drl"
