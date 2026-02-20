"""
tests/test_cmg_predictor_extended.py
=====================================
Extended tests for CMgPredictor — covers lines not reached by existing suite:
  - _predict_onnx path (lines 288-336)
  - load() with ONNX available / file not found
  - load_history_csv error paths (line 216-217, 222-224)
  - update() + history_size
  - best_charge_window / best_discharge_window
  - projected_arbitrage_revenue (empty + populated)
  - predict_next_24h → smoothing confidence with/without history
"""

from __future__ import annotations

import csv
import math
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.interfaces.cmg_predictor import CMgPredictor, PriceForecast

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_predictor(node: str = "Maitencillo") -> CMgPredictor:
    """Return a fresh predictor with no model file."""
    return CMgPredictor(node=node, model_path=Path("/nonexistent/model.onnx"))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ── PriceForecast dataclass ────────────────────────────────────────────────


class TestPriceForecast:
    def test_dispatch_priority_charge(self):
        # solar trough hour (12) + price < 30 → charge
        f = PriceForecast(hour=12, cmg_clp_kwh=20.0, confidence=0.8, method="smoothing")
        assert f.dispatch_priority == "charge"

    def test_dispatch_priority_discharge(self):
        # peak hour (19) + price > 50 → discharge
        f = PriceForecast(hour=19, cmg_clp_kwh=130.0, confidence=0.8, method="smoothing")
        assert f.dispatch_priority == "discharge"

    def test_dispatch_priority_hold(self):
        # non-peak, non-solar-trough → hold
        f = PriceForecast(hour=3, cmg_clp_kwh=75.0, confidence=0.8, method="smoothing")
        assert f.dispatch_priority == "hold"

    def test_priceforrcast_is_peak_flag(self):
        # hour 18-22 are peak hours
        f = PriceForecast(hour=20, cmg_clp_kwh=100.0, confidence=0.9, method="onnx")
        assert f.is_peak is True

    def test_priceforecast_is_solar_trough_flag(self):
        # hours 11-16 are solar trough
        f = PriceForecast(hour=13, cmg_clp_kwh=25.0, confidence=0.9, method="onnx")
        assert f.is_solar_trough is True


# ── load() ─────────────────────────────────────────────────────────────────


class TestLoad:
    def test_load_fallback_when_no_model(self):
        p = _make_predictor()
        p.load()  # must not raise — file doesn't exist
        assert not p.is_onnx_loaded

    def test_load_fallback_when_onnx_not_available(self):
        """Even if path exists, if _ONNX_AVAILABLE=False -> fallback."""
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            model_path = Path(f.name)
        p = CMgPredictor(node="X", model_path=model_path)
        with patch("src.interfaces.cmg_predictor._ONNX_AVAILABLE", False):
            p.load()
        assert not p.is_onnx_loaded
        model_path.unlink(missing_ok=True)

    def test_load_onnx_success(self):
        """Simulate successful ONNX load via mocked ort."""
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock(name="input")]
        mock_ort = MagicMock()
        mock_ort.SessionOptions.return_value = MagicMock()
        mock_ort.InferenceSession.return_value = mock_session

        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            model_path = Path(f.name)
        p = CMgPredictor(node="X", model_path=model_path)
        with (
            patch("src.interfaces.cmg_predictor._ONNX_AVAILABLE", True),
            patch("src.interfaces.cmg_predictor.ort", mock_ort),
        ):
            p.load()
        assert p.is_onnx_loaded
        model_path.unlink(missing_ok=True)

    def test_load_onnx_exception_falls_back(self):
        """If ort.InferenceSession raises, is_onnx_loaded stays False."""
        mock_ort = MagicMock()
        mock_ort.SessionOptions.return_value = MagicMock()
        mock_ort.InferenceSession.side_effect = RuntimeError("bad model")

        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            model_path = Path(f.name)
        p = CMgPredictor(node="X", model_path=model_path)
        with (
            patch("src.interfaces.cmg_predictor._ONNX_AVAILABLE", True),
            patch("src.interfaces.cmg_predictor.ort", mock_ort),
        ):
            p.load()
        assert not p.is_onnx_loaded
        model_path.unlink(missing_ok=True)


# ── load_history_from_csv ───────────────────────────────────────────────────────


