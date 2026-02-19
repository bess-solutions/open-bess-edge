"""
src/interfaces/metrics.py
==========================
BESSAI Edge Gateway — Prometheus Metrics Registry.

Exposes application metrics via the ``prometheus_client`` library.
All counters / gauges defined here are imported by the main orchestrator
and updated at each acquisition cycle.

Endpoint: GET /metrics  (served by the health server on port 8000)
"""

from __future__ import annotations

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

__all__ = [
    # v0.5.0
    "CYCLES_TOTAL",
    "SAFETY_BLOCKS_TOTAL",
    "PUBLISH_ERRORS_TOTAL",
    "LAST_SOC_PERCENT",
    "LAST_POWER_KW",
    "LAST_CYCLE_DURATION_S",
    "CONTENT_TYPE_LATEST",
    "generate_metrics",
    # v0.6.0 — AI-IDS
    "IDS_ALERTS_TOTAL",
    "IDS_ANOMALY_SCORE",
    # v0.6.0 — ONNX Dispatcher
    "ONNX_INFERENCE_MS",
    "ONNX_DISPATCH_COMMANDS_TOTAL",
]

# ---------------------------------------------------------------------------
# Counters — monotonically increasing
# ---------------------------------------------------------------------------

CYCLES_TOTAL: Counter = Counter(
    "bess_cycles_total",
    "Total number of acquisition cycles completed by the gateway.",
    ["site_id"],
)

SAFETY_BLOCKS_TOTAL: Counter = Counter(
    "bess_safety_blocks_total",
    "Number of cycles where the safety guard blocked telemetry publishing.",
    ["site_id", "reason"],
)

PUBLISH_ERRORS_TOTAL: Counter = Counter(
    "bess_publish_errors_total",
    "Number of failed GCP Pub/Sub publish operations.",
    ["site_id"],
)

CONNECT_RETRIES_TOTAL: Counter = Counter(
    "bess_modbus_connect_retries_total",
    "Total Modbus TCP connection retries.",
    ["site_id"],
)

# v0.6.0 — AI-IDS counters & gauges
IDS_ALERTS_TOTAL: Counter = Counter(
    "bess_ids_alerts_total",
    "Total number of Modbus anomaly alerts raised by the AI-IDS.",
    ["site_id", "reason"],
)

IDS_ANOMALY_SCORE: Gauge = Gauge(
    "bess_ids_anomaly_score",
    "Latest AI-IDS ensemble anomaly score (0 = normal, 1 = highly anomalous).",
    ["site_id"],
)

# v0.6.0 — ONNX Dispatcher gauges & counters
ONNX_INFERENCE_MS: Gauge = Gauge(
    "bess_onnx_inference_ms",
    "Wall-clock duration of the last ONNX model inference in milliseconds.",
    ["site_id"],
)

ONNX_DISPATCH_COMMANDS_TOTAL: Counter = Counter(
    "bess_onnx_dispatch_commands_total",
    "Total number of dispatch commands produced by the ONNX model.",
    ["site_id"],
)

# ---------------------------------------------------------------------------
# Gauges — current state at last sample
# ---------------------------------------------------------------------------

LAST_SOC_PERCENT: Gauge = Gauge(
    "bess_last_soc_percent",
    "State of Charge (%) reported in the last acquisition cycle.",
    ["site_id"],
)

LAST_POWER_KW: Gauge = Gauge(
    "bess_last_power_kw",
    "Active power (kW) reported in the last acquisition cycle.",
    ["site_id"],
)

LAST_CYCLE_DURATION_S: Gauge = Gauge(
    "bess_last_cycle_duration_seconds",
    "Wall-clock duration of the last acquisition cycle in seconds.",
    ["site_id"],
)

GATEWAY_INFO: Gauge = Gauge(
    "bess_gateway_info",
    "Static information labels about this gateway instance.",
    ["site_id", "version"],
)


def generate_metrics() -> bytes:
    """Return the current metrics snapshot as Prometheus text format."""
    return generate_latest(REGISTRY)

