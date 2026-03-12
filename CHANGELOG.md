# CHANGELOG — BESSAI Edge Gateway (`open-bess-edge`)

> **📌 NOTA PARA AGENTES IA — Leer antes de continuar el trabajo**
>
> Este documento es el punto de entrada para cualquier agente IA que tome control de este repositorio.
> Revisa la seción **[AGENT HANDOFF]** antes de escribir cualquier código.

---


## [Unreleased]

### 🚀 Feat — v2.15.0: BESSAIServer integrado en main.py (2026-03-02)
- **src/core/main.py**: `HealthServer` reemplazado por `BESSAIServer` — 8 endpoints activos en el loop productivo
  - `GET /health` → liveness + safety + compliance_score por ciclo
  - `GET /compliance/status` + `GET /compliance/report` → NTSyCS estado en tiempo real (fed desde `ComplianceStack.run_cycle()`)
  - `GET /fleet/summary` + `GET /fleet/sites` → KPIs VPP multi-sitio listos para FleetOrchestrator
  - `GET /api/v1/telemetry` → snapshot SOC, P(kW), T(°C) último ciclo
  - `set_cycle(cycle, ok, safety_status)` — actualiza cada ciclo (incluyendo SAFETY_BLOCK path)
  - `set_compliance_state(all_ok, score, violations, cycle)` — compliance en tiempo real en `/compliance/status`
  - `set_telemetry({soc_pct, p_kw, temp_c, safety_ok})` — telemetría REST viva en `/api/v1/telemetry`
- **Commit:** `420a93d` — `feat(v2.15.0): mount BESSAIServer in main.py — 8 endpoints active`
- **Backwards compatible:** `HealthServer` sigue activo para `tests/test_health.py` (unit tests intactos)

### 🔐 Security — PI Protection Policy v1.2 (2026-03-02)
- **pre-commit hook**: `.githooks/pre-commit` bloquea ONNX, `.env`, certificados, tarifas y credenciales antes de cada commit
- **git filter-repo**: historial completo purgado — `dispatch_policy.onnx`, `training_summary.json`, `gdmth_mexico.json` eliminados de todos los commits anteriores
- **docker-compose.production.yml**: `GF_SECURITY_ADMIN_PASSWORD` movida a `config/.env` (no más valores hardcoded)
- **models/training_summary.json**: agregado explícitamente a `.gitignore`
- **Makefile**: `make dev` activa el hook de seguridad automáticamente; eliminada última referencia `admin/bessai`
- **scripts/install_hooks.sh**: instalación de hooks en un comando para nuevos colaboradores
- **infrastructure/docker/docker-compose.yml**: `GF_SECURITY_ADMIN_PASSWORD` ahora usa variable de entorno con fallback `changeme_on_first_login`
- **Eradicación total**: `admin/bessai` eliminado de `CONTRIBUTING.md`, `PROJECT_STATUS.md`, `docs/local_development.md`, `README.md`

