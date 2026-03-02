# 🧪 BESSAI — Registro de Simulaciones

> **Última actualización:** 2026-03-02 · **Versión:** v2.14.0  
> *Documento vivo — actualizar en cada iteración cuando un componente pase de simulado a real.*

---

## 📋 ¿Para qué sirve este documento?

BESSAI sigue una estrategia **Sim-First**: el sistema arranca completo desde el día 1 usando datos simulados para cada subsistema que aún no tiene su fuente de datos real. Esto permite:

- ✅ Demostrar el sistema funcionando a clientes **inmediatamente**
- ✅ Desarrollar el frontend, dashboard y alertas sin depender de hardware
- ✅ Ejecutar todos los tests sin GCP, Modbus real, ni inversor físico
- 🔄 Reemplazar cada simulación **de forma incremental e independiente**

El principio de factorización central:

```
Capa de lógica de negocio
        │
        ▼
[DataProvider Interface]  ← punto de swap sim ↔ real
        │               │
        ▼               ▼
 SimProvider       RealProvider
(mock/hardcoded)  (Modbus / API / DB)
```

Cada componente simulado tiene su propia interfaz de swap documentada abajo.

---

## 🟥 Leyenda de estado

| Símbolo | Significado |
|---|---|
| 🔴 `SIM` | 100% simulado — datos ficticios hardcodeados |
| 🟡 `PARTIAL` | Lógica real, pero fuente de datos simulada |
| 🟢 `REAL` | Conectado a fuente de datos real en producción |
| ⬜ `N/A` | No aplica simulación (algoritmo puro) |

---

## 📊 Tabla maestra de simulaciones

| # | Componente | Archivo | Estado | Swap requerido | Prioridad |
|---|---|---|---|---|---|
| 1 | Telemetría Modbus | `src/drivers/modbus_driver.py` | 🟡 `PARTIAL` | IP real + perfil JSON | 🔴 Alta |
| 2 | Modelo ONNX de despacho | `src/interfaces/onnx_dispatcher.py` | 🔴 `SIM` | Entrenar + exportar modelo real | 🔴 Alta |
| 3 | Precios CMg | `src/interfaces/cmg_predictor.py` | 🟡 `PARTIAL` | API CEN / Excel coordinador.cl | 🔴 Alta |
| 4 | GCP Pub/Sub publisher | `src/core/main.py` | 🟡 `PARTIAL` | `GCP_PROJECT_ID` + service account | 🟡 Media |
| 5 | AI-IDS (entrenamiento inicial) | `src/interfaces/ai_ids.py` | 🟡 `PARTIAL` | Datos Modbus reales (>500 muestras) | 🟡 Media |
| 6 | Dashboard API — telemetría | `src/interfaces/dashboard_api.py` | 🔴 `SIM` | Conectar a driver Modbus real | 🔴 Alta |
| 7 | Carbon / LCA | `src/interfaces/lca_engine.py` | 🟡 `PARTIAL` | Factor emisión real por sitio (CEN) | 🟢 Baja |
| 8 | P2P Trading | `src/interfaces/p2p_trading.py` | 🔴 `SIM` | Hyperledger Fabric / blockchain real | 🟢 Baja |
| 9 | Fleet Orchestrator — sitios | `src/core/fleet_orchestrator.py` | 🔴 `SIM` | 1+ instalaciones activas | 🟡 Media |
| 10 | VPP / OpenADR 3.0 | `src/interfaces/vpp_publisher.py` | 🔴 `SIM` | Coordinador eléctrico real | 🟢 Baja |
| 11 | MQTT Broker | `src/interfaces/mqtt_publisher.py` | 🟡 `PARTIAL` | `MQTT_BROKER_URL` → broker real | 🟡 Media |
| 12 | Federated Learning | `src/interfaces/fl_client.py` | 🔴 `SIM` | Servidor FL remoto + peers reales | 🟢 Baja |

---

## 🔴 Simulaciones CRÍTICAS — Detalle técnico

### 1. Telemetría Modbus (SIM → REAL)

**Estado actual:** El `docker-compose.yml` incluye un perfil `simulator` que levanta un esclavo Modbus TCP que genera registros aleatorios de SOC, potencia y temperatura.

**Datos simulados:**
```python
# infrastructure/docker/modbus_simulator.py (perfil simulator)
SOC = random.uniform(20, 95)        # % — simulado
POWER_KW = random.uniform(-500, 500) # kW — simulado
TEMP_C = random.uniform(25, 45)      # °C — simulado
CYCLE_COUNT = random.randint(0, 1000)
```

