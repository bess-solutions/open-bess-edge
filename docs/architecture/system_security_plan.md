# BESSAI Edge Gateway — System Security Plan (SSP)

**Version:** 1.0  
**Date:** 2026-02-22  
**Classification:** Confidential — Restricted to PSIRT team and auditors  
**Status:** Active — IEC 62443 Phase 1 deliverable  
**Reference standard:** IEC 62443-3-3:2013

---

## 1. System Description

### 1.1 Product Overview

**BESSAI Edge Gateway** (`open-bess-edge`) is an open-source industrial software system for Battery Energy Storage System (BESS) management. It connects to battery inverters via Modbus TCP, applies safety monitoring and AI-based dispatch optimization, and publishes telemetry to cloud services.

| Attribute | Value |
|---|---|
| **Product version** | v1.8.0 (current) |
| **License** | Apache 2.0 |
| **Repository** | github.com/bess-solutions/open-bess-edge |
| **Language** | Python 3.10+ |
| **Deployment** | Docker / Kubernetes / Bare metal (Raspberry Pi 4+) |
| **Protocols** | Modbus TCP, MQTT TLS, OTLP/gRPC, REST/HTTPS |

### 1.2 System Boundary

The BESSAI Edge Gateway system boundary includes:
- The `open-bess-edge` software stack (Python application + Docker containers)
- The host operating system (Ubuntu 22.04 LTS)
- The Docker network isolation layer
- The Modbus TCP interface to the battery inverter

**Out of scope** (separate security domains):
- The battery inverter hardware itself
- The cloud backend (GCP) — governed by GCP's SOC 2 / ISO 27001
- The operator's corporate network

---

## 2. Security Objectives

| Objective | Description |
|---|---|
| **Confidentiality** | Telemetry data is encrypted in transit (TLS 1.3). No raw operational data leaves the site in plaintext. |
| **Integrity** | Commands to the battery inverter are validated by SafetyGuard before execution. Anomalous commands detected by AI-IDS trigger alerts. |
| **Availability** | The system operates in degraded mode (ONNX offline → MILP → safety rules) if cloud connectivity is lost. Black Start protocol ensures autonomous recovery. |
| **Non-repudiation** | All API access is logged with structured audit logs (structlog). Release artifacts are signed with cosign (SLSA L2). |

---

## 3. Security Requirements Mapping (IEC 62443-3-3 SR)

### 3.1 Identification and Authentication (FR 1)

| SR | Requirement | Implementation | Status |
|---|---|---|---|
| SR 1.1 | Human identification & authentication | API key authentication on all `/api/v1/*` endpoints | ✅ Implemented |
| SR 1.2 | Software process identification | Docker image signed with cosign; SLSA Level 2 provenance | ✅ Implemented |
| SR 1.3 | Account management | Single admin account; VPN required for remote access | ⚠️ Partial — MFA pending |
| SR 1.5 | Authenticator management | API keys stored as environment variables, not in code | ✅ Implemented |
| SR 1.7 | Strength of password-based authentication | API keys: minimum 32 chars random (documented in runbook) | ✅ Implemented |
| SR 1.13 | Access via untrusted networks | VPN required; TLS 1.3 enforced on all external interfaces | ✅ Implemented |

**Gap:** SR 1.3 — Multi-factor authentication (TOTP) not yet implemented for the admin dashboard. Remediation: `pyotp` integration in `src/interfaces/dashboard_api.py` (Q1 2026).

### 3.2 Use Control (FR 2)

| SR | Requirement | Implementation | Status |
|---|---|---|---|
| SR 2.1 | Authorization enforcement | Role-based access: admin endpoints require API key header | ✅ Implemented |
| SR 2.2 | Wireless use control | No wireless interfaces on the Edge Gateway itself | ✅ N/A |
| SR 2.4 | Mobile code | No mobile code (JavaScript, ActiveX) executed by the gateway | ✅ N/A |
| SR 2.8 | Auditable events | All API calls, safety blocks, and AI-IDS alerts logged via structlog | ✅ Implemented |
| SR 2.9 | Audit storage capacity | Logs forwarded to OTel Collector; local rotation: 50MB/day | ⚠️ Partial — SIEM forwarding pending |
| SR 2.12 | Non-repudiation | Structured audit log with timestamps, user, and action for all writes | ✅ Implemented |

**Gap:** SR 2.9 — Logs are collected by OTel but not forwarded to a persistent SIEM. Remediation: Fluentd/Loki output target (Q2 2026).

### 3.3 System Integrity (FR 3)

| SR | Requirement | Implementation | Status |
|---|---|---|---|
| SR 3.1 | Communication integrity | TLS 1.3 on MQTT, OTel, REST APIs; mTLS roadmap for OT segment | ⚠️ Partial |
| SR 3.2 | Protection from malicious code | Trivy container scanning in CI; pip-audit for dependencies; bandit SAST | ✅ Implemented |
| SR 3.3 | Security functionality verification | CI runs 378 tests (including 6 chaos tests) on every commit | ✅ Implemented |
| SR 3.4 | Software and information integrity | SLSA Level 2 provenance; cosign-signed Docker images; CycloneDX SBOM | ✅ Implemented |
| SR 3.9 | Protection of audit information | Audit logs are append-only; OTel Collector holds temporary buffer | ⚠️ Partial |

