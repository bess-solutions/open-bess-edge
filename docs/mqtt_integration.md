# MQTT Integration Guide

BESSAI Edge Gateway puede publicar telemetría a cualquier broker MQTT como alternativa o complemento a Google Cloud Pub/Sub. Ideal para instalaciones sin acceso constante a internet o integradas con Home Assistant, AWS IoT Core o Azure IoT Hub.

## Configuración rápida

En `config/.env`:

```dotenv
MQTT_BROKER_URL=mqtt://192.168.1.10:1883
```

## Brokers soportados

| Broker | URL ejemplo | Notas |
|---|---|---|
| Mosquitto local | `mqtt://localhost:1883` | Sin auth |
| Home Assistant | `mqtt://homeassistant.local:1883` | Habilitar integración MQTT en HA |
| HiveMQ Cloud | `mqtts://cluster.hivemq.cloud:8883` | Requiere usuario/pass |
| AWS IoT Core | `mqtts://xxxx.iot.us-east-1.amazonaws.com:8883` | TLS mutuo, ver más abajo |
| Azure IoT Hub | `mqtts://hub.azure-devices.net:8883` | SAS Token como password |

## Topics publicados

Todos los topics usan el `SITE_ID` como prefijo:

```
{SITE_ID}/telemetry       → SOC, potencia, temperatura, ciclos
{SITE_ID}/safety          → is_safe, watchdog
{SITE_ID}/ai/ids          → score anomalía, alertas, estado modelo
{SITE_ID}/ai/dispatch     → setpoint ONNX, latencia inferencia
{SITE_ID}/system/heartbeat → latido de liveness (cada 5 s)
```

Ejemplo de payload JSON (`telemetry`):
```json
{
  "ts": 1740151200.0,
  "site_id": "SITE-CL-001",
  "soc_pct": 72.3,
  "power_kw": -85.5,
  "temp_c": 28.1,
  "cycle_count": 312
}
```

## Autenticación con usuario/contraseña

```dotenv
MQTT_BROKER_URL=mqtt://broker.example.com:1883
MQTT_USERNAME=bessai_edge
MQTT_PASSWORD=s3cr3t
```

## TLS / MQTTS

```dotenv
MQTT_BROKER_URL=mqtts://broker.example.com:8883
MQTT_TLS_CA_CERT_PATH=/certs/ca.crt        # CA raíz del broker
```

## AWS IoT Core (TLS Mutuo)

1. En AWS IoT Console → Things → crea un Thing `bessai-edge-site001`
2. Descarga los 3 certificados: `cert.pem`, `private.key`, `root-CA.crt`
3. Configúralos en el contenedor:

```yaml
# docker-compose.yml (override)
volumes:
  - /path/to/certs:/certs:ro
```

```dotenv
MQTT_BROKER_URL=mqtts://xxxx-ats.iot.us-east-1.amazonaws.com:8883
MQTT_TLS_CA_CERT_PATH=/certs/root-CA.crt
MQTT_TLS_CERTFILE=/certs/cert.pem
MQTT_TLS_KEYFILE=/certs/private.key
```

## Home Assistant — integración automática

Con Mosquitto en HA, los topics aparecen automáticamente como sensores:

```yaml
# configuration.yaml (HA)
mqtt:
  sensor:
    - name: "BESS SOC"
      state_topic: "SITE-CL-001/telemetry"
      value_template: "{{ value_json.soc_pct }}"
      unit_of_measurement: "%"
    - name: "BESS Power"
      state_topic: "SITE-CL-001/telemetry"
      value_template: "{{ value_json.power_kw }}"
      unit_of_measurement: "kW"
```
