# BESSAI-SPEC-002: Safety Requirements Specification

**Version:** 1.0.0  
**Status:** Draft  
**Date:** 2026-02-22  
**Authors:** BESSAI Engineering Team (BESS Solutions)  
**Supersedes:** N/A  
**RFC Keywords:** The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Abstract

This specification defines the **Safety Requirements** for the BESSAI Edge Gateway, covering electrical safety thresholds, the Safety Guard enforcement logic, the autonomous Black Start protocol, and cybersecurity requirements at the OT layer. Conformance to this specification is mandatory for any deployment claiming BESSAI compatibility.

This specification is aligned with:
- **IEC 62619:2022** — Safety requirements for secondary lithium cells and batteries for use in electrical energy storage systems
- **IEC 62443-3-3:2013** — System security requirements and security levels (Security Level 2)
- **NTSyCS** — Chilean Technical Standard for Storage Systems (CNSEE)

---

## 1. Scope

This specification applies to:
- The `SafetyGuard` component (`src/core/safety.py`)
- All gateway deployments connected to physical BESS hardware
- Third-party implementations claiming BESSAI-compatible safety behavior
- Integration testing environments validating safety behavior

This specification does NOT cover:
- Physical installation safety (governed by local electrical codes)
- Fire suppression systems (governed by NFPA 855 or equivalent)
- Network security at the IT layer (see BESSAI cybersecurity documentation)

---

## 2. Normative References

- IEC 62619:2022: Safety requirements for secondary lithium cells and batteries
- IEC 62443-3-3:2013: Industrial communication networking — Security for IACS (SL-2)
- IEC 60950-1: Safety for information technology equipment
- BESSAI-SPEC-001: BESSDriver Interface Specification
- BESSAI-SPEC-003: Telemetry Schema Specification

---

## 3. Terms and Definitions

| Term | Definition |
|---|---|
| **Safety Block** | An event where the SafetyGuard prevents or halts a dispatch command due to unsafe conditions |
| **SOC** | State of Charge (%) — ratio of current charge to usable capacity |
| **SOH** | State of Health (%) — ratio of current capacity to original rated capacity |
| **LFP** | Lithium Iron Phosphate — battery chemistry type (most common in utility BESS) |
| **NMC** | Nickel Manganese Cobalt — battery chemistry type |
| **Black Start** | Autonomous restart procedure after total grid and communication failure |
| **Safe State** | A hardware state where no dispatch commands are issued; the battery is idle |

---

## 4. Electrical Safety Thresholds

### 4.1 SOC Limits

The SafetyGuard MUST enforce the following SOC limits. All values are expressed as percentage of usable capacity.

| Limit | LFP Default | NMC Default | Overridable | Rule |
|---|---|---|---|---|
| **SOC_MIN** | 10.0% | 15.0% | YES (config) | MUST NOT discharge below this |
| **SOC_MAX** | 95.0% | 90.0% | YES (config) | MUST NOT charge above this |
| **SOC_CRITICAL_LOW** | 5.0% | 8.0% | NO | MUST enter Safe State immediately |
| **SOC_CRITICAL_HIGH** | 98.0% | 95.0% | NO | MUST enter Safe State immediately |

- Overridable limits MAY be configured via `config/.env` but MUST NOT exceed the fixed critical bounds.
- The SafetyGuard MUST NOT honor any dispatch command that would drive SOC beyond an active limit.

#### Per IEC 62619 Clause 6.2
> The battery system SHALL prevent operation outside the safe operating area defined by the cell manufacturer.

The SOC_MIN and SOC_MAX values MUST be validated against the cell manufacturer's specification at commissioning time.

### 4.2 Temperature Limits

| Limit | Value | Action on Breach | Per Standard |
|---|---|---|---|
| **T_WARN_HIGH** | 45°C | Log warning, reduce P_setpoint by 50% | IEC 62619 Clause 7.1 |
| **T_MAX_HIGH** | 60°C | MUST enter Safe State, raise `CRITICAL` alarm | IEC 62619 Clause 6.1 |
| **T_MIN_LOW** | −10°C | Log warning, disable charging | IEC 62619 Clause 7.2 |
| **T_CRITICAL_LOW** | −20°C | MUST enter Safe State | IEC 62619 Clause 6.1 |

> [!CAUTION]
> At T ≥ 60°C, the risk of thermal runaway in LFP and NMC chemistries increases exponentially. This limit is NON-NEGOTIABLE and MUST NOT be overridden via configuration.

### 4.3 Current and Power Limits

- The SafetyGuard MUST reject any `P_setpoint_kW` command exceeding the device's `p_max_kw` value (from Device Profile, BESSAI-SPEC-001 Section 7).
- When SOC is below `SOC_MIN + 5%`, the maximum discharge power MUST be limited to 50% of `p_max_kw`.
- When temperature is above `T_WARN_HIGH`, the maximum power in either direction MUST be limited to 50% of `p_max_kw`.

---

## 5. SafetyGuard Behavior

### 5.1 Evaluation Cycle

The SafetyGuard MUST evaluate all safety conditions on every telemetry read cycle. The evaluation MUST be synchronous and MUST complete before any dispatch command is issued.

```
TELEMETRY READ → SAFETY EVALUATION → (PASS | BLOCK) → DISPATCH
```

The evaluation cycle MUST complete within **500ms** (P99).

### 5.2 Blocking Logic

A dispatch command MUST be blocked if any of the following conditions are true:

