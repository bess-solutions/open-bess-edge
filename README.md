# BESSAI Edge Gateway

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-45%2F45%20%E2%9C%85-success)](tests/)
[![pymodbus](https://img.shields.io/badge/pymodbus-3.12-blue)](https://github.com/pymodbus-dev/pymodbus)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

> **Gateway industrial agnóstico para la gestión segura y optimizada de activos BESS, cumpliendo normativa NTSyCS del CEN (Chile).**

---

## 🚀 Estado del Proyecto

| Componente | Estado |
|---|---|
| Modbus TCP Driver (`UniversalDriver`) | ✅ Funcional — pymodbus 3.12 |
| Safety Guard (`SafetyGuard`) | ✅ Funcional |
| Config (`pydantic-settings`) | ✅ Funcional — Python 3.14 |
| GCP Pub/Sub Publisher | ✅ Implementado (requiere credenciales) |
| OpenTelemetry | ✅ Implementado |
| Suite de tests | ✅ **45/45 tests pasan** |
| Docker Compose | 🔄 En progreso |
| Terraform (GCP) | 🔄 Pendiente |
| GitHub Actions CI | 🔄 Pendiente |

---

## ✨ Overview

`BESSAI Edge Gateway` (`open-bess-edge`) es el componente de borde del sistema BESSAI. Actúa como capa de integración entre equipos industriales de almacenamiento de energía en baterías (BESS) y la nube, proveyendo:

- **Adquisición de datos en tiempo real** vía Modbus TCP/RTU (pymodbus 3.12, struct-based encoding).
- **Normalización y validación** de telemetría con modelos Pydantic v2.
- **Publicación de eventos** a Google Cloud Pub/Sub de forma asíncrona.
- **Observabilidad completa** con trazas y métricas OpenTelemetry (OTLP).
- **Cumplimiento regulatorio** con la Norma Técnica de Seguridad y Calidad de Servicio (NTSyCS) del Coordinador Eléctrico Nacional de Chile (CEN).

---

## 🚀 Quick Start

### Prerrequisitos

| Herramienta | Versión mínima | Notas |
|---|---|---|
| Python | 3.10+ | Probado en 3.14.2 |
| Docker & Docker Compose | 24.x | Para ejecución containerizada |
| Git | 2.40+ | |

### Instalación local

```bash
# 1. Clonar el repositorio
git clone https://github.com/your-org/open-bess-edge.git
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

### Ejecución con Docker

```bash
docker compose -f infrastructure/docker/docker-compose.yml up --build
```

---

## 🏛️ Architecture

```
open-bess-edge/
├── src/
│   ├── core/          # Lógica de negocio (orquestador, config, safety)
│   ├── drivers/       # Adaptadores de hardware (Modbus TCP via struct)
│   └── interfaces/    # Conexiones externas (GCP Pub/Sub, OTLP)
├── registry/          # Perfiles JSON de dispositivos
├── config/            # Variables de entorno (.env.example)
├── tests/             # Suite de tests (pytest, 45/45 ✅)
├── infrastructure/
│   ├── terraform/     # IaC para GCP (en progreso)
│   └── docker/        # Dockerfiles y docker-compose
└── docs/              # Documentación técnica y normativa
```

### Flujo de datos

```
[BESS Hardware]
      │  Modbus TCP (pymodbus 3.12 + struct)
      ▼
[Drivers Layer]  ──►  [Core Engine]  ──►  [Interfaces Layer]
 (src/drivers/)         (src/core/)         (src/interfaces/)
                              │
                       Validación Pydantic v2
                       Safety Guard (SOC/Temp)
                       OpenTelemetry Traces
                              │
                              ▼
                     [GCP Pub/Sub / Cloud]
```

---

## ⚙️ Configuration

La configuración sigue el principio **12-Factor App** — toda la configuración se inyecta mediante variables de entorno y se valida al inicio con **pydantic-settings**.

| Variable | Requerida | Descripción | Default |
|---|---|---|---|
| `SITE_ID` | ✅ | Identificador único del sitio | — |
| `INVERTER_IP` | ✅ | Dirección IPv4/IPv6 del inversor | — |
| `INVERTER_PORT` | ➖ | Puerto TCP Modbus | `502` |
| `DRIVER_PROFILE_PATH` | ➖ | Ruta al perfil JSON del dispositivo | `registry/huawei_sun2000.json` |
| `WATCHDOG_TIMEOUT` | ➖ | Segundos entre heartbeats | `5` |
| `GCP_PROJECT_ID` | ✅¹ | ID del proyecto GCP | `None` |
| `GCP_PUBSUB_TOPIC` | ✅¹ | Tópico Pub/Sub de telemetría | `None` |
| `GOOGLE_APPLICATION_CREDENTIALS` | ✅¹ | Ruta al JSON de credenciales GCP | — |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | ➖ | Endpoint OTLP del collector | `http://otel-collector:4317` |
| `OTEL_SERVICE_NAME` | ➖ | Nombre del servicio en trazas | `bessai-edge-gateway` |
| `LOG_LEVEL` | ➖ | Nivel de logging | `INFO` |

> ¹ Requerida en producción. En desarrollo local puede omitirse si no se conecta a GCP.

Ver [`config/.env.example`](config/.env.example) para la plantilla completa.

---

## 🧪 Testing

```bash
# Suite completa (45/45 tests)
pytest tests/ -v --tb=short

# Con reporte de cobertura HTML
pytest tests/ --cov=src --cov-report=html
```

**Resultado actual:**
```
45 passed in 6.66s  ✅
Python 3.14.2 · pytest 9.0.2 · pymodbus 3.12
```

> **Nota para pruebas:** No se requiere archivo `.env` para correr los tests.
> El `conftest.py` inyecta las variables mínimas necesarias automáticamente.

---

## 🗺️ Roadmap v2.0

Ver el documento completo: [BESSAI v2.0 Technical Roadmap](docs/bessai_v2_roadmap.md)

| Fase | Área | Prioridad |
|---|---|---|
| Q2 2026 | Terraform GCP + GitHub Actions CI | 🔴 Alta |
| Q3 2026 | Edge AI (ONNX) + AI-IDS | 🔴 Alta |
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

---

## 📄 License

This project is licensed under the **Apache License 2.0** — see the [LICENSE](LICENSE) file for details.

---

## 📬 Contact

**BESS Solutions** — Equipo de Ingeniería  
📧 ingenieria@bess-solutions.cl  
🌐 [bess-solutions.cl](https://bess-solutions.cl)
