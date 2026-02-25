# BESSAI Edge Gateway

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-613%2F613%20%E2%9C%85-success)](tests/)
[![Docker](https://img.shields.io/badge/Docker-amd64%20%7C%20arm64-2496ED?logo=docker&logoColor=white)](https://ghcr.io/bess-solutions/open-bess-edge)
[![CI](https://github.com/bess-solutions/open-bess-edge/actions/workflows/ci.yml/badge.svg)](https://github.com/bess-solutions/open-bess-edge/actions)
[![Multi-Arch](https://github.com/bess-solutions/open-bess-edge/actions/workflows/docker-multiarch.yml/badge.svg)](https://github.com/bess-solutions/open-bess-edge/actions)
[![Codecov](https://codecov.io/gh/bess-solutions/open-bess-edge/branch/main/graph/badge.svg)](https://codecov.io/gh/bess-solutions/open-bess-edge)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/bess-solutions/open-bess-edge/badge)](https://scorecard.dev/viewer/?uri=github.com/bess-solutions/open-bess-edge)
[![Security Policy](https://img.shields.io/badge/Security-Policy-red?logo=github)](SECURITY.md)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/12001/badge)](https://www.bestpractices.dev/projects/12001)
[![IEC 62443](https://img.shields.io/badge/IEC_62443-SL--1_Mapped-orange)](docs/compliance/iec62443_mapping.md)
[![NTSyCS](https://img.shields.io/badge/NTSyCS-CEN_Chile-green)](docs/compliance/ntscys_compliance.md)
[![BESSAI-SPEC](https://img.shields.io/badge/BESSAI--SPEC-3_normative_docs-blueviolet)](docs/specs/)
[![BEP Process](https://img.shields.io/badge/Governance-BEP_Process-lightblue)](docs/bep/BEP-0001.md)
[![Discord](https://img.shields.io/badge/Discord-BESSAI_Community-5865F2?logo=discord&logoColor=white)](https://discord.gg/ZqpE8AZs)

> **Gateway industrial de código abierto para gestión segura y optimizada de activos BESS — cumpliendo normativa NTSyCS del CEN Chile, IEC 62443 SL-1 y estándares internacionales de software industrial.**

> 💬 **Comunidad:** [Únete a Discord](https://discord.gg/ZqpE8AZs) · [GitHub Discussions](https://github.com/bess-solutions/open-bess-edge/discussions) · [Bounty Program](docs/bounty_program.md)

---

## 🚀 Estado del Proyecto — v2.10.0-dev

| Componente | Estado |
|---|---|
| Modbus TCP Driver + **Auto-Reconexión** | ✅ `_reconnect()` + backoff, 6 chaos tests |
| Safety Guard (`SafetyGuard`) | ✅ Funcional |
| Config (`pydantic-settings`) | ✅ Funcional — acepta IPs y hostnames |
| Health Check HTTP (`GET /health`) | ✅ JSON status + uptime |
| Prometheus Metrics (`GET /metrics`) | ✅ 22 métricas + alert_rules.yml |
| **AI-IDS** (`ModbusAnomalyDetector`) | ✅ IsolationForest + z-score, score 0-1 |
| **ONNX Dispatcher** (`ONNXDispatcher`) | ✅ Inferencia offline, fallback seguro |
| GCP Pub/Sub Publisher | ✅ Implementado y conectado |
| **MQTT Publisher** (`paho-mqtt`) | ✅ Mosquitto / HA / AWS IoT Core / Azure |
| **IEEE 2030.5 / SEP 2.0** | ✅ **BEP-0100 Active** — 10 endpoints, TLS 1.2+, mTLS, DERControl |
| **DRL Arbitrage Agent** | ✅ **BEP-0200 Fase 2** — ONNXArbitrageAgent (observe-only) |
| OpenTelemetry + Cloud Trace | ✅ Implementado |
| Suite de tests | ✅ **613/613 tests pasan** (+23 BEP-0200 F3, +19 WatchdogManager) |
| Docker Compose (+ Simulador) | ✅ Operativo — perfil `monitoring` |
| **Multi-Arch Docker** (amd64 + arm64) | ✅ Buildx CI → ghcr.io — Raspberry Pi 4/5 |
| Prometheus + Grafana + Alerting | ✅ `--profile monitoring` + alert rules |
| Terraform GCP | ✅ 18 recursos en GCP |
| GitHub Actions CI/CD | ✅ 10 jobs: lint+typecheck+test+interop+security+terraform+helm+docker+trivy+push |
| **Hardware Registry** | ✅ 7 perfiles: Huawei, SMA, Victron, Fronius, SolarEdge, BYD, Tesla |
| **Gobernanza OSS** | ✅ SECURITY+COC+GOVERNANCE+CONTRIBUTING + **BOA Charter** |
| **IEC 62443 Compliance** | ✅ SL-1 mapeado · SL-2 certification path en `docs/compliance/` |
| **IEEE 2030.5** | ✅ **Implementado** (BEP-0100) + gap analysis en `docs/compliance/` |
| **NTSyCS CEN Chile** | ✅ Mapeado en `docs/compliance/` |
| **OpenSSF Best Practices** | ✅ Passing badge — bestpractices.dev |
| **Spec Formales (BESSAI-SPEC)** | ✅ 4 specs: driver, safety, telemetry, **BMS data model (IEEE P2686)** |
| **Gobernanza TSC + BEP** | ✅ BEP-0001 · `GOVERNANCE.md` · **BESSAI Open Alliance Charter** |
| **WatchdogManager** (Plan Inmortalidad) | ✅ Self-healing autónomo · backoff · Prometheus · AlertDispatcher |
| **Scrollytelling Landing** (`landing/`) | ✅ React + Vite · i18n ES/EN · Lucide icons · FAQ/Features refactored |

---

## ✨ Overview

`BESSAI Edge Gateway` (`open-bess-edge`) es el componente de borde del sistema BESSAI. Actúa como capa de integración entre equipos industriales de almacenamiento de energía en baterías (BESS) y la nube, proveyendo:

- **Adquisición de datos en tiempo real** vía Modbus TCP/RTU (pymodbus 3.12, struct-based encoding).
- **Normalización y validación** de telemetría con modelos Pydantic v2.
- **Publicación de eventos** a Google Cloud Pub/Sub de forma asíncrona.
- **Observabilidad completa** con trazas y métricas OpenTelemetry (OTLP) + Prometheus.
- **Health check HTTP** en `GET /health` y métricas Prometheus en `GET /metrics` (puerto 8000).
- **Cumplimiento regulatorio** con la Norma Técnica de Seguridad y Calidad de Servicio (NTSyCS) del Coordinador Eléctrico Nacional de Chile (CEN).

---

## 🚀 Quick Start

### Prerrequisitos

| Herramienta | Versión mínima | Notas |
|---|---|---|
| Python | 3.10+ | Probado en 3.14 |
| Docker & Docker Compose | 24.x | Para ejecución containerizada |
| Git | 2.40+ | |

### Instalación local

```bash
# 1. Clonar el repositorio
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# 2. Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.\.venv\Scripts\Activate.ps1   # Windows PowerShell

# 3. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# 4. Configurar variables de entorno
cp config/.env.example config/.env
# Editar config/.env con los valores de tu entorno

# 5. Ejecutar el gateway
python -m src.core.main
```

### Ejecución con Docker (modo simulador — sin hardware)

```bash
# Levanta gateway + simulador Modbus + OTel collector
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator up --build -d

# Con Prometheus + Grafana (monitoring stack)
docker compose -f infrastructure/docker/docker-compose.yml \
  --profile simulator --profile monitoring up --build -d
```

Una vez corriendo puedes acceder a:

| URL | Descripción |
|---|---|
| http://localhost:8000/health | Gateway health check (JSON) |
| http://localhost:8000/metrics | Métricas Prometheus |
| http://localhost:9090 | Prometheus UI |
| http://localhost:3000 | Grafana (admin / bessai) |

Ver la guía completa: [`docs/local_development.md`](docs/local_development.md)

---

## 🏛️ Architecture

```
open-bess-edge/
├── src/
│   ├── core/          # Lógica de negocio (orquestador, config, safety)
│   ├── drivers/       # Adaptadores de hardware (Modbus TCP, SimulatorDriver, Luna2000)
│   ├── agents/        # DRL Arbitrage Agent (BEP-0200): BESSArbitrageEnv, ArbitragePolicy, ONNXArbitrageAgent
│   └── interfaces/    # health · metrics · pubsub · mqtt · sep2_adapter (IEEE 2030.5) · ai_ids · onnx
├── registry/          # Perfiles JSON: Huawei, SMA, Victron, Fronius
├── config/            # Variables de entorno (.env.example)
├── models/            # ONNX models: dispatch_policy.onnx · drl_arbitrage_v1.onnx
├── tests/             # Suite de tests (pytest, 490/490 ✅ · interop · chaos · DRL)
├── infrastructure/
│   ├── terraform/     # IaC para GCP — Pub/Sub + IAM + WIF (aplicado ✅)
│   ├── prometheus/    # prometheus.yml · alert_rules.yml
│   ├── grafana/       # Datasource provisioning automático
│   └── docker/        # Dockerfiles y docker-compose
└── docs/              # specs/ · compliance/ · bep/ · governance/ · outreach/ · certification/
```

### Flujo de datos

```
[BESS Hardware]
      │  Modbus TCP (pymodbus 3.12 + struct)
      ▼
[Drivers Layer]  ──►  [Core Engine]  ──►  [Interfaces Layer]
 modbus_driver          (src/core/)        health.py      → /health /metrics
 luna2000_driver         │                 pubsub_publisher.py → GCP Pub/Sub
 simulator_driver   Safety Guard          mqtt_publisher.py   → MQTT Brokers
                    Pydantic v2           otel_setup.py       → Cloud Trace
                         │                ai_ids.py           → Anomaly score
                         │                onnx_dispatcher.py  → Dispatch cmds
                         ▼
               [Prometheus / Grafana]     dashboard_api.py    → http://:8080
               [GCP Pub/Sub / MQTT / Cloud]
```


---

## ⚙️ Configuration

La configuración sigue el principio **12-Factor App** — toda la configuración se inyecta mediante variables de entorno y se valida al inicio con **pydantic-settings**.

| Variable | Requerida | Descripción | Default |
|---|---|---|---|
| `SITE_ID` | ✅ | Identificador único del sitio | — |
| `INVERTER_IP` | ✅ | IP o hostname del inversor (acepta DNS, ej: `modbus-simulator`) | — |
| `INVERTER_PORT` | ➕ | Puerto TCP Modbus | `502` |
| `HEALTH_PORT` | ➕ | Puerto del servidor /health y /metrics | `8000` |
| `DRIVER_PROFILE_PATH` | ➕ | Ruta al perfil JSON del dispositivo | `registry/huawei_sun2000.json` |
| `WATCHDOG_TIMEOUT` | ➕ | Segundos entre heartbeats | `5` |
| `GCP_PROJECT_ID` | ✅¹ | ID del proyecto GCP | `None` |
| `GCP_PUBSUB_TOPIC` | ✅¹ | Tópico Pub/Sub de telemetría | `None` |
| `MQTT_BROKER_URL` | ➕ | URL broker MQTT (ej: `mqtt://localhost:1883`) | `None` |
| `SEP2_ENABLED` | ➕ | Habilitar IEEE 2030.5 adapter (BEP-0100) | `false` |
| `SEP2_HOST` / `SEP2_PORT` | ➕ | Bind del servidor IEEE 2030.5 | `0.0.0.0:8443` |
| `BESSAI_DRL_ENABLED` | ➕ | Activar agente DRL en main.py (BEP-0200) | `false` |
| `BESSAI_DRL_MODEL_PATH` | ➕ | Ruta al modelo ONNX del agente DRL | `models/drl_arbitrage_v1.onnx` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | ➕ | Endpoint OTLP del collector | `http://otel-collector:4317` |
| `LOG_LEVEL` | ➕ | Nivel de logging | `INFO` |

> ¹ Requerida en producción. En desarrollo local puede omitirse si no se conecta a GCP.

Ver [`config/.env.example`](config/.env.example) para la plantilla completa.

---

## 🧪 Testing

```bash
# Suite completa (378/378 tests)
pytest tests/ -v --tb=short

# Con reporte de cobertura HTML
pytest tests/ --cov=src --cov-report=html
```

**Resultado actual:**
```
613 passed in ~43s  ✅  (6 skipped)
Python 3.10+ · pytest-asyncio · numpy · scikit-learn · onnxruntime · structlog
```

> **Nota:** No se requiere archivo `.env` para los tests. El `conftest.py` inyecta las variables mínimas automáticamente.

---

## ☁️ GCP Infrastructure (Terraform)

Los recursos GCP están provisionados y activos:

```bash
# Ver recursos creados
cd infrastructure/terraform
terraform output
```

| Recurso | Nombre |
|---|---|
| Pub/Sub topic | `bess-telemetry-dev` |
| Pub/Sub subscription | `bess-telemetry-dev-pull` |
| Artifact Registry | `us-central1-docker.pkg.dev/…/bessai` |
| Service Account | `bessai-edge-sa-dev@…` |
| Workload Identity Pool | `github-actions-pool` |

---

## 🗺️ Roadmap v2.0

Ver el documento completo: [BESSAI v2.0 Technical Roadmap](docs/bessai_v2_roadmap.md)

| Fase | Área | Prioridad |
|---|---|---|
| ✅ Q1 2026 | Health/Metrics HTTP + Prometheus + Terraform GCP | 🔴 **Completado** |
| 🟡 Q3 2026 | Edge AI: ONNX ✅ + AI-IDS ✅ + DRL Training (Ray RLlib) | 🔴 **En progreso** |
| Q4 2026 | Federated Orchestration + VPP | 🟡 Media |
| Q1 2027 | Data Lakehouse + P2P Trading | 🟡 Media |
| Q2 2027 | LCA Engine + Carbon Dashboard | 🟢 Estratégica |

---

## 🏢 Adopters & Partners

> BESSAI is used in production and R&D deployments. Want to be listed?
> [Introduce your organization →](https://github.com/bess-solutions/open-bess-edge/discussions)

| Organization | Type | Country | Hardware |
|---|---|---|---|
| BESS Solutions | Integrator (reference) | 🇨🇱 Chile | Huawei SUN2000 |

**Partnership tiers** (Associate · Technology · Strategic · Academic): [`docs/partnership_program.md`](docs/partnership_program.md)  
**Become a BESSAI Certified hardware vendor**: [`docs/interoperability/BESSAI-CERTIFIED.md`](docs/interoperability/BESSAI-CERTIFIED.md)

---

## 📐 Formal Specifications

BESSAI publishes machine-readable normative specifications enabling third-party implementations:

| Spec | Title | Key Requirement |
|---|---|---|
| [BESSAI-SPEC-001](docs/specs/BESSAI-SPEC-001.md) | BESSDriver Interface | All drivers MUST implement `DataProvider` protocol |
| [BESSAI-SPEC-002](docs/specs/BESSAI-SPEC-002.md) | Safety Requirements | SafetyGuard MUST block when SOC < 5% or T > 60°C |
| [BESSAI-SPEC-003](docs/specs/BESSAI-SPEC-003.md) | Telemetry Schema | JSON Schema 2020-12 for all telemetry messages |
| [BESSAI-SPEC-004](docs/specs/BESSAI-SPEC-004.md) | BMS Data Model | `BatteryState` dataclass — IEEE P2686 alignment |

Propose a change: open a [BEP (BESSAI Enhancement Proposal)](docs/bep/BEP-0001.md)

---

## 🤝 Contributing

Las contribuciones son bienvenidas. Por favor sigue estos pasos:

1. **Fork** el repositorio y crea tu rama: `git checkout -b feature/my-feature`
2. **Commit** tus cambios: `git commit -m 'feat: add amazing feature'`
   - Seguimos la convención [Conventional Commits](https://www.conventionalcommits.org/).
3. **Push** a tu rama: `git push origin feature/my-feature`
4. Abre un **Pull Request** describiendo tus cambios.

> Para citar este proyecto en publicaciones académicas: **use el botón "Cite this repository"** que aparece en el panel lateral de GitHub (generado desde [`CITATION.cff`](CITATION.cff)).

### Guías de estilo

- Formatter: `ruff format`
- Linter: `ruff check`
- Type checker: `mypy`
- Config centralizada: [`pyproject.toml`](pyproject.toml)

---

## 📄 License

This project is licensed under the **Apache License 2.0** — see the [LICENSE](LICENSE) file for details.

---

## 📬 Contact

**BESS Solutions** — Equipo de Ingeniería  
📧 ingenieria@bess-solutions.cl  
🌐 [bess-solutions.cl](https://bess-solutions.cl)
