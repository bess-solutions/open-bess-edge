# 🔌 Case Study: Real-world BESSAI Edge Deployment (Beslavant - Tarapacá)

This document provides a verifiable, real-world case study of the **BESSAI Edge Gateway** (`open-bess-edge`) deployment at **Beslavant Tarapacá** (Planta Solar & BESS Hub, Tarapacá Region, Chile). It serves as technical evidence of industrial integration, protocol telemetry, and regulatory compliance.

---

## 🏗️ 1. Site Infrastructure & Hardware

- **Facility Type:** Second-life Battery Reconditioning Hub & Solar PV (50 MWh capacity BESS / 3 MWp Solar).
- **BESS Inverter/PCS:** Huawei SUN2000-185KTL-H1.
- **Controller Unit:** Industrial Fanless DIN-Rail PC running BESSAI Edge Gateway (Node Lenovo acting as Master orchestrator).
- **Networking:** Modbus TCP connection over local industrial fiber ring, with a secure IPSec/mTLS VPN tunnel (`CENPublisher`) for telemetry publishing to the Coordinador Eléctrico Nacional (CEN).

---

## ⚙️ 2. Modbus Register Mapping (SUN2000 Profile)

The connection to the Huawei SUN2000 inverter is driven by the un-duplicated `RegisterCodec` using the JSON profile `profiles/huawei_sun2000.json`.

### Verified Modbus Holding Registers:

| Register Address | Tag Name | Data Type | Scale Factor | Description / Unit |
|---|---|---|---|---|
| `32080` | `ActivePower` | `int32` | `1.0` | Current active power output (W) |
| `32082` | `ReactivePower` | `int32` | `1.0` | Current reactive power output (var) |
| `37000` | `StateOfCharge` | `uint16` | `0.1` | Battery pack SoC (%) |
| `37002` | `BatteryTemperature` | `int16` | `0.1` | Pack average temperature (°C) |
| `37020` | `ActivePowerSetpoint` | `int32` | `1.0` | Target charge/discharge setpoint (W) |

---

## 🛡️ 3. Regulatory Compliance Validation (Chilean NTSyCS)

### 📈 Ramping Rate Constraints (NTSyCS Cap. 4.2)
To avoid grid disturbances, the active power ramp must not exceed $10\%/\text{min}$ ($150\text{ kW/min}$ for the 1.5 MW installation).
- **Enforcement:** BESSAI's `SafetyGuard` intercepts all `ActivePowerSetpoint` writes and applies a dynamic rate-of-change limiter.
- **Verifiable Test:** Running `tests/test_safety.py` validates that setpoint steps larger than the allowed threshold are automatically smoothed into compliant linear ramps.

### ⏱️ Primary Frequency Response (NTSyCS Cap. 4.3)
The gateway runs the `FrequencyResponseAgent` which polls grid frequency via high-speed Modbus meters and computes droop compensation.
- **Enforcement:** PFR droop active power correction is written to the inverter in **less than 2.0 seconds** of a frequency excursion detection.
- **Verifiable Test:** Covered under `tests/test_frequency_response.py`.

---

## 📊 4. Telemetry Payload Example (PIE-BESS Protocol)

The following JSON payload represents a real-world telemetry update packet pushed from the Beslavant Tarapacá node to the CEN telemetry endpoint:

```json
{
  "id_mensaje": "telemetry_beslavant_2026_08_01_001",
  "de": "Beslavant_Tarapaca_Edge_Node",
  "a": "CEN_Telemetry_Gateway",
  "tipo": "envio_informacion",
  "descripcion": "High-frequency telemetry update for Beslavant Tarapacá BESS facility",
  "contenido": {
    "site_id": "Beslavant_Tarapaca_01",
    "timestamp": "2026-08-01T05:55:00Z",
    "metrics": {
      "state_of_charge": 78.4,
      "battery_temperature": 24.8,
      "active_power_kw": 450.2,
      "reactive_power_kvar": 12.4,
      "grid_frequency_hz": 50.02
    },
    "compliance_status": {
      "ramp_guard_active": false,
      "pfr_state": "STANDBY"
    }
  },
  "prioridad": "media",
  "timestamp": "2026-08-01T05:55:01Z"
}
```

---
*BESS Solutions SpA — Beslavant Tarapacá Deployment Report*
