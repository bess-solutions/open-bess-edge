# Regulatory Compliance Matrix (Chile SEN & International Standards)

Cross-reference matrix linking Chilean National Electric System (SEN) grid codes and international standards to their concrete technical implementations within **Open BESS Edge**.

---

## 1. NTSyCS (Technical Norm for Service Security and Quality) — CNE / CEN Chile

| NTSyCS Clause | Regulatory Requirement | Open BESS Edge Implementation | Verification Mechanism |
|:---|:---|:---|:---|
| **Cap. 3 & 4 — Frequency Control** | Fast Frequency Response (FFR) and Primary Frequency Control (droop $s=3\%$, deadband $\pm 30\text{ mHz}$). | [`open_bess_edge.control.ffr_droop`](file:///c:/Users/rodri/Desktop/open-bess-edge/src/open_bess_edge/control/ffr_droop.py): Proportional droop calculation with deadband filter and ramp limiter. | 278-test automated suite (`tests/test_ffr.py`) with simulated frequency steps under real loopback TCP sockets. |
| **Cap. 4 — Voltage & Reactive Control** | Dynamic reactive power injection and absorption $Q(V)$ for local voltage support. | [`open_bess_edge.control.volt_var`](file:///c:/Users/rodri/Desktop/open-bess-edge/src/open_bess_edge/control/volt_var.py) and [`limiter`](file:///c:/Users/rodri/Desktop/open-bess-edge/src/open_bess_edge/control/limiter.py): Circular capability curve and Volt/VAR slope limiter. | Automated unit tests (`tests/test_volt_var_limiter.py`) verifying P-Q priority envelopes. |
| **Cap. 6.1 — Telemetry to CEN** | Real-time telemetry reporting for active power, reactive power, voltages, and battery state. | [`open_bess_edge.runtime.audit`](file:///c:/Users/rodri/Desktop/open-bess-edge/src/open_bess_edge/runtime/audit.py) & Modbus telemetry engine. | Loopback audit logging and telemetry parsing verification. |
| **Response Time Budget** | FFR execution budget under 500 ms from event inception to setpoint dispatch. | Monotonic clock scheduling with 100 ms loop cycle (`runtime.cycle_ms`). | Real-time loopback latency tests (`tests/test_latency_realtime.py`) validating p99 execution. |

---

## 2. Superintendencia de Electricidad y Combustibles (SEC) — RIC & RGR

| SEC Standard / Article | Regulatory Safety Requirement | Open BESS Edge Implementation | Verification Mechanism |
|:---|:---|:---|:---|
| **RIC N° 01/02 — Communications** | Fail-safe behavior upon communication dropouts or signal staleness. | `BESS-GUARD-090` and `BESS-GUARD-091` in [`open_bess_edge.safety.envelope`](file:///c:/Users/rodri/Desktop/open-bess-edge/src/open_bess_edge/safety/envelope.py): Forces zero kW output if telemetry is stale. | Fault-injection tests (`tests/test_node.py`) simulating communication timeouts. |
| **RGR Safety Envelope** | Electrical, thermal, and DC insulation boundaries for stationary batteries. | 12 active deterministic safety guards (`BESS-GUARD-001` through `010`) covering cell voltages, temperatures, string limits, and insulation resistance. | Comprehensive boundary testing (`tests/test_safety.py`). |
| **Event Traceability** | Tamper-evident logging of abnormal alarms and safety trips. | Append-only JSONL audit trail with cryptographic hash chaining in `audit.py`. | CLI verification tool (`open-bess-edge verify-audit`). |

---

## 3. IEEE 1547-2018 (Interconnection of Distributed Energy Resources)

| IEEE 1547 Clause | Grid Support Requirement | Open BESS Edge Implementation | Verification Mechanism |
|:---|:---|:---|:---|
| **Section 5.4 — Frequency-Watt** | Active power modulation as a function of grid overfrequency and underfrequency. | Continuous droop controller in `open_bess_edge.control.ffr_droop`. | Parameter sweep tests under varying droop slopes. |
| **Section 5.3 — Voltage Regulation** | Volt-Reactive power mode and reactive power capability. | Volt/VAR piece-wise linear curve limiter in `open_bess_edge.control.volt_var`. | Automated P-Q circular envelope clipping tests. |
