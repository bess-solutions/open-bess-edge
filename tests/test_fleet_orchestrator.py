"""
tests/test_fleet_orchestrator.py
=================================
Unit tests for FleetOrchestrator, SiteProxy, and FleetSummary.
"""

from __future__ import annotations

import pytest
from src.core.fleet_orchestrator import (
    FleetOrchestrator,
    FleetSummary,
    SiteProxy,
    SiteTelemetry,
)


def _make_telemetry(
    site_id: str,
    soc: float = 70.0,
    power: float = 0.0,
    cap: float = 100.0,
    avail: float = 50.0,
    anomaly: float = 0.0,
) -> SiteTelemetry:
    return SiteTelemetry(
        site_id=site_id,
        soc_pct=soc,
        power_kw=power,
        temp_c=25.0,
        capacity_kwh=cap,
        available_kw=avail,
        anomaly_score=anomaly,
    )


def _make_proxy(site_id: str, **kw) -> SiteProxy:
    def fn(sid: str) -> SiteTelemetry:
        return _make_telemetry(sid, **kw)

    return SiteProxy(
        host="localhost", site_id=site_id, capacity_kwh=kw.get("cap", 100.0), telemetry_fn=fn
    )


class TestFleetOrchestrator:
    def test_register_site_increases_n_sites(self):
        orch = FleetOrchestrator()
        orch.register_site("A", _make_proxy("A"))
        orch.register_site("B", _make_proxy("B"))
        assert orch.n_sites == 2

    def test_remove_site_decreases_n_sites(self):
        orch = FleetOrchestrator()
        orch.register_site("A", _make_proxy("A"))
        orch.remove_site("A")
        assert orch.n_sites == 0

    def test_total_capacity_sums_all_sites(self):
        orch = FleetOrchestrator()
        orch.register_site("A", _make_proxy("A", cap=100.0))
        orch.register_site("B", _make_proxy("B", cap=200.0))
        assert orch.total_capacity_kwh == pytest.approx(300.0)

    def test_aggregate_empty_returns_zero_summary(self):
        orch = FleetOrchestrator()
        summary = orch.aggregate([])
        assert summary.n_sites == 0
        assert summary.fleet_soc_pct == pytest.approx(0.0)

    def test_aggregate_weighted_soc(self):
        tels = [
            _make_telemetry("A", soc=80.0, cap=100.0),
            _make_telemetry("B", soc=40.0, cap=100.0),
        ]
        orch = FleetOrchestrator()
        summary = orch.aggregate(tels)
        assert summary.fleet_soc_pct == pytest.approx(60.0)

    def test_aggregate_counts_alarms(self):
        tels = [
            _make_telemetry("A", anomaly=0.9),  # alarm
            _make_telemetry("B", anomaly=0.2),  # ok
            _make_telemetry("C", anomaly=0.8),  # alarm
        ]
        orch = FleetOrchestrator(anomaly_threshold=0.7)
        summary = orch.aggregate(tels)
        assert summary.sites_in_alarm == 2

    def test_run_cycle_returns_fleet_summary(self):
        orch = FleetOrchestrator()
        orch.register_site("A", _make_proxy("A", soc=60.0, avail=30.0))
        summary = orch.run_cycle()
        assert isinstance(summary, FleetSummary)
        assert summary.n_sites == 1
        assert summary.fleet_soc_pct == pytest.approx(60.0)
        assert summary.cycle_duration_s >= 0.0
