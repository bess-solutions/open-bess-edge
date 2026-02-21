# Quickstart: Raspberry Pi 4/5 Deployment

> **Tiempo estimado:** 15 minutos · **Hardware requerido:** Raspberry Pi 4/5 (4 GB RAM) + tarjeta microSD 32 GB

Deploy BESSAI Edge Gateway en un Raspberry Pi conectado a cualquier inversor BESS con Modbus TCP.
Soporta Huawei SUN2000, SMA Sunny Tripower, Victron MultiPlus-II y Fronius Symo GEN24.

---

## Prerrequisitos

| Ítem | Detalles |
|---|---|
| SO recomendado | Raspberry Pi OS Lite 64-bit (Bookworm) |
| Docker Engine | ≥ 24.0 (incluido en la sección de instalación) |
| Conectividad | RPi en la misma LAN que el inversor |
| IP del inversor | Modbus TCP habilitado en el inversor (ver manual) |

---

## 1. Prepara la Raspberry Pi

```bash
# En la RPi (via SSH o teclado/monitor):
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl

# Instala Docker en una línea:
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

---

## 2. Descarga BESSAI Edge

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# Crea archivo de configuración local
cp config/.env.example config/.env
```

---

## 3. Configura el sitio

Edita `config/.env` con los parámetros de tu instalación:

```dotenv
# ── Sitio ──────────────────────────────────────────────────────────────────
SITE_ID=SITE-MI-BESS-001          # Nombre único del sitio

# ── Inversor (Modbus TCP) ──────────────────────────────────────────────────
INVERTER_IP=192.168.1.100         # IP del inversor en tu LAN
INVERTER_PORT=502                  # Puerto Modbus TCP (default: 502)
MODBUS_UNIT_ID=1                   # Unit ID del esclavo (ver manual)
DEVICE_PROFILE=huawei_sun2000      # Perfil del dispositivo (ver tabla abajo)

# ── Dashboard ──────────────────────────────────────────────────────────────
DASHBOARD_API_KEY=                 # Dejar vacío en desarrollo; usar token en producción

# ── Cloud (opcional — omitir si usas MQTT) ────────────────────────────────
# GCP_PROJECT_ID=mi-proyecto
# GCP_PUBSUB_TOPIC=bess-telemetry

# ── MQTT (alternativa a GCP, recomendado para instalaciones sin internet) ──
MQTT_BROKER_URL=mqtt://192.168.1.10:1883   # IP de tu broker (p.ej. Home Assistant)
# MQTT_USERNAME=bessai
# MQTT_PASSWORD=secreto
```

### Perfiles de dispositivo disponibles

| Valor `DEVICE_PROFILE` | Fabricante | Modelo |
|---|---|---|
| `huawei_sun2000` | Huawei | SUN2000-L1 + LUNA2000 |
| `sma_sunny_tripower` | SMA | Sunny Tripower X + Home Storage |
| `victron_multiplus2` | Victron Energy | MultiPlus-II via Venus OS |
| `fronius_gen24_byd` | Fronius | Symo GEN24 Plus + BYD HVS |

---

## 4. Arranca el sistema

```bash
# La imagen ARM64 se descarga automáticamente desde ghcr.io:
docker compose -f infrastructure/docker/docker-compose.yml up -d

# Verifica que levantó correctamente:
docker compose logs -f bessai-gateway
```

Deberías ver en los logs:
```
{"event":"driver.connected","host":"192.168.1.100","port":502,...}
{"event":"gateway.watchdog_loop.started","version":"1.7.0",...}
{"event":"dashboard_api.listening","port":8080,...}
```

---

## 5. Abre el Dashboard

En un navegador en la misma red, abre:

```
http://<IP-de-la-RPi>:8080
```

El dashboard mostrará en tiempo real:
- 🔋 SOC y potencia del BESS
- ⚡ Flujo de potencia (red ↔ BESS ↔ carga)
- 🤖 Score AI-IDS (detección de anomalías)
- 💰 Proyección de arbitraje 24h

---

## 6. Verifica la salud del sistema

```bash
# Endpoint de health (liveness probe):
curl http://<IP-RPi>:8000/health

# Métricas Prometheus:
curl http://<IP-RPi>:8000/metrics

# API REST directa:
curl http://<IP-RPi>:8080/api/v1/status | python3 -m json.tool
```

---

## 7. Habilita arranque automático

```bash
# El gateway arranca automáticamente con el sistema gracias a restart: unless-stopped:
sudo systemctl enable docker
# ¡Listo! Se reinicia solo después de un corte de luz.
```

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `driver.connection_failed` en logs | IP incorrecta o Modbus no habilitado en el inversor | Verificar IP con `ping` y activar Modbus TCP en el menú del inversor |
| Dashboard no carga (`ERR_CONNECTION_REFUSED`) | Puerto 8080 bloqueado | `sudo ufw allow 8080/tcp` |
| `GCP_PROJECT_ID is required` | Usando PubSub sin configurar | Dejar variables GCP vacías y usar MQTT en su lugar |
| SOC siempre `--` | Unit ID incorrecto | Probar `MODBUS_UNIT_ID=3` (Huawei) o `227` (Victron) |

---

## Próximos pasos

- [Configura MQTT](./mqtt_integration.md) para publicar en Home Assistant, AWS IoT o un broker propio
- [Arquitectura del sistema](./architecture.md)
- [Runbook de operaciones](./runbook.md)
- [API Reference](./api_reference.md)