**Gap:** SR 3.1 — Mutual TLS (mTLS) not yet implemented on the Modbus TCP wrapper for the OT segment. Remediation: client cert pinning in `src/drivers/modbus_driver.py` (Q2 2026).

### 3.4 Data Confidentiality (FR 4)

| SR | Requirement | Implementation | Status |
|---|---|---|---|
| SR 4.1 | Information confidentiality | Telemetry encrypted via TLS before leaving the site | ✅ Implemented |
| SR 4.2 | Information persistence | Sensitive config stored as environment variables, not in Docker image | ✅ Implemented |
| SR 4.3 | Use of cryptography | TLS 1.3 (AES-256-GCM), ECDHE key exchange | ✅ Implemented |

### 3.5 Restricted Data Flow (FR 5)

| SR | Requirement | Implementation | Status |
|---|---|---|---|
| SR 5.1 | Network segmentation | Docker bridge networks isolate OT simulator from monitoring stack | ✅ Implemented |
| SR 5.2 | Zone boundary protection | Three-zone architecture (OT / DMZ / IT); no inbound connections to Zone 0 | ✅ Implemented |
| SR 5.3 | General purpose person-to-person communication restrictions | No chat, email, or file-sharing services run on Edge Gateway | ✅ N/A |
| SR 5.4 | Application partitioning | Core safety functions isolated in `src/core/safety.py`; fail-safe defaults | ✅ Implemented |

### 3.6 Timely Response to Events (FR 6)

| SR | Requirement | Implementation | Status |
|---|---|---|---|
| SR 6.1 | Audit log accessibility | Structured logs accessible via OTel Collector API | ✅ Implemented |
| SR 6.2 | Continuous monitoring | Prometheus metrics + Grafana alerting + AI-IDS anomaly detection | ✅ Implemented |

### 3.7 Resource Availability (FR 7)

| SR | Requirement | Implementation | Status |
|---|---|---|---|
| SR 7.1 | DoS protection | Docker resource limits in `docker-compose.yml`; NetworkPolicy in K8s | ✅ Implemented |
| SR 7.3 | Control system backup | Configuration backed up in git; `.env` backed up per operator runbook | ✅ Implemented |
| SR 7.4 | Control system recovery | Black Start protocol + `ONNX offline` mode docs | ✅ Implemented |
| SR 7.6 | Network and security configuration settings | All config as environment variables; IaC via Terraform | ✅ Implemented |

---

## 4. Security Architecture (Summary)

See [`docs/architecture/network_diagram.md`](network_diagram.md) for the full visual representation.

**Key architectural decisions:**
1. **Edge-First:** Safety-critical operations never depend on cloud connectivity (ADR-001)
2. **Defense-in-Depth:** Threat model assumes each layer can be individually compromised
3. **Least Privilege:** Each Docker container runs with minimal Linux capabilities
4. **Zero-Trust for Cloud:** GCP auth via Workload Identity Federation — no long-lived credentials
5. **Supply Chain Security:** SLSA L2 provenance + cosign + SBOM on every release

---

## 5. Open Gaps and Remediation Plan

| Gap ID | SR | Description | Remediation | Target |
|---|---|---|---|---|
| GAP-001 | SR 1.3 | No MFA on admin dashboard | Implement TOTP via `pyotp` in `dashboard_api.py` | Q1 2026 |
| GAP-002 | SR 2.9 | Logs not forwarded to SIEM | Add Fluentd/Loki output to OTel Collector config | Q2 2026 |
| GAP-003 | SR 3.1 | No mTLS on OT segment | Client cert pinning in `modbus_driver.py`; Ingress mTLS config | Q2 2026 |
| GAP-004 | SR 5.2 | No hardware data diode | Evaluate Fox DataDiode / Waterfall for physical separation | Q3 2026 |

**Current SL-2 readiness: ~65%** (baseline from `iec62443_sl2_gap.md`)  
**Target after GAP-001–003 remediation: ~85%** (sufficient for formal audit)

---

## 6. Review and Maintenance

This SSP must be reviewed and updated:
- After any **MAJOR version release** of `open-bess-edge`
- Within **30 days** of any significant architecture change (per IEC 62443 maintenance requirements)
- Annually as part of the certification surveillance audit (after formal SL-2 is obtained)

**Next review date:** 2026-06-01 (after Q1/Q2 gap remediation)

---

## 7. References

- [Network Architecture Diagram](network_diagram.md)
- [IEC 62443 SL-2 Certification Path](../compliance/iec_62443_sl2_certification_path.md)
- [PSIRT Process](../compliance/psirt_process.md)
- [Patch Management SLA](../compliance/patch_management_sla.md)
- [SECURITY.md](../../SECURITY.md)
- [ADR-001: Edge-First Architecture](../adr/)
- IEC 62443-3-3:2013 — Industrial automation and control systems security
