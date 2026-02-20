"""
src/interfaces/cmg_predictor.py
================================
BESSAI Edge Gateway — CMg Price Predictor v2.

Mejoras v2:
  - TTL cache (30 min) en predict_next_24h() → sin recómputo innecesario
  - 11 features (+ lag_168h, is_weekend) para coincidir con train_price_model v2
  - Bandas de incertidumbre p10/p90 via modelos cuantílicos opcionales
  - invalidate_cache() explícito cuando llega nueva observación con delta > umbral

Architecture (degradation chain):
    ONNX price model → Exponential Smoothing → Historic Daily Mean

Features ONNX (en orden):
    [soc_pct, hour_of_day, day_of_week, recent_mean_cmg, recent_std_cmg,
     peak_flag, solar_hour_flag, lag_1h, lag_24h, lag_168h, is_weekend]

Usage::

    predictor = CMgPredictor(node="Maitencillo", history_path="data/historical")
    predictor.load()
    forecast = predictor.predict_next_24h(current_hour=14, current_cmg=52.3)
    for h in forecast:
        print(h.hour, h.cmg_clp_kwh, h.confidence, h.cmg_p10, h.cmg_p90)
"""

from __future__ import annotations

import math
import statistics
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

__all__ = ["CMgPredictor", "PriceForecast"]

log = structlog.get_logger(__name__)

# ── Optional deps ─────────────────────────────────────────────────────────────
try:
    import numpy as np
    import onnxruntime as ort  # type: ignore[import-untyped]
    _ONNX_AVAILABLE = True
except ImportError:
    _ONNX_AVAILABLE = False
    np = None   # type: ignore[assignment]
    ort = None  # type: ignore[assignment]

# ── Chilean SEN hourly CMg profile (CLP/kWh) — empirical 2023-2024 aggregate ─
_HOURLY_MEAN_CMG: list[float] = [
    38.2, 36.1, 34.8, 34.1, 33.9, 35.2,  # 00-05  Off-peak
    42.1, 58.3, 71.2, 61.4, 48.3, 38.9,  # 06-11  Morning ramp
    29.4, 24.1, 22.8, 21.3, 22.1, 28.7,  # 12-17  Solar trough
    44.2, 62.3, 78.4, 71.2, 58.3, 46.1,  # 18-23  Evening peak
]

_PEAK_HOURS: frozenset[int] = frozenset({18, 19, 20, 21, 22})
_SOLAR_TROUGH_HOURS: frozenset[int] = frozenset({11, 12, 13, 14, 15, 16})

# Feature list (must stay in sync with train_price_model.py v2)
_FEATURE_NAMES_V2 = [
    "soc_pct", "hour_of_day", "day_of_week",
    "recent_mean_cmg", "recent_std_cmg",
    "peak_flag", "solar_hour_flag",
    "lag_1h", "lag_24h", "lag_168h", "is_weekend",
]
_FEATURE_NAMES_V1 = [
    "soc_pct", "hour_of_day", "day_of_week",
    "recent_mean_cmg", "recent_std_cmg",
    "peak_flag", "solar_hour_flag",
    "lag_1h", "lag_24h",
]

# Cache TTL — 30 minutes.  Override for testing.
_CACHE_TTL_S: float = 1800.0

# Minimum CMg delta (CLP/kWh) to trigger cache invalidation on new observation.
_CACHE_INVALIDATE_DELTA: float = 5.0


