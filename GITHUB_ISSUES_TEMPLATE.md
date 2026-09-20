# GitHub Issues - Open BESS Edge Performance Improvements

## Issue 1: [P0] LATENCIA DE LAZO CERRADO - Paralelización de Evaluadores

```markdown
# [P0] Optimizar Latencia de Lazo Cerrado (4-7ms → 0.05-0.15ms)

## Descripción
La versión actual ejecuta evaluadores de forma **secuencial** (Safety → FFR → VoltVar), 
resultando en latencias de **4-7 ms** por ciclo. El objetivo CEN/NTSyCS es < 500ms para FFR, 
pero podemos alcanzar **0.05-0.15 ms** mediante paralelización asyncio.

## Problema Raíz
- Cada `await` induce context switch sin paralelización
- Evaluadores de Safety y FFR son independientes pero corren secuencialmente
- Polling de telemetría sin estrategia de caché

## Solución Propuesta
- ✅ Crear evaluadores paralelos (`_eval_safety_async`, `_eval_ffr_async`)
- ✅ Usar `asyncio.gather()` para ejecutar en paralelo
- ✅ Precalcular constantes (P_nom, Q_max, capacity) en `__init__`
- ✅ Implementar caché de último estado seguro

## Impacto
- **Latencia:** -95% (4-7ms → 0.05-0.15ms)
- **Throughput:** +47x (142 → 6,666 ciclos/s)
- **CPU Context Switches:** -60%

## Archivos Afectados
- `src/edge_node.py` → Crear `src/edge_node_optimized.py`
- `src/config.py` → Validación early-binding

## Referencias
- CEN CFyDR 2026: Tiempo respuesta FFR < 500ms
- NTSyCS Cap. 3: Latencia de control < 1s
- IEEE 1547: Respuesta dinámica de BESS < 100ms

## Checklist de Implementación
- [ ] Crear `src/edge_node_optimized.py` con paralelización
- [ ] Implementar precálculo de constantes
- [ ] Agregar `asyncio.gather()` en `step_optimized()`
- [ ] Mantener backward compatibility con `step()`
- [ ] Tests de latencia (p95 < 0.5ms, p99 < 2ms)
- [ ] Benchmark comparativo original vs optimizado
- [ ] Documentación en OPERATIONAL_PROCEDURES.md
```

---

## Issue 2: [P1] WATCHDOG DE SEGURIDAD EN TIEMPO REAL

```markdown
# [P1] Agregar Watchdog para Detección de Deadlock

## Descripción
Implementar mecanismo de supervisión que detecte deadlocks en el lazo de control 
y ejecute shutdown automático después de timeout.

## Problema
- Sin watchdog: deadlock silencioso → downtime manual (∞)
- Disponibilidad actual: 99.7% → necesario: 99.95%
- Tiempo de detección de fallo: Manual → Automático

## Solución Propuesta
- ✅ Clase `EdgeNodeWatchdog` en thread separado
- ✅ Heartbeat después de cada ciclo exitoso
- ✅ Timeout 10-15 segundos
- ✅ Señal `SIGUSR1` para shutdown limpio en caso de timeout

## Impacto
- **Uptime:** 99.7% → 99.95% (+0.25%)
- **Recovery Time:** Manual (∞) → Automático (10-15s)
- **MTBF:** Mejora significativa

## Archivos
- `src/edge_node_optimized.py` - Integrar `EdgeNodeWatchdog`
- `docs/OPERATIONAL_PROCEDURES.md` - Documentar procedimiento

## Implementación
```python
watchdog = EdgeNodeWatchdog(timeout_s=10.0)
watchdog.start()

# En cada ciclo exitoso
watchdog.heartbeat()

# En stop()
watchdog.stop()
```

## Testing
- Test de detección de timeout después de N segundos sin heartbeat
- Test de recovery automático
```

---

## Issue 3: [P1] RESILIENCIA DE COMUNICACIONES MODBUS

```markdown
# [P1] Graceful Degradation - Estrategias de Fallback Modbus

## Descripción
Implementar múltiples estrategias de fallback cuando falla comunicación Modbus TCP:
1. TCP Normal (primaria)
2. RTU Serial (fallback)
3. Graceful Degradation (cache + predicción)
4. Safety Hold (mantenimiento de setpoint seguro)

## Problema Actual
- Solo TCP: sin fallback
- Falla de comunicación = downtime total
- Unavailability ~0.3% por comunicaciones

## Solución Propuesta
- ✅ `read_telemetry_with_fallback()` con 4 estrategias
- ✅ `_synthesize_readings_from_cache()` con derivada mínima
- ✅ Transiciones automáticas entre modos
- ✅ Logging de transiciones

## Impacto
- **Disponibilidad:** 99.7% → 99.97% (-90% downtime por comms)
- **Recovery:** Automático en < 30s
- **Operabilidad:** No requiere intervención manual

## Archivos
- `src/drivers/modbus_client.py` - Agregar fallbacks
- `tests/test_modbus_resilience.py` - Suite de tests

## Modos de Operación
| Modo | Comunicación | Telemetría | Duración |
|------|--------------|-----------|----------|
| NORMAL | TCP | Real-time | ∞ |
| FALLBACK_RTU | Serial | Real-time | ∞ |
| GRACEFUL_DEGRAD | None | Cache + Predicción | 30s máx |
| SAFETY_HOLD | None | Último setpoint seguro | ∞ |

```

