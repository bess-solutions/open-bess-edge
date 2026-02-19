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
    "CYCLES_TOTAL",
    "SAFETY_BLOCKS_TOTAL",
    "PUBLISH_ERRORS_TOTAL",
    "LAST_SOC_PERCENT",
    "LAST_POWER_KW",
    "LAST_CYCLE_DURATION_S",
    "CONTENT_TYPE_LATEST",
    "generate_metrics",
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
