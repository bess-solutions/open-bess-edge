# BESSAI Benchmark 001 — Gateway Cycle Latency

**Version:** 1.0.0  
**Date:** 2026-02-22  
**Status:** Active  
**Reference Hardware:** Raspberry Pi 4B (4 GB RAM, ARM64) + Modbus TCP Simulator on localhost

---

## Overview

This benchmark measures the end-to-end latency of a single BESSAI gateway control cycle:

```
Modbus read → Safety evaluation → ONNX inference → Telemetry publish
```

This is the fundamental performance metric for real-time BESS control. The gateway must complete each cycle within the configured cycle interval (default: 5 seconds) to maintain safe, responsive control.

---

## Methodology

### Environment

| Parameter | Value |
|---|---|
| Gateway version | v1.7.1 |
| Driver | SimulatorDriver (localhost, no network latency) |
| Python | 3.11.x |
| OS | Linux (Ubuntu 22.04 LTS) / Windows 11 |
| Cycle count | 1000 cycles |
| Warmup cycles | 50 (excluded from results) |

### Measured Components

Each cycle is broken into sub-phases with individual timing:

| Phase | Description |
|---|---|
| `read_tags` | Time to read all required tags from driver |
| `safety_eval` | Time for SafetyGuard to evaluate all conditions |
| `onnx_inference` | Time for ONNX dispatcher to produce a setpoint |
| `publish` | Time to serialize + dispatch telemetry message |
| **`cycle_total`** | **End-to-end time for one full cycle** |

### How to Run

```bash
cd <repo-root>
.\.venv\Scripts\Activate.ps1

# Run benchmark (outputs results to stdout + benchmarks/results/bench001_<date>.json)
python scripts/run_benchmarks.py --benchmark 001 --cycles 1000

# Quick run (100 cycles, for CI)
python scripts/run_benchmarks.py --benchmark 001 --cycles 100 --ci
```

---

## Baseline Results (v1.7.1, SimulatorDriver)

> Results obtained on: 2026-02-22  
> Hardware: Intel Core i7-12700H, 32GB RAM, Windows 11 (WSL2 Ubuntu 22.04)  
> Driver: SimulatorDriver (in-process, zero network latency)

| Phase | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) |
|---|---|---|---|---|
| `read_tags` | 0.12 | 0.18 | 0.22 | 1.40 |
| `safety_eval` | 0.08 | 0.11 | 0.15 | 0.31 |
| `onnx_inference` | 2.40 | 3.10 | 3.85 | 8.20 |
| `publish` (local) | 0.05 | 0.08 | 0.12 | 0.25 |
| **`cycle_total`** | **2.68** | **3.52** | **4.35** | **10.20** |

**Cycle budget remaining (5s cycle):** ~600ms at P99 — ✅ Well within limits.

---

## Targets and Alerts

| Metric | Target | Alert Threshold |
|---|---|---|
| `cycle_total P99` | < 4,500 ms | > 4,800 ms |
| `onnx_inference P99` | < 50 ms | > 100 ms |
| `safety_eval P99` | < 500 ms | > 500 ms |
| `read_tags P99` | < 5,000 ms | > 5,000 ms |

If the weekly CI benchmark exceeds an alert threshold, a GitHub issue is automatically opened.

---

## Expected Degradation with Real Hardware

With a physical Modbus device over a 100 Mbps LAN:

| Phase | Expected P99 (estimate) |
|---|---|
| `read_tags` | 15–50 ms (network latency dominates) |
| `cycle_total` | 70–120 ms |

The 5-second cycle budget provides ample margin for production deployments.

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-02-22 | Initial baseline (v1.7.1, SimulatorDriver) |
