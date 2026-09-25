# Open BESS Edge v3

Substation edge gateway for Battery Energy Storage Systems (BESS): reads telemetry via Modbus TCP, evaluates a *fail-closed* safety envelope, calculates frequency response (droop/FFR) and reactive power support (Volt/VAR), and writes verified P/Q setpoints to the PCS. Spanish version: `README.md`; parameters and conventions: `docs/spec/CONTROL.md`.

> **Honest Status.** Tested against emulators and an independent Modbus server. Pending physical bench homologation with real PCS hardware (formal criterion: 72-hour continuous test protocol with a commercial inverter such as Huawei SUN2000 or SMA Tripower, satisfying FFR <500 ms and zero spurious safety envelope trips). See `PROJECT_STATUS.md`.

## Quick Start

```bash
pip install .                       # or: pip install -e ".[dev]"
open-bess-edge simulate             # simulated plant + Modbus TCP + edge node (49.65 Hz contingency)
open-bess-edge check-config config/edge_config.yaml
open-bess-edge run --config config/edge_config.yaml
open-bess-edge profile-info open_bess_edge_reference
open-bess-edge verify-audit /var/lib/open-bess-edge/audit.jsonl
```

## Physical Convention (Universal Across Codebase)
P + = discharge / grid injection, − = charge. Q + = capacitive (raises voltage). Conversion from each manufacturer's convention occurs exclusively within the profile (`sign`, `factor`).

## Control Loop
`read → safety envelope → FFR/droop → Volt/VAR → limiter → write (+verification) → heartbeat → audit`

Guarantees, each verified with automated tests (`tests/test_node.py`, `tests/test_fuzz_invariants.py`):
- Start at 0 kW and validate `startup_valid_cycles` before operating.
- Telemetry loss: retains setpoint for `comm_loss_hold_s` (2 s), then forces 0 kW, retrying until confirmed. A PCS lacking a watchdog holds the last setpoint while the link is down: use the heartbeat register.
- Missing, NaN, infinite, or physically impossible required telemetry ⇒ output 0 (never a "plausible" value).
- Latched safety trips; cleared only via explicit reset when the fault condition is cleared with hysteresis.
- Setpoints truncate toward zero; register overflow triggers an error, never wrap-around.
- Internal errors do not crash the control loop: enters `SAFE_STATE` and logs audit entry.

## Safety Guards
| Code | Effect |
|---|---|
| BESS-GUARD-001 / 002 | Cell under/overvoltage: latched trip |
| BESS-GUARD-003 | Cell overtemperature: latched trip |
| BESS-GUARD-004 | DC isolation fault: latched trip |
| BESS-GUARD-005 | Cell imbalance: warning |
| BESS-GUARD-006 / 009 | High cell / ambient temperature: 50% derating |
| BESS-GUARD-007 | Low temperature: inhibit charge |
| BESS-GUARD-008 | String voltage out of range: latched trip |
| BESS-GUARD-010 | SOC limit reached: inhibit discharge or charge |
| BESS-GUARD-020 / 021 | Grid frequency / voltage alarm (only if thresholds configured) |
| BESS-GUARD-090 | Required telemetry invalid: output 0, recovers after N valid cycles |
| BESS-GUARD-091 | Grid meter (PCC) data stale/missing: output 0, recovers after N valid cycles |

## Device Profiles (`registry/`)
A device profile permits **control** only if it declares an active power setpoint and required safety signals. Currently, vendor profiles operate in **monitor** mode at `unverified` tier (derived from register specifications without physical device validation).

| Profile | Mode | Tier |
|---|---|---|
| `open_bess_edge_reference` | control | reference (project-defined register map) |
| `huawei_sun2000` | monitor | unverified |
| `sma_sunny_tripower` | monitor | unverified |
| `fronius_gen24_byd` | monitor | unverified |
| `solaredge_storedge` | monitor | unverified |
| `victron_multiplus2` | monitor | unverified |
| `open_bess_edge_meter_reference` | monitor | reference (PCC grid meter; project map) |

## Installation Context (BTM Peak Shaving)
`installation` declares generic constraints (`max_grid_import_kw`, `max_grid_export_kw`, `soc_reserve_pct`) enforced by the edge using measurements from a grid meter at the PCC (`grid_meter`). If the meter fails, output falls to 0 (BESS-GUARD-091).
Rule set validity (`VIGENTE`/`EN_EVALUACION`/`SUPUESTO`) is audited and exposed at `/status`. If not `VIGENTE`, the node requires `accept_unverified_rule_set: true`. A local EMS can supply an expiring base schedule via authenticated HTTP (loopback only, plaintext). Example: `config/installation_btm_peak_shaving.yaml`; architectural decisions: `docs/spec/INSTALLATION.md`.

## Verification
`make check` runs linting, strict mypy type checking, test suites, claims verifier, and security audit. It covers unit, property-based, end-to-end Modbus TCP with fault injection, fuzzing, and loopback latency tests. Compatible with pymodbus ≥ 3.9.2 (3.9.2 through 3.15.0 validated; 3.8.x is excluded due to acceptance of invalid transaction IDs).

## Experimental Modules (`open_bess_edge.experimental`, Outside Control Loop)
CAN/DBC (validated with `cantools`), IEC 60870-5-104 (interoperates on STARTDT and interrogation with `c104`; without t1/t2/t3 timers), and a GOOSE-like codec over UDP loopback (not Layer 2 GOOSE). No latency guarantees are claimed.