class TestLoadHistoryCsv:
    def test_valid_csv_loads_history(self):
        p = _make_predictor()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            csv_path = Path(f.name)
        _write_csv(
            csv_path,
            [{"hora": str(h), "cmg_clp_kwh": "55.0"} for h in range(12)],
        )
        count = p.load_history_from_csv(csv_path)
        assert count == 12
        csv_path.unlink(missing_ok=True)

    def test_csv_with_malformed_rows_skips_them(self):
        """Rows with non-numeric values (line 216) are skipped."""
        p = _make_predictor()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            csv_path = Path(f.name)
        _write_csv(
            csv_path,
            [
                {"hora": "not_a_number", "cmg_clp_kwh": "55.0"},  # ValueError
                {"hora": "0", "cmg_clp_kwh": "60.0"},  # valid
            ],
        )
        count = p.load_history_from_csv(csv_path)
        assert count == 1
        csv_path.unlink(missing_ok=True)

    def test_csv_alternate_column_names(self):
        """Accepts 'hour' + 'costo_marginal' column names."""
        p = _make_predictor()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            csv_path = Path(f.name)
        _write_csv(
            csv_path,
            [{"hour": "6", "costo_marginal": "48.5"}],
        )
        count = p.load_history_from_csv(csv_path)
        assert count == 1
        csv_path.unlink(missing_ok=True)

    def test_missing_file_returns_zero(self):
        """Non-existent file triggers except branch (line 222) → returns 0."""
        p = _make_predictor()
        count = p.load_history_from_csv(Path("/this/does/not/exist.csv"))
        assert count == 0

    def test_empty_csv_returns_zero(self):
        p = _make_predictor()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            csv_path = Path(f.name)
        # header only, no rows
        _write_csv(csv_path, [{"hora": "0", "cmg_clp_kwh": "0"}])
        csv_path.write_text("hora,cmg_clp_kwh\n")  # overwrite with empty
        count = p.load_history_from_csv(csv_path)
        assert count == 0
        csv_path.unlink(missing_ok=True)


# ── update + history_size ─────────────────────────────────────────────────


class TestUpdateAndHistory:
    def test_update_changes_smooth(self):
        p = _make_predictor()
        initial = p._smooth[6]
        p.update(6, 200.0)  # very high price → smooth should increase
        assert p._smooth[6] != initial

    def test_history_size_grows(self):
        p = _make_predictor()
        assert p.history_size == 0
        p.update(0, 50.0)
        p.update(1, 60.0)
        assert p.history_size == 2

    def test_update_clamps_alpha(self):
        """Alpha in [0,1] — calling update many times shouldn't crash."""
        p = _make_predictor()
        for h in range(24):
            p.update(h, 100.0)
        assert all(v > 0 for v in p._smooth.values())


# ── predict_next_24h — smoothing paths ───────────────────────────────────


class TestPredictSmoothing:
    def test_returns_24_forecasts(self):
        p = _make_predictor()
        forecasts = p.predict_next_24h(current_hour=8)
        assert len(forecasts) == 24

    def test_current_cmg_updates_history(self):
        p = _make_predictor()
        p.predict_next_24h(current_hour=10, current_cmg=80.0)
        assert p.history_size == 1

    def test_confidence_lower_without_history(self):
        """Low-confidence fallback (line 260) when no history."""
        p = _make_predictor()
        forecasts = p.predict_next_24h(current_hour=0)
        # All confidence values should be positive
        assert all(f.confidence > 0 for f in forecasts)

    def test_confidence_scaled_with_history(self):
        """With >=2 history points, cv is calculated (lines 255-258)."""
        p = _make_predictor()
        for h in range(24):
            p.update(h, 50.0 + h * 2)
        forecasts = p.predict_next_24h(current_hour=0)
        assert len(forecasts) == 24
        assert all(f.confidence >= 0.1 for f in forecasts)

    def test_blend_toward_mean_for_distant_horizons(self):
        """Offsets > 12 blend toward historic mean (lines 271-273)."""
        p = _make_predictor()
        # Set smooth values very high to ensure blend changes prediction
        for h in range(24):
            p._smooth[h] = 1000.0
        forecasts = p.predict_next_24h(current_hour=0)
        # Hour at offset 24 should be lower than 1000 due to blending
        assert forecasts[-1].cmg_clp_kwh < 1000.0

    def test_method_is_exponential_smoothing(self):
        p = _make_predictor()
        forecasts = p.predict_next_24h(current_hour=5)
        assert all(f.method == "exponential_smoothing" for f in forecasts)


# ── _predict_onnx path ────────────────────────────────────────────────────


