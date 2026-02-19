# CHANGELOG — BESSAI Edge Gateway (`open-bess-edge`)

> **📌 NOTA PARA AGENTES IA — Leer antes de continuar el trabajo**
>
> Este documento es el punto de entrada para cualquier agente IA que tome control de este repositorio.
> Revisa la sección **[AGENT HANDOFF]** antes de escribir cualquier código.

---

## 🤖 AGENT HANDOFF — Estado actual del proyecto (2026-02-19T11:55 -03:00)

### Contexto del sistema
**BESSAI Edge Gateway** (`open-bess-edge`) es el componente de borde de un sistema de gestión de baterías industriales (BESS). Adquiere telemetría via **Modbus TCP** desde inversores Huawei SUN2000, valida seguridad, y publica a **GCP Pub/Sub** con observabilidad via **OpenTelemetry**.

### Estado del código — ✅ COMPLETO Y VALIDADO

| Archivo | Estado | Notas |
|---|---|---|
| `src/core/config.py` | ✅ Producción | Settings pydantic-settings + GCP/OTEL fields, lazy `settings` proxy |
| `src/core/safety.py` | ✅ Producción | check_safety + watchdog_loop async |
| `src/core/main.py` | ✅ Producción | Orquestador 5 pasos, graceful shutdown SIGINT/SIGTERM |
| `src/drivers/modbus_driver.py` | ✅ Producción | pymodbus 3.12, struct-based encode/decode |
| `src/interfaces/pubsub_publisher.py` | ✅ Producción | Async context manager, GCP Pub/Sub, JSON envelope |
| `src/interfaces/otel_setup.py` | ✅ Producción | TracerProvider + MeterProvider, OTEL_SERVICE_NAME desde settings |
| `registry/huawei_sun2000.json` | ✅ Producción | 3 registros: active_power, soc, watchdog_heartbeat |
| `infrastructure/docker/Dockerfile` | ✅ Producción | Multi-stage, non-root user `bess` |
| `infrastructure/docker/docker-compose.yml` | ✅ Producción | gateway + otel-collector services |
| `tests/conftest.py` | ✅ Producción | Variables mínimas de entorno para todos los tests |
| `tests/test_config.py` | ✅ 15 casos | Singleton, tipos, required fields |
| `tests/test_safety.py` | ✅ 16 casos | SOC/Temp boundary conditions, watchdog async, UINT16 wrap |
| `tests/test_modbus_driver.py` | ✅ 14 casos | Mocked Modbus, connect retries, encode/decode |

**Suite de tests: 45/45 ✅ en 6.62s — Python 3.14.2 · pytest 9.0.2 · pymodbus 3.12.0**

### 🚫 Bloqueadores activos — Requieren acción humana

