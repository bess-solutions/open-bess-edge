# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
scripts/bessai_data_scraper.py
==============================
BESSAI Edge Gateway — Multi-Source Data Scraper ("El Busquilla")

Scrapes and caches all external data sources relevant to BESS arbitrage
model training and BESSAIEvolve fitness evaluation:

  1. CMg spot price          — CEN Chile (energiaabierta.cl + coordinador.cl Excel)
  2. ERNC generation         — CEN Chile (solar + wind + PMGD)
  3. SEN gross demand        — CEN Chile system load
  4. Weather / irradiance    — Open-Meteo (free, no API key)
  5. Grid frequency          — CEN Chile (5-min frequency data)
  6. Battery degradation ref — NREL Degradation Tracker (public JSON)

All sources write to data/raw/<source>/<YYYY-MM-DD>.parquet
A merged dataset is persisted to data/training_dataset.parquet

Usage::

    # Scrape everything (last 30 days)
    python scripts/bessai_data_scraper.py

    # Specific sources + custom window
    python scripts/bessai_data_scraper.py --sources cmg ernc weather --days 60

    # Preview available data without downloading
    python scripts/bessai_data_scraper.py --status

Exit codes:
    0 — Success: at least one source produced data
    1 — All sources failed (evolution falls back to synthetic profile)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── Optional imports — fail gracefully ────────────────────────────────────────
try:
    import numpy as np
    _NP = True
except ImportError:
    _NP = False
    np = None  # type: ignore[assignment]

try:
    import pandas as pd
    _PD = True
except ImportError:
    _PD = False
    pd = None  # type: ignore[assignment]

try:
    import requests as _req
    _REQ = True
except ImportError:
    _REQ = False
    _req = None  # type: ignore[assignment]

# ── Configuration ─────────────────────────────────────────────────────────────

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
MERGED_PATH = DATA_DIR / "training_dataset.parquet"

# Lat/lon for Santiago, Chile (SEN grid centroid)
DEFAULT_LAT = -33.45
DEFAULT_LON = -70.66

# CEN public APIs
_API_BASE = "https://api.energiaabierta.cl"
_CMG_URL  = _API_BASE + "/clevels/cmg/pMarginalGestor/json"
_GEN_URL  = _API_BASE + "/clevels/ernc/generateResumen/json"
_DEM_URL  = _API_BASE + "/clevels/demanda/DemandaBruta/json"
_FREQ_URL = (
    "https://www.coordinador.cl/wp-content/uploads/{year}/{month:02d}/"
    "Frecuencia-{year}-{month:02d}.xlsx"
)

# Open-Meteo (free, no API key required)
_OPENMETEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&hourly=temperature_2m,direct_radiation,diffuse_radiation,windspeed_10m"
    "&start_date={start}&end_date={end}"
    "&timezone=America%2FSantiago"
)

# NREL degradation reference (static public JSON)
_NREL_DEG_URL = (
    "https://raw.githubusercontent.com/NREL/battery-degradation-data/"
    "main/public/li_ion_capacity_fade.json"
)


# ── Utility ───────────────────────────────────────────────────────────────────

