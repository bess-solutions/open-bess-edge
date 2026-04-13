# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_servicios_complementarios.py
========================================
Unit tests for ``src.core.servicios_complementarios``.

Covers:
  - SCEligibility: SOC gate, capacity gate, full combination
  - SCOffer: per-service power allocation and totals
  - SCRevenueEstimate: monthly / annual revenue calculations
  - ServiciosComplementarios.from_env(): env-var override
  - Edge cases: zero power, at-limit SOC, ineligible offer → all zeros
"""

from __future__ import annotations

import os

import pytest
from src.core.servicios_complementarios import (
    SCOffer,
    ServiciosComplementarios,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sc() -> ServiciosComplementarios:
    """Default SC instance — 1 MW nameplate, default fractions."""
    return ServiciosComplementarios(p_nom_kw=1000.0)


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

class TestEligibility:
    def test_fully_eligible(self, sc: ServiciosComplementarios):
        elig = sc.check_eligibility(soc=65.0, p_available_kw=800.0)
        assert elig.eligible is True
        assert elig.pfr_eligible is True
        assert elig.r2_eligible is True
        assert elig.r3_eligible is True
        assert elig.qv_eligible is True
        assert elig.reasons == []

    def test_low_soc_disables_pfr_r2_r3(self, sc: ServiciosComplementarios):
        elig = sc.check_eligibility(soc=10.0, p_available_kw=800.0)
        assert elig.pfr_eligible is False
        assert elig.r2_eligible is False
        assert elig.r3_eligible is False
        # QV is reactive power — not SOC-gated (depends on q_max_kvar only)
        assert elig.qv_eligible is True
        # Still overall eligible because QV is ok
        assert elig.eligible is True
        assert len(elig.reasons) >= 1

    def test_soc_at_threshold_is_eligible(self, sc: ServiciosComplementarios):
        """SOC = exactly soc_min should pass."""
        elig = sc.check_eligibility(soc=15.0, p_available_kw=800.0)
        assert elig.pfr_eligible is True

    def test_zero_power_disables_pfr(self, sc: ServiciosComplementarios):
        elig = sc.check_eligibility(soc=65.0, p_available_kw=0.0)
        assert elig.pfr_eligible is False
        # At least QV might still be eligible
        assert not elig.pfr_eligible

    def test_below_100kw_disables_pfr(self, sc: ServiciosComplementarios):
        elig = sc.check_eligibility(soc=65.0, p_available_kw=99.0)
        assert elig.pfr_eligible is False
        assert "100 kW" in " ".join(elig.reasons)

    def test_exactly_100kw_pfr_eligible(self, sc: ServiciosComplementarios):
        elig = sc.check_eligibility(soc=65.0, p_available_kw=100.0)
        assert elig.pfr_eligible is True

    def test_zero_q_max_disables_qv(self):
        sc = ServiciosComplementarios(p_nom_kw=1000.0, q_max_kvar=0.0)
        elig = sc.check_eligibility(soc=65.0, p_available_kw=800.0)
        assert elig.qv_eligible is False

    def test_available_capacity_reflected(self, sc: ServiciosComplementarios):
        elig = sc.check_eligibility(soc=70.0, p_available_kw=500.0)
        assert elig.available_capacity_kw == pytest.approx(500.0)

    def test_both_gates_fail_ineligible(self, sc: ServiciosComplementarios):
        """Low SOC + zero power + zero q_max → fully ineligible."""
        sc2 = ServiciosComplementarios(p_nom_kw=1000.0, q_max_kvar=0.0)
        elig = sc2.check_eligibility(soc=5.0, p_available_kw=0.0)
        assert elig.eligible is False


# ---------------------------------------------------------------------------
# Offer calculation
# ---------------------------------------------------------------------------

class TestOffer:
    def test_ineligible_offer_is_all_zeros(self):
        sc = ServiciosComplementarios(p_nom_kw=1000.0, q_max_kvar=0.0)
        offer = sc.compute_offer(soc=5.0, p_available_kw=0.0)
        assert offer.pfr_offer_kw == pytest.approx(0.0)
        assert offer.r2_offer_kw == pytest.approx(0.0)
        assert offer.r3_offer_kw == pytest.approx(0.0)
        assert offer.qv_offer_kvar == pytest.approx(0.0)
        assert offer.total_sc_mw == pytest.approx(0.0)

    def test_pfr_fraction(self, sc: ServiciosComplementarios):
        offer = sc.compute_offer(soc=65.0, p_available_kw=1000.0)
        # pfr_fraction=0.2 → 200 kW
        assert offer.pfr_offer_kw == pytest.approx(200.0)

    def test_r3_fraction(self, sc: ServiciosComplementarios):
        offer = sc.compute_offer(soc=65.0, p_available_kw=1000.0)
        # r3_fraction=0.3 → 300 kW
        assert offer.r3_offer_kw == pytest.approx(300.0)

    def test_r2_gets_remainder(self, sc: ServiciosComplementarios):
        offer = sc.compute_offer(soc=65.0, p_available_kw=1000.0)
        # r2 = 1000 - 200(pfr) - 300(r3) = 500 kW
        assert offer.r2_offer_kw == pytest.approx(500.0)

    def test_total_mw_correct(self, sc: ServiciosComplementarios):
        offer = sc.compute_offer(soc=65.0, p_available_kw=1000.0)
        expected_mw = (200.0 + 500.0 + 300.0) / 1000.0
        assert offer.total_sc_mw == pytest.approx(expected_mw)

    def test_qv_offer_uses_q_max(self):
        sc = ServiciosComplementarios(p_nom_kw=1000.0, q_max_kvar=484.0)
        offer = sc.compute_offer(soc=65.0, p_available_kw=800.0)
        assert offer.qv_offer_kvar == pytest.approx(484.0)

    def test_custom_fractions(self):
        sc = ServiciosComplementarios(
            p_nom_kw=2000.0,
            pfr_fraction=0.1,
            r3_fraction=0.4,
        )
        offer = sc.compute_offer(soc=65.0, p_available_kw=2000.0)
        assert offer.pfr_offer_kw == pytest.approx(200.0)   # 0.1 × 2000
        assert offer.r3_offer_kw == pytest.approx(800.0)    # 0.4 × 2000


# ---------------------------------------------------------------------------
# Revenue estimation
# ---------------------------------------------------------------------------

class TestRevenue:
    def test_zero_offer_zero_revenue(self, sc: ServiciosComplementarios):
        zero_offer = SCOffer(0, 0, 0, 0, 0)
        rev = sc.estimate_monthly_revenue(zero_offer)
        assert rev.total_monthly_usd == pytest.approx(0.0)
        assert rev.total_annual_usd == pytest.approx(0.0)

    def test_annual_is_12x_monthly(self, sc: ServiciosComplementarios):
        offer = sc.compute_offer(soc=65.0, p_available_kw=1000.0)
        rev = sc.estimate_monthly_revenue(offer)
        assert rev.total_annual_usd == pytest.approx(rev.total_monthly_usd * 12, rel=1e-3)

    def test_revenue_components_sum_to_total(self, sc: ServiciosComplementarios):
        offer = sc.compute_offer(soc=65.0, p_available_kw=1000.0)
        rev = sc.estimate_monthly_revenue(offer)
        component_sum = rev.pfr_usd + rev.r2_usd + rev.r3_usd + rev.qv_usd
        assert rev.total_monthly_usd == pytest.approx(component_sum, rel=1e-3)

    def test_positive_revenue_for_eligible_bess(self, sc: ServiciosComplementarios):
        offer = sc.compute_offer(soc=65.0, p_available_kw=1000.0)
        rev = sc.estimate_monthly_revenue(offer)
        assert rev.total_monthly_usd > 0
        assert rev.total_annual_usd > 0

    def test_revenue_scales_with_capacity(self):
        """2 MW BESS should generate roughly 2× revenue of 1 MW BESS for
        capacity-dependent services (PFR, R2, R3). QV uses a fixed q_max_kvar
        so we isolate to capacity-dependent revenue by disabling QV (q_max=0)."""
        sc1 = ServiciosComplementarios(p_nom_kw=1000.0, q_max_kvar=0.0)
        sc2 = ServiciosComplementarios(p_nom_kw=2000.0, q_max_kvar=0.0)
        offer1 = sc1.compute_offer(65.0, 1000.0)
        offer2 = sc2.compute_offer(65.0, 2000.0)
        rev1 = sc1.estimate_monthly_revenue(offer1)
        rev2 = sc2.estimate_monthly_revenue(offer2)
        # Without QV, PFR+R2+R3 scale exactly 2× with 2× capacity
        assert rev2.total_monthly_usd == pytest.approx(rev1.total_monthly_usd * 2, rel=0.01)


# ---------------------------------------------------------------------------
# from_env() classmethod
# ---------------------------------------------------------------------------

class TestFromEnv:
    def test_from_env_defaults(self):
        for key in ["BESSAI_P_NOM_KW", "BESSAI_Q_MAX_KVAR", "SC_SOC_MIN_PCT",
                    "SC_PFR_FRACTION", "SC_R3_FRACTION"]:
            os.environ.pop(key, None)
        sc = ServiciosComplementarios.from_env()
        assert sc._p_nom_kw == pytest.approx(1000.0)
        assert sc._q_max_kvar == pytest.approx(484.0)

    def test_from_env_overrides(self):
        os.environ["BESSAI_P_NOM_KW"] = "5000.0"
        os.environ["SC_PFR_FRACTION"] = "0.15"
        try:
            sc = ServiciosComplementarios.from_env()
            assert sc._p_nom_kw == pytest.approx(5000.0)
            assert sc._pfr_frac == pytest.approx(0.15)
        finally:
            os.environ.pop("BESSAI_P_NOM_KW", None)
            os.environ.pop("SC_PFR_FRACTION", None)


# ---------------------------------------------------------------------------
# Pricing env-var override
# ---------------------------------------------------------------------------

class TestPricingEnvOverride:
    def test_custom_pfr_price_affects_revenue(self):
        os.environ["SC_PFR_PRICE_USD_MWH"] = "10.0"  # 10× default
        try:
            sc_high = ServiciosComplementarios(p_nom_kw=1000.0)
            offer = sc_high.compute_offer(65.0, 1000.0)
            rev = sc_high.estimate_monthly_revenue(offer)
        finally:
            os.environ.pop("SC_PFR_PRICE_USD_MWH", None)

        sc_default = ServiciosComplementarios(p_nom_kw=1000.0)
        offer_d = sc_default.compute_offer(65.0, 1000.0)
        rev_d = sc_default.estimate_monthly_revenue(offer_d)

        # PFR revenue should be higher for the 10× price instance
        assert rev.pfr_usd > rev_d.pfr_usd
