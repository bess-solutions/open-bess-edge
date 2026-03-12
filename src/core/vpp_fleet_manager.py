# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/vpp_fleet_manager.py
================================
BESSAI Edge Gateway — VPP Fleet Manager (BEP-0400).

Coordinates FleetOrchestrator + VPPPublisher + ONNX DRL dispatch in a
single control loop. This is the "brain" that bridges per-site telemetry
to fleet-level market participation.

Architecture::

    ┌─────────────────────────────────────────────────┐
    │            VPPFleetManager (BEP-0400)           │
    │                                                 │
    │  FleetOrchestrator ──► aggregate()  ─────────► │
    │                                                 │
    │  MarketPrice feed ──► dispatch_strategy() ───► │
    │                                                 │
    │  ONNX DRL (optional) ──► recommend_kw() ─────► │
    │                          ▼                     │
    │  VPPPublisher.publish_event(dispatch_kw)        │
    │                          ▼                     │
    │  SiteSetpoints: per-site kW allocation          │
    └─────────────────────────────────────────────────┘

BEP-0400 spec reference:
  docs/bep/BEP-0400.md (to be created)

Usage::

    mgr = VPPFleetManager(
        fleet=FleetOrchestrator(),
        vpp=VPPPublisher(program_id="BESSAI-VPP-SEN"),
    )
    mgr.add_site("CL-001", SiteProxy("10.0.1.50", capacity_kwh=200))
    mgr.add_site("CL-002", SiteProxy("10.0.1.51", capacity_kwh=500))

    result = mgr.run_cycle(market_price_usd_mwh=95.0)
    print(result.event)       # OpenADREvent or None
    print(result.setpoints)   # {site_id: kW}
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

from src.core.fleet_orchestrator import FleetOrchestrator, FleetSummary, SiteProxy
from src.interfaces.vpp_publisher import OpenADREvent, SiteCapacity, VPPPublisher

__all__ = [
    "VPPFleetManager",
    "DispatchStrategy",
    "CycleResult",
    "SiteSetpoint",
]

log = structlog.get_logger(__name__)


class DispatchStrategy(str, Enum):
    """Dispatch strategy selector for the VPP Fleet Manager.

    PRICE_ARBITRAGE: Discharge when market price > threshold, charge otherwise.
    PEAK_SHAVING:    Minimize peak grid draw (load-follower mode).
    FREQUENCY_REG:   Fast response mode for frequency regulation services.
    DRL:             ONNX DRL agent makes the decision (BEP-0200 Phase 3).
    HOLD:            Do not dispatch (maintenance / forced idle).
    """

    PRICE_ARBITRAGE = "price_arbitrage"
    PEAK_SHAVING = "peak_shaving"
    FREQUENCY_REG = "frequency_reg"
    DRL = "drl"
    HOLD = "hold"


@dataclass
class SiteSetpoint:
    """Per-site dispatch setpoint computed by the fleet manager."""

    site_id: str
    target_kw: float  # + discharge, - charge, 0 = hold
    strategy: DispatchStrategy
    rationale: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class CycleResult:
    """Result of a single VPP fleet management cycle."""

    fleet_summary: FleetSummary
    strategy: DispatchStrategy
    total_dispatch_kw: float
    setpoints: list[SiteSetpoint]
    event: OpenADREvent | None
    market_price_usd_mwh: float
    cycle_duration_s: float
    timestamp: float = field(default_factory=time.time)

    @property
    def n_sites(self) -> int:
        return self.fleet_summary.n_sites

    @property
    def dispatching(self) -> bool:
        return self.event is not None

    def summary_log(self) -> dict[str, Any]:
        return {
            "n_sites": self.n_sites,
            "strategy": self.strategy.value,
            "total_dispatch_kw": round(self.total_dispatch_kw, 2),
            "event_id": self.event.event_id if self.event else None,
            "fleet_soc_pct": round(self.fleet_summary.fleet_soc_pct, 1),
            "alarms": self.fleet_summary.sites_in_alarm,
            "market_price": round(self.market_price_usd_mwh, 2),
            "duration_s": round(self.cycle_duration_s, 4),
        }


