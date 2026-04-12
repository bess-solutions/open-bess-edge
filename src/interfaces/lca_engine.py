# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/interfaces/lca_engine.py
=============================
BESSAI Edge Gateway — Life-Cycle Assessment (LCA) Carbon Engine.

Calculates CO₂ emissions avoided by the BESS compared to a grid-baseline
scenario at each dispatch cycle, and tracks battery lifetime extension.

Carbon accounting methodology (simplified LCA):
  - Emission factor: country/regional grid carbon intensity (gCO₂eq/kWh)
  - Avoided emissions: grid kWh replaced by BESS discharge × grid_ef
  - Battery embodied carbon is amortised over lifetime cycles
  - Net benefit = avoided_grid_co2 - amortised_battery_co2

References:
  - IEA World Energy Outlook 2024 grid emission factors
  - EU taxonomy for sustainable finance (Art. 10 climate mitigation)
  - IEEE 2030.6 - Lifecycle assessment for energy storage

Usage::

    engine = LCAEngine(region="CL", capacity_kwh=100.0)
    result = engine.update(discharged_kwh=12.5, charged_kwh=15.0)
    print(f"CO2 avoided: {result.co2_avoided_kg:.3f} kg")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import structlog

from .lca_config import BATTERY_EMBODIED_CO2_KG_KWH, GRID_EMISSION_FACTORS_G_KWH
from .metrics import (
    CARBON_AVOIDED_KG,
    CARBON_INTENSITY_G_KWH,
)

__all__ = ["LCAEngine", "LCAResult", "LCAConfig"]

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Carbon viability thresholds (gCO₂eq/kWh)
# ---------------------------------------------------------------------------
# Based on BESS break-even analysis: battery embodied CO₂ (60 kgCO₂/kWh)
# amortised over 4000 full-cycles at 80% DoD.
# Net benefit only positive when grid EF > ~30 g/kWh.
_VIABILITY_LOW_G_KWH: float = 80.0    # EF < 80 → low commercial carbon benefit
_VIABILITY_MID_G_KWH: float = 200.0   # EF 80–200 → moderate benefit
_VIABILITY_HIGH_G_KWH: float = 400.0  # EF > 400 → high benefit (coal-heavy grid)


@dataclass
class LCAConfig:
    """LCA engine configuration.

    Attributes:
        region:             ISO-3166-1 alpha-2 country code (e.g., 'CL', 'DE').
        capacity_kwh:       BESS nameplate capacity in kWh.
        design_cycles:      Expected full cycle lifetime (default: 4000 cycles).
        embodied_co2_per_kwh_kg: Battery manufacturing CO₂ per kWh capacity (kgCO₂eq/kWh).
        grid_emission_factor: Manual override for grid EF in gCO₂eq/kWh. If None, uses DB.
    """

    region: str = "CL"
    capacity_kwh: float = 100.0
    design_cycles: int = 4_000
    embodied_co2_per_kwh_kg: float = 0.0  # auto-set from BATTERY_EMBODIED_CO2_KG_KWH
    grid_emission_factor: float | None = None  # gCO₂eq/kWh


@dataclass
class LCAResult:
    """Result of one LCA accounting cycle.

    Attributes:
        co2_avoided_kg:     Net CO₂ avoided this cycle (kg).
        co2_grid_kg:        CO₂ that grid would have emitted (kg).
        co2_battery_amort:  Amortised battery manufacturing CO₂ this cycle (kg).
        grid_intensity:     Grid emission factor used (gCO₂eq/kWh).
        discharged_kwh:     Energy discharged to grid this cycle (kWh).
        cumulative_avoided_kg: Lifetime CO₂ avoided (kg).
        timestamp:          Unix time of calculation.
    """

    co2_avoided_kg: float
    co2_grid_kg: float
    co2_battery_amort: float
    grid_intensity: float
    discharged_kwh: float
    cumulative_avoided_kg: float
    timestamp: float = field(default_factory=time.time)


