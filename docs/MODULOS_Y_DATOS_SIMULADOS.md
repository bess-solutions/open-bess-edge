# 🧩 Módulos y Datos Simulados — BESSAI Edge Gateway

> **Actualizado:** 2026-02-24 · v2.9.0-dev  
> Este archivo documenta el status real de cada módulo: qué es producción, qué es simulado,  
> y qué datos son sintéticos vs. reales. Crítico para NO confundir capacidades reales con mock.

---

## Leyenda

| Icono | Significado |
|---|---|
| ✅ **Prod** | Código probado en producción con hardware real |
| 🧪 **Sim** | Módulo funcional pero probado solo con datos simulados |
| 🔶 **Mock** | Implementado con datos sintéticos (placeholder) — NO conectado a fuente real |
| 📋 **Design** | Solo diseñado en BEP o doc — no implementado |

---

## src/agents/ — Agentes de IA

| Módulo | Archivo | Status | Datos usados | Datos reales disponibles |
|---|---|---|---|---|
| BESSArbitrageEnv | `bess_rl_env.py` | 🧪 **Sim** | CMg duck curve sintético (parámetros calibrados CEN) | Pendiente BEP-0200 Fase 3 |
| ArbitragePolicy (rule-based) | `arbitrage_policy.py` | ✅ **Prod** | Reglas fijas CEN 2023-2025 | N/A — basado en reglas |
| ONNXArbitrageAgent | `drl_agent.py` | 🔶 **Mock** | Modelo ONNX dummy (`dispatch_policy.onnx`) | Pendiente entrenamiento PPO real |
| **MILP Optimizer** | `milp_optimizer.py` | 🧪 **Sim** | Series CMg sintéticas PuLP/CBC | Conectar a `cmg_maitencillo.json` |
| **Degradation Model** | `degradation_model.py` | 🧪 **Sim** | Parámetros Steinbuch default (LFP/NMC) | Calibrar con datos BESS real |
| **Benchmark Suite** | `benchmark_suite.py` | 🧪 **Sim** | Same simulados que arriba | Requiere ONNX real (BEP-0200 F3) |
| Digital Twin PINN | `digital_twin.py` [PENDIENTE] | 📋 **Design** | N/A | BEP-0201 — v2.10.0 |

---

## dashboard/ — Interfaz de visualización

| Componente | Archivo | Status | Datos usados | Nota |
|---|---|---|---|---|
| CMg data Maitencillo | `data/cmg_maitencillo.json` | 🔶 **Mock** | **98 KB · 48 días · 288 puntos 5-min** generados con física SEN | No es datos CEN API real — son patrones calibrados |
| CMg data exporter | `scripts/export_cmg_json.py` | 🧪 **Sim** | Generador reproducible con duck curve | Seed fija → reproducible |
| SOC trajectory | `optimizer.js` | 🧪 **Sim** | Simulación a partir de CMg mock | Conectar tras BEP-0200 Fase 3 |
| Benchmark display | `optimizer.js` | 🔶 **Mock** | Valores de benchmark hardcodeados (BENCHMARK-004) | Reemplazar con `benchmark_suite.py` live |

---

## src/interfaces/ — Protocolos y conectores

| Módulo | Archivo | Status | Datos usados | Nota |
|---|---|---|---|---|
| Modbus TCP Driver | `modbus_driver.py` | ✅ **Prod** | Inversores reales vía TCP/Modbus | mTLS opcional |
| Simulator Driver | `simulator_driver.py` | ✅ **Prod** | Genera valores deterministas (safe defaults) | Usado en CI y dev |
| IEEE 2030.5 Adapter | `sep2_adapter.py` | ✅ **Prod** | HTTP/TLS endpoints reales | 1 test SSL con mock cert (pre-existente) |
| MQTT Publisher | `mqtt_publisher.py` | ✅ **Prod** | Telemetría real vía paho-mqtt | Multi-broker |
| AI-IDS | `ai_ids.py` | 🧪 **Sim** | IsolationForest entrenado en datos simulados | No entrenado con tráfico real OT |
| ONNX Dispatcher | `onnx_dispatcher.py` | 🔶 **Mock** | `dispatch_policy.onnx` dummy | Reemplazar con modelo real BEP-0200 F3 |
| VPP Publisher | `vpp_publisher.py` | 🧪 **Sim** | OpenADR 3.0 mock server | Sin VPP real conectado |
| FL Client/Server | `fl_client.py`, `fl_server.py` | 🧪 **Sim** | Flower framework, sin datos federados reales | Piloto pendiente |
| LCA Engine | `lca_engine.py` | 🧪 **Sim** | Factores emisión estimados 40+ países | Datos de grillas reales (no medidos) |
| P2P Trading | `p2p_trading.py` | 🧪 **Sim** | Smart contracts sin blockchain real conectada | PoC |
| DataLake Publisher | `datalake_publisher.py` | 🧪 **Sim** | BigQuery mock (sin GCP conectado en dev) | Funcional con credenciales reales |

---

## models/ — Modelos ONNX

| Archivo | Status | Descripción |
|---|---|---|
| `models/dispatch_policy.onnx` | 🔶 **Mock** | Modelo dummy generado por `scripts/generate_dummy_onnx.py` — pesos aleatorios |
| `models/drl_arbitrage_v1.onnx` | 📋 **Pendiente** | Objetivo de BEP-0200 Fase 3 — entrenamiento PPO real con CMg CEN 2023-2025 |

---

## registry/ — Perfiles hardware

| Perfil | Archivo | Status | Registros reales |
|---|---|---|---|
| Huawei SUN2000 | `registry/huawei_sun2000.json` | ✅ **Prod** | 28 registros documentados del manual SUN2000 |
| SMA Sunny | `registry/sma_sunny.json` | ✅ **Prod** | Registros SunSpec Model 1 |
| Victron Multi | `registry/victron_multi.json` | ✅ **Prod** | Registros VE.Bus publicados |
| Fronius Primo | `registry/fronius_primo.json` | ✅ **Prod** | Registros ModbusTCP Fronius |
| SolarEdge StorEdge | `registry/solaredge_storedge.json` | 🧪 **Sim** | SunSpec Model 124 — validar con hardware real |
| BYD Battery-Box | `registry/byd_battery_box.json` | 🧪 **Sim** | CAN frames de documentación pública BYD |
| Tesla Powerwall 3 | `registry/tesla_powerwall3.json` | 🧪 **Sim** | REST API — requiere acceso Fleet API real |

---

## Hoja de ruta para reemplazar mocks con datos reales

| Mock actual | Reemplazo real | BEP | Target |
|---|---|---|---|
| `dispatch_policy.onnx` dummy | `drl_arbitrage_v1.onnx` entrenado con CEN | BEP-0200 Fase 3 | v2.10.0 |
| CMg duck curve sintético | API CEN coordinador.cl (OAuth2) | BEP-0200 Fase 3 | v2.10.0 |
| AI-IDS entrenado en sim | Entrenado en tráfico Modbus real | — | v2.10.0 |
| VPP OpenADR mock | Piloto real CEN/CDEC 5 sitios | BEP-0300 | v3.0.0 |
| SolarEdge/BYD/Tesla perfiles | Validación con hardware físico | — | Hackathon 2026 |
