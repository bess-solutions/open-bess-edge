# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/fleet_coordinator.py
======================================
BESSAI Edge Gateway — Fleet Coordinator v1.0

Manages a virtual fleet of BESSAI edge sites, computes aggregate flex
capacity, distributes power setpoints per site, and exposes fleet-level
status for OpenADR 3.0 VPP dispatch.

Usage::

    from src.interfaces.fleet_coordinator import FleetCoordinator, FleetSiteState

    coord = FleetCoordinator(min_flex_kw=50.0)
    coord.register_site(FleetSiteState(
        site_id="SITE-01", node="Maitencillo", soc_pct=65.0,
        max_power_kw=500.0, current_power_kw=0.0
    ))
    summary = coord.fleet_summary()
    setpoints = coord.compute_setpoints(dispatch_kw=300.0)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import structlog

__all__ = ["FleetCoordinator", "FleetSiteState", "SiteSetpoint"]

log = structlog.get_logger(__name__)

# Seconds after which a site is considered stale/offline
SITE_STALE_THRESHOLD_S = 300  # 5 minutes


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FleetSiteState:
    """Live state reported by a single BESSAI edge site.

    Attributes:
        site_id:        Unique identifier for the site (e.g., "SITE-MAIT-01").
        node:           SEN node name (e.g., "Maitencillo").
        soc_pct:        State of Charge percentage [0-100].
        max_power_kw:   Maximum rated power for charge/discharge (kW).
        current_power_kw: Active power setpoint (+ charge, - discharge).
        temperature_c:  Optional battery temperature (°C). Used for derating.
        cycle_count:    Estimated full-cycle count (for degradation tracking).
        last_seen:      Unix timestamp of last telemetry update.
    """

    site_id: str
    node: str
    soc_pct: float
    max_power_kw: float
    current_power_kw: float = 0.0
    temperature_c: float | None = None
    cycle_count: int = 0
    last_seen: float = field(default_factory=time.time)

    @property
    def available_discharge_kw(self) -> float:
        """Max dispatchable discharge power accounting for SoC floor (10%)."""
        usable_soc = max(0.0, self.soc_pct - 10.0)
        return min(self.max_power_kw, usable_soc / 100 * self.max_power_kw * 2)

    @property
    def available_charge_kw(self) -> float:
        """Max charge power accounting for SoC ceiling (95%)."""
        headroom_soc = max(0.0, 95.0 - self.soc_pct)
        return min(self.max_power_kw, headroom_soc / 100 * self.max_power_kw * 2)

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.last_seen) > SITE_STALE_THRESHOLD_S

    @property
    def is_overtemperature(self) -> bool:
        return self.temperature_c is not None and self.temperature_c > 45.0

    def to_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "node": self.node,
            "soc_pct": round(self.soc_pct, 1),
            "max_power_kw": self.max_power_kw,
            "current_power_kw": round(self.current_power_kw, 1),
            "available_discharge_kw": round(self.available_discharge_kw, 1),
            "available_charge_kw": round(self.available_charge_kw, 1),
            "temperature_c": self.temperature_c,
            "cycle_count": self.cycle_count,
            "is_stale": self.is_stale,
            "is_overtemperature": self.is_overtemperature,
            "last_seen": self.last_seen,
        }


@dataclass
class SiteSetpoint:
    """Power setpoint dispatched to one site.

    Attributes:
        site_id:    Target site.
        power_kw:   Signed power (+ = charge, - = discharge).
        reason:     Why this setpoint was chosen (for logging/audit).
    """

    site_id: str
    power_kw: float
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "power_kw": round(self.power_kw, 1),
            "reason": self.reason,
        }


# ─────────────────────────────────────────────────────────────────────────────
# FleetCoordinator
# ─────────────────────────────────────────────────────────────────────────────

