# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/servicios_complementarios.py
=======================================
Servicios Complementarios BESS — Resolución CEN 2024.

Implements the eligibility check and offer calculation for a BESS to
participate in the Chilean Ancillary Services market (Servicios
Complementarios — SC), as regulated by the Coordinador Eléctrico Nacional
(CEN) 2024 Resolution.

Ancillary services monetized via this module
---------------------------------------------
SC-01  Regulación Primaria de Frecuencia (PFR)   — already implemented GAP-002
SC-02  Regulación Secundaria (AGC / R2)           — response in 30s window
SC-03  Reserva Terciaria (R3)                     — 15-min available capacity
SC-04  Tensión / Potencia Reactiva                — already implemented GAP-011
SC-05  Control de Arranque Negro (Black Start)    — stub, rare for BESS

Revenue model (CEN 2024)
------------------------
* Payment = availability_price × available_capacity + activation_price × activated_energy
* PFR payment: ~USD 0.5–2.5 / MW-h of regulation capacity offered
* R3 payment: ~USD 1.0–4.0 / MW-h of reserve capacity

Usage::

    sc = ServiciosComplementarios(p_nom_kw=1000.0, soc_min_sc=20.0)
    eligibility = sc.check_eligibility(soc=65.0, p_available_kw=800.0)
    if eligibility.eligible:
        offer = sc.compute_offer(soc=65.0, p_available_kw=800.0)
        revenue_est = sc.estimate_monthly_revenue(offer)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

# CEN 2024 indicative prices (USD/MW-h of capacity)
_PFR_PRICE_USD_MW_H: float = 1.5
_R2_PRICE_USD_MW_H: float = 2.0
_R3_PRICE_USD_MW_H: float = 2.5
_QV_PRICE_USD_MW_H: float = 0.8

# Minimum requirements for SC eligibility (CEN 2024)
_MIN_CAPACITY_FOR_PFR_MW: float = 0.1   # 100 kW
_MIN_SOC_FOR_SC_PCT: float = 15.0       # must have sufficient energy buffer
_MIN_RESPONSE_TIME_S: float = 2.0       # PFR must respond in ≤ 2s


@dataclass
class SCEligibility:
    """Result of ancillary service eligibility check."""
    eligible: bool
    pfr_eligible: bool
    r2_eligible: bool
    r3_eligible: bool
    qv_eligible: bool
    reasons: list[str]
    available_capacity_kw: float


@dataclass
class SCOffer:
    """Computed offer for CEN ancillary services."""
    pfr_offer_kw: float       # PFR regulation capacity offered (kW)
    r2_offer_kw: float        # AGC capacity offered (kW)
    r3_offer_kw: float        # Reserve capacity offered (kW)
    qv_offer_kvar: float      # Reactive capacity offered (kVAr)
    total_sc_mw: float        # Total ancillary service capacity (MW)


@dataclass
class SCRevenueEstimate:
    """Monthly revenue estimate from ancillary services."""
    pfr_usd: float
    r2_usd: float
    r3_usd: float
    qv_usd: float
    total_monthly_usd: float
    total_annual_usd: float


