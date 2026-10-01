# Industrial Operations Guide — Open BESS Edge Gateway

Operational procedures for deploying, supervising, and maintaining the Open BESS Edge Gateway on edge hardware (Industrial PCs, DIN-rail computers, or local substation servers) communicating with inverters and BESS controllers over isolated OT networks.

---

## 1. Edge Deployment Architecture

The gateway runs locally alongside the PCS inverter or BMS controller, interfacing directly via **Modbus TCP** across segregated OT networks:

* **Native Systemd Service:** Recommended deployment for industrial embedded Linux installations (Debian, Ubuntu Server, Raspberry Pi OS).
* **Docker Container:** Containerized runtime offering dependency isolation and automated restarts.

---

## 2. Systemd Service Deployment

### Unit File (`/etc/systemd/system/open-bess-edge.service`)

```ini
[Unit]
Description=Open BESS Edge Gateway Industrial Service
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=bess
Group=bess
WorkingDirectory=/opt/open-bess-edge
Environment="PYTHONPATH=/opt/open-bess-edge/src"
ExecStart=/opt/open-bess-edge/.venv/bin/open-bess-edge run --config /opt/open-bess-edge/config/edge_config.yaml
Restart=always
RestartSec=5s
LimitNOFILE=65535

# Industrial OT security sandboxing
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/lib/open-bess-edge /var/log/open-bess-edge
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

### Operational Commands

```bash
# Start edge gateway service
sudo systemctl start open-bess-edge

# Check service status and loop diagnostics
sudo systemctl status open-bess-edge

# Follow operational logs in real-time
sudo journalctl -u open-bess-edge -f -o cat
```

---

## 3. Docker Compose Deployment

```bash
# Start edge container in background
docker compose up -d

# Stream real-time logs from the edge node
docker compose logs -f --tail=100 open-bess-edge
```

---

## 4. Telemetry Supervision & Node Health

Key operational telemetry signals monitored by the gateway:

| Telemetry Signal | Nominal Operating Range | Anomaly Handling |
| :--- | :--- | :--- |
| **`modbus_poll_latency_ms`** | $< 100\text{ ms}$ | Inspect OT Ethernet switch, cabling, or inverter load if latency spikes. |
| **`grid_frequency_hz`** | $49.80 - 50.20\text{ Hz}$ | Normal SEN Chile range. Deviations beyond $\pm 30\text{ mHz}$ trigger FFR droop. |
| **`battery_soc_pct`** | $10\% - 95\%$ | Operating buffer protecting cells from deep degradation. |
| **`battery_cell_temp_max_c`** | $< 45^\circ\text{C}$ | Values $> 50^\circ\text{C}$ trigger 50% derating; $> 55^\circ\text{C}$ latches emergency trip. |

---

## 5. Safety Envelope Trip Response & Recovery

When the `SafetyEnvelope` detects an unrecoverable electrical, thermal, or communication fault:

1. **TRIP Execution:** The gateway immediately latches the trip state, commands $P = 0\text{ kW}$ and $Q = 0\text{ kVAR}$ to the PCS, and records an append-only audit event.
2. **Audit Inspection:** Verify cause in the local audit log:
   ```bash
   open-bess-edge verify-audit /var/lib/open-bess-edge/audit.jsonl
   ```
3. **Reset Procedure:** Safety trips remain latched even if conditions normalize transiently. Clearing requires:
   * Verification that all telemetry values have returned within nominal hysteresis limits for at least 60 seconds.
   * Explicit administrative reset action.
