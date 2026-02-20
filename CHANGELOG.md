# CHANGELOG — BESSAI Edge Gateway (`open-bess-edge`)

> **📌 NOTA PARA AGENTES IA — Leer antes de continuar el trabajo**
>
> Este documento es el punto de entrada para cualquier agente IA que tome control de este repositorio.
> Revisa la sección **[AGENT HANDOFF]** antes de escribir cualquier código.

---

## 🤖 AGENT HANDOFF — Estado actual del proyecto (2026-02-20T16:10 -03:00)

> [!IMPORTANT]
> **v1.3.1 — CI verde + Mega Scraper de datos** (2026-02-20)
> - CI/CD 100% verde: ruff (lint) ✅ · mypy (type check) ✅ · pytest 228/228 ✅ · Helm ✅ · Terraform ✅
> - `sources/mega_scraper_energia_abierta.py` — 8 módulos scraper dados de alta (CMg, ERNC, generación, combustibles, CO₂, embalsada).
> - `CMgPredictor v2` + `ArbitrageEngine v2` operativos con bandas p10/p90 · Dashboard web arbitraje activo
> - Pipeline completo: mega_scraper → train_price_model.py → ONNX v2 listo para datos reales CEN



### Contexto del sistema
**BESSAI Edge Gateway** (`open-bess-edge`) es el componente de borde de un sistema de gestión de baterías industriales (BESS). Adquiere telemetría via **Modbus TCP** desde inversores Huawei SUN2000 + batería LUNA2000, valida seguridad, y publica a **GCP Pub/Sub** con observabilidad via **OpenTelemetry** y **Prometheus**.

### Estado del código — ✅ v1.0.1, DOCKER STACK OPERATIVO

| Archivo | Estado | Notas |
|---|---|---|
| `src/core/config.py` | ✅ Producción | `INVERTER_IP` acepta IPs y hostnames |
| `src/core/safety.py` | ✅ Producción | check_safety + watchdog_loop async |
| `src/core/main.py` | ✅ Producción | Integrado con HealthServer + Prometheus metrics |
| `src/core/fleet_orchestrator.py` | ✅ v0.8 | Multi-site async polling, weighted SOC, alarms |
| `src/drivers/modbus_driver.py` | ✅ Producción | pymodbus 3.12, struct-based encode/decode |
| `src/drivers/luna2000_driver.py` | ✅ **NUEVO v1.0** | LUNA2000 SOC/power/temp/mode FC03+FC06 |
| `src/interfaces/health.py` | ✅ Producción | /health (JSON) + /metrics (Prometheus) vía aiohttp |
| `src/interfaces/metrics.py` | ✅ **22 métricas** | v0.5–v0.9 — todas etiquetadas `[site_id]` |
| `src/interfaces/ai_ids.py` | ✅ Producción | IsolationForest + z-score ensemble, score 0-1 |
| `src/interfaces/onnx_dispatcher.py` | ✅ Producción | ONNX Runtime offline dispatcher, fallback gracioso |
| `src/interfaces/vpp_publisher.py` | ✅ v0.7 | VPP OpenADR 3.0: agrega flex, publica EiEvent JSON |
| `src/interfaces/fl_client.py` | ✅ v0.7 | Flower FL client: datos no salen del edge |
| `src/interfaces/fl_server.py` | ✅ v0.8 | FedAvg weighted aggregation, simulate_round() |
| `src/interfaces/lca_engine.py` | ✅ v0.8 | CO₂ avoided (IEA WEO 2024 methodology) |
| `src/interfaces/lca_config.py` | ✅ v0.8 | 40+ países grid EF DB (IEA + ENTSO-E 2024) |
| `src/interfaces/p2p_trading.py` | ✅ v0.8 | EnergyCredit (SHA-256), Hyperledger Fabric stub |
| `src/interfaces/datalake_publisher.py` | ✅ v0.8 | BigQuery streaming + JSONL fallback offline |
| `src/interfaces/dashboard_api.py` | ✅ v0.9 | REST API 6 endpoints /status /fleet /carbon /p2p |
| `src/interfaces/alert_manager.py` | ✅ v0.9 | AlertLevel fire/resolve/dedup + Prometheus |
| `src/interfaces/sun2000_monitor.py` | ✅ **NUEVO v1.0** | SUN2000 full telemetry: PV strings, AC, alarms→AlertMgr |
| `src/simulation/bess_env.py` | ✅ v0.7 | Gymnasium BESS env: obs(8), action cont., 96 steps/ep |
| `src/simulation/bess_model.py` | ✅ v0.7 | Física BESS: SOC, degradación Rainflow, térmica RC |
| `scripts/train_drl_policy.py` | ✅ v0.7 | Ray RLlib PPO training + ONNX export |
| `infrastructure/helm/bessai-edge/` | ✅ v0.7 | Helm chart completo: deploy, service, HPA, ConfigMap |
| `infrastructure/grafana/dashboards/bessai_main.json` | ✅ **NUEVO v1.0** | 13 paneles: SOC, power, PV, CO₂, alarms, fleet, FL |
| `registry/huawei_sun2000.json` | ✅ **v2.0** | 28 registros reales (32xxx PV/AC + 37xxx LUNA2000) |
| `infrastructure/terraform/` | ✅ Producción | apply ejecutado — 18 recursos en GCP |
| `.github/workflows/ci.yml` | ✅ v0.9 | 7 jobs: lint→typecheck→test→tf-validate→helm-lint→docker |