---

## Issue 4: [P1] TELEMETRÍA Y OBSERVABILIDAD - Prometheus Metrics

```markdown
# [P1] Integración Prometheus para Observabilidad Operacional

## Descripción
Exponer métricas clave en Prometheus para:
- Monitoreo en tiempo real (Grafana dashboards)
- Alertas de degradación operacional
- Análisis histórico de comportamiento
- Detección predictiva de fallos

## Métricas a Exponer

### Histogramas
- `bess_edge_cycle_latency_ms` - Latencia de ciclo (p50, p95, p99)
- `bess_edge_ffr_response_time_ms` - Tiempo respuesta FFR en contingencia

### Contadores
- `bess_edge_safety_trip_count_total` - Disparos de seguridad (por fault_code)
- `bess_edge_modbus_errors_total` - Errores Modbus (por tipo)

### Gauges
- `bess_edge_soc_percent` - State of Charge
- `bess_edge_soh_percent` - State of Health
- `bess_edge_p_setpoint_kw` - Consigna de potencia activa
- `bess_edge_q_setpoint_kvar` - Consigna de potencia reactiva
- `bess_edge_f_measured_hz` - Frecuencia de red
- `bess_edge_v_measured_v` - Tensión de red
- `bess_edge_cell_v_imbalance_mv` - Desbalance de voltaje
- `bess_edge_cell_temp_max_c` - Temperatura máxima
- `bess_edge_dc_isolation_kohm` - Aislamiento DC

## Impacto
- **Visibilidad:** 0% → 100%
- **MTTR:** 2-4h → 10-15 min (-85%)
- **Predictibilidad:** N/A → 85% detección anticipada

## Archivos
- `src/services/metrics_prometheus.py` - Nuevo módulo ✅
- `src/edge_node_optimized.py` - Integración de métricas
- `infrastructure/docker-compose.yml` - Prometheus + Grafana
- `config/grafana_dashboards/` - Dashboards JSON

## Servidor HTTP
- Puerto: 8001
- Endpoint: `http://localhost:8001/metrics`
- Scrape interval recomendado: 10s

## Testing
- Test que metrics se incrementan correctamente
- Test de permisos (usuario bessedge sin privilegios)
```

---

## Issue 5: [P2] CACHÉ Y MEMOIZACIÓN - Lookup Tables

```markdown
# [P2] Precompute LUTs y Memoización - Reducir CPU

## Descripción
Reemplazar cálculos repetitivos por tablas precalculadas:
- Tabla droop: Δf → P (1M ciclos = 3M ops innecesarias)
- Tabla volt/var: V_pu → Q

## Solución
- ✅ `_precompute_droop_curve()` en `__init__`
- ✅ `_precompute_volt_var_curve()` en `__init__`
- ✅ Búsqueda en LUT durante ciclo (O(1))

## Impacto
- **Operaciones aritmética/ciclo:** -80%
- **Cache Hit Rate:** ~99.5%
- **Instrucciones CPU/ciclo:** -80%

## Archivos
- `src/edge_node_optimized.py` - LUT methods

## Precisión
- Resolución droop: 1 mHz
- Resolución volt/var: 0.1% V
- Error máximo: < 0.1% vs cálculo exacto
```

---

## Issue 6: [P2] GESTIÓN DE MEMORIA - Pool de Objetos

```markdown
# [P2] Optimización de Memoria - Object Pooling

## Descripción
Reducir presión de garbage collection mediante:
- `@dataclass(slots=True)` para objetos resultado
- Reutilización de buffers
- Cleanup periódico de métricas old

## Problema
- 1M ciclos/hora × 16 campos dict = 16M objetos/hora
- Heap memory: 250-300 MB
- GC pauses: 2-5ms cada 3-5 segundos

## Solución
- ✅ `CycleSummary` con `@dataclass(slots=True, frozen=True)`
- ✅ Pool de objetos reutilizables
- ✅ Buffer circular para histórico (maxlen)

## Impacto
- **Heap Memory:** -75% (250MB → 50-80MB)
- **GC Pauses:** -90% (2-5ms → <0.5ms)
- **GC Frequency:** -95% (3-5x/s → 0-1x/min)

## Archivos
- `src/edge_node_optimized.py` - Dataclass + slots

```

---

## Issue 7: [P2] VALIDACIÓN DE CONFIGURACIÓN

```markdown
# [P2] Early-binding Configuration Validation

## Descripción
Validar configuración en bootstrap (antes de operar) usando Pydantic validators.

## Problema
- Errores de config detectados tardíamente (en `step()`)
- Sin chequeos de coherencia entre módulos
- Downtime por config inválida: 10-30 min

