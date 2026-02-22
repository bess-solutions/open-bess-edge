# BESSAI-SPEC-003: Telemetry Schema Specification

**Version:** 1.0.0  
**Status:** Draft  
**Date:** 2026-02-22  
**Authors:** BESSAI Engineering Team (BESS Solutions)  
**Supersedes:** N/A  
**RFC Keywords:** The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Abstract

This specification defines the **BESSAI Telemetry Message Schema** — the canonical format for all telemetry messages published from a BESSAI Edge Gateway to any downstream system (cloud messaging, MQTT, REST API, data lake). Conformance ensures that consumers can parse BESSAI telemetry from any conforming gateway implementation without custom adaptation.

---

## 1. Scope

This specification covers:
- The canonical telemetry message envelope
- The payload schemas for: device telemetry, safety events, AI scores, fleet aggregates, and carbon metrics
- Transport bindings: GCP Pub/Sub, MQTT, and REST API
- Schema versioning and backward-compatibility rules

This specification does NOT cover:
- Transport authentication or authorization
- Data retention policies
- Analytics schemas (BigQuery table definitions)

---

## 2. Normative References

- [ECMA-404](https://ecma-international.org/publications-and-standards/standards/ecma-404/): The JSON Data Interchange Standard
- [JSON Schema Draft 2020-12](https://json-schema.org/specification)
- [ISO 8601:2019](https://www.iso.org/standard/70907.html): Date and time format
- BESSAI-SPEC-001: BESSDriver Interface Specification (tag names)
- BESSAI-SPEC-002: Safety Requirements Specification (event types)

---

## 3. Message Envelope

Every BESSAI telemetry message MUST be a valid JSON object conforming to the following envelope schema.

### 3.1 Envelope Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://bessai.io/schemas/v1/envelope.json",
  "title": "BESSAI Telemetry Envelope",
  "type": "object",
  "required": ["schema_version", "message_type", "site_id", "timestamp", "payload"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+$",
      "description": "Major.Minor version of this schema. MUST be '1.0' for this spec version.",
      "const": "1.0"
    },
    "message_type": {
      "type": "string",
      "enum": ["telemetry", "safety_event", "ai_score", "fleet_aggregate", "carbon_metric"],
      "description": "Identifies the payload structure."
    },
    "site_id": {
      "type": "string",
      "pattern": "^[A-Z]{4}-[A-Z]{2}-\\d{3}$",
      "description": "Unique site identifier. Format: <TYPE>-<COUNTRY ISO 3166-1 alpha-2>-<NUMBER>. Example: SITE-CL-001"
    },
    "gateway_version": {
      "type": "string",
      "description": "BESSAI Edge Gateway semver string. Example: '1.7.1'"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC timestamp of measurement. MUST include timezone offset. Example: '2026-02-22T13:00:00Z'"
    },
    "payload": {
      "type": "object",
      "description": "Message-type-specific payload. See Section 4."
    }
  }
}
```

### 3.2 Envelope Requirements

- `schema_version` MUST be set by the publisher and MUST match the specification version of the payload being sent.
- `timestamp` MUST be in UTC. Local times with timezone offsets are acceptable but RECOMMENDED to be UTC.
- `site_id` MUST uniquely identify the physical site across all deployments of an operator.
- `gateway_version` SHOULD be included in all production messages to aid debugging.

---

## 4. Payload Schemas

### 4.1 `telemetry` Payload

Published on every measurement cycle (nominal frequency: every 5 seconds).

```json
{
  "$id": "https://bessai.io/schemas/v1/payload/telemetry.json",
  "type": "object",
  "required": ["soc_pct", "power_kw", "temperature_c", "mode", "alarm_code"],
  "properties": {
    "soc_pct": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 100.0,
      "description": "State of Charge in percent."
    },
    "power_kw": {
      "type": "number",
      "description": "Active power in kW. Positive = discharge, negative = charge."
    },
    "temperature_c": {
      "type": "number",
      "minimum": -40.0,
      "maximum": 100.0,
      "description": "Battery cell temperature in Celsius."
    },
    "voltage_v": {
      "type": ["number", "null"],
      "minimum": 0.0,
      "description": "DC bus voltage in Volts. MAY be null if not available."
    },
    "current_a": {
      "type": ["number", "null"],
      "description": "DC current in Amperes. MAY be null if not available."
    },
    "mode": {
      "type": "integer",
      "enum": [0, 1, 2, 3],
      "description": "0=Idle, 1=Charging, 2=Discharging, 3=Fault"
    },
    "alarm_code": {
      "type": "integer",
      "minimum": 0,
      "description": "Device alarm bitmap. 0 means no active alarms."
    },
    "driver_source": {
      "type": "string",
      "description": "Value of driver.source_description property. For traceability."
    },
    "cycle_number": {
      "type": ["integer", "null"],
      "minimum": 0,
      "description": "Current cycle count since gateway start."
    }
  }
}
```

#### Example `telemetry` Message

```json
{
  "schema_version": "1.0",
  "message_type": "telemetry",
  "site_id": "SITE-CL-001",
  "gateway_version": "1.7.1",
  "timestamp": "2026-02-22T13:00:00Z",
  "payload": {
    "soc_pct": 72.5,
    "power_kw": 45.3,
    "temperature_c": 28.1,
    "voltage_v": 768.0,
    "current_a": 59.0,
    "mode": 2,
    "alarm_code": 0,
    "driver_source": "Huawei SUN2000-100KTL @ 192.168.1.100:502",
    "cycle_number": 142
  }
}
```

---

### 4.2 `safety_event` Payload

Published when the SafetyGuard blocks a dispatch or enters Safe State (see BESSAI-SPEC-002 §5).

```json
{
  "$id": "https://bessai.io/schemas/v1/payload/safety_event.json",
  "type": "object",
  "required": ["event_type", "trigger_condition", "soc_pct", "temperature_c", "action_taken"],
  "properties": {
    "event_type": {
      "type": "string",
      "enum": ["DISPATCH_BLOCKED", "SAFE_STATE_ENTERED", "SAFE_STATE_CLEARED", "STALE_DATA_BLOCK"]
    },
    "trigger_condition": {
      "type": "string",
      "description": "Human-readable description of the triggering safety condition."
    },
    "soc_pct": { "type": "number" },
    "temperature_c": { "type": "number" },
    "alarm_code": { "type": "integer" },
    "action_taken": {
      "type": "string",
      "description": "What the SafetyGuard did in response. E.g., 'Blocked discharge, issued mode_cmd=0'."
    },
    "resolution_required": {
      "type": "boolean",
      "description": "True if human intervention is required to resume operation."
    }
  }
}
```

---

### 4.3 `ai_score` Payload

Published after each AI inference cycle.

```json
{
  "$id": "https://bessai.io/schemas/v1/payload/ai_score.json",
  "type": "object",
  "required": ["ids_anomaly_score", "inference_source"],
  "properties": {
    "ids_anomaly_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0,
      "description": "AI-IDS anomaly score. 0=normal, 1=maximum anomaly."
    },
    "ids_alert": {
      "type": "boolean",
      "description": "True if score exceeded the alerting threshold."
    },
    "onnx_dispatch_kw": {
      "type": ["number", "null"],
      "description": "Power setpoint recommended by the ONNX dispatch model. Null if ONNX not active."
    },
    "onnx_inference_ms": {
      "type": ["number", "null"],
      "minimum": 0.0,
      "description": "ONNX inference latency in milliseconds."
    },
    "inference_source": {
      "type": "string",
      "enum": ["onnx_local", "milp_cloud", "rule_based", "none"],
      "description": "Which inference engine produced the dispatch recommendation."
    }
  }
}
```

---

### 4.4 `fleet_aggregate` Payload

Published by the Fleet Orchestrator when managing multiple sites.

```json
{
  "$id": "https://bessai.io/schemas/v1/payload/fleet_aggregate.json",
  "type": "object",
  "required": ["n_sites_active", "total_capacity_kwh", "avg_soc_pct"],
  "properties": {
    "n_sites_active": { "type": "integer", "minimum": 0 },
    "n_sites_faulted": { "type": "integer", "minimum": 0 },
    "total_capacity_kwh": { "type": "number", "minimum": 0.0 },
    "total_flex_kw": {
      "type": "number",
      "description": "Total available flexible power for VPP dispatch."
    },
    "avg_soc_pct": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 100.0
    },
    "active_alarms_count": { "type": "integer", "minimum": 0 }
  }
}
```

---

### 4.5 `carbon_metric` Payload

Published by the LCA Engine.

```json
{
  "$id": "https://bessai.io/schemas/v1/payload/carbon_metric.json",
  "type": "object",
  "required": ["co2_avoided_kg", "grid_intensity_g_kwh", "country_code"],
  "properties": {
    "co2_avoided_kg": {
      "type": "number",
      "description": "CO₂ equivalent avoided in this measurement period, kg."
    },
    "grid_intensity_g_kwh": {
      "type": "number",
      "minimum": 0.0,
      "description": "Grid carbon intensity in gCO₂eq/kWh at time of measurement."
    },
    "country_code": {
      "type": "string",
      "pattern": "^[A-Z]{2}$",
      "description": "ISO 3166-1 alpha-2 country code."
    },
    "period_kwh": {
      "type": "number",
      "minimum": 0.0,
      "description": "Energy throughput during the measurement period in kWh."
    }
  }
}
```

---

## 5. Transport Bindings

### 5.1 GCP Pub/Sub

- Topic MUST follow the pattern: `bess-telemetry-<environment>` (e.g., `bess-telemetry-prod`)
- Messages MUST include the following **Pub/Sub attributes** (metadata, not in JSON body):

| Attribute | Value |
|---|---|
| `site_id` | Same as envelope `site_id` |
| `message_type` | Same as envelope `message_type` |
| `schema_version` | Same as envelope `schema_version` |

- Attribute-based filtering allows consumers to subscribe only to specific message types without parsing the JSON body.

### 5.2 MQTT

- Topic MUST follow the pattern: `bessai/<site_id>/<message_type>`
- Example: `bessai/SITE-CL-001/telemetry`
- QoS MUST be at least **QoS 1** (at-least-once delivery) for `safety_event` messages.
- QoS MAY be **QoS 0** (fire-and-forget) for `telemetry` messages in high-frequency deployments.
- TLS MUST be used for any MQTT connection over an untrusted network.

### 5.3 REST API (`/api/v1/status`)

The Dashboard API endpoint MUST return the most recent `telemetry` payload embedded in the envelope format. The response MAY omit fields set to `null`.

---

## 6. Schema Versioning

### 6.1 Version Semantics

Schema versioning follows **semantic versioning** (`MAJOR.MINOR`):
- **MAJOR** increment: Breaking change (field removed, type changed, enum value removed)
- **MINOR** increment: Backward-compatible change (field added, enum value added)

### 6.2 Backward Compatibility Rules

- Publishers MUST include all REQUIRED fields for the schema version they declare.
- Consumers MUST ignore unknown optional fields (forward compatibility).
- A consumer that supports version `1.x` MUST be able to process any message with `schema_version: "1.y"` where `y ≥ x`.

### 6.3 Migration Path

When a MAJOR version increment is required:
1. A BEP (BESSAI Enhancement Proposal) MUST be published and accepted.
2. Both old and new schema versions MUST be supported simultaneously for a minimum of **6 months**.
3. The deprecation timeline MUST be announced in `CHANGELOG.md` and GitHub Discussions.

---

## 7. Conformance

A publisher is conforming if:
1. All published messages validate against the JSON Schema for their `message_type`.
2. The `timestamp` field is in ISO 8601 format.
3. The `site_id` matches the defined pattern.
4. Pub/Sub attributes (if using that transport) are set correctly.

Conformance can be validated using the compliance CI workflow (`.github/workflows/compliance-report.yml`).

---

## 8. Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-02-22 | Initial publication |

---

*This specification is governed by the BESSAI Enhancement Proposal (BEP) process. See `docs/bep/BEP-0001.md` for the change process.*
