# IEC 62443 Security Mapping — BESSAI Edge Gateway

> **IEC 62443** — Security for Industrial Automation and Control Systems (IACS)  
> **Relevant parts:** IEC 62443-2-1 (CSMS), IEC 62443-3-3 (System security requirements), IEC 62443-4-2 (Component requirements)  
> **Mapping date:** 2026-02-21 · **Project version:** `open-bess-edge` v1.3.2  
> **Target Security Level:** SL-1 (current) → SL-2 (target by v2.0)

---

## Summary

BESSAI Edge Gateway is an **Industrial Control System (ICS) component** that interfaces with BESS hardware via Modbus TCP and publishes operational data to cloud infrastructure. This document maps IEC 62443 controls to the implementation.

---

## IEC 62443-3-3: System Security Requirements

### FR 1 — Identification and Authentication Control (IAC)

| Requirement | SR | Implementation | Status |
|---|---|---|---|
| Human user identification | SR 1.1 | Dashboard API requires `DASHBOARD_API_KEY` in production mode | ✅ SL-1 |
| Software process identification | SR 1.2 | GCP Service Account (`bessai-edge-sa-dev`) with role `pubsub.publisher` only | ✅ SL-1 |
| Account management | SR 1.3 | IAM via Terraform; least-privilege roles; no shared accounts | ✅ SL-1 |
| Identifier management | SR 1.4 | `SITE_ID` env var uniquely identifies each gateway instance | ✅ |
| Authenticator management | SR 1.5 | Workload Identity Federation (no long-lived keys in containers) | ✅ SL-2 |
| Multi-factor authentication | SR 1.7 | Not implemented (edge device context) | ❌ N/A for SL-1 |

### FR 2 — Use Control (UC)

| Requirement | SR | Implementation | Status |
|---|---|---|---|
| Authorization enforcement | SR 2.1 | Dashboard API authorization via API key; Modbus write only to `watchdog_heartbeat` and allowed registers | ✅ SL-1 |
| Least privilege | SR 2.2 | GCP SA: only `pubsub.publisher` role; OTel exporter: only write to OTLP endpoint | ✅ SL-1 |
| Software and information integrity | SR 2.4 | Docker image built from pinned base image; pip dependencies version-locked; SBOM generated (release.yml) | ✅ SL-1 |

### FR 3 — System Integrity (SI)

| Requirement | SR | Implementation | Status |
|---|---|---|---|
| Communication integrity | SR 3.1 | GCP Pub/Sub uses TLS 1.3; OTLP uses gRPC with TLS | ✅ SL-1 |
| Malicious code protection | SR 3.2 | Bandit SAST in CI; Trivy CVE scanning on Docker image; pip-audit on dependencies | ✅ SL-1 |
| Security functionality verification | SR 3.3 | 372 automated tests including safety and anomaly detection;  CI gate at every push | ✅ SL-1 |
| Software and information integrity | SR 3.4 | `ruff`, `mypy` enforced in CI; no `eval()`, no `exec()`, no `pickle.loads()` on untrusted input | ✅ SL-1 |

### FR 4 — Data Confidentiality (DC)

| Requirement | SR | Implementation | Status |
|---|---|---|---|
| Information confidentiality | SR 4.1 | Telemetry data encrypted in transit (TLS 1.3 to GCP); at-rest encryption via GCP | ✅ SL-1 |
| Information persistence | SR 4.2 | No sensitive data persisted locally in plaintext; logs sanitized via structlog | ✅ SL-1 |
| Use of cryptography | SR 4.3 | GCP SDK uses OpenSSL; no custom crypto implementations | ✅ SL-1 |

### FR 5 — Restricted Data Flow (RDF)

| Requirement | SR | Implementation | Status |
|---|---|---|---|
| Network segmentation | SR 5.1 | Docker network isolation: `bessai-net` internal bridge; only port 8000 exposed | ✅ SL-1 |
| Zone boundary protection | SR 5.2 | Modbus TCP restricted to `INVERTER_IP` only; no Modbus server exposed | ✅ SL-1 |

### FR 6 — Timely Response to Events (TRE)

| Requirement | SR | Implementation | Status |
|---|---|---|---|
| Audit log accessibility | SR 6.1 | Structured logs via `structlog`; exported to GCP Cloud Logging via OTel | ✅ SL-1 |
| Continuous monitoring | SR 6.2 | Prometheus 22 metrics + Grafana dashboards; Alertmanager rules in `alert_rules.yml` | ✅ SL-1 |
| Response time metric | SR 6.3 | `bess_cycle_duration_seconds` histogram in Prometheus | ✅ |

### FR 7 — Resource Availability (RA)

| Requirement | SR | Implementation | Status |
|---|---|---|---|
| Denial of Service protection | SR 7.1 | Watchdog loop: auto-restart on gateway hang; Docker `restart: unless-stopped` | ✅ SL-1 |
| Resource management | SR 7.2 | Async event loop; no blocking I/O on main thread; OTel BatchSpanProcessor | ✅ SL-1 |
| Control system backup | SR 7.3 | SafetyGuard operates independently of cloud connectivity; fail-safe defaults | ✅ SL-1 |

---

## IEC 62443-4-2: Component Security Requirements

### Modbus Driver Component (`src/drivers/modbus_driver.py`)

| CSR | Requirement | Implementation |
|---|---|---|
| CSR 1.1 | Authenticator uniqueness | Single-host Modbus TCP; no shared connection pool |
| CSR 3.1 | Communication integrity | pymodbus CRC validation (built-in to Modbus protocol) |
| CSR 7.2 | Resource management | 3-retry exponential backoff; connection timeout configurable |

### Dashboard API Component (`src/interfaces/dashboard_api.py`)

| CSR | Requirement | Implementation |
|---|---|---|
| CSR 1.2 | API authentication | `X-API-Key` header; configurable secret via env var |
| CSR 2.1 | Access restriction | Read-only endpoints only; no write operations exposed to API |
| CSR 6.1 | Audit log | All API requests logged with `structlog` (method, path, status, latency) |

---

## Security Level Roadmap

| Feature | Current SL | Target SL | Gap Action |
|---|---|---|---|
| MFA for human operators | 0 | SL-2 | Integrate with GCP IAP or Keycloak |
| Encrypted Modbus (Modbus over TLS) | 0 | SL-2 | Requires inverter support; evaluate per-site |
| Integrity verification at boot | SL-1 | SL-2 | Docker image signing with cosign (release.yml) |
| Hardware Security Module (HSM) | 0 | SL-3 | Out of scope for v2.0 |

---

## References

- IEC 62443-2-1:2010 — Establishing an IACS Security Management System
- IEC 62443-3-3:2013 — System Security Requirements and Security Levels
- IEC 62443-4-2:2019 — Technical Security Requirements for IACS Components
- NIST SP 800-82 Rev 3 — Guide to OT Security (2023)
