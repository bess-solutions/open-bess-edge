# 📊 BESSAI Edge Gateway — Estado del Proyecto

> **Actualizado:** 2026-02-22T13:37 v1.8.0 · **Responsable:** Equipo TCI-GECOMP  
> *Actualiza este archivo en cada iteración junto con CHANGELOG.md y requirements.txt.*

---

## 🎯 ¿Qué es BESSAI?

Sistema industrial de gestión de baterías (BESS) con inteligencia artificial — **candidato a estándar global**. Conecta inversores reales (Huawei SUN2000, SMA, Victron, Fronius) vía Modbus TCP, valida la operación de forma segura, y publica telemetría a GCP Pub/Sub o MQTT con observabilidad completa.

**Visión:** Convertirse en el estándar de referencia mundial para gestión de BESS en el edge — adoptado por fabricantes, operadores y reguladores.  
Ver roadmap completo: [`docs/bessai_v2_roadmap.md`](docs/bessai_v2_roadmap.md)

---

## ✅ Estado Actual — v1.8.0

### Tests
```
378 / 378 passed ✅  (suite completa — 378 tests, 6 chaos tests, sin regresión)
CI/CD: ruff ✅ · mypy ✅ · pytest+codecov ✅ · bandit ✅ · trivy ✅ · docker ✅ · multiarch ✅ · scorecard ✅
Nuevos: benchmark.yml (semanal) · compliance-report.yml (semanal)
```


### Stack Docker — Métricas en vivo (confirmado 2026-02-19)
```
bess_cycles_total{site_id="SITE-CL-001"}    39      ← ciclos completados
bess_last_power_kw{site_id="SITE-CL-001"}   376.8   ← kW desde Modbus
bess_publish_errors_total                   39      ← GCP no configurado (esperado)
Grafana v10.4.2                             OK      ← localhost:3000 admin/bessai
Prometheus v2.51.2                          OK      ← localhost:9090
```

### Módulos implementados

