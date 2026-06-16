<div align="center">

# 🔋 BESSAI Edge Gateway

**Industrial-grade open-source edge gateway for secure, AI-optimized Battery Energy Storage System (BESS) management.**

*Self-evolving arbitrage intelligence · IEC 62443 SL-1→SL-3 · IEC 61850 · DNP3 · IEC 60870-5-104 · IEEE 1547-2018 IBR/GFM · NTSyCS Chile*

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/bess-solutions/open-bess-edge/actions/workflows/ci.yml/badge.svg)](https://github.com/bess-solutions/open-bess-edge/actions)
[![Docker](https://img.shields.io/badge/Docker-amd64%20%7C%20arm64-2496ED?logo=docker&logoColor=white)](https://ghcr.io/bess-solutions/open-bess-edge)
[![IEC 62443](https://img.shields.io/badge/IEC_62443-SL--1%2FSL--2%2FSL--3_Roadmap-orange)](docs/compliance/iec62443_mapping.md)
[![IEEE 1547](https://img.shields.io/badge/IEEE_1547--2018-IBR%2FGFM_Ready-green)](docs/compliance/ieee1547_mapping.md)
[![NTSyCS](https://img.shields.io/badge/NTSyCS-11_GAPs_Closed-brightgreen)](docs/compliance/ntscys_compliance.md)
[![Tests](https://img.shields.io/badge/tests-1227_passing-brightgreen)](tests/)
[![Version](https://img.shields.io/badge/version-v2.17.1-blue)](.)

[**Leer en Español 🇪🇸**](README.md) · [**Documentation**](https://bess-solutions.github.io/open-bess-edge) · [**Quick Start**](#-quick-start) · [**MCP Server**](docs/mcp_server.md) · [**BEP Proposals**](docs/bep/BEP-0001.md) · [**Roadmap**](#-roadmap)

</div>

---

## What is BESSAI Edge Gateway?

BESSAI is a production-ready edge computing platform that sits between your Battery Energy Storage System (BESS) hardware and cloud/SCADA infrastructure. It handles:

- **Real-time telemetry** collection from inverters and BMS (Modbus TCP, IEC 61850, DNP3, IEC 60870-5-104).
- **AI-powered dispatch** decisions via a Deep Reinforcement Learning (DRL) arbitrage agent (ONNX inference, no cloud connection required for local execution).
- **Autonomous self-improvement** via BESSAIEvolve — an evolutionary parameter search weekly cycle.
- **Safety enforcement** with IEC 62443 SL-1/SL-2 compliant guardrails (SafetyGuard).
- **Multi-cloud publishing** to GCP Pub/Sub, MQTT, and OpenTelemetry.
- **Full system architecture integration**: from BT battery racks, bidirectional inverters, step-up transformers, MT cells, protection relays, plant SCADA, substation SCADA, to industrial firewalls.

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

## 🔌 Model Context Protocol (MCP) Server

Open BESS Edge features a native Python-based **MCP Server** that exposes key operational tools to AI assistants (such as Claude Desktop or custom agents). This enables managing and querying BESS status in natural language with strict adherence to our Zero Mock Data Policy.

### Exposed Tools
* **`get_battery_health`**: Read real-time telemetry (SOC, voltage, active/reactive power, temperatures) over Modbus TCP.
* **`diagnose_faults`**: Inspect active alarms and status registers for fault-decoding.
* **`predict_rul`**: Forecast Remaining Useful Life (RUL) using Arrhenius thermal-stress kinetics over [training_dataset.parquet](data/training_dataset.parquet).
* **`cyber_hygiene_check`**: Audit host OS hardening parameters (SSH, TLS, rules).

### Claude Desktop Configuration
Add the server config to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "open-bess-edge": {
      "command": "python",
      "args": [
        "C:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge/mcp_server/server.py"
      ],
      "env": {
        "PYTHONPATH": "C:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/open-bess-edge"
      }
    }
  }
}
```

---

## ⚡ Quick Start

### 0. Interactive Setup (Recommended)

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
bash scripts/setup.sh   # interactive site config generation
```

### 1. Local (Python)

```bash
make dev                  # install dependencies + setup pre-commit hooks
bash scripts/setup.sh     # generate config/.env
make simulate             # run with integrated BESS simulator
make health               # verify all local components are active
```

### 2. Docker Compose (Recommended Deployment)

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
bash scripts/setup.sh     # generate config/.env
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring up -d
```

Grafana → http://localhost:3000 (Credentials: check `GF_SECURITY_ADMIN_PASSWORD` in `config/.env`)  
Metrics → http://localhost:8000/metrics  
Health  → http://localhost:8000/health

---

## ✨ Features

| Feature | Description | BEP |
|---|---|---|
| **Multi-protocol drivers** | Modbus TCP, IEC 61850, IEEE 2030.5 / SEP 2.0 | BEP-0100 |
| **Hardware profiles** | Certified profiles (Huawei, SMA, Victron, BYD, Tesla…) | – |
| **SafetyGuard** | SOC/thermal/power bounds — blocks unsafe commands | – |
| **AI-IDS** | Real-time anomaly detection (IsolationForest + z-score) | – |
| **DRL Arbitrage Agent** | PPO + 8 Chilean Node ONNX models — local execution | BEP-0200 |
| **BESSAIEvolve** | Parameter self-improvement weekly evolutionary cycle | BEP-0303 |
| **VPP Fleet Manager** | Multi-site Virtual Power Plant manager | BEP-0500 |
| **OpenTelemetry** | Distributed traces + metrics to GCP / Datadog / Grafana | – |
| **IEC 62443 SL-1/2** | Full cybersecurity control mapping — SL-2 compliant | – |
| **DNP3** | Utility / substation SCADA telecontrol driver | `DNP3Driver` |
| **IEC 60870-5-104** | Substation SCADA telecontrol for Chilean CEN | `IEC104Driver` |
| **IEEE 1547-2018 (IBR/GFM)** | Grid-Forming + anti-islanding + LVRT/HVRT | `FrequencyResponseAgent` |

---

## 🛡️ Compliance

| Standard | Status | Evidence |
|---|---|---|
| IEC 62443 SL-1 | ✅ Compliant | [iec62443_mapping.md](docs/compliance/iec62443_mapping.md) |
| IEC 62443 SL-2 | ✅ Compliant | `SL2SecurityGate` — RBAC + HMAC-SHA256 |
| NTSyCS Cap. 4.2 | ✅ GAP-001 | Ramp rate ≤10%/min (`SafetyGuard`) |
| NTSyCS Cap. 4.3 | ✅ GAP-002 | PFR droop < 2s (`FrequencyResponseAgent`) |
| NTSyCS Cap. 4.4 | ✅ GAP-011 | Q/V droop (`ReactiveController`) |
| NTSyCS Cap. 6.1 | ✅ GAP-003 | mTLS telemetry to CEN (`CENPublisher`) |
| NTSyCS Cap. 6.2 | ✅ GAP-004 | SCADA IEC 60870-5-104 (`IEC104Driver`) |
| Decreto 88/2023 | ✅ GAP-007 | Anti-arbitrage PMGD (`PMGDComplianceEngine`) |
| Ley 21.663/2024 | ✅ | Cyber incident notification CSIRT ≤3h (`SecurityNotifier`) |
| IEEE 2030.5 / SEP 2.0 | ✅ 10 endpoints | [BEP-0100](docs/bep/BEP-0100.md) |