class LCAEngine:
    """Life-Cycle Assessment engine for BESSAI edge gateway.

    Parameters:
        config: LCAConfig instance.
        site_id: Prometheus label for multi-site deployments.
    """

    def __init__(
        self,
        config: LCAConfig | None = None,
        site_id: str = "edge",
        strict_region: bool = False,
    ) -> None:
        self.config = config or LCAConfig()
        self.site_id = site_id
        self._cumulative_co2_avoided_kg: float = 0.0
        self._cumulative_discharged_kwh: float = 0.0
        self._cycle_count: float = 0.0

        # Resolve grid emission factor
        if self.config.grid_emission_factor is not None:
            self._grid_ef = self.config.grid_emission_factor
        else:
            region_key = self.config.region.upper()
            default_ef = 345.0  # global average gCO₂eq/kWh
            if region_key not in GRID_EMISSION_FACTORS_G_KWH:
                if strict_region:
                    raise ValueError(
                        f"Unsupported region: {self.config.region!r}. "
                        f"Supported regions: {sorted(GRID_EMISSION_FACTORS_G_KWH.keys())}"
                    )
                log.warning(
                    "lca_engine.unknown_region",
                    region=self.config.region,
                    fallback_ef=default_ef,
                )
            self._grid_ef = GRID_EMISSION_FACTORS_G_KWH.get(region_key, default_ef)

        # Battery embodied carbon amortisation
        if self.config.embodied_co2_per_kwh_kg > 0:
            self._battery_embodied_co2 = self.config.embodied_co2_per_kwh_kg
        else:
            self._battery_embodied_co2 = BATTERY_EMBODIED_CO2_KG_KWH

        # Total battery manufacturing CO₂ (kg)
        self._total_battery_co2_kg = self._battery_embodied_co2 * self.config.capacity_kwh
        # Co₂ per full equivalent cycle
        self._co2_per_fec_kg = self._total_battery_co2_kg / self.config.design_cycles

        log.info(
            "lca_engine.init",
            region=self.config.region,
            grid_ef_g_kwh=round(self._grid_ef, 1),
            battery_embodied_kg_kwh=round(self._battery_embodied_co2, 2),
            design_cycles=self.config.design_cycles,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(
        self,
        discharged_kwh: float,
        charged_kwh: float = 0.0,
        dt_h: float = 0.25,
    ) -> LCAResult:
        """Compute CO₂ accounting for one dispatch cycle.

        Args:
            discharged_kwh: Energy discharged to the grid this timestep (kWh ≥ 0).
            charged_kwh:    Energy absorbed from the grid (kWh ≥ 0).
            dt_h:           Timestep duration in hours (default: 0.25 = 15 min).

        Returns:
            LCAResult with instance metrics updated.
        """
        discharged_kwh = max(0.0, discharged_kwh)
        charged_kwh = max(0.0, charged_kwh)

        # CO₂ grid would have emitted if no BESS (discharge replaced by grid)
        co2_grid_kg = (discharged_kwh * self._grid_ef) / 1000.0  # g → kg

        # Amortised battery manufacturing CO₂ for this fractional cycle
        fec = (discharged_kwh + charged_kwh) / (2.0 * self.config.capacity_kwh)
        co2_battery_amort = fec * self._co2_per_fec_kg

        # Net avoided CO₂
        co2_avoided_kg = co2_grid_kg - co2_battery_amort

        # Accumulate
        self._cumulative_co2_avoided_kg += co2_avoided_kg
        self._cumulative_discharged_kwh += discharged_kwh
        self._cycle_count += fec

        # Update Prometheus
        CARBON_AVOIDED_KG.labels(site_id=self.site_id).set(self._cumulative_co2_avoided_kg)
        CARBON_INTENSITY_G_KWH.labels(site_id=self.site_id).set(self._grid_ef)

        result = LCAResult(
            co2_avoided_kg=co2_avoided_kg,
            co2_grid_kg=co2_grid_kg,
            co2_battery_amort=co2_battery_amort,
            grid_intensity=self._grid_ef,
            discharged_kwh=discharged_kwh,
            cumulative_avoided_kg=self._cumulative_co2_avoided_kg,
        )

        log.debug(
            "lca_engine.update",
            discharge_kwh=round(discharged_kwh, 2),
            co2_avoided_kg=round(co2_avoided_kg, 4),
            cumulative_kg=round(self._cumulative_co2_avoided_kg, 3),
        )
        return result

    def reset(self) -> None:
        """Reset accumulated CO₂ counters (useful between episodes)."""
        self._cumulative_co2_avoided_kg = 0.0
        self._cumulative_discharged_kwh = 0.0
        self._cycle_count = 0.0

    @property
    def cumulative_co2_avoided_kg(self) -> float:
        """Total CO₂ avoided since last reset (kg)."""
        return self._cumulative_co2_avoided_kg

    @property
    def grid_emission_factor_g_kwh(self) -> float:
        """Grid emission factor being used (gCO₂eq/kWh)."""
        return self._grid_ef

    @property
    def equivalent_trees_planted(self) -> float:
        """Rough equivalence: 1 tree absorbs ~21 kgCO₂/year."""
        return self._cumulative_co2_avoided_kg / 21.0

    @property
    def carbon_viability_score(self) -> int:
        """Commercial carbon viability score for this region/EF.

        Returns an integer 0–3 based on grid emission factor:

        - 0: **Marginal** — EF < 80 g/kWh (e.g. Norway, Uruguay, France).
             BESS may not pay back its embodied CO₂ on carbon savings alone.
        - 1: **Low** — EF 80–200 g/kWh (e.g. Brazil, Colombia, Sweden).
             Moderate carbon benefit; revenue case driven by arbitrage.
        - 2: **Medium** — EF 200–400 g/kWh (e.g. Chile, UK, Germany).
             Clear carbon benefit; supports carbon credit monetisation.
        - 3: **High** — EF > 400 g/kWh (e.g. India, Poland, South Africa).
             Strong carbon case; BESS payback in <5 years on carbon alone.

        Use ``carbon_viability_label`` for a human-readable string.
        """
        ef = self._grid_ef
        if ef < _VIABILITY_LOW_G_KWH:
            return 0
        if ef < _VIABILITY_MID_G_KWH:
            return 1
        if ef < _VIABILITY_HIGH_G_KWH:
            return 2
        return 3

    @property
    def carbon_viability_label(self) -> str:
        """Human-readable label for carbon_viability_score."""
        return [
            "marginal",   # 0
            "low",        # 1
            "medium",     # 2
            "high",       # 3
        ][self.carbon_viability_score]

    def viability_report(self) -> dict:
        """Return a client-facing carbon viability summary dict.

        Suitable for inclusion in PDF reports or API responses.

        Returns
        -------
        dict with keys:
            region, grid_ef_g_kwh, viability_score, viability_label,
            cumulative_co2_avoided_kg, equivalent_trees, warning (optional).
        """
        report: dict = {
            "region": self.config.region,
            "grid_ef_g_kwh": round(self._grid_ef, 1),
            "viability_score": self.carbon_viability_score,
            "viability_label": self.carbon_viability_label,
            "cumulative_co2_avoided_kg": round(self._cumulative_co2_avoided_kg, 2),
            "equivalent_trees": round(self.equivalent_trees_planted, 1),
        }
        if self.carbon_viability_score == 0:
            report["warning"] = (
                f"Grid EF={self._grid_ef:.0f} g/kWh is below 80 g/kWh. "
                "Carbon credits may not justify BESS investment in this region."
            )
        return report