| Módulo | Archivo | Versión | Estado |
|---|---|---|---|
| CMg Predictor v2 | `src/interfaces/cmg_predictor.py` | **v2.0** | ✅ **NUEVO** |
| Arbitrage Engine v2 | `src/interfaces/arbitrage_engine.py` | **v2.0** | ✅ **NUEVO** |
| Configuración | `src/core/config.py` | v0.5 | ✅ Producción |
| Seguridad (SOC / Temp) | `src/core/safety.py` | **v1.7.1** | ✅ Producción — acepta DataProvider |
| Orquestador principal | `src/core/main.py` | v0.5 | ✅ Producción |
| Fleet Orchestrator | `src/core/fleet_orchestrator.py` | v0.8 | ✅ Producción |
| Driver Modbus TCP | `src/drivers/modbus_driver.py` | **v1.7.1** | ✅ Producción — is_connected + source_description |
| Simulator Driver | `src/drivers/simulator_driver.py` | **v1.7.1** | ✅ Producción — Sim-First, 12 componentes |
| DataProvider Protocol | `src/drivers/base.py` | **v1.7.1** | ✅ Producción — protocolo runtime_checkable |
| LUNA2000 Driver | `src/drivers/luna2000_driver.py` | **v1.0** | ✅ Producción |
| Servidor /health + /metrics | `src/interfaces/health.py` | v0.5 | ✅ Producción |
| Prometheus metrics (22 total) | `src/interfaces/metrics.py` | v0.9 | ✅ Producción |
| OTel / Cloud Trace | `src/interfaces/otel_setup.py` | v0.9 | ✅ Producción |
| GCP Pub/Sub Publisher | `src/interfaces/pubsub_publisher.py` | v0.5 | ✅ Producción |
| MQTT Publisher | `src/interfaces/mqtt_publisher.py` | **v1.7.1** | ✅ Producción — paho-mqtt, TLS, multi-broker |
| AI-IDS | `src/interfaces/ai_ids.py` | v0.6 | ✅ Producción |
| ONNX Dispatcher | `src/interfaces/onnx_dispatcher.py` | v0.6 | ✅ Producción |
| VPP Publisher (OpenADR 3.0) | `src/interfaces/vpp_publisher.py` | v0.7 | ✅ Producción |
| FL Client (Flower) | `src/interfaces/fl_client.py` | v0.7 | ✅ Producción |
| FL Server (FedAvg) | `src/interfaces/fl_server.py` | v0.8 | ✅ Producción |
| LCA Carbon Engine | `src/interfaces/lca_engine.py` | v0.8 | ✅ Producción |
| LCA Config (40+ países) | `src/interfaces/lca_config.py` | v0.8 | ✅ Producción |
| P2P Energy Trading | `src/interfaces/p2p_trading.py` | v0.8 | ✅ Producción |
| DataLake Publisher (BigQuery) | `src/interfaces/datalake_publisher.py` | v0.8 | ✅ Producción |
| Dashboard REST API | `src/interfaces/dashboard_api.py` | v0.9 | ✅ Producción |
| Alert Manager | `src/interfaces/alert_manager.py` | v0.9 | ✅ Producción |
| SUN2000 Monitor | `src/interfaces/sun2000_monitor.py` | **v1.0** | ✅ Producción |
| BESS Gymnasium Env | `src/simulation/bess_env.py` | v0.7 | ✅ Producción |
| BESS Physics Model | `src/simulation/bess_model.py` | v0.7 | ✅ Producción |
| ONNX modelo dummy | `models/dispatch_policy.onnx` | v0.6 | ✅ Producción |
| DRL training script | `scripts/train_drl_policy.py` | v0.7 | ✅ Producción |
| Helm chart | `infrastructure/helm/bessai-edge/` | v0.7 | ✅ Completo |
| Grafana Dashboard | `infrastructure/grafana/dashboards/bessai_main.json` | **v1.0** | ✅ 13 paneles |
| Terraform GCP | `infrastructure/terraform/` | v0.5 | ✅ 18 recursos |
| Registro Modbus | `registry/huawei_sun2000.json` | **v2.0** | ✅ 28 registros reales |
| Modbus Simulator | `infrastructure/docker/modbus_sim/` | **v1.0.1** | ✅ pymodbus server, 22 registros |
| GitHub Actions CI/CD | `.github/workflows/ci.yml` | v1.0 | ✅ **9 jobs**: lint+typecheck+test+security+terraform+helm+docker+trivy+push |
| OpenSSF Scorecard CI | `.github/workflows/scorecard.yml` | v1.0 | ✅ Supply chain security automático — badge Scorecard activo |
| Mutation Testing | `.github/workflows/mutation-test.yml` | v1.0 | ✅ mutmut semanal — safety.py + config.py |
| K8s Manifests | `infrastructure/k8s/` | v1.0 | ✅ 6 manifests: namespace+configmap+service+deployment+netpol+kustomize |
| SBOM + SLSA L2 | `.github/workflows/release.yml` | v1.1 | ✅ CycloneDX SBOM + cosign signing + SLSA Level 2 provenance |

### 🐳 Stack Docker — ✅ COMPLETAMENTE OPERATIVO (v1.0.1)

> **Fix v1.0.1:** La imagen `oitc/modbus-server` ignoraba `configuration.json`. Se corrigió montando nuestro config directamente sobre `/app/modbus_server.json` con `listenerPort: 502`. Stack validado con métricas Modbus reales.

```powershell
# Stack completo con simulador + monitoreo:
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring up -d

# Verificar:
curl http://localhost:8000/health    # gateway health
curl http://localhost:8000/metrics   # prometheus metrics
# Grafana:    http://localhost:3000   (admin / bessai)
# Prometheus: http://localhost:9090
```

| Contenedor | Estado verificado | Puerto |
|---|---|---|
| `bessai-modbus-simulator` | ✅ **healthy** — escucha en 502 | `host:5020` → `container:502` |
| `bessai-gateway` | ✅ **healthy** — ciclos activos | **`8000`** (/health, /metrics) |
| `bessai-gateway-sim` | ✅ running — conectado al sim | **`8000`** (/health, /metrics) |
| `bessai-otel-collector` | ✅ running | 4317, 4318, 8888 |
| `bessai-prometheus` | ✅ **HTTP 200** | **`9090`** |
| `bessai-grafana` | ✅ **database:ok** v10.4.2 | **`3000`** (admin/bessai) |

