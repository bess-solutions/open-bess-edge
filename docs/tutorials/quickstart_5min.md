# ⚡ Quickstart: BESSAI en 5 Minutos (sin hardware)

> **Objetivo:** Tener BESSAI Edge Gateway corriendo localmente, publicando métricas reales y visible en Grafana — **sin necesitar un inversor físico**.

---

## Requisitos

| Herramienta | Versión mínima | ¿Cómo verificar? |
|---|---|---|
| Docker Desktop | 24.x | `docker --version` |
| Docker Compose | 2.x | `docker compose version` |
| Git | 2.40+ | `git --version` |

Eso es todo. **No necesitas Python, inversores ni credenciales de nube.**

---

## Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge
```

## Paso 2 — Levantar el stack completo (1 comando)

```bash
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator \
  --profile monitoring \
  up --build -d
```

Esto levanta **4 contenedores** automáticamente:

| Contenedor | Rol | Puerto |
|---|---|---|
| `bessai-modbus-simulator` | Simula un inversor Huawei SUN2000 con datos reales | interno |
| `bessai-gateway-sim` | Gateway BESSAI conectado al simulador | `8000` |
| `bessai-prometheus` | Scraping de métricas cada 15s | `9090` |
| `bessai-grafana` | Dashboard visual | `3000` |

> **Primera vez:** La descarga de imágenes tarda ~2-3 min. Las siguientes veces es instantáneo gracias al cache de Docker.

## Paso 3 — Verificar que todo está vivo

```bash
# Health check del gateway
curl http://localhost:8000/health
# Esperado: {"status": "ok", "uptime_s": ..., "site_id": "SITE-SIM-001"}

# Ver ciclos activos en métricas
curl http://localhost:8000/metrics | grep bess_cycles_total
```

## Paso 4 — Abrir Grafana

Navega a **http://localhost:3000** en tu navegador.

- **Usuario:** `admin`
- **Contraseña:** valor de `GF_SECURITY_ADMIN_PASSWORD` en tu `config/.env`
  > Si es la primera vez, el valor por defecto del `.env.example` está indicado ahí como guía.

Deberías ver el dashboard **BESSAI Main** con:
- 📊 SOC (State of Charge) en tiempo real
- ⚡ Potencia activa (kW) desde el simulador
- 🔍 AI-IDS anomaly score
- 💰 Métricas de arbitraje

![BESSAI Grafana Dashboard](../media/grafana_dashboard.png)

## Paso 5 — Detener el stack

```bash
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator --profile monitoring \
  down
```

---

## ¿Qué sigue?

| Quiero... | Lee esto |
|---|---|
| Conectar a un inversor real | [`docs/local_development.md`](../local_development.md) |
| Publicar a MQTT / Home Assistant | [`docs/tutorials/integration_homeassistant.md`](integration_homeassistant.md) |
| Deploy en Raspberry Pi 4/5 | [`docs/quickstart_rpi.md`](../quickstart_rpi.md) |
| Entender la arquitectura completa | [`docs/architecture.md`](../architecture.md) |

---

## Solución de problemas comunes

**El gateway no conecta al simulador:**
```bash
docker compose logs bessai-gateway-sim --tail=20
# Si ves "Connection refused": espera 10s más, el simulador tarda en iniciar
```

**Puerto 3000 ya en uso:**
```bash
# Cambiar puerto de Grafana editando docker-compose.yml:
# ports: ["3001:3000"]
```

**Grafana muestra "No data":**
```bash
# Verificar que Prometheus scrapeó métricas:
curl http://localhost:9090/api/v1/query?query=up
```

---

> 💡 **Tip:** El simulador genera datos variados (SOC 20-95%, potencia ±500kW) para que los dashboards se vean con actividad real desde el primer minuto.
