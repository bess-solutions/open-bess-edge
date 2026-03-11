#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2025-2026 BESS Solutions. All rights reserved.
"""
Demo: Perfil de carga de una fábrica industrial en México.

Contexto comercial:
  - Cliente: Integrador / Asset Manager mexicano.
  - Tarifa: CFE GDMTH (Gran Demanda Media Tensión Horaria).
  - Objetivo: Dimensionamiento BESS para Peak Shaving en Punta (18:00-22:00 L-V).

Ejecutar::

    python examples/mexico_profile_demo.py

No requiere datos reales — genera un perfil sintético realista de planta industrial.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Asegurar que el src esté en el path cuando se corre directamente
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics import LoadProfiler

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ── 1. Generar datos sintéticos de fábrica ───────────────────────────────────

def generate_factory_load(days: int = 30, resolution_min: int = 15) -> pd.DataFrame:
    """
    Genera datos sintéticos de una planta industrial mexicana.

    Curva de carga típica:
    - Lunes-Viernes: Alta carga de 07:00-20:00 (turno de producción).
    - Sábado: 50% de carga (limpieza y mantenimiento).
    - Domingo: 10% de carga (servicios mínimos).
    - Pico de producción 09:00-11:00 y 14:00-17:00.
    - Aire acondicionado agrega ~30 kW en 12:00-18:00.
    """
    rng = np.random.default_rng(seed=42)  # reproducible

    freq = f"{resolution_min}min"
    idx = pd.date_range("2024-01-15", periods=days * 24 * (60 // resolution_min), freq=freq)

    baseline_kw = 60.0          # consumo base (iluminación, oficinas, servicios)
    production_kw = 180.0       # línea de producción principal
    hvac_kw = 35.0              # aire acondicionado
    weekend_factor = {5: 0.5, 6: 0.1}  # Sat=50%, Sun=10%

    loads = []
    for ts in idx:
        day = ts.dayofweek  # 0=Mon ... 6=Sun
        hour = ts.hour

        if day in weekend_factor:
            kw = baseline_kw * weekend_factor[day]
        else:
            # Arranque de planta 07:00
            if hour < 7:
                kw = baseline_kw * 0.3
            elif hour == 7:
                kw = baseline_kw + production_kw * 0.5   # arranque gradual
            elif 8 <= hour <= 11:
                kw = baseline_kw + production_kw          # pico mañana
            elif hour == 12:
                kw = baseline_kw + production_kw * 0.6   # almuerzo
            elif 13 <= hour <= 17:
                kw = baseline_kw + production_kw          # pico tarde
            elif 18 <= hour <= 20:
                kw = baseline_kw + production_kw * 0.7   # bajada gradual ← PUNTA CFE aquí
            elif hour == 21:
                kw = baseline_kw + production_kw * 0.3   # limpieza
            else:
                kw = baseline_kw * 0.4

            # HVAC (solo horario diurno)
            if 11 <= hour <= 18:
                kw += hvac_kw

        # Ruido gaussiano ±5%
        noise = rng.normal(0, kw * 0.05)
        loads.append(max(0.0, kw + noise))

    df = pd.DataFrame({"timestamp": idx, "kw": loads})
    return df


# ── 2. Simular datos con huecos (escenario real) ──────────────────────────────

def inject_gaps(df: pd.DataFrame, gap_positions: list[int], gap_size: int = 4) -> pd.DataFrame:
    """Simula cortes de datos del medidor."""
    df = df.copy()
    for pos in gap_positions:
        if pos + gap_size < len(df):
            df.loc[pos : pos + gap_size, "kw"] = float("nan")  # noqa: E203
    return df


# ── 3. Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 60)
    print("  BESSAI Analytics — Demo Perfil de Carga México (GDMTH)")
    print("=" * 60 + "\n")

    # Generar datos sintéticos
    logger.info("Generando perfil sintético de fábrica industrial (30 días, 15-min)...")
    factory_df = generate_factory_load(days=30, resolution_min=15)

    # Inyectar 3 huecos de datos para simular un medidor con fallos reales
    factory_df = inject_gaps(factory_df, gap_positions=[500, 1200, 2800])
    logger.info("Datos generados: %d muestras con 3 huecos inyectados", len(factory_df))

    # ── Pipeline LoadProfiler ──────────────────────────────────────────────
    profiler = (
        LoadProfiler.from_dataframe(factory_df, market="mexico")
        .clean(fill_method="linear", zero_threshold_kw=5.0)
        .resample("15min")
        .tag_periods()
    )

    # ── Output ──────────────────────────────────────────────────────────────
    df_export = profiler.export_profile()

    print("\nPrimeras 5 filas del perfil exportado:")
    print(df_export.head().to_string())

    summary = profiler.summary()
    print(f"\n{summary}")

    # Perfil de día típico
    daily = profiler.daily_profile()
    print("\nPerfil día típico (primeras 24 horas):")
    print(daily.to_string(index=False))

    # Recomendación BESS
    peak_kw = summary.peak_demand_punta_kw
    avg_kw = summary.avg_demand_kw
    target_shaving_kw = peak_kw - avg_kw

    print("\n" + "=" * 60)
    print("  RECOMENDACIÓN BESS — Peak Shaving Estimado")
    print("=" * 60)
    print(f"  Demanda punta máxima   : {peak_kw:.1f} kW")
    print(f"  Demanda promedio       : {avg_kw:.1f} kW")
    print(f"  Target Peak Shaving    : {target_shaving_kw:.1f} kW (potencia mínima BESS)")
    print("  Duración ventana Punta : 4 h (18:00-22:00)")
    print(f"  Capacidad BESS mínima  : {target_shaving_kw * 4:.0f} kWh @ C1  "
          f"({target_shaving_kw * 2:.0f} kWh @ C2 recomendado)")
    print("=" * 60)
    print("\n✅ Análisis completado. Exportar df_export a CSV para entrega:")
    print("   df_export.to_csv('perfil_planta_cliente.csv')")
    print()


if __name__ == "__main__":
    main()