### Dashboard REST API (v0.9.0)

```powershell
# Ejecutar dashboard localmente
python -m uvicorn src.interfaces.dashboard_api:app --port 8080

# Endpoints disponibles
GET /api/v1/status   → SOC, power, temp, AI-IDS, ONNX
GET /api/v1/fleet    → n_sites, avg_SOC, flex_kW, alarms
GET /api/v1/carbon   → CO₂ avoided, EF, trees equivalent
GET /api/v1/p2p      → credits minted, kWh, pending
GET /api/v1/version  → version, build_date
GET /api/v1/health   → ok / degraded
```

### Prometheus — 22 métricas activas

| Categoría | Métricas |
|---|---|
| v0.5 — Base | `cycles_total`, `safety_blocks`, `soc_%`, `power_kw`, `cycle_duration_s` |
| v0.6 — AI | `ids_alerts_total`, `ids_anomaly_score`, `onnx_inference_ms`, `onnx_dispatch_commands` |
| v0.7 — VPP + FL | `vpp_flex_capacity_kw`, `vpp_events_published`, `fl_rounds_total`, `fl_train_loss` |
| v0.8 — LCA + Fleet + P2P + DL | `carbon_avoided_kg`, `carbon_intensity_g_kwh`, `fleet_sites_active`, `fleet_total_capacity_kwh`, `energy_credits_minted`, `energy_credits_kwh`, `datalake_rows_published` |

### Bloqueadores activos

> 🎉 **Sin bloqueadores activos** — CI/CD + Scorecard + Mutation Testing operativos. K8s manifests, SLSA L2 y estrategia SSAF implementados (v1.7.1).

### ✅ Entregables recientes (semanas 1-3+, 22-feb-2026)

| Commit | Entregable | Impacto |
|---|---|---|
| `e7d111a` | Scorecard CI, CITATION.cff, badges Codecov+Scorecard, hardware template | OpenSSF supply chain score automático |
| `545c084` | Tutorial 5min sin hardware, MQTT+HA tutorial, FUNDING.yml, MkDocs Tutorials | Onboarding < 5 min |
| `9bc4d78` | K8s manifests (6 archivos), kustomization.yaml | `kubectl apply -k` en K3s/RPi/GKE |
| `0ce640b` | Pitch deck, SSAF S16, IEC 62443 SL-2 gap, Bounty Program, NetworkPolicy, Mutation Test | Estrategia + postulación |
| `460bff6` | Tutorial hardware real, OpenSSF Gold checklist, SLSA L2, Maintainer Security Policy | OpenSSF Gold path |

### Pendientes (solo Rodrigo)

- [ ] Activar 2FA en cuenta GitHub
- [ ] Completar checkboxes en bestpractices.dev/projects/12001
- [ ] Conectar Codecov en codecov.io/gh/bess-solutions/open-bess-edge
- [ ] Subir postulación SSAF en startupchile.org (docs/startup_chile_ssaf.md listo)

---

## 🗺️ Roadmap

```
v0.5.0  ████████████████████████  ✅ Modbus + Safety + Prometheus
v0.6.0  ████████████████████████  ✅ AI-IDS + ONNX Dispatcher
v0.7.0  ████████████████████████  ✅ VPP + FL Client + Gymnasium + Helm
v0.8.0  ████████████████████████  ✅ FL Server + LCA + Fleet + P2P + DataLake
v0.9.0  ████████████████████████  ✅ Dashboard API + Alert Manager + CI/CD Helm
v1.0.0  ████████████████████████  ✅ Grafana Dashboards + LUNA2000 driver + 228 tests
v1.0.1  ████████████████████████  ✅ Docker stack corregido y 100% operativo
v1.2.0  ████████████████████████  ✅ CMgPredictor v2 + ArbitrageEngine v2 + Dashboard
v1.3.0  ████████████████████████  ✅ bessai-cen-data v0.3.0: 11 features ONNX · pipeline fix · CLI · API
v1.3.1  ████████████████████████  ✅ CI 100% verde (ruff+mypy fix) · Mega Scraper 8 módulos
v1.3.2  ████████████████████████  ✅ ruff format fix (4 archivos) · suite actualizada 372 tests
v1.4.0  ████████████████████████  ✅ Estándares internacionales: OSS governance, supply chain security, ADRs, compliance
v1.5.0  ████████████████████████  ✅ MkDocs site · PyPI package · API Reference · Runbook operacional
v2.0.0  ░░░░░░░░░░░░░░░░░░░░░░░░  📋 Multi-site planetary scale
```

