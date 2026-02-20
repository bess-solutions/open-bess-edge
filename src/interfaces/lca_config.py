"""
src/interfaces/lca_config.py
============================
BESSAI Edge Gateway — Grid Carbon Emission Factor Database.

Emission factors sourced from:
  - IEA World Energy Outlook 2024 (Annex A, Table A.1)
  - Red Eléctrica de España 2023 (system average)
  - Coordinador Eléctrico Nacional Chile 2023
  - ENTSO-E Transparency Platform 2024

Units: gCO₂eq/kWh (location-based, system average)
Last updated: 2026-Q1 (BESSAI v0.8.0)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Grid emission factors by country — gCO₂eq/kWh (location-based)
# ---------------------------------------------------------------------------
GRID_EMISSION_FACTORS_G_KWH: dict[str, float] = {
    # South America
    "AR": 350.0,  # Argentina — high gas share
    "BR": 82.0,  # Brazil — heavy hydro
    "CL": 335.0,  # Chile — SEN grid (gas + coal + solar transition)
    "CO": 130.0,  # Colombia — hydro-dominant
    "EC": 168.0,  # Ecuador
    "PE": 152.0,  # Peru
    "UY": 48.0,  # Uruguay — near 100% renewable
    "VE": 190.0,  # Venezuela
    # North America
    "US": 386.0,  # USA — eGRID national average
    "CA": 125.0,  # Canada — large hydro share
    "MX": 432.0,  # Mexico
    # Europe (ENTSO-E 2024)
    "DE": 349.0,  # Germany — coal + gas transition
    "ES": 152.0,  # Spain — renewables+nuclear
    "FR": 52.0,  # France — nuclear-heavy
    "GB": 233.0,  # UK
    "IT": 283.0,  # Italy
    "NO": 19.0,  # Norway — near-100% hydro
    "SE": 41.0,  # Sweden — nuclear + hydro
    "NL": 316.0,  # Netherlands
    "PL": 683.0,  # Poland — coal-heavy
    "PT": 136.0,  # Portugal
    # Asia-Pacific
    "AU": 510.0,  # Australia — coal
    "CN": 539.0,  # China
    "IN": 708.0,  # India — coal-dominant
    "JP": 432.0,  # Japan post-2011
    "KR": 415.0,  # South Korea
    "NZ": 115.0,  # New Zealand
    # Africa & Middle East
    "ZA": 840.0,  # South Africa — coal
    "MA": 543.0,  # Morocco
    "EG": 440.0,  # Egypt
    "AE": 385.0,  # UAE
    # Global fallback
    "GLOBAL": 345.0,  # IEA world average 2024
}

# ---------------------------------------------------------------------------
# Battery manufacturing embodied carbon
# ---------------------------------------------------------------------------
# Source: Lifecycle assessment studies (Ellingsen et al. 2024, Argonne ANL-22/45)
# NMC (Nickel Manganese Cobalt) cathode chemistry — typical for BESS
BATTERY_EMBODIED_CO2_KG_KWH: float = 60.0  # kgCO₂eq per kWh nameplate capacity

# LFP (Lithium Iron Phosphate) — lower embodied carbon
BATTERY_EMBODIED_CO2_LFP_KG_KWH: float = 40.0

# NCA (Nickel Cobalt Aluminum) — higher
BATTERY_EMBODIED_CO2_NCA_KG_KWH: float = 75.0

# ---------------------------------------------------------------------------
# Design lifetime assumptions
# ---------------------------------------------------------------------------
DESIGN_CYCLES_NMC: int = 4_000  # 80% DOD cycles to 80% capacity fade
DESIGN_CYCLES_LFP: int = 6_000  # LFP is more cycle-stable
DESIGN_CYCLES_NCA: int = 3_500  # NCA — less cycle-stable

# ---------------------------------------------------------------------------
# Equivalences for user reporting
# ---------------------------------------------------------------------------
CO2_KG_PER_TREE_YEAR: float = 21.0  # Average tree absorbs ~21 kgCO₂/year
CO2_KG_PER_KM_EV: float = 0.168  # Average EV at 0.168 kgCO₂eq/km (EU mix)
CO2_KG_PER_KWH_COAL: float = 0.820  # Pure coal generation