### 📚 Docs — Wave 7: Adopter Documentation Package (2026-03-02)
- **docs/ADOPTER_HUB.md** (NEW): Hub central de adopción con decision tree — probar / desplegar / contribuir
- **docs/ONBOARDING_7DAYS.md** (NEW): Roadmap día 0 → producción con hardware real + IA activa
- **docs/FAQ.md** (NEW): FAQ técnica — hardware alternativo, mercados LATAM/globales, licencia, troubleshooting
- **docs/CONTRIBUTING_ADOPTERS.md** (NEW): Guía del primer PR para adopters (perfiles hw, bug reports, docs)
- **scripts/setup.sh** (NEW): Setup interactivo — 5 preguntas → `config/.env` generado con password Grafana auto
- **.github/ISSUE_TEMPLATE/adopter_support.yml** (NEW): Template soporte onboarding
- **.github/DISCUSSION_TEMPLATE/early_adopter_intro.yml** (NEW): Formulario postulación Early Adopters
- **mkdocs.yml**: sección `Para Adopters` como primera pestaña de navegación (6 docs)
- **Makefile**: targets `make setup` y `make onboard` — setup interactivo + hooks en un comando
- **README.md**: sección `Para Early Adopters` visible al tope + Quick Start con `setup.sh` como paso 0
- **docs/index.md**: sección Early Adopters con tabla de rutas de adopción
- **docs/early_adopters.md**: fix licencia AGPL-3.0 → Apache 2.0 (bug); template → link a DISCUSSION_TEMPLATE
- **docs/tutorials/quickstart_5min.md**: eliminada referencia hardcoded `admin/bessai`
- **docs/tutorials/connecting_real_hardware.md**: link roto `bounty_program.md` corregido
- **docs/quickstart_rpi.md**: `setup.sh` como paso de configuración; links adopción en próximos pasos
- **docs/runbook.md**: versión v1.4.0 → v2.14.0; sección Recursos para adopters
- **docs/local_development.md**: versión v0.4.1 → v2.14.0; `setup.sh` como primer paso
- **docs/BENCHMARK_RESULTS.md**: licencia MIT → Apache 2.0
- **docs/ROADMAP.md**: Wave 7 documentada; pendientes actualizados
- **docs/adopters.md**: fecha actualizada 2026-03-02; link a ADOPTER_HUB


## 🤖 AGENT HANDOFF — Estado actual del proyecto (2026-03-02T19:05 -03:00)

> [!IMPORTANT]
> **Sprint 2026-03-02 — Adopter Documentation Wave 7 + Auditoría de Seguridad Completa**
>
> El repositorio `open-bess-edge` completó un sprint enfocado en **reducir la fricción de adopción** y asegurar el repositorio público. Todo empujado a `main`.

### ✅ Completado en esta sesión (commit range: `2d48b0c` → `1a03abc`)

| Área | Entregables | Commit |
|------|-------------|--------|
| **Setup** | `scripts/setup.sh` — config/.env interactivo en 2 min; `make setup` + `make onboard` | `9ebbd1d` |
| **Docs Adopción** | `ADOPTER_HUB.md` · `ONBOARDING_7DAYS.md` · `FAQ.md` · `CONTRIBUTING_ADOPTERS.md` | `4d91dd2` |
| **Templates** | `.github/ISSUE_TEMPLATE/adopter_support.yml` · `.github/DISCUSSION_TEMPLATE/early_adopter_intro.yml` | `4d91dd2` |
| **Navegación** | mkdocs.yml: `Para Adopters` como primera sección (6 docs) | `9ebbd1d` |
| **Seguridad** | docker-compose.yml: `GF_SECURITY_ADMIN_PASSWORD` env var; erradicación total `admin/bessai` | `f294f0a` |
| **Auditoría docs** | 79 docs auditados · fix 2×AGPL-3.0 bug · fix 2×`cp .env.example` roto · 12+ versiones sincronizadas | `1a03abc` |
| **Blog** | `bessai-web/blog.html`: OBE-DOC-001 agregado (push manual pendiente por workspace) | local |

### 🔜 Próximas prioridades (v2.15.0)

1. `src/interfaces/server.py` → mount en `main.py` reemplazando `HealthServer`
2. `src/core/cen_sc_bidder.py` → integrar en main loop post-ComplianceStack
3. Datos reales CEN → entrenar PPO 500k steps → `models/dispatch_policy.onnx` real
4. Activar `CENSCBidder` en producción (`dry_run=False` post-registro CEN)
5. FleetOrchestrator: añadir sitios 2+3 (VPP multi-site activo)
6. **Push blog.html**: `cd bessai-web && git add blog.html && git commit -m "blog: OBE-DOC-001" && git push`

---


> [!IMPORTANT]
> **Sprint v2.14.0 — BESSAIServer unificado, SC bidder automático CEN, BEP-0200 Phase 3 PPO**

