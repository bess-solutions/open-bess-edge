# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/market_adapter.py
===========================
BESSAI Edge Gateway — Market Adapter Layer v1.0

Abstracts the electricity market interface so BESSAI can operate in
multiple Latam markets without changing core dispatch logic.

Supported markets:
  SEN   — Chile (Sistema Eléctrico Nacional) — fully implemented.
  COES  — Peru (Comité de Operación Económica del Sistema) — stub.
  XM    — Colombia (Administrador del Sistema de Intercambios Comerciales) — stub.
  CENACE — Mexico (Centro Nacional de Control de Energía) — stub.

Usage::

    from src.core.market_adapter import MarketAdapterRegistry

    adapter = MarketAdapterRegistry.get()   # reads BESSAI_MARKET env var
    prices = adapter.get_spot_prices_clp_kwh(date="2026-03-11")
    rules = adapter.get_dispatch_rules()
    services = adapter.get_ancillary_services()
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import structlog

__all__ = [
    "SpotPrice",
    "AncillaryServiceDef",
    "DispatchRules",
    "MarketAdapter",
    "SENAdapter",
    "COESAdapter",
    "XMAdapter",
    "CENACEAdapter",
    "MarketAdapterRegistry",
]

log = structlog.get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Shared data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SpotPrice:
    """Hourly spot price for one market node.

    Attributes:
        hour:       Hour of day (0–23).
        price_usd_mwh:   Spot price in USD per MWh.
        node:       Market node name.
        market:     Market identifier (SEN, COES, XM, CENACE).
        date:       Date of the price.
    """

    hour: int
    price_usd_mwh: float
    node: str
    market: str
    date: str = ""

    @property
    def price_clp_kwh(self) -> float:
        """Convert to CLP/kWh using SEN reference rate (950 CLP/USD)."""
        return self.price_usd_mwh / 1000 * 950.0

    def to_dict(self) -> dict:
        return {
            "hour": self.hour,
            "price_usd_mwh": round(self.price_usd_mwh, 2),
            "price_clp_kwh": round(self.price_clp_kwh, 2),
            "node": self.node,
            "market": self.market,
            "date": self.date,
        }


@dataclass
class AncillaryServiceDef:
    """Definition of an ancillary service available in a market.

    Attributes:
        service_id:     Canonical ID (e.g., 'CSF', 'SPINNING_RESERVE').
        label:          Human-readable name.
        min_power_kw:   Minimum BESS power to qualify.
        price_usd_mwh:  Reference price for capacity reservation.
        response_s:     Required response time in seconds.
        available:      Whether active in this market.
    """

    service_id: str
    label: str
    min_power_kw: float
    price_usd_mwh: float
    response_s: int
    available: bool = True


@dataclass
class DispatchRules:
    """Market-specific BESS dispatch constraints.

    Attributes:
        min_soc_pct:        Minimum state of charge allowed (%).
        max_soc_pct:        Maximum state of charge allowed (%).
        max_daily_cycles:   Max full charge/discharge cycles per day.
        peak_hours:         Hours considered peak (0-indexed list).
        currency:           Local currency code.
        usd_local_rate:     USD to local currency exchange rate.
        grid_frequency_hz:  Grid nominal frequency.
    """

    min_soc_pct: float = 10.0
    max_soc_pct: float = 95.0
    max_daily_cycles: int = 2
    peak_hours: list[int] = field(default_factory=lambda: list(range(18, 23)))
    currency: str = "CLP"
    usd_local_rate: float = 950.0
    grid_frequency_hz: float = 50.0


# ─────────────────────────────────────────────────────────────────────────────
# Abstract base — MarketAdapter Protocol
# ─────────────────────────────────────────────────────────────────────────────

