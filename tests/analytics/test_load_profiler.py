# SPDX-License-Identifier: Apache-2.0
# Copyright 2025-2026 BESS Solutions. All rights reserved.
"""Tests para src/analytics/load_profiler.py — Mercado México (CFE GDMTH)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from src.analytics import LoadProfiler, LoadSummary

# ── Helpers / Fixtures ────────────────────────────────────────────────────────

def make_df(start: str = "2024-01-15", days: int = 1, resolution_min: int = 15,
            base_kw: float = 100.0, seed: int = 0) -> pd.DataFrame:
    """Genera un DataFrame de prueba con demanda constante + ruido pequeño."""
    rng = np.random.default_rng(seed)
    freq = f"{resolution_min}min"
    n = days * 24 * (60 // resolution_min)
    idx = pd.date_range(start, periods=n, freq=freq)
    kw = rng.normal(base_kw, base_kw * 0.02, size=n).clip(min=1.0)
    return pd.DataFrame({"timestamp": idx, "kw": kw})


def make_csv_string(df: pd.DataFrame) -> str:
    return df.to_csv(index=False)


# ── Tests: Ingesta ────────────────────────────────────────────────────────────

class TestIngestion:
    def test_from_dataframe_loads_correctly(self):
        df = make_df(days=1)
        p = LoadProfiler.from_dataframe(df, market="mexico")
        result = p.export_profile()
        assert len(result) == len(df)

    def test_from_csv_loads_correctly(self, tmp_path):
        df = make_df(days=1)
        csv_path = tmp_path / "test_load.csv"
        csv_path.write_text(df.to_csv(index=False))
        p = LoadProfiler.from_csv(csv_path, market="mexico")
        result = p.export_profile()
        assert len(result) == len(df)

    def test_from_csv_custom_column_names(self, tmp_path):
        df = make_df(days=1).rename(columns={"timestamp": "fecha", "kw": "potencia"})
        csv_path = tmp_path / "custom_cols.csv"
        csv_path.write_text(df.to_csv(index=False))
        p = LoadProfiler.from_csv(csv_path, timestamp_col="fecha", kw_col="potencia")
        assert len(p.export_profile()) > 0

    def test_from_csv_missing_column_raises(self, tmp_path):
        df = pd.DataFrame({"fecha": ["2024-01-01"], "watts": [100.0]})
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text(df.to_csv(index=False))
        with pytest.raises(ValueError, match="timestamp"):
            LoadProfiler.from_csv(csv_path)

    def test_unsupported_market_raises(self):
        df = make_df(days=1)
        with pytest.raises(ValueError, match="no soportado"):
            LoadProfiler.from_dataframe(df, market="noexiste")

    def test_assert_loaded_raises_before_load(self):
        p = LoadProfiler(market="mexico")
        with pytest.raises(RuntimeError, match="No hay datos"):
            p.export_profile()


# ── Tests: Limpieza ───────────────────────────────────────────────────────────

class TestCleaning:
    def test_clean_fills_gaps_linear(self):
        df = make_df(days=1)
        # Inyectar NaN
        df.loc[10:14, "kw"] = float("nan")
        p = LoadProfiler.from_dataframe(df).clean(fill_method="linear")
        result = p.export_profile()
        assert result["kw"].isna().sum() == 0

    def test_clean_removes_duplicates(self):
        df = make_df(days=1)
        df_dup = pd.concat([df, df.iloc[:5]]).reset_index(drop=True)
        p = LoadProfiler.from_dataframe(df_dup).clean()
        result = p.export_profile()
        assert len(result) == len(df)

    def test_clean_treats_zeros_as_nan_and_interpolates(self):
        df = make_df(days=1, base_kw=100.0)
        df.loc[20:24, "kw"] = 0.0   # ceros falsos (corte)
        p = LoadProfiler.from_dataframe(df).clean(zero_threshold_kw=1.0)
        result = p.export_profile()
        # Los ceros deben haber sido interpolados a valores > 0
        assert (result["kw"].loc[result.index[20:25]] > 0).all()


# ── Tests: Resampleo ──────────────────────────────────────────────────────────

class TestResampling:
    def test_resample_to_15min_preserves_count(self):
        df = make_df(days=1, resolution_min=5)   # datos a 5-min
        p = LoadProfiler.from_dataframe(df).resample("15min")
        result = p.export_profile()
        # 24h × 4 periodos/h = 96 registros a 15-min por día
        assert 90 <= len(result) <= 100   # margen por bordes

    def test_resample_to_1h(self):
        df = make_df(days=1, resolution_min=15)
        p = LoadProfiler.from_dataframe(df).resample("1h")
        result = p.export_profile()
        assert len(result) == 24

    def test_resample_no_nulls_after(self):
        df = make_df(days=1, resolution_min=15)
        df.loc[10:12, "kw"] = float("nan")
        p = LoadProfiler.from_dataframe(df).clean().resample("15min")
        result = p.export_profile()
        assert result["kw"].isna().sum() == 0


# ── Tests: Etiquetado tarifario CFE GDMTH ────────────────────────────────────

class TestTariffTagging:
    """Verifica la lógica tarifaria CFE GDMTH para México."""

    def _classify(self, ts_str: str) -> str:
        p = LoadProfiler(market="mexico")
        return p._classify_period(pd.Timestamp(ts_str))

    # ── PUNTA: Lunes-Viernes 18:00-21:59
    def test_punta_weekday_evening(self):
        assert self._classify("2024-01-15 19:00:00") == "PUNTA"   # Lunes 19h

    def test_punta_starts_at_18(self):
        assert self._classify("2024-01-15 18:00:00") == "PUNTA"   # Lunes 18h

    def test_punta_ends_before_22(self):
        assert self._classify("2024-01-15 22:00:00") == "INTERMEDIA"  # Lunes 22h → no es Punta

    # ── INTERMEDIA: Lunes-Viernes 06:00-17:59 y 22:00-23:59
    def test_intermedia_morning(self):
        assert self._classify("2024-01-15 09:00:00") == "INTERMEDIA"  # Lunes 9h

    def test_intermedia_late_night_weekday(self):
        assert self._classify("2024-01-15 23:00:00") == "INTERMEDIA"  # Lunes 23h

    # ── BASE: Lunes-Viernes 00:00-05:59
    def test_base_early_morning_weekday(self):
        assert self._classify("2024-01-15 03:00:00") == "BASE"  # Lunes 3h

    def test_base_just_before_6am(self):
        assert self._classify("2024-01-15 05:59:00") == "BASE"  # Lunes 5:59h

    # ── Fines de semana: siempre BASE
    def test_saturday_punta_hours_is_base(self):
        assert self._classify("2024-01-20 20:00:00") == "BASE"  # Sábado 20h

    def test_sunday_intermedia_hours_is_base(self):
        assert self._classify("2024-01-21 10:00:00") == "BASE"  # Domingo 10h

    def test_tag_periods_populates_column(self):
        df = make_df(days=7)  # una semana completa
        p = LoadProfiler.from_dataframe(df).tag_periods()
        result = p.export_profile()
        assert "tariff_period" in result.columns
        assert set(result["tariff_period"].unique()).issubset({"BASE", "INTERMEDIA", "PUNTA"})
        # Con 7 días completos deben aparecer los 3 periodos
        assert len(result["tariff_period"].unique()) == 3


# ── Tests: Summary / Dimensionamiento ────────────────────────────────────────

class TestSummary:
    def test_summary_returns_load_summary(self):
        df = make_df(days=7)
        p = LoadProfiler.from_dataframe(df).clean().resample("15min").tag_periods()
        s = p.summary()
        assert isinstance(s, LoadSummary)

    def test_load_factor_between_0_and_1(self):
        df = make_df(days=7, base_kw=150.0)
        s = LoadProfiler.from_dataframe(df).summary()
        assert 0.0 < s.load_factor <= 1.0

    def test_energy_by_period_sums_to_total(self):
        df = make_df(days=7)
        s = LoadProfiler.from_dataframe(df).summary()
        total_from_periods = sum(s.energy_kwh_by_period.values())
        assert abs(total_from_periods - s.energy_kwh_total) < 1.0   # tolerancia 1 kWh

    def test_estimated_cost_positive_if_config_has_prices(self):
        df = make_df(days=7)
        s = LoadProfiler.from_dataframe(df, market="mexico").summary()
        assert s.estimated_monthly_cost_mxn is not None
        assert s.estimated_monthly_cost_mxn > 0

    def test_summary_str_contains_key_info(self):
        df = make_df(days=7)
        s = LoadProfiler.from_dataframe(df).summary()
        output = str(s)
        assert "Demanda máx" in output
        assert "Factor de carga" in output
        assert "PUNTA" in output

    def test_daily_profile_has_24_rows(self):
        df = make_df(days=7)
        p = LoadProfiler.from_dataframe(df)
        daily = p.daily_profile()
        assert len(daily) == 24
        assert "kw_mean" in daily.columns
        assert "kw_max" in daily.columns


# ── Tests: Pipeline completo (integración ligera) ─────────────────────────────

class TestFullPipeline:
    def test_fluent_pipeline_end_to_end(self):
        """Pipeline encadenado completo sin errores."""
        df = make_df(days=14, resolution_min=5, base_kw=200.0)
        df.loc[100:105, "kw"] = float("nan")   # hueco

        result = (
            LoadProfiler.from_dataframe(df, market="mexico")
            .clean(fill_method="linear", zero_threshold_kw=5.0)
            .resample("15min")
            .tag_periods()
            .export_profile()
        )

        assert len(result) > 0
        assert "kw" in result.columns
        assert "tariff_period" in result.columns
        assert result["kw"].isna().sum() == 0
