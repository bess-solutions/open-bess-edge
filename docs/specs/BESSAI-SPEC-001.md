# BESSAI-SPEC-001: BESSDriver Interface Specification

**Version:** 1.0.0  
**Status:** Draft  
**Date:** 2026-02-22  
**Authors:** BESSAI Engineering Team (BESS Solutions)  
**Supersedes:** N/A  
**RFC Keywords:** The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Abstract

This specification defines the **BESSDriver Interface**, the mandatory contract that any hardware driver MUST implement to be compatible with the BESSAI Edge Gateway. Conforming implementations allow the gateway to operate with any Battery Energy Storage System (BESS) or inverter without modification to the core logic.

This specification covers: method signatures, type contracts, timing constraints, error semantics, and connection lifecycle requirements.

---

## 1. Scope

This specification applies to:
- All driver implementations in `src/drivers/`
- Any third-party driver claiming BESSAI compatibility
- Test doubles and simulators used in development and integration testing

This specification does NOT cover:
- Internal implementation of the safety guard (`src/core/safety.py`)
- Cloud telemetry interfaces (see BESSAI-SPEC-003)
- AI inference dispatching (see `src/interfaces/onnx_dispatcher.py`)

---

## 2. Normative References

- IEC 61850-7-2: Communication networks and systems for power utility automation — Abstract communication service interface (ACSI)
- IEC 62619:2022: Safety requirements for secondary lithium cells and batteries
- IEC 62443-3-3: Industrial communication networks — Security for industrial automation and control systems
- [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119): Key words for use in RFCs to Indicate Requirement Levels
- BESSAI-SPEC-002: Safety Requirements Specification (this project)

---

## 3. Terms and Definitions

| Term | Definition |
|---|---|
| **Driver** | A software component that translates hardware-specific protocols (e.g., Modbus TCP) into the BESSDriver interface |
| **Tag** | A named measurement point on a BESS device (e.g., `SOC_%`, `P_kW`, `T_battery_C`) |
| **Source Description** | A human-readable string identifying the physical device a driver is connected to |
| **Gateway** | The BESSAI Edge Gateway core orchestrator consuming this interface |
| **OT Network** | Operational Technology network where the BESS and driver communicate |

---

## 4. The DataProvider Protocol

### 4.1 Protocol Definition

A conforming driver MUST implement the `DataProvider` runtime-checkable protocol as defined in `src/drivers/base.py`. The protocol consists of the following members:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DataProvider(Protocol):
    """
    Normative interface for all BESSAI hardware drivers.
    
    All methods that may perform I/O MUST be async.
    """

    @property
    def is_connected(self) -> bool: ...

    @property
    def source_description(self) -> str: ...

    async def connect(self) -> None: ...
    async def read_tag(self, tag_name: str) -> float: ...
    async def write_tag(self, tag_name: str, value: float) -> None: ...
    async def disconnect(self) -> None: ...
