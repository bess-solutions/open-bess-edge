"""
src/interfaces/arbitrage_engine.py
====================================
BESSAI Edge Gateway — Arbitrage Schedule Engine v2.

Mejoras v2:
  - Umbral mínimo de confianza: sólo opera cuando forecast.confidence >= min_confidence
  - Usa bandas p10/p90 del CMgPredictor para revenue conservador
  - DispatchSlot expone cmg_p10, cmg_p90, confidence en to_dict()
  - Logging enriquecido con avg_confidence y n_low_confidence slots

Algorithm:
    1. Filtrar horas con confidence < min_confidence → hold forzado.
    2. Ordenar restantes por precio.
    3. Cheapest N → charge (si precio < media − 0.5σ AND spread p10-p90 bajo).
    4. Most expensive N → discharge (si precio > media + 0.5σ AND spread bajo).
    5. Simular SOC con safety constraints.

Usage::

    from src.interfaces.cmg_predictor import CMgPredictor
    from src.interfaces.arbitrage_engine import ArbitrageEngine

    predictor = CMgPredictor(node="Maitencillo")
    predictor.load()
    forecast = predictor.predict_next_24h(current_hour=10, current_cmg=45.2)

    engine = ArbitrageEngine(capacity_kwh=1000.0, max_power_kw=500.0, min_confidence=0.4)
    schedule = engine.compute(forecast, current_soc_pct=30.0)
    print(schedule.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import structlog

from .cmg_predictor import PriceForecast

__all__ = ["ArbitrageEngine", "ArbitrageSchedule", "DispatchSlot"]

log = structlog.get_logger(__name__)

Action = Literal["charge", "discharge", "hold"]


@dataclass
class DispatchSlot:
    """One hour of the dispatch schedule.

    Attributes:
        hour:           Hour-of-day (0-23).
        action:         'charge', 'discharge', or 'hold'.
        power_kw:       Power setpoint (positive = charge, negative = discharge).
        forecast:       Price forecast for this hour.
        soc_before_pct: Estimated SOC at the start of this hour.
        soc_after_pct:  Estimated SOC at the end of this hour.
        revenue_clp:    Revenue (positive) or cost (negative) for this slot.
    """

    hour: int
    action: Action
    power_kw: float
    forecast: PriceForecast
    soc_before_pct: float = 0.0
    soc_after_pct: float = 0.0
    revenue_clp: float = 0.0

    @property
    def net_kwh(self) -> float:
        """Net energy exchanged in this slot (positive = charged into battery)."""
        return self.power_kw  # 1h slot → kWh = kW

    def to_dict(self) -> dict:
        return {
            "hour": self.hour,
            "action": self.action,
            "power_kw": round(self.power_kw, 1),
            "cmg_clp_kwh": self.forecast.cmg_clp_kwh,
            "cmg_p10": self.forecast.cmg_p10,
            "cmg_p90": self.forecast.cmg_p90,
            "confidence": round(self.forecast.confidence, 3),
            "soc_before_pct": round(self.soc_before_pct, 1),
            "soc_after_pct": round(self.soc_after_pct, 1),
            "revenue_clp": round(self.revenue_clp),
            "is_peak": self.forecast.is_peak,
        }


@dataclass
class ArbitrageSchedule:
    """Complete 24-hour arbitrage dispatch schedule.

    Attributes:
        node:               SEN node name.
        slots:              24 DispatchSlot objects ordered by hour.
        projected_revenue_clp: Total revenue from discharge operations.
        projected_cost_clp:    Total cost from charge operations.
        projected_net_clp:     Net daily income.
        n_charge_hours:     Number of hours actively charging.
        n_discharge_hours:  Number of hours actively discharging.
        capacity_kwh:       Battery capacity used in computation.
        efficiency:         Round-trip efficiency assumed.
    """

    node: str = "unknown"
    slots: list[DispatchSlot] = field(default_factory=list)
    projected_revenue_clp: float = 0.0
    projected_cost_clp: float = 0.0
    projected_net_clp: float = 0.0
    n_charge_hours: int = 0
    n_discharge_hours: int = 0
    capacity_kwh: float = 1000.0
    efficiency: float = 0.92

    def summary(self) -> str:
        lines = [
            f"ArbitrageSchedule — {self.node}",
            f"  Charge:    {self.n_charge_hours}h | Discharge: {self.n_discharge_hours}h",
            f"  Revenue:   CLP {self.projected_revenue_clp:,.0f}",
            f"  Cost:      CLP {self.projected_cost_clp:,.0f}",
            f"  Net:       CLP {self.projected_net_clp:,.0f}",
        ]
        return "\n".join(lines)

    def to_api_dict(self) -> dict:
        """Serializable dict for REST API /api/v1/schedule endpoint."""
        return {
            "node": self.node,
            "capacity_kwh": self.capacity_kwh,
            "efficiency": self.efficiency,
            "projected_revenue_clp": round(self.projected_revenue_clp),
            "projected_cost_clp": round(self.projected_cost_clp),
            "projected_net_clp": round(self.projected_net_clp),
            "n_charge_hours": self.n_charge_hours,
            "n_discharge_hours": self.n_discharge_hours,
            "hourly_schedule": [
                slot.to_dict() for slot in sorted(self.slots, key=lambda s: s.hour)
            ],
        }


class ArbitrageEngine:
    """Computes optimal arbitrage schedules for BESS systems.

    Parameters:
        capacity_kwh:       Usable battery capacity (kWh).
        max_power_kw:       Maximum charge/discharge power (kW).
        min_soc_pct:        Minimum allowed SOC (%) — safety floor.
        max_soc_pct:        Maximum allowed SOC (%) — safety ceiling.
        efficiency:         Round-trip efficiency [0, 1].
        max_charge_hours:   Maximum hours to charge per day (cycle life mgmt).
        max_discharge_hours: Maximum hours to discharge per day.
        node:               SEN node name (for logging).
    """

    def __init__(
        self,
        capacity_kwh: float = 1000.0,
        max_power_kw: float = 500.0,
        min_soc_pct: float = 10.0,
        max_soc_pct: float = 95.0,
        efficiency: float = 0.92,
        max_charge_hours: int = 6,
        max_discharge_hours: int = 4,
        node: str = "unknown",
        min_confidence: float = 0.4,
        min_spread_clp: float = 30.0,
    ) -> None:
        self.capacity_kwh = capacity_kwh
        self.max_power_kw = max_power_kw
        self.min_soc_pct = min_soc_pct
        self.max_soc_pct = max_soc_pct
        self.efficiency = efficiency
        self.max_charge_hours = max_charge_hours
        self.max_discharge_hours = max_discharge_hours
        self.node = node
        # v2 uncertainty controls
        self.min_confidence = min_confidence   # skip hours below this confidence
        self.min_spread_clp = min_spread_clp   # min price spread to trade (p90_max - p10_min)

    # ── Core computation ──────────────────────────────────────────────────────

    def compute(
        self,
        forecasts: list[PriceForecast],
        current_soc_pct: float = 50.0,
    ) -> ArbitrageSchedule:
        """Compute the optimal 24h charge/discharge schedule.

        Args:
            forecasts:        24 PriceForecast objects (from CMgPredictor).
            current_soc_pct:  Current state of charge in percent.

        Returns:
            ArbitrageSchedule with all 24 slots filled.
        """
        if not forecasts:
            log.warning("arbitrage_engine.empty_forecast", node=self.node)
            return ArbitrageSchedule(node=self.node)

        # ── v2: filter low-confidence hours → hold forced ──
        viable = [f for f in forecasts if f.confidence >= self.min_confidence]
        low_conf_hours = {f.hour for f in forecasts if f.confidence < self.min_confidence}
        if low_conf_hours:
            log.info(
                "arbitrage_engine.low_confidence_skipped",
                node=self.node,
                n_skipped=len(low_conf_hours),
                hours=sorted(low_conf_hours),
            )

        # ── v2: check minimum spread using p10/p90 bands ──
        if viable:
            max_p90 = max(f.cmg_p90 for f in viable)
            min_p10 = min(f.cmg_p10 for f in viable)
            effective_spread = max_p90 - min_p10
        else:
            effective_spread = 0.0

        if effective_spread < self.min_spread_clp:
            log.info(
                "arbitrage_engine.spread_too_low",
                node=self.node,
                effective_spread=round(effective_spread, 1),
                min_spread_clp=self.min_spread_clp,
            )
            # Build all-hold schedule (no trading)
            return self._all_hold_schedule(forecasts, current_soc_pct)

        # Sort by price to identify charge/discharge candidates
        sorted_by_price = sorted(viable, key=lambda f: f.cmg_clp_kwh)

        # Cheapest N hours → charge candidates
        charge_hours = {
            f.hour
            for f in sorted_by_price[: self.max_charge_hours]
            if f.cmg_clp_kwh < self._price_threshold(viable, "low")
        }

        # Most expensive N hours → discharge candidates
        discharge_hours = {
            f.hour
            for f in sorted_by_price[-self.max_discharge_hours :]
            if f.cmg_clp_kwh > self._price_threshold(viable, "high")
        }

        # Prevent overlap (discharge takes priority)
        charge_hours -= discharge_hours

        # Simulate SOC evolution
        slots: list[DispatchSlot] = []
        soc = current_soc_pct
        total_revenue = 0.0
        total_cost = 0.0

        {f.hour: f for f in forecasts}

        for fc in sorted(forecasts, key=lambda f: f.hour):
            h = fc.hour
            soc_before = soc

            if h in charge_hours and soc < self.max_soc_pct:
                action: Action = "charge"
                # Power limited by remaining capacity
                energy_needed = (self.max_soc_pct - soc) / 100 * self.capacity_kwh
                power_kw = min(self.max_power_kw, energy_needed)
                delta_soc = (power_kw / self.capacity_kwh) * 100
                soc = min(self.max_soc_pct, soc + delta_soc)
                revenue = -power_kw * fc.cmg_clp_kwh / 1000  # cost (negative revenue)
                total_cost += abs(revenue)

            elif h in discharge_hours and soc > self.min_soc_pct:
                action = "discharge"
                energy_available = (soc - self.min_soc_pct) / 100 * self.capacity_kwh
                power_kw = min(self.max_power_kw, energy_available) * self.efficiency
                delta_soc = (min(self.max_power_kw, energy_available) / self.capacity_kwh) * 100
                soc = max(self.min_soc_pct, soc - delta_soc)
                revenue = power_kw * fc.cmg_clp_kwh / 1000
                total_revenue += revenue
                power_kw = -power_kw  # Negative = discharging

            else:
                action = "hold"
                power_kw = 0.0
                revenue = 0.0

            slots.append(
                DispatchSlot(
                    hour=h,
                    action=action,
                    power_kw=round(power_kw, 1),
                    forecast=fc,
                    soc_before_pct=round(soc_before, 1),
                    soc_after_pct=round(soc, 1),
                    revenue_clp=round(revenue * 1000),  # convert back to CLP
                )
            )

        net = total_revenue - total_cost
        avg_confidence = (
            sum(f.confidence for f in forecasts) / len(forecasts) if forecasts else 0.0
        )
        log.info(
            "arbitrage_engine.schedule_computed",
            node=self.node,
            charge_hours=len(charge_hours),
            discharge_hours=len(discharge_hours),
            projected_net_clp=round(net * 1000),
            avg_confidence=round(avg_confidence, 3),
            effective_spread=round(effective_spread, 1),
        )

        return ArbitrageSchedule(
            node=self.node,
            slots=slots,
            projected_revenue_clp=round(total_revenue * 1000),
            projected_cost_clp=round(total_cost * 1000),
            projected_net_clp=round(net * 1000),
            n_charge_hours=len(charge_hours),
            n_discharge_hours=len(discharge_hours),
            capacity_kwh=self.capacity_kwh,
            efficiency=self.efficiency,
        )

    def _all_hold_schedule(
        self,
        forecasts: list[PriceForecast],
        current_soc_pct: float,
    ) -> ArbitrageSchedule:
        """Return an all-hold schedule when spread is too low to trade."""
        slots = [
            DispatchSlot(
                hour=fc.hour,
                action="hold",
                power_kw=0.0,
                forecast=fc,
                soc_before_pct=current_soc_pct,
                soc_after_pct=current_soc_pct,
                revenue_clp=0.0,
            )
            for fc in sorted(forecasts, key=lambda f: f.hour)
        ]
        return ArbitrageSchedule(
            node=self.node,
            slots=slots,
            projected_net_clp=0.0,
            capacity_kwh=self.capacity_kwh,
            efficiency=self.efficiency,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _price_threshold(
        self,
        forecasts: list[PriceForecast],
        level: Literal["low", "high"],
    ) -> float:
        """Compute charge (low) or discharge (high) price threshold.

        Charge if price < mean − 0.5σ
        Discharge if price > mean + 0.5σ
        """
        prices = [f.cmg_clp_kwh for f in forecasts]
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std = variance**0.5

        if level == "low":
            return float(mean - 0.5 * std)
        return float(mean + 0.5 * std)

    def daily_roe_estimate(
        self,
        schedule: ArbitrageSchedule,
        capex_usd: float = 720_000,
        usd_clp_rate: float = 950.0,
        days_per_year: int = 350,
    ) -> float:
        """Estimate annualized ROE from a single day's schedule.

        Args:
            capex_usd:       CAPEX in USD (default: USD 720k for 1 MWh system).
            usd_clp_rate:    USD/CLP exchange rate.
            days_per_year:   Operating days per year (accounting for maintenance).

        Returns:
            Annualized ROE as a decimal (e.g., 0.284 = 28.4%).
        """
        annual_net_clp = schedule.projected_net_clp * days_per_year
        capex_clp = capex_usd * usd_clp_rate
        return annual_net_clp / capex_clp if capex_clp > 0 else 0.0
