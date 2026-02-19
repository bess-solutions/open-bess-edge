# 📊 BESSAI Edge Gateway — Estado del Proyecto

> **Actualizado:** 2026-02-19 v0.4.0-dev · **Responsable:** Equipo TCI-GECOMP  
> *Actualiza este archivo cada vez que avances una fase.*

---

## 🎯 ¿Qué es BESSAI?

Sistema industrial de gestión de baterías (BESS) con inteligencia artificial. Conecta inversores reales (Huawei SUN2000) vía Modbus TCP, valida la operación de forma segura, y publica telemetría a la nube (GCP) con observabilidad completa.

**Visión a largo plazo:** Evolucionar a una plataforma de energía distribuida de escala planetaria (VPP, Edge AI, P2P Trading, LCA).  
Ver roadmap completo: [`docs/bessai_v2_roadmap.md`](docs/bessai_v2_roadmap.md)

---

## ✅ Estado Actual — v0.4.0-dev

### Tests
```
45 / 45 passed ✅   (6.6s · Python 3.14.2 · pymodbus 3.12)
```

### Módulos implementados

| Módulo | Archivo | Estado |
|---|---|---|
| Configuración | `src/core/config.py` | ✅ Completo |
| Seguridad (SOC / Temp) | `src/core/safety.py` | ✅ Completo |
| Orquestador principal | `src/core/main.py` | ✅ Completo |
| Driver Modbus TCP | `src/drivers/modbus_driver.py` | ✅ Compatible pymodbus 3.12 |
| Publicador GCP Pub/Sub | `src/interfaces/pubsub_publisher.py` | ✅ Completo |
| Observabilidad (OTel) | `src/interfaces/otel_setup.py` | ✅ Completo |
| Perfil Huawei SUN2000 | `registry/huawei_sun2000.json` | ✅ Completo |
| Docker Compose + Simulador | `infrastructure/docker/` | ✅ Con profile `simulator` |
| Tests unitarios | `tests/` | ✅ 45/45 |
| **GitHub Actions CI/CD** | `.github/workflows/` | ✅ `ci.yml` + `release.yml` |
| **Terraform GCP** | `infrastructure/terraform/` | ✅ Pub/Sub + IAM + WIF |
| **Simulador Modbus** | `infrastructure/docker/modbus-simulator-config.json` | ✅ Registros SUN2000 simulados |
| **Documentación técnica** | `docs/` | ✅ Roadmap + Runbook + ADRs |

### Bloqueadores activos

| # | Bloqueador | Acción requerida |
|---|---|---|
| 🔴 1 | Docker Desktop no instalado | Instalar manualmente |
| 🔴 2 | `config/.env` no existe | Copiar `.env.example` y completar `SITE_ID` e `INVERTER_IP` |
| 🟡 3 | GCP Project ID pendiente | Configurar `GCP_PROJECT_ID` y ejecutar `terraform apply` |
| 🟡 4 | GitHub Secrets pendientes | Agregar `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, `GCP_REGION`, `GCP_PROJECT_ID` en Settings del repo |

---

## 🗺️ Roadmap

```
v0.3.0  ████████████████████████
        Tests 45/45 ✅ · Python 3.14 · pymodbus 3.12

FASE 1  ████████████████████████  HOY ──────────────────────────────►
        ✅ GitHub Actions CI/CD  (ci.yml + release.yml)
        ✅ Terraform GCP         (Pub/Sub + IAM + WIF + Artifact Registry)
        ✅ Simulador Modbus       (docker-compose profile simulator)
        ✅ Docs                   (roadmap + runbook + architecture ADRs)
        ⏳ terraform apply        (pendiente credenciales GCP reales)
        ⏳ GitHub Secrets         (pendiente configurar en el repo)

FASE 2  ░░░░░░░░   Q3 2026
        ░░░░░░░░   Edge AI: ONNX Runtime (inferencia offline)
        ░░░░░░░░   AI-IDS: detección de intrusiones Modbus
        ░░░░░░░░   DRL Training: Ray RLlib (PPO/SAC)

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