1. `SOC_%` < `SOC_MIN` and commanded direction is discharge
2. `SOC_%` > `SOC_MAX` and commanded direction is charge
3. `SOC_%` < `SOC_CRITICAL_LOW` (regardless of direction)
4. `SOC_%` > `SOC_CRITICAL_HIGH` (regardless of direction)
5. `T_battery_C` > `T_MAX_HIGH`
6. `T_battery_C` < `T_CRITICAL_LOW`
7. `alarm_code` from driver is non-zero AND alarm is classified as SAFETY-CRITICAL (see Section 5.4)
8. The driver reports `is_connected = False`
9. The last successful tag read was more than **30 seconds** ago (stale data protection)

On any block condition:
- The SafetyGuard MUST increment the `bess_safety_blocks_total` Prometheus counter.
- The SafetyGuard MUST log the event at `ERROR` level with the triggering condition.
- The SafetyGuard MUST NOT silently swallow the block — the orchestrator MUST be notified.

### 5.3 Safe State

Upon entering Safe State:
- The SafetyGuard MUST issue a `write_tag("mode_cmd", 0.0)` command (Idle) to the driver.
- The SafetyGuard MUST set an active alarm in the Alert Manager with severity `CRITICAL`.
- The gateway MUST NOT resume dispatch until the triggering condition is resolved AND a human operator (or autonomous reinstatement logic with documented override) clears the alarm.

### 5.4 Alarm Classification

Alarm codes from drivers are classified as:

| Class | Examples | SafetyGuard Action |
|---|---|---|
| **SAFETY-CRITICAL** | Overcurrent, thermal runaway, BMS fault | Block dispatch immediately, enter Safe State |
| **WARNING** | Temperature warning, communication degradation | Log + reduce power as specified in §4.2 |
| **INFO** | Calibration due, fan speed alert | Log only |

Implementations MUST maintain an alarm classification table in the Device Profile or a shared `registry/alarm_codes.json`.

---

## 6. Data Staleness Protection

- The SafetyGuard MUST track the timestamp of the last successful `read_tag()` call.
- If the last successful read was more than **30 seconds** ago (configurable via `SAFETY_STALE_TIMEOUT_S`, minimum 10s), the SafetyGuard MUST enter Safe State.
- Upon driver reconnect and successful read, normal operation MAY resume automatically (no human intervention required for staleness recovery).

---

## 7. Autonomous Black Start Protocol

The Black Start protocol is activated when the gateway detects total grid and communication failure.

### 7.1 Activation Conditions

The Black Start protocol MUST activate when ALL of the following are true:
- Grid frequency or voltage out of bounds for > 60 seconds (or grid status signal lost)
- Cloud connectivity lost (Pub/Sub / MQTT unreachable) for > 120 seconds
- No VPP dispatch signal received for > 180 seconds

### 7.2 Black Start Sequence

| Phase | Elapsed time | Action | Reversible |
|---|---|---|---|
| **T+0s** | 0 | Detect triggering conditions | — |
| **T+30s** | 30s | Verify SOC > 20%. If NO: enter Safe State and halt. | — |
| **T+60s** | 60s | Load priority table from local config. Activate critical loads only. | YES |
| **T+2min** | 2 min | ONNX local model assumes dispatch control (offline mode). | YES |
| **T+10min** | 10 min | Full autonomous operation: ONNX + safety rules, no cloud dependency. | YES |
| **Reconnect** | Variable | Sync state with cloud. Resume normal operation after 3 consecutive successful heartbeats. | — |

### 7.3 Local Configuration Requirement

A valid Black Start configuration MUST be stored locally (not dependent on cloud connectivity) and MUST include:
- Critical load list with priorities
- SOC reservation threshold (default: 20%)
- ONNX model path for offline inference

---

## 8. Cybersecurity Requirements (OT Layer)

These requirements derive from IEC 62443-3-3 Security Level 2 (SL-2).

### 8.1 Network Segmentation (SR 1.1 / SR 1.13)
- The OT network (BESS ↔ Gateway) MUST be physically or logically segmented from the IT network.
- Direct internet access from the OT network MUST NOT be permitted.
- All cloud communication MUST flow through the gateway acting as a controlled boundary.

### 8.2 Least Privilege (SR 1.2)
- The gateway process MUST run with the minimum operating system privileges required.
- The gateway MUST use separate credentials for OT communication (Modbus) and IT communication (cloud publishers).

### 8.3 Input Validation (SR 3.5)
- All values received from hardware via `read_tag()` MUST be validated against the ranges in Section 4 before use.
- Controls received from external systems (VPP, dashboard) MUST be validated against Section 4 limits before being passed to the driver.

### 8.4 Availability (SR 7.1 / SR 7.2)
- The gateway MUST implement automatic recovery from driver disconnection.
- The Black Start protocol (Section 7) provides availability continuity during cloud outages.

### 8.5 Audit Logging (SR 6.1 / SR 6.2)
- Every Safety Block event MUST be logged with: timestamp, triggering condition, tag values, and resolved state.
- Every write to a control tag MUST be logged with: timestamp, tag name, value, and requesting component.
- Logs MUST be shipped to the observability stack (OpenTelemetry) and MUST be retained for a minimum of 90 days.

---

## 9. Conformance

An implementation is conforming to this specification if:

1. All electrical thresholds in Section 4 are enforced.
2. The SafetyGuard blocking logic in Section 5 is implemented completely.
3. Safe State behavior in Section 5.3 is implemented.
4. The Black Start protocol in Section 7 is implemented.
5. Audit logging requirements in Section 8.5 are met.
6. The implementation passes the chaos test suite: `pytest tests/ -m chaos`.

---

## 10. Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-02-22 | Initial publication |

---

*This specification is governed by the BESSAI Enhancement Proposal (BEP) process. See `docs/bep/BEP-0001.md` for the change process.*