### Entregables v2.14.0

| Archivo | Descripción |
|---|---|
| `src/interfaces/server.py` | `BESSAIServer` — 8 endpoints unificados: `/health` `/metrics` `/compliance/status` `/compliance/report` `/fleet/summary` `/fleet/sites` `/api/v1/telemetry`. Stateful, aiohttp |
| `src/core/cen_sc_bidder.py` | `CENSCBidder` — licitación automática SC (PFR/CREG/AGC/SE) al CEN con mTLS, dry-run, auto-bid loop, stats y métricas de revenue |
| `src/core/ppo_trainer.py` | `PPOTrainer` + `BESSDispatchEnv` — BEP-0200 Phase 3: entorno Gymnasium 8-feat, reward multi-obj, entrenamiento PPO vía SB3 o fallback validation, exportación ONNX con metadata JSON |
| `tests/test_cen_sc_bidder.py` | 20 tests: elegibilidad SOC/P_nom, construcción bids, payload NTSyCS, dry-run, revenue |
| `tests/test_ppo_trainer.py` | 9 tests: obs/step/reset, SOC clamping, episodio, CMg sintético |
| `.github/workflows/pilot-validation.yml` | 4 jobs CI paralelos: NTSyCS 11 GAPs, BEP-0200 PPO, BESSAIServer smoke, Pilot Readiness. Weekly regression check |
| `Makefile` | +7 targets: `test-compliance` `train-ppo` `cert` `pilot` `compliance-report` `fleet` + `SITE_ID`/`PORT` vars |

### Próximas prioridades v2.15.0

- `src/interfaces/server.py` — mount en `main.py` reemplazando `HealthServer`
- `src/core/cen_sc_bidder.py` — integrar en main loop post-ComplianceStack
- Datos reales CEN → entrenar PPO 500k steps → `models/dispatch_policy.onnx`
- Activar `CENSCBidder` en producción (dry_run=False post-registro CEN)
- FleetOrchestrator: añadir sitios 2+3 (VPP multi-site activo)

---

## 🤖 AGENT HANDOFF — Estado anterior v2.13.0 (2026-02-28T13:49 -03:00)

> [!IMPORTANT]
> **v2.13.0 — Infraestructura de Producción LISTA** (2026-02-28)
>
> ComplianceStack wired · REST API compliance · mTLS certs · Pilot setup wizard · Docker production

> ### Entregables v2.13.0
>
> | Archivo | Commit |
> |---|---|
> | `src/core/config.py` — 15 vars NTSyCS/SC/CEN | `e6be52a` |
> | `src/core/main.py` — ComplianceStack (startup + loop) | `e6be52a` |
> | `.env.example` — template completo 30+ vars | `e6be52a` |
> | `src/interfaces/compliance_api.py` — `/compliance/status` + `/report` | `c5bca2b` |
> | `infrastructure/certs/gen_certs.sh` — mTLS CEN GAP-003 | `c5bca2b` |
> | `scripts/pilot_setup.py` — readiness wizard 0-100 | `c5bca2b` |
> | `docker-compose.production.yml` | `c5bca2b` |
> | `docs/PILOT_GUIDE.md` | `c5bca2b` |

> ### Próximas prioridades — v2.14.0
>
> 1. Arrancar el primer sitio piloto real (ver `docs/PILOT_GUIDE.md`)
> 2. API REST compliance → integrar al HealthServer en misma instancia
> 3. PPO training con datos reales CEN → `models/dispatch_policy.onnx` real
> 4. VPP FleetOrchestrator: agregar 3 sitios para SC