**Suite de tests: 228/228 ✅ en 10.02s — Python 3.14**

### 🐳 Stack Docker — ✅ 100% OPERATIVO (v1.0.1)

```powershell
# Modo simulador (básico)
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator up --build -d

# Con stack de monitoreo completo
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring up --build -d
```

| Contenedor | Estado | Puerto |
|---|---|---|
| `bessai-modbus-simulator` | ✅ healthy | host:5020 → container:502 |
| `bessai-gateway` | ✅ running | **8000 (/health, /metrics)** |
| `bessai-gateway-sim` | ✅ running | **8000 (/health, /metrics)** |
| `bessai-otel-collector` | ✅ running | 4317, 4318, 8888 |
| `bessai-prometheus` (monitoring) | disponible | **9090** |
| `bessai-grafana` (monitoring) | disponible | **3000** (admin/bessai) |

### ✅ Sin Bloqueadores Activos

| # | Bloqueador | Solución |
|---|---|---|
| 1 | ~~Docker Desktop no instalado~~ | ✅ **RESUELTO** — Docker v4.61.0 |
| 2 | ~~`config/.env` no existe~~ | ✅ **RESUELTO** — `.env` con simulador |
| 3 | ~~GCP Project ID pendiente~~ | ✅ **RESUELTO** — `terraform apply` ejecutado, 18 recursos GCP creados |
| 4 | ~~GitHub Secrets pendientes~~ | ✅ **RESUELTO** — 4 secrets configurados en Actions |

### 🟢 Próximo agente — Continuar aquí

**Todos los bloqueadores resueltos.** El pipeline completo está operativo.

**Próxima prioridad — BESSAI v0.8.0 (Edge AI Fase 3):**
- DRL Training real: Ray RLlib en servidor, export a ONNX, despliegue en edge
- Federated Orchestration: servidor FL con Flower, FedAvg con N>=3 sitios
- VPP real: conectar a broker OpenADR 3.0
- Ver roadmap: `docs/bessai_v2_roadmap.md` — FASE 3 50% completada

