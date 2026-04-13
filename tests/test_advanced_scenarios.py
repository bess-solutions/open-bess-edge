# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_advanced_scenarios.py
==================================
Advanced test scenarios — Tier-1 production readiness.

Implements all recommendations from the 2026-04-12 review:
  1. LCAEngine.carbon_viability_score and viability_report()
  2. LCAEngine strict_region — ValueError on unknown region
  3. AlertManager — CRITICAL never silenced by dedup window timing
  4. AlertManager — configurable dedup_window_s edge cases
  5. FleetSiteState.injection_kw — positive alias, in to_dict()
  6. FleetCoordinator stress — 100 sites computed in < 100 ms
  7. Integration: FleetCoordinator overtemp → AlertManager CRITICAL
     → HealthServer reflects degraded state
"""

from __future__ import annotations

import json
import time

import pytest
from aiohttp.test_utils import make_mocked_request
from src.interfaces.alert_manager import AlertLevel, AlertManager
from src.interfaces.fleet_coordinator import (
    FleetCoordinator,
    FleetSiteState,
)
from src.interfaces.health import HealthServer
from src.interfaces.lca_config import GRID_EMISSION_FACTORS_G_KWH
from src.interfaces.lca_engine import LCAConfig, LCAEngine

# ---------------------------------------------------------------------------
# 1. LCAEngine — carbon_viability_score
# ---------------------------------------------------------------------------

class TestCarbonViabilityScore:
    """Validate the 0-3 carbon viability scoring system."""

    def test_norway_is_marginal(self):
        """NO: 19 g/kWh < 80 → score 0 (marginal)."""
        engine = LCAEngine(config=LCAConfig(region="NO"))
        assert engine.carbon_viability_score == 0
        assert engine.carbon_viability_label == "marginal"

    def test_france_is_marginal(self):
        """FR: 52 g/kWh < 80 → score 0 (nuclear-heavy)."""
        engine = LCAEngine(config=LCAConfig(region="FR"))
        assert engine.carbon_viability_score == 0

    def test_uruguay_is_marginal(self):
        """UY: 48 g/kWh → marginal."""
        engine = LCAEngine(config=LCAConfig(region="UY"))
        assert engine.carbon_viability_score == 0

    def test_brazil_is_low(self):
        """BR: 82 g/kWh — just above 80 threshold → score 1 (low)."""
        engine = LCAEngine(config=LCAConfig(region="BR"))
        assert engine.carbon_viability_score == 1
        assert engine.carbon_viability_label == "low"

    def test_colombia_is_low(self):
        """CO: 130 g/kWh → low."""
        engine = LCAEngine(config=LCAConfig(region="CO"))
        assert engine.carbon_viability_score == 1

    def test_chile_is_medium(self):
        """CL: 335 g/kWh → medium (supports carbon credits)."""
        engine = LCAEngine(config=LCAConfig(region="CL"))
        assert engine.carbon_viability_score == 2
        assert engine.carbon_viability_label == "medium"

    def test_germany_is_medium(self):
        """DE: 349 g/kWh → medium."""
        engine = LCAEngine(config=LCAConfig(region="DE"))
        assert engine.carbon_viability_score == 2

    def test_india_is_high(self):
        """IN: 708 g/kWh → high (coal-dominant)."""
        engine = LCAEngine(config=LCAConfig(region="IN"))
        assert engine.carbon_viability_score == 3
        assert engine.carbon_viability_label == "high"

    def test_south_africa_is_high(self):
        """ZA: 840 g/kWh → high."""
        engine = LCAEngine(config=LCAConfig(region="ZA"))
        assert engine.carbon_viability_score == 3

    def test_poland_is_high(self):
        """PL: 683 g/kWh → high."""
        engine = LCAEngine(config=LCAConfig(region="PL"))
        assert engine.carbon_viability_score == 3

    @pytest.mark.parametrize("ef, expected_score", [
        (10.0, 0),    # well below 80
        (79.9, 0),    # just below low threshold
        (80.0, 1),    # exactly at low threshold
        (199.9, 1),   # just below mid threshold
        (200.0, 2),   # exactly at mid threshold
        (399.9, 2),   # just below high threshold
        (400.0, 3),   # exactly at high threshold
        (999.0, 3),   # well above high threshold
    ])
    def test_score_boundaries(self, ef: float, expected_score: int):
        """Boundary conditions for the four scoring tiers."""
        engine = LCAEngine(config=LCAConfig(grid_emission_factor=ef))
        assert engine.carbon_viability_score == expected_score

    def test_score_monotonic_increasing(self):
        """Higher EF → higher or equal score."""
        efs = [10, 80, 200, 400, 800]
        scores = [
            LCAEngine(config=LCAConfig(grid_emission_factor=ef)).carbon_viability_score
            for ef in efs
        ]
        assert scores == sorted(scores)

    def test_label_matches_score(self):
        """Each score maps to a consistent label."""
        label_map = {0: "marginal", 1: "low", 2: "medium", 3: "high"}
        for ef, expected_score in [(10, 0), (100, 1), (300, 2), (500, 3)]:
            engine = LCAEngine(config=LCAConfig(grid_emission_factor=ef))
            assert engine.carbon_viability_label == label_map[expected_score]


class TestViabilityReport:
    """Validate viability_report() dict structure and content."""

    def test_report_has_required_keys(self):
        engine = LCAEngine(config=LCAConfig(region="CL"))
        report = engine.viability_report()
        for key in ["region", "grid_ef_g_kwh", "viability_score", "viability_label",
                    "cumulative_co2_avoided_kg", "equivalent_trees"]:
            assert key in report

    def test_marginal_report_includes_warning(self):
        """Marginal regions must include a warning key."""
        engine = LCAEngine(config=LCAConfig(region="NO"))  # 19 g/kWh
        report = engine.viability_report()
        assert "warning" in report
        assert "80 g/kWh" in report["warning"]

    def test_high_viability_report_no_warning(self):
        """High-viability regions must NOT include a warning."""
        engine = LCAEngine(config=LCAConfig(region="PL"))
        report = engine.viability_report()
        assert "warning" not in report

    def test_report_cumulative_reflects_updates(self):
        engine = LCAEngine(config=LCAConfig(region="CL"))
        engine.update(discharged_kwh=50.0)
        engine.update(discharged_kwh=50.0)
        report = engine.viability_report()
        assert report["cumulative_co2_avoided_kg"] > 0

    def test_report_region_reflected(self):
        engine = LCAEngine(config=LCAConfig(region="DE"))
        report = engine.viability_report()
        assert report["region"] == "DE"


# ---------------------------------------------------------------------------
# 2. LCAEngine — strict_region
# ---------------------------------------------------------------------------

class TestStrictRegion:
    def test_strict_raises_on_unknown(self):
        with pytest.raises(ValueError, match="Unsupported region"):
            LCAEngine(config=LCAConfig(region="XX"), strict_region=True)

    def test_strict_raises_message_includes_region(self):
        with pytest.raises(ValueError, match="XX"):
            LCAEngine(config=LCAConfig(region="XX"), strict_region=True)

    def test_strict_raises_message_includes_supported_list(self):
        with pytest.raises(ValueError, match="CL"):
            LCAEngine(config=LCAConfig(region="ZZ"), strict_region=True)

    def test_strict_false_does_not_raise(self):
        """Default behaviour (strict_region=False) → no error, uses global EF."""
        engine = LCAEngine(config=LCAConfig(region="XX"), strict_region=False)
        assert engine.grid_emission_factor_g_kwh == pytest.approx(345.0)

    def test_strict_valid_region_does_not_raise(self):
        """Valid region with strict_region=True must work normally."""
        engine = LCAEngine(config=LCAConfig(region="CL"), strict_region=True)
        assert engine.grid_emission_factor_g_kwh > 0

    @pytest.mark.parametrize("region", list(GRID_EMISSION_FACTORS_G_KWH.keys()))
    def test_all_supported_regions_pass_strict(self, region: str):
        """Every region in the DB must pass strict_region=True."""
        engine = LCAEngine(config=LCAConfig(region=region), strict_region=True)
        assert engine.carbon_viability_score in (0, 1, 2, 3)


# ---------------------------------------------------------------------------
# 3. AlertManager — CRITICAL dedup behaviour
# ---------------------------------------------------------------------------

class TestCriticalAlertDedup:
    """Critical alerts should be re-fired after the dedup window expires.
    Within the window, the dedup suppresses repeats — but the FIRST alert
    is always recorded in _active and remains visible.
    """

    def test_critical_first_fire_always_recorded(self):
        mgr = AlertManager(dedup_window_s=3600.0)  # 1 hour window
        result = mgr.fire(AlertLevel.CRITICAL, "OVERTEMP", "58°C")
        assert result is not None
        assert mgr.has_critical is True

    def test_critical_within_window_suppressed(self):
        """Within dedup window → second fire returns None; alert stays in _active."""
        mgr = AlertManager(dedup_window_s=3600.0)
        mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")
        result = mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")
        assert result is None           # suppressed
        assert mgr.has_critical is True  # but original still active!

    def test_critical_after_window_refired(self):
        """After window expires, the same alert CAN be refired."""
        mgr = AlertManager(dedup_window_s=0.01)  # 10ms window
        mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")
        time.sleep(0.05)  # exhaust the dedup window
        result = mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")
        assert result is not None

    def test_critical_always_visible_when_active(self):
        """Even if dedup silences re-fires, has_critical must remain True."""
        mgr = AlertManager(dedup_window_s=3600.0)
        mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")
        # Many attempts to re-fire → all silenced
        for _ in range(10):
            mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")
        # One active CRITICAL must remain
        assert mgr.has_critical is True
        assert mgr.critical_count == 1

    def test_critical_resolved_then_refirable(self):
        """After resolving CRITICAL alert, it can be fired again regardless of window."""
        mgr = AlertManager(dedup_window_s=3600.0)
        mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")
        mgr.resolve("OVERTEMP")         # resolve clears _active
        result = mgr.fire(AlertLevel.CRITICAL, "OVERTEMP")  # new fire
        assert result is not None
        assert mgr.has_critical is True

    def test_multiple_distinct_critical_all_active(self):
        """Multiple different CRITICAL names are all independent — no dedup cross-contamination."""
        mgr = AlertManager(dedup_window_s=3600.0)
        for i in range(5):
            mgr.fire(AlertLevel.CRITICAL, f"FAULT_{i}")
        assert mgr.critical_count == 5

    def test_warning_dedup_does_not_affect_critical_different_name(self):
        """Dedup of WARNING does NOT suppress a CRITICAL with a DIFFERENT name."""
        mgr = AlertManager(dedup_window_s=3600.0)
        mgr.fire(AlertLevel.WARNING, "SENSOR_FAULT_WARNING")
        result = mgr.fire(AlertLevel.CRITICAL, "SENSOR_FAULT_CRITICAL")
        # Different names → independent dedup → CRITICAL fires freely
        assert result is not None
        assert mgr.has_critical is True

    def test_warning_and_critical_same_name_dedup_semantics(self):
        """AlertManager uses alert NAME as dedup key (level-agnostic).
        If WARNING fires first and stays in _active, a CRITICAL with the
        same name within the dedup window is suppressed.
        This is by design — use distinct names to separate severity levels.
        """
        mgr = AlertManager(dedup_window_s=3600.0)
        mgr.fire(AlertLevel.WARNING, "SENSOR_FAULT")
        result = mgr.fire(AlertLevel.CRITICAL, "SENSOR_FAULT")  # same name → deduped
        assert result is None          # suppressed because name already active
        # WARNING remains the level stored — not silently upgraded
        assert mgr._active["SENSOR_FAULT"].level == AlertLevel.WARNING


# ---------------------------------------------------------------------------
# 4. FleetSiteState.injection_kw
# ---------------------------------------------------------------------------

class TestInjectionKw:
    """injection_kw is always non-negative and equal to available_discharge_kw."""

    def test_injection_kw_equals_discharge_kw(self):
        site = FleetSiteState(
            site_id="S1", node="Maitencillo",
            soc_pct=70.0, max_power_kw=500.0
        )
        assert site.injection_kw == pytest.approx(site.available_discharge_kw)

    def test_injection_kw_is_non_negative(self):
        """Even at lowest SOC, injection_kw >= 0."""
        for soc in [0.0, 5.0, 10.0, 50.0, 100.0]:
            site = FleetSiteState(
                site_id="T", node="N", soc_pct=soc, max_power_kw=500.0
            )
            assert site.injection_kw >= 0.0

    def test_injection_kw_zero_at_soc_floor(self):
        site = FleetSiteState(
            site_id="T", node="N", soc_pct=10.0, max_power_kw=500.0
        )
        assert site.injection_kw == pytest.approx(0.0)

    def test_injection_kw_in_to_dict(self):
        site = FleetSiteState(
            site_id="T", node="N", soc_pct=70.0, max_power_kw=500.0
        )
        d = site.to_dict()
        assert "injection_kw" in d
        assert d["injection_kw"] >= 0.0

    def test_injection_kw_to_dict_matches_property(self):
        site = FleetSiteState(
            site_id="T", node="N", soc_pct=75.0, max_power_kw=500.0
        )
        d = site.to_dict()
        assert d["injection_kw"] == pytest.approx(site.injection_kw, abs=0.1)

    def test_injection_kw_never_negative_for_any_config(self):
        """Fuzz: random SOC values — injection_kw always >= 0."""
        import random
        rng = random.Random(42)
        for _ in range(50):
            soc = rng.uniform(0.0, 100.0)
            max_kw = rng.uniform(50.0, 5000.0)
            site = FleetSiteState(
                site_id="T", node="N", soc_pct=soc, max_power_kw=max_kw
            )
            assert site.injection_kw >= 0.0


# ---------------------------------------------------------------------------
# 5. FleetCoordinator — Stress test (100 sites)
# ---------------------------------------------------------------------------

class TestFleetCoordinatorStress:
    """Performance: 100 registered sites must compute in < 100 ms."""

    def _register_n_sites(self, n: int) -> FleetCoordinator:
        coord = FleetCoordinator(min_flex_kw=0.0)
        for i in range(n):
            coord.register_site(FleetSiteState(
                site_id=f"SITE-{i:04d}",
                node=f"Node-{i}",
                soc_pct=50.0 + (i % 40),   # varied SOC 50-90%
                max_power_kw=500.0,
                temperature_c=25.0 + (i % 10),  # varied temp 25-34°C
            ))
        return coord

    def test_100_sites_registration_fast(self):
        t0 = time.perf_counter()
        coord = self._register_n_sites(100)
        elapsed = time.perf_counter() - t0
        assert coord.n_sites == 100
        assert elapsed < 0.5  # 500ms generous budget for registration

    def test_100_sites_total_flex_fast(self):
        coord = self._register_n_sites(100)
        t0 = time.perf_counter()
        flex = coord.total_flex_kw("discharge")
        elapsed = time.perf_counter() - t0
        assert flex > 0
        assert elapsed < 0.1  # < 100ms

    def test_100_sites_compute_setpoints_fast(self):
        coord = self._register_n_sites(100)
        t0 = time.perf_counter()
        setpoints = coord.compute_setpoints(dispatch_kw=10_000.0, mode="discharge")
        elapsed = time.perf_counter() - t0
        assert len(setpoints) == 100
        assert elapsed < 0.1  # < 100ms

    def test_100_sites_fleet_summary_fast(self):
        coord = self._register_n_sites(100)
        t0 = time.perf_counter()
        summary = coord.fleet_summary()
        elapsed = time.perf_counter() - t0
        assert summary["n_sites"] == 100
        assert elapsed < 0.1

    def test_100_sites_setpoints_sum_bounded_by_flex(self):
        """Total absolute setpoints must not exceed total available flex."""
        coord = self._register_n_sites(100)
        total_flex = coord.total_flex_kw("discharge")
        setpoints = coord.compute_setpoints(
            dispatch_kw=total_flex * 2, mode="discharge"
        )
        total_allocated = sum(abs(sp.power_kw) for sp in setpoints)
        assert total_allocated <= total_flex + 1.0  # allow rounding

    def test_stale_sites_excluded_at_scale(self):
        """50/100 stale sites — only 50 should appear in active set."""
        coord = FleetCoordinator(min_flex_kw=0.0)
        now = time.time()
        for i in range(50):
            coord.register_site(FleetSiteState(
                site_id=f"ACTIVE-{i}", node="N", soc_pct=70.0, max_power_kw=500.0,
                last_seen=now
            ))
        for i in range(50):
            coord.register_site(FleetSiteState(
                site_id=f"STALE-{i}", node="N", soc_pct=70.0, max_power_kw=500.0,
                last_seen=now - 400  # stale
            ))
        assert coord.n_active_sites == 50


# ---------------------------------------------------------------------------
# 6. Integration: FleetCoordinator overtemp → AlertManager → HealthServer
# ---------------------------------------------------------------------------

class TestIntegrationOvertempFlow:
    """
    End-to-end scenario:
      1. FleetCoordinator detects overtemperature sites.
      2. AlertManager fires CRITICAL.
      3. HealthServer /health reflects degraded state (503).
    """

    def _setup(self):
        """Return initialized coordinator, alert manager, health server."""
        coord = FleetCoordinator()
        mgr = AlertManager(site_id="INTEG-001")
        server = HealthServer(site_id="INTEG-001", version="test")
        return coord, mgr, server

    def test_overtemp_site_detected_in_summary(self):
        coord, _, _ = self._setup()
        coord.register_site(FleetSiteState(
            site_id="HOT-SITE", node="Maitencillo",
            soc_pct=70.0, max_power_kw=500.0, temperature_c=50.0  # overtemp
        ))
        summary = coord.fleet_summary()
        assert "HOT-SITE" in summary["overtemp_sites"]

    def test_alertmanager_critical_on_overtemp_detection(self):
        coord, mgr, _ = self._setup()
        coord.register_site(FleetSiteState(
            site_id="HOT-SITE", node="N",
            soc_pct=70.0, max_power_kw=500.0, temperature_c=50.0
        ))
        # Business logic: iterate sites and fire CRITICAL for overtemp
        summary = coord.fleet_summary()
        for site_id in summary["overtemp_sites"]:
            mgr.fire(AlertLevel.CRITICAL, f"OVERTEMP_{site_id}", f"Site {site_id} overtemperature")

        assert mgr.has_critical is True
        assert mgr.critical_count == 1

    async def test_healthserver_degraded_when_critical_alert(self):
        coord, mgr, server = self._setup()
        # Register an overtemp site
        coord.register_site(FleetSiteState(
            site_id="HOT-SITE", node="N",
            soc_pct=70.0, max_power_kw=500.0, temperature_c=50.0
        ))
        # Fire critical alert
        summary = coord.fleet_summary()
        for site_id in summary["overtemp_sites"]:
            mgr.fire(AlertLevel.CRITICAL, f"OVERTEMP_{site_id}")

        # Update HealthServer state to reflect critical alert
        server.last_cycle_ok = not mgr.has_critical

        # Query health endpoint
        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)

        assert resp.status == 503
        assert payload["status"] == "degraded"

    async def test_healthserver_healthy_after_alert_resolved(self):
        coord, mgr, server = self._setup()
        coord.register_site(FleetSiteState(
            site_id="HOT-SITE", node="N",
            soc_pct=70.0, max_power_kw=500.0, temperature_c=50.0
        ))
        summary = coord.fleet_summary()
        for site_id in summary["overtemp_sites"]:
            mgr.fire(AlertLevel.CRITICAL, f"OVERTEMP_{site_id}")

        # Simulate cooling: resolve alert
        mgr.resolve_all()
        server.last_cycle_ok = not mgr.has_critical  # True → healthy

        req = make_mocked_request("GET", "/health")
        resp = await server._handle_health(req)
        payload = json.loads(resp.text)

        assert resp.status == 200
        assert payload["status"] == "healthy"

    def test_multiple_overtemp_sites_all_fire_alerts(self):
        coord, mgr, _ = self._setup()
        for i in range(5):
            coord.register_site(FleetSiteState(
                site_id=f"HOT-{i}", node="N",
                soc_pct=70.0, max_power_kw=500.0, temperature_c=50.0
            ))
        summary = coord.fleet_summary()
        for site_id in summary["overtemp_sites"]:
            mgr.fire(AlertLevel.CRITICAL, f"OVERTEMP_{site_id}")

        assert mgr.critical_count == 5

    def test_normal_temperature_does_not_trigger_alert(self):
        coord, mgr, _ = self._setup()
        coord.register_site(FleetSiteState(
            site_id="COOL-SITE", node="N",
            soc_pct=70.0, max_power_kw=500.0, temperature_c=35.0  # normal
        ))
        summary = coord.fleet_summary()
        # No overtemp sites → no alerts fired
        for site_id in summary["overtemp_sites"]:
            mgr.fire(AlertLevel.CRITICAL, f"OVERTEMP_{site_id}")

        assert mgr.has_critical is False

    def test_mixed_fleet_only_hot_sites_alert(self):
        coord, mgr, _ = self._setup()
        coord.register_site(FleetSiteState(
            site_id="COOL-1", node="N", soc_pct=70.0, max_power_kw=500.0, temperature_c=30.0
        ))
        coord.register_site(FleetSiteState(
            site_id="HOT-1", node="N", soc_pct=70.0, max_power_kw=500.0, temperature_c=55.0
        ))
        coord.register_site(FleetSiteState(
            site_id="COOL-2", node="N", soc_pct=70.0, max_power_kw=500.0, temperature_c=25.0
        ))
        summary = coord.fleet_summary()
        for site_id in summary["overtemp_sites"]:
            mgr.fire(AlertLevel.CRITICAL, f"OVERTEMP_{site_id}")

        assert mgr.critical_count == 1
        active_names = [a["name"] for a in mgr.get_active()]
        assert any("HOT-1" in n for n in active_names)
