# BESSAI Edge Gateway — Network Architecture Diagram

**Version:** 1.0  
**Date:** 2026-02-22  
**Classification:** Non-confidential (topology names and IPs are representative)  
**Status:** Active — IEC 62443 Phase 1 deliverable

---

## Overview

This document provides the formal **network architecture diagram** for BESSAI Edge Gateway deployments, defining the OT/IT network segmentation required for IEC 62443-3-3 SL-2 certification (SR 5.2 — Zone and Conduit definitions).

---

## Zone and Conduit Model (IEC 62443-3-3 SR 5.2)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ZONE 0 — OT / Field Level (Air-Gapped)                                      │
│  Security Level: SL-2 target                                                 │
│                                                                              │
│  ┌──────────────────────┐    Modbus TCP     ┌──────────────────────────────┐ │
│  │  BESS / Inverter     │ ──────────────►  │  BESSAI Edge Gateway         │ │
│  │  (Huawei SUN2000     │   Port 502        │  (open-bess-edge)            │ │
│  │   / SMA / Victron    │   Private VLAN    │  IP: 192.168.10.10           │ │
│  │   / Fronius)         │                  │  Ports: 8000 (API), 502      │ │
│  │  IP: 192.168.10.1    │                  │  OS: Ubuntu 22.04 LTS        │ │
│  └──────────────────────┘                  │  Runtime: Docker 24.x         │ │
│                                            └──────────────┬───────────────┘ │
└────────────────────────────────────────────────────────── │ ────────────────┘
                                                            │
                                    ╔═══════════════════════╪═══════════╗
                                    ║  CONDUIT C1 — OT→DMZ  │           ║
                                    ║  Protocol: OTLP/gRPC  │           ║
                                    ║  Direction: Outbound  │           ║
                                    ║  Auth: mTLS (client   │           ║
                                    ║        cert pinned)   │           ║
                                    ╚═══════════════════════╪═══════════╝
                                                            │
┌──────────────────────────────────────────────────────────────────────────────┐
│  ZONE 1 — DMZ / Security Boundary                                            │
│                                                                              │
│  ┌───────────────────────┐         ┌────────────────────────────────────┐   │
│  │  AI-IDS               │         │  OpenTelemetry Collector           │   │
│  │  (Isolation Forest    │         │  Port: 4317 (gRPC), 4318 (HTTP)    │   │
│  │   + LSTM Autoencoder) │         │  Receives: traces, metrics, logs   │   │
│  │  Modbus traffic       │         │  Exports: → Prometheus, → Loki     │   │
│  │  anomaly detection    │         │                                    │   │
│  └────────────┬──────────┘         └────────────────────┬───────────────┘   │
│               │ SIEM alerts                              │                   │
└────────────── │ ──────────────────────────────────────── │ ──────────────────┘
                │                                          │
    ╔═══════════╪═══════════════╗            ╔═════════════╪═════════════╗
    ║  CONDUIT C2 — DMZ→IT SIEM║            ║  CONDUIT C3 — DMZ→Cloud   ║
    ║  Protocol: Syslog/TLS     ║            ║  Protocol: HTTPS/TLS 1.3  ║
    ║  Direction: Outbound only ║            ║  Direction: Outbound only ║
    ╚═══════════╪═══════════════╝            ╚═════════════╪═════════════╝
                │                                          │
┌───────────────┼──────────────────────────────────────────┼───────────────────┐
│  ZONE 2 — IT Network / Corporate                                             │
│               │                                          │                   │
│  ┌────────────┴────────────┐         ┌────────────────────┴────────────────┐ │
│  │  SIEM                   │         │  Cloud (GCP)                        │ │
│  │  (Chronicle / Splunk)   │         │  ├── GCP Pub/Sub (telemetry stream) │ │
│  │  Receives security       │         │  ├── BigQuery (data lake)           │ │
│  │  alerts from AI-IDS     │         │  ├── Prometheus (metrics)           │ │
│  │  Port: 514 (Syslog/TLS) │         │  ├── Grafana (dashboards)           │ │
│  └─────────────────────────┘         │  └── Loki (structured logs)         │ │
│                                      └─────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  Operator Workstation — Management Access                               │ │
│  │  VPN required (WireGuard) → Edge Gateway admin port :8000               │ │
│  │  MFA required (TOTP — roadmap Q1 2026)                                  │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Zone Definitions