### 📚 Documentation
- **edge**: v2.15.1 PROJECT_STATUS sync 2026-03-12 (`aa16c354`, @BESS Solutions)
- **edge**: v2.15.1 PROJECT_STATUS sync 2026-03-12 (`79af26d4`, @BESS Solutions)
- **edge**: v2.14.0 PROJECT_STATUS sync 2026-03-11 (`3eed376f`, @BESS Solutions)
- **edge**: v2.14.0 PROJECT_STATUS sync 2026-03-04 (`4ef8fd8d`, @BESS Solutions)
- **edge**: v2.12.0 PROJECT_STATUS sync 2026-03-03 (`95ce9a5d`, @BESS Solutions)
- final deep-audit — fix AGPL bug in research_topics, date sync (`1a03abc5`, @BESS Solutions)
- deep audit batch — version sync, setup.sh, arch diagram (`f541687a`, @BESS Solutions)
- final audit — fix license bug, update versions, complete CHANGELOG (`e0d64648`, @BESS Solutions)
- mass update — version fixes, adopter links, security cleanup (`a5a80c46`, @BESS Solutions)
- **adopters**: friction reduction — setup targets, contributing guide, README fixes (`9ebbd1d0`, @BESS Solutions)
- complete early adopter documentation package (`ba4474e3`, @BESS Solutions)
- **edge**: v2.12.0 PROJECT_STATUS sync 2026-03-02 (`738010a4`, @BESS Solutions)
- add BENCHMARK_RESULTS.md with complete benchmark data, CEN correlation Maitencillo_220, methodology and SHAP explainability (`43725aff`, @BESS Solutions)
- expand PILOT_GUIDE.md to v2.14.0 — hardware reqs, SC bidder, PPO training, timeline (`50481c51`, @BESSAI sec-ingestor)
- update README + CHANGELOG to v2.12.0 state (`4e5edbd1`, @BESSAI sec-ingestor)

### 🔐 Security
- eradicate all admin/bessai references from the entire codebase (`f294f0a5`, @BESS Solutions)
- final PI cleanup — remove hostname refs, admin/bessai, analysis artifacts (`3068d543`, @BESS Solutions)
- add pre-commit PI protection hook + fix last hardcoded refs (`ad49e1c3`, @BESS Solutions)
- remove hardcoded Grafana password + untrack proprietary AI artifacts (`f502d34c`, @BESS Solutions)
- **pi**: remove FL client/server — moved to bessai-core (private) (`9736306c`, @BESSAI sec-ingestor)
- **pi**: migrate AI agents to private bessai-core repo (`a2e50533`, @BESSAI sec-ingestor)
- **pi**: SECURITY.md + parametrize SC prices via env vars (`8280f53c`, @BESSAI sec-ingestor)
- extend .gitignore PI protection policy v1.1 (`62527583`, @BESSAI sec-ingestor)

### 🐛 Bug Fixes
- repair 6 broken internal links (exhaustive link scan) (`1790f17e`, @BESS Solutions)
- remove broken image in quickstart_5min.md (`aeedafdb`, @BESS Solutions)
- **mkdocs**: remove nav duplicates found in pre-close review (`434f394f`, @BESS Solutions)
- **tariffs**: tarifas GDMTH reales DOF agosto 2025 - BASE 0.9649 INTER 1.8829 PUNTA 2.1757 MXN/kWh cargo demanda 102.05/kW (`7b388db1`, @BESS Solutions)
- **quality**: remediacion completa Pyright 0 errores + Bandit 0 alertas Medium/High (`bbb366cc`, @BESS Solutions)

### 🔧 Maintenance
- 360Deg consolidation 2026-03-12 v2.15.1 (`bfedfa11`, @BESS Solutions)
- 360Deg consolidation 2026-03-12 v2.15.1 (`3be19636`, @BESS Solutions)
- 360Deg consolidation 2026-03-11 v2.14.0 (`d23612da`, @BESS Solutions)
- 360Deg consolidation 2026-03-11 v2.14.0 (`a44a45bd`, @BESS Solutions)
- 360Deg consolidation 2026-03-11 v2.14.0 (`a76c3304`, @BESS Solutions)
- **release**: transversal BESSAI ecosystem iteration (`70015031`, @BESS Solutions)
- untrack secrets.yaml.template, add k8s secrets pattern to .gitignore - Agente del Orden (`b271c549`, @BESS Solutions)
- remove mypy_output_v2.txt analysis artifact from tracking (`c1bd7c0b`, @BESS Solutions)
- **repo**: remover website/ del tracking + actualizar .gitignore (`6bfc2eae`, @BESS Solutions)
- remove deprecated fetch_cmg_evolution.py (superseded by bessai_data_scraper.py) (`1f734cd4`, @BESS Solutions)

