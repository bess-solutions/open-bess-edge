"""
src/interfaces/cmg_predictor.py
================================
BESSAI Edge Gateway — CMg Price Predictor.

Predicts hourly PMGD prices (CLP/kWh) for the next 24 hours using a
lightweight exponential smoothing model that runs without ML dependencies.

When an ONNX price model is available at ``models/price_predictor.onnx``,
it is loaded and used instead (LSTM/Transformer trained offline).

Architecture (degradation chain):
    ONNX price model → Exponential Smoothing → Historic Daily Mean → Flat fallback

Features used by the ONNX model (in order):
    [soc_pct, hour_of_day, day_of_week, recent_mean_cmg, recent_std_cmg,
     peak_flag, solar_hour_flag, lag_1h, lag_24h]

Output:
    List of 24 PriceForecast objects (one per hour, starting from next hour).

Usage::

    predictor = CMgPredictor(node="Maitencillo", history_path="data/historical")
    predictor.load()
    forecast = predictor.predict_next_24h(current_hour=14, current_cmg=52.3)
    for h in forecast:
        print(h.hour, h.cmg_clp_kwh, h.confidence)
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import structlog

__all__ = ["CMgPredictor", "PriceForecast"]

log = structlog.get_logger(__name__)

# Try ONNX for price prediction model
try:
    import numpy as np
    import onnxruntime as ort  # type: ignore[import-untyped]

    _ONNX_AVAILABLE = True
except ImportError:
    _ONNX_AVAILABLE = False
    np = None  # type: ignore[assignment]
    ort = None  # type: ignore[assignment]

# ── Chilean SEN seasonal CMg profile (CLP/kWh) — mean by hour (empirical)
# Source: Coordinador Eléctrico Nacional PMGD 2023-2024 aggregate
_HOURLY_MEAN_CMG: list[float] = [
    38.2,
    36.1,
    34.8,
    34.1,
    33.9,
    35.2,  # 00-05  Off-peak
    42.1,
    58.3,
    71.2,
    61.4,
    48.3,
    38.9,  # 06-11  Morning ramp
    29.4,
    24.1,
    22.8,
    21.3,
    22.1,
    28.7,  # 12-17  Solar trough
    44.2,
    62.3,
    78.4,
    71.2,
    58.3,
    46.1,  # 18-23  Evening peak
]

# Peak hours in Chilean SEN (where discharge is most valuable)
_PEAK_HOURS: frozenset[int] = frozenset({18, 19, 20, 21, 22})
_SOLAR_TROUGH_HOURS: frozenset[int] = frozenset({11, 12, 13, 14, 15, 16})


@dataclass
class PriceForecast:
    """Single-hour CMg price forecast.

    Attributes:
        hour:           Hour-of-day (0-23).
        cmg_clp_kwh:    Predicted price in CLP/kWh.
        confidence:     Confidence level [0, 1] — lower = more uncertain.
        method:         Model used: 'onnx', 'exponential_smoothing', 'historic_mean'.
        is_peak:        Whether this hour is SEN peak (high discharge value).
        is_solar_trough: Whether solar generation typically depresses prices.
    """

    hour: int
    cmg_clp_kwh: float
    confidence: float = 1.0
    method: str = "historic_mean"
    is_peak: bool = field(init=False)
    is_solar_trough: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_peak = self.hour in _PEAK_HOURS
        self.is_solar_trough = self.hour in _SOLAR_TROUGH_HOURS

    @property
    def dispatch_priority(self) -> str:
        """Quick label for dispatch scheduling."""
        if self.is_peak and self.cmg_clp_kwh > 50:
            return "discharge"
        if self.is_solar_trough and self.cmg_clp_kwh < 30:
            return "charge"
        return "hold"


class CMgPredictor:
    """Predicts PMGD prices for the next 24 hours.

    Parameters:
        node:           SEN node name (used for logging and model selection).
        model_path:     Path to ONNX price prediction model (optional).
        history_window: Number of recent observations used for smoothing.
        alpha:          Exponential smoothing factor [0, 1] (higher = more reactive).
    """

    def __init__(
        self,
        node: str = "Maitencillo",
        model_path: str | Path = "models/price_predictor.onnx",
        history_window: int = 72,  # 3 days of hourly data
        alpha: float = 0.3,
    ) -> None:
        self.node = node
        self.model_path = Path(model_path)
        self.history_window = history_window
        self.alpha = alpha

        # Rolling history buffer: list of (hour, cmg) tuples
        self._history: list[tuple[int, float]] = []
        self._session: object | None = None  # ort.InferenceSession
        self._input_name: str | None = None
        self._onnx_loaded: bool = False

        # Exponential smoothing state per hour
        self._smooth: dict[int, float] = {h: _HOURLY_MEAN_CMG[h] for h in range(24)}

    # ── Model Loading ─────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load ONNX model if available. Falls back to smoothing silently."""
        if _ONNX_AVAILABLE and self.model_path.exists():
            try:
                opts = ort.SessionOptions()
                opts.log_severity_level = 3
                self._session = ort.InferenceSession(
                    str(self.model_path),
                    sess_options=opts,
                    providers=["CPUExecutionProvider"],
                )
                assert self._session is not None
                self._input_name = self._session.get_inputs()[0].name  # type: ignore[union-attr]
                self._onnx_loaded = True
                log.info("cmg_predictor.onnx_loaded", node=self.node, path=str(self.model_path))
            except Exception as exc:
                log.warning("cmg_predictor.onnx_load_failed", error=str(exc), node=self.node)
        else:
            log.info(
                "cmg_predictor.fallback_mode",
                node=self.node,
                reason="no_onnx_model" if not self.model_path.exists() else "onnxruntime_missing",
            )

    # ── History Update ────────────────────────────────────────────────────────

    def update(self, hour: int, cmg_clp_kwh: float) -> None:
        """Feed a new observed price into the predictor state.

        Args:
            hour:           Hour-of-day (0-23) of the observation.
            cmg_clp_kwh:    Observed CMg price in CLP/kWh.
        """
        self._history.append((hour, cmg_clp_kwh))
        if len(self._history) > self.history_window:
            self._history.pop(0)

        # Update exponential smoothing for this hour slot
        prev = self._smooth.get(hour, _HOURLY_MEAN_CMG[hour])
        self._smooth[hour] = self.alpha * cmg_clp_kwh + (1 - self.alpha) * prev

    def load_history_from_csv(self, csv_path: Path) -> int:
        """Seed history from a CSV file with columns: hora, cmg_clp_kwh.

        Returns number of rows loaded.
        """
        try:
            import csv

            count = 0
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = sorted(reader, key=lambda r: (r.get("fecha", ""), r.get("hora", "0")))
                # Use last history_window rows
                for row in rows[-self.history_window :]:
                    try:
                        h = int(float(row.get("hora", row.get("hour", 0))))
                        cmg = float(row.get("cmg_clp_kwh", row.get("costo_marginal", 0)))
                        self.update(h, cmg)
                        count += 1
                    except (ValueError, KeyError):
                        continue
            log.info(
                "cmg_predictor.history_loaded", node=self.node, rows=count, path=str(csv_path)
            )
            return count
        except Exception as exc:
            log.warning("cmg_predictor.history_load_failed", error=str(exc), path=str(csv_path))
            return 0

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_next_24h(
        self,
        current_hour: int,
        current_cmg: float | None = None,
    ) -> list[PriceForecast]:
        """Generate price forecasts for the next 24 hours.

        Args:
            current_hour: Current hour-of-day (0-23).
            current_cmg:  Latest observed CMg price (CLP/kWh). Updates history.

        Returns:
            List of 24 PriceForecast objects, ordered by hour.
        """
        if current_cmg is not None:
            self.update(current_hour, current_cmg)

        if self._onnx_loaded and self._session is not None:
            return self._predict_onnx(current_hour, current_cmg or 0.0)
        return self._predict_smoothing(current_hour)

    def _predict_smoothing(self, current_hour: int) -> list[PriceForecast]:
        """Exponential smoothing prediction — no ML dependencies."""
        forecasts: list[PriceForecast] = []

        # Compute recent spread to scale confidence
        recent_vals = [v for _, v in self._history[-24:]] if self._history else []
        if len(recent_vals) >= 2:
            std = statistics.stdev(recent_vals)
            mean = statistics.mean(recent_vals)
            cv = std / mean if mean > 0 else 0.5
        else:
            cv = 0.5  # no history → low confidence

        for offset in range(1, 25):
            h = (current_hour + offset) % 24
            predicted = self._smooth[h]

            # Decay confidence with forecast horizon
            horizon_decay = math.exp(-offset / 12)  # half-life ~8h
            confidence = max(0.1, (1 - cv) * horizon_decay)

            # Blend toward historic mean for distant horizons
            if offset > 12:
                weight = (offset - 12) / 12
                predicted = (1 - weight) * predicted + weight * _HOURLY_MEAN_CMG[h]

            forecasts.append(
                PriceForecast(
                    hour=h,
                    cmg_clp_kwh=round(predicted, 2),
                    confidence=round(confidence, 3),
                    method="exponential_smoothing",
                )
            )

        return forecasts

    def _predict_onnx(self, current_hour: int, current_cmg: float) -> list[PriceForecast]:
        """ONNX model inference for 24h price forecast."""
        recent_vals = [v for _, v in self._history[-24:]] if self._history else [current_cmg]
        recent_mean = (
            statistics.mean(recent_vals) if recent_vals else _HOURLY_MEAN_CMG[current_hour]
        )
        recent_std = statistics.stdev(recent_vals) if len(recent_vals) > 1 else 5.0
        lag_1h = self._history[-1][1] if self._history else current_cmg
        lag_24h = self._history[-24][1] if len(self._history) >= 24 else recent_mean

        forecasts: list[PriceForecast] = []

        for offset in range(1, 25):
            h = (current_hour + offset) % 24
            features = np.array(
                [
                    [
                        50.0,  # soc_pct placeholder (updated by orchestrator)
                        h,  # hour_of_day
                        0.0,  # day_of_week (unknown)
                        recent_mean,  # recent_mean_cmg
                        recent_std,  # recent_std_cmg
                        float(h in _PEAK_HOURS),  # peak_flag
                        float(h in _SOLAR_TROUGH_HOURS),  # solar_hour_flag
                        lag_1h,  # lag_1h
                        lag_24h,  # lag_24h
                    ]
                ],
                dtype=np.float32,
            )

            try:
                assert self._session is not None
                output = self._session.run(None, {self._input_name: features})  # type: ignore[attr-defined]
                predicted = float(output[0].flatten()[0])
                confidence = 0.85  # ONNX model: higher base confidence
            except Exception as exc:
                log.warning("cmg_predictor.onnx_inference_error", error=str(exc), hour=h)
                predicted = self._smooth[h]
                confidence = 0.3

            forecasts.append(
                PriceForecast(
                    hour=h,
                    cmg_clp_kwh=round(max(0.0, predicted), 2),
                    confidence=confidence,
                    method="onnx",
                )
            )

        return forecasts

    # ── Utilities ─────────────────────────────────────────────────────────────

    @property
    def is_onnx_loaded(self) -> bool:
        return self._onnx_loaded

    @property
    def history_size(self) -> int:
        return len(self._history)

    def best_charge_window(self, forecasts: list[PriceForecast]) -> list[int]:
        """Return hours where charging is most recommended (lowest prices)."""
        charge_candidates = [f for f in forecasts if f.dispatch_priority == "charge"]
        sorted_by_price = sorted(charge_candidates, key=lambda f: f.cmg_clp_kwh)
        return [f.hour for f in sorted_by_price[:4]]

    def best_discharge_window(self, forecasts: list[PriceForecast]) -> list[int]:
        """Return hours where discharging is most recommended (highest prices)."""
        discharge_candidates = [f for f in forecasts if f.dispatch_priority == "discharge"]
        sorted_by_price = sorted(discharge_candidates, key=lambda f: -f.cmg_clp_kwh)
        return [f.hour for f in sorted_by_price[:4]]

    def projected_arbitrage_revenue(
        self,
        forecasts: list[PriceForecast],
        capacity_kwh: float = 1000.0,
        efficiency: float = 0.92,
    ) -> float:
        """Estimate daily arbitrage revenue (CLP) given a capacity.

        Simplified: assumes full charge at min price hours, full discharge at max.

        Args:
            capacity_kwh:  Usable battery capacity in kWh.
            efficiency:    Round-trip efficiency (default 92%).

        Returns:
            Projected daily revenue in CLP.
        """
        if not forecasts:
            return 0.0

        prices = [f.cmg_clp_kwh for f in forecasts]
        min_price = min(prices)
        max_price = max(prices)

        energy_dispatched = capacity_kwh * efficiency
        cost_to_charge = capacity_kwh * min_price
        revenue_discharge = energy_dispatched * max_price

        return round(revenue_discharge - cost_to_charge, 2)
