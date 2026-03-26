# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/ancillary_services.py
======================================
BESSAI Edge Gateway — Ancillary Services Revenue Stack Engine v1.0

Maps BESS residual capacity to Chilean SEN ancillary (complementary) services
after energy arbitrage has been scheduled. Services covered:

  CSF  — Capacidad de Suficiencia de Frecuencia (fast frequency response)
  RP   — Reserva Primaria (primary frequency reserve, ±0.2 Hz droop)
  RSS  — Reserva de Seguridad Semanal (weekly security reserve)
  RSB  — Reserva de Seguridad de Banda (spinning reserve)
  AGC  — Control Automático de Generación (secondary frequency)

Usage::

    from src.interfaces.ancillary_services import CapacityAllocator

    allocator = CapacityAllocator(capacity_kwh=1000.0, max_power_kw=500.0)
    stack = allocator.allocate(
        soc_pct=60.0,
        arbitrage_reserved_kw=200.0,   # power slots already committed to arbitrage
    )
    print(stack.summary())
    print(stack.total_revenue_clp_per_hour)

References:
  NTSyCS — CEN Chile normativa de servicios complementarios
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import structlog

__all__ = [
    "AncillaryService",
    "AncillaryServiceCapacity",
    "AncillaryStack",
    "CapacityAllocator",
    "SEN_SERVICES",
]

log = structlog.get_logger(__name__)

# SEN service identifiers
AncillaryService = Literal["CSF", "RP", "RSS", "RSB", "AGC"]

# ─────────────────────────────────────────────────────────────────────────────
# SEN Market defaults (2026 reference prices — USD/MW·h)
# Source: NTSyCS CEN Chile, CND technical reports
# ─────────────────────────────────────────────────────────────────────────────
SEN_SERVICES: dict[str, dict] = {
    "CSF": {
        "label": "Capacidad Suficiencia Frecuencia",
        "min_kw": 10.0,          # minimum BESS power to qualify
        "max_kw_pct": 0.30,      # max fraction of rated power that can go to this service
        "price_usd_mw_h": 4.5,   # USD per MW·h of reserved capacity
        "priority": 1,           # allocation priority (1 = highest)
        "soc_min_pct": 20.0,     # minimum SoC required to commit
        "soc_max_pct": 95.0,
        "response_s": 1,         # response time requirement (seconds)
    },
    "RP": {
        "label": "Reserva Primaria",
        "min_kw": 20.0,
        "max_kw_pct": 0.25,
        "price_usd_mw_h": 3.8,
        "priority": 2,
        "soc_min_pct": 25.0,
        "soc_max_pct": 90.0,
        "response_s": 30,
    },
    "RSS": {
        "label": "Reserva Seguridad Semanal",
        "min_kw": 50.0,
        "max_kw_pct": 0.40,
        "price_usd_mw_h": 2.9,
        "priority": 3,
        "soc_min_pct": 30.0,
        "soc_max_pct": 95.0,
        "response_s": 300,
    },
    "RSB": {
        "label": "Reserva Seguridad de Banda",
        "min_kw": 30.0,
        "max_kw_pct": 0.35,
        "price_usd_mw_h": 2.4,
        "priority": 4,
        "soc_min_pct": 25.0,
        "soc_max_pct": 90.0,
        "response_s": 60,
    },
    "AGC": {
        "label": "Control Automático de Generación",
        "min_kw": 15.0,
        "max_kw_pct": 0.20,
        "price_usd_mw_h": 5.2,   # AGC commands → highest premium
        "priority": 5,
        "soc_min_pct": 30.0,
        "soc_max_pct": 85.0,
        "response_s": 4,
    },
}