### ✨ New Features
- **bep0200-p3**: PPO DRL trainer + 8 CEN ONNX models + global market adapters v2.15.2 (`18e51e30`, @BESS Solutions)
- **v2.15.0**: mount BESSAIServer in main.py — 8 endpoints active (`fb29fdae`, @BESS Solutions)
- **adopters**: setup interactivo + mkdocs nav + discussion template (`4d91dd22`, @BESS Solutions)
- v2.12.0 — BEP-0300 write_tag + 24 ONNX reales + SETUP_GCP.md + PROJECT_STATUS (`f3ab9cf7`, @BESS Solutions)
- **pilot**: compliance REST API + mTLS certs + pilot setup wizard (`c5bca2b9`, @BESSAI sec-ingestor)
- **production**: wire ComplianceStack + NTSyCS env vars + .env.example (`e6be52a4`, @BESSAI sec-ingestor)
- NTSyCS Full Compliance Sprint v2.12.0 — 11 GAPs, 148 tests, ComplianceStack (`d1fa7440`, @bess-solutions)
- **analytics**: LoadProfiler Mexico CFE GDMTH - ingesta/limpieza/resampleo/etiquetado tarifario, 29 tests, demo sintetico (`7c2b53b0`, @BESS Solutions)
- **docs**: agregar GOOD_FIRST_ISSUES.md (12 issues), TECHNICAL_RECOMMENDATIONS.md (5 REQs), limpiar Makefile duplicado (`642899a9`, @BESS Solutions)
- **ai**: BESSAIEvolve v2 - CMA-ES + NSGA-II + Elite Archive (Fase 1 plan 20/10) (`cdf85807`, @BESS Solutions)
- **ai-20-10**: XAI engine, auto-retrain loop, dummy ONNX generator, perf baseline (`a1f10f13`, @BESS Solutions)
- **workflows**: add 8 power workflows for BESSAI monster automation (`0be81e39`, @BESS Solutions)

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
| `bessai-grafana` (monitoring) | disponible | **3000** (ver `GF_SECURITY_ADMIN_PASSWORD` en `config/.env`) |

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
# Esperado: 613 passed ✅ (v2.10.0)

# Health endpoint (requiere Docker)
Invoke-RestMethod http://localhost:8000/health | ConvertTo-Json

# Métricas Prometheus
Invoke-WebRequest http://localhost:8000/metrics | Select-Object -Exp Content
.venv\Scripts\Activate.ps1
pytest tests/ -v --tb=short
# Expected: 613 passed in ~43s ✅
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

## [v2.10.0] — 2026-02-25

> **Hito:** Scrollytelling Landing + OpenSSF Compliance + 360° Audit + BEPs 0300/0301/0302

### Added
- `docs/API.md` — Documentación de interfaz externa (Modbus, REST, MQTT, Pub/Sub, SEP2, OTel, env vars) para cumplimiento OpenSSF
- `docs/bep/BEP-0300.md` — DRL Autonomous Control: protocolo para activar `write_tag()` real con safety protocol
- `docs/bep/BEP-0301.md` — XAI Layer: SHAP explainability para agentes DRL e IDS
- `docs/bep/BEP-0302.md` — Real-Time Market Integration: CMg live feed multi-fuente (CEN API v2 + Excel scraper)