**Swap a REAL:**
```dotenv
# config/.env — reemplazar:
INVERTER_IP=192.168.1.100   # IP real del inversor
INVERTER_PORT=502
MODBUS_UNIT_ID=3            # ver manual del fabricante
DEVICE_PROFILE=huawei_sun2000  # o sma_sunny_tripower, victron_multiplus2, fronius_gen24_byd
```

**Evidencia de que el swap funciona:** El `ModbusDriver` soporta reconexión automática (`_reconnect()`), 6 chaos tests pasan. Solo cambia la fuente de datos.

---

### 2. Modelo ONNX de Despacho (SIM → REAL)

**Estado actual:** `ONNXDispatcher` carga `models/dispatch_policy.onnx`. Si el archivo no existe o la inferencia falla, devuelve `dispatch_kw = 0.0` (modo seguro).

**Datos simulados:**
```python
# src/interfaces/onnx_dispatcher.py — fallback
if self._model is None:
    return DispatchResult(dispatch_kw=0.0, inference_ms=0.0, source="fallback_safe")
```

**Swap a REAL:**
```bash
# 1. Entrenar con datos históricos del CEN (CMg) y Modbus real:
python scripts/train_dispatch_onnx.py \
  --cmg-csv data/cmg_historico.csv \
  --modbus-log data/modbus_telemetria.csv \
  --output models/dispatch_policy.onnx

# 2. El swap es automático — ONNXDispatcher detecta el archivo al arrancar
```

**Entradas del modelo (shape):** `[soc_pct, power_kw, cmg_clp_kwh, hour_of_day, day_of_week]`  
**Salida:** `dispatch_kw` (float, positivo = cargar, negativo = descargar)

---

### 3. Precios CMg (SIM → REAL)

**Estado actual:** `CMgPredictor` tiene dos modos:  
1. **Mock** — genera precios aleatorios entre 50 y 200 CLP/kWh  
2. **CEN API** — llama a `coordinador.cl` (ya implementado, requiere credenciales OAuth2 o Excel público)

**Datos simulados:**
```python
# src/interfaces/cmg_predictor.py
if not self._api_available:
    return [random.uniform(50, 200) for _ in range(24)]  # CLP/kWh
```

**Swap a REAL:**
```dotenv
# Opción A: API OAuth2 CEN (v2)
CEN_API_USER_KEY=tu_clave_aqui

# Opción B: Excel público (fallback, ya implementado en bessai-cen-data)
CMG_SOURCE=excel_public
```

**Referencia:** Ver repo `bessai-cen-data` — orchestrator con multi-source fallback.

---

### 6. Dashboard API — Telemetría (SIM → REAL)

**Estado actual:** Los endpoints `/api/v1/status` y `/telemetry` devuelven datos mock cuando no hay driver Modbus conectado.

**Datos simulados:**
```python
# src/interfaces/dashboard_api.py — mock_data
return {
    "soc_pct": 72.3,        # hardcodeado
    "power_kw": -85.5,      # hardcodeado
    "temp_c": 29.1,         # hardcodeado
    "ai_ids_score": 0.12,   # hardcodeado
}
```

**Swap a REAL:** Conectar la instancia de `ModbusDriver` al `DashboardAPI`:
```python
# En main.py — ya previsto, swap en 3 líneas:
dashboard_api = DashboardAPI(
    driver=modbus_driver,    # ← era None, pasar instancia real
    arbitrage=arb_pipeline,
    ...
)
```

---

## 🟡 Simulaciones PARCIALES — Detalle

### 4. GCP Pub/Sub Publisher

**Modo simulado:** Si `GCP_PROJECT_ID` está vacío, el sistema **no falla** — simplemente loguea los mensajes que habría publicado.

```python
# src/core/main.py
if not _cfg.GCP_PROJECT_ID:
    log.warning("pubsub.disabled", reason="GCP_PROJECT_ID not set")
    publisher = NullPublisher()  # descarta silenciosamente
```

**Swap:** Definir `GCP_PROJECT_ID` y `GCP_PUBSUB_TOPIC` en `.env` + montar service account JSON.

---

### 5. AI-IDS (entrenamiento inicial)

**Modo simulado:** El `ModbusAnomalyDetector` se entrena al arrancar con datos normales generados sintéticamente (distribución Gaussian). A medida que el sistema corre, se **auto-reentrena** con datos Modbus reales.