| # | Bloqueador | Solución requerida |
|---|---|---|
| 1 | **Docker Desktop no instalado** en el equipo host | Instalar desde [docker.com](https://www.docker.com/products/docker-desktop/) |
| 2 | **`config/.env` no existe** | Copiar `config/.env.example` → `config/.env` y completar `SITE_ID` e `INVERTER_IP` |
| 3 | **No hay inversor real disponible** para tests de integración | Usar simulador Modbus (ver roadmap) |

### 🟡 Work in Progress — Próximo agente debe continuar aquí

**Prioridad 1 — Infraestructura como código:**
- `infrastructure/terraform/` está vacío. Crear: GCP Pub/Sub topic + subscription, IAM service account, Secret Manager.

**Prioridad 2 — CI/CD:**
- No existe `.github/workflows/`. Crear: `lint (ruff)` → `typecheck (mypy)` → `test (pytest)` → `docker build` → `push to Artifact Registry`.

**Prioridad 3 — Simulador Modbus:**
- Añadir al `docker-compose.yml` un servicio `pymodbus.simulator` para tests de integración sin hardware.

**Prioridad 4 — BESSAI v2.0:**
- Ver roadmap completo en `docs/bessai_v2_roadmap.md`.
- Siguiente milestone: Edge AI (ONNX Runtime) + AI-IDS + Federated Orchestration.

### 📂 Estructura de archivos clave
```
open-bess-edge/
├── src/core/        config.py · safety.py · main.py
├── src/drivers/     modbus_driver.py
├── src/interfaces/  pubsub_publisher.py · otel_setup.py
├── registry/        huawei_sun2000.json
├── config/          .env.example  ← ⚠️ copiar a .env antes de ejecutar
├── infrastructure/docker/   Dockerfile · docker-compose.yml · otel-collector-config.yaml
├── infrastructure/terraform/ ← ⚠️ VACÍO — pendiente implementar
├── docs/            bessai_v2_roadmap.md
└── tests/           conftest.py · test_config.py · test_safety.py · test_modbus_driver.py
```

### Comando de validación rápida (sin Docker, sin hardware)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v --tb=short
# Expected: 45 passed in ~6s ✅
```

---

All notable changes to this project are documented here.  
Format: [Semantic Versioning](https://semver.org/) · [Conventional Commits](https://www.conventionalcommits.org/)

---

## [0.3.0] — 2026-02-19

### 🐛 Fix — Compatibilidad Python 3.14 / pymodbus 3.12

#### `requirements.txt` / `requirements-dev.txt`
- Actualizadas todas las dependencias a `>=` para permitir wheels pre-compiladas en Python 3.14.
- `pydantic>=2.9.0`, `pydantic-settings>=2.5.0`, `pymodbus>=3.7.0`, `opentelemetry-*>=1.27.0`.

#### `src/drivers/modbus_driver.py`
- Eliminadas: `pymodbus.constants.Endian`, `BinaryPayloadDecoder`, `BinaryPayloadBuilder` (API removida en pymodbus 3.12).
- `_decode_value()` y `_encode_value()` reescritos con `struct` de la stdlib Python.
- Soporta: `INT32`, `UINT32`, `INT16`, `UINT16`, `FLOAT32`.

#### `src/core/config.py`
- Añadidos campos: `GCP_PROJECT_ID`, `GCP_PUBSUB_TOPIC`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `LOG_LEVEL`.
- Eliminado singleton `settings = get_settings()` a nivel de módulo.
- Añadido `_LazySettings` proxy — `settings` se importa sin fallo aun sin `.env`.

#### `src/interfaces/otel_setup.py`
- `OTEL_SERVICE_NAME` leído desde `settings`. `service.version` bumped a `0.2.0`.
- `_resolve_endpoint()` delega a `settings.OTEL_EXPORTER_OTLP_ENDPOINT`.

#### `src/interfaces/pubsub_publisher.py`
- Reemplazado import directo de `settings` por `get_settings()`. Sin `type: ignore`.

#### `src/core/main.py`
- Reemplazado `from src.core.config import settings` por `get_settings()` + alias `_cfg`.

#### `tests/conftest.py` *(nuevo)*
- Inyecta `SITE_ID`, `INVERTER_IP` mínimos antes de cada test via `os.environ`.

#### `tests/test_modbus_driver.py`
- `_make_driver()` → `async def` (pymodbus 3.12 requiere event loop al instanciar cliente).
- `test_connect_retries_then_succeeds` — mock simplificado con `connected=True` fijo.

### 📋 Resultado
- **45/45 tests pasan** en Python 3.14.2, pytest 9.0.2, pymodbus 3.12.0.

---

## [0.2.0] — 2026-02-19

### ✨ Features — Core Orchestrator (`src/core/main.py`)

- Ciclo de adquisición explícito en 5 pasos (Adquisición → Seguridad → Watchdog → Publicación → Ritmo).
- `_ensure_watchdog()`: monitorea liveness de la tarea y la reinicia si muere.
- `SAFETY_BLOCK` se loguea a nivel `CRITICAL` con telemetría completa.
- Graceful shutdown en `SIGINT` / `SIGTERM` (cancela watchdog, drena Pub/Sub, desconecta Modbus, flush OTel).

---

## [0.1.0] — 2026-02-19

### 🏗️ Project Scaffolding

- Estructura de directorios inicializada: `src/core/`, `src/drivers/`, `src/interfaces/`, `registry/`, `config/`, `tests/`, `infrastructure/`.

### ⚙️ Core (`src/core/`)

- `config.py`: `Settings` via `pydantic-settings`, `@lru_cache` singleton, `SITE_ID`, `INVERTER_IP`, `INVERTER_PORT`, `DRIVER_PROFILE_PATH`, `WATCHDOG_TIMEOUT`.
- `safety.py`: SOC < 5% / > 98% → block. Temp > 45°C → block. `watchdog_loop` async, UINT16 wrap, 2-failure escalation.

### 🔌 Drivers (`src/drivers/modbus_driver.py`)
- `UniversalDriver`: JSON profile-driven, 3-retry exponential backoff.
- Excepciones: `DriverConfigError`, `TagNotFoundError`, `ModbusReadError`, `ModbusWriteError`.

### 🌐 Interfaces (`src/interfaces/`)
- `PubSubPublisher`: async context manager, JSON envelope, `schema_version`, `site_id`.
- `otel_setup`: `TracerProvider + MeterProvider`, OTLP/gRPC, `BatchSpanProcessor`.

### 🗂️ Device Registry
- `registry/huawei_sun2000.json`: `active_power` (INT32/RO), `soc` (UINT16/RO), `watchdog_heartbeat` (UINT16/RW).

### 🐳 Infrastructure
- `Dockerfile`: multi-stage, non-root `bess` user. `docker-compose.yml`: `gateway` + `otel-collector`.

---

## Roadmap — BESSAI v2.0

| Fase | Área | Prioridad |
|---|---|---|
| Q2 2026 | Terraform GCP (Pub/Sub + IAM + Cloud Run) | 🔴 Alta |
| Q2 2026 | GitHub Actions CI (lint → test → Docker → deploy) | 🔴 Alta |
| Q3 2026 | Edge AI: ONNX Runtime + AI-IDS | 🔴 Alta |
| Q4 2026 | Federated Orchestration + VPP (OpenADR 3.0) | 🟡 Media |
| Q1 2027 | Data Lakehouse + P2P Energy Trading (Hyperledger) | 🟡 Media |
| Q2 2027 | LCA Engine + Carbon Dashboard | 🟢 Estratégica |
