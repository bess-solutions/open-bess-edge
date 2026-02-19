"""
src/interfaces/vpp_publisher.py
================================
BESSAI Edge Gateway — Virtual Power Plant (VPP) Publisher.

Aggregates flexible capacity signals from multiple BESSAI edge sites and
publishes OpenADR 3.0-compatible EiEvent payloads.

This implementation provides:
- Aggregation of per-site SOC and power into fleet-level flex capacity
- OpenADR 3.0 JSON event payload generation (stub — wire to real broker in prod)
- Prometheus metrics for VPP monitoring

OpenADR 3.0 reference: https://www.openadr.org/
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import structlog

from .metrics import VPP_FLEX_CAPACITY_KW, VPP_EVENTS_PUBLISHED_TOTAL

__all__ = ["SiteCapacity", "VPPPublisher", "OpenADREvent"]

log = structlog.get_logger(__name__)


@dataclass
class SiteCapacity:
    """Flex capacity report from a single BESSAI edge site.

    Attributes:
        site_id:        Unique site identifier.
        soc_pct:        Current State of Charge (%).
        max_power_kw:   Max charge/discharge power at this site (kW).
        available_kw:   Currently dispatchable power (signed: + discharge, - charge).
    """
    site_id: str
    soc_pct: float
    max_power_kw: float
    available_kw: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class OpenADREvent:
    """OpenADR 3.0 EiEvent payload (simplified).

    Fields follow the OpenADR 3.0 YAML schema:
    https://github.com/openadr/openADR3-EPRI
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    program_id: str = "BESSAI-VPP-001"
    event_name: str = "FLEX_DISPATCH"
    priority: int = 1
    targets: list[dict] = field(default_factory=list)
    intervals: list[dict] = field(default_factory=list)
    payload_descriptors: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """Serialize to OpenADR 3.0 JSON format."""
        return json.dumps({
            "objectType": "EVENT",
            "programID": self.program_id,
            "eventName": self.event_name,
            "priority": self.priority,
            "targets": self.targets,
            "reportDescriptors": None,
            "payloadDescriptors": self.payload_descriptors,
            "intervalPeriod": {
                "start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.created_at)),
                "duration": "PT15M",
                "randomizeStart": "PT0S",
            },
            "intervals": self.intervals,
        }, indent=2)


class VPPPublisher:
    """Aggregates BESSAI edge sites and publishes VPP flex capacity events.

    Parameters:
        program_id:     OpenADR 3.0 program identifier.
        min_flex_kw:    Minimum aggregated flex to publish an event (kW).
        site_id:        Publisher site ID for Prometheus labels.
    """

    def __init__(
        self,
        program_id: str = "BESSAI-VPP-001",
        min_flex_kw: float = 10.0,
        site_id: str = "fleet",
    ) -> None:
        self.program_id = program_id
        self.min_flex_kw = min_flex_kw
        self.site_id = site_id
        self._sites: dict[str, SiteCapacity] = {}

    # ------------------------------------------------------------------
    # Site registration
    # ------------------------------------------------------------------

    def register_site(self, capacity: SiteCapacity) -> None:
        """Register or update a site's capacity report."""
        self._sites[capacity.site_id] = capacity
        log.debug(
            "vpp.site_registered",
            site_id=capacity.site_id,
            available_kw=capacity.available_kw,
            soc_pct=capacity.soc_pct,
        )

    def remove_site(self, site_id: str) -> None:
        """Remove a site from the fleet."""
        self._sites.pop(site_id, None)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def aggregate_flex_kw(self) -> float:
        """Return total aggregated flex capacity across all registered sites."""
        return sum(s.available_kw for s in self._sites.values())

    def fleet_avg_soc(self) -> float:
        """Return fleet-weighted average SOC (%)."""
        if not self._sites:
            return 0.0
        return sum(s.soc_pct for s in self._sites.values()) / len(self._sites)

    def publish_event(self, flex_request_kw: Optional[float] = None) -> Optional[OpenADREvent]:
        """Aggregate flex capacity and publish an OpenADR 3.0 event.

        Args:
            flex_request_kw: Requested dispatch power. If None, uses full aggregate.

        Returns:
            OpenADREvent if published, None if below min_flex_kw threshold.
        """
        total_flex = self.aggregate_flex_kw()
        dispatch_kw = flex_request_kw if flex_request_kw is not None else total_flex

        # Update Prometheus
        VPP_FLEX_CAPACITY_KW.labels(site_id=self.site_id).set(total_flex)

        if abs(total_flex) < self.min_flex_kw:
            log.debug(
                "vpp.below_threshold",
                total_flex_kw=round(total_flex, 2),
                min_flex_kw=self.min_flex_kw,
            )
            return None

        # Build event
        targets = [
            {"type": "RESOURCE_NAME", "values": [s.site_id]}
            for s in self._sites.values()
        ]
        intervals = [{
            "id": 1,
            "payloads": [{"type": "SIMPLE", "values": [dispatch_kw]}],
        }]
        payload_descriptors = [{
            "objectType": "EVENT_PAYLOAD_DESCRIPTOR",
            "payloadType": "SIMPLE",
            "units": "KW",
            "currency": None,
        }]

        event = OpenADREvent(
            program_id=self.program_id,
            event_name="FLEX_DISPATCH",
            targets=targets,
            intervals=intervals,
            payload_descriptors=payload_descriptors,
        )

        VPP_EVENTS_PUBLISHED_TOTAL.labels(site_id=self.site_id).inc()
        log.info(
            "vpp.event_published",
            event_id=event.event_id,
            total_flex_kw=round(total_flex, 2),
            dispatch_kw=round(dispatch_kw, 2),
            n_sites=len(self._sites),
            fleet_soc_pct=round(self.fleet_avg_soc(), 1),
        )
        return event

    @property
    def n_sites(self) -> int:
        """Number of registered sites."""
        return len(self._sites)
