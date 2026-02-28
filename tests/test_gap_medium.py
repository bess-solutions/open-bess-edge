# SPDX-License-Identifier: Apache-2.0
"""tests/test_gap_medium.py — Tests unitarios para GAP-005..011 (síncronos)."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# GAP-010: Power Quality Monitor
# ---------------------------------------------------------------------------
from src.core.power_quality import PowerQualityMonitor


class TestPowerQualityMonitor:
    @pytest.fixture()
    def pq(self) -> PowerQualityMonitor:
        return PowerQualityMonitor()

    def test_nominal_passes(self, pq: PowerQualityMonitor) -> None:
        ok, _ = pq.check({"thd_pct": 3.0, "pst": 0.5, "plt": 0.6})
        assert ok is True

    def test_empty_telemetry_passes(self, pq: PowerQualityMonitor) -> None:
        ok, _ = pq.check({})
        assert ok is True

    def test_thd_at_limit_passes(self, pq: PowerQualityMonitor) -> None:
        ok, _ = pq.check({"thd_pct": 8.0})
        assert ok is True

    def test_thd_over_limit_blocks(self, pq: PowerQualityMonitor) -> None:
        ok, reason = pq.check({"thd_pct": 9.0})
        assert ok is False
        assert "THD" in reason

    def test_pst_over_limit_blocks(self, pq: PowerQualityMonitor) -> None:
        ok, reason = pq.check({"pst": 1.1})
        assert ok is False
        assert "Pst" in reason

    def test_plt_over_limit_blocks(self, pq: PowerQualityMonitor) -> None:
        ok, reason = pq.check({"plt": 0.9})
        assert ok is False
        assert "Plt" in reason

    def test_headroom_calculation(self, pq: PowerQualityMonitor) -> None:
        assert pq.compute_thd_headroom(3.0) == pytest.approx(5.0)
        assert pq.compute_thd_headroom(9.0) == pytest.approx(0.0)  # floored

    def test_transmission_limit_override(self) -> None:
        pq5 = PowerQualityMonitor(thd_limit_pct=5.0)
        ok, _ = pq5.check({"thd_pct": 6.0})
        assert ok is False


# ---------------------------------------------------------------------------
# GAP-011: Reactive Power Controller
# ---------------------------------------------------------------------------
from src.core.reactive_power import ReactiveController


class TestReactiveController:
    @pytest.fixture()
    def qv(self) -> ReactiveController:
        return ReactiveController(q_max_kvar=484.0, p_nom_kw=1000.0)

    def test_nominal_voltage_zero_q(self, qv: ReactiveController) -> None:
        q = qv.compute_q_setpoint(1.0)
        assert q == pytest.approx(0.0)

    def test_deadband_upper_zero_q(self, qv: ReactiveController) -> None:
        q = qv.compute_q_setpoint(1.01)
        assert q == pytest.approx(0.0)

    def test_deadband_lower_zero_q(self, qv: ReactiveController) -> None:
        q = qv.compute_q_setpoint(0.99)
        assert q == pytest.approx(0.0)

    def test_undervoltage_injects_positive_q(self, qv: ReactiveController) -> None:
        q = qv.compute_q_setpoint(0.95)
        assert q > 0.0

    def test_overvoltage_absorbs_negative_q(self, qv: ReactiveController) -> None:
        q = qv.compute_q_setpoint(1.05)
        assert q < 0.0

    def test_severe_undervoltage_clamped_to_qmax(self, qv: ReactiveController) -> None:
        q = qv.compute_q_setpoint(0.50)
        assert q == pytest.approx(484.0)

    def test_q_max_property(self, qv: ReactiveController) -> None:
        assert qv.q_max_kvar == pytest.approx(484.0)

    def test_power_factor_capability(self, qv: ReactiveController) -> None:
        # pf = P / sqrt(P²+Q²) = 1000/sqrt(1000²+484²)
        import math
        expected = 1000.0 / math.sqrt(1000**2 + 484**2)
        assert qv.power_factor_capability == pytest.approx(expected, rel=1e-4)

    def test_zero_q_max_raises(self) -> None:
        with pytest.raises(ValueError, match="q_max_kvar"):
            ReactiveController(q_max_kvar=0.0)


# ---------------------------------------------------------------------------
# GAP-007: PMGD Compliance
# ---------------------------------------------------------------------------
from src.core.pmgd_compliance import PMGDComplianceEngine


class TestPMGDCompliance:
    @pytest.fixture()
    def pmgd(self) -> PMGDComplianceEngine:
        return PMGDComplianceEngine(export_limit_kw=200.0)

    def test_nominal_dispatch_compliant(self, pmgd: PMGDComplianceEngine) -> None:
        ok, _ = pmgd.check_dispatch(p_bess_kw=50.0, p_pmgd_kw=200.0, p_load_kw=100.0)
        assert ok is True

    def test_export_ceiling_exceeded(self, pmgd: PMGDComplianceEngine) -> None:
        ok, reason = pmgd.check_dispatch(p_bess_kw=150.0, p_pmgd_kw=200.0, p_load_kw=50.0)
        assert ok is False
        assert "export" in reason.lower()

    def test_arbitrage_violation(self, pmgd: PMGDComplianceEngine) -> None:
        # BESS 120 kW > PMGD 100 kW → arbitrage; net_export=120+100-100=120 (< 200, so export OK)
        ok, reason = pmgd.check_dispatch(p_bess_kw=120.0, p_pmgd_kw=100.0, p_load_kw=100.0)
        assert ok is False
        assert "arbitrage" in reason.lower()

    def test_bess_charging_always_ok(self, pmgd: PMGDComplianceEngine) -> None:
        ok, _ = pmgd.check_dispatch(p_bess_kw=-100.0, p_pmgd_kw=200.0, p_load_kw=100.0)
        assert ok is True

    def test_export_headroom(self, pmgd: PMGDComplianceEngine) -> None:
        headroom = pmgd.export_headroom_kw(p_bess_kw=50.0, p_pmgd_kw=100.0, p_load_kw=80.0)
        # net_export = 50+100-80 = 70. headroom = 200-70 = 130
        assert headroom == pytest.approx(130.0)

    def test_negative_export_limit_raises(self) -> None:
        with pytest.raises(ValueError):
            PMGDComplianceEngine(export_limit_kw=-1.0)


# ---------------------------------------------------------------------------
# GAP-008: ERNC Registry
# ---------------------------------------------------------------------------
from src.core.ernc_registry import ERNCRegistry


class TestERNCRegistry:
    @pytest.fixture()
    def registry(self) -> ERNCRegistry:
        return ERNCRegistry(site_id="SITE-001")

    def test_initial_fraction_zero(self, registry: ERNCRegistry) -> None:
        assert registry.ernc_fraction() == pytest.approx(0.0)

    def test_solar_charge_qualifies(self, registry: ERNCRegistry) -> None:
        registry.record_charge(100.0, "solar")
        assert registry.ernc_fraction() == pytest.approx(1.0)

    def test_grid_charge_does_not_qualify(self, registry: ERNCRegistry) -> None:
        registry.record_charge(100.0, "grid")
        assert registry.ernc_fraction() == pytest.approx(0.0)

    def test_mixed_charge_fraction(self, registry: ERNCRegistry) -> None:
        registry.record_charge(80.0, "solar")
        registry.record_charge(20.0, "grid")
        assert registry.ernc_fraction() == pytest.approx(0.8)

    def test_certificate_qualifies_at_99pct(self, registry: ERNCRegistry) -> None:
        registry.record_charge(99.0, "wind")
        registry.record_charge(1.0, "grid")
        cert = registry.ernc_certificate()
        # 99.0% meets the 99.0% threshold (>=) → qualifies
        assert cert.qualifies is True
        assert cert.ernc_fraction == pytest.approx(0.99)

    def test_certificate_qualifies_100pct(self, registry: ERNCRegistry) -> None:
        registry.record_charge(100.0, "solar")
        cert = registry.ernc_certificate()
        assert cert.qualifies is True
        assert cert.site_id == "SITE-001"

    def test_reset_clears_counters(self, registry: ERNCRegistry) -> None:
        registry.record_charge(50.0, "solar")
        registry.reset_period()
        assert registry.ernc_fraction() == pytest.approx(0.0)

    def test_negative_energy_raises(self, registry: ERNCRegistry) -> None:
        with pytest.raises(ValueError):
            registry.record_charge(-10.0, "solar")

    def test_all_ernc_sources(self, registry: ERNCRegistry) -> None:
        for src in ("solar", "wind", "hydro", "geothermal", "biomass", "tidal"):
            r = ERNCRegistry("X")
            r.record_charge(1.0, src)
            assert r.ernc_fraction() == pytest.approx(1.0), f"{src} should be ERNC"


# ---------------------------------------------------------------------------
# GAP-009: IEC 62443 SL-2 Security Gate
# ---------------------------------------------------------------------------
from src.core.iec62443 import SL2SecurityGate


class TestSL2SecurityGate:
    @pytest.fixture()
    def gate(self) -> SL2SecurityGate:
        return SL2SecurityGate(enforce_tls=False)  # TLS off for unit tests

    def test_operator_can_set_power(self, gate: SL2SecurityGate) -> None:
        ok, _ = gate.authorize_command("operator", "set_power", "OT")
        assert ok is True

    def test_read_only_cannot_set_power(self, gate: SL2SecurityGate) -> None:
        ok, reason = gate.authorize_command("read_only", "set_power", "OT")
        assert ok is False
        assert "FR-2" in reason

    def test_admin_can_do_anything(self, gate: SL2SecurityGate) -> None:
        ok, _ = gate.authorize_command("admin", "delete_all_logs", "OT")
        assert ok is True

    def test_unknown_zone_denied(self, gate: SL2SecurityGate) -> None:
        ok, reason = gate.authorize_command("operator", "set_power", "INTERNET")
        assert ok is False
        assert "FR-5" in reason

    def test_tls_enforced(self) -> None:
        gate_tls = SL2SecurityGate(enforce_tls=True)
        ok, reason = gate_tls.authorize_command(
            "operator", "set_power", "OT", tls_active=False
        )
        assert ok is False
        assert "FR-4" in reason

    def test_tls_ok_passes(self) -> None:
        gate_tls = SL2SecurityGate(enforce_tls=True)
        ok, _ = gate_tls.authorize_command(
            "operator", "set_power", "OT", tls_active=True
        )
        assert ok is True

    def test_hmac_sign_and_verify(self) -> None:
        gate_hmac = SL2SecurityGate(hmac_secret=b"secret123", enforce_tls=False)
        payload = b'{"cmd":"set_power","value":500}'
        sig = gate_hmac.sign_payload(payload)
        ok, _ = gate_hmac.authorize_command(
            "operator", "set_power", "OT",
            payload=payload, payload_hmac=sig,
        )
        assert ok is True

    def test_hmac_tampered_payload_denied(self) -> None:
        gate_hmac = SL2SecurityGate(hmac_secret=b"secret123", enforce_tls=False)
        payload = b'{"cmd":"set_power","value":500}'
        ok, reason = gate_hmac.authorize_command(
            "operator", "set_power", "OT",
            payload=payload, payload_hmac="deadbeef",
        )
        assert ok is False
        assert "HMAC" in reason

    def test_audit_log_populated(self, gate: SL2SecurityGate) -> None:
        gate.authorize_command("operator", "set_power", "OT")
        gate.authorize_command("read_only", "set_power", "OT")
        log = gate.audit_log
        assert len(log) == 2
        assert log[0].allowed is True
        assert log[1].allowed is False

    def test_rate_limit_enforced(self) -> None:
        """Admin is capped at 30 commands/min — exceed it."""
        gate_rl = SL2SecurityGate(enforce_tls=False)
        results = []
        for _ in range(35):
            ok, _ = gate_rl.authorize_command("admin", "set_power", "OT")
            results.append(ok)
        # First 30 should pass, remaining should fail
        assert all(results[:30])
        assert not all(results[30:])