### Changed — 360° Consistency Audit (13 fixes)
- `CONTRIBUTING.md` — test count `372` → `613` (era v2.7)
- `README.md` — árbol de archivos `490/490` → `613/613`; estado proyecto `-dev` eliminado; OpenSSF badge `Passing` → `In Progress`
- `pyproject.toml` — email autor `@bess-solutions.com` → `@bess-solutions.cl`
- `CHANGELOG.md` — AGENT HANDOFF test count `590` → `613`; comandos validación `54/45` → `613`
- `PROJECT_STATUS.md` — Helm `appVersion 2.6.0` → `2.10.0`; gaps table targets `v2.9.0` → `v2.11.0`
- `docs/ROADMAP.md` — título `v2.7` → `v2.10`; Estado actual heading; BEP-0200 target actualizado
- `mkdocs.yml` — `docs/API.md` añadido a navegación; BEP-0300/0301/0302 añadidos
- `docs/bep/BEP-0202.md` — release targets `v2.9.0` → `v2.11.0`
- `docs/interoperability/BDF_alignment.md` — target `v2.9.0` → `v2.11.0`

### Removed — Privacy & Repository Sanitization
- `landing/` (35 archivos) — Aplicación React/Vite movida a repo privado
- `dashboard/` (5 archivos) — UI propietaria + datos CMg CEN Chile removidos
- `docs/MANUAL_ACCIONES_RODRIGO.md` — Documento interno de acceso propietario
- `docs/PLAN_INMORTALIDAD.md` — Plan estratégico interno
- `docs/MODULOS_Y_DATOS_SIMULADOS.md` — Estado operacional interno
- `docs/PENDIENTES.md` — Backlog interno con detalles de infraestructura privada
- `.gitignore` — Rutas propietarias bloqueadas permanentemente
- **Historial git purgado** via `git filter-repo` — 138 commits reescritos

### Tests
```
613 passed ✅ · 0 failed · 6 skipped · 43.21s
```

---

## [v2.8.0-dev] — 2026-02-24

> **Hito:** Superset — 11 recomendaciones superadas con entregables de producción (6 Waves)

### Added — Wave 1: DRL Agent Madurez
- `docs/benchmarks/BENCHMARK-004-drl-arbitrage.md` — Benchmark público DRL vs rule-based: **+33.5% ingresos anuales** con `ONNXArbitrageAgent` (PPO). Latencia edge < 3 ms en RPi 5.
- `docs/tutorials/training_custom_drl.md` — Tutorial completo Ray RLlib → ONNX export → edge deploy. Cubre datos CEN, hiperparámetros, exportación cuantizada, rollback a `ArbitragePolicy`.

### Added — Wave 2: Hardware Registry (+3 fabricantes)
- `registry/solaredge_storedge.json` — SolarEdge StorEdge (SunSpec Model 124): remote dispatch via registros 57348–57362, safe-mode, read-back verification.
- `registry/byd_battery_box.json` — BYD Battery-Box Premium LVS: CAN bus 500 kbaud, frames 0x0351/0x0355/0x0356/0x035A con DBC parseable.
- `registry/tesla_powerwall3.json` — Tesla Powerwall 3: REST API local (`/api/1/`) + Fleet API OAuth2 (`fleet-api.prd.vn.cloud.tesla.com`).
- `docs/tutorials/hardware_profile_contribution.md` — Guía contribución registry: template JSON, transforms, niveles certificación (experimental → community → manufacturer), proceso PR.
- `tests/interop/test_new_profiles.py` — **51 tests de validación automática** (schema, integridad datos, regresión todos los perfiles). 51/51 ✅

### Added — Wave 3: Edge Optimization
- `docs/benchmarks/BENCHMARK-005-edge-devices.md` — CPU, RAM y latencia en RPi 4 (4GB), RPi 5 (8GB), Intel NUC i5-1235U. Conclusión: BESSAI cabe cómodamente en todos.
- `src/core/lightweight_mode.py` — `LightweightModeManager`: activa con `BESSAI_LIGHTWEIGHT=1`, desactiva OpenTelemetry / AI-IDS full / VPP / P2P / FL / debug logging. −50% CPU en RPi 4.

