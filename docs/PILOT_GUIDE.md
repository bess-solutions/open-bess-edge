# Field Pilot Commissioning Guide — Open BESS Edge Gateway

This engineering guide outlines procedures for commissioning the Open BESS Edge Gateway in pilot battery storage installations, validating Modbus TCP communication with inverters/PCS, and verifying dynamic grid support in compliance with Chilean grid standards (NTSyCS / Coordinador Eléctrico Nacional).

---

## 1. Field Requirements

* **Hardware:** Industrial PC (IPC), DIN-rail edge computer, or Linux gateway (x86_64 or aarch64).
* **OT Network:** Isolated Ethernet connection with direct IP visibility to the PCS inverter or plant controller (e.g., Huawei SmartLogger, SMA Data Manager, SunGrow controller).
* **Software Environment:** Python 3.10+ (or containerized deployment via Docker Compose).

---

## 2. Gateway Setup & Configuration

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bess-solutions/open-bess-edge.git
   cd open-bess-edge
   ```

2. **Initialize isolated environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. **Configure site parameters in `config/edge_config.yaml`:**
   ```yaml
   site:
     id: "PILOT-CL-LINARES-01"
     inverter_type: "huawei_sun2000"
     modbus_host: "192.168.1.50"
     modbus_port: 502
     unit_id: 1

   grid_standards:
     nominal_frequency_hz: 50.0
     deadband_hz: 0.030          # ±30 mHz deadband (CEN CFyDR standards)
     droop_percentage: 3.0       # 3.0% droop characteristic
     ffr_response_time_ms: 500   # Fast Frequency Response under 500 ms
   ```

4. **Validate configuration syntax:**
   ```bash
   open-bess-edge check-config config/edge_config.yaml
   ```

---

## 3. Preflight Quality & Safety Verification

Before connecting to live plant equipment or enabling writes, execute the canonical test suite and claims verification:

```bash
# Validate core test suite (278 tests)
pytest -q

# Run claims verification
python scripts/verify_claims.py
```

All 278 canonical core tests must pass.

---

## 4. Gateway Execution & Telemetry Validation

Launch the edge node in execution mode:

```bash
open-bess-edge run --config config/edge_config.yaml
```

Verify the following in stdout/logs:
1. Successful socket connection to the target Modbus TCP device.
2. Initial state transitions: `INIT -> STARTING -> RUNNING`.
3. Clean acquisition of cell voltages, string currents, active/reactive power, and SOC.
4. `SafetyEnvelope` evaluates to `NORMAL` state with zero trips.

---

## 5. Frequency & Grid Support Validation

To audit the Fast Frequency Response (FFR / droop) loop:
* Verify that frequency deviations exceeding $\pm 30\text{ mHz}$ trigger proportional active power adjustments $\Delta P$ corresponding to the configured $3\%$ droop slope.
* Confirm that setpoint generation and dispatch completes within the 500 ms normative budget.
* Verify that telemetry dropouts automatically trigger `BESS-GUARD-090` / `091`, clamping output setpoints to 0 kW.