---

## 🏗️ Arquitectura del Sistema (v0.9.0)

```
┌─────────────────────────────────────────────────────────────────┐
│                    BESSAI Edge Gateway v0.9.0                    │
│                                                                   │
│  [BESS / Inversor]                                                │
│       │ Modbus TCP (pymodbus 3.12)                               │
│       ▼                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ UniversalDriver│  │ SafetyGuard  │    │  AI-IDS      │       │
│  │ (struct I/O) │   │ SOC + Temp   │    │ (IsolForest) │       │
│  └──────┬───────┘   └──────┬───────┘    └──────┬───────┘       │
│         └──────────────────┼───────────────────┘               │
│                            ▼                                     │
│                   ┌─────────────┐                               │
│                   │ Orquestador │◄── DashboardState             │
│                   │  main.py    │                               │
│                   └──────┬──────┘                               │
│         ┌────────────────┼────────────────┐                     │
│         ▼                ▼                ▼                     │
│  [ONNX Dispatcher]  [LCA Engine]    [P2P Trader]               │
│  [VPP Publisher]    [FL Server]     [DataLake]                 │
│  [Fleet Orch.]      [Alert Mgr]     [Dashboard API :8080]      │
│         │                ▼                                       │
│  [GCP Pub/Sub]    [BigQuery DL]                                 │
│  [OTel → Prometheus → Grafana]                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura del Repositorio (v0.9.0)

```
open-bess-edge/
├── 📄 README.md
├── 📄 PROJECT_STATUS.md         ← ESTE ARCHIVO
├── 📄 CHANGELOG.md              ← Historial + AGENT HANDOFF
├── 📄 requirements.txt          ← Deps producción (actualizado v0.9.0)
├── 📄 requirements-dev.txt      ← Deps desarrollo
│
├── 📂 src/
│   ├── 📂 core/
│   │   ├── config.py
│   │   ├── safety.py
│   │   ├── main.py
│   │   └── fleet_orchestrator.py  ← NEW v0.8
│   ├── 📂 drivers/
│   │   └── modbus_driver.py
│   └── 📂 interfaces/
│       ├── health.py, metrics.py       ← base
│       ├── ai_ids.py, onnx_dispatcher.py  ← v0.6
│       ├── vpp_publisher.py, fl_client.py ← v0.7
│       ├── fl_server.py, lca_engine.py    ← v0.8
│       ├── lca_config.py, p2p_trading.py  ← v0.8
│       ├── datalake_publisher.py          ← v0.8
│       ├── dashboard_api.py               ← v0.9 NEW
│       └── alert_manager.py              ← v0.9 NEW
│
├── 📂 src/simulation/
│   ├── bess_env.py              ← Gymnasium BESS (v0.7)
│   └── bess_model.py            ← física BESS (v0.7)
│
├── 📂 tests/                    ← 183 tests / 183 ✅
│
├── 📂 scripts/
│   ├── generate_dummy_onnx.py
│   └── train_drl_policy.py      ← Ray RLlib PPO (v0.7)
│
├── 📂 infrastructure/
│   ├── 📂 docker/               ← Docker Compose + Dockerfile
│   ├── 📂 helm/bessai-edge/     ← Helm chart v0.7
│   ├── 📂 terraform/            ← GCP (18 recursos)
│   └── 📂 grafana/              ← Grafana provisioning
│
└── 📂 .github/workflows/
    └── ci.yml                   ← 7 jobs CI/CD (v0.9)
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

