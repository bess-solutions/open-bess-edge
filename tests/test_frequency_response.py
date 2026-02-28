# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_frequency_response.py
==================================
Unit tests for ``src.core.frequency_response.FrequencyResponseAgent``
NTSyCS Cap. 4.3 — Primary Frequency Response (GAP-002).

Covers:
* Within deadband → p_base unchanged.
* Underfrequency → output increases toward Pnom.
* Overfrequency → output decreases toward 0.
* Output clamped to [0, Pnom].
* Compute time < 2 s (NTSyCS requirement).
* Invalid constructor parameters raise ValueError.
"""

from __future__ import annotations

import time

import pytest
from src.core.frequency_response import FrequencyResponseAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def pfr() -> FrequencyResponseAgent:
    """1 MW, 5 % droop, ±0.1 Hz deadband, 50 Hz nominal."""
    return FrequencyResponseAgent(
        f_nominal=50.0,
        deadband_hz=0.1,
        droop_pct=5.0,
        p_nom_kw=1000.0,
    )


# ---------------------------------------------------------------------------
# Deadband
# ---------------------------------------------------------------------------


class TestDeadband:
    def test_nominal_frequency_unchanged(self, pfr: FrequencyResponseAgent) -> None:
        assert pfr.compute_setpoint(50.0, 500.0) == pytest.approx(500.0)

    def test_upper_deadband_edge_unchanged(self, pfr: FrequencyResponseAgent) -> None:
        assert pfr.compute_setpoint(50.1, 500.0) == pytest.approx(500.0)

    def test_lower_deadband_edge_unchanged(self, pfr: FrequencyResponseAgent) -> None:
        assert pfr.compute_setpoint(49.9, 500.0) == pytest.approx(500.0)

    def test_just_outside_upper_deadband_responds(self, pfr: FrequencyResponseAgent) -> None:
        result = pfr.compute_setpoint(50.101, 500.0)
        assert result < 500.0  # overfrequency → reduce output


# ---------------------------------------------------------------------------
# Underfrequency response
# ---------------------------------------------------------------------------


class TestUnderfrequency:
    def test_underfrequency_increases_output(self, pfr: FrequencyResponseAgent) -> None:
        """49.5 Hz → ΔP = -(-0.5/2.5)*1000 = 200 kW → 700 kW total."""
        result = pfr.compute_setpoint(49.5, 500.0)
        assert result == pytest.approx(700.0, rel=1e-4)

    def test_severe_underfrequency_clamped_to_pnom(self, pfr: FrequencyResponseAgent) -> None:
        """Very low frequency → corrected > Pnom → clamped to 1000."""
        result = pfr.compute_setpoint(47.0, 500.0)
        assert result == pytest.approx(1000.0)

    def test_underfrequency_from_zero_base(self, pfr: FrequencyResponseAgent) -> None:
        """Base=0, underfrequency → positive setpoint is injected."""
        result = pfr.compute_setpoint(49.5, 0.0)
        assert result > 0.0


# ---------------------------------------------------------------------------
# Overfrequency response
# ---------------------------------------------------------------------------


class TestOverfrequency:
    def test_overfrequency_decreases_output(self, pfr: FrequencyResponseAgent) -> None:
        """50.5 Hz → ΔP = -(0.5/2.5)*1000 = -200 kW → 300 kW total."""
        result = pfr.compute_setpoint(50.5, 500.0)
        assert result == pytest.approx(300.0, rel=1e-4)

    def test_severe_overfrequency_clamped_to_zero(self, pfr: FrequencyResponseAgent) -> None:
        """Very high frequency → corrected < 0 → clamped to 0."""
        result = pfr.compute_setpoint(53.0, 500.0)
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# NTSyCS performance requirement: computation < 2 s
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_compute_time_under_2s(self, pfr: FrequencyResponseAgent) -> None:
        """NTSyCS Cap. 4.3 requires <2 s response. Computation must be << 1 ms."""
        t0 = time.perf_counter()
        for _ in range(1000):
            pfr.compute_setpoint(49.8, 500.0)
        elapsed = time.perf_counter() - t0
        # 1000 iterations must complete in <1 s total → avg <1 ms per call
        assert elapsed < 1.0, f"1000 PFR calls took {elapsed:.3f} s — too slow"


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_p_nom_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="p_nom_kw"):
            FrequencyResponseAgent(p_nom_kw=0.0)

    def test_p_nom_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="p_nom_kw"):
            FrequencyResponseAgent(p_nom_kw=-500.0)

    def test_droop_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="droop_pct"):
            FrequencyResponseAgent(droop_pct=0.0)

    def test_deadband_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="deadband_hz"):
            FrequencyResponseAgent(deadband_hz=-0.1)

    def test_properties_accessible(self, pfr: FrequencyResponseAgent) -> None:
        assert pfr.deadband_hz == pytest.approx(0.1)
        assert pfr.droop_pct == pytest.approx(5.0)
        assert pfr.p_nom_kw == pytest.approx(1000.0)
