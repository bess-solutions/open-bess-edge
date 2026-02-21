# NTSyCS Compliance Mapping — BESSAI Edge Gateway

> **Norma Técnica de Seguridad y Calidad de Servicio (NTSyCS)**  
> Coordinador Eléctrico Nacional (CEN) — Chile  
> **Version:** 2024 revision · **Mapping date:** 2026-02-21  
> **Project version:** `open-bess-edge` v1.3.2

---

## Executive Summary

BESSAI Edge Gateway is designed to interface with Battery Energy Storage Systems (BESS) in compliance with the NTSyCS regulation issued by the Coordinador Eléctrico Nacional (CEN) of Chile. This document maps each relevant NTSyCS requirement to the specific implementation in this software.

> **Disclaimer:** This document represents the development team's interpretation of NTSyCS requirements as applicable to edge gateway software. Formal certification requires review by the CEN and/or an accredited third-party auditor.

---

## Scope of Applicability

| NTSyCS Scope | Applicability to BESSAI | Notes |
|---|---|---|
| Generation units ≥ 1 MW | ✅ Applicable | BESS systems connected to SIC |
| Reactive power control | ⚠️ Partial | Monitoring only; control via inverter firmware |
| Frequency response (FR) | ✅ Applicable | Via Arbitrage Engine dispatch scheduling |
| Voltage regulation | ⚠️ Partial | Monitoring; set point via LUNA2000 FC06 writes |
| Telemetry to CEN | 🔄 In progress | GCP Pub/Sub → CEN data pipeline (planned) |
| Cybersecurity requirements | ✅ Applicable | See IEC 62443 mapping |

---

## Chapter 4 — BESS Technical Requirements

### 4.1 State of Charge (SOC) Management

| Requirement | Clause | Implementation | Status |
|---|---|---|---|
| SOC shall be maintained between 5% and 95% of nominal capacity | §4.1.2 | `src/core/safety.py`: `SafetyGuard.check_safety()` blocks charge/discharge when SOC < 5% or > 98% | ✅ |
| SOC measurement accuracy ≤ ±2% | §4.1.4 | Depends on inverter firmware (SUN2000/LUNA2000); validated via Modbus register `soc` (UINT16, 0.1% resolution) | ⚠️ Inverter-dependent |
| SOC shall be reported every 5 minutes to the operator | §4.1.6 | Telemetry cycle configurable via `WATCHDOG_TIMEOUT` env var; default 5s; Prometheus scrape at 10s intervals | ✅ |

### 4.2 Power Control

| Requirement | Clause | Implementation | Status |
|---|---|---|---|
| Active power set point via digital command | §4.2.1 | `src/drivers/modbus_driver.py`: `write_tag()` via FC06 (single register write) | ✅ |
| Response time ≤ 200ms from command receipt | §4.2.3 | Async Modbus write via `pymodbus 3.12`; nominal < 50ms on LAN | ✅ |
| Power ramp rate limit | §4.2.5 | Not yet implemented in software layer; must be configured in inverter firmware | ❌ Planned v2.0 |

### 4.3 Frequency Response

| Requirement | Clause | Implementation | Status |
|---|---|---|---|
| Primary frequency response (PFR) capability | §4.3.1 | `src/interfaces/arbitrage_engine.py`: dispatch scheduling based on CMg signals; frequency droop planned | ⚠️ Partial |
| Dead band ±0.15 Hz | §4.3.4 | Not yet implemented; planned for VPP integration | ❌ Planned v2.0 |

---

## Chapter 6 — Telemetry and Communication

### 6.1 Real-Time Data Reporting

| Requirement | Clause | Implementation | Status |
|---|---|---|---|
| Report: active power, reactive power, voltage, SOC, alarms | §6.1.1 | All in `src/interfaces/metrics.py` (22 Prometheus metrics) + `src/interfaces/dashboard_api.py` `/api/v1/status` | ✅ |
| Timestamp synchronization (NTP) | §6.1.3 | Handled by host OS; Docker containers sync via system clock | ✅ (OS-level) |
| Data retention ≥ 30 days | §6.1.6 | GCP Pub/Sub → BigQuery (`src/interfaces/datalake_publisher.py`); BigQuery retention configurable | ✅ |

### 6.2 Communication Protocols

| Required Protocol | Clause | Implementation Status |
|---|---|---|
| IEC 60870-5-104 or Modbus TCP to CEN SCADA | §6.2.2 | Modbus TCP driver ✅; IEC 60870-5-104 not yet implemented |
| Secure channel (TLS 1.2+) | §6.2.4 | GCP Pub/Sub uses TLS 1.3; direct SCADA connection: planned |

---

## Chapter 8 — Cybersecurity Requirements (NTSyCS 2024 Annex)

| Requirement | Implementation |
|---|---|
| Access control — no default credentials | `DASHBOARD_API_KEY` required in production; documented in README |
| Audit logging | `structlog` structured logging in all modules; Cloud Logging via OTel |
| Software integrity verification | Docker image signed via cosign (planned in release.yml) |
| Vulnerability management | Dependabot weekly scans; `pip-audit` in CI |
| Incident response plan | See [`SECURITY.md`](../../SECURITY.md) |

---

## Gap Analysis

| Gap | Priority | Planned Version |
|---|---|---|
| Power ramp rate limiting | 🔴 High | v2.0 |
| IEC 60870-5-104 protocol support | 🟡 Medium | v2.0 |
| Primary Frequency Response (PFR) droop curve | 🟡 Medium | v2.0 |
| Formal CEN certification submission | 🟢 Strategic | Post-v2.0 |
| Direct TLS SCADA channel to CEN | 🟡 Medium | v1.5 |

---

## References

- NTSyCS 2022 (latest revision) — [Resolución del CEN](https://www.coordinador.cl/normativa/)
- Decreto N° 125 de 2017 (Ministerio de Energía Chile)
- IEEE 1547-2018 — Standard for Interconnection and Interoperability of Distributed Energy Resources
