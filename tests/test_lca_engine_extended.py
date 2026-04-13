# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_lca_engine_extended.py
===================================
Extended unit tests for ``src.interfaces.lca_engine``.

Covers:
  - CO2 accounting: grid CO2, battery amortisation, net avoided
  - Cumulative tracking over multiple cycles
  - Region emission factor lookup (CL, FR, PL, unknown → global fallback)
  - Custom grid_emission_factor override
  - Custom embodied_co2_per_kwh_kg override
  - Negative / zero dispatch inputs
  - reset() clears all accumulators
  - equivalence properties (trees_planted)
  - LCAConfig defaults
"""

from __future__ import annotations

import pytest
from src.interfaces.lca_config import (
    BATTERY_EMBODIED_CO2_KG_KWH,
    GRID_EMISSION_FACTORS_G_KWH,
)
from src.interfaces.lca_engine import LCAConfig, LCAEngine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine_cl() -> LCAEngine:
    """Standard Chilean grid engine — 100 kWh BESS."""
    return LCAEngine(config=LCAConfig(region="CL", capacity_kwh=100.0))


@pytest.fixture()
def engine_no() -> LCAEngine:
    """Norway — near-zero grid intensity."""
    return LCAEngine(config=LCAConfig(region="NO", capacity_kwh=100.0))


@pytest.fixture()
def engine_pl() -> LCAEngine:
    """Poland — highest grid intensity in DB."""
    return LCAEngine(config=LCAConfig(region="PL", capacity_kwh=100.0))


# ---------------------------------------------------------------------------
# LCAConfig defaults
# ---------------------------------------------------------------------------

class TestLCAConfigDefaults:
    def test_default_region(self):
        cfg = LCAConfig()
        assert cfg.region == "CL"

    def test_default_capacity(self):
        cfg = LCAConfig()
        assert cfg.capacity_kwh == pytest.approx(100.0)

    def test_default_design_cycles(self):
        cfg = LCAConfig()
        assert cfg.design_cycles == 4_000

    def test_grid_ef_none_by_default(self):
        cfg = LCAConfig()
        assert cfg.grid_emission_factor is None


# ---------------------------------------------------------------------------
# Region lookup
# ---------------------------------------------------------------------------

class TestRegionLookup:
    def test_cl_emission_factor(self):
        engine = LCAEngine(config=LCAConfig(region="CL"))
        assert engine.grid_emission_factor_g_kwh == pytest.approx(GRID_EMISSION_FACTORS_G_KWH["CL"])

    def test_fr_emission_factor_low(self):
        """France has nuclear-dominant low EF."""
        engine = LCAEngine(config=LCAConfig(region="FR"))
        assert engine.grid_emission_factor_g_kwh == pytest.approx(GRID_EMISSION_FACTORS_G_KWH["FR"])
        assert engine.grid_emission_factor_g_kwh < 100.0

    def test_pl_emission_factor_high(self):
        """Poland has coal-dominant high EF."""
        engine = LCAEngine(config=LCAConfig(region="PL"))
        assert engine.grid_emission_factor_g_kwh > 600.0

    def test_unknown_region_falls_back_to_345(self):
        """Unknown region code → global average 345 gCO2/kWh."""
        engine = LCAEngine(config=LCAConfig(region="XX"))
        assert engine.grid_emission_factor_g_kwh == pytest.approx(345.0)

    def test_lowercase_region_normalized(self):
        """Region code should be uppercased internally."""
        engine = LCAEngine(config=LCAConfig(region="cl"))
        assert engine.grid_emission_factor_g_kwh == pytest.approx(GRID_EMISSION_FACTORS_G_KWH["CL"])

    def test_custom_override_ignores_region(self):
        """Manual grid_emission_factor overrides region lookup."""
        engine = LCAEngine(config=LCAConfig(region="PL", grid_emission_factor=50.0))
        assert engine.grid_emission_factor_g_kwh == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# CO2 accounting math
# ---------------------------------------------------------------------------

class TestCO2Accounting:
    def test_zero_discharge_zero_grid_co2(self, engine_cl: LCAEngine):
        result = engine_cl.update(discharged_kwh=0.0, charged_kwh=0.0)
        assert result.co2_grid_kg == pytest.approx(0.0)

    def test_grid_co2_formula(self, engine_cl: LCAEngine):
        """co2_grid = discharged_kwh × grid_ef / 1000 (g → kg)."""
        ef = GRID_EMISSION_FACTORS_G_KWH["CL"]  # 335 g/kWh
        result = engine_cl.update(discharged_kwh=10.0)
        expected = 10.0 * ef / 1000.0
        assert result.co2_grid_kg == pytest.approx(expected, rel=1e-6)

    def test_battery_amort_formula(self, engine_cl: LCAEngine):
        """co2_battery_amort = fec × co2_per_fec."""
        cap = 100.0
        fec = (10.0 + 0.0) / (2.0 * cap)  # discharged=10, charged=0
        total_battery_co2 = BATTERY_EMBODIED_CO2_KG_KWH * cap
        co2_per_fec = total_battery_co2 / 4_000
        expected = fec * co2_per_fec
        result = engine_cl.update(discharged_kwh=10.0)
        assert result.co2_battery_amort == pytest.approx(expected, rel=1e-6)

    def test_net_avoided_is_grid_minus_battery(self, engine_cl: LCAEngine):
        result = engine_cl.update(discharged_kwh=20.0, charged_kwh=25.0)
        assert result.co2_avoided_kg == pytest.approx(
            result.co2_grid_kg - result.co2_battery_amort, rel=1e-9
        )

    def test_high_ef_region_more_co2_avoided(self):
        """Poland (683 g) avoids more CO2 per kWh than Norway (19 g)."""
        e_pl = LCAEngine(config=LCAConfig(region="PL", capacity_kwh=100.0))
        e_no = LCAEngine(config=LCAConfig(region="NO", capacity_kwh=100.0))
        r_pl = e_pl.update(discharged_kwh=10.0)
        r_no = e_no.update(discharged_kwh=10.0)
        assert r_pl.co2_grid_kg > r_no.co2_grid_kg

    def test_discharged_kwh_reflected_in_result(self, engine_cl: LCAEngine):
        result = engine_cl.update(discharged_kwh=15.5, charged_kwh=0.0)
        assert result.discharged_kwh == pytest.approx(15.5)

    def test_grid_intensity_reflected_in_result(self, engine_cl: LCAEngine):
        result = engine_cl.update(discharged_kwh=10.0)
        assert result.grid_intensity == pytest.approx(engine_cl.grid_emission_factor_g_kwh)

    def test_negative_input_clamped_to_zero(self, engine_cl: LCAEngine):
        """Negative kWh inputs must be clamped — no negative emissions."""
        result = engine_cl.update(discharged_kwh=-5.0, charged_kwh=-3.0)
        assert result.co2_grid_kg == pytest.approx(0.0)
        assert result.co2_battery_amort == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Cumulative tracking
# ---------------------------------------------------------------------------

class TestCumulativeTracking:
    def test_cumulative_increases_each_cycle(self, engine_cl: LCAEngine):
        for _ in range(5):
            engine_cl.update(discharged_kwh=10.0)
        assert engine_cl.cumulative_co2_avoided_kg > engine_cl.update(discharged_kwh=10.0).co2_avoided_kg

    def test_cumulative_in_result_matches_property(self, engine_cl: LCAEngine):
        engine_cl.update(discharged_kwh=5.0)
        result = engine_cl.update(discharged_kwh=5.0)
        assert result.cumulative_avoided_kg == pytest.approx(engine_cl.cumulative_co2_avoided_kg)

    def test_cumulative_additive_over_cycles(self, engine_cl: LCAEngine):
        r1 = engine_cl.update(discharged_kwh=10.0)
        r2 = engine_cl.update(discharged_kwh=10.0)
        assert r2.cumulative_avoided_kg == pytest.approx(
            r1.co2_avoided_kg + r2.co2_avoided_kg, rel=1e-9
        )

    def test_zero_cumulative_at_start(self):
        engine = LCAEngine()
        assert engine.cumulative_co2_avoided_kg == pytest.approx(0.0)

    def test_many_cycles_accumulate(self, engine_cl: LCAEngine):
        for _ in range(100):
            engine_cl.update(discharged_kwh=10.0, charged_kwh=12.0)
        assert engine_cl.cumulative_co2_avoided_kg != 0.0


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_zeroes_cumulative(self, engine_cl: LCAEngine):
        for _ in range(10):
            engine_cl.update(discharged_kwh=20.0)
        engine_cl.reset()
        assert engine_cl.cumulative_co2_avoided_kg == pytest.approx(0.0)

    def test_accumulation_restarts_after_reset(self, engine_cl: LCAEngine):
        engine_cl.update(discharged_kwh=10.0)
        engine_cl.reset()
        result = engine_cl.update(discharged_kwh=10.0)
        # After reset, cumulative = this single cycle's value
        assert result.cumulative_avoided_kg == pytest.approx(result.co2_avoided_kg)

    def test_reset_does_not_change_config(self, engine_cl: LCAEngine):
        ef_before = engine_cl.grid_emission_factor_g_kwh
        engine_cl.reset()
        assert engine_cl.grid_emission_factor_g_kwh == pytest.approx(ef_before)


# ---------------------------------------------------------------------------
# Tree equivalence
# ---------------------------------------------------------------------------

class TestTreeEquivalence:
    def test_zero_avoided_zero_trees(self):
        engine = LCAEngine()
        assert engine.equivalent_trees_planted == pytest.approx(0.0)

    def test_21_kg_co2_equals_one_tree(self, engine_cl: LCAEngine):
        """If cumulative CO2 avoided = 21 kg → 1 tree."""
        # Force cumulative by running many cycles until cumulative ≥ 21 kg
        for _ in range(200):
            engine_cl.update(discharged_kwh=10.0)

        trees = engine_cl.equivalent_trees_planted
        # cumulative / 21 = trees
        assert trees == pytest.approx(engine_cl.cumulative_co2_avoided_kg / 21.0)

    def test_trees_proportional_to_avoided_co2(self, engine_cl: LCAEngine):
        engine_cl.update(discharged_kwh=50.0)
        trees = engine_cl.equivalent_trees_planted
        assert trees == pytest.approx(engine_cl.cumulative_co2_avoided_kg / 21.0)


# ---------------------------------------------------------------------------
# Custom embodied carbon
# ---------------------------------------------------------------------------

class TestCustomEmbodiedCarbon:
    def test_custom_embodied_used(self):
        """Custom embodied_co2_per_kwh_kg > 0 overrides the default."""
        cfg = LCAConfig(capacity_kwh=100.0, embodied_co2_per_kwh_kg=10.0)
        engine = LCAEngine(config=cfg)
        # total battery CO2 = 10 × 100 = 1000 kg; per FEC = 1000/4000 = 0.25 kg
        # FEC for 10 kWh discharge 0-charged = 10/(2×100) = 0.05
        result = engine.update(discharged_kwh=10.0, charged_kwh=0.0)
        expected_amort = 0.05 * (1000.0 / 4000.0)
        assert result.co2_battery_amort == pytest.approx(expected_amort, rel=1e-6)

    def test_zero_embodied_no_battery_penalty(self):
        """With zero embodied carbon, net avoided = grid CO2."""
        cfg = LCAConfig(capacity_kwh=100.0, embodied_co2_per_kwh_kg=1e-9)
        engine = LCAEngine(config=cfg)
        result = engine.update(discharged_kwh=10.0, charged_kwh=0.0)
        assert result.co2_avoided_kg == pytest.approx(result.co2_grid_kg, rel=1e-2)
