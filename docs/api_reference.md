# API Reference — BESSAI Edge Gateway

> **Base URL (local):** `http://localhost:8000`  
> **Authentication:** `X-API-Key: <DASHBOARD_API_KEY>` (required in production mode)

---

## Health & Status

### `GET /health`

Returns gateway liveness and basic operational state.

**Authentication:** None required

```bash
curl http://localhost:8000/health
```

**Response 200 OK:**
```json
{
  "status": "healthy",
  "site_id": "SITE-CL-001",
  "uptime_s": 127.4,
  "last_cycle_ts": "2026-02-21T17:45:00+00:00",
  "safety_status": "ok"
}
```

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `status` | `string` | `"healthy"` \| `"degraded"` \| `"error"` |
| `site_id` | `string` | SITE_ID from config |
| `uptime_s` | `float` | Seconds since gateway start |
| `last_cycle_ts` | `string` | ISO-8601 timestamp of last Modbus cycle |
| `safety_status` | `string` | `"ok"` \| `"safety_block_active"` |

---

### `GET /metrics`

Returns Prometheus-format metrics for scraping.

**Authentication:** None required (Prometheus scrape endpoint)

```bash
curl http://localhost:8000/metrics
```

**Key metrics:**

| Metric | Type | Description |
|---|---|---|
| `bess_cycles_total` | Counter | Total Modbus polling cycles |
| `bess_safety_blocks_total` | Counter | Times SafetyGuard blocked a command |
| `bess_last_soc_pct` | Gauge | Current SOC in % |
| `bess_last_power_kw` | Gauge | Current active power in kW |
| `bess_cycle_duration_seconds` | Histogram | Polling cycle latency |
| `bess_ids_anomaly_score` | Gauge | AI-IDS anomaly score (0.0–1.0) |
| `bess_ids_alerts_total` | Counter | AI-IDS alerts triggered |
| `bess_onnx_inference_ms` | Histogram | ONNX model inference latency |
| `bess_publish_errors_total` | Counter | GCP Pub/Sub publish failures |
| `bess_fleet_sites_active` | Gauge | Active sites in fleet |

---

## Operational API

### `GET /api/v1/status`

Returns full real-time operational snapshot.

**Authentication:** `X-API-Key` header required

```bash
curl http://localhost:8000/api/v1/status \
  -H "X-API-Key: your-key-here"
```

**Response 200 OK:**
```json
{
  "site_id": "SITE-CL-001",
  "timestamp": "2026-02-21T17:45:00+00:00",
  "modbus": {
    "connected": true,
    "inverter_ip": "192.168.1.100",
    "last_read_ms": 45.2
  },
  "bess": {
    "soc_pct": 72.4,
    "power_kw": 150.0,
    "voltage_v": 820.5,
    "temperature_c": 28.3,
    "status_code": 0
  },
  "safety": {
    "status": "ok",
    "blocks_total": 0,
    "active_constraints": []
  },
  "ai_ids": {
    "anomaly_score": 0.12,
    "alert_active": false,
    "model_version": "isolation_forest_v1"
  },
  "cloud": {
    "pubsub_connected": true,
    "publish_errors_total": 0,
    "last_publish_ts": "2026-02-21T17:44:58+00:00"
  }
}
```

---

### `POST /api/v1/dispatch`

Sends a dispatch command to the inverter (write via Modbus FC06).

**Authentication:** `X-API-Key` header required  

!!! warning "Safety-Critical Endpoint"
    All dispatch commands pass through `SafetyGuard.check_safety()` before execution.
    Commands that violate SOC or temperature limits are rejected with HTTP 422.

```bash
curl -X POST http://localhost:8000/api/v1/dispatch \
  -H "X-API-Key: your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"target_kw": 100.0, "source": "arbitrage_engine"}'
```

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `target_kw` | `float` | ✅ | Target active power in kW. Positive = charge, negative = discharge |
| `source` | `string` | No | Command source identifier for audit logging |

**Response 200 OK:**
```json
{
  "status": "executed",
  "target_kw": 100.0,
  "safety_check": "passed",
  "modbus_register": 40101,
  "latency_ms": 47.3
}
```

**Response 422 Unprocessable Entity (Safety Block):**
```json
{
  "status": "rejected",
  "reason": "SOC below minimum threshold (5.0%). Current: 4.8%",
  "safety_constraint": "soc_min"
}
```

---

## Error Codes

| HTTP Status | Meaning |
|---|---|
| `200` | Success |
| `401` | Missing or invalid `X-API-Key` |
| `422` | Command rejected by SafetyGuard |
| `503` | Gateway degraded — Modbus disconnected |
| `500` | Internal error (check logs) |

---

## SDK / Client Libraries

```python
# Python client (future: bessai-edge-client package)
from bessai_edge import Client

client = Client("http://localhost:8000", api_key="your-key")
status = client.status()
client.dispatch(target_kw=100.0, source="my-app")
```
