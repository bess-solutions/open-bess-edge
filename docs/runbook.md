# BESSAI Edge Gateway — Runbook Operacional (Day-2)

> **Audiencia:** Ingenieros de operaciones, SRE, on-call  
> **Prerrequisito:** Docker Desktop instalado, `config/.env` configurado  
> **Última actualización:** 2026-02-19 v0.3.0

---

## 1. Arranque y Parada

### Arrancar el stack completo (producción)
```bash
# Modo producción — requiere inversor real en INVERTER_IP
docker compose -f infrastructure/docker/docker-compose.yml up -d
```

### Arrancar en modo simulador (desarrollo/tests)
```bash
# El simulador Modbus estará disponible en localhost:5020
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator up -d
```

### Parada ordenada (graceful shutdown)
```bash
# SIGTERM → el gateway drena Pub/Sub, desconecta Modbus y flushea OTel
docker compose -f infrastructure/docker/docker-compose.yml down
```

### Reinicio de emergencia
```bash
docker compose -f infrastructure/docker/docker-compose.yml restart gateway
```

---

## 2. Health Checks

### Estado de los contenedores
```bash
docker compose -f infrastructure/docker/docker-compose.yml ps
```

**Salidas esperadas:**

| NAME | STATUS | PORTS |
|---|---|---|
| bessai-gateway | healthy | — |
| bessai-otel-collector | running | 4317/tcp → 0.0.0.0:4317 |
| bessai-modbus-simulator | healthy | 502/tcp → 0.0.0.0:5020 |

### Verificar logs en tiempo real
```bash
# Gateway
docker logs -f bessai-gateway

# Filtrar solo errores
docker logs bessai-gateway 2>&1 | grep -i "error\|critical\|safety_block"

# OTel Collector
docker logs -f bessai-otel-collector
```

### Health check manual
```bash
# Verifica que la configuración carga sin errores
docker exec bessai-gateway python -c "from src.core.config import get_settings; s=get_settings(); print(f'Site: {s.SITE_ID}, IP: {s.inverter_ip_str}')"
```

### Verificar conectividad Modbus
```bash
# Desde el contenedor gateway hacia el inversor
docker exec bessai-gateway python -c "
import asyncio
from src.drivers.modbus_driver import UniversalDriver
async def check():
    d = UniversalDriver('config/profiles/huawei_sun2000.json')
    await d.connect()
    soc = await d.read_tag('soc')
    print(f'SOC: {soc}%')
asyncio.run(check())
"
```

---

## 3. Rotación de Credenciales GCP

### Rotar Service Account Key

```bash
# 1. Crear nueva key
gcloud iam service-accounts keys create new-key.json \
  --iam-account=bessai-edge-sa-dev@YOUR_PROJECT.iam.gserviceaccount.com

# 2. Subir al Secret Manager
gcloud secrets versions add bessai-edge-sa-key-dev \
  --data-file=new-key.json

# 3. Actualizar variable de entorno y reiniciar
#    (o usar referencia a Secret Manager en docker-compose)
docker compose -f infrastructure/docker/docker-compose.yml restart gateway

# 4. Eliminar el archivo local
rm new-key.json

# 5. Listar versiones activas (revocar la anterior después de validar)
gcloud secrets versions list bessai-edge-sa-key-dev

# 6. Deshabilitar versión anterior
gcloud secrets versions disable VERSION_ID --secret=bessai-edge-sa-key-dev
```

---

## 4. Diagnóstico de Errores Comunes

### Error: `SAFETY_BLOCK` frecuente

**Síntomas:** Logs con `level=CRITICAL event=SAFETY_BLOCK`

**Investigar:**
```bash
docker logs bessai-gateway 2>&1 | grep "SAFETY_BLOCK" | tail -20
```

**Causas posibles:**
| Causa | Señal | Acción |
|---|---|---|
| SOC < 5% | `soc < 5.0` | Revisar estado de carga del BESS |
| SOC > 98% | `soc > 98.0` | BESS completamente cargado — normal |
| Temperatura alta | `temp > 45.0` | Revisar sistema de enfriamiento |

### Error: `ModbusReadError` / `ConnectionError`

**Síntomas:** Logs con `ModbusReadError` o `ConnectionRefusedError`

```bash
# Verificar conectividad de red
docker exec bessai-gateway ping -c 3 $INVERTER_IP

# Verificar puerto 502
docker exec bessai-gateway python -c "
import socket
s = socket.create_connection(('$INVERTER_IP', 502), timeout=5)
print('Puerto 502: OK')
s.close()
"
```

### Error: Pub/Sub no recibe mensajes

```bash
# Verificar credenciales GCP
docker exec bessai-gateway python -c "
import google.auth
credentials, project = google.auth.default()
print(f'Project: {project}')
print(f'Credentials: {type(credentials).__name__}')
"

# Verificar conectividad a GCP
docker exec bessai-gateway curl -s https://pubsub.googleapis.com/ | head -5
```

### Error: OTel Collector desconectado

```bash
# Verificar que el collector acepta conexiones
curl -s http://localhost:8888/metrics | grep otelcol_receiver_accepted_spans
```

---

## 5. Actualización (Rolling Update)

```bash
# 1. Bajar imagen nueva
docker pull YOUR_REGION-docker.pkg.dev/YOUR_PROJECT/bessai/bessai-edge-gateway:latest

# 2. Recrear solo el gateway (sin afectar OTel Collector)
docker compose -f infrastructure/docker/docker-compose.yml up -d --no-deps gateway

# 3. Verificar estado
docker compose -f infrastructure/docker/docker-compose.yml ps
docker logs --tail 50 bessai-gateway
```

---

## 6. Protocolo de Emergencia — Loss of Communications

Si el gateway pierde conectividad cloud **durante más de 5 minutos**:

1. El `SafetyGuard.watchdog_loop()` sigue escribiendo el heartbeat local → **BESS no se detiene**.
2. Pub/Sub acumula mensajes en el buffer local de `gcloud-aio-pubsub` → se enviarán al recuperar conexión.
3. OTel Collector opera en modo `memory_limiter` → dropping de telemetría no crítica.

**No se requiere intervención humana** para pérdidas < 30 minutos.

Para pérdidas > 30 minutos:
```bash
# Reiniciar el stack para limpiar buffers acumulados
docker compose -f infrastructure/docker/docker-compose.yml restart
```

---

## 7. Backup de Configuración

Los únicos archivos que deben copiarse para restituir el servicio en un equipo nuevo:

```bash
# En el servidor de producción
config/.env                              # Credenciales — almacenar en Secret Manager
registry/huawei_sun2000.json            # Perfil del dispositivo — en el repo
infrastructure/docker/docker-compose.yml # Stack — en el repo
```

> ⚠️ **NUNCA** commitear `config/.env` al repositorio.

---

## 8. Contactos de Escalación

| Rol | Responsabilidad | Contacto |
|---|---|---|
| Ingeniería de Software | Gateway, CI/CD, cloud | ingenieria@bess-solutions.cl |
| Operaciones BESS | Inversor, hardware | operaciones@bess-solutions.cl |
| SRE / Infra | GCP, Terraform, OTel | sre@bess-solutions.cl |
