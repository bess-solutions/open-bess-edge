# 📊 BESSAI Edge Gateway — Estado del Proyecto

> **Actualizado:** 2026-03-12 v2.15.1 · **Responsable:** BESS Solutions SpA  
> *Actualiza este archivo en cada iteración junto con CHANGELOG.md y requirements.txt.*

---

## 🎯 ¿Qué es BESSAI?

Sistema industrial de gestión de baterías (BESS) con inteligencia artificial — **candidato a estándar global**. Conecta inversores reales (Huawei SUN2000, SMA, Victron, Fronius) vía Modbus TCP, valida la operación de forma segura, y publica telemetría a GCP Pub/Sub o MQTT con observabilidad completa.

**Visión:** Convertirse en el estándar de referencia mundial para gestión de BESS en el edge — adoptado por fabricantes, operadores y reguladores.  
Ver roadmap oficial: [`docs/ROADMAP.md`](docs/ROADMAP.md) · Roadmap v2 archivado: [`docs/bessai_v2_roadmap.md`](docs/bessai_v2_roadmap.md)

---

## ✅ Estado Actual — v2.15.1 (BESSAIEvolve v2 Fase 1 + Consolidación Cuántica)

> Ver: [`docs/PENDIENTES.md`](docs/PENDIENTES.md) · [`docs/MODULOS_Y_DATOS_SIMULADOS.md`](docs/MODULOS_Y_DATOS_SIMULADOS.md)

### Tests
```
624 passed ✅  · 0 failed · 8 skipped
Nuevo: test_bessai_evolve_v2.py — 24/24 CMAESMutator + NSGA-II + EliteArchive ✅
Nuevo: test_bess_rl_env_cen.py — 23/23 BEP-0200 F3 (env CMg real CEN) ✅
Nuevo: test_milp_optimizer.py — 14/14 MILP optimizer ✅
Nuevo: test_degradation_model.py — 15/15 DegradationModel ✅
Nuevo: test_watchdog_manager.py — 19/19 WatchdogManager ✅
Registry: 7 perfiles hardware (Fronius, Huawei, SMA, Victron + SolarEdge, BYD, Tesla)
CI/CD: ruff ✅ · mypy ✅ · pytest+codecov ✅ · bandit ✅ · trivy ✅ · docker ✅ · helm ✅
Landing: React scrollytelling v1.0 ✅ (i18n ES/EN, Lucide icons)
```

### 🔍 Audit 360° — Gaps Conocidos y Plan de Acción

> Ver detalle completo en [`docs/PENDIENTES.md`](docs/PENDIENTES.md)

| Prioridad | Gap | Archivo | Acción | Target |
|---|---|---|---|---|
| ✅ **CERRADO** | BEP-0200→0300 DRL observe→write | `main.py:Step4c` | `BESSAI_DRL_WRITE=true` implementado con doble guard | v2.15.1 |
| ✅ **CERRADO** | ONNX dummy→real (8 nodos CEN) | `models/` | 24 ONNX (Ridge v2, R²~0.79) entrenados con datos reales | v2.15.1 |
| ✅ **CERRADO** | DuckDB Polpaico 0 filas | `bessai-cen-data/db` | rebuild —  3.496 filas, 8 nodos completos | v2.15.1 |
| ✅ **CERRADO** | GCP no documentado | `docs/SETUP_GCP.md` | Guía completa: SA, roles, topic, terraform | v2.15.1 |
| 🔵 Baja | mypy `modbus_driver.py:179` | Múltiple | type-ignore + guards | v2.15.1 |
| 🔮 Baja | MILP optimizer sin tests de integración | `milp_optimizer.py` | `tests/agents/test_milp_optimizer.py` | v2.15.1 |
| 🔵 Baja | cosign keypair sin configurar | `release.yml` | Rodrigo: `cosign generate-keypair` + Secrets GH | Manual |
| 🟡 Pendiente | GCP Pub/Sub producción | `.env` | Configurar `GCP_PROJECT_ID` + service account | Piloto |
| 🟡 Pendiente | DRL write activo (staging) | `.env` | 2 sem. observe → `BESSAI_DRL_WRITE=true` | Piloto |