def _get(url: str, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    """GET with retry (2 attempts), returns parsed JSON or None."""
    if not _REQ:
        return None
    for attempt in range(2):
        try:
            resp = _req.get(
                url,
                params=params,
                timeout=timeout,
                headers={"User-Agent": "open-bess-edge/2.10 (BESSAIEvolve data scraper)"},
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"  HTTP {resp.status_code} — {url[:80]}", file=sys.stderr)
        except Exception as exc:
            if attempt == 0:
                print(f"  ⏳ Retry after error: {exc}", file=sys.stderr)
                time.sleep(2)
            else:
                print(f"  ❌ Failed: {exc}", file=sys.stderr)
    return None


def _save(df: "pd.DataFrame", name: str, label: str) -> Path | None:
    """Save DataFrame to data/raw/<name>/today.parquet."""
    if not _PD or df is None or df.empty:
        return None
    out_dir = RAW_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{date.today().isoformat()}.parquet"
    df.to_parquet(out, index=False, compression="snappy")
    print(f"  💾 {label}: {len(df)} records → {out}")
    return out


def _date_range(n_days: int) -> tuple[str, str]:
    today = date.today()
    start = today - timedelta(days=n_days)
    return start.isoformat(), today.isoformat()


# ── Source 1: CMg — Spot Price ─────────────────────────────────────────────────

def scrape_cmg(n_days: int = 30) -> "pd.DataFrame | None":
    """CMg (Costo Marginal de Gestión) — hourly spot price in USD/MWh."""
    print("📡 [CMg] Fetching spot price...")
    if not _PD or not _REQ:
        return None

    start, end = _date_range(n_days)
    data = _get(_CMG_URL, params={"startDate": start, "endDate": end, "type": "hourly"})

    if not data:
        return None

    df = pd.DataFrame(data)
    if df.empty:
        return None
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

    # Detect price column
    price_col = next((c for c in df.columns if "marginal" in c or "cmg" in c or "precio" in c), None)
    if price_col is None:
        print("  ⚠️  No price column found. Columns:", list(df.columns), file=sys.stderr)
        return None

    df = df.rename(columns={price_col: "cmg_usd_mwh"})
    df["cmg_usd_mwh"] = pd.to_numeric(df["cmg_usd_mwh"], errors="coerce")

    # Convert CLP/kWh → USD/MWh if values look like CLP
    if df["cmg_usd_mwh"].median() > 50:
        df["cmg_usd_mwh"] = df["cmg_usd_mwh"] / 950.0 * 1000.0

    df["source"] = "api_energiaabierta_cmg"
    df = df.dropna(subset=["cmg_usd_mwh"])
    _save(df[["cmg_usd_mwh", "source"]], "cmg", "CMg spot price")

    # Also write main parquet for FitnessEvaluator compatibility
    out = DATA_DIR / "cmg_historico.parquet"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False, compression="snappy")
    print(f"  💾 Also saved → {out} (FitnessEvaluator compat)")
    return df


# ── Source 2: ERNC — Renewable Generation ─────────────────────────────────────

def scrape_ernc(n_days: int = 30) -> "pd.DataFrame | None":
    """ERNC generation: solar PV + wind + mini-hydro (in MWh)."""
    print("🌞 [ERNC] Fetching renewable generation...")
    if not _PD or not _REQ:
        return None

    start, end = _date_range(n_days)
    data = _get(_GEN_URL, params={"startDate": start, "endDate": end})

    if not data:
        return None

    df = pd.DataFrame(data)
    if df.empty:
        return None
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

    # Keep numeric columns; rename if standard names are present
    for col in ("solar", "eolica", "mini_hidro", "total_ernc"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["source"] = "api_energiaabierta_ernc"
    _save(df, "ernc", "ERNC generation")
    return df


# ── Source 3: Gross Demand ─────────────────────────────────────────────────────

def scrape_demand(n_days: int = 30) -> "pd.DataFrame | None":
    """SEN system gross demand (MWh)."""
    print("⚡ [Demand] Fetching SEN gross demand...")
    if not _PD or not _REQ:
        return None

    start, end = _date_range(n_days)
    data = _get(_DEM_URL, params={"startDate": start, "endDate": end})

    if not data:
        return None

    df = pd.DataFrame(data)
    if df.empty:
        return None
    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]

    demand_col = next((c for c in df.columns if "demanda" in c or "demand" in c or "mwh" in c), None)
    if demand_col:
        df["demand_mwh"] = pd.to_numeric(df[demand_col], errors="coerce")

    df["source"] = "api_energiaabierta_demand"
    _save(df, "demand", "SEN gross demand")
    return df


# ── Source 4: Weather + Solar Irradiance ──────────────────────────────────────

