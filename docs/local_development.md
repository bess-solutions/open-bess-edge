# Guía de Desarrollo Local — BESSAI Edge Gateway

> Última actualización: 2026-02-19 · v0.4.1

Esta guía explica cómo configurar, ejecutar y verificar el entorno de desarrollo local completo para el **BESSAI Edge Gateway**, incluyendo el simulador Modbus, los endpoints de observabilidad y el stack de monitoreo.

---

## Requisitos Previos

| Herramienta | Versión mínima | Instalación |
|---|---|---|
| Python | 3.10+ | [python.org](https://www.python.org/) |
| Docker Desktop | 24.x | [docker.com](https://www.docker.com/products/docker-desktop/) |
| Git | 2.40+ | [git-scm.com](https://git-scm.com/) |
| Terraform (opcional) | 1.7+ | [terraform.io](https://www.terraform.io/) |

---

## 1. Setup Inicial

```powershell
# Clonar el repositorio
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# Crear entorno virtual
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell

# Instalar dependencias
pip install -r requirements.txt -r requirements-dev.txt

# Crear archivo .env desde la plantilla
Copy-Item config\.env.example config\.env
# Editar config/.env si necesitas cambiar valores
```

---

## 2. Ejecutar Tests Unitarios

Los tests no requieren Docker ni hardware real:

```powershell
# Suite completa
pytest tests/ -v --tb=short

# Esperado: 55+ passed en ~8s ✅

# Con cobertura de código
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# Solo un módulo específico
pytest tests/test_config.py -v
pytest tests/test_health.py -v
pytest tests/test_safety.py -v
pytest tests/test_modbus_driver.py -v
```

---

## 3. Stack Docker — Modo Simulador

El modo simulador levanta **4 contenedores** sin necesitar hardware BESS real:

```powershell
# Levantar el stack completo con simulador
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator up --build -d

# Verificar que todos los contenedores están healthy
docker ps

# Ver logs del gateway
docker logs bessai-gateway-sim -f

# Ver logs del simulador Modbus
docker logs bessai-modbus-simulator -f
```

### Contenedores esperados

| Contenedor | Status | Puerto |
|---|---|---|
| `bessai-modbus-simulator` | ✅ healthy | `localhost:5020` |
| `bessai-gateway-sim` | ✅ running | `localhost:8000` |
| `bessai-gateway` | ✅ running | — |
| `bessai-otel-collector` | ✅ running | `localhost:4317`, `4318`, `8888` |

---

## 4. Endpoints de Salud y Métricas

El gateway expone dos endpoints HTTP en el puerto `8000`:

### GET /health

```powershell
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "site_id": "SITE-SIM-001",
  "version": "0.4.1",
  "uptime_s": 42.1,
  "last_cycle": 8,
  "safety_status": "ok"
}
```

| Campo | Descripción |
|---|---|
| `status` | `healthy` (HTTP 200) o `degraded` (HTTP 503) |
| `last_cycle` | Ciclos de adquisición completados |
| `safety_status` | `ok`, `BLOCKED` o `unknown` |

### GET /metrics

```powershell
Invoke-WebRequest http://localhost:8000/metrics | Select-Object -ExpandProperty Content
```

Métricas disponibles:

| Métrica | Tipo | Descripción |
|---|---|---|
| `bess_cycles_total` | Counter | Ciclos de adquisición completados |
| `bess_safety_blocks_total` | Counter | Bloqueos del safety guard |
| `bess_publish_errors_total` | Counter | Fallos de publicación GCP Pub/Sub |
| `bess_last_soc_percent` | Gauge | Último SOC (%) leído |
| `bess_last_power_kw` | Gauge | Última potencia activa (kW) |
| `bess_last_cycle_duration_seconds` | Gauge | Duración del último ciclo |
| `bess_gateway_info` | Gauge | Info estática (version, site_id) |

---

## 5. Stack de Monitoreo (Prometheus + Grafana)

Para visualizar métricas históricas, agrega el perfil `monitoring`:

```powershell
docker compose -f infrastructure/docker/docker-compose.yml `
  --profile simulator --profile monitoring up --build -d
```

Contenedores adicionales:

| Contenedor | URL | Credenciales |
|---|---|---|
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / bessai |

### En Grafana:
1. Abre http://localhost:3000
2. La datasource **Prometheus** ya está pre-configurada automáticamente
3. En **Explore**, usa `bess_` para filtrar todas las métricas del gateway
4. Importa un dashboard de [grafana.com](https://grafana.com/grafana/dashboards/) usando el ID de Prometheus

---

## 6. Detener el Stack

```powershell
# Detener todos los contenedores (mantiene volúmenes)
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring down

# Detener y eliminar volúmenes (reset completo)
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring down -v
```

---

## 7. Variables de Entorno Clave

Ver la plantilla completa en [`config/.env.example`](../config/.env.example).

| Variable | Default | Descripción |
|---|---|---|
| `SITE_ID` | — | ID único de la instalación (**requerido**) |
| `INVERTER_IP` | — | IP o hostname del inversor (**requerido**) |
| `INVERTER_PORT` | `502` | Puerto Modbus TCP |
| `HEALTH_PORT` | `8000` | Puerto del servidor /health y /metrics |
| `WATCHDOG_TIMEOUT` | `5` | Segundos entre ciclos de adquisición |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
| `GCP_PROJECT_ID` | `None` | ID proyecto GCP (solo producción) |
| `GCP_PUBSUB_TOPIC` | `None` | Tópico Pub/Sub (solo producción) |

---

## 8. Flujo de CI Local

Antes de hacer push, verifica que todo pase:

```powershell
# 1. Lint
pip install ruff
ruff check src/ tests/
ruff format --check src/ tests/

# 2. Type check
mypy src/ --ignore-missing-imports

# 3. Tests
pytest tests/ -v --tb=short

# 4. Docker build
docker build -f infrastructure/docker/Dockerfile -t bessai-edge-gateway:test .

# 5. Terraform validate (opcional)
terraform -chdir=infrastructure/terraform init -backend=false
terraform -chdir=infrastructure/terraform validate
```

---

## 9. Estructura de Archivos Relevantes

```
open-bess-edge/
├── src/
│   ├── core/
│   │   ├── config.py          ← Settings (pydantic-settings)
│   │   ├── safety.py          ← Safety guard (SOC/Temp limits)
│   │   └── main.py            ← Acquisition loop + health server
│   ├── drivers/
│   │   └── modbus_driver.py   ← Modbus TCP (pymodbus 3.12)
│   └── interfaces/
│       ├── health.py          ← GET /health + GET /metrics server
│       ├── metrics.py         ← Prometheus counters/gauges
│       ├── pubsub_publisher.py← GCP Pub/Sub publisher
│       └── otel_setup.py      ← OpenTelemetry setup
├── config/
│   ├── .env.example           ← Plantilla (copiar a .env)
│   └── .env                   ← Variables locales (no commiteado)
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile
│   │   ├── docker-compose.yml ← Perfiles: default, simulator, monitoring
│   │   └── otel-collector-config.yaml
│   ├── prometheus/
│   │   └── prometheus.yml     ← Scrape config (Gateway + OTel)
│   ├── grafana/
│   │   └── provisioning/      ← Auto-provisioning de datasources
│   └── terraform/             ← IaC para GCP (Pub/Sub + IAM + WIF)
└── tests/
    ├── test_config.py
    ├── test_safety.py
    ├── test_modbus_driver.py
    └── test_health.py         ← Tests del servidor /health + /metrics
```
