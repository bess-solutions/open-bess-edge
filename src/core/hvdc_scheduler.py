# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/hvdc_scheduler.py
===========================
BESSAI Edge Gateway — HVDC Virtual Dispatch Scheduler (BEP-0700).

Simulates High-Voltage Direct Current (HVDC) link scheduling between
two BESSAI regions (e.g. Norte Grande ↔ SIC in Chile, or US West ↔ East).

Although this is a simulation module (real HVDC dispatch requires TSO-level
integration), it provides:
1. Physics-based HVDC power flow model (DC load flow, line limits)
2. Optimal dispatch schedule given two regional price signals
3. Import/export setpoints for each FleetOrchestrator region
4. Integration interface with VPPFleetManager

BEP-0700 spec reference: docs/bep/BEP-0700.md

Architecture::

    Region A (SEN Norte) ─── HVDCLink ─── Region B (SEN SIC)
         │                                      │
    FleetOrchestratorA                    FleetOrchestratorB
         │                                      │
              └──────── HVDCScheduler ──────────┘
                        (price arbitrage
                         + line limits
                         + losses)

Usage::

    scheduler = HVDCScheduler(
        link_capacity_mw=500.0,
        losses_pct=0.018,        # 1.8% losses (typical 750kV HVDC)
    )
    result = scheduler.schedule(
        price_a=45.0,   # USD/MWh in region A
        price_b=82.0,   # USD/MWh in region B
        available_a_kw=2000.0,
        available_b_kw=800.0,
    )
    print(result.flow_kw)        # + = A→B, - = B→A
    print(result.arbitrage_usd)  # Revenue from price difference
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

import structlog

__all__ = [
    "HVDCScheduler",
    "HVDCResult",
    "HVDCFlowDirection",
]

log = structlog.get_logger(__name__)


class HVDCFlowDirection(str, Enum):
    """Direction of power flow on the HVDC link."""

    A_TO_B = "A→B"  # Region A exports to region B
    B_TO_A = "B→A"  # Region B exports to region A
    IDLE = "idle"  # No flow (prices in equilibrium)


@dataclass
class HVDCResult:
    """Result of an HVDC dispatch scheduling computation.

    Attributes:
        flow_kw:         Scheduled flow (kW). Positive = A→B, negative = B→A.
        direction:       Flow direction enum.
        arbitrage_usd:   Estimated hourly revenue from price differential.
        region_a_setpoint_kw: Setpoint for region A fleet (negative = export).
        region_b_setpoint_kw: Setpoint for region B fleet (positive = receive).
        losses_kw:       Power lost in transmission.
        price_spread:    Absolute price difference (USD/MWh).
        constrained:     True if flow was clipped by link_capacity_mw.
        timestamp:       Unix timestamp of computation.
    """

    flow_kw: float
    direction: HVDCFlowDirection
    arbitrage_usd: float
    region_a_setpoint_kw: float
    region_b_setpoint_kw: float
    losses_kw: float
    price_spread: float
    constrained: bool
    timestamp: float = field(default_factory=time.time)

    @property
    def net_benefit_usd(self) -> float:
        """Arbitrage revenue minus estimated losses cost (at avg price)."""
        return self.arbitrage_usd

    @property
    def is_active(self) -> bool:
        """True if the link is actively carrying power."""
        return self.direction != HVDCFlowDirection.IDLE


