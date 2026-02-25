# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
scripts/fetch_cmg_evolution.py
================================
BESSAI Edge Gateway — CMg data fetcher for BESSAIEvolve (BEP-0303).

Downloads N days of real CMg (Costo Marginal) price data from the
Coordinador Eléctrico Nacional (CEN) Chile public Excel files and
saves them as data/cmg_historico.parquet for use by FitnessEvaluator.

Source: https://www.coordinador.cl/mercados/graficos/costos-marginales/
Format: Excel files with 5-minute CMg data by node.

Usage::

    # Download last 30 days
    python scripts/fetch_cmg_evolution.py

    # Download last 60 days, specific node
    python scripts/fetch_cmg_evolution.py --days 60 --node Maitencillo

    # Verify output without downloading (dry-run)
    python scripts/fetch_cmg_evolution.py --verify

Exit codes:
    0 — Success: parquet written or already up to date
    1 — Failure: could not fetch any data (will use synthetic fallback)
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Try imports — fail gracefully so the evolution loop still works with synthetic data
try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    _NP_AVAILABLE = False
    np = None  # type: ignore[assignment]

try:
    import pandas as pd
    _PD_AVAILABLE = True
except ImportError:
    _PD_AVAILABLE = False
    pd = None  # type: ignore[assignment]

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False
    requests = None  # type: ignore[assignment]

try:
    import openpyxl  # noqa: F401 — just checking availability
    _XLSX_AVAILABLE = True
except ImportError:
    _XLSX_AVAILABLE = False

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_PATH = Path("data/cmg_historico.parquet")
DEFAULT_NODE = "Maitencillo"
DEFAULT_DAYS = 30

# CEN public URL template for CMg monthly Excel files
# Pattern: https://www.coordinador.cl/wp-content/uploads/<year>/<month>/<filename>
_CMG_EXCEL_URL_TEMPLATE = (
    "https://www.coordinador.cl/wp-content/uploads/{year}/{month:02d}/"
    "Costos-Marginales-Reales-{year}-{month:02d}.xlsx"
)

# Fallback: energiaabierta.cl API v4 (hourly, no auth required)
_ENERGIA_ABIERTA_URL = (
    "https://api.energiaabierta.cl/clevels/cmg/pMarginalGestor/"
    "json?startDate={start}&endDate={end}&type=hourly"
)

# CMg column name variations in CEN Excel files
_CMG_COL_CANDIDATES = [
    "costo_marginal", "costo marginal", "cmg", "cmg_kwh",
    "costo_real", "cmg_real", "valor",
]
_DATE_COL_CANDIDATES = ["fecha", "date", "datetime", "hora", "timestamp"]


# ── Main fetch logic ──────────────────────────────────────────────────────────


def _check_dependencies() -> bool:
    if not _PD_AVAILABLE:
        print("❌ pandas not installed. Run: pip install pandas openpyxl", file=sys.stderr)
        return False
    if not _REQUESTS_AVAILABLE:
        print("❌ requests not installed. Run: pip install requests", file=sys.stderr)
        return False
    return True


def _fetch_via_energia_abierta(start: date, end: date) -> "pd.DataFrame | None":
    """Fetch from energiaabierta.cl API (hourly CMg, no auth required)."""
    if not _REQUESTS_AVAILABLE or not _PD_AVAILABLE:
        return None

    url = _ENERGIA_ABIERTA_URL.format(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
    )
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"⚠️  energiaabierta.cl returned {resp.status_code}", file=sys.stderr)
            return None
        data = resp.json()
        if not data:
            return None
        df = pd.DataFrame(data)
        # Normalise columns
        df.columns = [c.lower().strip() for c in df.columns]
        return df
    except Exception as exc:
        print(f"⚠️  energiaabierta.cl fetch failed: {exc}", file=sys.stderr)
        return None