### Added — Wave 4: AI-IDS Mejorado
- `src/core/alert_dispatcher.py` — `AlertDispatcher` multicanal: Slack webhook (attachment JSON con color por severidad), email SMTP (HTML con tabla de tags), structured log (fallback). Configurable 100% via env vars. Severidades INFO/WARNING/CRITICAL.

### Added — Wave 6: Comunidad y Academia
- `docs/early_adopters.md` — Programa Early Adopters: 5 categorías, criterios de elegibilidad, template de GitHub Discussion, proceso de selección en 5 pasos.
- `docs/research_topics.md` — 7 temas de investigación abiertos: DRL volatilidad, Transformers AI-IDS, PINN Digital Twin RUL, VPP frecuencia, Modbus security IEC 62443 SL-2, Carbon P2P tokenizado, Multi-activo (BESS+V2G+HP).
- `docs/academic_collaboration.md` — Modalidades FONDECYT, cursos universitarios, política de publicaciones, mentoría individual. Tabla de universidades en conversación.
- `docs/ROADMAP.md` — Añadida sección **Superset Q1-Q2 2026** con tabla de 6 Waves y totales de registry/benchmarks/tutoriales.

### Tests
```
541 passed ✅ · 1 failed (SSL PEM pre-existente, no-regresión) · 5 skipped · 16.65s
Nuevo: test_new_profiles.py — 51/51 registry validation tests
```

---

## [v1.9.0] — 2026-02-22

> **Hito:** OpenSSF Silver/Gold foundations + IEC 62443 SL-2 Phase 1 documentation

### Added — OpenSSF Gold Badge

- `docs/security_guide_maintainer.md` — Guía de seguridad completa para maintainers (GPG signing, 2FA, branch protection, secrets management, incident response). Satisface criterio Silver/Gold OpenSSF.
- `docs/release_process.md` — Proceso de release documentado (step-by-step: pre-checks, versioning, tag, CI pipeline, post-verification, rollback). Satisface criterio Silver/Gold OpenSSF.
- `.github/workflows/fuzzing.yml` — Fuzzing semanal (Atheris) sobre parsers críticos Modbus + MQTT. Satisface criterio Gold OpenSSF: "fuzzing of critical inputs".

### Added — IEC 62443 SL-2 Phase 1 (Pre-Assessment Deliverables)

- `docs/architecture/network_diagram.md` — Diagrama formal de arquitectura de red: Zonas OT/DMZ/IT, definición de conduits C1–C4, reglas firewall, mapeo a SR 5.2. Satisface IEC 62443-3-3 SR 5.2.
- `docs/architecture/system_security_plan.md` — System Security Plan (SSP) base: mapeo completo de todos los Security Requirements (FR1–FR7), estado actual de implementación, gaps y plan de remediación. Documento central para auditor SL-2.
- `docs/compliance/psirt_process.md` — Proceso formal PSIRT: lifecycle de vulnerabilidades, SLA por severity CVSS, coordinación con reporter, CVE numbering. Satisface IEC 62443-3-3 SR 2.12.
- `docs/compliance/patch_management_sla.md` — SLA formal de gestión de parches: Critical 14d / High 30d / Medium 90d, detection sources, prioritization matrix, metrics. Satisface IEC 62443-3-3 SR 2.2.

### Changed

- `docs/openssf_gold_checklist.md` — Actualizado: 12 ítems marcados como completados en v1.9.0. Estado: ~85% Gold criteria cubiertos (pendiente Rodrigo: 2FA + marcar checkboxes en bestpractices.dev).

### Tests
```
378 / 378 passed ✅ (sin regresión)
CI: ruff ✅ · mypy ✅ · pytest ✅ · bandit ✅ · trivy ✅
New workflows: fuzzing.yml (semanal — Atheris Modbus/MQTT)
```

