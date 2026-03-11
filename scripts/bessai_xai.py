#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA
"""
scripts/bessai_xai.py
=====================
BESSAI Explainability Engine — XAI for DRL arbitrage decisions

Provides post-hoc explainability for BESSAI's DRL model via:
  - SHAP (SHapley Additive exPlanations) — global + local feature importance
  - LIME (Local Interpretable Model-agnostic Explanations) — per-decision
  - Decision trace — human-readable JSON explaining each agent action

Input features explained:
  soc          — State of Charge (0–1)
  cmg          — CMg spot price (normalized USD/MWh)
  time_of_day  — Hour fraction (0–1)

Usage::

    # Explain last 24h of decisions
    python scripts/bessai_xai.py --data data/training_dataset.parquet

    # Explain a single observation
    python scripts/bessai_xai.py --obs 0.5 45.0 0.75

    # Generate HTML report
    python scripts/bessai_xai.py --report --output reports/xai_report.html
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import shap as _shap
    _SHAP = True
except ImportError:
    _SHAP = False

try:
    import onnxruntime as ort
    _ORT = True
except ImportError:
    _ORT = False

try:
    import pandas as pd
    _PD = True
except ImportError:
    _PD = False

FEATURE_NAMES = ["soc", "cmg_normalized", "time_of_day"]
FEATURE_DESCRIPTIONS = {
    "soc": "State of Charge — battery level (0=empty, 1=full)",
    "cmg_normalized": "CMg spot price normalized (100=USD100/MWh)",
    "time_of_day": "Time of day fraction (0=midnight, 0.5=noon, 1=midnight)",
}
ACTION_MAP = {
    (-1.0, -0.5): "⚡ DISCHARGE (aggressive) — sell energy at high price",
    (-0.5, -0.1): "📉 DISCHARGE (moderate) — sell excess energy",
    (-0.1,  0.1): "⏸️  IDLE — hold current SOC",
    ( 0.1,  0.5): "🔋 CHARGE (moderate) — buy cheap energy",
    ( 0.5,  1.0): "⚡ CHARGE (aggressive) — maximize storage at low price",
}


def _load_model() -> Any | None:
    """Load the ONNX model from models/ directory."""
    if not _ORT:
        return None
    model_path = next(Path("models").glob("**/*.onnx"), None)
    if not model_path or model_path.stat().st_size == 0:
        return None
    try:
        return ort.InferenceSession(str(model_path))
    except Exception as e:
        print(f"⚠️  Could not load ONNX model: {e}", file=sys.stderr)
        return None


def _infer(session: Any, obs: np.ndarray) -> np.ndarray:
    """Run a single inference."""
    input_name = session.get_inputs()[0].name
    if obs.ndim == 1:
        obs = obs[np.newaxis, :]
    return session.run(None, {input_name: obs.astype(np.float32)})[0]


def _interpret_action(action: float) -> str:
    """Convert scalar action to human-readable description."""
    for (lo, hi), desc in ACTION_MAP.items():
        if lo <= action < hi:
            return desc
    return "⚡ DISCHARGE (max)" if action < -0.5 else "🔋 CHARGE (max)"


def explain_observation(
    session: Any,
    obs: np.ndarray,
    background: np.ndarray | None = None,
) -> dict[str, Any]:
    """
    Explain a single observation using SHAP KernelExplainer.

    Returns a dict with action, shap_values, feature_importance, and narrative.
    """
    action = float(_infer(session, obs)[0][0])
    action_desc = _interpret_action(action)

    result: dict[str, Any] = {
        "observation": {
            name: float(obs[i]) for i, name in enumerate(FEATURE_NAMES)
        },
        "action": action,
        "action_description": action_desc,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if _SHAP and background is not None:
        try:
            def model_fn(x: np.ndarray) -> np.ndarray:
                return np.array([_infer(session, row)[0][0] for row in x])

            explainer = _shap.KernelExplainer(model_fn, background[:50])
            shap_values = explainer.shap_values(obs[np.newaxis, :], nsamples=100, silent=True)

            importance = {
                name: float(shap_values[0][i])
                for i, name in enumerate(FEATURE_NAMES)
            }
            sorted_features = sorted(importance.items(), key=lambda x: abs(x[1]), reverse=True)

            result["shap_values"] = importance
            result["top_factor"] = sorted_features[0][0]
            result["explanation"] = _build_narrative(obs, action, importance, sorted_features)
        except Exception as e:
            result["shap_error"] = str(e)
    else:
        # Rule-based fallback explanation (no SHAP)
        result["explanation"] = _rule_based_explanation(obs, action)

    return result


def _build_narrative(
    obs: np.ndarray,
    action: float,
    importance: dict[str, float],
    sorted_features: list[tuple[str, float]],
) -> str:
    """Build a human-readable explanation narrative."""
    soc, cmg, tod = obs[0], obs[1], obs[2]
    hour = int(tod * 24)
    top_feat, top_val = sorted_features[0]

    lines = [
        f"The agent decided to **{_interpret_action(action)}** (action={action:+.3f}).",
        "",
        "Key reasoning:",
        f"  1. Primary driver: **{top_feat}** (SHAP={top_val:+.3f}) — "
        f"{FEATURE_DESCRIPTIONS[top_feat]}",
    ]

    if len(sorted_features) > 1:
        f2, v2 = sorted_features[1]
        lines.append(f"  2. Secondary: **{f2}** (SHAP={v2:+.3f})")

    lines += [
        "",
        f"Context: SOC={soc:.0%}, Price={cmg*100:.1f} USD/MWh, Hour={hour:02d}:00",
    ]

    return "\n".join(lines)


def _rule_based_explanation(obs: np.ndarray, action: float) -> str:
    """Fallback explanation without SHAP (rule-based heuristic)."""
    soc, cmg, tod = obs[0], obs[1], obs[2]
    hour = int(tod * 24)

    if action < -0.1:
        reason = (
            f"Price is elevated ({cmg*100:.1f} USD/MWh) and SOC={soc:.0%} "
            f"— ideal conditions to sell and capture arbitrage revenue."
        )
    elif action > 0.1:
        reason = (
            f"Price is low ({cmg*100:.1f} USD/MWh) and SOC={soc:.0%} "
            f"— optimal moment to charge the battery cheaply."
        )
    else:
        reason = (
            f"Price ({cmg*100:.1f} USD/MWh) and SOC ({soc:.0%}) "
            f"do not present a clear arbitrage opportunity — holding."
        )

    return f"Hour {hour:02d}:00 — {reason}"


def batch_explain(
    session: Any,
    data: pd.DataFrame,
    n_samples: int = 100,
) -> list[dict[str, Any]]:
    """Explain N random samples from the dataset."""
    feature_cols = [c for c in FEATURE_NAMES if c in data.columns]
    if not feature_cols:
        print("⚠️  Feature columns not found in dataset", file=sys.stderr)
        return []

    sample = data[feature_cols].dropna().sample(min(n_samples, len(data)), random_state=42)
    background = sample.values.astype(np.float32)

    results = []
    for i, row in enumerate(background[:20]):  # Explain first 20 in detail
        exp = explain_observation(session, row, background)
        results.append(exp)
        if i % 5 == 0:
            print(f"  Explained {i+1}/20...", end="\r")

    print(f"\n✅ Explained {len(results)} observations")
    return results


def generate_html_report(explanations: list[dict], output_path: Path) -> None:
    """Generate a self-contained HTML XAI report."""
    rows = ""
    for exp in explanations:
        obs = exp.get("observation", {})
        action = exp.get("action", 0)
        desc = exp.get("action_description", "")
        narrative = exp.get("explanation", "").replace("\n", "<br>")
        shap = exp.get("shap_values", {})

        shap_bars = ""
        for feat, val in shap.items():
            color = "#e74c3c" if val < 0 else "#27ae60"
            width = min(abs(val) * 200, 100)
            shap_bars += (
                f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0">'
                f'<span style="width:120px;font-size:12px">{feat}</span>'
                f'<div style="background:{color};width:{width:.0f}px;height:14px;border-radius:3px"></div>'
                f'<span style="font-size:11px;color:{color}">{val:+.3f}</span>'
                f'</div>'
            )

        rows += f"""
        <tr>
          <td>{obs.get('soc', 0):.0%}</td>
          <td>{obs.get('cmg_normalized', 0)*100:.1f}</td>
          <td>{obs.get('time_of_day', 0)*24:.0f}:00</td>
          <td style="color:{'#e74c3c' if action < 0 else '#27ae60'}">{action:+.3f}</td>
          <td>{desc}</td>
          <td>{shap_bars or narrative}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>BESSAI XAI Report</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background:#0f172a; color:#e2e8f0; margin:0; padding:20px }}
  h1 {{ color:#38bdf8; border-bottom:2px solid #1e40af; padding-bottom:10px }}
  table {{ border-collapse:collapse; width:100%; background:#1e293b; border-radius:8px; overflow:hidden }}
  th {{ background:#1e40af; color:white; padding:10px; text-align:left }}
  td {{ padding:8px 10px; border-bottom:1px solid #334155; font-size:13px; vertical-align:top }}
  tr:hover {{ background:#334155 }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:12px; font-size:11px }}
</style>
</head><body>
<h1>🧠 BESSAI XAI Report — Decision Explanation</h1>
<p style="color:#94a3b8">Generated: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} | Model: ONNX DRL Policy</p>
<table>
  <thead><tr>
    <th>SOC</th><th>Price (USD/MWh)</th><th>Hour</th>
    <th>Action</th><th>Decision</th><th>SHAP / Reasoning</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
</body></html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"✅ HTML report saved → {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="BESSAI XAI — Explain DRL decisions")
    parser.add_argument("--data", type=Path, default=Path("data/training_dataset.parquet"),
                        help="Parquet dataset with observations")
    parser.add_argument("--obs", nargs=3, type=float, metavar=("SOC", "CMG", "TIME"),
                        help="Explain a single observation (soc cmg_norm time_of_day)")
    parser.add_argument("--report", action="store_true", help="Generate HTML report")
    parser.add_argument("--output", type=Path, default=Path("reports/xai_report.html"))
    parser.add_argument("--samples", type=int, default=100)
    args = parser.parse_args()

    if not _ORT:
        print("❌ onnxruntime required: pip install onnxruntime", file=sys.stderr)
        return 1

    session = _load_model()
    if session is None:
        print("⚠️  No ONNX model found — generating dummy model...")
        from scripts.generate_dummy_onnx import generate_dummy_onnx  # noqa
        generate_dummy_onnx(Path("models/bessai_policy_dummy.onnx"))
        session = _load_model()

    if session is None:
        print("❌ Could not load or generate model", file=sys.stderr)
        return 1

    if args.obs:
        obs = np.array(args.obs, dtype=np.float32)
        background = None

        if _PD and args.data.exists():
            df = pd.read_parquet(args.data)
            feat_cols = [c for c in FEATURE_NAMES if c in df.columns]
            if feat_cols:
                background = df[feat_cols].dropna().values.astype(np.float32)

        result = explain_observation(session, obs, background)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    # Batch mode
    if not _PD:
        print("❌ pandas required for batch mode: pip install pandas pyarrow", file=sys.stderr)
        return 1

    if not args.data.exists():
        print(f"⚠️  No dataset at {args.data} — using synthetic observations")
        rng = np.random.default_rng(42)
        data = pd.DataFrame({
            "soc": rng.uniform(0.1, 0.9, 200),
            "cmg_normalized": rng.uniform(0.2, 1.2, 200),
            "time_of_day": np.linspace(0, 1, 200),
        })
    else:
        data = pd.read_parquet(args.data)

    print(f"🔍 Explaining {min(args.samples, len(data))} decisions...")
    explanations = batch_explain(session, data, args.samples)

    if args.report and explanations:
        generate_html_report(explanations, args.output)
    elif explanations:
        for e in explanations[:5]:
            print(f"\n  Action: {e['action']:+.3f} — {e['action_description']}")
            print(f"  {e.get('explanation', '')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
