# Quickstart: Open BESS Edge in 5 Minutes (Hardware-Free)

> **Objective:** Run Open BESS Edge Gateway locally, verify telemetry over Modbus TCP, and monitor metrics in Grafana — **without requiring physical inverter hardware**.

---

## Prerequisites

| Tool | Minimum Version | Verification Command |
|---|---|---|
| Docker Desktop | 24.x | `docker --version` |
| Docker Compose | 2.x | `docker compose version` |
| Git | 2.40+ | `git --version` |

No cloud credentials or physical inverters required.

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
```

---

## Step 2 — Start the Stack

```bash
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator \
  --profile monitoring \
  up --build -d
```

This launches the local containers:

| Container | Role | Exposed Port |
|---|---|---|
| `bessai-modbus-simulator` | Simulates an industrial BESS plant over Modbus TCP | Internal |
| `bessai-gateway-sim` | Open BESS Edge Gateway connected to the simulator | `8000` |
| `bessai-prometheus` | Scrapes telemetry and loop metrics every 15s | `9090` |
| `bessai-grafana` | Visual operations dashboard | `3000` |

---

## Step 3 — Verify Gateway Health

```bash
# Check gateway health endpoint
curl http://localhost:8000/health
# Expected output: {"status": "ok", "uptime_s": ..., "site_id": "SITE-SIM-001"}

# Check active metrics scrape
curl http://localhost:8000/metrics | grep bess_cycles_total
```

---

## Step 4 — Open Grafana Dashboard

Navigate to **http://localhost:3000** in your browser:

- **Username:** `admin`
- **Password:** value of `GF_SECURITY_ADMIN_PASSWORD` in your `.env` (or defaults in `.env.example`).

The **BESSAI Main** dashboard provides:
- State of Charge (SOC) tracking
- Active & Reactive power (kW / kVAR) from the plant model
- Safety envelope evaluation & guard statuses
- Latency and cycle execution histograms

---

## Step 5 — Stop the Stack

```bash
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator --profile monitoring \
  down
```

---

## Next Steps

| I want to... | Read |
|---|---|
| Connect to real inverter hardware | [`docs/tutorials/connecting_real_hardware.md`](connecting_real_hardware.md) |
| Integrate with MQTT / Home Assistant | [`docs/tutorials/integration_homeassistant.md`](integration_homeassistant.md) |
| Deploy on Raspberry Pi 4/5 | [`docs/quickstart_rpi.md`](../quickstart_rpi.md) |
| Understand complete architecture | [`docs/architecture.md`](../architecture.md) |

---

## Troubleshooting

**Gateway does not connect to the simulator:**
```bash
docker compose logs bessai-gateway-sim --tail=20
# If "Connection refused" appears, wait a few seconds while the simulator finishes binding port 502.
```

**Port 3000 is already allocated:**
Adjust the host port in `docker-compose.yml`:
```yaml
ports:
  - "3001:3000"
```