### Stack Docker — Métricas en vivo (confirmado 2026-02-19)
```
bess_cycles_total{site_id="SITE-CL-001"}    39      ← ciclos completados
bess_last_power_kw{site_id="SITE-CL-001"}   376.8   ← kW desde Modbus
bess_publish_errors_total                   39      ← GCP no configurado (esperado)
Grafana v10.4.2                             OK      ← localhost:3000 (ver GF_SECURITY_ADMIN_PASSWORD en config/.env)
Prometheus v2.15.1                          OK      ← localhost:9090
```

### Módulos implementados

| Módulo | Archivo | Versión | Estado |
|---|---|---|---|
| CMg Predictor v2 | `src/interfaces/cmg_predictor.py` | **v2.0** | ✅ Producción |
| Arbitrage Engine v2 | `src/interfaces/arbitrage_engine.py` | **v2.0** | ✅ Producción |
| Configuración | `src/core/config.py` | v0.5 | ✅ Producción |
| Seguridad (SOC / Temp) | `src/core/safety.py` | **v1.7.1** | ✅ Producción |
| Orquestador principal | `src/core/main.py` | v0.5 | ✅ Producción |
| Fleet Orchestrator | `src/core/fleet_orchestrator.py` | v0.8 | ✅ Producción |
| Driver Modbus TCP | `src/drivers/modbus_driver.py` | **v2.15.1** | ✅ mTLS opcional (GAP-003) |
| Simulator Driver | `src/drivers/simulator_driver.py` | **v2.15.1** | ✅ 6 tags SPEC-001 normalizadas |
| DataProvider Protocol | `src/drivers/base.py` | **v1.7.1** | ✅ Producción |
| LUNA2000 Driver | `src/drivers/luna2000_driver.py` | **v1.0** | ✅ Producción |
| Servidor /health + /metrics | `src/interfaces/health.py` | v0.5 | ✅ Producción |
| Dashboard API | `src/interfaces/dashboard_api.py` | **v2.15.1** | ✅ Rate limiting SR 7.1 + TOTP |
| TOTP MFA | `src/interfaces/totp_auth.py` | **v2.15.1** | ✅ GAP-001 CLOSED |
| OT TLS Config | `src/interfaces/ot_tls_config.py` | **v2.15.1** | ✅ GAP-003 CLOSED |
| Prometheus metrics (22 total) | `src/interfaces/metrics.py` | v0.9 | ✅ Producción |
| OTel / Cloud Trace | `src/interfaces/otel_setup.py` | v0.9 | ✅ Producción |
| GCP Pub/Sub Publisher | `src/interfaces/pubsub_publisher.py` | v0.5 | ✅ Producción |
| MQTT Publisher | `src/interfaces/mqtt_publisher.py` | **v1.7.1** | ✅ Producción — paho-mqtt, TLS, multi-broker |
| **IEEE 2030.5 Adapter** | `src/interfaces/sep2_adapter.py` | **v1.0** | ✅ **NUEVO v2.6** — 10 endpoints SEP 2.0, TLS 1.2+, mTLS, DERControl (BEP-0100) |
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
| Helm chart | `infrastructure/helm/bessai-edge/` | **0.10.0** | ✅ appVersion 2.10.0 |
| Grafana Dashboard | `infrastructure/grafana/dashboards/bessai_main.json` | **v1.0** | ✅ 13 paneles |
| Terraform GCP | `infrastructure/terraform/` | v0.5 | ✅ 18 recursos |
| Registro Modbus | `registry/huawei_sun2000.json` | **v2.0** | ✅ 28 registros reales |
| Modbus Simulator | `infrastructure/docker/modbus_sim/` | **v1.0.1** | ✅ pymodbus server, 22 registros |
| GitHub Actions CI/CD | `.github/workflows/ci.yml` | v2.15.1 | ✅ **10 jobs**: lint+typecheck+test+interop+security+terraform+helm+docker+trivy+push |
| OpenSSF Scorecard CI | `.github/workflows/scorecard.yml` | v1.0 | ✅ Supply chain security automático — badge Scorecard activo |
| Mutation Testing | `.github/workflows/mutation-test.yml` | v1.0 | ✅ mutmut semanal — safety.py + config.py |
| K8s Manifests | `infrastructure/k8s/` | v1.0 | ✅ 6 manifests: namespace+configmap+service+deployment+netpol+kustomize |
| SBOM + SLSA L2 | `.github/workflows/release.yml` | v1.1 | ✅ CycloneDX SBOM + cosign signing + SLSA Level 2 provenance |
| **DRL Arb. Env (BEP-0200)** | `src/agents/bess_rl_env.py` | **v1.0** | ✅ **NUEVO v2.7** — Gymnasium env 5-min timestep, CMg duck curve, obs 8-d |
| **Arbitrage Policy** | `src/agents/arbitrage_policy.py` | **v1.0** | ✅ **NUEVO v2.7** — 4 reglas CEN Chile, fallback DRL |
| **ONNX DRL Agent** | `src/agents/drl_agent.py` | **v1.0** | ✅ **NUEVO v2.7** — ONNXArbitrageAgent + train_ppo + export_onnx |
| **main.py Step 5e** | `src/core/main.py` | **v2.7** | ✅ **NUEVO v2.7** — ONNXArbitrageAgent integrado (observe-only, env var opt-in) |
| **BESSAI-SPEC-004** | `docs/specs/BESSAI-SPEC-004.md` | **v0.1** | ✅ **NUEVO v2.7** — BatteryState IEEE P2686 data model |
| **Lightweight Mode** | `src/core/lightweight_mode.py` | **v1.0** | ✅ **NUEVO v2.8** — `BESSAI_LIGHTWEIGHT=1` → −50% CPU en RPi 4 |
| **Alert Dispatcher** | `src/core/alert_dispatcher.py` | **v1.0** | ✅ **NUEVO v2.8** — Slack + email SMTP + structured log |
| **BENCHMARK-004** | `docs/benchmarks/BENCHMARK-004-drl-arbitrage.md` | **v1.0** | ✅ **NUEVO v2.8** — DRL +33.5% vs rule-based |
| **BENCHMARK-005** | `docs/benchmarks/BENCHMARK-005-edge-devices.md` | **v1.0** | ✅ **NUEVO v2.8** — RPi4/5, NUC — CPU/RAM/latencia |
| **Registry SolarEdge** | `registry/solaredge_storedge.json` | **v2.0** | ✅ **NUEVO v2.8** — SunSpec Model 124, remote dispatch |
| **Registry BYD** | `registry/byd_battery_box.json` | **v2.0** | ✅ **NUEVO v2.8** — CAN bus 500 kbaud frames completos |
| **Registry Tesla** | `registry/tesla_powerwall3.json` | **v2.0** | ✅ **NUEVO v2.8** — REST API local + Fleet API OAuth2 |
| **MILP Optimizer** | `src/agents/milp_optimizer.py` | **v1.0** | ✅ **NUEVO v2.9** — Optimizador MILP de despacho (PuLP/CBC), complemento DRL |
| **Degradation Model** | `src/agents/degradation_model.py` | **v1.0** | ✅ **NUEVO v2.9** — Steinbuch calendar-aging + cycle-aging model |
| **Benchmark Suite** | `src/agents/benchmark_suite.py` | **v1.0** | ✅ **NUEVO v2.9** — A/B benchmark: DRL vs MILP vs rule-based |
| **CMg Data CEN** | `dashboard/data/cmg_maitencillo.json` | **v1.0** | ✅ **NUEVO v2.9** — 48 días × 288 puntos 5-min, Nodo Maitencillo 220 kV |
| **CMg Exporter** | `scripts/export_cmg_json.py` | **v1.0** | ✅ **NUEVO v2.9** — Generador reproducible con física real SEN |
| **Dashboard DRL** | `dashboard/optimizer.js` + `index.html` | **v2.0** | ✅ **NUEVO v2.9** — Tab DRL Optimizer, SOC trajectory, CMg selector 48 días |
| **WatchdogManager** | `src/core/watchdog_manager.py` | **v1.0** | ✅ **NUEVO v2.9** — Self-healing autónomo, exponential backoff, Prometheus, AlertDispatcher |
| **Scrollytelling Landing** | `landing/` (React + Vite) | **v1.0** | ✅ **NUEVO v2.10** — i18n ES/EN, Lucide icons, FAQ/Features, scrollytelling animations |