def _fetch_cen_excel(year: int, month: int) -> "pd.DataFrame | None":
    """Attempt to download monthly CMg Excel from CEN public URL."""
    if not _REQUESTS_AVAILABLE or not _PD_AVAILABLE or not _XLSX_AVAILABLE:
        return None

    url = _CMG_EXCEL_URL_TEMPLATE.format(year=year, month=month)
    try:
        resp = requests.get(url, timeout=60, headers={"User-Agent": "open-bess-edge/2.10"})
        if resp.status_code != 200:
            return None
        df = pd.read_excel(io.BytesIO(resp.content), engine="openpyxl")
        df.columns = [str(c).lower().strip().replace(" ", "_") for c in df.columns]
        return df
    except Exception as exc:
        print(f"⚠️  CEN Excel fetch ({year}/{month:02d}) failed: {exc}", file=sys.stderr)
        return None


def _extract_cmg_series(df: "pd.DataFrame", node: str) -> "pd.Series | None":
    """Extract CMg USD/MWh series from a raw DataFrame (handles multiple formats)."""
    if df is None or df.empty:
        return None

    # Find CMg column
    cmg_col = None
    for candidate in _CMG_COL_CANDIDATES:
        matches = [c for c in df.columns if candidate in c.lower()]
        if matches:
            # Prefer column that mentions the node
            node_match = [c for c in matches if node.lower() in c.lower()]
            cmg_col = node_match[0] if node_match else matches[0]
            break

    if cmg_col is None:
        print(f"⚠️  Could not find CMg column in DataFrame. Columns: {list(df.columns)}", file=sys.stderr)
        return None

    series = pd.to_numeric(df[cmg_col], errors="coerce").dropna()
    if series.empty:
        return None

    # CEN reports in CLP/kWh — convert to USD/MWh for BESSArbitrageEnv
    # CLP/kWh → USD/MWh: CLP 950/USD × 1000 kWh/MWh ≈ divide by 0.95
    # If values look like CLP (>100 typically) convert, else assume already USD
    if series.mean() > 50:  # CLP/kWh range
        series = series / 950.0 * 1000.0  # → USD/MWh approx

    return series


