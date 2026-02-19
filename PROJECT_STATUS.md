# 📊 BESSAI Edge Gateway — Estado del Proyecto

> **Actualizado:** 2026-02-19 v0.6.0 · **Responsable:** Equipo TCI-GECOMP  
> *Actualiza este archivo cada vez que avances una fase.*

---

## 🎯 ¿Qué es BESSAI?

Sistema industrial de gestión de baterías (BESS) con inteligencia artificial. Conecta inversores reales (Huawei SUN2000) vía Modbus TCP, valida la operación de forma segura, y publica telemetría a la nube (GCP) con observabilidad completa.

**Visión a largo plazo:** Evolucionar a una plataforma de energía distribuida de escala planetaria (VPP, Edge AI, P2P Trading, LCA).  
Ver roadmap completo: [`docs/bessai_v2_roadmap.md`](docs/bessai_v2_roadmap.md)

---

## ✅ Estado Actual — v0.6.0

### Tests
```
73 / 73 passed ✅   (11.89s · Python 3.14 · pytest-asyncio 1.3.0)
```

### Módulos implementados

| Módulo | Archivo | Estado |
|---|---|---|
| Configuración | `src/core/config.py` | ✅ Completo — acepta IPs y hostnames, `HEALTH_PORT=8000` |
| Seguridad (SOC / Temp) | `src/core/safety.py` | ✅ Completo |
| Orquestador principal | `src/core/main.py` | ✅ Integrado con HealthServer + métricas Prometheus |
| Driver Modbus TCP | `src/drivers/modbus_driver.py` | ✅ Compatible pymodbus 3.12 |
| Servidor /health y /metrics | `src/interfaces/health.py` | ✅ aiohttp, GET /health (JSON) + GET /metrics |
| Prometheus metrics registry | `src/interfaces/metrics.py` | ✅ **AMPLIADO v0.6.0** — 11 métricas (+ 4 AI) |
| **AI-IDS** | `src/interfaces/ai_ids.py` | ✅ **NUEVO** — IsolationForest + z-score, score 0-1, alertas |
| **ONNX Dispatcher** | `src/interfaces/onnx_dispatcher.py` | ✅ **NUEVO** — inferencia offline, fallback seguro |
| **Modelo ONNX dummy** | `models/dispatch_policy.onnx` | ✅ **NUEVO** — `target_kw = soc × 0.8` (para tests) |
| Publicador GCP Pub/Sub | `src/interfaces/pubsub_publisher.py` | ✅ Completo |
| Observabilidad (OTel) | `src/interfaces/otel_setup.py` | ✅ Completo |
| Perfil Huawei SUN2000 | `registry/huawei_sun2000.json` | ✅ Completo |
| Docker Compose + Simulador | `infrastructure/docker/` | ✅ Perfil `monitoring` (Prometheus+Grafana) |
| Prometheus scrape config | `infrastructure/prometheus/prometheus.yml` | ✅ Activo |
| Grafana datasource provisioning | `infrastructure/grafana/provisioning/` | ✅ Activo |
| Terraform GCP | `infrastructure/terraform/` | ✅ `apply` ejecutado — 18 recursos en GCP |
| pyproject.toml | `pyproject.toml` | ✅ ruff/mypy/pytest/coverage centralizados |
| Tests unitarios | `tests/` | ✅ **73/73** (inc. 11 AI-IDS + 8 ONNX tests) |
| GitHub Actions CI/CD | `.github/workflows/` | ✅ lint → test → tf-validate → docker-push |
| Guía desarrollo local | `docs/local_development.md` | ✅ Completo |

### 🐳 Stack Docker — OPERATIVO

```powershell
# Modo simulador básico:
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator up --build -d

# Con stack de monitoreo (Prometheus + Grafana):
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring up --build -d
```