### 📂 Estructura de archivos clave
```
open-bess-edge/
├── src/core/        config.py · safety.py · main.py
├── src/drivers/     modbus_driver.py
├── src/interfaces/  pubsub_publisher.py · otel_setup.py · health.py · metrics.py
├── registry/        huawei_sun2000.json
├── config/          .env.example · .env  ← ✅ existe (GCP_PROJECT_ID configurado)
├── infrastructure/docker/    Dockerfile · docker-compose.yml · otel-collector-config.yaml
├── infrastructure/terraform/ ← ✅ apply ejecutado — 18 recursos en GCP
├── infrastructure/prometheus/ prometheus.yml
├── infrastructure/grafana/   provisioning/datasources/prometheus.yml
├── .github/workflows/       ci.yml · release.yml
├── docs/            bessai_v2_roadmap.md · runbook.md · architecture.md
└── tests/           conftest.py · test_config.py · test_safety.py · test_modbus_driver.py
```

### Comando de validación rápida (sin Docker, sin hardware)
```powershell
# Tests
pytest tests/ -v --tb=short
# Esperado: 54 passed ✅

# Health endpoint (requiere Docker)
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json

# Métricas Prometheus
Invoke-WebRequest http://localhost:8000/metrics | Select-Object -Exp Content
.venv\Scripts\Activate.ps1
pytest tests/ -v --tb=short
# Expected: 45 passed in ~6.5s ✅
```

### Comando Docker completo (con simulador)
```powershell
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator up --build -d
docker ps  # Verificar 4 contenedores: healthy/running
```

---