```python
# src/interfaces/ai_ids.py
if self._training_samples < 500:
    # Bootstrap: entrenar con datos sintéticos
    X_boot = np.random.normal(loc=[75, 0, 30], scale=[15, 50, 5], size=(200, 3))
    self._model.fit(X_boot)
```

**Swap:** Automático — después de 500 ciclos con Modbus real, el modelo se reajusta.

---

### 11. MQTT Broker

**Modo simulado:** Si `MQTT_BROKER_URL` no está definida, el `MQTTPublisher` no arranca y el sistema usa GCP Pub/Sub. Si la URL está definida pero el broker no responde, loguea warning y continúa.

**Swap:** `MQTT_BROKER_URL=mqtt://192.168.1.10:1883` en `.env`. La conexión es lazy + auto-retry.

---

## 🗺️ Hoja de ruta de desimulación — "Sim-to-Real"

Prioridad ordenada para ir de demo a producción con Cliente Cero:

```
FASE 0 (Hoy)          FASE 1 (Semana 1-2)     FASE 2 (Mes 1)        FASE 3 (Mes 2-3)
─────────────         ──────────────────      ─────────────         ─────────────────
🔴 Todo sim           🟡 Modbus real          🟡 CMg real           🟢 Full producción
                      🟡 Dashboard live       🟡 ONNX entrenado
                                              🟡 GCP conectado
```

### Checklist de Cliente Cero

- [ ] **F1.1** IP inversor en `.env` → telemetría Modbus real
- [ ] **F1.2** Dashboard accesible en red local → SOC/potencia real en pantalla
- [ ] **F1.3** MQTT o GCP Pub/Sub conectado → datos en la nube
- [ ] **F2.1** Descargar CMg histórico (bessai-cen-data) → entrenar modelo ONNX
- [ ] **F2.2** Ejecutar `train_dispatch_onnx.py` → `models/dispatch_policy.onnx` real
- [ ] **F2.3** AI-IDS auto-reentrenado después de 500 ciclos Modbus reales
- [ ] **F3.1** Fleet Orchestrator con ≥2 sitios reales
- [ ] **F3.2** Pub/Sub → BigQuery → Grafana dashboards en tiempo real

---

## 🔧 Patrón de factorización recomendado

Para maximizar la reutilización de código entre sim y real, todos los drivers siguen el mismo protocolo:

```python
# Protocolo común (typing.Protocol) — definido en src/drivers/base.py
class DataProvider(Protocol):
    async def read_tag(self, tag_name: str) -> float: ...
    async def write_tag(self, tag_name: str, value: float) -> None: ...
    async def connect(self) -> None: ...

# Implementaciones intercambiables:
class ModbusDriver(DataProvider):   # real
    ...

class SimulatorDriver(DataProvider):  # sim — mismo contrato
    async def read_tag(self, tag_name: str) -> float:
        return SYNTHETIC_DATA[tag_name]()  # lambda con distribución

# En main.py — swap con variable de entorno:
driver: DataProvider = (
    ModbusDriver(host=cfg.INVERTER_IP, ...)
    if cfg.INVERTER_IP else
    SimulatorDriver(profile=cfg.DEVICE_PROFILE)
)
```

**Resultado**: el 100% del código de lógica de negocio (Safety Guard, AI-IDS, Arbitrage, Dashboard) funciona sin cambios tanto con datos simulados como con datos reales.

---

## 📌 Variable de entorno maestra de simulación

Para activar modo demo completo en una sola línea:

```dotenv
# config/.env — modo DEMO (todo simulado, sin conexiones externas)
BESSAI_MODE=demo

# config/.env — modo PRODUCCIÓN (conexiones reales)
BESSAI_MODE=production
INVERTER_IP=192.168.1.100
GCP_PROJECT_ID=mi-proyecto-gcp
```

> [!NOTE]
> `BESSAI_MODE=demo` está previsto como futura feature en la hoja de ruta. Hoy el modo simulado se activa implícitamente cuando `INVERTER_IP` está vacío o apunta al simulador (`modbus-simulator`).

---

*Relacionado: [`docs/quickstart_rpi.md`](quickstart_rpi.md) · [`docs/mqtt_integration.md`](mqtt_integration.md) · [`src/drivers/modbus_driver.py`](../src/drivers/modbus_driver.py)*
