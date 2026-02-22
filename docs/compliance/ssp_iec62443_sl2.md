# System Security Plan (SSP) — BESSAI Edge Gateway

**Document:** SSP-001  
**Version:** 1.0  
**Date:** 2026-02-22  
**Standard:** IEC 62443-3-3 Security Level 2 (SL-2)  
**Status:** Pre-assessment draft

---

## 1. System Identification

| Field | Value |
|-------|-------|
| System name | BESSAI Edge Gateway |
| Version | v2.1.0 |
| Owner | BESS Solutions SpA |
| Classification | Industrial Control System (IACS) — Energy Storage |
| Repository | [github.com/bess-solutions/open-bess-edge](https://github.com/bess-solutions/open-bess-edge) |
| Target SL | SL-2 (IEC 62443-3-3) |

---

## 2. System Description

The BESSAI Edge Gateway is a software-defined industrial gateway that:
1. Reads real-time telemetry from BESS inverters via Modbus TCP (mTLS encrypted)
2. Runs ML-based arbitrage optimization (hourly CMg price prediction)
3. Issues control setpoints back to the BESS inverter
4. Forwards structured audit logs to a SIEM (Grafana Loki)
5. Exposes a REST dashboard API with MFA for SCADA operators

**Deployment context:** Grid-connected BESS systems (100 kW – 100 MW). Operates in Zone 2 (Edge) mediating between Zone 1 (IT/SCADA) and Zone 3 (OT/inverter). See [NAD-001](../architecture/network_diagram.md).

---

## 3. Security Requirements Coverage (IEC 62443-3-3)

### 3.1 Foundational Requirements (FR)

#### FR 1 — Identification and Authentication Control (IAC)

| SR | Requirement | Implementation | Status |
|----|-------------|----------------|--------|
| SR 1.1 | Human user identification and authentication | Bearer token + TOTP MFA (`totp_auth.py`) | ✅ SL-2 |
| SR 1.2 | Software process and device identification | Docker container identity; OTel service.name | ✅ SL-2 |
| SR 1.3 | Account management | API key rotation via `DASHBOARD_API_KEY` env var | ✅ SL-2 |
| SR 1.5 | Authenticator management | TOTP secret via `DASHBOARD_MFA_SECRET` (not stored in code) | ✅ SL-2 |
| SR 1.13 | Access via untrusted network | TLS 1.3 required on all external interfaces | ✅ SL-2 |

#### FR 2 — Use Control (UC)

| SR | Requirement | Implementation | Status |
|----|-------------|----------------|--------|
| SR 2.1 | Authorization enforcement | Dashboard endpoints require Bearer + TOTP | ✅ SL-2 |
| SR 2.2 | Wireless use control | No wireless interfaces; wired Ethernet only | ✅ N/A |
| SR 2.8 | Auditable events | structlog → OTel → Loki (auth, writes, errors) | ✅ SL-2 |
| SR 2.9 | Audit storage capacity | Loki 30-day retention, filesystem-backed | ✅ SL-2 |
| SR 2.12 | Non-repudiation | Structured logs with timestamp, remote IP, user action | ✅ SL-2 |

#### FR 3 — System Integrity (SI)

| SR | Requirement | Implementation | Status |
|----|-------------|----------------|--------|
| SR 3.1 | Communication integrity | mTLS 1.3 on Modbus OT segment (stunnel proxy) | ✅ SL-2 |
| SR 3.2 | Malicious code protection | Trivy container scan in CI; Dependabot | ✅ SL-2 |
| SR 3.3 | Security functionality verification | pytest suite (419 tests); SLSA Level 2 | ✅ SL-2 |
| SR 3.4 | Software and information integrity | cosign image signing on every release | ✅ SL-2 |
| SR 3.6 | Deterministic output | ONNX deterministic inference; idempotent Modbus writes | ✅ SL-2 |

#### FR 4 — Data Confidentiality (DC)

| SR | Requirement | Implementation | Status |
|----|-------------|----------------|--------|
| SR 4.1 | Data confidentiality in transit | TLS 1.3 on all external channels (C1–C4) | ✅ SL-2 |
| SR 4.2 | Data confidentiality at rest | Secrets via env vars / Docker Secrets; no plaintext in code | ✅ SL-2 |
| SR 4.3 | Use of cryptography | TLS 1.3 (AES-256-GCM, ECDHE), TOTP (HMAC-SHA1, RFC 6238) | ✅ SL-2 |

#### FR 5 — Restricted Data Flow (RDF)

| SR | Requirement | Implementation | Status |
|----|-------------|----------------|--------|
| SR 5.1 | Network segmentation | Docker bess-net bridge; no OT port published to host | ✅ SL-2 |
| SR 5.2 | Zone boundary protection | 3 zones (Z1/Z2/Z3) with enforced conduits (NAD-001) | ✅ SL-2 |
| SR 5.3 | General purpose person-to-person communication | Not applicable (no chat/email in gateway) | ✅ N/A |

#### FR 6 — Timely Response to Events (TRE)

| SR | Requirement | Implementation | Status |
|----|-------------|----------------|--------|
| SR 6.1 | Audit log accessibility | Loki API, Grafana Explore; 30-day retention | ✅ SL-2 |
| SR 6.2 | Continuous monitoring | Prometheus + Grafana alerts; OTel metric pipeline | ✅ SL-2 |

#### FR 7 — Resource Availability (RA)

| SR | Requirement | Implementation | Status |
|----|-------------|----------------|--------|
| SR 7.1 | Denial of service protection | Docker resource limits (CPU/mem); rate limiting on API | ⚠️ Partial |
| SR 7.3 | Control system backup | `docker compose` declarative; config in Git | ✅ SL-2 |
| SR 7.6 | Network and security configuration settings | All config via env vars; no runtime config mutation | ✅ SL-2 |

---

## 4. Residual Risks

| Risk | Likelihood | Impact | Mitigation | SL gap |
|------|-----------|--------|-----------|--------|
| DoS on Dashboard API | Medium | Medium | Rate limiting (planned v2.2.0) | SR 7.1 partial |
| Physical access to edge node | Low | High | Scope: physical security by site operator | Out of scope |
| Formal auditor not yet engaged | N/A | N/A | Pre-assessment planned Q1 2026 | Process |

---

## 5. Evidence Index

| Evidence | Location |
|----------|----------|
| Source code + tests | [github.com/bess-solutions/open-bess-edge](https://github.com/bess-solutions/open-bess-edge) |
| Test results (419/419) | CI artifacts — GitHub Actions |
| Network diagram (NAD-001) | [`docs/architecture/network_diagram.md`](../architecture/network_diagram.md) |
| mTLS config | `infrastructure/certs/gen_certs.sh`, `infrastructure/docker/stunnel-ot.conf` |
| TOTP MFA | `src/interfaces/totp_auth.py`, `tests/test_totp_auth.py` |
| SIEM config | `infrastructure/loki/loki-config.yaml`, `infrastructure/docker/otel-collector-config.yaml` |
| SLSA + cosign | `.github/workflows/release.yml` |
| Vulnerability policy | [`SECURITY.md`](../../SECURITY.md) |
| Patch SLA | [`docs/compliance/patch_management_sla.md`](patch_management_sla.md) |

---

*This SSP maps BESSAI Edge Gateway v2.1.0 to IEC 62443-3-3 SL-2 requirements. Ready for pre-assessment submission to TÜV SÜD / DNV.*