@dataclass
class PriceForecast:
    """Single-hour CMg price forecast with uncertainty bands.

    Attributes:
        hour:            Hour-of-day (0-23).
        cmg_clp_kwh:     Predicted price in CLP/kWh (point estimate).
        cmg_p10:         p10 lower band (CLP/kWh) — from quantile model if available.
        cmg_p90:         p90 upper band (CLP/kWh) — from quantile model if available.
        confidence:      Confidence level [0, 1].
        method:          'onnx' | 'exponential_smoothing' | 'historic_mean'.
        is_peak:         True if SEN peak hour.
        is_solar_trough: True if solar generation typically depresses price.
    """

    hour: int
    cmg_clp_kwh: float
    confidence: float = 1.0
    method: str = "historic_mean"
    cmg_p10: float = 0.0
    cmg_p90: float = 0.0
    is_peak: bool = field(init=False)
    is_solar_trough: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_peak = self.hour in _PEAK_HOURS
        self.is_solar_trough = self.hour in _SOLAR_TROUGH_HOURS
        # Default bands: ±15% if not provided
        if self.cmg_p90 == 0.0:
            self.cmg_p90 = round(self.cmg_clp_kwh * 1.15, 2)
        if self.cmg_p10 == 0.0:
            self.cmg_p10 = round(self.cmg_clp_kwh * 0.85, 2)

    @property
    def spread_clp(self) -> float:
        """p90 - p10 band width (uncertainty)."""
        return round(self.cmg_p90 - self.cmg_p10, 2)

    @property
    def is_high_confidence(self) -> bool:
        """True when the uncertainty band is < 20% of the point estimate."""
        if self.cmg_clp_kwh <= 0:
            return False
        return (self.spread_clp / self.cmg_clp_kwh) < 0.20

    @property
    def dispatch_priority(self) -> str:
        """Quick label for dispatch scheduling."""
        if self.is_peak and self.cmg_clp_kwh > 50:
            return "discharge"
        if self.is_solar_trough and self.cmg_clp_kwh < 30:
            return "charge"
        return "hold"