| Contenedor | Estado | Puerto |
|---|---|---|
| `bessai-modbus-simulator` | ✅ healthy | `host:5020` → `container:502` |
| `bessai-gateway` | ✅ running | **`8000`** (/health, /metrics) |
| `bessai-gateway-sim` | ✅ running | **`8000`** (/health, /metrics) |
| `bessai-otel-collector` | ✅ running | 4317, 4318, 8888 |
| `bessai-prometheus` (monitoring) | disponible | **`9090`** |
| `bessai-grafana` (monitoring) | disponible | **`3000`** (admin/bessai) |

### Bloqueadores activos

| # | Bloqueador | Acción requerida |
|---|---|---|
| ✅ ~~1~~ | ~~Docker Desktop no instalado~~ | **RESUELTO** — Docker v4.61.0 operativo |
| ✅ ~~2~~ | ~~`config/.env` no existe~~ | **RESUELTO** — `.env` creado con simulador |
| ✅ ~~3~~ | ~~GCP Project ID pendiente~~ | **RESUELTO** — `terraform apply` ejecutado, 18 recursos en GCP |
| ✅ ~~4~~ | ~~GitHub Secrets pendientes~~ | **RESUELTO** — 4 secrets configurados en Actions |

> 🎉 **Sin bloqueadores activos** — el pipeline completo (lint → test → tf-validate → docker-push) está operativo.

---

## 🗺️ Roadmap

```
v0.3.0  ████████████████████████
        Tests 45/45 ✅ · Python 3.14 · pymodbus 3.12

FASE 1  ████████████████████████  ✅ COMPLETADO — 2026-02-19 ►
        ✅ GitHub Actions CI/CD  (ci.yml + release.yml)
        ✅ Terraform GCP         (Pub/Sub + IAM + WIF + Artifact Registry)
        ✅ Simulador Modbus       (docker-compose profile simulator) — healthy
        ✅ Docker stack           (4 contenedores operativos)
        ✅ Docs                   (roadmap + runbook + architecture ADRs)

FASE 2  ████████████████████████  ✅ COMPLETADO — 2026-02-19 ►
        ✅ GET /health (JSON)       src/interfaces/health.py
        ✅ GET /metrics (Prometheus) src/interfaces/metrics.py
        ✅ pyproject.toml           ruff + mypy + pytest + coverage centralizados
        ✅ Tests /health + /metrics  9 nuevos tests (54 total)
        ✅ Monitoring stack          Prometheus + Grafana via --profile monitoring
        ✅ Terraform backend.tf      GCS remote state listo para activar
        ✅ CI terraform-validate     sin credenciales GCP
        ✅ docs/local_development.md guía de desarrollo completa
        ✅ terraform apply            ejecutado — 18 recursos en gen-lang-client-0752731192
        ✅ GitHub Secrets             4 secrets configurados en Actions

FASE 3  ████████░░░░░░░░   Q3 2026 — EN PROGRESO
        ✅ ONNX Inference Engine     src/interfaces/onnx_dispatcher.py
        ✅ AI-IDS (IsolationForest)  src/interfaces/ai_ids.py
        ✅ Modelo ONNX dummy         models/dispatch_policy.onnx
        ░░░░░░░░   DRL Training: Ray RLlib (PPO/SAC) + Gymnasium
        ░░░░░░░░   Federated Learning (Flower/PySyft)

FASE 3  ░░░░░░░░   Q4 2026
        ░░░░░░░░   VPP: Virtual Power Plant (OpenADR 3.0)
        ░░░░░░░░   Federated Learning (Flower)

FASE 4  ░░░░░░░░   Q1 2027
        ░░░░░░░░   Data Lakehouse Global (Delta Lake + Iceberg)
        ░░░░░░░░   P2P Energy Trading (Hyperledger Fabric)

FASE 5  ░░░░░░░░   Q2 2027
        ░░░░░░░░   LCA Engine (huella de carbono en tiempo real)
        ░░░░░░░░   Carbon Dashboard (CO₂ evitado, vida útil extendida)
```

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    BESSAI Edge Gateway                   │
│                                                         │
│  [BESS / Inversor]                                      │
│       │ Modbus TCP (pymodbus 3.12)                      │
│       ▼                                                  │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  UniversalDriver  │  SafetyGuard │                   │
│  │  (struct I/O)│    │  SOC + Temp  │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                           │
│         └────────┬──────────┘                           │
│                  ▼                                       │
│           ┌─────────────┐                               │
│           │ Orquestador │ ← config.py (pydantic-settings)│
│           │  main.py    │                               │
│           └──────┬──────┘                               │
│                  │                                       │
│       ┌──────────┴──────────┐                           │
│       ▼                     ▼                           │
│  [GCP Pub/Sub]        [OTel Collector]                  │
│  (telemetría JSON)    (trazas + métricas)               │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura del Repositorio

