# BESSAI-SPEC-004: Battery Management System Data Model (IEEE 2686 Alignment)

**Version:** 0.1 (Draft)  
**Date:** 2026-02-24  
**Status:** Draft  
**Authors:** BESSAI Engineering Team  
**BEP:** TBD (BEP-0201 candidate)  
**Replaces:** None  
**License:** Creative Commons BY 4.0

---

## Abstract

This specification defines the **BESSAI Battery Status Data Model** — a normalized, vendor-agnostic representation of battery state data collected from physical Battery Management Systems (BMS). It is designed to align with **IEEE P2686** (*Recommended Practice for Battery Management Systems*) while remaining practical for field deployment on edge hardware with minimal BMS protocol access.

BESSAI-SPEC-004 is consumed by:
- `ONNXArbitrageAgent` (BEP-0200) for DRL inference
- Digital Twin PINN (BEP-0201, future)
- Energy management dashboards
- BESSAI-CERT program reporting

---

## 1. Scope

This specification covers:
- Normalized battery state fields accessible via BESSAI gateway
- Data types, units, and valid ranges
- Mapping from common BMS protocols (Modbus, CAN) to the BESSAI model
- Partial IEEE P2686 compliance table

Out of scope:
- Electrochemical modeling
- Cell-level balancing algorithms
- BMS hardware design requirements

---

## 2. Data Model

### 2.1 Core Battery State Object (`BatteryState`)

```python
@dataclass
class BatteryState:
    """BESSAI-SPEC-004 normalized battery state.
    
    All fields follow SI units unless otherwise noted.
    Timestamps are ISO 8601 UTC.
    """
    # Identity
    site_id: str                      # SITE_ID from config
    device_id: str                    # Unique device identifier
    timestamp: datetime               # Measurement timestamp (UTC)
    
    # State of Charge / Energy
    soc_pct: float                    # State of Charge [0.0, 100.0] %
    soh_pct: float | None             # State of Health [0.0, 100.0] % (if available)
    energy_available_kwh: float       # Available energy = capacity × SOC
    energy_capacity_kwh: float        # Nominal capacity (nameplate)
    
    # Power
    power_kw: float                   # Net power: positive=discharge, negative=charge
    current_a: float | None           # DC current (A), if available
    voltage_v: float | None           # DC bus voltage (V), if available
    
    # Thermal
    temp_c: float                     # Max cell temperature (°C)
    temp_min_c: float | None          # Min cell temperature (°C)
    temp_ambient_c: float | None      # Enclosure ambient temperature (°C)
    
    # Degradation & Lifetime (IEEE P2686 §5.3)
    cycle_count: int | None           # Total charge/discharge cycles
    cumulative_energy_kwh: float | None  # Lifetime throughput (kWh)
    rul_pct: float | None             # Remaining Useful Life estimate [0,1]
    
    # Alarms (IEC 62619 §6)
    alarm_overtemp: bool              # Cell overtemperature
    alarm_undervoltage: bool          # Pack undervoltage
    alarm_overcurrent: bool           # Overcurrent
    alarm_imbalance: bool             # Cell imbalance
    
    # Quality
    data_quality: str                 # "measured" | "estimated" | "simulated"
```

### 2.2 Minimum Required Fields

A BESSAI SPEC-004 compliant implementation MUST provide:

| Field | When Required | Notes |
|---|---|---|
| `site_id` | Always | Must match `SITE_ID` config |
| `timestamp` | Always | UTC, ISO 8601 |
| `soc_pct` | Always | From Modbus or BMS API |
| `power_kw` | Always | Positive=discharge |
| `temp_c` | Always | Max cell temp |
| `alarm_overtemp` | Always | IEC 62619 §6.2 |
| `energy_capacity_kwh` | At startup | From device profile |

All other fields are RECOMMENDED (`| None` if unavailable).

---

## 3. Telemetry Envelope Integration

BESSAI-SPEC-004 objects are serialized into the telemetry envelope defined by **BESSAI-SPEC-003** for GCP Pub/Sub and MQTT publishing:

```json
{
  "spec_version": "BESSAI-SPEC-003-v1 / BESSAI-SPEC-004-v0.1",
  "site_id": "CL-BESS-DEMO-001",
  "device_id": "huawei_sun2000_100ktl",
  "timestamp": "2026-02-24T14:30:00Z",
  "battery_state": {
    "soc_pct": 68.5,
    "soh_pct": 97.2,
    "energy_available_kwh": 137.0,
    "energy_capacity_kwh": 200.0,
    "power_kw": -50.0,
    "temp_c": 31.2,
    "cycle_count": 142,
    "alarm_overtemp": false,
    "alarm_undervoltage": false,
    "alarm_overcurrent": false,
    "alarm_imbalance": false,
    "data_quality": "measured"
  }
}
```

---

## 4. IEEE P2686 Alignment Map

| IEEE P2686 Clause | Description | BESSAI-SPEC-004 Field |
|---|---|---|
| §5.2.1 | State of Charge | `soc_pct` |
| §5.2.2 | State of Health | `soh_pct` |
| §5.3.1 | Cycle Count | `cycle_count` |
| §5.3.2 | Cumulative Energy | `cumulative_energy_kwh` |
| §5.4.1 | Temperature Measurement | `temp_c`, `temp_min_c` |
| §5.4.2 | Voltage Measurement | `voltage_v` |
| §5.4.3 | Current Measurement | `current_a` |
| §6.1 | Alarm — Overtemperature | `alarm_overtemp` |
| §6.2 | Alarm — Undervoltage | `alarm_undervoltage` |
| §6.3 | Alarm — Overcurrent | `alarm_overcurrent` |
| §7.1 | Remaining Useful Life | `rul_pct` |

**Compliance level:** PARTIAL (fields available via typical Modbus BMS access).  
Full IEEE P2686 compliance requires cell-level data not universally available via Modbus.

---

## 5. Protocol Mappings

### 5.1 Modbus TCP (Huawei SUN2000)

| BESSAI Field | Modbus Register | Scale | Unit |
|---|---|---|---|
| `soc_pct` | 37760 | ÷10 | % |
| `power_kw` | 37765 | ÷1000 | kW |
| `temp_c` | 37752 | ÷10 | °C |
| `voltage_v` | 37755 | ÷10 | V |
| `current_a` | 37756 | ÷10 | A |
| `alarm_overtemp` | 32090 bit 4 | boolean | — |

### 5.2 SunSpec (Generic)

| BESSAI Field | SunSpec Model | Point |
|---|---|---|
| `soc_pct` | SunSpec 802 (Battery) | `SoC` |
| `soh_pct` | SunSpec 802 | `SoH` |
| `cycle_count` | SunSpec 802 | `NCyc` |
| `temp_c` | SunSpec 802 | `TmpBatt` |

---

## 6. Changelog

| Version | Date | Changes |
|---|---|---|
| 0.1 | 2026-02-24 | Initial draft — data model + IEEE P2686 alignment |

---

## References

- IEEE P2686 — *Recommended Practice for Battery Management Systems for Stationary Applications*
- IEC 62619 — *Safety requirements for secondary lithium cells and batteries*
- [BESSAI-SPEC-001](BESSAI-SPEC-001.md) — Driver Interface
- [BESSAI-SPEC-003](BESSAI-SPEC-003.md) — Telemetry Envelope
- [BEP-0200](../bep/BEP-0200.md) — DRL Arbitrage Agent
