"""
src/interfaces/ai_ids.py
========================
BESSAI Edge Gateway — AI-based Intrusion Detection System (AI-IDS).

Detects anomalous Modbus traffic using a two-layer ensemble:
  1. IsolationForest  — unsupervised outlier detection on per-frame features.
  2. Statistical z-score baseline — lightweight guard during initial fit phase.

Algorithm (ensemble):
    anomaly_score = 0.4 * isolation_score + 0.6 * zscore_score   (0-1, higher = more anomalous)

Usage::

    detector = ModbusAnomalyDetector()
    detector.fit(normal_frames)          # train on known-good traffic
    score = detector.score(frame)        # 0.0 = normal, 1.0 = highly anomalous
    detector.check_and_alert(frame)      # scores + logs + updates Prometheus

The detector is safe to use before fit() — it returns 0.0 (no anomaly) if no
model has been trained yet, following the fail-safe principle of the roadmap.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
import structlog

from .metrics import IDS_ALERTS_TOTAL, IDS_ANOMALY_SCORE

try:
    from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]
    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SKLEARN_AVAILABLE = False

__all__ = ["ModbusFrame", "ModbusAnomalyDetector"]

log = structlog.get_logger(__name__)

# Default alert threshold — tune based on production baseline
DEFAULT_THRESHOLD: float = 0.65


@dataclass
class ModbusFrame:
    """Represents a single Modbus read operation (features for AI-IDS).

    Attributes:
        fc_code:      Modbus Function Code (1, 3, 4, 16, etc.).
        address:      Starting register address.
        count:        Number of registers requested.
        timing_ms:    Round-trip response time in milliseconds.
        soc_pct:      State of Charge % at time of read (context feature).
        power_kw:     Active power kW at time of read (context feature).
        timestamp:    Unix timestamp of the read (seconds since epoch).
    """
    fc_code: int = 3
    address: int = 0
    count: int = 1
    timing_ms: float = 10.0
    soc_pct: float = 50.0
    power_kw: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_features(self) -> np.ndarray:
        """Return a 1-D numpy array of numeric features for the detector."""
        return np.array(
            [self.fc_code, self.address, self.count, self.timing_ms,
             self.soc_pct, self.power_kw],
            dtype=np.float64,
        )


class ModbusAnomalyDetector:
    """Two-layer anomaly detector for Modbus traffic.

    Layer 1: IsolationForest (sklearn) over per-frame numeric features.
    Layer 2: Z-score over timing_ms baseline (always active, low overhead).

    Parameters:
        threshold:          Alert threshold on ensemble score (0-1).
        contamination:      Expected fraction of anomalies in training data.
        min_fit_samples:    Minimum frames before IsolationForest is trained.
        site_id:            Site identifier for Prometheus label.
    """

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        contamination: float = 0.05,
        min_fit_samples: int = 50,
        site_id: str = "unknown",
    ) -> None:
        self.threshold = threshold
        self.contamination = contamination
        self.min_fit_samples = min_fit_samples
        self.site_id = site_id

        self._iso_forest: Optional[IsolationForest] = None
        self._fitted: bool = False
        self._baseline_timings: list[float] = []
        self._timing_mean: float = 0.0
        self._timing_std: float = 1.0

        log.info("ai_ids.init", threshold=threshold, site_id=site_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, frames: Sequence[ModbusFrame]) -> None:
        """Train the IsolationForest on a sequence of known-normal frames.

        Safe to call with < min_fit_samples — will skip IsoForest training
        but will still compute the timing baseline.
        """
        if not frames:
            return

        timings = [f.timing_ms for f in frames]
        self._timing_mean = float(np.mean(timings))
        self._timing_std = max(float(np.std(timings)), 1.0)
        self._baseline_timings = list(timings)

        if _SKLEARN_AVAILABLE and len(frames) >= self.min_fit_samples:
            X = np.array([f.to_features() for f in frames])
            self._iso_forest = IsolationForest(
                contamination=self.contamination,
                random_state=42,
            )
            self._iso_forest.fit(X)
            self._fitted = True
            log.info("ai_ids.fitted", n_samples=len(frames), site_id=self.site_id)
        else:
            log.debug(
                "ai_ids.fit_skipped",
                reason="insufficient_samples" if len(frames) < self.min_fit_samples else "sklearn_unavailable",
                n_frames=len(frames),
                required=self.min_fit_samples,
            )

    def score(self, frame: ModbusFrame) -> float:
        """Return ensemble anomaly score in [0, 1].

        0.0 = completely normal
        1.0 = highly anomalous

        Returns 0.0 if no model has been trained yet (fail-safe).
        """
        iso_score = self._isolation_score(frame)
        z_score = self._zscore_timing(frame.timing_ms)
        ensemble = 0.4 * iso_score + 0.6 * z_score
        return float(np.clip(ensemble, 0.0, 1.0))

    def check_and_alert(self, frame: ModbusFrame) -> float:
        """Score the frame; if above threshold, log alert + update metrics.

        Returns the anomaly score.
        """
        s = self.score(frame)

        # Update Prometheus gauge always
        IDS_ANOMALY_SCORE.labels(site_id=self.site_id).set(s)

        if s >= self.threshold:
            IDS_ALERTS_TOTAL.labels(site_id=self.site_id, reason="anomaly").inc()
            log.warning(
                "ai_ids.anomaly_detected",
                score=round(s, 4),
                threshold=self.threshold,
                fc_code=frame.fc_code,
                address=frame.address,
                timing_ms=round(frame.timing_ms, 2),
                site_id=self.site_id,
            )
        else:
            log.debug("ai_ids.normal", score=round(s, 4), site_id=self.site_id)

        return s

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _isolation_score(self, frame: ModbusFrame) -> float:
        """IsolationForest score mapped to [0, 1].

        IsolationForest.decision_function returns negative → anomalous,
        positive → normal. We map to [0,1] by inverting and clamping.
        """
        if not self._fitted or self._iso_forest is None:
            return 0.0

        X = frame.to_features().reshape(1, -1)
        raw: float = float(self._iso_forest.decision_function(X)[0])
        # raw ∈ (-0.5, 0.5) typically; invert so high = anomalous
        score = float(np.clip(0.5 - raw, 0.0, 1.0))
        return score

    def _zscore_timing(self, timing_ms: float) -> float:
        """Z-score based timing anomaly, normalised to [0, 1].

        A timing deviation beyond 3σ yields score ≥ 1.
        """
        if not self._baseline_timings:
            return 0.0
        z = abs(timing_ms - self._timing_mean) / self._timing_std
        # Sigmoid-like mapping: z=0→0, z=3→~0.95
        return float(np.clip(z / (z + 1.0), 0.0, 1.0))
