# ADR-0003: Use IsolationForest + Z-Score Ensemble for AI-IDS

## Status
✅ Accepted — 2026-02-19

## Context

The BESSAI Edge Gateway requires anomaly detection on Modbus telemetry to identify:
- **Sensor faults** — stuck values, physically impossible readings
- **Modbus injection attacks** — unexpected register writes
- **Replay attacks** — repeated identical telemetry patterns

Requirements for the anomaly detector:
- Must operate **offline** (no cloud connectivity during inference)
- Must run on **edge hardware** (Raspberry Pi / industrial PC — constrained resources)
- Must produce a **calibrated score 0–1** (not just binary normal/anomaly)
- Must be **trainable on historical data** from the site without labeled anomalies
- Must **fail safe**: if it fails, normal operation continues unaffected

Alternatives considered:
- **Autoencoder (neural network)**: high accuracy but requires GPU and labeled data; too heavy for edge
- **One-Class SVM**: good theoretical guarantees but slow inference on large feature sets, hard to tune
- **Simple threshold rules**: fast but brittle, misses multivariate anomalies (e.g., SOC high AND power low)
- **LSTM time series model**: excellent for sequences but requires significant training data and ONNX export

## Decision

Use a **two-stage ensemble** combining:

1. **`sklearn.ensemble.IsolationForest`** — unsupervised anomaly detection via random partitioning. Scores outliers without labeled data. Fast inference (microseconds per sample).

2. **Z-score normalization** — per-feature statistical outlier detection. Catches individual feature extremes that IsolationForest might smooth over in high-dimensional spaces.

**Ensemble formula:**
```python
anomaly_score = 0.6 * isolation_forest_score + 0.4 * zscore_score
```

The weights (60/40) were chosen to give IsolationForest primary authority (it captures multivariate anomalies) while z-score catches single-variable extremes.

**Fail-safe behavior:**
- Before `fit()` is called (cold start): always returns `0.0` (no alarm)
- If inference raises any exception: returns `0.0` (fail-safe-open)
- Alert threshold: `0.65` — tunable via environment variable

## Consequences

### Positive
- **No labeled anomaly data required**: IsolationForest is fully unsupervised
- **Fast**: < 1ms inference per sample on a single CPU core
- **Lightweight**: scikit-learn is already a project dependency (ONNX model training)
- **Interpretable**: z-score component is human-readable for debugging
- **Fail-safe**: never blocks normal operation due to AI failure

### Negative
- **Training required**: cold-start period needed before meaningful scoring (typically 500+ samples)
- **No temporal context**: the model treats each sample independently; sequential attacks could be missed
- **Fixed weights**: the 60/40 ensemble weights are not adaptive — could be improved with meta-learning

### Neutral
- The model is retrained in memory on each gateway restart (no model persistence yet)
- Future improvement: persist the fitted IsolationForest model to disk as a pickle or ONNX (planned v2.0)
