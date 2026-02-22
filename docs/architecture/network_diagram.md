# Network Architecture — BESSAI Edge Gateway

**Document:** NAD-001  
**Version:** 1.0  
**Date:** 2026-02-22  
**IEC 62443 reference:** SR 5.2 — Zone and Conduit Model  
**Status:** Active

---

## 1. Overview

The BESSAI Edge Gateway mediates between the **OT zone** (BESS hardware) and the **IT zone** (cloud / SCADA). All inter-zone traffic passes through clearly defined conduits with enforced encryption and authentication.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                         IT ZONE (Trust Level: Low)                          ║
║                                                                              ║
║   ┌─────────────┐    HTTPS/TLS    ┌────────────────────────────────────┐   ║
║   │  SCADA /    │◄──────/443─────►│          Cloud / SaaS              │   ║
║   │  Operator   │                 │   (Azure IoT Hub / AWS IoT Core)   │   ║
║   │  Dashboard  │◄── REST+Bearer  │                                    │   ║
║   │  :8080      │    + TOTP MFA   └────────────────────────────────────┘   ║
║   └─────────────┘                                                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                    EDGE ZONE (Trust Level: Medium)                          ║
║                         [Docker bess-net bridge]                            ║
║                                                                             ║
║  ┌──────────────────────────────────────────────────────────────────────┐  ║
║  │                   BESSAI Edge Gateway Container                       │  ║
║  │  ┌───────────┐  ┌────────────┐  ┌──────────────┐  ┌─────────────┐  │  ║
║  │  │ Dashboard │  │  Arbitrage │  │ CMg Predictor│  │ OTel SDK    │  │  ║
║  │  │ API (REST)│  │  Engine    │  │  (ML model)  │  │ (OTLP gRPC) │  │  ║
║  │  └───────────┘  └────────────┘  └──────────────┘  └──────┬──────┘  │  ║
║  │               ┌─────────────────────┐                     │         │  ║
║  │               │  UniversalDriver /   │                     │         │  ║
║  │               │  ModbusDriver        │                     │         │  ║
║  │               └──────────┬──────────┘                     │         │  ║
║  └──────────────────────────┼────────────────────────────────┼─────────┘  ║
║                TCP:502 (bess-net only)               OTLP:4317             ║
║  ┌─────────────────────────▼──────────────────────────────────▼─────────┐ ║
║  │  bessai-stunnel (mTLS proxy)     │  bessai-otel-collector              │ ║
║  │  dweomer/stunnel:5.72            │  → bessai-loki (Loki push)          │ ║
║  │  profile: ot-security            │  → Prometheus scrape                │ ║
║  └──────────┬───────────────────────┴─────────────────────────────────────┘ ║
╠═════════════╪════════════════════════════════════════════════════════════════╣
║             │       OT ZONE (Trust Level: High)                             ║
║          TLS 1.3, mutual auth (GAP-003), Port 8502                         ║
║  ┌──────────▼───────────────────────────────────────────────────────────┐  ║
║  │  BESS Inverter / Battery Management System                            │  ║
║  │  (Huawei SUN2000, BYD, CATL — or simulator in dev mode)              │  ║
║  │  Isolated physical network / VLAN                                    │  ║
║  └──────────────────────────────────────────────────────────────────────┘  ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Security Zones (IEC 62443-3-2)

| Zone | ID | Components | Trust Level | Ingress Control |
|------|----|-----------|-------------|-----------------|
| IT Zone | Z1 | SCADA dashboard, operator browsers, cloud endpoints | Low | TLS 1.3 + Bearer + TOTP MFA |
| Edge Zone | Z2 | BESSAI Gateway, OTel Collector, Loki, Prometheus, Grafana | Medium | Docker bess-net (isolated bridge) |
| OT Zone | Z3 | BESS inverter, Battery Management System | High | mTLS 1.3 + mutual certificate auth |

---

## 3. Conduits (IEC 62443-3-2)

| ID | From | To | Protocol | Port | Security Controls |
|----|------|----|----------|------|-------------------|
| C1 | Z1 (Operators) | Z2 (Dashboard API) | HTTPS/REST | 8080 | TLS 1.3, Bearer + TOTP (GAP-001) |
| C2 | Z2 (Gateway) | Z3 (Inverter) | Modbus TCP over TLS | 8502 | mTLS 1.3, cert auth (GAP-003) |
| C3 | Z2 (OTel Collector) | Z1 (Cloud SIEM) | OTLP gRPC | 4317 | TLS 1.3, Loki push (GAP-002) |
| C4 | Z2 (Gateway) | Z1 (Cloud) | HTTPS/MQTT | 443/8883 | TLS 1.3, device cert or SAS token |
| C5 | Z2 (Prometheus) | Z2 (Grafana) | HTTP | 9090 | bess-net isolation (no external exposure) |

---

## 4. Port Exposure Summary

| Port | Service | Exposed | Justification |
|------|---------|---------|---------------|
| 8080 | Dashboard API | IT Zone | SCADA integration |
| 3000 | Grafana | IT Zone | Monitoring dashboards |
| 9090 | Prometheus | Internal | bess-net only |
| 3100 | Loki | Internal | bess-net only |
| 4317 | OTel OTLP gRPC | Internal | bess-net only |
| 502 | Modbus TCP | Internal | Proxied via stunnel — NOT published to host |
| 8502 | Modbus TLS | OT Zone | mTLS; inverter-side only |

---

## 5. Segmentation Controls

| Control | Implementation | IEC 62443 SR |
|---------|---------------|--------------|
| OT/IT zone separation | Docker bess-net bridge (no host network) | SR 5.2 |
| No direct OT external exposure | stunnel proxy in bess-net; port 8502 not published | SR 5.1 |
| Audit log forwarding | OTel → Loki, 30-day retention | SR 6.1, SR 6.2 |
| Management interface auth | Bearer + TOTP MFA | SR 1.3 |
| OT communication integrity | mTLS 1.3, verify=2 | SR 3.1 |

---

*Satisfies IEC 62443-3-2 §5.4 (Zone and Conduit documentation) required for SL-2 pre-assessment.*
