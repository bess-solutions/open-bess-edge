# Open BESS Edge + Home Assistant via MQTT

> **Objective:** Stream real-time BESS telemetry (SOC, active power, cell temperatures, alarms) to Home Assistant using MQTT.

---

## System Architecture

```text
[Inverter / Simulated Plant]
        │  Modbus TCP
        ▼
[Open BESS Edge Gateway]
        │  MQTT Client
        ▼
[Mosquitto Broker]  ◄──── or compatible broker (HiveMQ, EMQX)
        │
        ▼
[Home Assistant]  →  Dashboards, Lovelace UI, Automation Engine
```

**Broker Compatibility:** Eclipse Mosquitto, HiveMQ, EMQX, AWS IoT Core, Azure IoT Hub.

---

## Prerequisites

- Open BESS Edge Gateway running (see [Quickstart](quickstart_5min.md)).
- Home Assistant (any recent release).
- Accessible MQTT Broker.

---

## Step 1 — Deploy Mosquitto Broker

=== "Linux / Raspberry Pi"
```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

=== "Docker"
```bash
docker run -d \
  --name mosquitto \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto:2
```

=== "Home Assistant Add-on"
Navigate to **Settings → Add-ons → Mosquitto broker** and click Install.

---

## Step 2 — Configure MQTT in Open BESS Edge

Configure your environment or YAML settings:

```env
# MQTT Publisher Configuration
MQTT_ENABLED=true
MQTT_BROKER_HOST=192.168.1.100   # Broker IP address (or 'localhost')
MQTT_BROKER_PORT=1883
MQTT_CLIENT_ID=open-bess-edge-site1
MQTT_SITE_ID=SITE-CL-001

# Optional Authentication
# MQTT_USERNAME=bess
# MQTT_PASSWORD=your_password
```

### Published Telemetry Topics

| Topic Pattern | Payload Format | Publish Cadence | Example Content |
|---|---|---|---|
| `bessai/{site_id}/telemetry` | JSON | Periodic cycle (~5s) | `{"soc": 72.4, "power_kw": 120.5, ...}` |
| `bessai/{site_id}/status` | JSON | On state transition | `{"connected": true, "mode": "discharge"}` |
| `bessai/{site_id}/alarms` | JSON | On event trigger | `{"level": "warning", "msg": "SOC < 20%"}` |
| `bessai/{site_id}/heartbeat` | ISO-8601 String | Every 30s | `"2026-09-30T12:00:00Z"` |

---

## Step 3 — Home Assistant Configuration

### 3a. Add MQTT Integration in Home Assistant
Navigate to **Settings → Devices & Services → Add Integration → MQTT**:
- **Broker:** IP address of Mosquitto
- **Port:** 1883
- **Credentials:** if authentication is enabled

### 3b. Define Entities in `configuration.yaml`

```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "BESS SOC"
      unique_id: bess_soc_site1
      state_topic: "bessai/SITE-CL-001/telemetry"
      value_template: "{{ value_json.soc }}"
      unit_of_measurement: "%"
      device_class: battery
      icon: mdi:battery

    - name: "BESS Active Power"
      unique_id: bess_power_site1
      state_topic: "bessai/SITE-CL-001/telemetry"
      value_template: "{{ value_json.power_kw }}"
      unit_of_measurement: "kW"
      device_class: power
      icon: mdi:lightning-bolt

    - name: "BESS Max Temperature"
      unique_id: bess_temp_site1
      state_topic: "bessai/SITE-CL-001/telemetry"
      value_template: "{{ value_json.temperature_c }}"
      unit_of_measurement: "°C"
      device_class: temperature

  binary_sensor:
    - name: "BESS Gateway Online"
      unique_id: bess_online_site1
      state_topic: "bessai/SITE-CL-001/status"
      value_template: "{{ value_json.connected }}"
      payload_on: "true"
      payload_off: "false"
      device_class: connectivity
```

Reload Home Assistant YAML configuration via **Developer Tools → YAML → Manually configured MQTT entities**.

---

## Step 4 — Lovelace UI Dashboard

Add an entity card stack in your Lovelace dashboard:

```yaml
type: vertical-stack
cards:
  - type: gauge
    entity: sensor.bess_soc
    name: Battery SOC
    min: 0
    max: 100
    severity:
      green: 40
      yellow: 20
      red: 0

  - type: entities
    title: Open BESS Edge Telemetry
    entities:
      - sensor.bess_active_power
      - sensor.bess_max_temperature
      - binary_sensor.bess_gateway_online
```

---

## Step 5 — Verification & Troubleshooting

Verify message flow from your shell:

```bash
mosquitto_sub -h localhost -t "bessai/#" -v
```

| Symptom | Probable Cause | Remedy |
|---|---|---|
| Home Assistant receives no updates | Broker network isolation | Verify firewall allows ingress on port 1883 |
| Topic remains empty | `MQTT_ENABLED` is false | Verify setting in configuration |
| Authentication rejected | Mismatched credentials | Confirm username/password in `configuration.yaml` |

See [`docs/mqtt_integration.md`](../mqtt_integration.md) for mutual TLS (mTLS) and cloud IoT broker guides.
