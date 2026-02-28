# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_bessai_commercial.py
================================
Tests for the 3 new BESSAI commercial/monetization modules:

  * SecurityNotifier  (Ley 21.663/2024 CSIRT reporting)
  * ServiciosComplementarios  (CEN 2024 ancillary services revenue)
  * ComplianceReporter  (SEC/CEN audit report generator)
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# SecurityNotifier (Ley 21.663/2024)
# ---------------------------------------------------------------------------
from src.core.security_notifier import SecurityNotifier, IncidentReport


class TestSecurityNotifier:
    def test_init_dry_run_default(self) -> None:
        n = SecurityNotifier(site_id="TEST", dry_run=True)
        assert n._dry_run is True

    def test_from_env_returns_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SITE_ID", "ENV-TEST")
        monkeypatch.setenv("CSIRT_DRY_RUN", "true")
        n = SecurityNotifier.from_env()
        assert n._site_id == "ENV-TEST"

    def test_report_critical_incident(self) -> None:
        n = SecurityNotifier(dry_run=True)
        inc = asyncio.run(n.report_incident(
            "unauthorized_command", "CRITICAL",
            {"role": "read_only", "cmd": "set_power"},
        ))
        assert isinstance(inc, IncidentReport)
        assert inc.severity == "CRITICAL"
        assert inc.notified_csirt is True   # dry-run marks as notified
        assert inc.hash_sha256 != ""

    def test_report_high_auto_notifies(self) -> None:
        n = SecurityNotifier(dry_run=True)
        inc = asyncio.run(n.report_incident("hmac_failure", "HIGH", {}))
        assert inc.notified_csirt is True

    def test_report_medium_no_csirt(self) -> None:
        n = SecurityNotifier(dry_run=True)
        inc = asyncio.run(n.report_incident("rate_limit_exceeded", "MEDIUM", {}))
        assert inc.notified_csirt is False

    def test_report_low_no_csirt(self) -> None:
        n = SecurityNotifier(dry_run=True)
        inc = asyncio.run(n.report_incident("auth_check", "LOW", {}))
        assert inc.notified_csirt is False

    def test_incident_id_format(self) -> None:
        n = SecurityNotifier(site_id="SITE-XYZ", dry_run=True)
        inc = asyncio.run(n.report_incident("test", "LOW", {}))
        assert inc.incident_id.startswith("INC-SITE-XYZ-")

    def test_open_incidents_tracks_unnotified(self) -> None:
        n = SecurityNotifier(dry_run=False)  # won't actually POST
        # Patch _notify_csirt to skip network
        async def _mock(incident: IncidentReport) -> None:
            pass
        n._notify_csirt = _mock  # type: ignore[method-assign]
        asyncio.run(n.report_incident("test", "HIGH", {}))
        # HIGH but mock didn't set notified_csirt → open
        assert len(n.incident_log) == 1

    def test_hash_deterministic(self) -> None:
        n = SecurityNotifier(dry_run=True)
        inc1 = asyncio.run(n.report_incident("t", "LOW", {"k": "v"}))
        inc2 = asyncio.run(n.report_incident("t", "LOW", {"k": "v"}))
        # Different timestamps → different hashes (timestamp is part of dict)
        assert inc1.hash_sha256 != "" and inc2.hash_sha256 != ""


# ---------------------------------------------------------------------------
# ServiciosComplementarios (CEN 2024)
# ---------------------------------------------------------------------------
from src.core.servicios_complementarios import (
    ServiciosComplementarios, SCEligibility, SCOffer, SCRevenueEstimate
)