def scrape_weather(
    n_days: int = 30,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
) -> "pd.DataFrame | None":
    """Hourly weather data: temperature, direct+diffuse radiation, wind speed."""
    print(f"🌤️  [Weather] Fetching Open-Meteo ({lat:.2f}°, {lon:.2f}°)...")
    if not _PD or not _REQ:
        return None

    start, end = _date_range(n_days)
    url = _OPENMETEO_URL.format(lat=lat, lon=lon, start=start, end=end)

    try:
        resp = _req.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}", file=sys.stderr)
            return None
        payload = resp.json()
    except Exception as exc:
        print(f"  ❌ Open-Meteo: {exc}", file=sys.stderr)
        return None

    hourly = payload.get("hourly", {})
    if not hourly:
        return None

    df = pd.DataFrame(hourly)
    # Open-Meteo column names
    rename_map = {
        "time": "timestamp",
        "temperature_2m": "temp_c",
        "direct_radiation": "solar_direct_wm2",
        "diffuse_radiation": "solar_diffuse_wm2",
        "windspeed_10m": "windspeed_ms",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    for col in ("temp_c", "solar_direct_wm2", "solar_diffuse_wm2", "windspeed_ms"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Total global horizontal irradiance
    if "solar_direct_wm2" in df.columns and "solar_diffuse_wm2" in df.columns:
        df["solar_ghi_wm2"] = df["solar_direct_wm2"] + df["solar_diffuse_wm2"]

    df["source"] = "open_meteo"
    _save(df, "weather", "Open-Meteo weather")
    return df


# ── Source 5: Grid Frequency from CEN Excel ───────────────────────────────────

def scrape_frequency(n_days: int = 30) -> "pd.DataFrame | None":
    """SEN grid frequency (Hz) — 5-minute resolution from CEN public Excel."""
    print("📊 [Frequency] Fetching grid frequency from CEN Excel...")
    if not _PD or not _REQ:
        return None

    try:
        import openpyxl  # noqa: F401
        _XLSX = True
    except ImportError:
        print("  ⚠️  openpyxl not installed — skipping frequency data", file=sys.stderr)
        return None

    today = date.today()
    months = {(today.year, today.month)}
    if today.day < n_days:
        prev = today.replace(day=1) - timedelta(days=1)
        months.add((prev.year, prev.month))

    frames = []
    for year, month in sorted(months):
        url = _FREQ_URL.format(year=year, month=month)
        try:
            resp = _req.get(url, timeout=60)
            if resp.status_code != 200:
                continue
            df_xl = pd.read_excel(io.BytesIO(resp.content), engine="openpyxl")
            df_xl.columns = [str(c).lower().strip().replace(" ", "_") for c in df_xl.columns]
            freq_col = next((c for c in df_xl.columns if "frecuencia" in c or "freq" in c or "hz" in c), None)
            if freq_col:
                df_xl["freq_hz"] = pd.to_numeric(df_xl[freq_col], errors="coerce")
                frames.append(df_xl[["freq_hz"]])
                print(f"  ✅ {year}/{month:02d}: {len(df_xl)} rows")
            time.sleep(0.5)
        except Exception as exc:
            print(f"  ⚠️  {year}/{month:02d}: {exc}", file=sys.stderr)

    if not frames:
        return None

    df = pd.concat(frames, ignore_index=True)
    df["source"] = "cen_excel_frequency"
    _save(df, "frequency", "SEN grid frequency")
    return df


# ── Source 6: Battery Degradation Reference ───────────────────────────────────

def scrape_degradation_ref() -> "pd.DataFrame | None":
    """NREL Li-ion battery capacity fade reference data (used for cost calibration)."""
    print("🔬 [Degradation] Fetching NREL degradation reference...")
    if not _PD or not _REQ:
        return None

    data = _get(_NREL_DEG_URL, timeout=15)
    if not data:
        return None

    try:
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Flatten nested structure
            rows = []
            for chem, entries in data.items():
                if isinstance(entries, list):
                    for e in entries:
                        e["chemistry"] = chem
                        rows.append(e)
            df = pd.DataFrame(rows)
        else:
            return None

        df["source"] = "nrel_degradation_ref"
        _save(df, "degradation", "NREL degradation reference")
        return df
    except Exception as exc:
        print(f"  ⚠️  NREL parse error: {exc}", file=sys.stderr)
        return None


# ── Merge: Build Training Dataset ─────────────────────────────────────────────

def build_training_dataset(frames: dict[str, "pd.DataFrame"]) -> "pd.DataFrame | None":
    """Merge all time-series sources into a single wide training dataset."""
    if not _PD:
        return None

    ts_sources = {k: v for k, v in frames.items() if k in ("cmg", "ernc", "demand", "weather", "frequency")}
    if not ts_sources:
        print("⚠️  No time-series data available for merge", file=sys.stderr)
        return None

    # Use CMg as the primary index if available, otherwise first available
    primary = ts_sources.get("cmg") or next(iter(ts_sources.values()))

    # Simple concat — in production you'd align on a proper timestamp column
    merged = pd.concat(list(ts_sources.values()), axis=0, ignore_index=True)
    merged = merged.loc[:, ~merged.columns.duplicated()]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(MERGED_PATH, index=False, compression="snappy")
    print(f"\n✅ Training dataset: {len(merged)} rows × {len(merged.columns)} features → {MERGED_PATH}")
    return merged


# ── Status ────────────────────────────────────────────────────────────────────

def show_status() -> None:
    """Print status of all locally cached data sources."""
    print("📂 BESSAI Data Scraper — Cached Data Status")
    print(f"   Data directory: {DATA_DIR.resolve()}\n")

    sources = ["cmg", "ernc", "demand", "weather", "frequency", "degradation"]
    for src in sources:
        src_dir = RAW_DIR / src
        if not src_dir.exists():
            print(f"  ❌ {src:<15} — no data")
            continue
        files = sorted(src_dir.glob("*.parquet"))
        if not files:
            print(f"  ❌ {src:<15} — empty directory")
            continue
        latest = files[-1]
        age_h = (time.time() - latest.stat().st_mtime) / 3600
        size_kb = latest.stat().st_size / 1024
        print(f"  ✅ {src:<15} — {latest.name}  ({size_kb:.1f} KB, {age_h:.1f}h ago)")

    print()
    if MERGED_PATH.exists():
        if _PD:
            df = pd.read_parquet(MERGED_PATH)
            print(f"  📊 Training dataset: {len(df)} rows × {len(df.columns)} features → {MERGED_PATH}")
        else:
            size_kb = MERGED_PATH.stat().st_size / 1024
            print(f"  📊 Training dataset: {size_kb:.1f} KB → {MERGED_PATH}")
    else:
        print("  ❌ Training dataset: not built yet. Run: python scripts/bessai_data_scraper.py")


# ── CLI ───────────────────────────────────────────────────────────────────────

ALL_SOURCES = ("cmg", "ernc", "demand", "weather", "frequency", "degradation")

SCRAPERS = {
    "cmg":         lambda days: scrape_cmg(days),
    "ernc":        lambda days: scrape_ernc(days),
    "demand":      lambda days: scrape_demand(days),
    "weather":     lambda days: scrape_weather(days),
    "frequency":   lambda days: scrape_frequency(days),
    "degradation": lambda _:    scrape_degradation_ref(),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BESSAI multi-source data scraper — feeds BESSAIEvolve and DRL training"
    )
    parser.add_argument(
        "--sources", nargs="+",
        choices=list(ALL_SOURCES) + ["all"],
        default=["all"],
        help="Data sources to fetch (default: all)",
    )
    parser.add_argument("--days", type=int, default=30, help="Historical window in days")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Latitude (for weather)")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON, help="Longitude (for weather)")
    parser.add_argument("--status", action="store_true", help="Show status of cached data and exit")
    parser.add_argument("--no-merge", action="store_true", help="Skip building merged dataset")
    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    if not _PD:
        print("❌ pandas required: pip install pandas requests openpyxl pyarrow", file=sys.stderr)
        return 1

    sources = ALL_SOURCES if "all" in args.sources else tuple(args.sources)
    print(f"🚀 BESSAI Data Scraper — fetching {len(sources)} sources ({args.days} days)")
    print(f"   Sources: {', '.join(sources)}\n")

    results: dict[str, "pd.DataFrame"] = {}
    start_ts = time.time()

    for src in sources:
        if src not in SCRAPERS:
            continue
        try:
            df = SCRAPERS[src](args.days)
            if df is not None and not df.empty:
                results[src] = df
                print()
        except Exception as exc:
            print(f"  ❌ {src}: {exc}\n", file=sys.stderr)

    elapsed = time.time() - start_ts

    if not results:
        print("\n❌ All sources failed. BESSAIEvolve will use synthetic data.", file=sys.stderr)
        return 1

    print(f"✅ Fetched {len(results)}/{len(sources)} sources in {elapsed:.1f}s")

    if not args.no_merge:
        build_training_dataset(results)

    # Write a manifest JSON for auditing
    manifest = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "days": args.days,
        "sources_requested": list(sources),
        "sources_ok": list(results.keys()),
        "sources_failed": [s for s in sources if s not in results],
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "scraper_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n📋 Manifest → {DATA_DIR / 'scraper_manifest.json'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
