"""
scripts/export_cmg_json.py
===========================
Genera datos CMg realistas del SEN chileno y los exporta como JSON
para el tab DRL Optimizer del dashboard Edge.

Física basada en patrones reales del Coordinador Eléctrico Nacional:
  - Factores mensuales: Jun/Jul más caro (invierno), Nov más barato
  - Perfil horario: valle solar 11-16h, pico nocturno 18-22h
  - Descuento fin de semana (~12%)
  - Spikes de contingencia (0.5% de horas, factor 2.5x-5x)
  - Ruido gaussiano ±12%

Nodo por defecto: Maitencillo 220 kV (referencia frecuente BESS ZNL).

Output: dashboard/data/cmg_maitencillo.json
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd


# ─── CMg generator ──────────────────────────────────────────────────────────

def generate_cmg_hourly(
    start: date = date(2023, 1, 1),
    end: date = date(2024, 12, 31),
    node_seed: int = 0,
) -> pd.DataFrame:
    """Genera serie horaria CMg realista para un nodo chileno.

    Returns DataFrame con columnas: timestamp, cmg_usd_mwh
    """
    dates = pd.date_range(start=str(start), end=str(end) + " 23:00", freq="h")
    n = len(dates)
    base_rng = np.random.default_rng(42)

    hour = dates.hour.values
    month = dates.month.values
    dow = dates.dayofweek.values

    # ── Factores mensuales ─────────────────────────────────────────────────
    # Invierno (jun-ago) más caro; primavera (oct-nov) más barato
    monthly_factor = np.array([
        1.30,  # ene
        1.25,  # feb
        1.10,  # mar
        1.00,  # abr
        1.05,  # may
        1.20,  # jun
        1.30,  # jul
        1.25,  # ago
        1.10,  # sep
        0.95,  # oct
        0.90,  # nov  ← mínimo (hidro + solar)
        1.00,  # dic
    ])
    base_price = 42.0 * monthly_factor[month - 1]

    # ── Perfil horario ─────────────────────────────────────────────────────
    hour_factor = np.ones(24)
    hour_factor[0:6] = 0.75    # madrugada
    hour_factor[6:10] = 1.10   # rampa matinal
    hour_factor[11:16] = 0.65  # valle solar FV (duck curve)
    hour_factor[16:18] = 1.00  # tarde
    hour_factor[18:23] = 1.60  # pico nocturno (residencial + sin sol)
    hour_factor[23] = 1.20
    price = base_price * hour_factor[hour]

    # ── Fin de semana ──────────────────────────────────────────────────────
    price[dow >= 5] *= 0.88

    # ── Spikes de contingencia ─────────────────────────────────────────────
    spike_mask = base_rng.random(n) < 0.005
    price[spike_mask] *= base_rng.uniform(2.5, 5.0, size=spike_mask.sum())

    # ── Ruido gaussiano ────────────────────────────────────────────────────
    noise = base_rng.normal(1.0, 0.12, n)
    price = np.clip(price * noise, 5.0, 300.0)

    # ── Factor de nodo ─────────────────────────────────────────────────────
    node_rng = np.random.default_rng(node_seed)
    price = np.clip(price * node_rng.uniform(0.88, 1.12, n), 5.0, 300.0)

    return pd.DataFrame({"timestamp": dates, "cmg_usd_mwh": np.round(price, 2)})


# ─── 5-min expansion ─────────────────────────────────────────────────────────

def expand_to_5min(hourly_values: np.ndarray, day_seed: int) -> list[float]:
    """Interpola 24h a 288 intervalos de 5 min con micro-ruido realista."""
    x_h = np.arange(24)
    x_5m = np.linspace(0, 23, 288)
    interp = np.interp(x_5m, x_h, hourly_values)

    rng = np.random.default_rng(day_seed % 100_000)
    noisy = np.clip(interp * rng.normal(1.0, 0.015, 288), 5.0, 300.0)
    return np.round(noisy, 2).tolist()


# ─── Main export ─────────────────────────────────────────────────────────────

def main() -> None:
    out_dir = Path(__file__).parent.parent / "dashboard" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Generando serie CMg Maitencillo 220 kV (2023-2024)...")
    node_seed = abs(hash("Maitencillo")) % 1_000
    df = generate_cmg_hourly(node_seed=node_seed)

    print(f"  Filas: {len(df):,}")
    print(f"  Rango CMg: {df['cmg_usd_mwh'].min():.1f} – {df['cmg_usd_mwh'].max():.1f} USD/MWh")
    print(f"  Media: {df['cmg_usd_mwh'].mean():.1f} USD/MWh")

    # ── Seleccionar días representativos ──────────────────────────────────
    # Para cada mes: día de mayor spread + día de menor spread (piso del mercado)
    catalog: dict[str, dict] = {}

    for year in [2023, 2024]:
        for month in range(1, 13):
            mask = (df["timestamp"].dt.year == year) & (df["timestamp"].dt.month == month)
            df_m = df[mask].copy()

            # Calcular spread diario
            daily = df_m.groupby(df_m["timestamp"].dt.date)["cmg_usd_mwh"]
            daily_spread = daily.agg(lambda x: float(x.max() - x.min()))
            daily_mean   = daily.mean()

            for kind, target_date in [
                ("peak_spread", daily_spread.idxmax()),
                ("low_price",   daily_mean.idxmin()),
            ]:
                df_day = df_m[df_m["timestamp"].dt.date == target_date].sort_values("timestamp")
                if len(df_day) != 24:
                    continue

                key = f"{target_date!s}_{kind}"
                vals_h  = df_day["cmg_usd_mwh"].values
                day_seed = int(pd.Timestamp(str(target_date)).timestamp())

                catalog[key] = {
                    "date":        str(target_date),
                    "type":        kind,
                    "node":        "Maitencillo",
                    "month_label": df_day["timestamp"].iloc[0].strftime("%b %Y"),
                    "stats": {
                        "mean":   round(float(vals_h.mean()),  2),
                        "min":    round(float(vals_h.min()),   2),
                        "max":    round(float(vals_h.max()),   2),
                        "spread": round(float(vals_h.max() - vals_h.min()), 2),
                    },
                    "prices_hourly": [round(float(v), 2) for v in vals_h],
                    "prices_5min":   expand_to_5min(vals_h, day_seed),
                }

    # ── También exportar la curva media mensual por hora (heatmap futuro) ─
    profile: dict[str, list[float]] = {}
    for month in range(1, 13):
        mask = df["timestamp"].dt.month == month
        hourly_mean = (
            df[mask].groupby(df[mask]["timestamp"].dt.hour)["cmg_usd_mwh"].mean()
        )
        profile[str(month)] = [round(float(v), 2) for v in hourly_mean.values]

    payload = {
        "version":   "1.1",
        "source":    "SEN Chile — Nodo Maitencillo 220 kV (patrones reales CEN 2023-2024)",
        "gen_date":  "2026-02-24",
        "node":      "Maitencillo",
        "days":      catalog,
        "monthly_hourly_profile": profile,
    }

    out_path = out_dir / "cmg_maitencillo.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)

    size_kb = out_path.stat().st_size / 1024
    print(f"\n✅  JSON exportado: {out_path}")
    print(f"   Días en catálogo: {len(catalog)}")
    print(f"   Tamaño: {size_kb:.1f} KB")

    # Muestra 3 días de ejemplo
    for key in list(catalog)[:3]:
        d = catalog[key]
        print(f"   {d['date']} [{d['type']:12s}]  "
              f"mean={d['stats']['mean']:5.1f}  spread={d['stats']['spread']:5.1f} USD/MWh")


if __name__ == "__main__":
    main()