class VPPFleetManager:
    """Coordinator between FleetOrchestrator, VPPPublisher, and ONNX DRL dispatch.

    Parameters:
        fleet:                  FleetOrchestrator instance (manages site proxies).
        vpp:                    VPPPublisher instance (builds OpenADR events).
        default_strategy:       Default dispatch strategy when no DRL model loaded.
        discharge_threshold:    Market price (USD/MWh) above which to discharge.
        charge_threshold:       Market price (USD/MWh) below which to charge.
        max_discharge_pct:      Fraction of available_kw to dispatch (0-1).
        min_soc_pct:            Never discharge below this SOC (safety guard).
        max_soc_pct:            Never charge above this SOC (safety guard).
        min_fleet_sites:        Skip dispatch if fewer sites are responsive.
    """

    def __init__(
        self,
        fleet: FleetOrchestrator | None = None,
        vpp: VPPPublisher | None = None,
        default_strategy: DispatchStrategy = DispatchStrategy.PRICE_ARBITRAGE,
        discharge_threshold: float = 80.0,  # USD/MWh — discharge above this
        charge_threshold: float = 40.0,  # USD/MWh — charge below this
        max_discharge_pct: float = 0.85,  # use up to 85% of available flex
        min_soc_pct: float = 15.0,  # safety floor
        max_soc_pct: float = 95.0,  # safety ceiling
        min_fleet_sites: int = 1,
    ) -> None:
        self._fleet = fleet or FleetOrchestrator()
        self._vpp = vpp or VPPPublisher()
        self.default_strategy = default_strategy
        self.discharge_threshold = discharge_threshold
        self.charge_threshold = charge_threshold
        self.max_discharge_pct = max_discharge_pct
        self.min_soc_pct = min_soc_pct
        self.max_soc_pct = max_soc_pct
        self.min_fleet_sites = min_fleet_sites
        self._cycle_count: int = 0
        self._last_result: CycleResult | None = None

    # ------------------------------------------------------------------
    # Site management (delegates to fleet orchestrator)
    # ------------------------------------------------------------------

    def add_site(self, site_id: str, proxy: SiteProxy) -> None:
        """Register a site with the fleet orchestrator."""
        self._fleet.register_site(site_id, proxy)
        log.info("vpp_fleet.site_added", site_id=site_id, n_sites=self._fleet.n_sites)

    def remove_site(self, site_id: str) -> None:
        """Remove a site from the fleet."""
        self._fleet.remove_site(site_id)
        self._vpp.remove_site(site_id)
        log.info("vpp_fleet.site_removed", site_id=site_id)

    @property
    def n_sites(self) -> int:
        return self._fleet.n_sites

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    def _select_strategy(
        self,
        market_price: float,
        summary: FleetSummary,
    ) -> DispatchStrategy:
        """Determine dispatch strategy based on market price and fleet state."""
        if summary.sites_in_alarm > summary.n_sites // 2:
            return DispatchStrategy.HOLD  # majority of fleet in alarm → hold
        if market_price >= self.discharge_threshold:
            return DispatchStrategy.PRICE_ARBITRAGE
        if market_price <= self.charge_threshold:
            return DispatchStrategy.PRICE_ARBITRAGE  # still arbitrage (charging)
        return DispatchStrategy.HOLD  # price in neutral band → hold

    # ------------------------------------------------------------------
    # Setpoint computation
    # ------------------------------------------------------------------

    def _compute_setpoints(
        self,
        fleet_telemetries: list,
        strategy: DispatchStrategy,
        market_price: float,
    ) -> tuple[list[SiteSetpoint], float]:
        """Compute per-site setpoints and total dispatch kW.

        Returns:
            (setpoints, total_dispatch_kw)
        """
        if strategy == DispatchStrategy.HOLD or not fleet_telemetries:
            setpoints = [
                SiteSetpoint(
                    site_id=t.site_id,
                    target_kw=0.0,
                    strategy=strategy,
                    rationale="hold — neutral price band or alarm",
                )
                for t in fleet_telemetries
            ]
            return setpoints, 0.0

        discharging = market_price >= self.discharge_threshold
        setpoints: list[SiteSetpoint] = []
        total_kw = 0.0

        for t in fleet_telemetries:
            if t.anomaly_score > 0.7:
                # Site in alarm — always hold
                setpoints.append(
                    SiteSetpoint(
                        site_id=t.site_id,
                        target_kw=0.0,
                        strategy=DispatchStrategy.HOLD,
                        rationale=f"anomaly_score={t.anomaly_score:.2f} > 0.7",
                    )
                )
                continue

            if discharging:
                # Price-driven discharge
                if t.soc_pct <= self.min_soc_pct:
                    target = 0.0
                    rationale = f"SOC {t.soc_pct:.1f}% at floor {self.min_soc_pct}%"
                else:
                    target = t.available_kw * self.max_discharge_pct
                    rationale = (
                        f"discharge price={market_price:.1f} > "
                        f"threshold={self.discharge_threshold:.1f} USD/MWh"
                    )
            else:
                # Price-driven charge
                if t.soc_pct >= self.max_soc_pct:
                    target = 0.0
                    rationale = f"SOC {t.soc_pct:.1f}% at ceiling {self.max_soc_pct}%"
                else:
                    # Charge at 60% of available capacity (avoid grid overload)
                    target = -t.available_kw * 0.6
                    rationale = (
                        f"charge price={market_price:.1f} < "
                        f"threshold={self.charge_threshold:.1f} USD/MWh"
                    )

            setpoints.append(
                SiteSetpoint(
                    site_id=t.site_id,
                    target_kw=round(target, 2),
                    strategy=strategy,
                    rationale=rationale,
                )
            )
            total_kw += target

        return setpoints, round(total_kw, 2)

    # ------------------------------------------------------------------
    # VPP registration from telemetry
    # ------------------------------------------------------------------

    def _sync_vpp_sites(self, fleet_telemetries: list) -> None:
        """Update VPPPublisher capacity reports from latest telemetry."""
        for t in fleet_telemetries:
            capacity = SiteCapacity(
                site_id=t.site_id,
                soc_pct=t.soc_pct,
                max_power_kw=t.capacity_kwh * 0.5,  # C/2 rate
                available_kw=t.available_kw,
            )
            self._vpp.register_site(capacity)

    # ------------------------------------------------------------------
    # Main control cycle
    # ------------------------------------------------------------------

    def run_cycle(
        self,
        market_price_usd_mwh: float = 60.0,
        strategy_override: DispatchStrategy | None = None,
    ) -> CycleResult:
        """Run one VPP fleet management cycle.

        Steps:
            1. Poll all sites via FleetOrchestrator.poll_all()
            2. Aggregate fleet KPIs
            3. Select dispatch strategy
            4. Compute per-site setpoints
            5. Sync VPP capacity reports
            6. Publish OpenADR event (if above threshold)
            7. Return CycleResult

        Args:
            market_price_usd_mwh:  Real-time market price (USD or local currency /MWh).
            strategy_override:     Force a specific strategy (ignores price signals).

        Returns:
            CycleResult with fleet summary, setpoints, and OpenADR event.
        """
        t0 = time.perf_counter()
        self._cycle_count += 1

        # Step 1: Poll fleet
        fleet_summary = self._fleet.run_cycle()

        # Step 2: Safety check — skip if below minimum responsive sites
        if fleet_summary.n_sites < self.min_fleet_sites:
            log.warning(
                "vpp_fleet.insufficient_sites",
                n_sites=fleet_summary.n_sites,
                min_sites=self.min_fleet_sites,
            )
            result = CycleResult(
                fleet_summary=fleet_summary,
                strategy=DispatchStrategy.HOLD,
                total_dispatch_kw=0.0,
                setpoints=[],
                event=None,
                market_price_usd_mwh=market_price_usd_mwh,
                cycle_duration_s=time.perf_counter() - t0,
            )
            self._last_result = result
            return result

        # Get raw telemetries for per-site setpoints
        import asyncio  # noqa: PLC0415 — local import for async loop handling

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        fleet_telemetries = loop.run_until_complete(self._fleet.poll_all())

        # Step 3: Select strategy
        strategy = strategy_override or self._select_strategy(market_price_usd_mwh, fleet_summary)

        # Step 4: Compute setpoints
        setpoints, total_kw = self._compute_setpoints(
            fleet_telemetries, strategy, market_price_usd_mwh
        )

        # Step 5: Sync VPP capacity
        self._sync_vpp_sites(fleet_telemetries)

        # Step 6: Publish VPP event
        event = self._vpp.publish_event(flex_request_kw=total_kw) if total_kw != 0.0 else None

        duration = time.perf_counter() - t0

        result = CycleResult(
            fleet_summary=fleet_summary,
            strategy=strategy,
            total_dispatch_kw=total_kw,
            setpoints=setpoints,
            event=event,
            market_price_usd_mwh=market_price_usd_mwh,
            cycle_duration_s=duration,
        )
        self._last_result = result

        log.info("vpp_fleet.cycle_complete", **result.summary_log())
        return result

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_result(self) -> CycleResult | None:
        return self._last_result

    @property
    def fleet(self) -> FleetOrchestrator:
        return self._fleet

    @property
    def vpp(self) -> VPPPublisher:
        return self._vpp