# Dashboard API (v0.9)
DASHBOARD_API_KEY=           # vacío = dev mode (no auth)

# P2P Trading
P2P_LEDGER_ENDPOINT=http://localhost:7050/api/v1/invoke

# DataLake
BIGQUERY_PROJECT_ID=my-bess-project
BIGQUERY_DATASET=bessai_telemetry
```

---

## 🚀 Validación rápida (sin hardware)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
pip install gymnasium>=0.29.0
pytest tests/ -v --tb=short
# 183 passed ✅ en ~8.5s
```

---

## 📌 Historial de Actualizaciones

| Fecha | Versión | Tests | Cambio |
|---|---|---|---|
| 2026-02-19 | v0.3.0 | 45/45 | Creación inicial |
| 2026-02-19 | v0.4.0 | 45/45 | CI/CD, Terraform GCP, simulador Modbus |
| 2026-02-19 | v0.5.0 | 54/54 | /health, /metrics, pyproject.toml, monitoring stack |
| 2026-02-19 | v0.6.0 | 73/73 | AI-IDS, ONNX Dispatcher, modelo dummy |
| 2026-02-19 | v0.7.0 | 108/108 | VPP, FL Client, BESSEnv, Helm, Ray RLlib |
| 2026-02-19 | v0.8.0 | 159/159 | FL Server, LCA, Fleet, P2P, DataLake, 22 métricas |
| 2026-02-19 | v0.9.0 | 183/183 | Dashboard API, Alert Manager, CI Helm job |
| 2026-02-19 | v1.0.0 | 228/228 | LUNA2000 driver, SUN2000 monitor, Grafana 13 paneles, registry v2.0 |
| 2026-02-19 | v1.0.1 | 228/228 | Fix Docker: simulador Modbus oitc corregido, stack 100% operativo |
| 2026-02-20 | **v1.2.0** | **57+228** | **CMgPredictor v2** (TTL cache, int8, p10/p90) · **ArbitrageEngine v2** (umbral confianza, spread mín) · `train_price_model.py v2` (11 features, ensemble, batch) · Dashboard web arbitraje |
| 2026-02-20 | **v1.3.0** | **228/228** | **bessai-cen-data v0.3.0**: `pipeline.py` corregido 9→11 features (`lag_168h`, `is_weekend`), shape (24,11) match v2 ONNX · `pyproject.toml` v0.3.0 + CLI `bessai-fetch-renewables`/`bessai-build-dataset` · `bessai-web` polling real `/api/v1/schedule` + `/api/v1/status` · `drawChartFromSchedule()` con zonas carga/descarga · renewable-energy-chile dashboard: 5 bugs arreglados |
| 2026-02-20 | **v1.3.1** | **228/228** | **CI 100% verde**: fix ruff UP045/UP037/I001/F401 + mypy attr-defined en `_run_session` · **Mega Scraper** `sources/mega_scraper_energia_abierta.py` v1.0: 8 módulos CNE+CEN, pipeline `historical/market/training/`, dry-run verificado |
| 2026-02-21 | **v1.3.2** | **372/372** | **ruff format fix**: 4 archivos reformateados · Suite actualizada 228 → 372 tests |
| 2026-02-21 | **v1.7.0** | **378/378** | hardware registry (SMA/Victron/Fronius), MQTT publisher, 6 chaos tests, Multi-Arch CI, Raspberry Pi docs, OpenSSF badge |
| 2026-02-21 | **v1.7.1** | **378/378** | **CI Green**: fix(ci) mypy+ruff+pytest · DataProvider protocol en safety.py · UniversalDriver properties · fixture async test_reconnect_chaos · connect() mock en test_modbus_driver |
| 2026-02-22 | **v1.7.1+** | **378/378** | **Ruta 10/10**: Semana 1 (Scorecard, CITATION, badges) · Semana 2 (tutoriales, FUNDING) · Semana 3 (K8s manifests, NetworkPolicy) · Estrategia (pitch deck, SSAF, IEC62443 SL-2, bounties, SLSA L2, OpenSSF Gold) |
