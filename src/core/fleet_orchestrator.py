"""
src/core/fleet_orchestrator.py
================================
BESSAI Edge Gateway — Multi-Site Fleet Orchestrator.

Manages telemetry, dispatch, and federated learning coordination across
multiple BESSAI edge sites from a single orchestration process.

Architecture:
  - FleetOrchestrator is instantiated once per aggregation tier
  - Each SiteProxy represents a remote BESSAI edge gateway
  - Orchestrator polls sites, aggregates fleet KPIs, triggers VPP events

Typical deployment:
  - 1 fleet orchestrator per VPP control zone (e.g., per electricity market)
  - Each orchestrator coordinates N=5..50 BESSAI edge gateways
  - Communicates with edge via REST/gRPC (stub → mTLS in prod)

Usage::

    orch = FleetOrchestrator(vpp=VPPPublisher(), lca=LCAEngine())
    orch.register_site("CL-001", SiteProxy("10.0.1.50", capacity_kwh=100))
    orch.register_site("CL-002", SiteProxy("10.0.1.51", capacity_kwh=200))
    summary = orch.run_cycle()
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import structlog

from src.interfaces.metrics import (
    FLEET_SITES_ACTIVE,
    FLEET_TOTAL_CAPACITY_KWH,
)

__all__ = [
    "FleetOrchestrator",
    "SiteProxy",
    "SiteTelemetry",
    "FleetSummary",
]

log = structlog.get_logger(__name__)


@dataclass
class SiteTelemetry:
    """Telemetry snapshot from a single BESSAI edge site."""

    site_id: str
    soc_pct: float  # 0-100
    power_kw: float  # + = charging, - = discharging
    temp_c: float
    capacity_kwh: float
    available_kw: float
    anomaly_score: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class FleetSummary:
    """Aggregated fleet KPIs for one orchestration cycle."""

    n_sites: int
    total_capacity_kwh: float
    fleet_soc_pct: float  # weighted average SOC
    total_power_kw: float  # sum of all site power (kW)
    total_available_kw: float  # sum of flex capacity
    sites_in_alarm: int  # sites with anomaly_score > 0.7
    cycle_duration_s: float
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return (
            f"FleetSummary(n={self.n_sites}, "
            f"soc={self.fleet_soc_pct:.1f}%, "
            f"power={self.total_power_kw:.1f}kW, "
            f"flex={self.total_available_kw:.1f}kW)"
        )


class SiteProxy:
    """Proxy representing a remote BESSAI edge site.

    In production this would use an async httpx/gRPC call.
    In simulation / testing, inject a ``telemetry_fn`` callback.

    Parameters:
        host:           IP/hostname of the remote site.
        site_id:        Unique site identifier.
        capacity_kwh:   Nameplate BESS capacity.
        telemetry_fn:   Optional callable returning SiteTelemetry (for testing).
    """

    def __init__(
        self,
        host: str,
        site_id: str = "unknown",
        capacity_kwh: float = 100.0,
        telemetry_fn: Callable[[str], SiteTelemetry] | None = None,
    ) -> None:
        self.host = host
        self.site_id = site_id
        self.capacity_kwh = capacity_kwh
        self._telemetry_fn = telemetry_fn
        self._last_telemetry: SiteTelemetry | None = None

    async def fetch_telemetry(self) -> SiteTelemetry:
        """Fetch current telemetry from this site.

        Returns:
            SiteTelemetry — from inject fn (test), or a realistic stub.
        """
        if self._telemetry_fn is not None:
            tel = self._telemetry_fn(self.site_id)
            self._last_telemetry = tel
            return tel

        # Production stub — would be: async with httpx.AsyncClient() as c: ...
        stub = SiteTelemetry(
            site_id=self.site_id,
            soc_pct=60.0,
            power_kw=0.0,
            temp_c=28.0,
            capacity_kwh=self.capacity_kwh,
            available_kw=self.capacity_kwh * 0.5,  # 50% flex
        )
        self._last_telemetry = stub
        return stub

    @property
    def last_telemetry(self) -> SiteTelemetry | None:
        return self._last_telemetry


class FleetOrchestrator:
    """Multi-site BESS fleet orchestrator.

    Parameters:
        site_id:            Identifier for Prometheus labels.
        anomaly_threshold:  Score above which a site is counted as 'in alarm'.
    """

    def __init__(
        self,
        site_id: str = "fleet",
        anomaly_threshold: float = 0.7,
    ) -> None:
        self.site_id = site_id
        self.anomaly_threshold = anomaly_threshold
        self._sites: dict[str, SiteProxy] = {}

    # ------------------------------------------------------------------
    # Site management
    # ------------------------------------------------------------------

    def register_site(self, site_id: str, proxy: SiteProxy) -> None:
        """Register a remote site under the given ID."""
        self._sites[site_id] = proxy
        FLEET_SITES_ACTIVE.labels(site_id=self.site_id).set(len(self._sites))
        log.info("fleet.site_registered", site_id=site_id, host=proxy.host)

    def remove_site(self, site_id: str) -> None:
        """Remove a site from the fleet."""
        self._sites.pop(site_id, None)
        FLEET_SITES_ACTIVE.labels(site_id=self.site_id).set(len(self._sites))
        log.info("fleet.site_removed", site_id=site_id)

    @property
    def n_sites(self) -> int:
        return len(self._sites)

    @property
    def total_capacity_kwh(self) -> float:
        return sum(p.capacity_kwh for p in self._sites.values())

    # ------------------------------------------------------------------
    # Orchestration cycle
    # ------------------------------------------------------------------

    async def poll_all(self) -> list[SiteTelemetry]:
        """Poll all registered sites concurrently.

        Returns:
            List of SiteTelemetry objects (one per site).
        """
        coros = [proxy.fetch_telemetry() for proxy in self._sites.values()]
        results = await asyncio.gather(*coros, return_exceptions=True)
        telemetries: list[SiteTelemetry] = []
        for result in results:
            if isinstance(result, BaseException):
                log.error("fleet.poll_error", error=str(result))
            elif isinstance(result, SiteTelemetry):
                telemetries.append(result)
        return telemetries

    def aggregate(self, telemetries: list[SiteTelemetry]) -> FleetSummary:
        """Aggregate telemetry list into a FleetSummary.

        Args:
            telemetries: List of SiteTelemetry dataclasses.

        Returns:
            FleetSummary KPIs.
        """
        if not telemetries:
            return FleetSummary(
                n_sites=0,
                total_capacity_kwh=0.0,
                fleet_soc_pct=0.0,
                total_power_kw=0.0,
                total_available_kw=0.0,
                sites_in_alarm=0,
                cycle_duration_s=0.0,
            )

        total_cap = sum(t.capacity_kwh for t in telemetries)
        weighted_soc = (
            sum(t.soc_pct * t.capacity_kwh for t in telemetries) / total_cap
            if total_cap > 0
            else 0.0
        )
        total_power = sum(t.power_kw for t in telemetries)
        total_avail = sum(t.available_kw for t in telemetries)
        alarms = sum(1 for t in telemetries if t.anomaly_score > self.anomaly_threshold)

        # Update Prometheus
        FLEET_TOTAL_CAPACITY_KWH.labels(site_id=self.site_id).set(total_cap)
        FLEET_SITES_ACTIVE.labels(site_id=self.site_id).set(len(telemetries))

        return FleetSummary(
            n_sites=len(telemetries),
            total_capacity_kwh=total_cap,
            fleet_soc_pct=weighted_soc,
            total_power_kw=total_power,
            total_available_kw=total_avail,
            sites_in_alarm=alarms,
            cycle_duration_s=0.0,  # populated by run_cycle()
        )

    def run_cycle(self) -> FleetSummary:
        """Run a synchronous orchestration cycle (wraps async poll_all).

        Returns:
            FleetSummary with aggregated fleet KPIs.
        """
        t0 = time.perf_counter()
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        telemetries = loop.run_until_complete(self.poll_all())
        summary = self.aggregate(telemetries)
        summary.cycle_duration_s = time.perf_counter() - t0

        log.info(
            "fleet.cycle_complete",
            n_sites=summary.n_sites,
            fleet_soc=round(summary.fleet_soc_pct, 1),
            total_power_kw=round(summary.total_power_kw, 1),
            alarms=summary.sites_in_alarm,
            duration_s=round(summary.cycle_duration_s, 4),
        )
        return summary