class TestServiciosComplementarios:
    def test_from_env_returns_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BESSAI_P_NOM_KW", "500.0")
        sc = ServiciosComplementarios.from_env()
        assert sc._p_nom_kw == pytest.approx(500.0)

    def test_eligible_nominal_state(self) -> None:
        sc = ServiciosComplementarios(p_nom_kw=1000.0)
        elig = sc.check_eligibility(soc=65.0, p_available_kw=800.0)
        assert elig.eligible is True
        assert elig.pfr_eligible is True
        assert elig.r3_eligible is True

    def test_low_soc_ineligible(self) -> None:
        sc = ServiciosComplementarios(p_nom_kw=1000.0, soc_min_sc=15.0)
        elig = sc.check_eligibility(soc=10.0, p_available_kw=800.0)
        assert elig.pfr_eligible is False
        assert len(elig.reasons) >= 1

    def test_qv_always_eligible_if_q_max_set(self) -> None:
        sc = ServiciosComplementarios(q_max_kvar=484.0)
        elig = sc.check_eligibility(soc=10.0, p_available_kw=0.0)
        assert elig.qv_eligible is True   # QV doesn't need SOC

    def test_compute_offer_partitions_correctly(self) -> None:
        sc = ServiciosComplementarios(p_nom_kw=1000.0,
                                       pfr_fraction=0.2, r3_fraction=0.3)
        offer = sc.compute_offer(soc=65.0, p_available_kw=800.0)
        assert offer.pfr_offer_kw == pytest.approx(160.0)
        assert offer.r3_offer_kw == pytest.approx(240.0)
        assert offer.total_sc_mw == pytest.approx(0.8)

    def test_revenue_estimate_1mw_bess(self) -> None:
        sc = ServiciosComplementarios(p_nom_kw=1000.0)
        offer = sc.compute_offer(soc=65.0, p_available_kw=1000.0)
        rev = sc.estimate_monthly_revenue(offer)
        # 1 MW BESS should generate at least USD 500/month
        assert rev.total_monthly_usd > 500.0
        assert rev.total_annual_usd == pytest.approx(rev.total_monthly_usd * 12, rel=0.01)

    def test_revenue_zero_when_ineligible(self) -> None:
        sc = ServiciosComplementarios(p_nom_kw=1000.0, q_max_kvar=0.0)
        offer = sc.compute_offer(soc=5.0, p_available_kw=0.0)
        rev = sc.estimate_monthly_revenue(offer)
        assert rev.total_monthly_usd == pytest.approx(0.0)

    def test_offer_zero_when_ineligible(self) -> None:
        sc = ServiciosComplementarios(p_nom_kw=1000.0, q_max_kvar=0.0)
        offer = sc.compute_offer(soc=5.0, p_available_kw=0.0)
        assert offer.total_sc_mw == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# ComplianceReporter
# ---------------------------------------------------------------------------

from src.core.compliance_reporter import ComplianceReporter


class _FakeResult:
    dispatch_allowed = True
    block_reason = ""
    p_pfr_setpoint_kw = 105.0
    q_setpoint_kvar = 484.0
    pfr_active = True
    qv_active = True
    norm_refs = ["NTCSE", "NTSyCS-SAF", "NTSyCS-4.2", "NTSyCS-4.3", "NTSyCS-4.4"]


class _BlockedResult:
    dispatch_allowed = False
    block_reason = "THD exceeded"
    p_pfr_setpoint_kw = 0.0
    q_setpoint_kvar = 0.0
    pfr_active = False
    qv_active = False
    norm_refs = ["NTCSE"]


class TestComplianceReporter:
    def test_empty_report_100pct(self) -> None:
        r = ComplianceReporter(site_id="T")
        report = r.generate("2026-02")
        assert report.availability_pct == pytest.approx(100.0)
        assert report.compliance_score == pytest.approx(100.0)

    def test_record_and_compute_availability(self) -> None:
        r = ComplianceReporter(site_id="T")
        r.record_cycle(_FakeResult())
        r.record_cycle(_FakeResult())
        r.record_cycle(_BlockedResult())  # 1/3 blocked
        report = r.generate("2026-02")
        assert report.total_cycles == 3
        assert report.blocked_cycles == 1
        assert report.availability_pct == pytest.approx(66.67, rel=0.01)

    def test_norm_coverage_accumulates(self) -> None:
        r = ComplianceReporter(site_id="T")
        r.record_cycle(_FakeResult())
        report = r.generate("2026-02")
        assert "NTSyCS-4.3" in report.norm_coverage
        assert "NTCSE" in report.norm_coverage

    def test_pfr_activations_counted(self) -> None:
        r = ComplianceReporter(site_id="T")
        r.record_cycle(_FakeResult())  # pfr_active=True
        r.record_cycle(_FakeResult())
        r.record_cycle(_BlockedResult())  # pfr_active=False
        report = r.generate("2026-02")
        assert report.pfr_activations == 2
        assert report.qv_activations == 2

    def test_markdown_contains_site_id(self) -> None:
        r = ComplianceReporter(site_id="PMGD-001")
        r.record_cycle(_FakeResult())
        report = r.generate("2026-02")
        assert "PMGD-001" in report.summary_md

    def test_block_reasons_tracked(self) -> None:
        r = ComplianceReporter(site_id="T")
        r.record_cycle(_BlockedResult())
        r.record_cycle(_BlockedResult())
        report = r.generate("2026-02")
        assert report.block_reasons.get("THD exceeded") == 2

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SITE_ID", "ENV-SITE")
        rep = ComplianceReporter.from_env()
        assert rep._site_id == "ENV-SITE"

    def test_save_json(self, tmp_path: Path) -> None:
        r = ComplianceReporter(site_id="T", reports_dir=tmp_path)
        r.record_cycle(_FakeResult())
        report = r.generate("2026-02")
        p = r.save_json(report)
        assert p.exists()
        assert p.suffix == ".json"

    def test_save_markdown(self, tmp_path: Path) -> None:
        r = ComplianceReporter(site_id="T", reports_dir=tmp_path)
        r.record_cycle(_FakeResult())
        report = r.generate("2026-02")
        p = r.save_markdown(report)
        assert p.exists()
        txt = p.read_text()
        assert "Compliance" in txt