class CMgPredictor:
    """Predicts PMGD prices for the next 24 hours (v2).

    Parameters:
        node:            SEN node name.
        model_path:      Path to main ONNX model (float32 or int8).
        model_p10_path:  Path to p10 quantile ONNX model (optional).
        model_p90_path:  Path to p90 quantile ONNX model (optional).
        history_window:  Max observations kept in rolling buffer.
        alpha:           Exponential smoothing factor [0, 1].
        cache_ttl_s:     Seconds before forecast cache expires (default 1800).
    """

    def __init__(
        self,
        node: str = "Maitencillo",
        model_path: str | Path = "models/price_predictor.onnx",
        model_p10_path: Optional[str | Path] = None,
        model_p90_path: Optional[str | Path] = None,
        history_window: int = 192,   # 8 days → supports lag_168h
        alpha: float = 0.3,
        cache_ttl_s: float = _CACHE_TTL_S,
    ) -> None:
        self.node = node
        self.model_path = Path(model_path)
        self.history_window = history_window
        self.alpha = alpha
        self._cache_ttl_s = cache_ttl_s

        # Auto-discover int8 version if base path given
        int8_path = self.model_path.with_stem(self.model_path.stem + "_int8")
        if int8_path.exists():
            self.model_path = int8_path
            log.info("cmg_predictor.using_int8", node=node, path=str(int8_path))

        # Quantile model paths (auto-discover from base path)
        def _q_path(suffix: str, override: Optional[str | Path]) -> Path:
            if override:
                return Path(override)
            base = Path(model_path)
            return base.with_stem(base.stem.replace("_int8", "") + suffix)

        self._p10_path = _q_path("_p10", model_p10_path)
        self._p90_path = _q_path("_p90", model_p90_path)

        # Rolling history: list of (hour, cmg) tuples
        self._history: list[tuple[int, float]] = []

        # ONNX sessions
        self._session: object | None = None
        self._session_p10: object | None = None
        self._session_p90: object | None = None
        self._input_name: str | None = None
        self._onnx_loaded: bool = False
        self._quantile_loaded: bool = False
        self._n_features: int = 9  # detected on load

        # Exponential smoothing state per hour
        self._smooth: dict[int, float] = {h: _HOURLY_MEAN_CMG[h] for h in range(24)}

        # Forecast cache: (timestamp_s, [PriceForecast])
        self._cache: Optional[tuple[float, list[PriceForecast]]] = None

    # ── Model Loading ─────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load ONNX models (main + quantile). Fails silently → smoothing fallback."""
        if not (_ONNX_AVAILABLE and self.model_path.exists()):
            log.info(
                "cmg_predictor.fallback_mode", node=self.node,
                reason="no_onnx_model" if not self.model_path.exists() else "onnxruntime_missing",
            )
            return

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        opts.intra_op_num_threads = 1   # prevents thread-pool churn on edge device

        try:
            self._session = ort.InferenceSession(
                str(self.model_path), sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            self._input_name = self._session.get_inputs()[0].name  # type: ignore[union-attr]
            self._n_features = self._session.get_inputs()[0].shape[1]  # type: ignore[union-attr]
            self._onnx_loaded = True
            log.info(
                "cmg_predictor.onnx_loaded", node=self.node,
                path=str(self.model_path), n_features=self._n_features,
            )
        except Exception as exc:
            log.warning("cmg_predictor.onnx_load_failed", error=str(exc), node=self.node)
            return

        # Load quantile models if available
        for attr, path, label in [
            ("_session_p10", self._p10_path, "p10"),
            ("_session_p90", self._p90_path, "p90"),
        ]:
            if path.exists():
                try:
                    setattr(self, attr, ort.InferenceSession(
                        str(path), sess_options=opts,
                        providers=["CPUExecutionProvider"],
                    ))
                    log.info("cmg_predictor.quantile_loaded", label=label, path=str(path))
                    self._quantile_loaded = True
                except Exception as exc:
                    log.warning("cmg_predictor.quantile_load_failed", label=label, error=str(exc))

    # ── History Update ────────────────────────────────────────────────────────

    def update(self, hour: int, cmg_clp_kwh: float) -> None:
        """Feed a new CMg observation. Invalidates cache if price delta > threshold."""
        # Invalidate cache on large price movement
        if (
            self._cache is not None
            and self._history
            and abs(cmg_clp_kwh - self._history[-1][1]) > _CACHE_INVALIDATE_DELTA
        ):
            self._cache = None

        self._history.append((hour, cmg_clp_kwh))
        if len(self._history) > self.history_window:
            self._history.pop(0)

        # Update smoothing for this hour
        prev = self._smooth.get(hour, _HOURLY_MEAN_CMG[hour])
        self._smooth[hour] = self.alpha * cmg_clp_kwh + (1 - self.alpha) * prev

    def invalidate_cache(self) -> None:
        """Force cache expiry on next predict call."""
        self._cache = None

    def load_history_from_csv(self, csv_path: Path) -> int:
        """Seed rolling history from CSV (columns: hora, cmg_clp_kwh).

        Returns number of rows loaded.
        """
        try:
            import csv

            count = 0
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = sorted(reader, key=lambda r: (r.get("fecha", ""), r.get("hora", "0")))
                for row in rows[-self.history_window:]:
                    try:
                        h   = int(float(row.get("hora", row.get("hour", 0))))
                        cmg = float(row.get("cmg_clp_kwh", row.get("costo_marginal", 0)))
                        self.update(h, cmg)
                        count += 1
                    except (ValueError, KeyError):
                        continue
            log.info("cmg_predictor.history_loaded", node=self.node, rows=count)
            return count
        except Exception as exc:
            log.warning("cmg_predictor.history_load_failed", error=str(exc))
            return 0

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_next_24h(
        self,
        current_hour: int,
        current_cmg: Optional[float] = None,
    ) -> list[PriceForecast]:
        """Generate 24h price forecasts with uncertainty bands.

        Uses a 30-minute TTL cache to avoid redundant inference on every
        telemetry cycle. Cache is invalidated when price delta > 5 CLP/kWh.

        Args:
            current_hour: Current hour-of-day (0-23).
            current_cmg:  Latest observed CMg (CLP/kWh). Updates history.

        Returns:
            List of 24 PriceForecast objects ordered by hour starting at
            (current_hour + 1) % 24.
        """
        if current_cmg is not None:
            self.update(current_hour, current_cmg)

        # ── TTL cache check ──
        now = _time.monotonic()
        if (
            self._cache is not None
            and (now - self._cache[0]) < self._cache_ttl_s
        ):
            return self._cache[1]

        # ── Compute fresh forecast ──
        if self._onnx_loaded and self._session is not None:
            result = self._predict_onnx(current_hour, current_cmg or 0.0)
        else:
            result = self._predict_smoothing(current_hour)

        self._cache = (now, result)
        return result

    def _predict_smoothing(self, current_hour: int) -> list[PriceForecast]:
        """Exponential smoothing prediction — no ML dependencies."""
        recent_vals = [v for _, v in self._history[-24:]] if self._history else []
        if len(recent_vals) >= 2:
            std  = statistics.stdev(recent_vals)
            mean = statistics.mean(recent_vals)
            cv   = std / mean if mean > 0 else 0.5
        else:
            cv = 0.5

        forecasts: list[PriceForecast] = []
        for offset in range(1, 25):
            h         = (current_hour + offset) % 24
            predicted = self._smooth[h]
            horizon_decay = math.exp(-offset / 12)
            confidence    = max(0.1, (1 - cv) * horizon_decay)

            if offset > 12:
                w         = (offset - 12) / 12
                predicted = (1 - w) * predicted + w * _HOURLY_MEAN_CMG[h]

            # Simple ±15% bands scaled by confidence
            band = predicted * (0.3 - 0.2 * confidence)
            forecasts.append(PriceForecast(
                hour=h,
                cmg_clp_kwh=round(predicted, 2),
                confidence=round(confidence, 3),
                method="exponential_smoothing",
                cmg_p10=round(max(0.0, predicted - band), 2),
                cmg_p90=round(predicted + band, 2),
            ))
        return forecasts

    def _make_feature_vector(
        self,
        h: int,
        recent_mean: float,
        recent_std: float,
        lag_1h: float,
        lag_24h: float,
        lag_168h: float,
        day_of_week: float = 0.0,
        soc_pct: float = 50.0,
    ) -> "np.ndarray":
        """Build the input feature vector for ONNX inference."""
        is_weekend = float(int(day_of_week) >= 5)
        if self._n_features == 11:
            # v2 model
            vec = [
                soc_pct, h, day_of_week,
                recent_mean, recent_std,
                float(h in _PEAK_HOURS), float(h in _SOLAR_TROUGH_HOURS),
                lag_1h, lag_24h, lag_168h, is_weekend,
            ]
        else:
            # v1 model (9 features, backwards compat)
            vec = [
                soc_pct, h, day_of_week,
                recent_mean, recent_std,
                float(h in _PEAK_HOURS), float(h in _SOLAR_TROUGH_HOURS),
                lag_1h, lag_24h,
            ]
        return np.array([vec], dtype=np.float32)

    def _run_session(self, session: object, features: "np.ndarray") -> float:
        """Run a single ONNX session and return scalar output."""
        out = session.run(None, {self._input_name: features})  # type: ignore[union-attr]
        return float(out[0].flatten()[0])

    def _predict_onnx(self, current_hour: int, current_cmg: float) -> list[PriceForecast]:
        """ONNX inference for all 24h slots, with optional quantile bands."""
        recent_vals  = [v for _, v in self._history[-24:]] or [current_cmg]
        recent_mean  = statistics.mean(recent_vals) if recent_vals else _HOURLY_MEAN_CMG[current_hour]
        recent_std   = statistics.stdev(recent_vals) if len(recent_vals) > 1 else 5.0
        lag_1h       = self._history[-1][1]   if self._history          else current_cmg
        lag_24h      = self._history[-24][1]  if len(self._history) >= 24  else recent_mean
        lag_168h     = self._history[-168][1] if len(self._history) >= 168 else recent_mean

        forecasts: list[PriceForecast] = []
        for offset in range(1, 25):
            h        = (current_hour + offset) % 24
            features = self._make_feature_vector(h, recent_mean, recent_std, lag_1h, lag_24h, lag_168h)

            try:
                predicted = max(0.0, self._run_session(self._session, features))
                confidence = 0.85

                # Quantile bands
                p10 = p90 = 0.0
                if self._quantile_loaded:
                    try:
                        p10 = max(0.0, self._run_session(self._session_p10, features))
                        p90 = max(0.0, self._run_session(self._session_p90, features))
                    except Exception:
                        pass

                    # Narrow bands → higher confidence
                    if predicted > 0 and p90 > p10:
                        band_ratio = (p90 - p10) / predicted
                        confidence = max(0.3, min(0.98, 1 - band_ratio * 0.5))

            except Exception as exc:
                log.warning("cmg_predictor.onnx_inference_error", error=str(exc), hour=h)
                predicted  = self._smooth[h]
                confidence = 0.3
                p10 = p90  = 0.0

            forecasts.append(PriceForecast(
                hour=h,
                cmg_clp_kwh=round(predicted, 2),
                confidence=round(confidence, 3),
                method="onnx",
                cmg_p10=round(p10, 2) if p10 else 0.0,
                cmg_p90=round(p90, 2) if p90 else 0.0,
            ))
        return forecasts

    # ── Utilities ─────────────────────────────────────────────────────────────

    @property
    def is_onnx_loaded(self) -> bool:
        return self._onnx_loaded

    @property
    def has_quantile_models(self) -> bool:
        return self._quantile_loaded

    @property
    def history_size(self) -> int:
        return len(self._history)

    @property
    def cache_age_s(self) -> float:
        """Seconds since last forecast was cached (0 if no cache)."""
        if self._cache is None:
            return 0.0
        return _time.monotonic() - self._cache[0]

    def best_charge_window(self, forecasts: list[PriceForecast]) -> list[int]:
        """Return hours most suitable for charging (lowest price + high confidence)."""
        candidates = [f for f in forecasts if f.dispatch_priority == "charge"]
        candidates.sort(key=lambda f: (f.cmg_clp_kwh, -f.confidence))
        return [f.hour for f in candidates[:4]]

    def best_discharge_window(self, forecasts: list[PriceForecast]) -> list[int]:
        """Return hours most suitable for discharging (highest price + high confidence)."""
        candidates = [f for f in forecasts if f.dispatch_priority == "discharge"]
        candidates.sort(key=lambda f: (-f.cmg_clp_kwh, -f.confidence))
        return [f.hour for f in candidates[:4]]

    def projected_arbitrage_revenue(
        self,
        forecasts: list[PriceForecast],
        capacity_kwh: float = 1000.0,
        efficiency: float = 0.92,
    ) -> float:
        """Estimate daily arbitrage revenue (CLP) using point-estimate prices."""
        if not forecasts:
            return 0.0
        prices             = [f.cmg_clp_kwh for f in forecasts]
        energy_dispatched  = capacity_kwh * efficiency
        cost_to_charge     = capacity_kwh * min(prices)
        revenue_discharge  = energy_dispatched * max(prices)
        return round(revenue_discharge - cost_to_charge, 2)

    def projected_arbitrage_revenue_conservative(
        self,
        forecasts: list[PriceForecast],
        capacity_kwh: float = 1000.0,
        efficiency: float = 0.92,
    ) -> float:
        """Conservative estimate: charge at p90 (worst charge price), discharge at p10 (worst discharge)."""
        if not forecasts:
            return 0.0
        charge_price    = max((f.cmg_p90 for f in forecasts), default=0.0)
        discharge_price = min((f.cmg_p10 for f in forecasts if f.is_peak), default=0.0)
        energy          = capacity_kwh * efficiency
        return round(energy * discharge_price - capacity_kwh * charge_price, 2)
