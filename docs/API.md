# BESSAI Edge Gateway — External Interface (API)

> **OpenSSF criterion `documentation_interface`:** This document describes all external inputs and outputs of the BESSAI Edge Gateway software produced by the `open-bess-edge` project.

---

## Overview

BESSAI Edge Gateway exposes several interfaces for integration with industrial BESS hardware, cloud backends, and monitoring systems. All interfaces are designed to be FLOSS-compatible and configurable via environment variables.

---

## 1. Modbus TCP — Input (Hardware Telemetry)

**Direction:** Gateway ← Inverter/BESS  
**Protocol:** Modbus TCP (IEC 61158)  
**Port:** configurable (`INVERTER_PORT`, default `502`)

### Input Registers Read

| Tag | Register | Type | Unit | Description |
|---|---|---|---|---|
| `soc` | 37760 | UINT16 | % | State of Charge (0–100) |
| `soh` | 37799 | UINT16 | % | State of Health |
| `voltage_dc` | 37752 | UINT32 | 0.1 V | DC bus voltage |
| `current_charge` | 37766 | INT32 | 0.1 A | Charging current |
| `current_discharge` | 37768 | INT32 | 0.1 A | Discharging current |
| `power_kw` | 37001 | INT32 | 1 W | Active power |
| `temperature` | 37022 | INT16 | 0.1 °C | Battery cell temperature |
| `alarm_code` | 32090 | UINT32 | — | Active alarm bitmap |

### Output Registers Written (Control)

| Tag | Register | Type | Description |
|---|---|---|---|
| `charge_setpoint` | 47075 | UINT16 | Target charging power (W) |
| `discharge_setpoint` | 47076 | UINT16 | Target discharging power (W) |
| `storage_control_mode` | 47086 | UINT16 | 0=auto, 5=manual |

---

## 2. HTTP REST API — Dashboard & Monitoring

**Direction:** External client → Gateway  
**Base URL:** `http://<GATEWAY_IP>:8000`  
**Authentication:** TOTP-based token (header `X-BESSAI-Token`)

### Endpoints

#### `GET /health`
Returns gateway operational status.

**Response:**
```json
{
  "status": "ok",
  "version": "2.10.0",
  "uptime_s": 12345,
  "site_id": "BESS-001"
}
```

#### `GET /metrics`
Prometheus-format metrics for scraping.

**Response:** `text/plain; version=0.0.4` (OpenMetrics format)

```
bessai_soc_percent{site="BESS-001"} 78.5
bessai_power_kw{site="BESS-001",direction="charge"} 42.1
bessai_alarm_active{site="BESS-001",code="0"} 0
```

#### `GET /api/v1/status`
Full telemetry snapshot (rate-limited: 60 req/min).

**Response:**
```json
{
  "timestamp": "2026-02-25T14:00:00-03:00",
  "soc": 78.5,
  "soh": 96.2,
  "power_kw": 42.1,
  "voltage_dc": 748.4,
  "temperature_c": 28.3,
  "mode": "discharge",
  "alarm": null
}
```

#### `GET /api/v1/history?minutes=60`
Historical telemetry for the last N minutes (max 1440).

#### `POST /api/v1/control`
Send a dispatch setpoint (requires authentication).

**Request:**
```json
{
  "mode": "charge",
  "power_kw": 50.0,
  "duration_min": 30
}
```

**Response:**
```json
{"accepted": true, "setpoint_id": "sp-20260225-001"}
```

---

## 3. MQTT — Telemetry Publishing

**Direction:** Gateway → MQTT Broker  
**Protocol:** MQTT 3.1.1 / 5.0  
**Broker:** configurable (`MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`)

### Topics Published

| Topic | Frequency | Payload |
|---|---|---|
| `bessai/<site_id>/telemetry` | 5 s | JSON telemetry snapshot |
| `bessai/<site_id>/alarm` | On change | JSON alarm object |
| `bessai/<site_id>/status` | 60 s | JSON health summary |

---

## 4. GCP Pub/Sub — Cloud Telemetry

**Direction:** Gateway → Google Cloud Pub/Sub  
**Topic:** `bessai-telemetry` (configurable via `GCP_PUBSUB_TOPIC`)

**Message format:**
```json
{
  "site_id": "BESS-001",
  "ts": "2026-02-25T14:00:00Z",
  "soc": 78.5,
  "power_kw": 42.1,
  "alarm_code": 0
}
```

---

## 5. IEEE 2030.5 / SEP 2.0 — DER Control

**Direction:** Utility/VPP → Gateway (server-push)  
**Protocol:** HTTPS + TLS mTLS (client certificate required)  
**Standard:** SEPA/IEEE 2030.5-2018

The gateway acts as a SEP 2.0 **DER** end device and accepts:
- `DERControl` events (charge/discharge schedules)
- `PricingProgram` signals (for arbitrage)
- `MessagingProgram` notifications

See [`docs/SEP2.md`](SEP2.md) for full endpoint and resource documentation.

---

## 6. OpenTelemetry — Traces & Spans

**Direction:** Gateway → OTLP Collector  
**Endpoint:** configurable (`OTEL_EXPORTER_OTLP_ENDPOINT`)

Key spans exported:
- `modbus.read_tag` — per-register read latency
- `pubsub.publish` — GCP publish latency
- `ai.inference` — ONNX model inference time
- `safety.check` — SafetyGuard validation time

---

## Environment Variables (Configuration Inputs)

| Variable | Required | Default | Description |
|---|---|---|---|
| `SITE_ID` | ✅ | — | Unique site identifier |
| `INVERTER_IP` | ✅ | — | Modbus TCP host |
| `INVERTER_PORT` | ❌ | `502` | Modbus TCP port |
| `GCP_PROJECT_ID` | ✅ | — | Google Cloud project ID |
| `GCP_PUBSUB_TOPIC` | ❌ | `bessai-telemetry` | Pub/Sub topic |
| `MQTT_BROKER_HOST` | ❌ | — | MQTT broker hostname |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | ❌ | — | OpenTelemetry collector |
| `SAFETY_SOC_MIN` | ❌ | `10` | Minimum SOC limit (%) |
| `SAFETY_SOC_MAX` | ❌ | `95` | Maximum SOC limit (%) |
| `BESSAI_DRL_ENABLED` | ❌ | `false` | Enable DRL dispatch control |

Full configuration reference: [`config/.env.example`](../config/.env.example)
