# BESSAI Interoperability Test Suite

**Version:** 1.0.0  
**Date:** 2026-02-22  
**Status:** Active

---

## Overview

This document defines the **BESSAI Interoperability Test Suite** — a set of reproducible tests that any third-party hardware driver implementation MUST pass to claim BESSAI compatibility. The suite validates conformance with [BESSAI-SPEC-001](../specs/BESSAI-SPEC-001.md) (BESSDriver Interface Specification).

Any organization that passes this suite with their hardware driver may apply for the **BESSAI Certified** badge. See [BESSAI-CERTIFIED.md](BESSAI-CERTIFIED.md).

---

## Prerequisites

To run the interoperability test suite, you need:

- Python 3.10+
- BESSAI Edge Gateway installed: `pip install -r requirements.txt`
- Your driver implementation accessible as a Python module
- A test environment with the target hardware (or a hardware-accurate simulator)

---

## Test Categories

### Category A — Contract Tests (Automated)

These tests validate that the driver implements the `DataProvider` protocol correctly. They run against any driver without hardware by testing the interface contract.

**Test file:** `tests/interop/test_driver_contract.py`

```bash
# Run against your driver
pytest tests/interop/test_driver_contract.py \
  --driver-class="your_package.YourDriver" \
  --driver-args='{"host":"192.168.1.100","port":502}' \
  -v
```

| Test ID | Description | Requirement |
|---|---|---|
| `A-01` | Driver implements `DataProvider` protocol | SPEC-001 §4.1 |
| `A-02` | `is_connected` is False before `connect()` | SPEC-001 §4.2 |
| `A-03` | `source_description` is non-empty string | SPEC-001 §4.3 |
| `A-04` | `connect()` is idempotent (no error on double call) | SPEC-001 §4.4 |
| `A-05` | `read_tag()` raises `KeyError` for unsupported tag | SPEC-001 §4.5 |
| `A-06` | `read_tag()` raises `ConnectionError` when disconnected | SPEC-001 §4.5 |
| `A-07` | `write_tag()` raises `ValueError` for out-of-bounds value | SPEC-001 §4.6 |
| `A-08` | `disconnect()` is idempotent | SPEC-001 §4.7 |
| `A-09` | `is_connected` is False after `disconnect()` | SPEC-001 §4.2 |
| `A-10` | Device Profile JSON exists and validates against schema | SPEC-001 §7 |

### Category B — Required Tag Tests (Hardware Required)

These tests verify that all REQUIRED tags from BESSAI-SPEC-001 §5.1 return valid values.

```bash
pytest tests/interop/test_driver_contract.py::TestRequiredTags \
  --driver-class="your_package.YourDriver" \
  --driver-args='{"host":"192.168.1.100","port":502}' \
  -v
```

| Test ID | Tag | Expected Range | Requirement |
|---|---|---|---|
| `B-01` | `SOC_%` | [0.0, 100.0] | SPEC-001 §5.1 |
| `B-02` | `P_kW` | (−∞, +∞) | SPEC-001 §5.1 |
| `B-03` | `T_battery_C` | [−40.0, 100.0] | SPEC-001 §5.1 |
| `B-04` | `V_dc_V` | [0.0, +∞) | SPEC-001 §5.1 |
| `B-05` | `mode` | {0.0, 1.0, 2.0, 3.0} | SPEC-001 §5.1 |
| `B-06` | `alarm_code` | ≥ 0 | SPEC-001 §5.1 |

### Category C — Timing Tests (Hardware Required)

These tests verify that the driver meets the timing requirements of BESSAI-SPEC-001.

| Test ID | Description | Requirement |
|---|---|---|
| `C-01` | `read_tag()` completes within 5 seconds (P99 over 100 calls) | SPEC-001 §4.5 |
| `C-02` | `connect()` completes within 30 seconds | SPEC-001 §4.4 |
| `C-03` | `is_connected` does not perform I/O (returns within 1ms) | SPEC-001 §4.2 |

### Category D — SafetyGuard Integration Tests (Simulated)

These tests verify that the SafetyGuard correctly handles edge cases from your driver.

```bash
pytest tests/interop/test_safety_integration.py \
  --driver-class="your_package.YourDriver" \
  -v
```

| Test ID | Description |
|---|---|
| `D-01` | SafetyGuard blocks discharge when driver reports SOC < SOC_MIN |
| `D-02` | SafetyGuard enters Safe State when driver reports T > 60°C |
| `D-03` | SafetyGuard blocks all commands when driver reports `is_connected = False` |
| `D-04` | SafetyGuard triggers stale data protection after 30s without read |

---

## Running the Full Suite

```bash
# Full suite (requires hardware or accurate simulator)
pytest tests/interop/ -v --tb=short \
  --driver-class="your_package.YourDriver" \
  --driver-args='{"host":"192.168.1.100","port":502}' \
  --junit-xml=interop_results.xml

# Contract tests only (no hardware required)
pytest tests/interop/test_driver_contract.py::TestContractOnly -v
```

---

## Reporting Results

When applying for BESSAI Certified status, include the full `pytest` output (or the JUnit XML report) showing all test IDs and results. See [BESSAI-CERTIFIED.md](BESSAI-CERTIFIED.md) for the submission process.

---

## Adding Your Driver to CI

For drivers maintained in their own repository, you can add the BESSAI interop tests to your CI pipeline:

```yaml
# .github/workflows/bessai_interop.yml
- name: Run BESSAI Interoperability Tests
  run: |
    pip install bess-edge-gateway
    pytest tests/bessai_interop/ --driver-class="mypackage.MyDriver"
```

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-02-22 | Initial publication |
