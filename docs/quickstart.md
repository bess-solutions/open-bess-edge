# Quick Start Guide — Open BESS Edge Gateway

Get the **Open BESS Edge** gateway up and running locally with the built-in physics simulator in under 10 minutes.

---

## 📋 Prerequisites

* **Python 3.10+** (Python 3.12 recommended).
* **Git**.
* Optional: **Docker** & **Docker Compose** for containerized deployment.

---

## ⚡ Step-by-Step Setup

### Step 1: Clone the Repository
```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
```

### Step 2: Initialize Virtual Environment
On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### Step 3: Run the In-Tree Simulation
Execute the deterministic battery plant simulation over real loopback Modbus TCP:

```bash
open-bess-edge simulate --duration 15
```

This runs a 1000 kW / 2000 kWh battery model with a dynamic 49.65 Hz under-frequency event, demonstrating the real-time Fast Frequency Response (FFR) droop calculation and setpoint dispatch.

### Step 4: Validate Site Configuration
Verify your deployment YAML configuration file:

```bash
open-bess-edge check-config config/edge_config.yaml
```

### Step 5: Inspect Vendor Device Profiles
Explore the standardized register maps in the registry:

```bash
open-bess-edge profile-info open_bess_edge_reference
open-bess-edge profile-info huawei_sun2000
```

### Step 6: Verify Test Suite
Run the 278-test canonical suite:

```bash
pytest -q
```

---

## 🔍 Next Steps

* **Industrial Operations:** Consult the [Operations Guide](OPERATIONS_GUIDE.md) for systemd and service sandboxing.
* **Real Hardware Interfacing:** Follow the [Connecting Real Hardware Tutorial](tutorials/connecting_real_hardware.md).
* **Field Pilot Commissioning:** See the [Site Pilot Guide](PILOT_GUIDE.md).
