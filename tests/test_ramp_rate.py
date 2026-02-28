# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_ramp_rate.py
========================
Unit tests for ``SafetyGuard.apply_ramp_limit`` — NTSyCS Cap. 4.2
Ramp Rate Limiting (GAP-001).

Covers:
* Setpoint within limit → passes unchanged.
* Setpoint exceeds limit (charge direction) → clamped correctly.
* Setpoint exceeds limit (discharge direction) → clamped correctly.
* dt_s == 0 (first write) → target returned unchanged.
* Custom RAMP_RATE_MAX_PCT_PER_MIN via subclass override.
"""

from __future__ import annotations

import pytest
from src.core.safety import SafetyGuard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def guard_1mw() -> SafetyGuard:
    """1 MW system, 10 %/min → 100 kW/min ramp limit."""
    return SafetyGuard(p_nom_kw=1000.0)


# ---------------------------------------------------------------------------
# Within ramp limit — passthrough
# ---------------------------------------------------------------------------


class TestRampRatePassthrough:
    def test_small_step_unchanged(self, guard_1mw: SafetyGuard) -> None:
        """80 kW change over 60 s < 100 kW/min → unchanged."""
        result = guard_1mw.apply_ramp_limit(0.0, 80.0, dt_s=60.0)
        assert result == pytest.approx(80.0)

    def test_exact_boundary_unchanged(self, guard_1mw: SafetyGuard) -> None:
        """Exactly 100 kW change over 60 s == limit → unchanged."""
        result = guard_1mw.apply_ramp_limit(0.0, 100.0, dt_s=60.0)
        assert result == pytest.approx(100.0)

    def test_half_second_step(self, guard_1mw: SafetyGuard) -> None:
        """0.5 s step → max delta = 100/120 ≈ 0.833 kW."""
        result = guard_1mw.apply_ramp_limit(100.0, 100.5, dt_s=0.5)
        assert result == pytest.approx(100.5)

    def test_dt_zero_passthrough(self, guard_1mw: SafetyGuard) -> None:
        """dt_s=0 (first write) → any setpoint allowed."""
        result = guard_1mw.apply_ramp_limit(0.0, 999.0, dt_s=0.0)
        assert result == pytest.approx(999.0)

    def test_negative_dt_passthrough(self, guard_1mw: SafetyGuard) -> None:
        """Negative dt treated same as 0 → passthrough."""
        result = guard_1mw.apply_ramp_limit(0.0, 500.0, dt_s=-1.0)
        assert result == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Exceeds ramp limit — clamped
# ---------------------------------------------------------------------------


class TestRampRateClamped:
    def test_discharge_ramp_clamped(self, guard_1mw: SafetyGuard) -> None:
        """Request 500 kW in 60 s from 0 → clamped to 100 kW."""
        result = guard_1mw.apply_ramp_limit(0.0, 500.0, dt_s=60.0)
        assert result == pytest.approx(100.0)

    def test_charge_ramp_clamped(self, guard_1mw: SafetyGuard) -> None:
        """Request -500 kW in 60 s from 0 → clamped to -100 kW."""
        result = guard_1mw.apply_ramp_limit(0.0, -500.0, dt_s=60.0)
        assert result == pytest.approx(-100.0)

    def test_clamped_from_non_zero_base(self, guard_1mw: SafetyGuard) -> None:
        """From 200 kW → request 500 kW in 60 s → clamped to 300 kW."""
        result = guard_1mw.apply_ramp_limit(200.0, 500.0, dt_s=60.0)
        assert result == pytest.approx(300.0)

    def test_short_dt_tight_limit(self, guard_1mw: SafetyGuard) -> None:
        """1 s step → max delta = 100/60 ≈ 1.667 kW; request 50 kW → clamped."""
        max_delta = (10.0 / 100.0) * 1000.0 * (1.0 / 60.0)
        result = guard_1mw.apply_ramp_limit(0.0, 50.0, dt_s=1.0)
        assert result == pytest.approx(max_delta, rel=1e-6)

    def test_custom_ramp_rate(self) -> None:
        """Override RAMP_RATE_MAX_PCT_PER_MIN → 5 %/min → 50 kW/min."""

        class SlowGuard(SafetyGuard):
            RAMP_RATE_MAX_PCT_PER_MIN: float = 5.0

        guard = SlowGuard(p_nom_kw=1000.0)
        result = guard.apply_ramp_limit(0.0, 200.0, dt_s=60.0)
        assert result == pytest.approx(50.0)

    def test_existing_check_safety_still_passes(self, guard_1mw: SafetyGuard) -> None:
        """Verify GAP-001 changes did not break check_safety (regression)."""
        assert guard_1mw.check_safety({"soc": 50.0, "temp": 30.0}) is True
        assert guard_1mw.check_safety({"soc": 1.0}) is False
