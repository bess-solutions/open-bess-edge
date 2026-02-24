"""
tests/agents/test_arbitrage_policy.py
======================================
Tests for ArbitragePolicy (BEP-0200 rule-based baseline).
"""

from __future__ import annotations

import numpy as np
import pytest
from src.agents.arbitrage_policy import (
    _CMG_MAX_NORM,
    OBS_CMG_1H,
    OBS_CMG_NOW,
    OBS_SOC,
    ArbitragePolicy,
)


def _make_obs(
    soc: float = 0.5,
    cmg_now: float = 50.0,
    cmg_1h: float = 50.0,
) -> np.ndarray:
    """Build a minimal observation array for testing."""
    obs = np.zeros(8, dtype=np.float32)
    obs[OBS_SOC] = soc
    obs[OBS_CMG_NOW] = cmg_now / _CMG_MAX_NORM
    obs[OBS_CMG_1H] = cmg_1h / _CMG_MAX_NORM
    return obs


class TestArbitragePolicyInit:
    def test_default_thresholds(self):
        p = ArbitragePolicy()
        assert p.cmg_low == pytest.approx(30.0 / _CMG_MAX_NORM, rel=1e-4)
        assert p.cmg_high == pytest.approx(80.0 / _CMG_MAX_NORM, rel=1e-4)
        assert p.soc_min == pytest.approx(0.15)
        assert p.soc_max == pytest.approx(0.95)

    def test_custom_thresholds(self):
        p = ArbitragePolicy(cmg_low_threshold_norm=0.05, cmg_high_threshold_norm=0.50)
        assert p.cmg_low == pytest.approx(0.05)
        assert p.cmg_high == pytest.approx(0.50)


class TestArbitragePolicyRules:
    def test_solar_dump_charges(self):
        """Low CMg + room to charge → charge rule triggered."""
        policy = ArbitragePolicy()
        obs = _make_obs(soc=0.50, cmg_now=10.0)  # 10 USD/MWh < 30 threshold
        p_pu, info = policy.predict(obs)
        assert p_pu < 0, "Should charge (negative p_pu)"
        assert info["rule"] == "solar_dump_charge"

    def test_solar_dump_skipped_when_full(self):
        """Low CMg but battery full → should not charge."""
        policy = ArbitragePolicy()
        obs = _make_obs(soc=0.96, cmg_now=10.0)  # SOC above soc_max
        p_pu, info = policy.predict(obs)
        # Should NOT trigger solar_dump_charge
        assert info["rule"] != "solar_dump_charge"

    def test_evening_peak_discharges(self):
        """High CMg + SOC above min → discharge rule triggered."""
        policy = ArbitragePolicy()
        obs = _make_obs(soc=0.70, cmg_now=120.0, cmg_1h=100.0)  # > 80 threshold
        p_pu, info = policy.predict(obs)
        assert p_pu > 0, "Should discharge (positive p_pu)"
        assert info["rule"] == "evening_peak_discharge"

    def test_evening_peak_skipped_low_soc(self):
        """High CMg but battery depleted → no discharge."""
        policy = ArbitragePolicy()
        obs = _make_obs(soc=0.10, cmg_now=120.0, cmg_1h=100.0)  # SOC below soc_min
        p_pu, info = policy.predict(obs)
        assert info["rule"] != "evening_peak_discharge"

    def test_idle_moderate_price(self):
        """Moderate CMg with normal SOC → idle."""
        policy = ArbitragePolicy()
        obs = _make_obs(soc=0.50, cmg_now=50.0, cmg_1h=55.0)
        _, info = policy.predict(obs)
        assert info["rule"] == "idle"

    def test_predict_returns_valid_types(self):
        policy = ArbitragePolicy()
        obs = _make_obs()
        p_pu, info = policy.predict(obs)
        assert isinstance(p_pu, float)
        assert isinstance(info, dict)
        assert "source" in info
        assert "rule" in info

    def test_p_pu_bounds(self):
        """Per-unit action must always be ∈ [-1, 1]."""
        policy = ArbitragePolicy()
        test_cases = [
            _make_obs(soc=0.50, cmg_now=5.0),  # solar dump
            _make_obs(soc=0.80, cmg_now=150.0, cmg_1h=120.0),  # peak discharge
            _make_obs(soc=0.50, cmg_now=50.0),  # idle
            _make_obs(soc=0.92, cmg_now=70.0),  # high SOC moderate
        ]
        for obs in test_cases:
            p_pu, _ = policy.predict(obs)
            assert -1.0 <= p_pu <= 1.0, f"p_pu={p_pu} out of range for obs={obs}"

    def test_pre_charge_spike_anticipation(self):
        """Moderate CMg now + high forecast → pre-charge rule.
        cmg_now must be > cmg_low (30 USD) so Rule 1 (solar_dump) does NOT fire first.
        """
        policy = ArbitragePolicy()
        # 40 USD > cmg_low (30) but < cmg_high (80) + high 1h forecast → spike anticipation
        obs = _make_obs(soc=0.50, cmg_now=40.0, cmg_1h=150.0)
        p_pu, info = policy.predict(obs)
        assert p_pu < 0, "Should pre-charge"
        assert info["rule"] == "pre_charge_spike_anticipation"

    def test_source_always_rule_based(self):
        """Source field must always be 'rule_based'."""
        policy = ArbitragePolicy()
        for cmg in [5.0, 50.0, 150.0]:
            obs = _make_obs(soc=0.60, cmg_now=cmg)
            _, info = policy.predict(obs)
            assert info["source"] == "rule_based"
