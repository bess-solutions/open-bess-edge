# SPDX-License-Identifier: Apache-2.0
# Copyright 2025-2026 BESS Solutions. All rights reserved.
"""
LoadProfiler — Módulo de ingesta y reconstrucción de perfiles de carga.

Mercado soporte inicial: México (CFE GDMTH — Gran Demanda Media Tensión Horaria).
Extensible a Chile (CEN/CMg) y otros mercados vía config JSON.

Uso rápido::

    profiler = LoadProfiler.from_csv("medidor_planta.csv", market="mexico")
    profiler.clean()
    profiler.resample("15min")
    df = profiler.export_profile()
    print(profiler.summary())
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

TARIFF_DIR = Path(__file__).parent / "tariffs"
SUPPORTED_MARKETS = {"mexico": "gdmth_mexico.json"}

# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class LoadSummary:
    """Resumen ejecutivo del perfil de carga — para reportes y dimensionamiento BESS."""

    start: datetime
    end: datetime
    records: int
    resolution_min: int
    max_demand_kw: float
    avg_demand_kw: float
    load_factor: float                          # promedio / máximo (0-1)
    peak_demand_punta_kw: float                 # demanda máxima en periodo Punta
    energy_kwh_total: float
    energy_kwh_by_period: dict[str, float]      # {"BASE": x, "INTERMEDIA": y, "PUNTA": z}
    estimated_monthly_cost_mxn: Optional[float] = None   # si hay precios en config

    def __str__(self) -> str:
        lines = [
            "═" * 60,
            "  LOAD PROFILE SUMMARY — BESSAI Analytics",
            "═" * 60,
            f"  Periodo  : {self.start:%Y-%m-%d} → {self.end:%Y-%m-%d}",
            f"  Muestras : {self.records:,} @ {self.resolution_min}-min",
            f"  Demanda máx.     : {self.max_demand_kw:>8.1f} kW",
            f"  Demanda promedio : {self.avg_demand_kw:>8.1f} kW",
            f"  Factor de carga  : {self.load_factor:>8.1%}",
            f"  Punta máx.       : {self.peak_demand_punta_kw:>8.1f} kW ← target Peak Shaving",
            f"  Energía total    : {self.energy_kwh_total:>8.1f} kWh",
            "  Energía por periodo:",
        ]
        for period, kwh in sorted(self.energy_kwh_by_period.items()):
            lines.append(f"    {period:<12}: {kwh:>8.1f} kWh")
        if self.estimated_monthly_cost_mxn is not None:
            lines.append(f"  Costo estimado   : ${self.estimated_monthly_cost_mxn:>10,.0f} MXN/mes")
        lines.append("═" * 60)
        return "\n".join(lines)


# ── Core class ────────────────────────────────────────────────────────────────


class LoadProfiler:
    """
    Ingesta, limpia y etiqueta perfiles de carga para dimensionamiento BESS.

    Soporta fuentes de datos: CSV de medidor, DataFrame de pandas.
    Etiqueta periodos tarifarios según config JSON (CFE GDMTH, extensible).
    """

    def __init__(self, market: str = "mexico", tariff_config_path: Optional[Path] = None) -> None:
        """
        Args:
            market: Mercado objetivo. "mexico" usa CFE GDMTH por defecto.
            tariff_config_path: Ruta custom al JSON de tarifas (override de market).
        """
        self._market = market.lower()
        self._config = self._load_tariff_config(tariff_config_path)
        self._df: Optional[pd.DataFrame] = None  # datos crudos / procesados
        self._resolution: Optional[str] = None

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_tariff_config(self, custom_path: Optional[Path]) -> dict:
        if custom_path is not None:
            with open(custom_path, encoding="utf-8") as f:
                return json.load(f)

        if self._market not in SUPPORTED_MARKETS:
            raise ValueError(
                f"Mercado '{self._market}' no soportado. "
                f"Opciones: {list(SUPPORTED_MARKETS.keys())}"
            )
        config_file = TARIFF_DIR / SUPPORTED_MARKETS[self._market]
        with open(config_file, encoding="utf-8") as f:
            return json.load(f)

    # ── Ingesta ───────────────────────────────────────────────────────────────

    @classmethod
    def from_csv(
        cls,
        filepath: str | Path,
        market: str = "mexico",
        timestamp_col: str = "timestamp",
        kw_col: str = "kw",
        sep: str = ",",
        datetime_format: Optional[str] = None,
    ) -> "LoadProfiler":
        """
        Carga datos desde CSV de medidor.

        Expected columns: timestamp, kw (configurable vía args).

        Example CSV::

            timestamp,kw
            2024-01-15 00:00:00,145.2
            2024-01-15 00:15:00,142.8
            ...

        Args:
            filepath: Ruta al archivo CSV.
            market: Mercado para etiquetado tarifario.
            timestamp_col: Nombre de la columna de timestamp.
            kw_col: Nombre de la columna de potencia (kW).
            sep: Separador CSV (default: coma).
            datetime_format: Formato datetime (None = autodetect).

        Returns:
            Instancia de LoadProfiler con datos cargados (sin limpiar aún).
        """
        profiler = cls(market=market)
        df = pd.read_csv(filepath, sep=sep)

        if timestamp_col not in df.columns:
            raise ValueError(f"Columna '{timestamp_col}' no encontrada. Columnas: {df.columns.tolist()}")
        if kw_col not in df.columns:
            raise ValueError(f"Columna '{kw_col}' no encontrada. Columnas: {df.columns.tolist()}")

        df[timestamp_col] = pd.to_datetime(df[timestamp_col], format=datetime_format)
        df = df.rename(columns={timestamp_col: "timestamp", kw_col: "kw"})
        df = df[["timestamp", "kw"]].copy()
        df = df.sort_values("timestamp").reset_index(drop=True)
        df = df.set_index("timestamp")

        profiler._df = df
        logger.info("CSV cargado: %d filas desde %s", len(df), filepath)
        return profiler

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        market: str = "mexico",
        timestamp_col: str = "timestamp",
        kw_col: str = "kw",
    ) -> "LoadProfiler":
        """Carga datos desde un DataFrame de pandas existente."""
        profiler = cls(market=market)
        data = df[[timestamp_col, kw_col]].copy()
        data = data.rename(columns={timestamp_col: "timestamp", kw_col: "kw"})
        data["timestamp"] = pd.to_datetime(data["timestamp"])
        data = data.sort_values("timestamp").set_index("timestamp")
        profiler._df = data
        return profiler

    # ── Limpieza ──────────────────────────────────────────────────────────────

    def clean(
        self,
        fill_method: str = "linear",
        zero_threshold_kw: float = 0.0,
        max_gap_minutes: int = 120,
    ) -> "LoadProfiler":
        """
        Limpia el perfil de carga:
        - Elimina duplicados de timestamp.
        - Rellena huecos (NaN) con interpolación.
        - Opcionalmente trata ceros como cortes de luz (NaN) si > threshold.

        Args:
            fill_method: Método de interpolación pandas ("linear", "time", "ffill").
            zero_threshold_kw: Ceros iguales o menores se tratan como NaN si > 0.
            max_gap_minutes: No interpolar huecos mayores a este valor (queda NaN).

        Returns:
            Self (encadenamiento fluido).
        """
        self._assert_loaded()
        df = self._df.copy()

        before = len(df)
        df = df[~df.index.duplicated(keep="first")]
        dupes_removed = before - len(df)
        if dupes_removed:
            logger.warning("Eliminados %d timestamps duplicados", dupes_removed)

        initial_nulls = df["kw"].isna().sum()

        if zero_threshold_kw > 0:
            false_zeros = df["kw"] <= zero_threshold_kw
            df.loc[false_zeros, "kw"] = float("nan")
            logger.info("Convertidos %d ceros (<= %.1f kW) a NaN", false_zeros.sum(), zero_threshold_kw)

        # La interpolación solo en huecos menores al límite
        if fill_method == "ffill":
            df["kw"] = df["kw"].ffill(limit=max_gap_minutes // 15)
        else:
            df["kw"] = df["kw"].interpolate(
                method=fill_method,
                limit=max_gap_minutes // 15,
                limit_area="inside",
            )

        final_nulls = df["kw"].isna().sum()
        logger.info(
            "Limpieza: %d NaN iniciales → %d restantes (huecos > %dmin no interpolados)",
            initial_nulls, final_nulls, max_gap_minutes,
        )

        self._df = df
        return self

    # ── Resampleo ─────────────────────────────────────────────────────────────

    def resample(self, resolution: str = "15min") -> "LoadProfiler":
        """
        Ajusta el perfil a la resolución temporal requerida.

        Args:
            resolution: Frecuencia pandas ("15min", "30min", "1h", "5min").
                        Para BESS y mercados eléctricos, "15min" es el estándar.

        Returns:
            Self (encadenamiento fluido).
        """
        self._assert_loaded()
        df = self._df.copy()

        original_res = pd.infer_freq(df.index)
        df = df.resample(resolution).mean()

        # Rellenar huecos creados por el resampleo
        df["kw"] = df["kw"].interpolate(method="time")

        self._df = df
        self._resolution = resolution
        logger.info("Resampleo: %s → %s. Filas: %d", original_res or "desconocida", resolution, len(df))
        return self

    # ── Etiquetado tarifario ──────────────────────────────────────────────────

    def _classify_period(self, ts: pd.Timestamp) -> str:
        """
        Clasifica un timestamp según el config tarifario activo.

        Evaluación en orden: PUNTA > INTERMEDIA > BASE (más restrictivo primero).
        """
        periods_config = self._config.get("periods", {})
        day_name = ts.day_name()   # "Monday", "Tuesday", etc.
        hour = ts.hour

        for period_name in ["PUNTA", "INTERMEDIA", "BASE"]:
            period_rules = periods_config.get(period_name, {}).get("rules", [])
            for rule in period_rules:
                if day_name in rule["days"]:
                    if rule["hours_start"] <= hour < rule["hours_end"]:
                        return period_name

        return "BASE"   # fallback seguro

    def tag_periods(self) -> "LoadProfiler":
        """
        Agrega columna `tariff_period` (BASE / INTERMEDIA / PUNTA) al DataFrame.

        Returns:
            Self (encadenamiento fluido).
        """
        self._assert_loaded()
        self._df["tariff_period"] = self._df.index.map(self._classify_period)
        logger.info("Periodos tarifarios etiquetados. Distribución:\n%s", self._df["tariff_period"].value_counts().to_string())
        return self

    # ── Output ────────────────────────────────────────────────────────────────

    def export_profile(self) -> pd.DataFrame:
        """
        Retorna el DataFrame final con columnas: [timestamp (index), kw, tariff_period].

        Si `tag_periods()` no fue llamado aún, lo ejecuta automáticamente.
        """
        self._assert_loaded()
        if "tariff_period" not in self._df.columns:
            self.tag_periods()
        return self._df.copy()

    def summary(self) -> LoadSummary:
        """
        Calcula y retorna un resumen ejecutivo del perfil para dimensionamiento BESS.

        Incluye: demanda máxima, factor de carga, energía por periodo,
        demanda máxima en Punta (=target para Peak Shaving) y costo estimado.
        """
        df = self.export_profile()
        resolution_min = self._infer_resolution_minutes()

        kwh_factor = resolution_min / 60.0  # kW × fracción_hora = kWh

        energy_by_period: dict[str, float] = {}
        for period in ["BASE", "INTERMEDIA", "PUNTA"]:
            mask = df["tariff_period"] == period
            energy_by_period[period] = float(df.loc[mask, "kw"].sum() * kwh_factor)

        punta_mask = df["tariff_period"] == "PUNTA"
        peak_punta = float(df.loc[punta_mask, "kw"].max()) if punta_mask.any() else 0.0
        max_demand = float(df["kw"].max())
        avg_demand = float(df["kw"].mean())

        # Costo estimado si hay precios en config
        prices = self._config.get("prices_mxn_kwh", {})
        demand_charge = self._config.get("demand_charge_mxn_kw_month", {})
        cost = None
        if prices:
            energy_cost = sum(energy_by_period[p] * prices.get(p, 0.0) for p in energy_by_period)
            demand_cost = peak_punta * demand_charge.get("PUNTA", 0.0)
            cost = energy_cost + demand_cost

        return LoadSummary(
            start=df.index.min().to_pydatetime(),
            end=df.index.max().to_pydatetime(),
            records=len(df),
            resolution_min=resolution_min,
            max_demand_kw=max_demand,
            avg_demand_kw=avg_demand,
            load_factor=avg_demand / max_demand if max_demand > 0 else 0.0,
            peak_demand_punta_kw=peak_punta,
            energy_kwh_total=float(df["kw"].sum() * kwh_factor),
            energy_kwh_by_period=energy_by_period,
            estimated_monthly_cost_mxn=cost,
        )

    def daily_profile(self) -> pd.DataFrame:
        """
        Retorna el perfil de día típico (promedio por hora del día).

        Útil para graficar la curva de carga 24h característica.
        """
        df = self.export_profile()
        df = df.copy()
        df["hour"] = df.index.hour
        daily = df.groupby("hour")["kw"].agg(["mean", "max", "min"]).reset_index()
        daily.columns = ["hour", "kw_mean", "kw_max", "kw_min"]
        return daily

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _assert_loaded(self) -> None:
        if self._df is None:
            raise RuntimeError("No hay datos cargados. Usa from_csv() o from_dataframe().")

    def _infer_resolution_minutes(self) -> int:
        if self._resolution:
            return int(pd.Timedelta(self._resolution).total_seconds() / 60)
        if self._df is not None and len(self._df) > 1:
            freq = pd.infer_freq(self._df.index)
            if freq:
                return max(1, int(pd.Timedelta(freq).total_seconds() / 60))
        return 15   # default