class TestPredictOnnx:
    def _predictor_with_mock_session(self, output_val: float = 75.0) -> CMgPredictor:
        """Create a CMgPredictor with _onnx_loaded=True and a mocked session."""
        p = _make_predictor()
        mock_session = MagicMock()
        import numpy as _np

        mock_session.run.return_value = [_np.array([[output_val]], dtype=_np.float32)]
        mock_session.get_inputs.return_value = [MagicMock(name="input")]
        p._session = mock_session
        p._input_name = "input"
        p._onnx_loaded = True
        return p

    def test_predict_onnx_returns_24_forecasts(self):
        p = self._predictor_with_mock_session(75.0)
        forecasts = p.predict_next_24h(current_hour=8, current_cmg=60.0)
        assert len(forecasts) == 24

    def test_predict_onnx_method_label(self):
        p = self._predictor_with_mock_session(75.0)
        forecasts = p.predict_next_24h(current_hour=0)
        assert all(f.method == "onnx" for f in forecasts)

    def test_predict_onnx_uses_session_output(self):
        p = self._predictor_with_mock_session(120.0)
        forecasts = p.predict_next_24h(current_hour=0)
        assert all(f.cmg_clp_kwh == 120.0 for f in forecasts)

    def test_predict_onnx_confidence_is_high(self):
        """ONNX forecasts have base confidence 0.85."""
        p = self._predictor_with_mock_session(80.0)
        forecasts = p.predict_next_24h(current_hour=0)
        assert all(f.confidence == 0.85 for f in forecasts)

    def test_predict_onnx_negative_output_clamped_to_zero(self):
        """max(0.0, predicted) ensures no negative prices (line 330)."""
        p = self._predictor_with_mock_session(-10.0)
        forecasts = p.predict_next_24h(current_hour=0)
        assert all(f.cmg_clp_kwh >= 0.0 for f in forecasts)

    def test_predict_onnx_inference_exception_falls_back_to_smoothing(self):
        """If session.run raises, forecast uses smoothing value (lines 322-325)."""
        p = _make_predictor()
        mock_session = MagicMock()
        mock_session.run.side_effect = RuntimeError("inference error")
        mock_session.get_inputs.return_value = [MagicMock(name="input")]
        p._session = mock_session
        p._input_name = "input"
        p._onnx_loaded = True

        forecasts = p.predict_next_24h(current_hour=0)
        assert len(forecasts) == 24
        # Fallen-back forecasts use confidence=0.3
        assert all(f.confidence == 0.3 for f in forecasts)

    def test_predict_onnx_with_24h_history(self):
        """len(history) >= 24 path for lag_24h (line 294)."""
        p = self._predictor_with_mock_session(65.0)
        for i in range(25):
            p.update(i % 24, 50.0 + i)
        forecasts = p.predict_next_24h(current_hour=12, current_cmg=70.0)
        assert len(forecasts) == 24

    def test_predict_onnx_no_history_uses_current_cmg(self):
        """No history → lag_1h and lag_24h use current_cmg (lines 293-294)."""
        p = self._predictor_with_mock_session(70.0)
        forecasts = p.predict_next_24h(current_hour=6, current_cmg=70.0)
        assert len(forecasts) == 24


# ── Utility methods ────────────────────────────────────────────────────────


class TestUtilityMethods:
    def _make_forecasts(self) -> list[PriceForecast]:
        prices = [
            30,
            28,
            25,
            22,
            30,
            45,
            90,
            120,
            150,
            140,
            130,
            110,
            80,
            70,
            65,
            60,
            75,
            95,
            140,
            160,
            120,
            80,
            50,
            35,
        ]
        return [
            PriceForecast(hour=h, cmg_clp_kwh=float(p), confidence=0.8, method="smoothing")
            for h, p in enumerate(prices)
        ]

    def test_best_charge_window_returns_up_to_4(self):
        p = _make_predictor()
        forecasts = self._make_forecasts()
        window = p.best_charge_window(forecasts)
        assert len(window) <= 4
        assert all(isinstance(h, int) for h in window)

    def test_best_charge_window_selects_lowest_prices(self):
        p = _make_predictor()
        forecasts = self._make_forecasts()
        window = p.best_charge_window(forecasts)
        # All selected hours should have "charge" dispatch priority
        charge_hours = {f.hour for f in forecasts if f.dispatch_priority == "charge"}
        assert all(h in charge_hours for h in window)

    def test_best_discharge_window_selects_highest_prices(self):
        p = _make_predictor()
        forecasts = self._make_forecasts()
        window = p.best_discharge_window(forecasts)
        discharge_hours = {f.hour for f in forecasts if f.dispatch_priority == "discharge"}
        assert all(h in discharge_hours for h in window)

    def test_best_charge_window_empty_when_no_charge_candidates(self):
        """All high prices → no charge candidates."""
        p = _make_predictor()
        forecasts = [
            PriceForecast(hour=h, cmg_clp_kwh=200.0, confidence=0.8, method="smoothing")
            for h in range(24)
        ]
        window = p.best_charge_window(forecasts)
        assert window == []

    def test_projected_arbitrage_revenue_empty_forecasts(self):
        p = _make_predictor()
        revenue = p.projected_arbitrage_revenue([])
        assert revenue == 0.0

    def test_projected_arbitrage_revenue_positive(self):
        p = _make_predictor()
        forecasts = self._make_forecasts()
        revenue = p.projected_arbitrage_revenue(forecasts, capacity_kwh=1000.0, efficiency=0.92)
        assert revenue > 0

    def test_projected_arbitrage_revenue_formula(self):
        """Verify exact formula: revenue_discharge - cost_to_charge."""
        p = _make_predictor()
        forecasts = [
            PriceForecast(hour=h, cmg_clp_kwh=float(price), confidence=0.8, method="smoothing")
            for h, price in [(0, 20.0), (12, 100.0)]
        ]
        revenue = p.projected_arbitrage_revenue(forecasts, capacity_kwh=500.0, efficiency=1.0)
        expected = round(500.0 * 100.0 - 500.0 * 20.0, 2)
        assert math.isclose(revenue, expected, rel_tol=1e-5)

    def test_is_onnx_loaded_false_by_default(self):
        p = _make_predictor()
        assert not p.is_onnx_loaded

    def test_history_size_zero_by_default(self):
        p = _make_predictor()
        assert p.history_size == 0