class ServiciosComplementarios:
    """
    CEN Ancillary Services eligibility and offer calculator.

    Parameters
    ----------
    p_nom_kw        Nominal BESS power (kW).
    q_max_kvar      Reactive power capacity (kVAr).
    soc_min_sc      Minimum SOC to offer SC (%). Default 15%.
    pfr_fraction    Fraction of capacity reserved for PFR. Default 0.2.
    r3_fraction     Fraction of capacity for R3 reserve. Default 0.3.
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

    def check_eligibility(
        self,
        soc: float,
        p_available_kw: float,
    ) -> SCEligibility:
        """
        Verify if the BESS currently meets CEN eligibility for SC markets.

        Parameters
        ----------
        soc             Current state of charge (%).
        p_available_kw  Currently available power capacity (kW).
        """
        reasons: list[str] = []
        pfr_ok = True
        r2_ok = True
        r3_ok = True
        qv_ok = self._q_max_kvar > 0

        if soc < self._soc_min:
            pfr_ok = r2_ok = r3_ok = False
            reasons.append(f"SOC {soc:.1f}% < SC minimum {self._soc_min:.1f}%")

        if p_available_kw < _MIN_CAPACITY_FOR_PFR_MW * 1000:
            pfr_ok = False
            reasons.append(f"Available power {p_available_kw:.0f} kW < PFR minimum 100 kW")

        eligible = pfr_ok or r2_ok or r3_ok or qv_ok

        log.info(
            "sc.eligibility",
            eligible=eligible, soc=soc, p_kw=p_available_kw,
            pfr=pfr_ok, r2=r2_ok, r3=r3_ok, qv=qv_ok,
            norm_ref="CEN Res. 2024",
        )

        return SCEligibility(
            eligible=eligible,
            pfr_eligible=pfr_ok,
            r2_eligible=r2_ok,
            r3_eligible=r3_ok,
            qv_eligible=qv_ok,
            reasons=reasons,
            available_capacity_kw=p_available_kw,
        )

    def compute_offer(
        self,
        soc: float,
        p_available_kw: float,
    ) -> SCOffer:
        """Compute the optimal SC offer given current state."""
        eligibility = self.check_eligibility(soc, p_available_kw)
        if not eligibility.eligible:
            return SCOffer(0, 0, 0, 0, 0)

        pfr_kw = p_available_kw * self._pfr_frac if eligibility.pfr_eligible else 0.0
        r3_kw = p_available_kw * self._r3_frac if eligibility.r3_eligible else 0.0
        r2_kw = max(0.0, p_available_kw - pfr_kw - r3_kw) if eligibility.r2_eligible else 0.0
        qv_kvar = self._q_max_kvar if eligibility.qv_eligible else 0.0

        total_mw = (pfr_kw + r2_kw + r3_kw) / 1000.0

        log.info(
            "sc.offer_computed",
            pfr_kw=pfr_kw, r2_kw=r2_kw, r3_kw=r3_kw,
            qv_kvar=qv_kvar, total_mw=round(total_mw, 3),
        )

        return SCOffer(
            pfr_offer_kw=pfr_kw,
            r2_offer_kw=r2_kw,
            r3_offer_kw=r3_kw,
            qv_offer_kvar=qv_kvar,
            total_sc_mw=total_mw,
        )

    def estimate_monthly_revenue(self, offer: SCOffer) -> SCRevenueEstimate:
        """
        Estimate monthly revenue from SC market participation.

        Uses CEN 2024 indicative availability prices (USD/MW-h).
        Hours per month: 730 h
        """
        hours = 730.0
        pfr_usd = (offer.pfr_offer_kw / 1000) * _PFR_PRICE_USD_MW_H * hours
        r2_usd = (offer.r2_offer_kw / 1000) * _R2_PRICE_USD_MW_H * hours
        r3_usd = (offer.r3_offer_kw / 1000) * _R3_PRICE_USD_MW_H * hours
        qv_usd = (offer.qv_offer_kvar / 1000) * _QV_PRICE_USD_MW_H * hours
        total = pfr_usd + r2_usd + r3_usd + qv_usd

        log.info(
            "sc.revenue_estimate",
            pfr_usd=round(pfr_usd, 0),
            r2_usd=round(r2_usd, 0),
            r3_usd=round(r3_usd, 0),
            qv_usd=round(qv_usd, 0),
            total_monthly_usd=round(total, 0),
            total_annual_usd=round(total * 12, 0),
        )

        return SCRevenueEstimate(
            pfr_usd=round(pfr_usd, 2),
            r2_usd=round(r2_usd, 2),
            r3_usd=round(r3_usd, 2),
            qv_usd=round(qv_usd, 2),
            total_monthly_usd=round(total, 2),
            total_annual_usd=round(total * 12, 2),
        )