---

## [v1.4.0] — 2026-02-21

> **Hito:** Nivelación a estándares internacionales de software industrial open source

### Added
- **Gobernanza OSS** (requerida por CNCF/Linux Foundation):
  - `SECURITY.md` — responsible disclosure, SLAs, protocolo emergencia ICS, safe harbor
  - `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1
  - `GOVERNANCE.md` — roles (Maintainer/Contributor/Community), proceso de decisiones, release policy
  - `CONTRIBUTING.md` — setup entorno, convención commits, reglas safety-critical, cómo añadir drivers
- **GitHub Templates**:
  - `.github/ISSUE_TEMPLATE/bug_report.yml` — 10 campos con componente, OS, logs
  - `.github/ISSUE_TEMPLATE/feature_request.yml` — área, motivación, voluntad de contribuir
  - `.github/pull_request_template.md` — checklist con Safety Impact Assessment
  - `.github/dependabot.yml` — actualizaciones semanal: pip + github-actions + docker
- **Supply Chain Security en CI** (`ci.yml` a 9 jobs):
  - Job `security`: `bandit -r src/ --severity medium` (SAST) + `pip-audit --requirement requirements.txt` (CVE deps)
  - Job `trivy`: escaneo imagen Docker, resultados subidos al GitHub Security tab (SARIF)
- **SBOM + Firma de release** (`release.yml`):
  - Job `generate-sbom`: CycloneDX JSON + XML adjuntos como asset del GitHub Release
  - Job `sign-image`: cosign keyless signing (Sigstore) de la imagen Docker en Artifact Registry
- **Architecture Decision Records** (`docs/adr/`):
  - ADR-0001: pydantic-settings para configuración (vs dynaconf/configparser)
  - ADR-0002: `struct` stdlib para Modbus encoding (vs BinaryPayloadDecoder removido en pymodbus 3.12)
  - ADR-0003: IsolationForest + z-score ensemble para AI-IDS (vs autoencoder/SVM)
  - ADR-0004: ONNX Runtime para inferencia offline en edge (vs PyTorch/TFLite)
  - ADR-0005: GCP Pub/Sub para telemetría (vs MQTT/Kafka/AWS IoT)
- **Documentación de compliance** (`docs/compliance/`):
  - `ntscys_compliance.md` — mapeo formal NTSyCS CEN Chile (Cap. 4, 6, 8)
  - `iec62443_mapping.md` — IEC 62443-3-3 SL-1: 7 Foundation Requirements mapeados a implementación
- **Prometheus Alerting** (`infrastructure/prometheus/`):
  - `alert_rules.yml` — 12 reglas en 4 grupos: availability, safety, AI-IDS, connectivity
  - `prometheus.yml` — `rule_files` activado apuntando a `alert_rules.yml`
- **pyproject.toml**: sección `[tool.bandit]` con skips ajustados al codebase
- **README.md**: 4 nuevos badges (Security Policy, OpenSSF Best Practices, IEC 62443, NTSyCS)

### Tests
```
372 / 372 passed (sin regresión)
CI: ruff ✅ · format ✅ · 9 jobs activos
```

---

## [v1.3.2] — 2026-02-21

### Fixed
- **CI / Formato (ruff format)** — 4 archivos reformateados que bloqueaban el pipeline:
  - `src/interfaces/arbitrage_engine.py`
  - `src/interfaces/cmg_predictor.py`
  - `src/interfaces/dashboard_api.py`
  - `tests/test_luna2000_driver_async.py`

### Changed
- Documentación actualizada: suite real en **372 tests** (vs 228 documentados en v1.3.1)
- `PROJECT_STATUS.md` — versión bump a v1.3.2, historial actualizado

### Tests
```
372 / 372 passed (suite completa open-bess-edge)
CI verde: ruff ✅ · mypy ✅ · pytest ✅ · helm ✅ · terraform ✅
```

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
