# Contributing Hardware Device Profiles to Open BESS Edge

> **Audience**: Systems integrators, inverter/BMS manufacturers, and open-source contributors  
> **Skill Level**: Intermediate  
> **Estimated Effort**: 1–2 hours per profile  

---

## Why Contribute a Device Profile?

The **Open BESS Edge Device Registry** ([`registry/`](../../registry/)) maintains vendor register definitions used by the gateway. Each JSON profile specifies:
- The industrial protocol configuration (Modbus TCP, SunSpec, CAN)
- Register maps and data types required for telemetry acquisition and setpoint dispatch
- Signal bindings to the normalized internal model (`soc_pct`, `active_power_kw`, `temp_c`, etc.)
- Physical safety envelope and capability constraints

Expanding profile coverage directly increases out-of-the-box hardware interoperability.

---

## Step 1: Check Existing Registry Profiles

```bash
# Check existing profiles in registry
ls registry/
```

Verify whether your hardware model or family is already covered.

---

## Step 2: Gather Manufacturer Technical Documentation

Obtain the official protocol specification from the manufacturer:

| Protocol | Required Documentation |
|---|---|
| **Modbus TCP / RTU** | Complete register address table with data types, scaling factors, endianness, and unit identifiers. |
| **SunSpec** | Implemented SunSpec Model IDs (e.g., Model 701 DER Measurement, Model 702 DER Storage). |
| **CAN Bus** | DBC file or frame/signal matrix defining arbitration IDs and scaling. |

---

## Step 3: Profile Structure & Conventions

Create `registry/<manufacturer>_<model>.json` using standard JSON syntax:

```json
{
  "name": "vendor_model",
  "manufacturer": "VendorName",
  "model": "ModelIdentifier",
  "version": "1.0.0",
  "protocol": "modbus_tcp",
  "endianness": "big",
  "registers": {
    "telemetry": [
      {
        "name": "battery_soc",
        "address": 30001,
        "type": "uint16",
        "scale": 0.1,
        "unit": "%",
        "binding": "soc_pct"
      },
      {
        "name": "active_power",
        "address": 30002,
        "type": "int16",
        "scale": 1.0,
        "unit": "kW",
        "sign": 1.0,
        "binding": "active_power_kw"
      }
    ],
    "controls": [
      {
        "name": "active_power_setpoint",
        "address": 40001,
        "type": "int16",
        "scale": 1.0,
        "unit": "kW",
        "sign": 1.0,
        "binding": "active_power_setpoint_kw"
      }
    ]
  }
}
```

### Universal Physical Convention

Strictly adhere to the global sign convention:
* **Active Power (P):** `+` = discharge / injection; `−` = charge / import.
* **Reactive Power (Q):** `+` = capacitive (boosts voltage); `−` = inductive (lowers voltage).

If the manufacturer uses inverted signs (e.g., positive for charging), set `"sign": -1.0` in the register mapping.

---

## Step 4: Validate Profile Locally

Verify profile loading and schema compliance using the CLI:

```bash
# Inspect profile via CLI
open-bess-edge profile-info <your_profile_name>

# Execute tests to verify registry integrity
pytest tests/test_profile.py -q
```

---

## Step 5: Submit a Pull Request

1. Fork the repository on GitHub.
2. Create a feature branch: `git checkout -b registry/add-<vendor-model>`
3. Add your JSON profile to `registry/`.
4. Ensure all tests pass: `make check`.
5. Open a Pull Request referencing the manufacturer manual and test observations.

### Profile Validation Tiers

| Tier | Criteria | Operational State |
|---|---|---|
| `unverified` | Derived from technical manuals without physical hardware bench testing | Monitor-only |
| `reference` | Maintained canonical project profiles with automated test suites | Full Control & Monitor |
| `bench_verified` | Validated on physical bench with commercial PCS over 72h continuous test | Control Authorized |