All notable changes to this project are documented here.  
Format: [Semantic Versioning](https://semver.org/) · [Conventional Commits](https://www.conventionalcommits.org/)

---

---

## [v1.3.1] — 2026-02-20

### Fixed
- **CI / Lint (ruff)** — 13 errores resueltos en `cmg_predictor.py` y tests:
  - `src/interfaces/cmg_predictor.py`: `Optional[X]` → `X | None` (UP045, 5 ocurrencias), strings en type annotations eliminados (UP037, 2 ocurrencias), `Optional` sin uso removido (F401)
  - `tests/test_dashboard_api_handlers.py`: imports re-ordenados (I001), `AsyncMock` sin uso removido (F401)
  - `tests/test_luna2000_driver_async.py`: mismo patrón I001 + F401
- **CI / Type check (mypy)** — `_run_session(session: object)` cambiado a `session: Any`; mypy reportaba `attr-defined` ya que `object` no tiene `.run()`

### Added
- `sources/mega_scraper_energia_abierta.py` — **Mega Scraper energiaabierta.cl + Coordinador CEN**:
  - 8 módulos: `cmg`, `cmg_prog`, `hidro`, `generacion`, `ernc`, `capacidad`, `emision`, `combustibles`
  - Output en `sources/data/{historical,market,training}/` compatible con `train_price_model.py v2`
  - Modo `--dry-run` verificado · Rate limiting · Soporte CSV/XLS/XLSX · `scraper_manifest.json`
  - Nodos: Maitencillo, Polpaico, Lo Aguirre, Cardones, Crucero, Charrua, Quillota, Hualpen

### Tests
```
228 / 228 passed (suite completa open-bess-edge)
CI verde: ruff ✅ · mypy ✅ · pytest ✅ · helm ✅ · terraform ✅
```

---

## [v1.2.0] — 2026-02-20

### Added
- `src/interfaces/cmg_predictor.py` **v2** — CMgPredictor con:
  - TTL cache 30 min en `predict_next_24h()` (evita re-cómputo redundante)
  - Soporte 11 features (`lag_168h` + `is_weekend` vs. 9 anteriores)
  - Auto-descubrimiento del modelo `_int8.onnx` para inferencia ~3× más rápida
  - Bandas de incertidumbre `cmg_p10` / `cmg_p90` via modelos cuantílicos ONNX
  - Invalidación de cache si Δprecio > umbral `_CACHE_INVALIDATE_DELTA`
  - Propiedad `is_high_confidence` y `spread_clp` en `PriceForecast`
  - Ventana de historial ampliada a 192h (8 días) para soportar `lag_168h`
  - Método `projected_arbitrage_revenue_conservative()` usando bandas p10/p90
- `src/interfaces/arbitrage_engine.py` **v2** — ArbitrageEngine con:
  - Parámetros `min_confidence=0.4` y `min_spread_clp=30.0`
  - Filtrado de horas con baja confianza → `hold` forzado, logging enriquecido
  - Guard `_all_hold_schedule()` cuando spread p10/p90 es insuficiente para operar
  - `DispatchSlot.to_dict()` expone `cmg_p10`, `cmg_p90` y `confidence`
  - `avg_confidence` y `effective_spread` en log `arbitrage_engine.schedule_computed`
- `bessai-cen-data/scripts/train_price_model.py` **v2**:
  - 11 features: agrega `lag_168h` (weekly seasonality) + `is_weekend`
  - Cuantización post-entrenamiento int8 (`onnxruntime-quantization`): ~3× más rápido en CPU
  - Quantile Regression p10/p90 exportada a ONNX separado
  - Tipos de modelo: `ridge`, `gbm` (LightGBM), `ensemble` (Ridge+LightGBM avg)
  - Flag `--all-nodos`: entrena todos los nodos SEN en batch
  - Flag `--no-quantize`: desactiva cuantización
- `bessai-cen-data/dashboard/arbitrage_dashboard.html` — Dashboard web standalone:
  - Forecast CMg 24h con bandas p10/p90 (Chart.js)
  - Evolución SOC de la batería
  - Tabla de schedule hora a hora filtrable (Carga / Descarga / Espera)
  - KPIs: Revenue neto, spread CLP/kWh, horas activas, confianza media
  - Selector de nodo (6 nodos SEN) y capacidad (500 kWh–5 MWh)
  - Auto-refresh cada 60 s · Port fiel del motor Python en JavaScript

### Changed
- `DispatchSlot.to_dict()` incluye `cmg_p10`, `cmg_p90`, `confidence` (adición no-breaking)
- `ArbitrageEngine.__init__()` con nuevos parámetros opcionales `min_confidence`, `min_spread_clp`

### Dependencies (bessai-cen-data)
- `lightgbm>=4.3.0` — modelo GBM para ensemble
- `onnxruntime>=1.18.0` — cuantización int8

### Tests
```
57 / 57 passed in 2.22s (test_cmg_predictor + test_arbitrage_engine + test_dashboard_api)
228 / 228 passed in 10.02s (suite completa open-bess-edge)
```

---

## [v0.7.0] — 2026-02-19

### Added
- `src/simulation/bess_env.py` — `BESSEnv` (Gymnasium): obs(8), action continuo [-50,50], 96 steps/ep
- `src/simulation/bess_model.py` — `BESSPhysicsModel`: SOC, degradación Rainflow approx, térmica RC
- `src/interfaces/vpp_publisher.py` — `VPPPublisher` + `OpenADREvent` (OpenADR 3.0 JSON)
- `src/interfaces/fl_client.py` — `BESSAIFlowerClient` (Flower NumPyClient): datos en edge, solo pesos salen
- `scripts/train_drl_policy.py` — entrenamiento PPO con Ray RLlib + export ONNX
- `infrastructure/helm/bessai-edge/` — Helm chart completo: Chart.yaml, values.yaml, deployment, HPA, ConfigMap, SA
- 4 nuevas métricas Prometheus: `bess_vpp_flex_capacity_kw`, `bess_vpp_events_published_total`, `bess_fl_rounds_total`, `bess_fl_train_loss`
- 35 nuevos tests: `test_bess_env.py` (15) + `test_vpp_publisher.py` (11) + `test_fl_client.py` (8) + 1 fix

### Dependencies
- Agregado `gymnasium>=0.29.0` a requirements.txt

### Tests
```
108 / 108 passed in 8.47s  (+35 tests vs v0.6.0: 73/73)
```

---

## [v0.6.0] — 2026-02-19

### Added
- `src/interfaces/ai_ids.py` — `ModbusAnomalyDetector` (IsolationForest + z-score ensemble)
  - Score 0-1; threshold=0.65; fail-safe retorna 0.0 antes de `fit()`
  - Alertas vía `structlog` + `bess_ids_alerts_total` Prometheus counter
- `src/interfaces/onnx_dispatcher.py` — `ONNXDispatcher` con ONNX Runtime
  - Carga `models/dispatch_policy.onnx` en CPU (sin internet)
  - Fallback seguro: retorna `None` si el modelo falta → SafetyGuard toma el control
- `models/dispatch_policy.onnx` — modelo dummy para tests (`target_kw = soc × 0.8`)
- `scripts/generate_dummy_onnx.py` — generador de modelo dummy con smoke test
- 4 nuevas métricas Prometheus en `metrics.py`:
  - `bess_ids_alerts_total`, `bess_ids_anomaly_score`
  - `bess_onnx_inference_ms`, `bess_onnx_dispatch_commands_total`
- 19 nuevos tests: `test_ai_ids.py` (11) + `test_onnx_dispatcher.py` (8)

### Changed
- `requirements.txt` — agregado `numpy>=1.26.0`, `scikit-learn>=1.4.0`, `onnxruntime>=1.18.0`
- `src/interfaces/metrics.py` — ampliado de 7 a 11 métricas

### Tests
```
73 / 73 passed in 11.89s  (+19 tests vs v0.5.0: 54/54)
```

---

## [0.4.1] — 2026-02-19

### 🐛 Fix — Compatibilidad Docker + Hermetismo Tests

#### `src/core/config.py`
- `INVERTER_IP` cambiado de `IPvAnyAddress` a `str` con validador regex (`_HOST_RE`).
- Acepta IPv4, IPv6 y hostnames DNS (ej: `modbus-simulator` en docker-compose).
- `inverter_ip_str` property simplificada (ya es str, sin `str()` wrapper).

#### `infrastructure/docker/docker-compose.yml`
- Healthcheck del servicio `modbus-simulator`: puerto corregido de `502` → `5020`.
  (El servidor escucha en `5020` internamente para evitar requerir privilegios root.)
- Stack completo probado: 4 contenedores operativos con `--profile simulator`.

#### `tests/test_config.py`
- Todas las llamadas directas a `Settings()` en tests de campos requeridos y defaults
  ahora usan `Settings(_env_file=None)` para hermetismo.
- Evita que el `config/.env` real del filesystem contamine los tests unitarios.
- `test_inverter_ip_invalid_raises`: actualizado a `"not an ip!"` (espacio + `!` son inválidos en hostname).
- `test_inverter_ip_parsed`: removida indirección `str()` innecesaria.

#### `config/.env`
- Creado desde `.env.example` con valores para modo desarrollo/simulador.
- `INVERTER_IP=modbus-simulator` (servicio Docker Compose), GCP desactivado.

### 📋 Resultado
- **45/45 tests pasan** en Python 3.14.2.
- **Docker stack completamente operativo** — 4 contenedores healthy/running.

---

## [0.4.0] — 2026-02-19

### ✨ Features — CI/CD + Infraestructura + Simulador

- `.github/workflows/ci.yml`: Pipeline lint → typecheck → test → docker-build → docker-push.
- `.github/workflows/release.yml`: Semver tagging + GitHub Release automático.
- `infrastructure/terraform/`: Pub/Sub topic/subscription, IAM SA, Workload Identity Federation, Artifact Registry.
- `infrastructure/docker/docker-compose.yml`: Perfil `simulator` con `modbus-simulator` + `gateway-sim`.
- `docs/`: architecture.md + runbook.md + bessai_v2_roadmap.md.

---


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