```

### 4.2 `is_connected` Property

- The property MUST return `True` if and only if the driver has an active, verified connection to the hardware device.
- The property MUST return `False` immediately after `disconnect()` is called.
- The property MUST NOT block or perform I/O. It SHALL reflect the last known connection state.
- Implementations SHOULD update `is_connected` within 1 second of a connection state change.

### 4.3 `source_description` Property

- The property MUST return a non-empty string identifying the hardware device.
- The string SHOULD follow the format: `"<Manufacturer> <Model> @ <host>:<port>"`.
- Example: `"Huawei SUN2000-100KTL @ 192.168.1.100:502"`
- For simulators: `"SimulatorDriver @ localhost:5020 (sim)"`

### 4.4 `connect()` Method

- MUST establish a connection to the hardware device.
- MUST be idempotent: calling `connect()` on an already-connected driver SHALL NOT raise an exception.
- MUST raise `ConnectionError` if the connection cannot be established after exhausting retries.
- MUST set `is_connected = True` before returning successfully.
- SHOULD implement exponential backoff with a maximum of 3 retries and a base delay of 1 second.
- MUST complete within **30 seconds** (hard timeout). Implementations MAY use a shorter timeout.

### 4.5 `read_tag()` Method

#### Signature
```python
async def read_tag(self, tag_name: str) -> float
```

#### Requirements
- MUST return the current value of the named tag as a `float`.
- MUST raise `KeyError` if `tag_name` is not supported by this driver.
- MUST raise `ConnectionError` if called when `is_connected` is `False`.
- MUST raise `TimeoutError` if the hardware does not respond within **5 seconds**.
- MUST NOT return `None`. If a value is unavailable, an exception MUST be raised.
- The returned value MUST be in the physical units defined in Section 5 (Tag Registry).
- Implementations SHOULD validate that the returned value is within the physical bounds defined in Section 5.

#### Timing Constraint
- MUST complete within **5 seconds** (P99). Exceeding this is treated as a `TimeoutError`.

### 4.6 `write_tag()` Method

#### Signature
```python
async def write_tag(self, tag_name: str, value: float) -> None
```

#### Requirements
- MUST write `value` to the named tag on the hardware.
- MUST raise `KeyError` if `tag_name` is not writable by this driver.
- MUST raise `ValueError` if `value` is outside the range defined in Section 5 for that tag.
- MUST raise `ConnectionError` if called when `is_connected` is `False`.
- MUST NOT exceed **5 seconds** (P99) for completion.

> [!WARNING]
> Write tags interact with physical hardware. Implementations MUST validate bounds BEFORE sending the command to the device. Out-of-bounds commands MUST be rejected locally to prevent hardware damage.

### 4.7 `disconnect()` Method

- MUST close any open connections and release resources.
- MUST set `is_connected = False` before returning.
- MUST be idempotent: calling `disconnect()` on an already-disconnected driver SHALL NOT raise an exception.
- MUST complete within **10 seconds**.

---

## 5. Normative Tag Registry

The following tags are REQUIRED for all conforming implementations. A driver that does not support a REQUIRED tag MUST raise `KeyError` when that tag is requested, and MUST document this limitation in its device profile (see Section 7).

### 5.1 Read-Only Tags (Telemetry)

| Tag Name | Unit | Type | Range | Description |
|---|---|---|---|---|
| `SOC_%` | % | float | [0.0, 100.0] | State of Charge |
| `P_kW` | kW | float | [-∞, +∞] | Active power (+ = discharge, − = charge) |
| `T_battery_C` | °C | float | [−40.0, 100.0] | Battery cell temperature (per IEC 62619) |
| `V_dc_V` | V | float | [0.0, +∞] | DC bus voltage |
| `I_dc_A` | A | float | [−∞, +∞] | DC current (+ = discharge) |
| `mode` | enum | float | {0.0, 1.0, 2.0, 3.0} | 0=Idle, 1=Charging, 2=Discharging, 3=Fault |
| `alarm_code` | — | float | ≥ 0 | Device alarm bitmap (0 = no alarm) |

**Encoding of `mode`**: Integer semantics encoded as float for uniformity. Implementations MUST return one of the four defined values. Unknown modes SHOULD be encoded as `3.0` (Fault).

### 5.2 Write-Only Tags (Control)

| Tag Name | Unit | Type | Range | Description |
|---|---|---|---|---|
| `P_setpoint_kW` | kW | float | [−P_max, +P_max] | Power setpoint command |
| `mode_cmd` | enum | float | {0.0, 1.0, 2.0} | 0=Idle CMD, 1=Charge CMD, 2=Discharge CMD |

**P_max**: The maximum power rating of the device. Implementations MUST reject setpoints exceeding this value.

### 5.3 Optional Tags (RECOMMENDED)

Drivers SHOULD implement these for full BESSAI feature set:

| Tag Name | Unit | Description |
|---|---|---|
| `SOH_%` | % | State of Health |
| `cycles_total` | count | Total charge/discharge cycles |
| `T_inverter_C` | °C | Inverter/power electronics temperature |
| `P_ac_kW` | kW | AC side active power |
| `Q_kVAR` | kVAR | Reactive power |
| `E_kwh_remaining` | kWh | Remaining energy at current SOC |

---

## 6. Connection Lifecycle

A conforming driver MUST implement the following state machine:

```
          connect()
DISCONNECTED ──────────────► CONNECTED
     ▲                           │
     │    disconnect()           │  read_tag() / write_tag()
     └───────────────────────────┘
          ConnectionError         │
               ▲                  │ (any unrecoverable error)
               └──────────────────┘
                      FAULTED
```

- Drivers MAY implement automatic reconnection from `FAULTED` state.
- If auto-reconnect is implemented, the driver MUST log each reconnect attempt and MUST NOT attempt more than once per 5 seconds.
- After 3 consecutive failed reconnect attempts, the driver SHOULD remain in `FAULTED` state and await explicit `connect()` call.

---

## 7. Device Profile

Every conforming driver MUST have an associated **Device Profile** JSON file in `registry/<manufacturer>_<model>.json` with the following schema:

```json
{
  "schema_version": "1.0",
  "manufacturer": "string (e.g., Huawei)",
  "model": "string (e.g., SUN2000-100KTL)",
  "protocol": "string (e.g., Modbus TCP)",
  "driver_class": "string (e.g., src.drivers.modbus_driver.HuaweiSUN2000Driver)",
  "supported_tags": {
    "read": ["SOC_%", "P_kW", "T_battery_C"],
    "write": ["P_setpoint_kW"]
  },
  "unsupported_required_tags": ["T_battery_C"],
  "p_max_kw": 100.0,
  "interop_certified": false,
  "interop_test_date": null,
  "notes": "string"
}
```

`unsupported_required_tags` MUST list any REQUIRED tags from Section 5.1 that this driver cannot provide. The gateway MUST handle missing required tags via the safety fallback mechanism defined in BESSAI-SPEC-002.

---

## 8. Conformance

An implementation is conforming to this specification if:

1. It implements all methods and properties defined in Section 4.
2. It satisfies all MUST-level requirements in Section 4.
3. It includes a Device Profile JSON as defined in Section 7.
4. It passes the `tests/interop/test_driver_contract.py` validation suite.

Implementations that fail only SHOULD-level requirements are considered **conditionally conforming** and MUST document which SHOULD requirements are not met.

---

## 9. Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-02-22 | Initial publication |

---

*This specification is governed by the BESSAI Enhancement Proposal (BEP) process. See `docs/bep/BEP-0001.md` for the change process.*