# USD/CLP exchange rate (updated via config in production)
DEFAULT_USD_CLP = 871.0


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AncillaryServiceCapacity:
    """Assigned capacity for one ancillary service.

    Attributes:
        service:            Service identifier (CSF, RP, etc.).
        label:              Human-readable name.
        reserved_kw:        Power committed to this service (kW).
        price_usd_mw_h:     Market price for this service (USD/MW·h).
        eligible:           Whether the BESS meets all requirements.
        rejection_reason:   Why the service was skipped, if not eligible.
    """

    service: AncillaryService
    label: str
    reserved_kw: float
    price_usd_mw_h: float
    eligible: bool = True
    rejection_reason: str = ""

    @property
    def revenue_usd_per_hour(self) -> float:
        """Revenue in USD for one hour of reserved capacity."""
        return self.reserved_kw / 1000.0 * self.price_usd_mw_h

    def revenue_clp_per_hour(self, usd_clp: float = DEFAULT_USD_CLP) -> float:
        """Revenue in CLP for one hour of reserved capacity."""
        return self.revenue_usd_per_hour * usd_clp

    def to_dict(self, usd_clp: float = DEFAULT_USD_CLP) -> dict:
        return {
            "service": self.service,
            "label": self.label,
            "reserved_kw": round(self.reserved_kw, 1),
            "price_usd_mw_h": self.price_usd_mw_h,
            "revenue_usd_per_hour": round(self.revenue_usd_per_hour, 4),
            "revenue_clp_per_hour": round(self.revenue_clp_per_hour(usd_clp)),
            "eligible": self.eligible,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class AncillaryStack:
    """Complete ancillary services allocation for a BESS site.

    Attributes:
        services:               List of per-service capacity assignments.
        total_reserved_kw:      Sum of kW committed across all services.
        total_revenue_usd_per_hour: Sum of hourly revenue in USD.
        available_for_arbitrage_kw: Remaining capacity for energy arbitrage.
        usd_clp_rate:           Exchange rate used for CLP conversion.
    """

    services: list[AncillaryServiceCapacity] = field(default_factory=list)
    total_reserved_kw: float = 0.0
    total_revenue_usd_per_hour: float = 0.0
    available_for_arbitrage_kw: float = 0.0
    usd_clp_rate: float = DEFAULT_USD_CLP

    @property
    def total_revenue_clp_per_hour(self) -> float:
        return self.total_revenue_usd_per_hour * self.usd_clp_rate

    @property
    def revenue_breakdown(self) -> dict[str, float]:
        """Revenue per service in CLP/h."""
        return {
            s.service: round(s.revenue_clp_per_hour(self.usd_clp_rate))
            for s in self.services if s.eligible
        }

    def summary(self) -> str:
        lines = ["── Ancillary Services Stack ──────────────────────"]
        for s in self.services:
            status = f"{s.reserved_kw:.0f} kW @ {s.price_usd_mw_h} USD/MW·h" if s.eligible else f"⚠ {s.rejection_reason}"
            lines.append(f"  {s.service:<5} {s.label:<40} {status}")
        lines.append(f"  {'TOTAL':>5} {'':40} {self.total_reserved_kw:.0f} kW")
        lines.append(f"  Revenue: USD {self.total_revenue_usd_per_hour:.4f}/h  "
                     f"CLP {self.total_revenue_clp_per_hour:,.0f}/h")
        lines.append(f"  Arbitrage headroom: {self.available_for_arbitrage_kw:.0f} kW")
        return "\n".join(lines)

    def to_api_dict(self) -> dict:
        return {
            "total_reserved_kw": round(self.total_reserved_kw, 1),
            "total_revenue_usd_per_hour": round(self.total_revenue_usd_per_hour, 4),
            "total_revenue_clp_per_hour": round(self.total_revenue_clp_per_hour),
            "available_for_arbitrage_kw": round(self.available_for_arbitrage_kw, 1),
            "revenue_breakdown": self.revenue_breakdown,
            "services": [s.to_dict(self.usd_clp_rate) for s in self.services],
        }


# ─────────────────────────────────────────────────────────────────────────────
# CapacityAllocator
# ─────────────────────────────────────────────────────────────────────────────

class CapacityAllocator:
    """Allocates residual BESS capacity to SEN ancillary services.

    The allocator works in priority order (CSF → RP → RSS → RSB → AGC).
    At each step it checks:
      1. SoC eligibility for the service.
      2. Minimum power threshold (min_kw).
      3. Remaining capacity after higher-priority allocations.

    Parameters:
        capacity_kwh:       Battery usable capacity (kWh).
        max_power_kw:       Max charge/discharge power (kW).
        usd_clp_rate:       USD/CLP exchange rate for revenue conversion.
        service_overrides:  Optional dict to override market prices per service.
    """

    def __init__(
        self,
        capacity_kwh: float = 1000.0,
        max_power_kw: float = 500.0,
        usd_clp_rate: float = DEFAULT_USD_CLP,
        service_overrides: dict | None = None,
    ) -> None:
        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self.usd_clp_rate = usd_clp_rate
        # Merge market defaults with any project-specific overrides
        self._services: dict[str, dict] = {}
        for svc_id, defaults in SEN_SERVICES.items():
            merged = dict(defaults)
            if service_overrides and svc_id in service_overrides:
                merged.update(service_overrides[svc_id])
            self._services[svc_id] = merged

    # ── Core allocation ───────────────────────────────────────────────────────

    def allocate(
        self,
        soc_pct: float,
        arbitrage_reserved_kw: float = 0.0,
    ) -> AncillaryStack:
        """Allocate remaining capacity to ancillary services.

        Args:
            soc_pct:                Current SoC percentage.
            arbitrage_reserved_kw:  kW already committed to energy arbitrage.

        Returns:
            AncillaryStack with per-service allocation and revenue totals.
        """
        remaining_kw = max(0.0, self.max_power_kw - arbitrage_reserved_kw)
        assignments: list[AncillaryServiceCapacity] = []
        total_reserved = 0.0
        total_revenue_usd = 0.0

        # Sort by priority (ascending = highest first)
        ordered = sorted(self._services.items(), key=lambda x: x[1]["priority"])

        for svc_id, cfg in ordered:
            svc: AncillaryService = svc_id  # type: ignore[assignment]
            label = cfg["label"]
            min_kw = cfg["min_kw"]
            max_kw = self.max_power_kw * cfg["max_kw_pct"]
            price = cfg["price_usd_mw_h"]
            soc_min = cfg["soc_min_pct"]
            soc_max = cfg["soc_max_pct"]

            # Check SoC window
            if not (soc_min <= soc_pct <= soc_max):
                reason = f"SoC {soc_pct:.1f}% outside [{soc_min}–{soc_max}]%"
                assignments.append(AncillaryServiceCapacity(
                    service=svc, label=label, reserved_kw=0.0,
                    price_usd_mw_h=price, eligible=False, rejection_reason=reason,
                ))
                continue

            # Check available capacity
            if remaining_kw < min_kw:
                reason = f"Only {remaining_kw:.1f} kW available, need ≥{min_kw}"
                assignments.append(AncillaryServiceCapacity(
                    service=svc, label=label, reserved_kw=0.0,
                    price_usd_mw_h=price, eligible=False, rejection_reason=reason,
                ))
                continue

            # Allocate up to max for this service
            allocated_kw = min(remaining_kw, max_kw)
            remaining_kw -= allocated_kw
            total_reserved += allocated_kw

            cap = AncillaryServiceCapacity(
                service=svc, label=label,
                reserved_kw=allocated_kw, price_usd_mw_h=price,
            )
            total_revenue_usd += cap.revenue_usd_per_hour
            assignments.append(cap)

            log.debug(
                "ancillary.allocated",
                service=svc_id, reserved_kw=round(allocated_kw, 1),
                revenue_usd_h=round(cap.revenue_usd_per_hour, 4),
            )

        stack = AncillaryStack(
            services=assignments,
            total_reserved_kw=round(total_reserved, 1),
            total_revenue_usd_per_hour=round(total_revenue_usd, 6),
            available_for_arbitrage_kw=round(arbitrage_reserved_kw, 1),
            usd_clp_rate=self.usd_clp_rate,
        )

        log.info(
            "ancillary.stack_computed",
            total_reserved_kw=stack.total_reserved_kw,
            total_revenue_clp_h=round(stack.total_revenue_clp_per_hour),
            soc_pct=soc_pct,
        )
        return stack

    def estimate_daily_revenue_clp(
        self,
        soc_pct: float,
        arbitrage_reserved_kw: float = 0.0,
        hours: int = 24,
    ) -> float:
        """Estimate total ancillary revenue in CLP for N hours."""
        stack = self.allocate(soc_pct=soc_pct, arbitrage_reserved_kw=arbitrage_reserved_kw)
        return stack.total_revenue_clp_per_hour * hours
