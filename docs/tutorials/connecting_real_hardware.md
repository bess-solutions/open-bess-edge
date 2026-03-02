# 🔌 Conectar un Inversor Real a BESSAI

> **Para quién:** Técnicos e ingenieros que ya tienen `docker compose --profile simulator up` funcionando y quieren conectar a un inversor Huawei SUN2000, SMA, Victron o Fronius real.
> **Tiempo estimado:** 30-45 minutos

---

## Requisitos previos

- BESSAI corriendo en modo simulador (verificado con `curl http://localhost:8000/health`)
- Acceso de red al inversor (misma LAN o VPN)
- El puerto **502 TCP** no bloqueado entre host BESSAI y el inversor
- Credenciales del inversor (si tiene auth habilitada)

---

## Paso 1 — Identificar la IP del inversor

### Huawei SUN2000
```bash
# El inversor tiene un dongle WiFi o puerto Ethernet
# Default: DHCP en red local. Buscar con nmap:
nmap -p 502 192.168.1.0/24 --open
# El host que responde en puerto 502 es el inversor
```

Alternativamente en la app **FusionSolar** → Dispositivo → Info de red.

### SMA Sunny Tripower
```bash
nmap -p 502 192.168.1.0/24 --open
# SMA suele asignarse IP estática configurada en el display
```

### Victron MultiPlus-II (via Venus OS)
- IP accesible desde VRM Portal → Local access
- Puerto Modbus: **502** (activar en Venus OS: Settings → Services → Modbus TCP)

### Fronius GEN24
- IP visible en la interfaz web del inversor
- Modbus TCP debe activarse: **Communication → Modbus TCP → Enable**

---

## Paso 2 — Verificar conectividad Modbus

```bash
# Instalar modpoll (herramienta de diagnóstico)
pip install pymodbus

# Test rápido Python (leer 1 registro del inversor):
python3 - << 'EOF'
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient("192.168.1.100", port=502, timeout=5)
conn = client.connect()
print(f"Conexión: {'OK' if conn else 'FALLÓ'}")
if conn:
    result = client.read_holding_registers(40001, count=2, slave=1)
    print(f"Registros 40001-40002: {result.registers if not result.isError() else result}")
client.close()
EOF
```

Si muestra registros → el inversor es accesible. Si `FALLÓ`, revisa firewall y Modbus habilitado en el inversor.

---

## Paso 3 — Seleccionar el perfil del hardware

BESSAI incluye 4 perfiles en `registry/`:

| Archivo | Hardware |
|---|---|
| `registry/huawei_sun2000.json` | Huawei SUN2000 + LUNA2000 |
| `registry/sma_sunny_tripower.json` | SMA Sunny Tripower |
| `registry/victron_multiplus.json` | Victron MultiPlus-II (via Venus OS) |
| `registry/fronius_gen24.json` | Fronius GEN24 + BYD |

```bash
# Ver qué registros incluye el perfil Huawei:
cat registry/huawei_sun2000.json | python3 -m json.tool | head -40
```

---

## Paso 4 — Configurar el `.env`

```bash
cp config/.env.example config/.env
```

Edita `config/.env`:

```env
# ── OBLIGATORIO ──────────────────────────────────────────
SITE_ID=SITE-ATACAMA-001          # Identificador único del sitio
INVERTER_IP=192.168.1.100         # ← IP real del inversor
INVERTER_PORT=502
BESSAI_MODE=modbus                # real hardware (no simulator)

# ── Perfil del hardware ───────────────────────────────────
DRIVER_PROFILE_PATH=registry/huawei_sun2000.json  # ← cambiar si es SMA/Victron/Fronius

# ── Opcional — GCP Pub/Sub ────────────────────────────────
# GCP_PROJECT_ID=mi-proyecto-gcp
# GCP_PUBSUB_TOPIC=bess-telemetria

# ── Opcional — MQTT ──────────────────────────────────────
# MQTT_ENABLED=true
# MQTT_BROKER_HOST=192.168.1.200
```

---

## Paso 5 — Levantar en modo hardware real

```bash
# Sin simulador (conecta directo al inversor)
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile monitoring \
  up --build -d

# Verificar que el gateway conectó:
docker compose logs bessai-gateway --tail=30 -f
```

**Logs esperados:**
```
INFO  [ModbusDriver] Connected to 192.168.1.100:502 (Huawei SUN2000)
INFO  [Gateway] Cycle 1: SOC=72.4% Power=120.5kW Temp=35.2°C
INFO  [SafetyGuard] All constraints OK
INFO  [PubSubPublisher] Published telemetry to bess-telemetry-dev
```

**Si ves `Connection refused` o `Timeout`:**
```bash
# (desde el host de BESSAI)
nc -zv 192.168.1.100 502
# Si falla: revisar el paso 2 de conectividad
```

---

## Paso 6 — Validar datos en Grafana

http://localhost:3000 → dashboard **BESSAI Main**

Deberías ver valores reales (no el rango simulado 20-95% SOC):
- **SOC real** del estado actual de la batería
- **Potencia real** (positivo = carga, negativo = descarga)
- **Temperatura** real de las celdas

---

## Paso 7 — Hardware no soportado

Si tu inversor no está entre los perfiles existentes:

1. Revisa si ya hay un issue abierto: [buscar en issues con etiqueta `hardware`](https://github.com/bess-solutions/open-bess-edge/issues?q=label%3Ahardware)
2. Si no existe, abre uno con la etiqueta `hardware` describiendo tu inversor y adjunta el mapa de registros Modbus del fabricante
3. Si tienes acceso al inversor físico, puedes contribuir el perfil JSON directamente: ver guía [hardware_profile_contribution.md](hardware_profile_contribution.md)

> Las contribuciones de perfiles de hardware son las más valoradas por la comunidad — se mencionan explícitamente en las release notes.

---

## Troubleshooting avanzado

| Síntoma | Causa | Solución |
|---|---|---|
| `ModbusConnectionException` | IP incorrecta o puerto bloqueado | `nmap -p 502 IP_INVERSOR` |
| Registros con valor `65535` | Slave ID incorrecto | Cambiar `MODBUS_SLAVE_ID` en `.env` |
| SOC siempre `0.0%` | Perfil JSON incorrecto | Verificar `DRIVER_PROFILE_PATH` |
| `TimeoutError` en todos los registros | Inversor en modo standby | Activar inversor y verificar Modbus habilitado |
| Reintentos constantes | Auto-reconnect activo (normal) | Verificar con `GET /health` el uptime |

> 📖 **Referencia completa:** [`docs/runbook.md`](../runbook.md) incluye checklist de producción, alertas Prometheus y procedimientos de escalada.
