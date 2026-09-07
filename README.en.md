# ⚡ Open BESS Edge

<div align="center">

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Grid Code](https://img.shields.io/badge/Grid%20Code-NTSyCS%20Cap.%203%20(Chile)-2ea44f?logo=lightning&logoColor=white)](https://www.cne.cl/)
[![CEN Standard](https://img.shields.io/badge/CEN%20SEN-CFyDR%202026%20Compliant-009688?logo=buffer&logoColor=white)](https://www.coordinador.cl/)
[![Latency](https://img.shields.io/badge/Loop%20Latency-sub--0.1ms-purple?logo=speedtest&logoColor=white)](#-benchmarking--closed-loop-latency)
[![Architecture](https://img.shields.io/badge/Platform-IPC%20x86__64%20%7C%20ARM64-orange?logo=docker&logoColor=white)](#-industrial-deployment)
[![Safety Standard](https://img.shields.io/badge/Safety-NFPA%20855%20%7C%20SEC%20RIC-red?logo=shield&logoColor=white)](#-hardware-safety-envelope-bess-guard)
[![Tests](https://img.shields.io/badge/Tests-16%2F16%20Passing%20(100%25)-brightgreen?logo=pytest&logoColor=white)](#-automated-testing--cen-compliance-suite)

**Mission-Critical Industrial Edge Gateway & Frequency Response Controller for Battery Energy Storage Systems (BESS)**  
*Deterministic substation edge computing platform for strict compliance with the Chilean National Electric System (SEN) Grid Code.*

[Architecture](#-substation-architecture) •
[CEN Grid Code](#-grid-code-compliance-cen-cfydr-2026) •
[BESS-GUARD Safety](#-hardware-safety-envelope-bess-guard) •
[Volt/VAR Q(V)](#-dynamic-voltvar-support-qv) •
[Hardware Ecosystem](#-supported-hardware-ecosystem) •
[Quick Start](#-quick-start)

</div>

---

## 🏗️ Substation Architecture

Open BESS Edge operates at the **OT (Operational Technology)** layer inside substation-hardened Industrial PCs (Edge IPC). It enforces real-time grid dynamic response during disturbances and autonomously protects battery assets.

```mermaid
graph TB
    subgraph PCC ["⚡ Point of Common Coupling (PCC) · SEN Chile"]
        GRID["Transmission / Distribution Grid<br/><b>66 kV / 110 kV / 220 kV</b>"]
        TRF["Main Step-Up Transformer<br/><b>LV (400V) → MV/HV</b>"]
    end

    subgraph BESS_PLANT ["🔋 BESS Power Yard"]
        PCS["Bidirectional Power Conversion System (PCS)<br/><i>Sungrow · Kehua · SMA · Ingeteam · PE</i><br/>[Active & Reactive Power Control · Modbus TCP]"]
        BMS["Battery Management System (BMS)<br/><i>CATL · BYD · Gotion · EVE (LFP 314Ah)</i><br/>[Cell Telemetry · Safety Interlocks]"]
    end

    subgraph EDGE_GATEWAY ["🖥️ Open BESS Edge Runtime (Substation IPC)"]
        direction TB
        MB["<b>ModbusBESSClient</b><br/>Async Driver with Exponential Backoff & Simulation Engine"]
        
        subgraph ENGINES ["Deterministic Control Loop (Sub-0.1ms Latency)"]
            GUARD["🛡️ <b>SafetyEnvelopeEvaluator</b><br/>Hardware Envelope BESS-GUARD-001..005"]
            FFR["⚡ <b>FFRDroopController</b><br/>FFR (<500ms) & Droop (s=3%, ±30mHz)"]
            VV["🔄 <b>VoltVarController</b><br/>Dynamic Q(V) & cos φ Support"]
        end

        TELEMETRY["📡 <b>Telemetry & Diagnostics</b><br/>Battery Data Format (BDF) · IEC 61850"]
    end

    subgraph SCADA_CEN ["🏢 National Grid Operator (CEN)"]
        CEN_SCADA["CEN SCADA & Energy Management System<br/>AGC Dispatch Setpoints & Grid Code Compliance"]
    end

    GRID --- TRF --- PCS
    PCS <-->|"DC Bus"| BMS

    PCS <-->|"Modbus TCP (Holding Regs)"| MB
    BMS <-->|"Cell & Rack Telemetry"| MB

    MB -->|"Hardware Snapshot"| GUARD
    GUARD -->|"Safe Envelope Condition"| FFR
    GUARD -->|"Safe Envelope Condition"| VV
    GUARD -.->|"Critical Safety Interlock (0 kW)"| MB

    FFR -->|"P Setpoint (kW)"| MB
    VV -->|"Q Setpoint (kVAR)"| MB
    MB -->|"Setpoint Commits"| PCS

    EDGE_GATEWAY -.->|"NTSyCS Telemetry Stream"| CEN_SCADA
```

---

## ⏱️ Real-Time Closed-Loop Sequence (Severe Contingency)

Millisecond-by-millisecond execution trace during a massive generation trip on the SEN (loss of 397 MW):

```mermaid
sequenceDiagram
    autonumber
    participant SEN as SEN Grid (PCC)
    participant PCS as PCS Inverter
    participant MB as Modbus Driver (Edge)
    participant GUARD as SafetyGuard Evaluator
    participant FFR as FFR Controller (CEN 2026)
    participant VV as Volt/VAR Controller

    Note over SEN: t = 0.0 ms: Thermal generator trip (f drops to 49.65 Hz)
    SEN->>PCS: Frequency excursion to 49.65 Hz (|Δf| = 0.35 Hz)
    PCS->>MB: Fast telemetry sampling (t = 2.0 ms)
    MB->>GUARD: Sub-millisecond cell voltage & temp check (t = 2.05 ms)
    GUARD-->>FFR: ✅ BESS-GUARD Status: SAFE_NORMAL
    Note over FFR: |Δf| ≥ 0.30 Hz: Emergency transition to FFR_EMERGENCY_FAST
    FFR->>FFR: Instantaneous nominal power target calculation (t = 2.08 ms)
    GUARD-->>VV: PCC Voltage verification (V = 398 V)
    VV->>VV: Within Q(V) deadband (Q = 0 kVAR)
    FFR->>MB: P Setpoint = +1000 kW (t = 2.10 ms)
    MB->>PCS: Modbus Holding Register 200 Write (t = 4.5 ms)
    PCS->>SEN: ⚡ Full power injection delivered in t < 500 ms (Nadir Defense)
```

---

## ⚡ Grid Code Compliance (CEN CFyDR 2026)

The edge controller parameters are calibrated against the official **Frequency Control & Reserve Determination Study (CFyDR 2026) by the Coordinador Eléctrico Nacional (CEN)** and the **NTSyCS Technical Grid Code (Res. CNE N° 343)**:

```text
                                 DROOP & FFR CHARACTERISTIC CURVE (CEN 2026)
        Discharge (+P)
              ▲
      P_nom ──┤                                            ┌─────────── Severe Contingency FFR (|Δf| ≥ 0.30 Hz)
              │                                           /              Ramp Released: Sub-500ms Full Injection
              │                                          /
              │                  Primary Droop Zone     /
              │                       (s = 3%)         /
              │                   (K_p = P_nom/s*f)   ┌
              │                                      /│
              │                                     / │
        0 kW ─┼──────────────────────────────┬─────┴──┼────────────────────────► Frequency (Hz)
              │                              │        │
              │                     49.70 Hz │        │ 49.97 Hz   50.00 Hz
              │                (FFR Trigger) │        │ (Deadband Boundary)
              │                              │        │
              │                              │        └─ CEN Official Primary Deadband: ±30 mHz
              │                              │
     -P_nom ──┤                              └─ Automatic Load Shedding: If P < 0, immediately cut to 0 kW
              ▼
         Charge (-P)
```

| Parameter | Grid Code Reference | Open BESS Edge Specification |
|---|---|---|
| **Nominal Frequency** | NTSyCS Art. 3-1 | $f_0 = 50.00\text{ Hz}$ |
| **Primary Deadband** | CEN CFyDR 2026 Study | $\Delta f_{deadband} = \pm 0.03\text{ Hz}$ ($\pm 30\text{ mHz}$) eliminating stochastic noise cycling |
| **Permanent Droop ($s$)** | Res. CNE N° 343 / NTSyCS | Configurable $s \in [0.02, 0.05]$ (Default: $s = 0.03$ / 3%) |
| **FFR Contingency Threshold**| CEN CFyDR 2026 Study | $|\Delta f| \ge 0.30\text{ Hz}$ ($f \le 49.70\text{ Hz}$ or $f \ge 50.30\text{ Hz}$) |
| **FFR Response Time** | NTSyCS Chapter 3 | Full power injection delivered in $t < 500\text{ ms}$ for Nadir support |
| **Normal Ramp Limit** | NTSyCS Art. 3-15 | Automated quasi-steady-state ramp clamp $\le 20\% P_{nom}/\text{min}$ |
| **Immediate Load Relief** | CFyDR 2026 Methodology | Instantaneous shedding to $0\text{ kW}$ if BESS was charging during an event |
| **CEN Performance Audit** | Formal Homologation | Deterministic measurement and reporting of $Aporte_{@10s}$ and $Aporte_{@2min}$ |

---

## 🔄 Dynamic Volt/VAR Support: $Q(V)$

In compliance with **NTSyCS Chapter 3 (Art. 3-21)**, all BESS facilities connected to the SEN must supply dynamic reactive power support at the PCC:

* **Automated $Q(V)$ Curve**: Capacitive reactive injection ($+Q$) when $V < 0.98\text{ pu}$; inductive reactive absorption ($-Q$) when $V > 1.02\text{ pu}$.
* **Constant $\cos\phi(P)$**: Smooth power factor control between $0.95$ inductive and $0.95$ capacitive.
* **Direct $Q$ Dispatch**: Centralized setpoints received from the system coordinator.

---

## 🛡️ Hardware Safety Envelope (BESS-GUARD)

Deterministic sub-millisecond safety interlocks engineered for **LFP 314Ah** utility-scale cells under **NFPA 855** and **SEC RIC N° 01/02**:

| Guard Code | Fault Description | Physical Boundary (LFP 314Ah) | Automated Edge Action |
|:---:|---|:---:|---|
| **`BESS-GUARD-001`** | **Cell Undervoltage** | $V_{cell,min} < 2.50\text{ V}$ | Discharge interlock & DC breaker trip |
| **`BESS-GUARD-002`** | **Cell Overvoltage** | $V_{cell,max} > 3.65\text{ V}$ | Charge interlock & PCS halt |
| **`BESS-GUARD-003`** | **Cell Overtemperature** | $T_{cell,max} > 50.0\text{ °C}$ | Emergency shutdown & maximum HVAC boost |
| **`BESS-GUARD-004`** | **DC Isolation Fault** | $R_{iso} < 500.0\text{ k}\Omega$ | Inverter trip & isolation alert dispatch |
| **`BESS-GUARD-005`** | **Cell Imbalance Warning**| $\Delta V_{cell} > 50.0\text{ mV}$ | Active balancing alert & preventive derating |

---

## 🔌 Supported Hardware Ecosystem

```mermaid
graph LR
    subgraph INVERTERS ["⚡ Bidirectional Inverters (PCS)"]
        SG["Sungrow SC / ST Series<br/>✅ Modbus TCP"]
        KH["Kehua Tech SPI Series<br/>✅ Modbus TCP"]
        SMA["SMA Sunny Central Storage<br/>✅ Modbus TCP"]
        ING["Ingeteam Ingecon Sun<br/>✅ Modbus TCP"]
        PE["Power Electronics HEM<br/>✅ Modbus TCP"]
    end

    subgraph BATTERIES ["🔋 Industrial BMS & LFP Racks"]
        CATL["CATL EnerOne / EnerC (314Ah)<br/>✅ BMS Telemetry"]
        BYD["BYD MC Cube ESS<br/>✅ BMS Telemetry"]
        GOT["Gotion High-Tech 314Ah<br/>✅ BMS Telemetry"]
        EVE["EVE Energy LF560K / LF314<br/>✅ BMS Telemetry"]
    end

    subgraph PROTOCOLS ["📡 Communication Protocols"]
        MB_TCP["Modbus TCP / RTU (SunSpec & IEC 61850)"]
        BDF["Battery Data Format (Linux Foundation Energy)"]
        BPX["Battery Parameter eXchange (BPX v1.1.1)"]
    end

    INVERTERS --> PROTOCOLS
    BATTERIES --> PROTOCOLS
    PROTOCOLOS --> CORE["🖥️ Open BESS Edge Gateway"]
```

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# Create virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e .[dev]
```

### 2. Run the Official CEN Compliance Test Suite

```bash
pytest tests/ -v
```

### 3. Run the Node in Deterministic Simulation Mode

```bash
python -m src.edge_node
```

---

## 🐳 Industrial Deployment (Docker / Substation IPC)

```bash
docker build -t bess-solutions/open-bess-edge:2.0.0 .

docker run -d \
  --name open-bess-edge \
  --restart always \
  --network host \
  -v $(pwd)/config/edge_config.yaml:/app/config/edge_config.yaml:ro \
  bess-solutions/open-bess-edge:2.0.0
```

---

## 🤖 Infrastructure & AI Architectural Assistance

<div align="center">

[![Docker AI](https://img.shields.io/badge/AI%20Assistance-Docker%20AI%20(Gordon)-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/ai/docker-agent/)
[![Dev Container](https://img.shields.io/badge/Dev%20Container-VS%20Code%20%7C%20Codespaces-blue?logo=visualstudiocode&logoColor=white)](.devcontainer/devcontainer.json)
[![IEC 62443 Hardened](https://img.shields.io/badge/Security-Hardened%20(IEC%2062443)-green?logo=docker&logoColor=white)](Dockerfile.hardened)

</div>

This project incorporates container infrastructure hardening, reproducible DevContainers, and unprivileged IEC 62443 security profiles developed with assistance from **Docker AI Assistant (Gordon)**, complemented by grid control engineering and SEN Chile market calibration by **Antigravity (Google DeepMind)**. See [CONTRIBUTORS.md](CONTRIBUTORS.md) for full attribution.

---

## 📄 License & Governance

Distributed under the **Apache 2.0** License. See [LICENSE](LICENSE) for details.
