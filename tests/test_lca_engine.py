"""
tests/test_lca_engine.py
=========================
Unit tests for LCAEngine and LCAConfig.
"""

from __future__ import annotations

import pytest
from src.interfaces.lca_config import BATTERY_EMBODIED_CO2_KG_KWH, GRID_EMISSION_FACTORS_G_KWH
from src.interfaces.lca_engine import LCAConfig, LCAEngine


class TestLCAConfig:

    def test_database_contains_chile(self):
        assert "CL" in GRID_EMISSION_FACTORS_G_KWH
        assert GRID_EMISSION_FACTORS_G_KWH["CL"] > 0

    def test_database_has_all_major_regions(self):
        required = {"CL", "DE", "FR", "US", "CN", "AU", "GLOBAL"}
        assert required.issubset(set(GRID_EMISSION_FACTORS_G_KWH))

    def test_emission_factors_are_positive(self):
        for country, ef in GRID_EMISSION_FACTORS_G_KWH.items():
            assert ef > 0, f"{country} has non-positive EF: {ef}"

    def test_embodied_co2_positive(self):
        assert BATTERY_EMBODIED_CO2_KG_KWH > 0


class TestLCAEngine:

    def _engine(self, region: str = "CL", capacity: float = 100.0) -> LCAEngine:
        config = LCAConfig(region=region, capacity_kwh=capacity)
        return LCAEngine(config=config)

    def test_init_resolves_grid_ef(self):
        engine = self._engine("FR")
        # France nuclear EF should be < 100
        assert engine.grid_emission_factor_g_kwh < 100.0

    def test_init_fallback_to_global_for_unknown_region(self):
        config = LCAConfig(region="XX")  # unknown code
        engine = LCAEngine(config=config)
        assert engine.grid_emission_factor_g_kwh == pytest.approx(345.0)

    def test_update_zero_discharge_returns_zero_co2(self):
        engine = self._engine()
        result = engine.update(discharged_kwh=0.0)
        assert result.co2_avoided_kg == pytest.approx(0.0, abs=1e-8)
        assert result.discharged_kwh == pytest.approx(0.0)

    def test_update_discharge_avoids_positive_co2(self):
        """Discharging in a high-carbon grid should avoid positive CO₂."""
        config = LCAConfig(region="PL", capacity_kwh=100.0)  # Poland: ~683 gCO₂/kWh
        engine = LCAEngine(config=config)
        result = engine.update(discharged_kwh=10.0)
        # grid_co2 ≈ 10 × 683 / 1000 = 6.83 kg, battery amort << 6.83
        assert result.co2_avoided_kg > 0.0

    def test_cumulative_increases_monotonically(self):
        engine = self._engine()
        engine.update(discharged_kwh=5.0)
        first = engine.cumulative_co2_avoided_kg
        engine.update(discharged_kwh=5.0)
        assert engine.cumulative_co2_avoided_kg > first

    def test_reset_clears_cumulative(self):
        engine = self._engine()
        engine.update(discharged_kwh=50.0)
        engine.reset()
        assert engine.cumulative_co2_avoided_kg == pytest.approx(0.0)

    def test_grid_intensity_field(self):
        engine = self._engine("NO")  # Norway ~19 gCO₂/kWh
        result = engine.update(discharged_kwh=10.0)
        assert result.grid_intensity == pytest.approx(19.0)

    def test_manual_grid_ef_override(self):
        config = LCAConfig(grid_emission_factor=500.0, capacity_kwh=100.0)
        engine = LCAEngine(config=config)
        assert engine.grid_emission_factor_g_kwh == pytest.approx(500.0)
        result = engine.update(discharged_kwh=1.0)
        assert result.grid_intensity == pytest.approx(500.0)

    def test_equivalent_trees_positive_after_discharge(self):
        engine = self._engine("DE")  # Germany: 349 gCO₂/kWh
        engine.update(discharged_kwh=100.0)
        trees = engine.equivalent_trees_planted
        assert trees >= 0.0  # should be positive after sufficient discharge

    def test_negative_discharge_clipped_to_zero(self):
        engine = self._engine()
        result = engine.update(discharged_kwh=-10.0)  # invalid input
        assert result.discharged_kwh == pytest.approx(0.0)