class FleetCoordinator:
    """Coordinates power dispatch across a fleet of BESSAI edge sites.

    Priority order for dispatch allocation:
    1. Exclude stale and over-temperature sites.
    2. Sort by available capacity (highest first) for discharge dispatch.
    3. Distribute requested power proportionally to available capacity.
    4. Respect individual site max_power_kw and SoC limits.

    Parameters:
        min_flex_kw:    Minimum total fleet flex to consider dispatching (kW).
        program_id:     VPP program identifier for OpenADR events.
    """

    def __init__(
        self,
        min_flex_kw: float = 50.0,
        program_id: str = "BESSAI-VPP-001",
    ) -> None:
        self.min_flex_kw = min_flex_kw
        self.program_id = program_id
        self._sites: dict[str, FleetSiteState] = {}

    # ── Site registry ─────────────────────────────────────────────────────────

    def register_site(self, site: FleetSiteState) -> None:
        """Add or refresh a site in the fleet registry."""
        self._sites[site.site_id] = site
        log.debug("fleet.site_registered", site_id=site.site_id,
                  soc_pct=site.soc_pct, max_power_kw=site.max_power_kw)

    def update_site(self, site_id: str, **kwargs) -> None:
        """Update telemetry fields for an existing site."""
        if site_id not in self._sites:
            raise KeyError(f"Site {site_id!r} not registered")
        site = self._sites[site_id]
        for k, v in kwargs.items():
            if hasattr(site, k):
                setattr(site, k, v)
        site.last_seen = time.time()

    def remove_site(self, site_id: str) -> None:
        """Remove a site from the fleet."""
        self._sites.pop(site_id, None)
        log.info("fleet.site_removed", site_id=site_id)

    @property
    def active_sites(self) -> list[FleetSiteState]:
        """Sites that are online, not stale, and not overtemperature."""
        return [
            s for s in self._sites.values()
            if not s.is_stale and not s.is_overtemperature
        ]

    @property
    def n_sites(self) -> int:
        return len(self._sites)

    @property
    def n_active_sites(self) -> int:
        return len(self.active_sites)

    # ── Aggregation ───────────────────────────────────────────────────────────

    def total_flex_kw(self, mode: str = "discharge") -> float:
        """Aggregate available flex power across all active sites.

        Args:
            mode: 'discharge' (default) or 'charge'.
        """
        sites = self.active_sites
        if not sites:
            return 0.0
        if mode == "discharge":
            return sum(s.available_discharge_kw for s in sites)
        return sum(s.available_charge_kw for s in sites)

    def fleet_avg_soc(self) -> float:
        """Fleet-weighted average State of Charge (%)."""
        sites = self.active_sites
        if not sites:
            return 0.0
        return sum(s.soc_pct for s in sites) / len(sites)

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def compute_setpoints(
        self,
        dispatch_kw: float,
        mode: str = "discharge",
    ) -> list[SiteSetpoint]:
        """Distribute a requested power level across active sites.

        Allocation strategy: proportional to each site's available capacity.

        Args:
            dispatch_kw: Total power to dispatch (positive value).
            mode:        'discharge' or 'charge'.

        Returns:
            List of SiteSetpoint — one per active site.
        """
        sites = self.active_sites
        if not sites:
            log.warning("fleet.no_active_sites")
            return []

        total_available = self.total_flex_kw(mode)
        if total_available < self.min_flex_kw:
            log.info("fleet.below_min_flex",
                     total_available_kw=round(total_available, 1),
                     min_flex_kw=self.min_flex_kw)
            return [SiteSetpoint(s.site_id, 0.0, "below_min_flex") for s in sites]

        capped = min(dispatch_kw, total_available)
        setpoints: list[SiteSetpoint] = []

        for site in sites:
            cap = (site.available_discharge_kw if mode == "discharge"
                   else site.available_charge_kw)
            if total_available > 0:
                share = (cap / total_available) * capped
            else:
                share = 0.0
            # Apply sign convention: discharge = negative power
            signed = -round(share, 1) if mode == "discharge" else round(share, 1)
            setpoints.append(SiteSetpoint(
                site_id=site.site_id,
                power_kw=signed,
                reason=f"proportional_{mode}",
            ))
            log.debug("fleet.setpoint", site_id=site.site_id,
                      power_kw=signed, mode=mode)

        log.info("fleet.setpoints_computed",
                 n_sites=len(setpoints), dispatch_kw=capped,
                 mode=mode, total_available_kw=round(total_available, 1))
        return setpoints

    # ── Summary ───────────────────────────────────────────────────────────────

    def fleet_summary(self) -> dict:
        """Return a fleet-wide status dictionary for API/dashboard use."""
        stale = [s.site_id for s in self._sites.values() if s.is_stale]
        overtemp = [s.site_id for s in self._sites.values() if s.is_overtemperature]
        return {
            "n_sites": self.n_sites,
            "n_active": self.n_active_sites,
            "stale_sites": stale,
            "overtemp_sites": overtemp,
            "fleet_avg_soc_pct": round(self.fleet_avg_soc(), 1),
            "total_discharge_flex_kw": round(self.total_flex_kw("discharge"), 1),
            "total_charge_flex_kw": round(self.total_flex_kw("charge"), 1),
            "program_id": self.program_id,
            "sites": [s.to_dict() for s in self._sites.values()],
        }
