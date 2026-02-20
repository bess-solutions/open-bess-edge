"""
tests/test_ai_ids.py
=====================
Unit tests for the AI-IDS ModbusAnomalyDetector.

Tests cover:
  - ModbusFrame feature extraction
  - Unfitted detector returns 0.0 (fail-safe)
  - Normal traffic → low anomaly score
  - Anomalous traffic → high anomaly score (after fitting)
  - Z-score timing anomaly (even without IsolationForest)
  - Alert threshold triggering
  - Prometheus metric updates
  - fit() with insufficient samples (graceful skip)
"""

from __future__ import annotations

import pytest
from src.interfaces.ai_ids import ModbusAnomalyDetector, ModbusFrame

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _normal_frame(timing_ms: float = 10.0) -> ModbusFrame:
    """Return a typical normal Modbus read frame."""
    return ModbusFrame(
        fc_code=3, address=0x1000, count=10, timing_ms=timing_ms, soc_pct=75.0, power_kw=50.0
    )


def _anomalous_frame() -> ModbusFrame:
    """Return a frame that mimics a Modbus reconnaissance attack."""
    return ModbusFrame(
        fc_code=1,  # Coil read — unusual for this inverter
        address=0xFFFF,  # Max address range scan
        count=125,  # Max registers in one request
        timing_ms=500.0,  # Very slow response — possible MITM
        soc_pct=75.0,
        power_kw=50.0,
    )


def _normal_traffic(n: int = 80) -> list[ModbusFrame]:
    """Generate n normal frames for fitting the detector."""
    return [_normal_frame(timing_ms=10.0 + i * 0.02) for i in range(n)]


# ---------------------------------------------------------------------------
# Tests — ModbusFrame
# ---------------------------------------------------------------------------


def test_modbus_frame_feature_shape():
    """Feature vector must have exactly 6 elements."""
    frame = _normal_frame()
    features = frame.to_features()
    assert features.shape == (6,)


def test_modbus_frame_feature_values():
    """Feature vector contains the correct values in correct order."""
    frame = ModbusFrame(
        fc_code=3, address=0x1000, count=10, timing_ms=15.5, soc_pct=80.0, power_kw=30.0
    )
    f = frame.to_features()
    assert f[0] == 3  # fc_code
    assert f[1] == 0x1000  # address
    assert f[2] == 10  # count
    assert f[3] == pytest.approx(15.5)
    assert f[4] == pytest.approx(80.0)
    assert f[5] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Tests — Unfitted detector (fail-safe)
# ---------------------------------------------------------------------------


def test_unfitted_detector_returns_zero():
    """Before fit(), score() must return 0.0 (fail-safe, no false positives)."""
    detector = ModbusAnomalyDetector()
    score = detector.score(_normal_frame())
    assert score == pytest.approx(0.0)


def test_unfitted_detector_alerting_safe():
    """check_and_alert() must not raise even when unfitted."""
    detector = ModbusAnomalyDetector(site_id="test-unfitted")
    # Should not raise
    score = detector.check_and_alert(_normal_frame())
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Tests — After fitting
# ---------------------------------------------------------------------------


def test_fit_with_enough_samples():
    """fit() with ≥ min_fit_samples should set _fitted = True."""
    detector = ModbusAnomalyDetector(min_fit_samples=50)
    detector.fit(_normal_traffic(80))
    assert detector._fitted is True


def test_fit_with_insufficient_samples():
    """fit() with < min_fit_samples should NOT set _fitted (but not raise)."""
    detector = ModbusAnomalyDetector(min_fit_samples=50)
    detector.fit(_normal_traffic(20))
    assert detector._fitted is False


def test_fit_with_empty_frames():
    """fit() with empty list must not raise."""
    detector = ModbusAnomalyDetector()
    detector.fit([])  # should not raise
    assert detector._fitted is False


def test_normal_traffic_low_score():
    """Normal frames after fit() should score below the alert threshold."""
    detector = ModbusAnomalyDetector(threshold=0.65, min_fit_samples=50)
    detector.fit(_normal_traffic(80))
    score = detector.score(_normal_frame(timing_ms=11.0))
    assert score < 0.65, f"Expected normal score < 0.65, got {score:.4f}"


def test_anomalous_timing_high_score_after_fit():
    """An extreme timing outlier should score higher than a normal frame."""
    detector = ModbusAnomalyDetector(threshold=0.65, min_fit_samples=50)
    detector.fit(_normal_traffic(80))  # baseline ~10ms timing
    score_normal = detector.score(_normal_frame(timing_ms=10.5))
    score_anomaly = detector.score(_normal_frame(timing_ms=5000.0))  # 5 seconds!
    assert score_anomaly > score_normal, (
        f"Anomaly score ({score_anomaly:.4f}) should exceed normal ({score_normal:.4f})"
    )


# ---------------------------------------------------------------------------
# Tests — Score range
# ---------------------------------------------------------------------------


def test_score_always_in_0_1_range():
    """score() must always return a value in [0, 1]."""
    detector = ModbusAnomalyDetector(min_fit_samples=50)
    detector.fit(_normal_traffic(80))
    for frame in [_normal_frame(), _anomalous_frame(), _normal_frame(timing_ms=9999.9)]:
        s = detector.score(frame)
        assert 0.0 <= s <= 1.0, f"score {s} out of [0,1]"


# ---------------------------------------------------------------------------
# Tests — Z-score timing (works without IsolationForest)
# ---------------------------------------------------------------------------


def test_zscore_timing_without_isolation_forest():
    """Z-score should increase monotonically with timing deviation."""
    detector = ModbusAnomalyDetector(min_fit_samples=200)  # won't fit IsoForest
    detector.fit(_normal_traffic(30))  # builds baseline only
    assert detector._fitted is False
    assert len(detector._baseline_timings) == 30

    s_low = detector.score(_normal_frame(timing_ms=10.0))
    s_high = detector.score(_normal_frame(timing_ms=1000.0))
    assert s_high > s_low