## Solución
- ✅ `@field_validator` en Pydantic models
- ✅ `validate_cross_constraints()` para coherencia inter-módulos
- ✅ Logging de advertencias no-críticas

## Validaciones
- `bess_hardware`: P_nom > 0, E >= 0.5*P, C-rate en rango
- `grid_code`: f_nom ~50Hz, estatismo CEN [0.02-0.05], deadband oficial ±30mHz
- `modbus`: puerto [1-65535], timeout [0.1-30]s
- `cross_constraints`: rampa mínima para respuesta FFR

## Impacto
- **Errores Detectados en Bootstrap:** N/A → 100%
- **Downtime por Config:** 10-30min → 0min

## Archivos
- `src/config.py` - Agregar validators
```

---

## Issue 8: [P3] ESCALABILIDAD MODULAR - Inyección de Dependencias

```markdown
# [P3] Refactor para Inyección de Dependencias

## Descripción
Desacoplar componentes mediante inyección de dependencias para mejorar:
- Testabilidad (+45%)
- Extensibilidad (+1 componente = 1 fichero)
- Reusabilidad de código

## Solución
- ✅ Interfaces (ABC) para `TelemetryDriver`, `SafetyEvaluator`, `FrequencyController`
- ✅ `BESSEdgeNode.__init__()` acepta inyecciones
- ✅ Defaults robustos si no se inyecta

## Ejemplo
```python
# Inyectar mock driver para testing
mock_driver = MockTelemetryDriver()
mock_driver.inject_readings(BESSReadings(...))

node = BESSEdgeNode(
    config=EdgeConfig(),
    driver=mock_driver,
    safety=SafetyEnvelopeEvaluator()
)
```

## Impacto
- **Testabilidad:** 40% → 85%+ cobertura
- **Time to Feature:** 3-5 días → 4-6 horas

## Archivos
- `src/drivers/telemetry_driver.py` - Nueva interfaz
- `src/safety/safety_evaluator.py` - Nueva interfaz
- `src/controllers/frequency_controller.py` - Nueva interfaz
- `src/edge_node_optimized.py` - Refactor constructor
```

---

## Issue 9: [P3] DOCUMENTACIÓN OPERACIONAL

```markdown
# [P3] Procedimientos Operacionales - OPERATIONAL_PROCEDURES.md

## Descripción
Crear documentación de procedimientos operacionales incluyendo:
- Modos de operación (Normal, Degradado, Safety Hold)
- Checklist pre-operacional
- Diagnóstico de fallos
- Escalas de respuesta esperadas
- Procedimiento ante degradación

## Contenido Propuesto
1. **Modos de Operación**
   - NORMAL: Todos los evaluadores activos
   - DEGRADADO: Cache + predicción (30s máx)
   - SAFETY_HOLD: Setpoint seguro, indefinido

2. **Checklist Pre-Operacional**
   - Config YAML válida y coherente
   - Conexión Modbus TCP funcional
   - Métricas Prometheus accesibles
   - Watchdog activo
   - Últimos 10 ciclos < 1.0 ms
   - SOC 20-80%, Temp < 45°C

3. **Diagnóstico**
   - Latencia > 1ms: Revisar CPU, memoria, I/O
   - Modbus timeout: Fallback automático a RTU
   - Safety trip: No reiniciar, contactar soporte

4. **Métricas Clave a Monitorear**
   - p95 latencia < 0.5ms, p99 < 2ms
   - Safety trip count = 0 (operación normal)
   - FFR response p95 < 300ms
   - Modbus error rate < 0.1%
   - SOC rango 20-80%

## Archivos
- `docs/OPERATIONAL_PROCEDURES.md` - Nuevo ✅
```

---

# Resumen de Issues

| # | Título | Prioridad | Esfuerzo | ROI | Estado |
|---|--------|-----------|----------|-----|--------|
| 1 | Latencia Lazo | P0 | 3 días | 40-140x | 🆕 |
| 2 | Watchdog | P1 | 1 día | 99.95% uptime | 🆕 |
| 3 | Resiliencia Comun. | P1 | 2 días | 99.97% uptime | 🆕 |
| 4 | Prometheus Metrics | P1 | 3 días | MTTR -85% | ✅ (código en src/services) |
| 5 | Caché & LUTs | P2 | 1 día | CPU -80% | 🆕 |
| 6 | Gestión Memoria | P2 | 2 días | Heap -75% | 🆕 |
| 7 | Validación Config | P2 | 1 día | 0 errors | 🆕 |
| 8 | Escalabilidad | P3 | 4 días | Test +45% | 🆕 |
| 9 | Documentación Op. | P3 | 2 días | MTTR -50% | 🆕 |

---

# Cómo Usar Este Archivo

1. Copiar cada Issue a https://github.com/bess-solutions/open-bess-edge/issues/new
2. Usar las descripciones propuestas como template
3. Etiquetar con `performance`, `optimization`, `enhancement`
4. Enlazar con PRs que se generen
5. Seguimiento en proyecto/milestone "Performance Phase 1"
```

