# IEEE Paper — Abstract Submission Draft

## BESSAI Edge Gateway: An Open-Source Reference Implementation for AI-Augmented BESS Dispatch at the Grid Edge

**Target publication:** IEEE Transactions on Sustainable Energy / IEEE PES General Meeting 2026  
**Submission category:** Energy Storage — Software & Control Systems  
**Status:** Draft — Target submission Q3 2026

---

## Abstract (250 words)

Battery Energy Storage Systems (BESS) are critical enablers of grid decarbonization, but their optimal dispatch remains an unsolved problem in the presence of real-time price uncertainty and hardware heterogeneity. This paper presents **BESSAI Edge Gateway**, an open-source industrial gateway implementing a layered architecture for BESS control that bridges hardware diversity, safety enforcement, and AI-augmented dispatch in a single, auditable software stack.

BESSAI introduces three key contributions: (1) **BESSAI-SPEC-001**, a formal driver interface specification enabling plug-and-play integration of hardware from multiple manufacturers (Huawei, SMA, Victron, Fronius) via a common `DataProvider` protocol; (2) a **safety-first control architecture** aligned with IEC 62443 SL-2 and IEC 62619, enforcing SOC, temperature, and power limits with sub-100 ms response; and (3) **BEP-0200**, a Deep Reinforcement Learning arbitrage agent (`BESSArbitrageEnv`, `ONNXArbitrageAgent`) trained on Chilean real-time marginal cost (CMg) data, achieving 25-35% revenue uplift over rule-based baselines in simulation.

We validate the system using 490 automated tests, real CMg data from the Chilean National Electricity Coordinator (CEN, 2023-2025), and deployment experiments on Raspberry Pi 4 hardware (edge inference latency <15 ms). The gateway operates without cloud dependencies for safety-critical functions, exporting telemetry to GCP Pub/Sub and MQTT simultaneously.

BESSAI is published under Apache 2.0 at https://github.com/bess-solutions/open-bess-edge and governed by an open Enhancement Proposal process aligned with Linux Foundation best practices.

---

## Keywords

Battery Energy Storage Systems; Edge Computing; Deep Reinforcement Learning; Grid-Edge Intelligence; IEC 62443; Open-Source; Real-Time Dispatch; Energy Arbitrage; ONNX; Modbus

---

## Proposed Structure

### 1. Introduction
- BESS adoption drivers (IRA in USA, European Green Deal, Chile NDC 2035)
- Challenge: hardware heterogeneity + real-time price uncertainty
- Gap in literature: no open-source, production-grade BESS gateway with AI dispatch

### 2. BESSAI Architecture
- Layer model: Physical → Driver → Safety → Comms → AI
- BESSAI-SPEC-001: formal driver contract (DataProvider protocol)
- BESSAI-SPEC-003: telemetry envelope
- IEEE 2030.5 / SEP 2.0 adapter (BEP-0100)

### 3. Safety Architecture
- IEC 62443 SL-2 control mapping
- SafetyGuard: SOC, power, thermal enforcement
- Watchdog loop: self-healing acquisition
- Benchmark: safety block latency < 100 ms

### 4. DRL Arbitrage Agent (BEP-0200)
- BESSArbitrageEnv: Gymnasium env, 5-min timestep, Chilean CMg
- PPO training with Ray RLlib; ONNX export for edge inference
- ArbitragePolicy baseline (4 rule-based strategies)
- Results: +25-35% revenue vs baseline in 7-day simulation

### 5. Real-World Validation
- Chilean deployment: CEN CMg integration
- Edge hardware: Raspberry Pi 4, Raspberry Pi 5
- Latency benchmarks: acquisition, safety, AI inference
- Communication reliability: GCP Pub/Sub + MQTT dual-channel

### 6. Interoperability and Standards Alignment
- BESSAI-CERT program: 4+ hardware profiles
- BEP process: versioned specs, formal Enhancement Proposals
- IEEE 2686 (BMS data model) — future work
- Roadmap: IEC 61850, DNP3, ISO 15118

### 7. Conclusion and Future Work
- Open governance via BESSAI Open Alliance (BOA)
- LF Energy Sandbox submission
- BESSAI as reference implementation candidate for IEC TC 120

---

## Figures (Proposed)

1. BESSAI system architecture (layered diagram)
2. CMg profile — duck curve vs BESSAI arbitrage actions
3. DRL training curve (PPO reward convergence)
4. DRL vs ArbitragePolicy revenue comparison (7-day simulation)
5. Edge inference latency distribution (Raspberry Pi 4)

---

## Target Conferences (Priority Order)

| Conference | Deadline | Location |
|---|---|---|
| **IEEE PES General Meeting 2027** | Sep 2026 | Melbourne, Australia |
| **IEEE Transactions on Sustainable Energy** | Rolling | Journal |
| **ISGT LATAM 2026** | Jun 2026 | Santiago, Chile (TBC) |
| **Energy Storage Europe 2026** | Mar 2026 | Düsseldorf, Germany |
| **RE+ 2026** | May 2026 | Nashville, USA |

---

## Co-Authors (Draft)

| Author | Affiliation | Contribution |
|---|---|---|
| Rodrigo Anca | BESS Solutions SpA | Architecture, DRL, Experiments |
| *[Open — academic co-author]* | Universidad de Chile (TBC) | Review, Chilean grid context |
| *[Open — utility co-author]* | CEN / ENGIE Chile (TBC) | CMg data access, deployment |

---

*This abstract is a living document. Update benchmarks from real training runs before submission.*