def _build_synthetic_fallback(n_days: int) -> "pd.DataFrame":
    """Build a plausible synthetic CMg profile as last resort."""
    if not _PD_AVAILABLE or not _NP_AVAILABLE:
        return None  # type: ignore[return-value]

    rng = np.random.default_rng(2024)
    # Chilean hourly profile in USD/MWh (SEN approximate 2024 values)
    hourly_base = np.array([
        22, 20, 18, 18, 19, 21,   # 00-05 off-peak
        28, 42, 55, 48, 38, 28,   # 06-11 morning ramp
        16, 12, 10,  9, 10, 14,   # 12-17 solar trough
        32, 48, 62, 55, 42, 30,   # 18-23 evening peak
    ], dtype=float)

    steps_per_day = 288  # 5-min resolution
    n_steps = n_days * steps_per_day
    t = np.arange(n_steps)
    hour_idx = (t // 12) % 24  # 12 steps per hour (5-min)
    base = hourly_base[hour_idx]
    noise = rng.normal(0, 0.15, n_steps) * base
    cmg = np.clip(base + noise, 0.5, 250.0)

    return pd.DataFrame({"cmg_usd_mwh": cmg, "source": "synthetic"})


def fetch_cmg(
    n_days: int = DEFAULT_DAYS,
    node: str = DEFAULT_NODE,
    output_path: Path = OUTPUT_PATH,
) -> bool:
    """Download CMg data and save as parquet.

    Returns True on success (real data or synthetic), False on hard failure.
    """
    if not _check_dependencies():
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if existing file is fresh enough (< n_days old worth of data)
    if output_path.exists():
        age_days = (time.time() - output_path.stat().st_mtime) / 86400
        if age_days < 1.0:
            print(f"✅ {output_path} is fresh ({age_days:.1f} days old) — skipping fetch")
            return True

    today = date.today()
    start = today - timedelta(days=n_days)
    frames: list[Any] = []

    # ── Strategy 1: energiaabierta.cl API (cleanest, hourly) ─────────────────
    print(f"📡 Fetching CMg from energiaabierta.cl ({start} → {today})...")
    df_api = _fetch_via_energia_abierta(start, today)
    if df_api is not None:
        series = _extract_cmg_series(df_api, node)
        if series is not None and len(series) > 100:
            print(f"✅ energiaabierta.cl: {len(series)} records")
            frames.append(series.rename("cmg_usd_mwh").to_frame().assign(source="api"))

    # ── Strategy 2: CEN Excel files for current + previous month ─────────────
    if not frames:
        print("📡 Fetching CMg from CEN Excel files...")
        months_needed = set()
        d = start
        while d <= today:
            months_needed.add((d.year, d.month))
            d += timedelta(days=32)
            d = d.replace(day=1)

        all_series: list[Any] = []
        for year, month in sorted(months_needed):
            print(f"   Downloading {year}/{month:02d}...", end=" ", flush=True)
            df_xl = _fetch_cen_excel(year, month)
            s = _extract_cmg_series(df_xl, node)
            if s is not None:
                all_series.append(s)
                print(f"✅ {len(s)} rows")
            else:
                print("⚠️  skipped")
            time.sleep(0.5)  # be polite to CEN servers

        if all_series:
            import pandas as pd
            combined = pd.concat(all_series, ignore_index=True)
            frames.append(combined.rename("cmg_usd_mwh").to_frame().assign(source="cen_excel"))

    # ── Strategy 3: Synthetic fallback ───────────────────────────────────────
    if not frames:
        print(f"⚠️  All real-data sources failed. Generating {n_days}-day synthetic profile...")
        df_synth = _build_synthetic_fallback(n_days)
        if df_synth is not None:
            frames.append(df_synth)
            print(f"✅ Synthetic: {len(df_synth)} steps")
        else:
            print("❌ Could not generate synthetic data either", file=sys.stderr)
            return False

    import pandas as pd
    final_df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    # Ensure correct dtype and drop NaN
    final_df["cmg_usd_mwh"] = pd.to_numeric(final_df["cmg_usd_mwh"], errors="coerce")
    final_df = final_df.dropna(subset=["cmg_usd_mwh"])

    final_df.to_parquet(output_path, index=False, compression="snappy")
    source = final_df["source"].iloc[0] if "source" in final_df.columns else "unknown"
    print(f"💾 Saved {len(final_df)} CMg records → {output_path} (source: {source})")
    return True


def verify(output_path: Path = OUTPUT_PATH) -> None:
    """Print stats about the current CMg parquet file."""
    if not _PD_AVAILABLE:
        print("pandas not available", file=sys.stderr)
        return

    if not output_path.exists():
        print(f"❌ {output_path} not found")
        return

    import pandas as pd
    df = pd.read_parquet(output_path)
    print(f"✅ {output_path}")
    print(f"   Records : {len(df)}")
    print(f"   Columns : {list(df.columns)}")
    print(f"   CMg mean: {df['cmg_usd_mwh'].mean():.2f} USD/MWh")
    print(f"   CMg min : {df['cmg_usd_mwh'].min():.2f} USD/MWh")
    print(f"   CMg max : {df['cmg_usd_mwh'].max():.2f} USD/MWh")
    age_days = (time.time() - output_path.stat().st_mtime) / 86400
    print(f"   Age     : {age_days:.1f} days")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch CMg CEN Chile data for BESSAIEvolve (BEP-0303)"
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--node", type=str, default=DEFAULT_NODE)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        verify(args.output)
        sys.exit(0)

    ok = fetch_cmg(n_days=args.days, node=args.node, output_path=args.output)
    sys.exit(0 if ok else 1)
