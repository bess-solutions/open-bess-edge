# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_fleet_coordinator.py
=================================
Unit tests for ``src.interfaces.fleet_coordinator``.

Covers:
  - FleetSiteState: available_discharge_kw, available_charge_kw, is_stale,
    is_overtemperature, to_dict()
  - SiteSetpoint: to_dict()
  - FleetCoordinator: register/update/remove site, active_sites filtering,
    total_flex_kw, fleet_avg_soc, compute_setpoints (discharge & charge),
    fleet_summary, edge cases
"""

from __future__ import annotations

import time

import pytest

from src.interfaces.fleet_coordinator import (
    FleetCoordinator,
    FleetSiteState,
    SiteSetpoint,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _site(
    site_id: str = "S1",
    node: str = "Maitencillo",
    soc: float = 70.0,
    max_kw: float = 500.0,
    current_kw: float = 0.0,
    temp: float | None = None,
    last_seen: float | None = None,
) -> FleetSiteState:
    s = FleetSiteState(
        site_id=site_id,
        node=node,
        soc_pct=soc,
        max_power_kw=max_kw,
        current_power_kw=current_kw,
        temperature_c=temp,
    )
    if last_seen is not None:
        s.last_seen = last_seen
    return s


def _coord(**kwargs) -> FleetCoordinator:
    return FleetCoordinator(**kwargs)


# ---------------------------------------------------------------------------
# FleetSiteState properties
# ---------------------------------------------------------------------------

class TestFleetSiteStateProperties:
    # available_discharge_kw

    def test_discharge_kw_full_soc(self):
        """SOC=70% with 500 kW max → usable_soc=60%, expected discharge."""
        s = _site(soc=70.0, max_kw=500.0)
        expected = min(500.0, (70.0 - 10.0) / 100.0 * 500.0 * 2)
        assert s.available_discharge_kw == pytest.approx(expected)

    def test_discharge_kw_zero_at_soc_floor(self):
        """SOC at 10% → usable_soc=0 → available_discharge=0."""
        s = _site(soc=10.0, max_kw=500.0)
        assert s.available_discharge_kw == pytest.approx(0.0)

    def test_discharge_kw_capped_at_max(self):
        """Very high SOC → cap at max_power_kw."""
        s = _site(soc=100.0, max_kw=100.0)
        assert s.available_discharge_kw == pytest.approx(100.0)

    def test_discharge_kw_below_floor_is_zero(self):
        """SOC below 10% → 0 discharge (clamped via max(0, soc-10))."""
        s = _site(soc=5.0, max_kw=500.0)
        assert s.available_discharge_kw == pytest.approx(0.0)

    # available_charge_kw

    def test_charge_kw_room_below_ceiling(self):
        """SOC=50% → headroom=45% → charge kW."""
        s = _site(soc=50.0, max_kw=500.0)
        expected = min(500.0, (95.0 - 50.0) / 100.0 * 500.0 * 2)
        assert s.available_charge_kw == pytest.approx(expected)

    def test_charge_kw_zero_at_ceiling(self):
        """SOC=95% → headroom=0 → no charge."""
        s = _site(soc=95.0, max_kw=500.0)
        assert s.available_charge_kw == pytest.approx(0.0)

    def test_charge_kw_capped_at_max(self):
        """Very low SOC → cap at max_power_kw."""
        s = _site(soc=0.0, max_kw=100.0)
        assert s.available_charge_kw == pytest.approx(100.0)

    # is_stale

    def test_fresh_site_not_stale(self):
        s = _site(last_seen=time.time())
        assert not s.is_stale

    def test_old_site_is_stale(self):
        s = _site(last_seen=time.time() - 400.0)
        assert s.is_stale

    # is_overtemperature

    def test_no_temp_not_overtemp(self):
        s = _site(temp=None)
        assert not s.is_overtemperature

    def test_temp_below_45_not_overtemp(self):
        s = _site(temp=40.0)
        assert not s.is_overtemperature

    def test_temp_above_45_is_overtemp(self):
        s = _site(temp=46.0)
        assert s.is_overtemperature

    def test_temp_exactly_45_not_overtemp(self):
        s = _site(temp=45.0)
        assert not s.is_overtemperature

    # to_dict()

    def test_to_dict_contains_required_keys(self):
        s = _site()
        d = s.to_dict()
        for key in ["site_id", "node", "soc_pct", "max_power_kw",
                    "available_discharge_kw", "available_charge_kw",
                    "is_stale", "is_overtemperature"]:
            assert key in d

    def test_to_dict_values_rounded(self):
        s = _site(soc=70.123456, max_kw=500.0)
        d = s.to_dict()
        assert d["soc_pct"] == pytest.approx(70.1, abs=0.05)


# ---------------------------------------------------------------------------
# SiteSetpoint
# ---------------------------------------------------------------------------

class TestSiteSetpoint:
    def test_to_dict_keys(self):
        sp = SiteSetpoint(site_id="S1", power_kw=-200.0, reason="proportional_discharge")
        d = sp.to_dict()
        assert "site_id" in d
        assert "power_kw" in d
        assert "reason" in d

    def test_to_dict_values(self):
        sp = SiteSetpoint(site_id="S1", power_kw=-200.5678)
        d = sp.to_dict()
        assert d["power_kw"] == pytest.approx(-200.6, abs=0.05)


# ---------------------------------------------------------------------------
# FleetCoordinator — site management
# ---------------------------------------------------------------------------

class TestSiteManagement:
    def test_register_site_increments_n_sites(self):
        coord = _coord()
        coord.register_site(_site("S1"))
        coord.register_site(_site("S2"))
        assert coord.n_sites == 2

    def test_register_same_id_overwrites(self):
        coord = _coord()
        coord.register_site(_site("S1", soc=60.0))
        coord.register_site(_site("S1", soc=80.0))
        assert coord.n_sites == 1
        assert coord._sites["S1"].soc_pct == pytest.approx(80.0)

    def test_remove_site(self):
        coord = _coord()
        coord.register_site(_site("S1"))
        coord.remove_site("S1")
        assert coord.n_sites == 0

    def test_remove_nonexistent_no_error(self):
        coord = _coord()
        coord.remove_site("DOES_NOT_EXIST")  # should not raise

    def test_update_site_changes_field(self):
        coord = _coord()
        coord.register_site(_site("S1", soc=60.0))
        coord.update_site("S1", soc_pct=80.0)
        assert coord._sites["S1"].soc_pct == pytest.approx(80.0)

    def test_update_unknown_site_raises(self):
        coord = _coord()
        with pytest.raises(KeyError):
            coord.update_site("UNKNOWN", soc_pct=50.0)

    def test_update_site_refreshes_last_seen(self):
        coord = _coord()
        old_ts = time.time() - 200
        coord.register_site(_site("S1", last_seen=old_ts))
        coord.update_site("S1", soc_pct=50.0)
        assert coord._sites["S1"].last_seen > old_ts


# ---------------------------------------------------------------------------
# FleetCoordinator — active_sites filtering
# ---------------------------------------------------------------------------

class TestActiveSites:
    def test_fresh_sites_are_active(self):
        coord = _coord()
        coord.register_site(_site("S1"))
        coord.register_site(_site("S2"))
        assert coord.n_active_sites == 2

    def test_stale_site_excluded(self):
        coord = _coord()
        coord.register_site(_site("S1"))
        coord.register_site(_site("S2", last_seen=time.time() - 400))
        assert coord.n_active_sites == 1

    def test_overtemp_site_excluded(self):
        coord = _coord()
        coord.register_site(_site("S1", temp=50.0))  # overtemp
        coord.register_site(_site("S2", temp=35.0))  # ok
        assert coord.n_active_sites == 1

    def test_stale_and_overtemp_both_excluded(self):
        coord = _coord()
        coord.register_site(_site("S1", last_seen=time.time() - 400, temp=50.0))
        assert coord.n_active_sites == 0


# ---------------------------------------------------------------------------
# FleetCoordinator — aggregation
# ---------------------------------------------------------------------------

class TestAggregation:
    def test_total_flex_discharge_zero_no_sites(self):
        coord = _coord()
        assert coord.total_flex_kw("discharge") == pytest.approx(0.0)

    def test_total_flex_charge_zero_no_sites(self):
        coord = _coord()
        assert coord.total_flex_kw("charge") == pytest.approx(0.0)

    def test_total_flex_discharge_sums_sites(self):
        coord = _coord()
        s1 = _site("S1", soc=70.0, max_kw=500.0)
        s2 = _site("S2", soc=80.0, max_kw=500.0)
        coord.register_site(s1)
        coord.register_site(s2)
        expected = s1.available_discharge_kw + s2.available_discharge_kw
        assert coord.total_flex_kw("discharge") == pytest.approx(expected)

    def test_fleet_avg_soc_simple(self):
        coord = _coord()
        coord.register_site(_site("S1", soc=60.0))
        coord.register_site(_site("S2", soc=80.0))
        assert coord.fleet_avg_soc() == pytest.approx(70.0)

    def test_fleet_avg_soc_zero_no_sites(self):
        coord = _coord()
        assert coord.fleet_avg_soc() == pytest.approx(0.0)

    def test_fleet_avg_soc_excludes_stale(self):
        coord = _coord()
        coord.register_site(_site("S1", soc=60.0))
        coord.register_site(_site("S2", soc=100.0, last_seen=time.time() - 400))
        # Only S1 is active
        assert coord.fleet_avg_soc() == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# FleetCoordinator — compute_setpoints()
# ---------------------------------------------------------------------------

class TestComputeSetpoints:
    def test_no_active_sites_returns_empty(self):
        coord = _coord()
        assert coord.compute_setpoints(dispatch_kw=100.0) == []

    def test_below_min_flex_returns_zeros(self):
        coord = _coord(min_flex_kw=1000.0)
        coord.register_site(_site("S1", soc=70.0, max_kw=100.0))
        setpoints = coord.compute_setpoints(dispatch_kw=50.0)
        assert len(setpoints) == 1
        assert setpoints[0].power_kw == pytest.approx(0.0)
        assert setpoints[0].reason == "below_min_flex"

    def test_discharge_setpoints_negative_sign(self):
        coord = _coord(min_flex_kw=0.0)
        coord.register_site(_site("S1", soc=70.0, max_kw=500.0))
        setpoints = coord.compute_setpoints(dispatch_kw=100.0, mode="discharge")
        assert setpoints[0].power_kw <= 0.0  # discharge = negative

    def test_charge_setpoints_positive_sign(self):
        coord = _coord(min_flex_kw=0.0)
        coord.register_site(_site("S1", soc=50.0, max_kw=500.0))
        setpoints = coord.compute_setpoints(dispatch_kw=100.0, mode="charge")
        assert setpoints[0].power_kw >= 0.0  # charge = positive

    def test_setpoints_capped_at_available_flex(self):
        coord = _coord(min_flex_kw=0.0)
        coord.register_site(_site("S1", soc=70.0, max_kw=500.0))
        avail = coord._sites["S1"].available_discharge_kw
        setpoints = coord.compute_setpoints(dispatch_kw=avail * 10, mode="discharge")
        # Actual delivery should not exceed available
        assert abs(setpoints[0].power_kw) <= avail + 1.0  # allow rounding

    def test_proportional_allocation_two_sites(self):
        coord = _coord(min_flex_kw=0.0)
        # S1 has 2× more flex than S2 → should get 2× the setpoint
        coord.register_site(_site("S1", soc=90.0, max_kw=500.0))
        coord.register_site(_site("S2", soc=90.0, max_kw=250.0))
        setpoints = coord.compute_setpoints(dispatch_kw=150.0, mode="discharge")
        by_site = {sp.site_id: abs(sp.power_kw) for sp in setpoints}
        # S1 should get roughly 2× S2's setpoint
        assert by_site["S1"] == pytest.approx(by_site["S2"] * 2, rel=0.05)

    def test_one_setpoint_per_active_site(self):
        coord = _coord(min_flex_kw=0.0)
        for i in range(4):
            coord.register_site(_site(f"S{i}", soc=70.0))
        setpoints = coord.compute_setpoints(dispatch_kw=200.0)
        assert len(setpoints) == 4

    def test_stale_sites_excluded_from_setpoints(self):
        coord = _coord(min_flex_kw=0.0)
        coord.register_site(_site("S1", soc=70.0))
        coord.register_site(_site("S2", soc=70.0, last_seen=time.time() - 400))
        setpoints = coord.compute_setpoints(dispatch_kw=100.0)
        site_ids = [sp.site_id for sp in setpoints]
        assert "S2" not in site_ids


# ---------------------------------------------------------------------------
# FleetCoordinator — fleet_summary()
# ---------------------------------------------------------------------------

class TestFleetSummary:
    def test_summary_keys(self):
        coord = _coord()
        s = coord.fleet_summary()
        for key in ["n_sites", "n_active", "stale_sites", "overtemp_sites",
                    "fleet_avg_soc_pct", "total_discharge_flex_kw",
                    "total_charge_flex_kw", "program_id", "sites"]:
            assert key in s

    def test_summary_n_sites(self):
        coord = _coord()
        coord.register_site(_site("S1"))
        coord.register_site(_site("S2"))
        assert coord.fleet_summary()["n_sites"] == 2

    def test_summary_stale_sites_listed(self):
        coord = _coord()
        coord.register_site(_site("S1", last_seen=time.time() - 400))
        s = coord.fleet_summary()
        assert "S1" in s["stale_sites"]

    def test_summary_overtemp_sites_listed(self):
        coord = _coord()
        coord.register_site(_site("S1", temp=50.0))
        s = coord.fleet_summary()
        assert "S1" in s["overtemp_sites"]

    def test_summary_program_id(self):
        coord = FleetCoordinator(program_id="BESSAI-TEST-99")
        assert coord.fleet_summary()["program_id"] == "BESSAI-TEST-99"

    def test_summary_sites_list(self):
        coord = _coord()
        coord.register_site(_site("S1"))
        sites_list = coord.fleet_summary()["sites"]
        assert len(sites_list) == 1
        assert sites_list[0]["site_id"] == "S1"
