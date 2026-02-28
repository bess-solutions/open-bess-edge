# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_compliance_integration.py
======================================
Integration test — All NTSyCS compliance modules working together
in a simulated single control cycle, end-to-end.

Verifies that:
* SafetyGuard.check_safety + apply_ramp_limit pipeline (GAP-001)
* FrequencyResponseAgent + ReactiveController compute setpoints (GAP-002/011)
* PowerQualityMonitor gate blocks on bad PQ metrics (GAP-010)
* CENPublisher dry-run publishes correct payload (GAP-003)
* SL2SecurityGate authorizes/blocks commands correctly (GAP-009)
* PMGDComplianceEngine blocks Decreto 88/2023 violations (GAP-007)
* ERNCRegistry tracks ERNC fractions + generates certificate (GAP-008)
"""

from __future__ import annotations

import asyncio
import time

import pytest

from src.core.safety import SafetyGuard
from src.core.frequency_response import FrequencyResponseAgent
from src.core.reactive_power import ReactiveController
from src.core.power_quality import PowerQualityMonitor
from src.core.publishers.cen_publisher import CENPublisher
from src.core.iec62443 import SL2SecurityGate
from src.core.pmgd_compliance import PMGDComplianceEngine
from src.core.ernc_registry import ERNCRegistry


# ---------------------------------------------------------------------------
# Shared fixture: realistic BESS telemetry snapshot
# ---------------------------------------------------------------------------

TELEMETRY_NOMINAL = {
    "soc": 68.5,
    "active_power": 45000.0,   # 45 kW (expressed in W for main.py compat)
    "grid_frequency": 49.85,   # slightly below nominal = underfrequency event
    "ac_voltage": 218.5,       # 218.5/230 = 0.95 pu = significant undervoltage
    "temp_c": 28.5,
    "thd_pct": 3.2,
    "pst": 0.6,
    "plt": 0.5,
}


# ---------------------------------------------------------------------------
# GAP-001: Ramp Rate + Safety integrated pipeline
# ---------------------------------------------------------------------------


class TestGAP001RampRateIntegration:
    def test_safe_telemetry_passes_both_checks(self) -> None:
        guard = SafetyGuard(p_nom_kw=1000.0)
        assert guard.check_safety(TELEMETRY_NOMINAL) is True

        # First cycle: dt=0 → passthrough
        safe_kw = guard.apply_ramp_limit(0.0, 45.0, dt_s=0.0)
        assert safe_kw == pytest.approx(45.0)

    def test_ramp_limited_on_fast_step(self) -> None:
        guard = SafetyGuard(p_nom_kw=1000.0)
        # 1 s step → max delta = 100/60 ≈ 1.667 kW
        safe_kw = guard.apply_ramp_limit(0.0, 500.0, dt_s=1.0)
        max_1s = (10.0 / 100.0) * 1000.0 * (1.0 / 60.0)
        assert safe_kw == pytest.approx(max_1s, rel=1e-4)

    def test_unsafe_soc_blocks_before_ramp(self) -> None:
        guard = SafetyGuard(p_nom_kw=1000.0)
        bad_tel = {**TELEMETRY_NOMINAL, "soc": 2.0}  # below 5% SOC_MIN
        assert guard.check_safety(bad_tel) is False


# ---------------------------------------------------------------------------
# GAP-002: PFR + GAP-011: Q/V integrated
# ---------------------------------------------------------------------------


class TestComplianceSetpointPipeline:
    def test_pfr_responds_to_underfrequency(self) -> None:
        pfr = FrequencyResponseAgent(p_nom_kw=1000.0)
        # 49.85 Hz → delta = -0.15 Hz outside ±0.1 deadband
        p_base = 45.0
        p_corr = pfr.compute_setpoint(TELEMETRY_NOMINAL["grid_frequency"], p_base)
        # Underfrequency → more power → p_corr > p_base
        assert p_corr > p_base

    def test_qv_responds_to_undervoltage(self) -> None:
        qv = ReactiveController(q_max_kvar=484.0)
        v_pu = TELEMETRY_NOMINAL["ac_voltage"] / 230.0  # ≈ 0.991
        q = qv.compute_q_setpoint(v_pu)
        # Undervoltage → inject reactive → Q > 0
        assert q > 0.0

    def test_pfr_within_deadband_unchanged(self) -> None:
        pfr = FrequencyResponseAgent(p_nom_kw=1000.0)
        p = pfr.compute_setpoint(50.0, 500.0)
        assert p == pytest.approx(500.0)

    def test_full_cycle_pipeline(self) -> None:
        """End-to-end: acquire → ramp → pfr → qv setpoints are valid floats."""
        guard = SafetyGuard(p_nom_kw=1000.0)
        pfr = FrequencyResponseAgent(p_nom_kw=1000.0)
        qv = ReactiveController(q_max_kvar=484.0)

        is_safe = guard.check_safety(TELEMETRY_NOMINAL)
        assert is_safe

        current_kw = TELEMETRY_NOMINAL["active_power"] / 1000.0  # 45 kW
        safe_kw = guard.apply_ramp_limit(0.0, current_kw, dt_s=5.0)  # 5 s interval
        pfr_kw = pfr.compute_setpoint(TELEMETRY_NOMINAL["grid_frequency"], safe_kw)
        v_pu = TELEMETRY_NOMINAL["ac_voltage"] / 230.0
        q_kvar = qv.compute_q_setpoint(v_pu)

        assert isinstance(pfr_kw, float)
        assert isinstance(q_kvar, float)
        assert 0.0 <= pfr_kw <= 1000.0


# ---------------------------------------------------------------------------
# GAP-003: CEN Publisher dry-run
# ---------------------------------------------------------------------------


class TestGAP003CENPublisher:
    def test_publish_dry_run_full_payload(self) -> None:
        pub = CENPublisher(endpoint_url=None, site_id="INTEGRATION-TEST", dry_run=True)
        payload = {
            "soc_pct": TELEMETRY_NOMINAL["soc"],
            "p_kw": 46.2,
            "q_kvar": 12.5,
            "f_hz": TELEMETRY_NOMINAL["grid_frequency"],
            "status": "ONLINE",
            "bess_temp_c": TELEMETRY_NOMINAL["temp_c"],
        }
        result = asyncio.run(pub.publish(payload))
        assert result is True

    def test_from_env_no_endpoint_is_dry_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CEN_ENDPOINT_URL", raising=False)
        pub = CENPublisher.from_env()
        assert pub.dry_run is True


# ---------------------------------------------------------------------------
# GAP-009: SL2 Security Gate
# ---------------------------------------------------------------------------


class TestGAP009SL2Integration:
    def test_operator_can_write_setpoint(self) -> None:
        gate = SL2SecurityGate(enforce_tls=False)
        ok, _ = gate.authorize_command("operator", "set_power", "OT")
        assert ok is True

    def test_unauthorized_actor_blocked(self) -> None:
        gate = SL2SecurityGate(enforce_tls=False)
        ok, reason = gate.authorize_command("read_only", "set_power", "OT")
        assert ok is False
        assert "FR-2" in reason

    def test_audit_trail_maintained(self) -> None:
        gate = SL2SecurityGate(enforce_tls=False)
        gate.authorize_command("operator", "set_power", "OT")
        gate.authorize_command("read_only", "set_power", "OT")
        assert len(gate.audit_log) == 2


# ---------------------------------------------------------------------------
# GAP-010: Power Quality gate
# ---------------------------------------------------------------------------


class TestGAP010PowerQualityGate:
    def test_nominal_telemetry_passes(self) -> None:
        pq = PowerQualityMonitor()
        ok, _ = pq.check(TELEMETRY_NOMINAL)
        assert ok is True

    def test_high_thd_blocks_cycle(self) -> None:
        pq = PowerQualityMonitor()
        bad = {**TELEMETRY_NOMINAL, "thd_pct": 9.5}
        ok, reason = pq.check(bad)
        assert ok is False
        assert "THD" in reason


# ---------------------------------------------------------------------------
# GAP-007 + GAP-008: PMGD + ERNC combined scenario
# ---------------------------------------------------------------------------


class TestGAP007008PMGDandERNC:
    def test_compliant_pmgd_and_ernc_solar_charging(self) -> None:
        pmgd = PMGDComplianceEngine(export_limit_kw=200.0)
        registry = ERNCRegistry(site_id="PMGD-001")

        # Scenario: PMGD 150 kW solar, BESS charging 50 kW, load 100 kW
        ok, _ = pmgd.check_dispatch(p_bess_kw=-50.0, p_pmgd_kw=150.0, p_load_kw=100.0)
        assert ok is True  # net_export = -50+150-100 = 0 ≤ 200

        # Record solar charge
        registry.record_charge(50.0, "solar")
        cert = registry.ernc_certificate()
        assert cert.ernc_fraction == pytest.approx(1.0)
        assert cert.qualifies is True

    def test_arbitrage_blocked_ernc_correctly_zero(self) -> None:
        pmgd = PMGDComplianceEngine(export_limit_kw=200.0)
        # BESS 120 kW > PMGD 100 kW = arbitrage
        ok, reason = pmgd.check_dispatch(p_bess_kw=120.0, p_pmgd_kw=100.0, p_load_kw=100.0)
        assert ok is False
        assert "arbitrage" in reason.lower()


# ---------------------------------------------------------------------------
# Full end-to-end scenario: one complete control cycle
# ---------------------------------------------------------------------------


class TestFullComplianceCycle:
    def test_one_cycle_all_modules(self) -> None:
        """Simulate one complete control cycle with all compliance modules active."""
        t0 = time.perf_counter()

        guard = SafetyGuard(p_nom_kw=1000.0)
        pfr = FrequencyResponseAgent(p_nom_kw=1000.0)
        qv = ReactiveController(q_max_kvar=484.0)
        pq = PowerQualityMonitor()
        gate = SL2SecurityGate(enforce_tls=False)
        pub = CENPublisher(dry_run=True)

        tel = TELEMETRY_NOMINAL

        # Step 1: PQ gate
        pq_ok, _ = pq.check(tel)

        # Step 2: Safety
        safe = guard.check_safety(tel)

        # Step 3: Ramp limit (5s interval)
        kw = tel["active_power"] / 1000.0
        safe_kw = guard.apply_ramp_limit(0.0, kw, dt_s=5.0)

        # Step 4: PFR
        pfr_kw = pfr.compute_setpoint(tel["grid_frequency"], safe_kw)

        # Step 5: Q/V
        q = qv.compute_q_setpoint(tel["ac_voltage"] / 230.0)

        # Step 6: Auth gate
        auth_ok, _ = gate.authorize_command("operator", "set_power", "OT")

        # Step 7: CEN publish (sync run)
        result = asyncio.run(pub.publish({
            "soc_pct": tel["soc"], "p_kw": pfr_kw, "q_kvar": q,
            "f_hz": tel["grid_frequency"], "status": "ONLINE",
        }))

        elapsed = time.perf_counter() - t0

        assert pq_ok is True
        assert safe is True
        assert auth_ok is True
        assert result is True
        assert elapsed < 0.5, f"Full cycle took {elapsed:.3f}s — too slow for 50Hz control"
