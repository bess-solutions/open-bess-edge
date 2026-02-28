# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/servicios_complementarios.py
=======================================
Servicios Complementarios BESS — Resolución CEN 2024.

Eligibility check and offer calculation for BESS participation in the
Chilean Ancillary Services market (Servicios Complementarios — SC).

NOTE ON PRICING
---------------
Ancillary service prices are CEN-published indicative reference values
(public, in CEN market documentation). They are loaded from environment
variables to allow operator-specific tuning and avoid hardcoding
commercial strategy in the open-source codebase.

  SC_PFR_PRICE_USD_MWH   (default: 1.5)  PFR regulation price
  SC_R2_PRICE_USD_MWH    (default: 2.0)  R2 AGC price
  SC_R3_PRICE_USD_MWH    (default: 2.5)  R3 reserve price
  SC_QV_PRICE_USD_MWH    (default: 0.8)  Q/V reactive price

Usage::

    sc = ServiciosComplementarios.from_env()
    eligibility = sc.check_eligibility(soc=65.0, p_available_kw=800.0)
    if eligibility.eligible:
        offer = sc.compute_offer(soc=65.0, p_available_kw=800.0)
        revenue = sc.estimate_monthly_revenue(offer)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# Minimum requirements for SC eligibility (CEN 2024)
_MIN_CAPACITY_FOR_PFR_MW: float = 0.1   # 100 kW
_MIN_SOC_FOR_SC_PCT: float = 15.0


def _price(env_var: str, default: float) -> float:
    """Load pricing from env var — never hardcode commercial strategy."""
    return float(os.getenv(env_var, str(default)))


@dataclass
class SCEligibility:
    eligible: bool
    pfr_eligible: bool
    r2_eligible: bool
    r3_eligible: bool
    qv_eligible: bool
    reasons: list[str]
    available_capacity_kw: float


@dataclass
class SCOffer:
    pfr_offer_kw: float
    r2_offer_kw: float
    r3_offer_kw: float
    qv_offer_kvar: float
    total_sc_mw: float


@dataclass
class SCRevenueEstimate:
    pfr_usd: float
    r2_usd: float
    r3_usd: float
    qv_usd: float
    total_monthly_usd: float
    total_annual_usd: float


class ServiciosComplementarios:
    """
    CEN Ancillary Services eligibility and offer calculator.

    All pricing loaded from environment variables — see module docstring.
    """

    def __init__(
        self,
        p_nom_kw: float = 1000.0,
        q_max_kvar: float = 484.0,
        soc_min_sc: float = _MIN_SOC_FOR_SC_PCT,
        pfr_fraction: float = 0.2,
        r3_fraction: float = 0.3,
    ) -> None:
        self._p_nom_kw = p_nom_kw
        self._q_max_kvar = q_max_kvar
        self._soc_min = soc_min_sc
        self._pfr_frac = pfr_fraction
        self._r3_frac = r3_fraction

        # Pricing — from environment, never hardcoded
        self._pfr_price = _price("SC_PFR_PRICE_USD_MWH", 1.5)
        self._r2_price  = _price("SC_R2_PRICE_USD_MWH",  2.0)
        self._r3_price  = _price("SC_R3_PRICE_USD_MWH",  2.5)
        self._qv_price  = _price("SC_QV_PRICE_USD_MWH",  0.8)

        log.info(
            "sc.initialized",
            p_nom_kw=p_nom_kw, q_max_kvar=q_max_kvar,
            norm_ref="CEN Res. 2024 — Servicios Complementarios",
        )

    @classmethod
    def from_env(cls) -> "ServiciosComplementarios":
        return cls(
            p_nom_kw=float(os.getenv("BESSAI_P_NOM_KW", "1000.0")),
            q_max_kvar=float(os.getenv("BESSAI_Q_MAX_KVAR", "484.0")),
            soc_min_sc=float(os.getenv("SC_SOC_MIN_PCT", "15.0")),
            pfr_fraction=float(os.getenv("SC_PFR_FRACTION", "0.2")),
            r3_fraction=float(os.getenv("SC_R3_FRACTION", "0.3")),
        )

    def check_eligibility(self, soc: float, p_available_kw: float) -> SCEligibility:
        reasons: list[str] = []
        pfr_ok = r2_ok = r3_ok = True
        qv_ok = self._q_max_kvar > 0

        if soc < self._soc_min:
            pfr_ok = r2_ok = r3_ok = False
            reasons.append(f"SOC {soc:.1f}% < minimum {self._soc_min:.1f}%")

        if p_available_kw < _MIN_CAPACITY_FOR_PFR_MW * 1000:
            pfr_ok = False
            reasons.append(f"Power {p_available_kw:.0f} kW < PFR minimum 100 kW")

        eligible = pfr_ok or r2_ok or r3_ok or qv_ok
        log.info("sc.eligibility", eligible=eligible, soc=soc, p_kw=p_available_kw,
                 pfr=pfr_ok, r2=r2_ok, r3=r3_ok, qv=qv_ok, norm_ref="CEN Res. 2024")
        return SCEligibility(eligible=eligible, pfr_eligible=pfr_ok,
                             r2_eligible=r2_ok, r3_eligible=r3_ok,
                             qv_eligible=qv_ok, reasons=reasons,
                             available_capacity_kw=p_available_kw)

    def compute_offer(self, soc: float, p_available_kw: float) -> SCOffer:
        elig = self.check_eligibility(soc, p_available_kw)
        if not elig.eligible:
            return SCOffer(0, 0, 0, 0, 0)

        pfr_kw = p_available_kw * self._pfr_frac if elig.pfr_eligible else 0.0
        r3_kw  = p_available_kw * self._r3_frac  if elig.r3_eligible  else 0.0
        r2_kw  = max(0.0, p_available_kw - pfr_kw - r3_kw) if elig.r2_eligible else 0.0
        qv_kvar = self._q_max_kvar if elig.qv_eligible else 0.0
        total_mw = (pfr_kw + r2_kw + r3_kw) / 1000.0

        log.info("sc.offer", pfr_kw=pfr_kw, r2_kw=r2_kw, r3_kw=r3_kw,
                 qv_kvar=qv_kvar, total_mw=round(total_mw, 3))
        return SCOffer(pfr_offer_kw=pfr_kw, r2_offer_kw=r2_kw,
                       r3_offer_kw=r3_kw, qv_offer_kvar=qv_kvar, total_sc_mw=total_mw)

    def estimate_monthly_revenue(self, offer: SCOffer) -> SCRevenueEstimate:
        hours = 730.0
        pfr = (offer.pfr_offer_kw / 1000) * self._pfr_price * hours
        r2  = (offer.r2_offer_kw  / 1000) * self._r2_price  * hours
        r3  = (offer.r3_offer_kw  / 1000) * self._r3_price  * hours
        qv  = (offer.qv_offer_kvar / 1000) * self._qv_price * hours
        total = pfr + r2 + r3 + qv

        log.info("sc.revenue", pfr=round(pfr, 0), r2=round(r2, 0),
                 r3=round(r3, 0), qv=round(qv, 0), monthly=round(total, 0))
        return SCRevenueEstimate(pfr_usd=round(pfr, 2), r2_usd=round(r2, 2),
                                  r3_usd=round(r3, 2), qv_usd=round(qv, 2),
                                  total_monthly_usd=round(total, 2),
                                  total_annual_usd=round(total * 12, 2))