```
open-bess-edge/
├── 📄 README.md                     ← Documentación principal
├── 📄 PROJECT_STATUS.md             ← ESTE ARCHIVO
├── 📄 CHANGELOG.md                  ← Historial + AGENT HANDOFF
├── 📄 requirements.txt              ← Dependencias de producción
├── 📄 requirements-dev.txt          ← Dependencias de desarrollo
├── 📄 pytest.ini                    ← Config de tests
│
├── 📂 src/
│   ├── 📂 core/
│   │   ├── config.py               ← Settings (pydantic-settings)
│   │   ├── safety.py               ← Guard de seguridad
│   │   └── main.py                 ← Orquestador principal
│   ├── 📂 drivers/
│   │   └── modbus_driver.py        ← Driver Modbus TCP universal
│   └── 📂 interfaces/
│       ├── pubsub_publisher.py     ← GCP Pub/Sub async
│       └── otel_setup.py           ← OpenTelemetry bootstrap
│
├── 📂 registry/
│   └── huawei_sun2000.json         ← Perfil del dispositivo
│
├── 📂 config/
│   └── .env.example                ← Template de variables de entorno
│
├── 📂 tests/
│   ├── conftest.py                 ← Fixtures globales
│   ├── test_config.py              ← 15 tests
│   ├── test_safety.py              ← 16 tests
│   └── test_modbus_driver.py       ← 14 tests
│
├── 📂 infrastructure/
│   ├── 📂 docker/
│   │   ├── Dockerfile              ← Multi-stage, non-root
│   │   ├── docker-compose.yml      ← Stack completo
│   │   └── otel-collector-config.yaml
│   └── 📂 terraform/               ← ⚠️ VACÍO — pendiente
│
└── 📂 docs/
    └── bessai_v2_roadmap.md        ← Roadmap técnico v2.0
```

---

## 🔑 Variables de Entorno Clave

```bash
# Mínimas para ejecutar
SITE_ID=SITE-CL-001
INVERTER_IP=192.168.1.100

# GCP (producción)
GCP_PROJECT_ID=my-bess-project
GCP_PUBSUB_TOPIC=bess-telemetry
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcp-key.json

# Opcionales
INVERTER_PORT=502
WATCHDOG_TIMEOUT=5
LOG_LEVEL=INFO
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

---

## 🚀 Validación rápida (sin hardware)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v --tb=short
# 45 passed ✅
```

---

## 📌 Historial de Actualizaciones de este archivo

| Fecha | Versión | Cambio |
|---|---|---|
| 2026-02-19 | v0.3.0 | Creación inicial. Tests 45/45, Python 3.14, pymodbus 3.12 |
| 2026-02-19 | v0.4.0-dev | CI/CD (GitHub Actions), Terraform GCP (Pub/Sub + IAM + WIF), simulador Modbus, docs (roadmap + runbook + ADRs) |
| 2026-02-19 | v0.4.1 | Docker stack operativo. Fix: `INVERTER_IP` acepta hostnames, healthcheck puerto 5020, tests herméticos con `_env_file=None` |