### 🐳 Stack Docker — ✅ COMPLETAMENTE OPERATIVO (v1.0.1)

> **Fix v1.0.1:** La imagen `oitc/modbus-server` ignoraba `configuration.json`. Se corrigió montando nuestro config directamente sobre `/app/modbus_server.json` con `listenerPort: 502`. Stack validado con métricas Modbus reales.

```powershell
# Stack completo con simulador + monitoreo:
docker compose -f infrastructure/docker/docker-compose.yml --profile simulator --profile monitoring up -d

# Verificar:
curl http://localhost:8000/health    # gateway health
curl http://localhost:8000/metrics   # prometheus metrics
# Grafana:    http://localhost:3000   (ver GF_SECURITY_ADMIN_PASSWORD en config/.env)
# Prometheus: http://localhost:9090
```

| Contenedor | Estado verificado | Puerto |
|---|---|---|
| `bessai-modbus-simulator` | ✅ **healthy** — escucha en 502 | `host:5020` → `container:502` |
| `bessai-gateway` | ✅ **healthy** — ciclos activos | **`8000`** (/health, /metrics) |
| `bessai-gateway-sim` | ✅ running — conectado al sim | **`8000`** (/health, /metrics) |
| `bessai-otel-collector` | ✅ running | 4317, 4318, 8888 |
| `bessai-prometheus` | ✅ **HTTP 200** | **`9090`** |
| `bessai-grafana` | ✅ **database:ok** v10.4.2 | **`3000`** (ver `GF_SECURITY_ADMIN_PASSWORD` en `config/.env`) |

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

