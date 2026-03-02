# BESSAI Edge Gateway

> **Open-source industrial BESS gateway** — AI-augmented anomaly detection, NTSyCS-compliant telemetry, and IEC 62443 SL-1 security architecture for battery energy storage systems.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/bess-solutions/open-bess-edge/actions/workflows/ci.yml/badge.svg)](https://github.com/bess-solutions/open-bess-edge/actions)
[![Security Policy](https://img.shields.io/badge/Security-Policy-red?logo=github)](https://github.com/bess-solutions/open-bess-edge/blob/main/SECURITY.md)
[![IEC 62443](https://img.shields.io/badge/IEC_62443-SL--1_Mapped-orange)](compliance/iec62443_mapping.md)
[![NTSyCS](https://img.shields.io/badge/NTSyCS-CEN_Chile-green)](compliance/ntscys_compliance.md)

---

## What is BESSAI Edge Gateway?

BESSAI Edge Gateway is a **production-grade, open-source** industrial control system component that:

- 🔌 **Connects** to BESS inverters (Huawei SUN2000 / LUNA2000) via **Modbus TCP**
- 🛡️ **Enforces** real-time safety constraints (SOC limits, temperature thresholds) via `SafetyGuard`
- 🤖 **Detects** anomalies using an ensemble of **IsolationForest + z-score** (AI-IDS)
- 🧠 **Dispatches** ONNX ML model inferences for **optimal energy arbitrage**
- ☁️ **Publishes** telemetry to **GCP Pub/Sub** with full OpenTelemetry observability
- 📊 **Exposes** 22 **Prometheus metrics** + Grafana dashboards

```mermaid
graph TD
    A[Inversor SUN2000 / LUNA2000] -->|Modbus TCP| B[BESSAI Edge Gateway]
    B --> C[SafetyGuard - SOC/Temp]
    B --> D[AI-IDS - IsolationForest]
    B --> E[ONNX Dispatcher]
    B --> F[GCP Pub/Sub]
    B --> G[Prometheus /metrics]
    G --> H[Grafana Dashboard]
    F --> I[GCP Cloud Logging / BigQuery]
```

---

## Key Features

=== "Safety-First"
    - Hard limits enforced independently of cloud connectivity
    - Watchdog loop with automatic restart on gateway hang
    - `SafetyGuard.check_safety()` blocks unsafe commands before execution

=== "AI-Powered"
    - `ModbusAnomalyDetector`: IsolationForest + z-score ensemble
    - `ONNXDispatcher`: offline edge inference with safe fallback
    - 6 real-time AI metrics in Prometheus

=== "Standards-Compliant"
    - ✅ IEC 62443-3-3 SL-1 (7 Foundation Requirements)
    - ✅ NTSyCS CEN Chile (Chapter 4, 6, 8)
    - ✅ OpenSSF Best Practices
    - ✅ SBOM (CycloneDX) + cosign image signing

=== "Observable"
    - 22 Prometheus metrics with [12 alert rules](alerting.md)
    - OpenTelemetry traces to GCP Cloud Trace
    - Structured logs via `structlog`

---

## 🚀 Para Early Adopters

> ¿Quieres desplegar BESSAI en una instalación real? Empieza aquí.

| Quiero... | Recurso |
|-----------|--------|
| Elegir mi camino (probar / desplegar / contribuir) | [ADOPTER_HUB.md](ADOPTER_HUB.md) |
| Demo local en 5 min (sin hardware) | [tutorials/quickstart_5min.md](tutorials/quickstart_5min.md) |
| Roadmap día 0 → producción | [ONBOARDING_7DAYS.md](ONBOARDING_7DAYS.md) |
| FAQ técnica (hw alternativo, mercados, licencia) | [FAQ.md](FAQ.md) |
| Programa Early Adopters (soporte prioritario) | [early_adopters.md](early_adopters.md) |

---

## Quick Start

```bash
# Clone
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# Configure
cp config/.env.example config/.env
# Edit INVERTER_IP, SITE_ID, GCP_PROJECT_ID

# Run (Docker)
docker compose up bessai-gateway

# Verify
curl http://localhost:8000/health
# → {"status": "healthy", "site_id": "SITE-CL-001", "uptime_s": 12.3}
```

→ See the full [Quick Start guide](quickstart.md)

---

## Architecture

The gateway runs a **single async event loop** with three concurrent tasks:

1. **Modbus polling loop** — reads all registers every cycle (`WATCHDOG_TIMEOUT`)
2. **AI-IDS pipeline** — runs anomaly detection, updates Prometheus metrics
3. **Cloud publisher** — batches and publishes to GCP Pub/Sub

→ See [Architecture Overview](architecture.md) and [ADRs](adr/README.md)

---

## Project Status — v1.4.0

| Component | Status |
|---|---|
| Modbus TCP Driver | ✅ Production |
| SafetyGuard | ✅ Production |
| AI-IDS (IsolationForest + z-score) | ✅ Production |
| ONNX Dispatcher | ✅ Production |
| GCP Pub/Sub Publisher | ✅ Production |
| OpenTelemetry | ✅ Production |
| Prometheus (22 metrics + 12 alerts) | ✅ Production |
| Grafana Dashboards | ✅ Production |
| IEC 62443 SL-1 | ✅ Mapped |
| NTSyCS CEN Chile | ✅ Mapped |
| SBOM + cosign signing | ✅ On every release |
| Test suite | ✅ 372/372 |

---

## Community

- 🤝 **Early Adopters:** [ADOPTER_HUB.md](ADOPTER_HUB.md) — empieza por aquí
- 🐛 **Bug reports:** [GitHub Issues](https://github.com/bess-solutions/open-bess-edge/issues/new?template=bug_report.yml)
- 🆘 **Adopter support:** [GitHub Issues](https://github.com/bess-solutions/open-bess-edge/issues/new?template=adopter_support.yml)
- ✨ **Feature requests:** [GitHub Issues](https://github.com/bess-solutions/open-bess-edge/issues/new?template=feature_request.yml)
- 🔒 **Security vulnerabilities:** See [SECURITY.md](https://github.com/bess-solutions/open-bess-edge/blob/main/SECURITY.md)
- 📖 **Contributing:** See [CONTRIBUTING.md](https://github.com/bess-solutions/open-bess-edge/blob/main/CONTRIBUTING.md)