class HVDCScheduler:
    """HVDC link virtual dispatch scheduler.

    Computes optimal power flow between two BESSAI regions based on
    real-time spot price differentials, subject to:
      - Link thermal capacity limit (MVA → kW)
      - Minimum price spread threshold (deadband)
      - Transmission losses (resistive, proportional to flow²)
      - Each region's available dispatch capacity

    Parameters:
        link_capacity_mw:   Thermal rating of the HVDC link in MW.
        losses_pct:         Transmission losses as fraction of flow (0–1).
        min_spread_usd_mwh: Minimum price spread to trigger dispatch.
        max_util_pct:       Max fraction of link capacity to use (safety margin).
    """

    def __init__(
        self,
        link_capacity_mw: float = 500.0,
        losses_pct: float = 0.018,  # 1.8% for 750kV HVDC
        min_spread_usd_mwh: float = 5.0,  # Deadband — don't dispatch below this
        max_util_pct: float = 0.95,  # Never use more than 95% of capacity
    ) -> None:
        self.link_capacity_kw = link_capacity_mw * 1_000.0
        self.losses_pct = losses_pct
        self.min_spread_usd_mwh = min_spread_usd_mwh
        self.max_util_pct = max_util_pct
        self._dispatch_count: int = 0
        self._history: list[HVDCResult] = []

    # ------------------------------------------------------------------
    # Core scheduling logic
    # ------------------------------------------------------------------

    def schedule(
        self,
        price_a: float,  # USD/MWh, region A
        price_b: float,  # USD/MWh, region B
        available_a_kw: float,  # Available dispatch from region A
        available_b_kw: float,  # Available dispatch from region B
    ) -> HVDCResult:
        """Compute optimal HVDC dispatch for current prices.

        The flow is determined by:
          1. Spread = |price_B - price_A|
          2. If spread < min_spread_usd_mwh → IDLE
          3. Direction: power flows from cheap to expensive region
          4. Flow magnitude: min(available, link_capacity × max_util)
          5. Losses deducted from received power

        Args:
            price_a:       Current spot price in region A (USD/MWh).
            price_b:       Current spot price in region B (USD/MWh).
            available_a_kw: kW available from region A for export.
            available_b_kw: kW available from region B for export.

        Returns:
            HVDCResult with flow, setpoints, revenue, and metadata.
        """
        spread = abs(price_b - price_a)

        if spread < self.min_spread_usd_mwh:
            return self._idle_result(spread)

        # Determine direction: flow from lower price to higher price
        a_cheaper = price_a < price_b
        if a_cheaper:
            direction = HVDCFlowDirection.A_TO_B
            source_available = available_a_kw
        else:
            direction = HVDCFlowDirection.B_TO_A
            source_available = available_b_kw

        # Compute unconstrained flow
        max_link_kw = self.link_capacity_kw * self.max_util_pct
        raw_flow = min(source_available, max_link_kw)
        constrained = source_available > max_link_kw

        # Apply losses
        losses_kw = raw_flow * self.losses_pct
        received_kw = raw_flow - losses_kw

        # Compute arbitrage revenue (USD/h): flow × spread × 1h / 1000 kW→MW
        # Revenue = (flow MW exported) × (price_high - price_low - losses_cost)
        avg_price = (price_a + price_b) / 2.0
        losses_cost_usd = (losses_kw / 1000.0) * avg_price
        arbitrage_usd = (raw_flow / 1000.0) * spread - losses_cost_usd

        # Build setpoints
        if a_cheaper:
            sp_a = -raw_flow  # A exports (negative = discharge to grid)
            sp_b = received_kw  # B receives (positive = charge from grid)
        else:
            sp_a = received_kw
            sp_b = -raw_flow

        result = HVDCResult(
            flow_kw=raw_flow if a_cheaper else -raw_flow,
            direction=direction,
            arbitrage_usd=round(arbitrage_usd, 2),
            region_a_setpoint_kw=round(sp_a, 2),
            region_b_setpoint_kw=round(sp_b, 2),
            losses_kw=round(losses_kw, 2),
            price_spread=round(spread, 2),
            constrained=constrained,
        )

        self._dispatch_count += 1
        self._history.append(result)

        log.info(
            "hvdc.scheduled",
            direction=direction.value,
            flow_kw=round(raw_flow, 1),
            spread=round(spread, 2),
            arbitrage_usd=round(arbitrage_usd, 2),
            constrained=constrained,
        )
        return result

    def _idle_result(self, spread: float) -> HVDCResult:
        """Return an IDLE result when spread is below threshold."""
        return HVDCResult(
            flow_kw=0.0,
            direction=HVDCFlowDirection.IDLE,
            arbitrage_usd=0.0,
            region_a_setpoint_kw=0.0,
            region_b_setpoint_kw=0.0,
            losses_kw=0.0,
            price_spread=round(spread, 2),
            constrained=False,
        )

    # ------------------------------------------------------------------
    # Accessors and diagnostics
    # ------------------------------------------------------------------

    @property
    def dispatch_count(self) -> int:
        return self._dispatch_count

    @property
    def history(self) -> list[HVDCResult]:
        return list(self._history)

    def total_arbitrage_usd(self) -> float:
        """Sum of all arbitrage revenue from session history."""
        return round(sum(r.arbitrage_usd for r in self._history), 2)

    def average_spread_usd_mwh(self) -> float:
        """Average price spread across all dispatches in session."""
        if not self._history:
            return 0.0
        return round(sum(r.price_spread for r in self._history) / len(self._history), 2)
