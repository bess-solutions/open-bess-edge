# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/core/ernc_registry.py
==========================
ERNC Registry — Ley 21.185 (GAP-008).

Tracks ERNC (Energías Renovables No Convencionales) compliance for
BESS + renewable generation as required by Chilean Ley 21.185, which
establishes obligations for utilities and generators to meet renewable
energy portfolio standards.

Key Requirements (Ley 21.185)
------------------------------
* BESS charged exclusively from renewable sources qualifies for ERNC
  certificate (Certificado de Energía Renovable — CER).
* Non-renewable charging must be tracked separately.
* Monthly CER generation report must be submitted to CNE.

Usage::

    registry = ERNCRegistry(site_id="PMGD-001-BESS")
    registry.record_charge(energy_kwh=100.0, source="solar")
    registry.record_charge(energy_kwh=20.0, source="grid")
    cert = registry.ernc_certificate()
    # cert.ernc_fraction == 0.833...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)

_ERNC_SOURCES = frozenset({"solar", "wind", "hydro", "geothermal", "biomass", "tidal"})


@dataclass
class ERNCCertificate:
    """Snapshot of ERNC compliance for reporting to CNE."""

    site_id: str
    period_start: str
    period_end: str
    ernc_kwh: float           # kWh charged from renewable sources
    non_ernc_kwh: float       # kWh charged from non-renewable sources
    ernc_fraction: float      # ernc_kwh / total_kwh
    qualifies: bool           # True if ernc_fraction >= minimum threshold
    threshold_pct: float      # Required minimum (default 99.0 %)


class ERNCRegistry:
    """
    ERNC energy tracking and certification engine.

    Parameters
    ----------
    site_id:
        Site identifier for the CER report.
    min_ernc_pct:
        Minimum renewable fraction to qualify for ERNC certificate (default 99.0 %).
    """

    def __init__(self, site_id: str, min_ernc_pct: float = 99.0) -> None:
        self._site_id = site_id
        self._min_pct = min_ernc_pct
        self._ernc_kwh: float = 0.0
        self._non_ernc_kwh: float = 0.0
        self._period_start = datetime.now(timezone.utc).isoformat()

        log.info("ernc_registry.initialized", site_id=site_id,
                 min_ernc_pct=min_ernc_pct, norm_ref="Ley 21.185")

    def record_charge(self, energy_kwh: float, source: str) -> None:
        """
        Record a charging event.

        Parameters
        ----------
        energy_kwh:
            Energy charged in kWh (must be positive).
        source:
            Energy source string. ERNC-qualifying: "solar", "wind", "hydro",
            "geothermal", "biomass", "tidal". Anything else = non-ERNC.
        """
        if energy_kwh < 0:
            raise ValueError(f"energy_kwh must be >= 0, got {energy_kwh}")

        is_ernc = source.lower() in _ERNC_SOURCES
        if is_ernc:
            self._ernc_kwh += energy_kwh
        else:
            self._non_ernc_kwh += energy_kwh

        log.debug("ernc.charge_recorded", energy_kwh=energy_kwh,
                  source=source, is_ernc=is_ernc)

    def ernc_fraction(self) -> float:
        """Current ERNC fraction [0, 1]."""
        total = self._ernc_kwh + self._non_ernc_kwh
        return self._ernc_kwh / total if total > 0 else 0.0

    def ernc_certificate(self) -> ERNCCertificate:
        """Generate the current period ERNC certificate for CNE submission."""
        fraction = self.ernc_fraction()
        cert = ERNCCertificate(
            site_id=self._site_id,
            period_start=self._period_start,
            period_end=datetime.now(timezone.utc).isoformat(),
            ernc_kwh=self._ernc_kwh,
            non_ernc_kwh=self._non_ernc_kwh,
            ernc_fraction=fraction,
            qualifies=fraction * 100.0 >= self._min_pct,
            threshold_pct=self._min_pct,
        )
        log.info("ernc.certificate_generated", site_id=self._site_id,
                 ernc_pct=round(fraction * 100, 2), qualifies=cert.qualifies,
                 norm_ref="Ley 21.185")
        return cert

    def reset_period(self) -> None:
        """Reset counters for a new reporting period."""
        self._ernc_kwh = 0.0
        self._non_ernc_kwh = 0.0
        self._period_start = datetime.now(timezone.utc).isoformat()
        log.info("ernc.period_reset", site_id=self._site_id)
