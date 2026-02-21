# BESSAI Edge Gateway

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-372%2F372%20%E2%9C%85-success)](tests/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![CI](https://github.com/bess-solutions/open-bess-edge/actions/workflows/ci.yml/badge.svg)](https://github.com/bess-solutions/open-bess-edge/actions)
[![Security Policy](https://img.shields.io/badge/Security-Policy-red?logo=github)](SECURITY.md)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/0000/badge)](https://www.bestpractices.dev/projects/0000)
[![IEC 62443](https://img.shields.io/badge/IEC_62443-SL--1_Mapped-orange)](docs/compliance/iec62443_mapping.md)
[![NTSyCS](https://img.shields.io/badge/NTSyCS-CEN_Chile-green)](docs/compliance/ntscys_compliance.md)

> **Gateway industrial de código abierto para gestión segura y optimizada de activos BESS — cumpliendo normativa NTSyCS del CEN Chile, IEC 62443 SL-1 y estándares internacionales de software industrial.**

---

## 🚀 Estado del Proyecto — v1.3.2

| Componente | Estado |
|---|---|
| Modbus TCP Driver (`UniversalDriver`) | ✅ Funcional — pymodbus 3.12 |
| Safety Guard (`SafetyGuard`) | ✅ Funcional |
| Config (`pydantic-settings`) | ✅ Funcional — acepta IPs y hostnames |
| Health Check HTTP (`GET /health`) | ✅ JSON status + uptime |
| Prometheus Metrics (`GET /metrics`) | ✅ 22 métricas + alert_rules.yml |
| **AI-IDS** (`ModbusAnomalyDetector`) | ✅ IsolationForest + z-score, score 0-1 |
| **ONNX Dispatcher** (`ONNXDispatcher`) | ✅ Inferencia offline, fallback seguro |
| GCP Pub/Sub Publisher | ✅ Implementado y conectado |
| OpenTelemetry + Cloud Trace | ✅ Implementado |
| Suite de tests | ✅ **372/372 tests pasan** |
| Docker Compose (+ Simulador) | ✅ Operativo — perfil `monitoring` |
| Prometheus + Grafana + Alerting | ✅ `--profile monitoring` + alert rules |
| Terraform GCP | ✅ 18 recursos en GCP |
| GitHub Actions CI/CD | ✅ 9 jobs: lint+test+security+trivy+docker |
| **Gobernanza OSS** | ✅ SECURITY+COC+GOVERNANCE+CONTRIBUTING |
| **ADRs (5 decisiones)** | ✅ `docs/adr/` — pydantic, Modbus, IDS, ONNX, Pub/Sub|
| **IEC 62443 Compliance** | ✅ SL-1 mapeado en `docs/compliance/` |
| **NTSyCS CEN Chile** | ✅ Mapeado en `docs/compliance/` |

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
│   ├── drivers/       # Adaptadores de hardware (Modbus TCP via struct)
│   └── interfaces/    # health.py · metrics.py · pubsub_publisher.py · otel_setup.py
├── registry/          # Perfiles JSON de dispositivos
├── config/            # Variables de entorno (.env.example)
├── tests/             # Suite de tests (pytest, 54/54 ✅)
├── infrastructure/
│   ├── terraform/     # IaC para GCP — Pub/Sub + IAM + WIF (aplicado ✅)
│   ├── prometheus/    # prometheus.yml — scrape config
│   ├── grafana/       # Datasource provisioning automático
│   └── docker/        # Dockerfiles y docker-compose
└── docs/              # local_development.md · runbook.md · architecture.md
```

### Flujo de datos

```
[BESS Hardware]
      │  Modbus TCP (pymodbus 3.12 + struct)
      ▼
[Drivers Layer]  ──►  [Core Engine]  ──►  [Interfaces Layer]
 (src/drivers/)         (src/core/)        health.py  /health /metrics
                              │             pubsub_publisher.py → GCP Pub/Sub
                       Safety Guard         otel_setup.py → Cloud Trace
                       Pydantic v2
                              │
                              ▼
                   [Prometheus / Grafana]
                   [GCP Pub/Sub / Cloud]
```

---

## ⚙️ Configuration

La configuración sigue el principio **12-Factor App** — toda la configuración se inyecta mediante variables de entorno y se valida al inicio con **pydantic-settings**.

| Variable | Requerida | Descripción | Default |
|---|---|---|---|
| `SITE_ID` | ✅ | Identificador único del sitio | — |
| `INVERTER_IP` | ✅ | IP o hostname del inversor (acepta DNS, ej: `modbus-simulator`) | — |
| `INVERTER_PORT` | ➖ | Puerto TCP Modbus | `502` |
| `HEALTH_PORT` | ➖ | Puerto del servidor /health y /metrics | `8000` |
| `DRIVER_PROFILE_PATH` | ➖ | Ruta al perfil JSON del dispositivo | `registry/huawei_sun2000.json` |
| `WATCHDOG_TIMEOUT` | ➖ | Segundos entre heartbeats | `5` |
| `GCP_PROJECT_ID` | ✅¹ | ID del proyecto GCP | `None` |
| `GCP_PUBSUB_TOPIC` | ✅¹ | Tópico Pub/Sub de telemetría | `None` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | ➖ | Endpoint OTLP del collector | `http://otel-collector:4317` |
| `LOG_LEVEL` | ➖ | Nivel de logging | `INFO` |

> ¹ Requerida en producción. En desarrollo local puede omitirse si no se conecta a GCP.

Ver [`config/.env.example`](config/.env.example) para la plantilla completa.

---

## 🧪 Testing

```bash
# Suite completa (54/54 tests)
pytest tests/ -v --tb=short

# Con reporte de cobertura HTML
pytest tests/ --cov=src --cov-report=html
```

**Resultado actual:**
```
372 passed in ~30s  ✅
Python 3.14 · pytest-asyncio · numpy 2.4.x · scikit-learn 1.8.x · onnxruntime 1.24.x
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

## 🤝 Contributing

Las contribuciones son bienvenidas. Por favor sigue estos pasos:

1. **Fork** el repositorio y crea tu rama: `git checkout -b feature/my-feature`
2. **Commit** tus cambios: `git commit -m 'feat: add amazing feature'`
   - Seguimos la convención [Conventional Commits](https://www.conventionalcommits.org/).
3. **Push** a tu rama: `git push origin feature/my-feature`
4. Abre un **Pull Request** describiendo tus cambios.

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