> 🎉 **Sin bloqueadores activos** — CI/CD + Scorecard + Mutation Testing + Fuzzing operativos. OpenSSF Gold ~85% cubierto. IEC 62443 Phase 1 docs listos. Repository lint 100% limpio en v2.15.1.

### ✅ Entregables recientes (v1.8.0–v1.9.0, 22-feb-2026)

| Commit | Entregable | Impacto |
|---|---|---|
| `TBD` | `security_guide_maintainer.md`, `release_process.md` | OpenSSF Silver/Gold — docs completos |
| `TBD` | `fuzzing.yml` — Atheris Modbus + MQTT parsers | OpenSSF Gold — fuzzing crítico |
| `TBD` | `network_diagram.md` — Zonas OT/DMZ/IT + conduits | IEC 62443 SR 5.2 |
| `TBD` | `system_security_plan.md` — SSP FR1–FR7 mapeado | IEC 62443 Phase 1 pre-audit |
| `TBD` | `psirt_process.md` + `patch_management_sla.md` | IEC 62443 SR 2.2 + SR 2.12 |
| `e7d111a` | Scorecard CI, CITATION.cff, badges Codecov+Scorecard | OpenSSF supply chain score |
| `545c084` | Tutorial 5min sin hardware, MQTT+HA tutorial, MkDocs | Onboarding < 5 min |
| `9bc4d78` | K8s manifests (6 archivos), kustomization.yaml | `kubectl apply -k` en K3s/RPi/GKE |

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
v1.8.0  ████████████████████████  ✅ BESSAI Global Standard: specs formales, BEPs, interop, benchmarks, LF Energy
v1.9.0  ████████████████████████  ✅ OpenSSF Gold foundations + IEC 62443 SL-2 Phase 1 docs · fuzzing Atheris
v2.15.1  ████████████████████████  ✅ Fix: 18→0 errores interop · TOTP MFA · Loki SIEM
v2.15.1  ████████████████████████  ✅ mTLS OT segment (GAP-003) · stunnel · OtTlsConfig
v2.15.1  ████████████████████████  ✅ Auditoría IEC 62443 SL-2: SSP, NAD, PMS, PSIRT
v2.15.1  ████████████████████████  ✅ Rate Limiting SR 7.1 · mkdocs nav · pip-audit CI semanal
v2.15.1  ████████████████████████  ✅ Fix: markers pytest · coverage 80% CI · versión `1.4.0`→`2.4.0` en `pyproject.toml` · Dockerfile OCI label
v2.15.1  ████████████████████████  ✅ Fix: import math lint · Helm appVersion · ci.yml Job numbering
v2.15.1  ████████████████████████  ✅ Lint 360°: ruff 35/36 fixes · structlog drl_agent · 490 tests
v2.15.1  ████████████████████████  ✅ Superset: 6 Waves · 3 registry HW · lightweight_mode · alert_dispatcher · 541 tests
v3.0.0  ░░░░░░░░░░░░░░░░░░░░░░░░  📋 Multi-site planetary scale · SL-2 certification
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
| 2026-02-22 | **v1.8.0** | **378/378** | BESSAI Global Standard: `BESSAI-SPEC-001/002/003`, BEP-0001, ADR-007/008, `docs/interoperability/`, benchmarks públicos, `docs/compliance/iec_62443_sl2_certification_path.md`, `lf_energy_proposal.md`, `partnership_program.md` |
| 2026-02-22 | **v1.9.0** | **378/378** | OpenSSF Silver/Gold: `security_guide_maintainer.md`, `release_process.md`, `fuzzing.yml` (Atheris Modbus/MQTT) · IEC 62443 Phase 1: `network_diagram.md`, `system_security_plan.md`, `psirt_process.md`, `patch_management_sla.md` |
| 2026-02-22 | **v2.15.1** | **378/378** | Fix: 18→0 errores interop · TOTP MFA (`totp_auth.py`) · Loki SIEM (`docker-compose.yml`) · `asyncio_mode=auto` funcional |
| 2026-02-22 | **v2.15.1** | **426/426** | GAP-003 mTLS OT: `gen_certs.sh` PKI · `stunnel-ot.conf` TLS 1.3 · `OtTlsConfig.from_env()` · `modbus_driver.py` params TLS |
| 2026-02-22 | **v2.15.1** | **426/426** | Auditoría IEC 62443 SL-2: `ssp_iec62443_sl2.md` (SSP-001) · `network_diagram.md` (NAD-001) · `patch_management_sla.md` · SECURITY.md PSIRT |
| 2026-02-22 | **v2.15.1** | **426/426** | SR 7.1 Rate Limiting (`_RateLimiter`, 300 req/min, `429+Retry-After`) · mkdocs nav SSP/NAD/PMS · `pip-audit` weekly CI · `requirements.hash.txt` scaffold |
| 2026-02-23 | **v2.15.1** | **426/426** | Fix markers pytest (`slow`, `asyncio`) · coverage 80% CI · versión `1.4.0`→`2.4.0` en `pyproject.toml` · Dockerfile OCI label `0.1.0`→`2.4.0` |
| 2026-02-23 | **v2.15.1** | **426/426** | Fix lint `simulator_driver.py` (import math redundante) · Helm `appVersion 0.7.0`→`2.4.0` · `ci.yml` Job numbering 5→10 corregido |
| 2026-02-24 | **v2.15.1** | **490/490** | Lint 360°: ruff 35/36 auto-fix · drl_agent→structlog · 20 archivos reformateados |
| 2026-02-24 | **v2.15.1-dev** | **541/547** | **Superset 6 Waves**: BENCHMARK-004/005 · 3 perfiles HW (SolarEdge/BYD/Tesla) · `lightweight_mode.py` · `alert_dispatcher.py` · 51 tests registry · early_adopters/research_topics/academic_collaboration |
| 2026-02-24 | **v2.15.1-dev** | **590/590** | **AI Environment Devoration**: Fix MARL `rewards[__all__]` · Fix C901 `handle_der_control` refactor · Fix SSL mTLS validation order · **WatchdogManager** self-healing autónomo · 19 tests nuevos |
| 2026-02-25 | **v2.15.1** | **613/613** | **Scrollytelling Landing** (React + Vite): i18n ES/EN, Lucide icons, FAQ/Features refactored, scrollytelling animations · **360° doc sync** · **BEPs 0300/0301/0302** Draft · Archivos propietarios removidos del repo público |
| 2026-02-27 | **v2.15.1** | **685/685** | **BESSAIEvolve v2** (CMAESMutator+NSGA-II+EliteArchive 24/24) · **BEP-0200 F3** env CMg real CEN (23/23) · MILP + Degradation + Watchdog · NTSyCS ComplianceStack 11 GAPs · 685 tests |
| 2026-03-02 | **v2.15.1** | **685/685** | **BEP-0300 activado**: `BESSAI_DRL_WRITE=true` opt-in con doble guard safety+clamp · **24 modelos ONNX reales** (Ridge v2 R²~0.79, 8 nodos CEN) en `models/` · **DuckDB rebuild** 3.496 filas 8 nodos · **docs/SETUP_GCP.md** guía completa |
