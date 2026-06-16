<div align="center">

# 🔋 BESSAI Edge Gateway

**Industrial-grade open-source edge gateway for secure, AI-optimized Battery Energy Storage System (BESS) management.**

*Self-evolving arbitrage intelligence · IEC 62443 SL-1→SL-3 · IEC 61850 · DNP3 · IEC 60870-5-104 · IEEE 1547-2018 IBR/GFM · NTSyCS Chile*

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/bess-solutions/open-bess-edge/actions/workflows/ci.yml/badge.svg)](https://github.com/bess-solutions/open-bess-edge/actions)
[![Codecov](https://codecov.io/gh/bess-solutions/open-bess-edge/branch/main/graph/badge.svg)](https://codecov.io/gh/bess-solutions/open-bess-edge)
[![Docker](https://img.shields.io/badge/Docker-amd64%20%7C%20arm64-2496ED?logo=docker&logoColor=white)](https://ghcr.io/bess-solutions/open-bess-edge)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/bess-solutions/open-bess-edge/badge)](https://scorecard.dev/viewer/?uri=github.com/bess-solutions/open-bess-edge)
[![IEC 62443](https://img.shields.io/badge/IEC_62443-SL--1%2FSL--2%2FSL--3_Roadmap-orange)](docs/compliance/iec62443_mapping.md)
[![IEEE 1547](https://img.shields.io/badge/IEEE_1547--2018-IBR%2FGFM_Ready-green)](docs/compliance/ieee1547_mapping.md)
[![DNP3](https://img.shields.io/badge/DNP3-IEC_60870--5--104-blue)](docs/specs/protocol_stack.md)
[![NTSyCS](https://img.shields.io/badge/NTSyCS-11_GAPs_Closed-brightgreen)](docs/compliance/ntscys_compliance.md)
[![BESSAI-SPEC](https://img.shields.io/badge/BESSAI--SPEC-4_normative_docs-blueviolet)](docs/specs/)
[![BEP Process](https://img.shields.io/badge/BEPs-10_proposals-lightblue)](docs/bep/BEP-0001.md)
[![Tests](https://img.shields.io/badge/tests-799_passing-brightgreen)](tests/)
[![Version](https://img.shields.io/badge/version-v2.17.1-blue)](.)
[![Security](https://img.shields.io/badge/Security-SECURITY.md-red)](SECURITY.md)

[**Documentation**](https://bess-solutions.github.io/open-bess-edge) · [**Quick Start**](#-quick-start) · [**Discord**](https://discord.gg/ZqpE8AZs) · [**BEP Proposals**](docs/bep/BEP-0001.md) · [**Roadmap**](#-roadmap)

</div>

---

## What is BESSAI Edge Gateway?

BESSAI is a production-ready edge computing platform that sits between your Battery Energy Storage System hardware and cloud infrastructure. It handles:

- **Real-time telemetry** collection from inverters and BMS (Modbus TCP, IEC 61850, DNP3, IEC 60870-5-104)
- **AI-powered dispatch** decisions via a DRL arbitrage agent (ONNX inference, no cloud required)
- **Autonomous self-improvement** via BESSAIEvolve — an AlphaEvolve-inspired weekly evolution loop
- **Safety enforcement** with IEC 62443 SL-1/SL-2 compliant guardrails — roadmap to SL-3
- **Multi-cloud publishing** to GCP Pub/Sub, MQTT, OpenTelemetry
- **Full system architecture**: from BT battery racks + bidirectional inverters + transformers + MT cells + protections + plant SCADA + substation SCADA + IoT gateway + industrial firewall/DMZ + local EMS + control UPS

> **Reference deployment:** 200kWh / 100kW Huawei SUN2000 BESS, Santiago Chile — arbitraging the Chilean SEN spot market (CMg) in production since 2025.

---

## 🏗️ Architecture

```mermaid
graph TB
    subgraph HW["⚡ Physical BESS System"]
        BAT[Battery Racks BT<br/>+ BMS per module]
        INV[Bidirectional Inverters<br/>Huawei · SMA · Sungrow · BYD · Tesla]
        TRF[Step-up Transformer<br/>BT → MT]
        MT[MT Switchgear & Cells<br/>13.2 kV / 23 kV]
        PROT[Protection Relays<br/>All interfaces: BT · AC · MT · PCC]
    end

    subgraph Edge["🖥️ Open BESS Edge Gateway"]
        GW[IoT Gateway / Edge Compute<br/>Modbus→MQTT · OPC-UA · TLS]
        FW[Industrial Firewall + DMZ<br/>OT/IT Segmentation · DPI]
        EMS[Local EMS / DERMS<br/>24-48h Autonomous · Grid-Forming]
        UPS[Control UPS<br/>Emergency power for control systems]
        DRV[Protocol Drivers<br/>Modbus TCP · IEC 61850 · DNP3 · IEC 104]
        SG[SafetyGuard<br/>IEC 62443 SL-1/SL-2]
        subgraph AI["🤖 AI Engine"]
            IDS[AI-IDS<br/>IsolationForest]
            DRL[DRL Agent<br/>PPO ONNX]
            EVO[BESSAIEvolve<br/>Weekly μ+λ Evolution]
        end
        TEL[Telemetry Layer<br/>Prometheus · OpenTelemetry · MQTT/TLS]
    end

    subgraph SE["🏭 Substation SCADA"]
        SCADA_SE[SCADA SE<br/>IEC 60870-5-104 · DNP3]
        IED[Protection IEDs<br/>IEC 61850 GOOSE]
    end

    subgraph Cloud["☁️ Cloud"]
        GCP[GCP Pub/Sub]
        PROM[Prometheus + Grafana]
        OT[Cloud Trace]
    end

    subgraph Market["📈 Market"]
        CMG[CEN Chile CMg API<br/>Real-time spot price]
    end

    BAT -->|CAN/RS485| GW
    INV -->|Modbus TCP| DRV
    TRF & MT & PROT -->|IEC 61850 GOOSE| IED
    IED --> SCADA_SE
    GW --> FW
    FW --> EMS
    EMS --> DRV
    DRV --> SG
    SG --> AI
    CMG -->|30-day history| EVO
    AI --> TEL
    SCADA_SE -->|IEC 60870-5-104| TEL
    TEL --> GCP
    TEL --> PROM
    TEL --> OT
    UPS -.->|Powers| GW & FW & EMS
```

---

## 📊 Data Flow

```mermaid
sequenceDiagram
    participant HW as BESS Hardware
    participant DRV as Driver
    participant SG as SafetyGuard
    participant DRL as DRL Agent (ONNX)
    participant MKT as CMg Market
    participant PUB as Publishers

    HW->>DRV: Poll telemetry (5s)
    DRV->>SG: BatteryState {soc, temp, power}
    SG-->>DRL: ✅ Safe to dispatch
    MKT-->>DRL: CMg price forecast
    DRL->>SG: Proposed setpoint p_pu ∈ [-1, 1]
    SG->>SG: Validate SOC bounds + thermal limits
    alt safe
        SG->>HW: Write power setpoint
    else violation
        SG->>HW: Hold (0 kW)
        SG->>PUB: safety_violation alert
    end
    SG->>PUB: Telemetry + metrics
    PUB->>PUB: Prometheus / GCP / MQTT / OTel
```

---

## 🔌 Hardware Registry

```mermaid
graph LR
    subgraph Inverters
        HW[Huawei SUN2000<br/>✅ Production]
        SMA[SMA Sunny Tripower<br/>✅ Tested]
        VIC[Victron MultiPlus<br/>✅ Tested]
        FRO[Fronius Symo<br/>✅ Tested]
        SE[SolarEdge StorEdge<br/>✅ Tested]
    end
    subgraph Batteries
        BYD[BYD Battery Box<br/>✅ Tested]
        TES[Tesla Powerwall<br/>✅ Tested]
    end
    subgraph Pending["🔵 Roadmap (BEP-0202)"]
        ABB[ABB PCS100]
        SCH[Schneider Conext]
        GE[GE Grid Solutions]
    end
    DRIV[BESSAI Protocol Drivers]
    HW & SMA & VIC & FRO & SE & BYD & TES -->|Modbus TCP| DRIV
```

---

## 📸 Visuals

> **Note to contributors:** the screenshots/GIFs below are placeholders. We welcome PRs that add real captures.  
> See [docs/CONTRIBUTING_MEDIA.md](docs/CONTRIBUTING_MEDIA.md) for recording guidelines.

| # | What to capture | Tool | Priority |
|---|---|---|---|
| 1 | `docker compose up` boot sequence — all services healthy | asciinema | 🔴 High |
| 2 | Grafana dashboard: SOC curve + CMg price overlay | Screen recording → GIF | 🔴 High |
| 3 | `make simulate` running with live telemetry output | asciinema | 🟡 Medium |
| 4 | BESSAIEvolve GitHub Actions run + auto-PR creation | Screenshot | 🟡 Medium |
| 5 | Raspberry Pi 4 running BESSAI (`htop` + `make health`) | Photo + terminal | 🟢 Nice |
| 6 | IEEE 2030.5 DERControl endpoint responding to curl | asciinema | 🟢 Nice |

---

## 🤝 Para Early Adopters

> ¿Quieres desplegar BESSAI en una instalación real?

| Quiero... | Recurso |
|-----------|---------|
| 🗺️ Elegir mi camino de adopción | [**ADOPTER_HUB.md**](docs/ADOPTER_HUB.md) |
| ⚡ Demo en 5 min (sin hardware) | [tutorials/quickstart_5min.md](docs/tutorials/quickstart_5min.md) |
| 📅 Roadmap Día 0 → Producción | [ONBOARDING_7DAYS.md](docs/ONBOARDING_7DAYS.md) |
| ❓ FAQ técnica (hw, mercados, licencia) | [FAQ.md](docs/FAQ.md) |
| 🛡️ Programa Early Adopters (soporte prioritario) | [early_adopters.md](docs/early_adopters.md) |
| 🆘 Soporte durante el onboarding | [Abrir issue](https://github.com/bess-solutions/open-bess-edge/issues/new?template=adopter_support.yml) |

---

## ⚡ Quick Start

### 0. Setup interactivo (recomendado)

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
bash scripts/setup.sh   # 5 preguntas → genera config/.env listo
```

### 1. Local (Python)

```bash
make dev                  # instala dependencias + pre-commit hooks
bash scripts/setup.sh     # genera config/.env
make simulate             # arranca con simulador integrado
make health               # verifica que todo está activo
```

### 2. Docker Compose (recommended)

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
bash scripts/setup.sh     # genera config/.env con parámetros de tu sitio
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring up -d
```

Grafana → http://localhost:3000 (credenciales: ver `GF_SECURITY_ADMIN_PASSWORD` en `config/.env`)  
Metrics → http://localhost:8000/metrics  
Health  → http://localhost:8000/health

### 3. Raspberry Pi 4 / 5

```bash
# On the Pi (arm64):
docker pull ghcr.io/bess-solutions/open-bess-edge:latest
docker run -d \
  --name bessai \
  --env-file .env \
  -p 8000:8000 \
  ghcr.io/bess-solutions/open-bess-edge:latest
```

> Full Raspberry Pi guide: [docs/quickstart_rpi.md](docs/quickstart_rpi.md)

### 4. Dev Container (VS Code / GitHub Codespaces)

Open in VS Code → **Reopen in Container** — all dependencies, pre-commit hooks, and the simulator start automatically.

---

## ✨ Features

| Feature | Description | BEP |
|---|---|---|
| **Multi-protocol drivers** | Modbus TCP, IEC 61850, IEEE 2030.5 / SEP 2.0 | BEP-0100 |
| **Hardware profiles** | 7 certified profiles (Huawei, SMA, Victron, BYD, Tesla…) | – |
| **SafetyGuard** | SOC/thermal/power bounds — blocks unsafe commands | – |
| **AI-IDS** | Real-time anomaly detection (IsolationForest + z-score) | – |
| **DRL Arbitrage Agent** | PPO + 8 CEN ONNX models — <0.1ms, no cloud required | BEP-0200 |
| **BESSAIEvolve** | AlphaEvolve-inspired weekly self-improvement loop | BEP-0303 |
| **VPP Fleet Manager** | Multi-site VPP: FleetOrchestrator + DRL per-site | BEP-0500 |
| **SENMarketFeed** | Live CEN prices: DuckDB → HTTP → Duck Curve fallback (TTL 15min) | BEP-0500 |
| **FL Coordinator** | Federated Learning FedAvg (capacity-weighted), L2 convergence | BEP-0600 |
| **HVDC Scheduler** | Inter-regional DC power flow arbitrage (500MW, 1.8% losses) | BEP-0700 |
| **CMg Live Feed** | Real-time Chilean SEN spot price ingestion | BEP-0302 |
| **Fleet P99 SLAs** | Locust Load Testing SLA guard rails (<100ms latency) | – |
| **Tier-1 Operability** | Prometheus Alerts (`HighFleetLatency`, `LowCarbon`) & K8s HPA auto-scaling | – |
| **OpenTelemetry** | Distributed traces + metrics to GCP / Datadog / Grafana | – |
| **Global Market Adapters** | CAISO · ERCOT · ENTSO-E · SEN · COES · XM · CENACE | – |
| **Multi-arch Docker** | amd64 + arm64 (Raspberry Pi 4/5 native) | – |
| **IEC 62443 SL-1/2** | Full control mapping — SL-2 compliant | – |
| **IEC 62443 SL-3** | Aspiracional — zero-trust OT + HSM + SOC 24/7 | Roadmap v3.x |
| **DNP3** | Telecontrol a subestación y CEN | `DNP3Driver` |
| **IEC 60870-5-104** | SCADA SE telecontrol (CEN/CDEC Chile) | `IEC104Driver` |
| **IEEE 1547-2018 (IBR/GFM)** | Grid-Forming + anti-island + LVRT/HVRT | `FrequencyResponseAgent` |
| **Telemetry — Degradation Profile** | SOC/SOH + V/I per rack + BMS mode + cycles + C-rate history | `TelemetryPublisher` |

---

## 🛡️ Compliance

| Standard | Status | Evidence |
|---|---|---|
| IEC 62443 SL-1 | ✅ Compliant | [iec62443_mapping.md](docs/compliance/iec62443_mapping.md) |
| IEC 62443 SL-2 | ✅ Compliant | `SL2SecurityGate` — RBAC + HMAC-SHA256 |
| NTSyCS Cap. 4.2 | ✅ GAP-001 | Ramp rate ≤10%/min (`SafetyGuard`) |
| NTSyCS Cap. 4.3 | ✅ GAP-002 | PFR droop < 2s (`FrequencyResponseAgent`) |
| NTSyCS Cap. 4.4 | ✅ GAP-011 | Q/V droop (`ReactiveController`) |
| NTSyCS Cap. 6.1 | ✅ GAP-003 | mTLS telemetría CEN (`CENPublisher`) |
| NTSyCS Cap. 6.2 | ✅ GAP-004 | SCADA IEC 60870-5-104 (`IEC104Driver`) |
| NTCSE | ✅ GAP-010 | THD/Flicker gate (`PowerQualityMonitor`) |
| Decreto 88/2023 | ✅ GAP-007 | Anti-arbitrage PMGD (`PMGDComplianceEngine`) |
| Ley 21.185 | ✅ GAP-008 | CER para CNE (`ERNCRegistry`) |
| Ley 21.663/2024 | ✅ | CSIRT ≤3h (`SecurityNotifier`) |
| IEEE 2030.5 / SEP 2.0 | ✅ 10 endpoints | [BEP-0100](docs/bep/BEP-0100.md) |
| Apache 2.0 SPDX | ✅ All source files | [LICENSE](LICENSE) |

---

## 📐 Open BESS Edge Standard v1.0

This gateway implements the **Open BESS Edge Standard** — a Chilean-context architecture specification for secure, interoperable BESS deployments.

### System Components (Full Stack)

| Layer | Components | Voltage Level |
|---|---|---|
| **Storage** | Battery racks + modular BMS | BT < 1,000 V AC / < 1,500 V DC |
| **Conversion** | Bidirectional PCS/Inverters | BT → MT |
| **Transformation** | Step-up power transformer | BT/MT → MT |
| **MT Interface** | MT switchgear & cells | 1 kV – 36 kV |
| **Protection** | Protection relays at ALL interfaces | Per NCh / IEC |
| **Plant SCADA** | Local BESS control & supervision | OT isolated network |
| **Substation SCADA** | Integration with SE SCADA | OT/IT via DMZ |
| **IoT Gateway** | Edge compute: Modbus→MQTT/OPC-UA, local preprocessing | — |
| **Industrial Firewall + DMZ** | OT/IT segmentation, DPI, allowlist rules | — |
| **Local EMS/DERMS** | Autonomous 24-48h operation, Grid-Forming mode | — |
| **Control UPS** | Emergency power for all control & security systems | — |

### Protocol Stack

| Protocol | Layer | Mandatory |
|---|---|---|
| Modbus TCP/RTU | Field Level (BMS ↔ PCS ↔ SCADA) | ✅ |
| IEC 61850 (GOOSE + MMS) | Station Level (protection IEDs, SE) | ✅ |
| DNP3 | SCADA Level (utility requirement) | ✅ |
| IEC 60870-5-104 | Telecontrol (SCADA SE / CEN-CDEC) | ✅ |
| MQTT v5 + TLS 1.3 | Cloud / API telemetry | ⭐ Recommended |
| OPC-UA | IT/OT convergence, multi-vendor | ⭐ Recommended |

### IEC 62443 Security Levels — Roadmap

```
SL-3 ◀ Aspirational (2027+) — APT resistance, HSM, SOC 24/7
SL-2 ◀ Operational target (2026) — MFA, TLS, IDS/IPS, patch mgmt
SL-1 ◀ Commissioning minimum (current) — Passwords, segmentation, logs
```

### Regulatory Framework (Chile)

- **NTSCS** (CNE) — mandatory regulatory floor for SEN connection
- **IEEE 1547-2018** — technical standard for IBR/GFM interconnection
- **IEC 61850** — communication vocabulary (logical nodes: ZBAT, MMXU, PTOC, PFRC)

> 📄 Full specification: [Open BESS Edge Standard v1.0](docs/standards/open_bess_edge_standard_v1.md)

---

## 🗺️ Roadmap

| Status | What | Version |
|---|---|---|
| ✅ Done | IEC 62443 SL-1/2 · OpenSSF · BEPs 0100–0303 · BESSAIEvolve v1 | v2.10.0–v2.12.0 |
| ✅ Done | **8 CEN DRL ONNX models** · PPO trainer · Global Market Adapters (CAISO, ERCOT, ENTSO-E) | v2.14.0 |
| ✅ Done | **VPP Fleet Manager (BEP-0500)** · SENMarketFeed CEN live · Multi-site ONNX DRL dispatch | v2.15.0 |
| ✅ Done | **FL Coordinator (BEP-0600)** · FedAvg capacity-weighted · L2 convergence · 799 CI tests | v2.16.0 |
| ✅ Done | **HVDC Scheduler (BEP-0700)** · DC power flow · 500MW · inter-regional price arbitrage | v2.16.0 |
| ✅ Done | **Tier-1 Observability** · Prometheus Alerts (HighFleetLatency/Carbon) · K8s HPA | **v2.17.1** |
| 🔵 Planned | Flower (flwr) integration for FL · gRPC + mTLS FL protocol | v2.18.0 |
| 🔵 Planned | P2P Energy Trading · LCA Engine · Carbon Dashboard | 2027 |

See full roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)

---

## 🧬 BESSAIEvolve — Self-Improving AI

BESSAI autonomously improves its arbitrage policy every week using an evolutionary algorithm inspired by **AlphaEvolve (DeepMind, 2025)**:

```
Every Monday 00:00 UTC:
  1. Fetch 30 days of real CMg price data (CEN Chile API)
  2. Generate 10 policy candidates (Gaussian mutation)
  3. Evaluate each in a 8,640-step sandbox (30 days × 288 timesteps)
  4. Select parents via tournament → produce next generation
  5. Repeat for 5 generations → if best > +5% + 0 safety violations
  6. Open a PR automatically for human approval
```

→ Full explanation: [docs/BESSAI_EVOLVE.md](docs/BESSAI_EVOLVE.md) · Spec: [BEP-0303](docs/bep/BEP-0303.md)

---

## 📦 Project Structure

```
open-bess-edge/                      ← PUBLIC (Apache 2.0)
├── src/core/
│   ├── safety_guard.py          # IEC 62443 SL-1/2 SOC/thermal guardrail
│   ├── compliance_stack.py      # 11 GAPs NTSyCS
│   ├── vpp_fleet_manager.py     # BEP-0500: VPP multi-site + ONNX DRL dispatch
│   ├── sen_market_feed.py       # BEP-0500 P2: CEN live price (DuckDB → duck-curve)
│   ├── fl_coordinator.py        # BEP-0600: Federated Learning FedAvg coordinator
│   ├── hvdc_scheduler.py        # BEP-0700: HVDC inter-regional DC power flow
│   ├── market_adapter.py        # 7 global markets (SEN, CAISO, ERCOT, ENTSO-E…)
│   └── ...                      # SafetyGuard, AI-IDS, BESSAIEvolve, XAI…
├── tests/               # 799 tests (pytest) · 0 failures · CI/CD
├── docs/bep/            # BEP-0001 → BEP-0700 (10 proposals)
├── docs/compliance/     # IEC 62443, NTSyCS, IEEE 2030.5
├── .github/workflows/   # CI/CD + weekly BESSAIEvolve
├── infrastructure/      # Terraform GCP (18 resources)
└── CHANGELOG.md

bess-solutions/bessai-core           ← PRIVATE (Proprietary)
├── src/agents/          # 16 AI modules (MARL, MILP, DRL, evolution)
├── src/interfaces/      # fl_client.py, fl_server.py (Federated Learning)
└── models/              # dispatch_policy.onnx (trained PPO)
```

---

## 🤝 Contributing

Contributions are welcome. BESSAI follows the [BEP process](docs/bep/BEP-0001.md) for significant changes.

```bash
git checkout -b feature/my-feature
make test           # must pass before PR
make lint           # ruff + mypy + bandit
git commit -m "feat(scope): clear description"
gh pr create
```

- **Good First Issues** → [docs/GOOD_FIRST_ISSUES.md](docs/GOOD_FIRST_ISSUES.md)
- **Hardware profile contribution** → [docs/tutorials/hardware_profile_contribution.md](docs/tutorials/hardware_profile_contribution.md)
- **Bug reports** → [GitHub Issues](https://github.com/bess-solutions/open-bess-edge/issues/new/choose)
- **Security vulnerabilities** → [SECURITY.md](SECURITY.md) (private disclosure)
- **Design discussions** → [GitHub Discussions](https://github.com/bess-solutions/open-bess-edge/discussions)

---

## 🌐 Community

| Channel | Purpose |
|---|---|
| [Discord](https://discord.gg/ZqpE8AZs) | Real-time chat, support, showcase |
| [GitHub Discussions](https://github.com/bess-solutions/open-bess-edge/discussions) | RFCs, design decisions, Q&A |
| [GitHub Issues](https://github.com/bess-solutions/open-bess-edge/issues) | Bugs and feature requests |

---

## 📄 License

Apache 2.0 — see [LICENSE](LICENSE).  
SPDX headers in all source files. Third-party attributions in [NOTICE](NOTICE).

---

<details>
<summary>🇨🇱 Versión en Español</summary>

## BESSAI Edge Gateway — Descripción en Español

**Gateway industrial de código abierto para gestión segura y optimizada de activos BESS.**

BESSAI es una plataforma de computación en el borde (edge) que conecta tu sistema de almacenamiento de energía (BESS) con la infraestructura cloud. Sus capacidades principales:

- **Drivers industriales**: Modbus TCP, IEC 61850, IEEE 2030.5 / SEP 2.0
- **IA en el borde**: Agente DRL (PPO) para arbitraje en el mercado spot chileno (CMg)
- **Auto-mejora**: BESSAIEvolve — bucle evolutivo semanal inspirado en AlphaEvolve (DeepMind)
- **Seguridad industria**: SafetyGuard compatible IEC 62443 SL-1 + NTSyCS CEN Chile
- **Observabilidad**: Prometheus, Grafana, OpenTelemetry, GCP Pub/Sub

**Despliegue de referencia:** BESS 200kWh / 100kW Huawei SUN2000, Santiago de Chile — en producción desde 2025.

### Inicio rápido

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
make dev
make simulate
```

### Documentación
- [Inicio rápido (5 min)](docs/tutorials/quickstart_5min.md)
- [Raspberry Pi 4/5](docs/quickstart_rpi.md)
- [BESSAIEvolve — IA que se mejora sola](docs/BESSAI_EVOLVE.md)
- [Cumplimiento IEC 62443](docs/compliance/iec62443_mapping.md)
- [Cumplimiento NTSyCS CEN Chile](docs/compliance/ntscys_compliance.md)

### Comunidad
- [Discord en español](https://discord.gg/ZqpE8AZs) — canal `#español`
- [Reportar un bug](https://github.com/bess-solutions/open-bess-edge/issues/new/choose)
- [Proponer mejora (BEP)](docs/bep/BEP-0001.md)

</details>