| Zone | Name | Security Level | Description |
|---|---|---|---|
| **Zone 0** | OT / Field | SL-2 (target) | Battery inverter hardware + Edge Gateway. Physically isolated. No inbound connections. |
| **Zone 1** | DMZ | SL-1 (current) | Security inspection layer. AI-IDS, OTel collector. Unidirectional data flow outbound only. |
| **Zone 2** | IT / Cloud | SL-1 | Corporate network and cloud services. No direct access to Zone 0. |

---

## Conduit Definitions

| Conduit | From → To | Protocol | Direction | Auth | Encryption |
|---|---|---|---|---|---|
| **C1** | Zone 0 → Zone 1 | OTLP/gRPC | Outbound only | mTLS (roadmap) | TLS 1.3 |
| **C2** | Zone 1 → Zone 2 (SIEM) | Syslog/TLS | Outbound only | TLS client cert | TLS 1.3 |
| **C3** | Zone 1 → Cloud (GCP) | HTTPS | Outbound only | OIDC/WIF | TLS 1.3 |
| **C4** | Zone 2 → Zone 0 (mgmt) | HTTPS + VPN | Inbound limited | API key + VPN + MFA | TLS 1.3 + WireGuard |

> **No direct conduit exists from Zone 2 to Zone 0.** All management access goes through Zone 1 and is authenticated + encrypted.

---

## Firewall Rules Summary

### Zone 0 (Edge Gateway) — Inbound

| Port | Protocol | Source | Purpose |
|---|---|---|---|
| 502 | TCP | 192.168.10.0/24 (OT VLAN) | Modbus TCP from inverter |
| 8000 | TCP | 10.0.0.0/8 (VPN range) | Admin API (requires VPN) |

### Zone 0 (Edge Gateway) — Outbound

| Port | Protocol | Destination | Purpose |
|---|---|---|---|
| 4317 | TCP | OTel Collector (DMZ) | OTLP/gRPC telemetry |
| 1883 / 8883 | TCP | MQTT broker (optional) | MQTT publishing |

### Zone 1 (DMZ) — Outbound

| Port | Protocol | Destination | Purpose |
|---|---|---|---|
| 443 | HTTPS | GCP APIs | Pub/Sub, BigQuery, Artifact Registry |
| 514 | TLS | SIEM endpoint | Security alerts from AI-IDS |

---

## IEC 62443 Compliance Mapping

| Requirement | Standard | Implementation |
|---|---|---|
| SR 5.2 — Zone separation | IEC 62443-3-3 | Three zones (OT / DMZ / IT) with explicit conduits |
| SR 3.1 — Communication integrity | IEC 62443-3-3 | TLS 1.3 enforced on all external conduits |
| SR 1.3 — Account management | IEC 62443-3-3 | API key auth + VPN + MFA (roadmap) for admin |
| SR 7.1 — DoS protection | IEC 62443-3-3 | NetworkPolicy (K8s) + Docker network isolation |

---

## Gaps and Remediation Roadmap

| Gap | Current State | Target | Timeline |
|---|---|---|---|
| mTLS on C1 (OT→DMZ) | TLS server-only | mTLS with pinned client cert | Q1 2026 |
| MFA on management access | API key only | TOTP via pyotp | Q1 2026 |
| SIEM integration (C2) | Logs in container stdout | Fluentd → Loki export | Q2 2026 |
| Physical data diode (C1) | Software isolation | Fox DataDiode / Waterfall | Q3 2026 (hardware) |

---

## References

- [IEC 62443 SL-2 Certification Path](iec_62443_sl2_certification_path.md)
- [System Security Plan](system_security_plan.md)
- [Architecture Overview](../architecture.md)
- [IEC 62443-3-3:2013 — System Security Requirements and Security Levels](https://www.iec.ch/iec62443)
