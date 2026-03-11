# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
tests/test_fleet_coordinator.py
=================================
Test suite for FleetCoordinator and FleetSiteState (Phase 2 — Fleet Mode).
"""
from __future__ import annotations

import time

import pytest

from src.interfaces.fleet_coordinator import FleetCoordinator, FleetSiteState, SiteSetpoint


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_site(site_id="SITE-01", soc=60.0, power_kw=500.0, temp=None) -> FleetSiteState:
    return FleetSiteState(
        site_id=site_id,
        node="Maitencillo",
        soc_pct=soc,
        max_power_kw=power_kw,
        temperature_c=temp,
    )


@pytest.fixture
def coord() -> FleetCoordinator:
    return FleetCoordinator(min_flex_kw=10.0)


@pytest.fixture
def three_site_coord() -> FleetCoordinator:
    c = FleetCoordinator(min_flex_kw=10.0)
    c.register_site(make_site("SITE-01", soc=70.0, power_kw=500.0))
    c.register_site(make_site("SITE-02", soc=50.0, power_kw=300.0))
    c.register_site(make_site("SITE-03", soc=40.0, power_kw=200.0))
    return c


# ── FleetSiteState tests ──────────────────────────────────────────────────────

class TestFleetSiteState:

    def test_available_discharge_at_normal_soc(self):
        site = make_site(soc=60.0, power_kw=500.0)
        assert site.available_discharge_kw > 0
        assert site.available_discharge_kw <= site.max_power_kw

    def test_available_discharge_zero_at_min_soc(self):
        site = make_site(soc=10.0, power_kw=500.0)
        assert site.available_discharge_kw == 0.0

    def test_available_charge_at_normal_soc(self):
        site = make_site(soc=60.0, power_kw=500.0)
        assert site.available_charge_kw > 0

    def test_available_charge_zero_at_full_soc(self):
        site = make_site(soc=95.0, power_kw=500.0)
        assert site.available_charge_kw == 0.0

    def test_not_stale_when_just_created(self):
        site = make_site()
        assert not site.is_stale

    def test_stale_when_last_seen_old(self):
        site = make_site()
        site.last_seen = time.time() - 400  # 400s ago > 300s threshold
        assert site.is_stale

    def test_overtemperature_above_45c(self):
        site = make_site(temp=46.0)
        assert site.is_overtemperature

    def test_normal_temperature(self):
        site = make_site(temp=35.0)
        assert not site.is_overtemperature

    def test_to_dict_structure(self):
        site = make_site()
        d = site.to_dict()
        assert "site_id" in d
        assert "soc_pct" in d
        assert "available_discharge_kw" in d
        assert "is_stale" in d


# ── FleetCoordinator tests ────────────────────────────────────────────────────

class TestFleetCoordinator:

    def test_register_and_count(self, coord):
        coord.register_site(make_site("A"))
        coord.register_site(make_site("B"))
        assert coord.n_sites == 2

    def test_remove_site(self, coord):
        coord.register_site(make_site("A"))
        coord.remove_site("A")
        assert coord.n_sites == 0

    def test_update_site_soc(self, coord):
        coord.register_site(make_site("A", soc=50.0))
        coord.update_site("A", soc_pct=80.0)
        assert coord._sites["A"].soc_pct == 80.0

    def test_update_unknown_site_raises(self, coord):
        with pytest.raises(KeyError):
            coord.update_site("UNKNOWN", soc_pct=50.0)

    def test_active_sites_excludes_stale(self, coord):
        coord.register_site(make_site("FRESH"))
        stale = make_site("STALE")
        stale.last_seen = time.time() - 400
        coord.register_site(stale)
        assert len(coord.active_sites) == 1
        assert coord.active_sites[0].site_id == "FRESH"

    def test_active_sites_excludes_overtemp(self, coord):
        coord.register_site(make_site("NORMAL", temp=30.0))
        coord.register_site(make_site("HOT", temp=50.0))
        assert len(coord.active_sites) == 1

    def test_total_flex_discharge(self, three_site_coord):
        flex = three_site_coord.total_flex_kw("discharge")
        assert flex > 0

    def test_fleet_avg_soc(self, three_site_coord):
        avg = three_site_coord.fleet_avg_soc()
        # 3 sites at 70, 50, 40 → avg = 53.3
        assert 50 < avg < 60

    def test_fleet_avg_soc_empty(self, coord):
        assert coord.fleet_avg_soc() == 0.0

    def test_compute_setpoints_discharge(self, three_site_coord):
        setpoints = three_site_coord.compute_setpoints(dispatch_kw=200.0, mode="discharge")
        assert len(setpoints) == 3
        total = sum(abs(s.power_kw) for s in setpoints if s.power_kw < 0)
        assert total > 0

    def test_compute_setpoints_below_min_flex(self):
        coord = FleetCoordinator(min_flex_kw=9999.0)
        coord.register_site(make_site(soc=50.0, power_kw=10.0))
        setpoints = coord.compute_setpoints(dispatch_kw=100.0)
        # All should be 0 (below min_flex)
        assert all(s.power_kw == 0.0 for s in setpoints)

    def test_compute_setpoints_no_sites(self, coord):
        result = coord.compute_setpoints(dispatch_kw=100.0)
        assert result == []

    def test_fleet_summary_structure(self, three_site_coord):
        summary = three_site_coord.fleet_summary()
        assert "n_sites" in summary
        assert "fleet_avg_soc_pct" in summary
        assert "total_discharge_flex_kw" in summary
        assert "sites" in summary
        assert len(summary["sites"]) == 3

    def test_stale_sites_in_summary(self):
        coord = FleetCoordinator()
        stale = make_site("STALE")
        stale.last_seen = time.time() - 400
        coord.register_site(stale)
        summary = coord.fleet_summary()
        assert "STALE" in summary["stale_sites"]
