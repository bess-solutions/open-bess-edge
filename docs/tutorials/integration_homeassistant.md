# 🏠 BESSAI + Home Assistant via MQTT

> **Objetivo:** Publicar telemetría BESS (SOC, potencia, temperatura) a Home Assistant en tiempo real, usando MQTT como bus de mensajería.

---

## Arquitectura

```
[Inversor / Simulador]
        │  Modbus TCP
        ▼
[BESSAI Edge Gateway]
        │  MQTT paho-client
        ▼
[Mosquitto Broker]  ◄──── o cualquier broker compatible
        │
        ▼
[Home Assistant]  →  Automations, Dashboards, Lovelace
```

**Compatibilidad de brokers:** Mosquitto · HiveMQ · EMQX · AWS IoT Core · Azure IoT Hub

---

## Requisitos

- BESSAI Edge Gateway corriendo (ver [quickstart_5min.md](quickstart_5min.md))
- Home Assistant (cualquier versión reciente)
- Broker MQTT instalado (se usa Mosquitto en este tutorial)

---

## Paso 1 — Instalar Mosquitto

=== "Linux / Raspberry Pi"
```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

=== "Docker (recomendado)"
```bash
docker run -d \
  --name mosquitto \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto:2
```

=== "Home Assistant Add-on"
En HA, ve a **Ajustes → Add-ons → Mosquitto broker** e instálalo con un clic.

---

## Paso 2 — Configurar BESSAI para MQTT

Edita `config/.env` (copia desde `config/.env.example`):

```env
# MQTT — activar publisher
MQTT_ENABLED=true
MQTT_BROKER_HOST=192.168.1.100   # IP de tu broker (o 'localhost')
MQTT_BROKER_PORT=1883
MQTT_CLIENT_ID=bessai-edge-site1
MQTT_SITE_ID=SITE-CL-001

# Opcional — autenticación
# MQTT_USERNAME=bessai
# MQTT_PASSWORD=your_password

# Opcional — TLS
# MQTT_USE_TLS=true
# MQTT_CA_CERT=/certs/ca.crt
```

### Topics que publica BESSAI automáticamente

| Topic | Tipo | Frecuencia | Ejemplo de payload |
|---|---|---|---|
| `bessai/{site_id}/telemetry` | JSON | Cada ciclo (~5s) | `{"soc": 72.4, "power_kw": 120.5, ...}` |
| `bessai/{site_id}/status` | JSON | En cambios | `{"connected": true, "mode": "discharge"}` |
| `bessai/{site_id}/alarms` | JSON | En eventos | `{"level": "warning", "msg": "SOC < 20%"}` |
| `bessai/{site_id}/heartbeat` | string | Cada 30s | `"2026-02-22T00:00:00Z"` |

---

## Paso 3 — Configurar Home Assistant

### 3a. Añadir integración MQTT en HA

Ve a **Ajustes → Dispositivos y Servicios → + Añadir integración → MQTT**.

Ingresa:
- **Broker:** IP de Mosquitto
- **Puerto:** 1883
- **Usuario/contraseña:** si configuraste auth

### 3b. Definir sensores MQTT en `configuration.yaml`

```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "BESSAI SOC"
      unique_id: bessai_soc_site1
      state_topic: "bessai/SITE-CL-001/telemetry"
      value_template: "{{ value_json.soc }}"
      unit_of_measurement: "%"
      device_class: battery
      icon: mdi:battery

    - name: "BESSAI Power"
      unique_id: bessai_power_site1
      state_topic: "bessai/SITE-CL-001/telemetry"
      value_template: "{{ value_json.power_kw }}"
      unit_of_measurement: "kW"
      device_class: power
      icon: mdi:lightning-bolt

    - name: "BESSAI Temperature"
      unique_id: bessai_temp_site1
      state_topic: "bessai/SITE-CL-001/telemetry"
      value_template: "{{ value_json.temperature_c }}"
      unit_of_measurement: "°C"
      device_class: temperature

    - name: "BESSAI AI-IDS Score"
      unique_id: bessai_ids_site1
      state_topic: "bessai/SITE-CL-001/telemetry"
      value_template: "{{ value_json.ids_anomaly_score }}"
      icon: mdi:shield-alert

  binary_sensor:
    - name: "BESSAI Online"
      unique_id: bessai_online_site1
      state_topic: "bessai/SITE-CL-001/status"
      value_template: "{{ value_json.connected }}"
      payload_on: "true"
      payload_off: "false"
      device_class: connectivity
```

Luego reinicia HA: **Ajustes → Sistema → Reiniciar**.

---

## Paso 4 — Dashboard Lovelace

Añade una tarjeta tipo **Gauge** y **Entity** en tu dashboard:

```yaml
# Dashboard Lovelace — tarjeta BESS
type: vertical-stack
cards:
  - type: gauge
    entity: sensor.bessai_soc
    name: BESSAI SOC
    min: 0
    max: 100
    severity:
      green: 40
      yellow: 20
      red: 0

  - type: entities
    title: BESSAI Edge Gateway
    entities:
      - sensor.bessai_power
      - sensor.bessai_temperature
      - sensor.bessai_ai_ids_score
      - binary_sensor.bessai_online
```

---

## Paso 5 — Automatización: alerta cuando SOC < 20%

```yaml
# automations.yaml
- alias: "BESSAI — Alerta SOC crítico"
  trigger:
    - platform: numeric_state
      entity_id: sensor.bessai_soc
      below: 20
  action:
    - service: notify.mobile_app
      data:
        title: "⚠️ BESS — SOC Crítico"
        message: "SOC cayó a {{ states('sensor.bessai_soc') }}%"
```

---

## Verificación rápida

```bash
# Suscribirse a los topics desde terminal
mosquitto_sub -h localhost -t "bessai/#" -v

# Deberías ver mensajes cada ~5 segundos:
# bessai/SITE-CL-001/telemetry {"soc": 72.4, "power_kw": 120.5, ...}
```

---

## Solución de problemas

| Problema | Causa probable | Solución |
|---|---|---|
| HA no recibe datos | Broker no accesible | `ping IP_BROKER` desde el host de HA |
| Topic vacío | MQTT_ENABLED=false | Verificar `.env` |
| Auth error | Credenciales incorrectas | Revisar `MQTT_USERNAME`/`MQTT_PASSWORD` |
| TLS handshake fail | Certificado incorrecto | Verificar `MQTT_CA_CERT` path |

---

> 📖 **Referencia completa:** [`docs/mqtt_integration.md`](../mqtt_integration.md) — incluye configuración TLS mutuo, AWS IoT Core, y Azure IoT Hub.
