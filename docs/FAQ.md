# Open BESS Edge — Frequently Asked Questions (FAQ)

> Direct, technical answers regarding architecture, compliance, and industrial deployment of Open BESS Edge v3.

---

## Hardware Integration & Compatibility

### Which inverters and BMS controllers are supported?

Open BESS Edge utilizes vendor-agnostic JSON profile maps in the [`registry/`](../registry/) directory to translate physical Modbus TCP register layouts into normalized internal signals.

Current profiles include:
- **`open_bess_edge_reference`**: Canonical industrial profile supporting bidirectional active/reactive power control (P/Q) and hardware watchdog heartbeat.
- **Vendor profiles (monitor mode)**: `huawei_sun2000`, `sma_sunny_tripower`, `fronius_gen24_byd`, `solaredge_storedge`, `victron_multiplus2`.

> **Engineering Note:** Commercial vendor profiles are categorized strictly in *monitor-only* mode for telemetry collection until completing physical hardware-in-the-loop (HIL) bench qualification (72 hours of uninterrupted continuous operation without spurious trips).

---

## Response Times & Grid Codes

### What is the contingency response latency?

The core execution cycle executes deterministically at **100 ms** (configurable via `runtime.cycle_ms`).

For Fast Frequency Response (FFR / droop control), the end-to-end response budget satisfies the Chilean NTSyCS grid standard requirements (**under 500 ms** from frequency step detection through setpoint dispatch over Modbus TCP).

---

## Autonomous Operation & Cloud Independence

### Does the gateway require an internet or cloud connection?

**No.** Open BESS Edge is engineered for **autonomous, deterministic local execution (OT edge)**:
- All protective logic (`SafetyEnvelope`, `BESS-GUARD-001` through `091`) runs entirely on local compute.
- If connectivity to the PCC grid meter or PCS inverter drops, the node immediately enters `SAFE_STATE`, clamping power setpoints to zero kW.
- The critical control and safety loop has zero external cloud or API dependencies.

---

## Architecture & Algorithm Boundaries

### Does the gateway execute machine learning or black-box models in the control loop?

**No.** Open BESS Edge strictly enforces deterministic protection guardrails and primary grid support.
- Market arbitrage, dispatch scheduling, and state-of-health forecasting models reside exclusively in higher-level supervisory layers (EMS / Cloud).
- Supervisory systems communicate with the gateway via time-bounded (TTL) dispatch schedules constrained by the physical safety envelope.
- Safety-critical trip actions are never delegated to stochastic or black-box algorithms.

---

## Hardware-Free Verification

### How is the codebase validated without physical battery hardware?

The repository includes a physics-informed simulation environment (`SimEnvironment` and `Harness`) running over real loopback TCP sockets. This enables automated execution of the 278-test canonical suite, exercising frequency contingencies, cell voltage/temperature imbalances, and communication link drops against real network sockets with zero driver-level mocks.

---

## Licensing & Governance

### Under what license is Open BESS Edge distributed?

Open BESS Edge is released under the permissive open-source **Apache License 2.0**. It can be audited, adapted, and integrated into industrial energy storage projects.