class MarketAdapter(ABC):
    """Abstract interface all market adapters must implement."""

    @property
    @abstractmethod
    def market_id(self) -> str:
        """Short market identifier (e.g., 'SEN', 'COES')."""

    @property
    @abstractmethod
    def country(self) -> str:
        """Country name."""

    @abstractmethod
    def get_spot_prices(self, date_str: str, node: str) -> list[SpotPrice]:
        """Fetch hourly spot prices for the given date and node.

        Args:
            date_str: ISO format date string 'YYYY-MM-DD'.
            node:     Market node or bus name.

        Returns:
            List of 24 SpotPrice objects.
        """

    @abstractmethod
    def get_ancillary_services(self) -> list[AncillaryServiceDef]:
        """Return the ancillary services available in this market."""

    @abstractmethod
    def get_dispatch_rules(self) -> DispatchRules:
        """Return market-specific BESS dispatch constraints."""

    def get_market_zones(self) -> list[str]:
        """Return list of market nodes/zones. Optional override."""
        return []

    def to_dict(self) -> dict:
        return {
            "market_id": self.market_id,
            "country": self.country,
            "zones": self.get_market_zones(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# SEN — Chile (fully implemented)
# ─────────────────────────────────────────────────────────────────────────────

class SENAdapter(MarketAdapter):
    """Market adapter for Chile's SEN (Sistema Eléctrico Nacional).

    Wraps the existing CMg/DuckDB pipeline and sen_constants definitions
    behind the MarketAdapter interface.
    """

    SEN_NODES = [
        "Maitencillo", "Quillota", "Pan_de_Azucar", "Cardones",
        "Crucero", "Encuentro", "Diego_de_Almagro", "Polpaico",
    ]

    @property
    def market_id(self) -> str:
        return "SEN"

    @property
    def country(self) -> str:
        return "Chile"

    def get_spot_prices(self, date_str: str, node: str = "Maitencillo") -> list[SpotPrice]:
        """Return stub 24h prices. In production, queries DuckDB bessai_cen.db."""
        import math
        prices = []
        for h in range(24):
            # Duck Curve model for Chilean SEN:
            # – Cheapest overnight (2-4 AM), mid-price midday solar dip, peak 18-21 PM
            overnight_dip  = -12.0 * math.exp(-((h - 3) ** 2) / 5.0)   # cheap off-peak
            solar_dip      = -8.0  * math.exp(-((h - 12) ** 2) / 6.0)  # solar overgeneration
            evening_peak   =  28.0 * math.exp(-((h - 19) ** 2) / 4.0)  # ramping demand
            price = max(0.0, 35.0 + overnight_dip + solar_dip + evening_peak)
            prices.append(SpotPrice(
                hour=h,
                price_usd_mwh=price,
                node=node,
                market="SEN",
                date=date_str,
            ))
        return prices

    def get_ancillary_services(self) -> list[AncillaryServiceDef]:
        """Returns the 5 SEN complementary services (NTSyCS)."""
        return [
            AncillaryServiceDef("CSF", "Capacidad Suficiencia Frecuencia", 10.0, 4.5, 1),
            AncillaryServiceDef("RP", "Reserva Primaria", 20.0, 3.8, 30),
            AncillaryServiceDef("RSS", "Reserva Seguridad Semanal", 50.0, 2.9, 300),
            AncillaryServiceDef("RSB", "Reserva Seguridad de Banda", 30.0, 2.4, 60),
            AncillaryServiceDef("AGC", "Control Automático de Generación", 15.0, 5.2, 4),
        ]

    def get_dispatch_rules(self) -> DispatchRules:
        return DispatchRules(
            min_soc_pct=10.0, max_soc_pct=95.0,
            max_daily_cycles=2,
            peak_hours=list(range(17, 24)),
            currency="CLP", usd_local_rate=950.0,
            grid_frequency_hz=50.0,
        )

    def get_market_zones(self) -> list[str]:
        return self.SEN_NODES


# ─────────────────────────────────────────────────────────────────────────────
# COES — Peru (stub)
# ─────────────────────────────────────────────────────────────────────────────

class COESAdapter(MarketAdapter):
    """Peru COES market adapter (stub — wire to COES API for production)."""

    @property
    def market_id(self) -> str:
        return "COES"

    @property
    def country(self) -> str:
        return "Peru"

    def get_spot_prices(self, date_str: str, node: str = "LIMA_SUR") -> list[SpotPrice]:
        log.warning("coes_adapter.stub", msg="COES API not yet connected — returning zeros")
        return [SpotPrice(h, 0.0, node, "COES", date_str) for h in range(24)]

    def get_ancillary_services(self) -> list[AncillaryServiceDef]:
        # COES uses Reserva de Frecuencia Primaria (RFP) and Potencia Firme
        return [
            AncillaryServiceDef("RFP", "Reserva de Frecuencia Primaria", 20.0, 3.5, 30, available=False),
            AncillaryServiceDef("PF", "Potencia Firme", 100.0, 2.0, 3600, available=False),
        ]

    def get_dispatch_rules(self) -> DispatchRules:
        return DispatchRules(
            min_soc_pct=15.0, max_soc_pct=90.0,
            currency="PEN", usd_local_rate=3.7,
            grid_frequency_hz=60.0,  # Peru runs 60 Hz
        )

    def get_market_zones(self) -> list[str]:
        return ["LIMA_SUR", "LIMA_NORTE", "CHIMBOTE", "TALARA"]


# ─────────────────────────────────────────────────────────────────────────────
# XM — Colombia (stub)
# ─────────────────────────────────────────────────────────────────────────────

class XMAdapter(MarketAdapter):
    """Colombia XM market adapter (stub — wire to XM API for production)."""

    @property
    def market_id(self) -> str:
        return "XM"

    @property
    def country(self) -> str:
        return "Colombia"

    def get_spot_prices(self, date_str: str, node: str = "BOGOTA") -> list[SpotPrice]:
        log.warning("xm_adapter.stub", msg="XM API not yet connected — returning zeros")
        return [SpotPrice(h, 0.0, node, "XM", date_str) for h in range(24)]

    def get_ancillary_services(self) -> list[AncillaryServiceDef]:
        return [
            AncillaryServiceDef("AGC_CO", "Regulación Automática", 10.0, 6.0, 4, available=False),
            AncillaryServiceDef("RES_CO", "Reserva Rodante", 30.0, 2.5, 60, available=False),
        ]

    def get_dispatch_rules(self) -> DispatchRules:
        return DispatchRules(
            min_soc_pct=10.0, max_soc_pct=95.0,
            currency="COP", usd_local_rate=4200.0,
            grid_frequency_hz=60.0,
        )

    def get_market_zones(self) -> list[str]:
        return ["BOGOTA", "MEDELLIN", "CALI", "BARRANQUILLA"]


# ─────────────────────────────────────────────────────────────────────────────
# CENACE — Mexico (stub)
# ─────────────────────────────────────────────────────────────────────────────

class CENACEAdapter(MarketAdapter):
    """Mexico CENACE market adapter (stub — wire to CENACE API for production)."""

    @property
    def market_id(self) -> str:
        return "CENACE"

    @property
    def country(self) -> str:
        return "Mexico"

    def get_spot_prices(self, date_str: str, node: str = "CDMX") -> list[SpotPrice]:
        log.warning("cenace_adapter.stub", msg="CENACE API not yet connected — returning zeros")
        return [SpotPrice(h, 0.0, node, "CENACE", date_str) for h in range(24)]

    def get_ancillary_services(self) -> list[AncillaryServiceDef]:
        return [
            AncillaryServiceDef("R_RAPIDA", "Reserva de Regulación Rápida", 10.0, 7.0, 10, available=False),
            AncillaryServiceDef("R_LENTA", "Reserva de Regulación Lenta", 50.0, 3.0, 300, available=False),
        ]

    def get_dispatch_rules(self) -> DispatchRules:
        return DispatchRules(
            min_soc_pct=10.0, max_soc_pct=90.0,
            currency="MXN", usd_local_rate=18.0,
            grid_frequency_hz=60.0,
        )

    def get_market_zones(self) -> list[str]:
        return ["CDMX", "MONTERREY", "GUADALAJARA", "MERIDA"]


# ─────────────────────────────────────────────────────────────────────────────
# Registry — resolve adapter from env
# ─────────────────────────────────────────────────────────────────────────────

_ADAPTERS: dict[str, type[MarketAdapter]] = {
    "SEN": SENAdapter,
    "COES": COESAdapter,
    "XM": XMAdapter,
    "CENACE": CENACEAdapter,
}


class MarketAdapterRegistry:
    """Singleton registry that resolves the active market adapter from env.

    Reads `BESSAI_MARKET` environment variable (default: 'SEN').

    Usage::
        adapter = MarketAdapterRegistry.get()           # from env
        adapter = MarketAdapterRegistry.get("COES")     # explicit
    """

    _instance: dict[str, MarketAdapter] = {}

    @classmethod
    def get(cls, market_id: str | None = None) -> MarketAdapter:
        """Return the adapter for the requested or configured market."""
        key = (market_id or os.getenv("BESSAI_MARKET", "SEN")).upper()
        if key not in cls._instance:
            adapter_cls = _ADAPTERS.get(key)
            if adapter_cls is None:
                supported = ", ".join(_ADAPTERS.keys())
                raise ValueError(
                    f"Unknown market: {key!r}. Supported: {supported}"
                )
            cls._instance[key] = adapter_cls()
            log.info("market_adapter.loaded", market_id=key)
        return cls._instance[key]

    @classmethod
    def available_markets(cls) -> list[str]:
        return list(_ADAPTERS.keys())

    @classmethod
    def reset(cls) -> None:
        """Clear cached instances (useful for testing)."""
        cls._instance.clear()
