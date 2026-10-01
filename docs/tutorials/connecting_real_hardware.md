# Connecting Real Inverter Hardware to Open BESS Edge

> **Audience:** Automation technicians and electrical engineers connecting Open BESS Edge Gateway to commercial inverters (e.g., Huawei SUN2000, SMA Sunny Tripower, Victron MultiPlus-II, Fronius GEN24).  
> **Estimated Time:** 30–45 minutes.

---

## Prerequisites

- Open BESS Edge running locally and verified (via `open-bess-edge check-config config/edge_config.yaml`).
- IP network visibility from the edge gateway host to the inverter controller across the OT local area network.
- **Port 502 TCP** accessible between the gateway host and the inverter/gateway logger.
- Inverter administrative credentials (if authentication or Modbus TCP enablement is required).

---

## Step 1 — Identify the Inverter IP Address

### Huawei SUN2000 / SmartLogger
- Connected via Smart Dongle-WLAN-FE or SmartLogger Ethernet port.
- Default: DHCP on local OT network or fixed static IP.
- Identify the host responding on port 502:
  ```bash
  nmap -p 502 192.168.1.0/24 --open
  ```
- Alternatively, check the network interface in the **FusionSolar** portal/app.

### SMA Sunny Tripower / Data Manager
- Locate IP configured via the device web interface or front panel display.
- Ensure Modbus TCP server is switched ON in inverter parameters.

### Victron MultiPlus-II (via Venus OS / GX device)
- Enable Modbus TCP in Venus OS: **Settings → Services → Modbus TCP**.
- Port: **502**. Unit ID: 100 (or as configured for the system gateway).

### Fronius GEN24
- Accessible via local web UI.
- Activate: **Communication → Modbus TCP → Enable** (Data format: Int+SF or float).

---

## Step 2 — Verify Modbus TCP Connectivity

Run a basic Python check to confirm the inverter socket accepts Modbus connections:

```bash
python - << 'EOF'
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.1.100", port=502, timeout=5)
connected = client.connect()
print(f"Modbus Connection: {'SUCCESS' if connected else 'FAILED'}")
if connected:
    result = client.read_holding_registers(40001, count=2, slave=1)
    print(f"Registers 40001-40002: {result.registers if not result.isError() else result}")
client.close()
EOF
```

If the connection is confirmed, proceed to profile configuration.

---

## Step 3 — Select Device Profile

Open BESS Edge includes standardized profiles in the [`registry/`](../../registry/) directory:

| Profile File | Target Hardware | Operational Mode |
|---|---|---|
| `registry/open_bess_edge_reference.json` | Project Reference Specification | Control (Active/Reactive) |
| `registry/huawei_sun2000.json` | Huawei SUN2000 + LUNA2000 | Monitor (Unverified tier) |
| `registry/sma_sunny_tripower.json` | SMA Sunny Tripower | Monitor (Unverified tier) |
| `registry/victron_multiplus2.json` | Victron MultiPlus-II (Venus OS) | Monitor (Unverified tier) |
| `registry/fronius_gen24_byd.json` | Fronius GEN24 + BYD Battery-Box | Monitor (Unverified tier) |

Inspect profile details via the CLI:
```bash
open-bess-edge profile-info huawei_sun2000
```

---

## Step 4 — Configure `config/edge_config.yaml`

Configure your site deployment file:

```yaml
site:
  id: "SITE-ATACAMA-001"
  inverter_type: "huawei_sun2000"
  modbus_host: "192.168.1.100"
  modbus_port: 502
  unit_id: 1

runtime:
  cycle_ms: 100
  startup_valid_cycles: 5
  comm_loss_hold_s: 2.0

grid_standards:
  nominal_frequency_hz: 50.0
  deadband_hz: 0.030
  droop_percentage: 3.0
```

Validate the file syntax:
```bash
open-bess-edge check-config config/edge_config.yaml
```

---

## Step 5 — Launch the Gateway

```bash
open-bess-edge run --config config/edge_config.yaml
```

**Expected Log Progression:**
```text
INFO open_bess_edge.modbus.transport: Connected to 192.168.1.100:502
INFO open_bess_edge.node: state INIT -> STARTING (STARTUP)
INFO open_bess_edge.node: state STARTING -> RUNNING (VALIDATED)
INFO open_bess_edge.safety.envelope: SafetyEnvelope evaluated: state=NORMAL trips=[]
```

---

## Universal Physical Convention Reminder

* **Active Power (P):** `+` = discharge / grid injection; `−` = charge / grid consumption.
* **Reactive Power (Q):** `+` = capacitive (injects VAR, raises voltage); `−` = inductive (absorbs VAR, lowers voltage).

Manufacturer-specific register conventions are mapped automatically using the `sign` and `factor` attributes in each profile.

---

## Troubleshooting

| Symptom | Probable Cause | Action |
|---|---|---|
| `ModbusConnectionException` | Incorrect IP address or blocked port | Check routing and run `nmap -p 502 <INVERTER_IP>` |
| Register values return `65535` | Inverted byte/word order or incorrect Slave Unit ID | Verify `unit_id` in YAML configuration |
| SOC returns `0.0%` | Incorrect register offset | Inspect device register map against profile JSON |
| Frequent link resets | Network latency or polling overload | Increase `runtime.cycle_ms` or inspect Ethernet switch |
