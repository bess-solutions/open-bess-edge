# BENCHMARK RESULTS — BESSAI v2.14

> **Aviso importante:** Los resultados presentados aquí corresponden a backtesting con datos históricos del CEN Chile (API oficial). No proyectan rendimiento futuro. Metodología y código auditables en este repositorio.

---

## BENCHMARK-004: DRL vs MILP vs Rule-Based

### Configuración del experimento

| Parámetro | Valor |
|-----------|-------|
| Hardware BESS | Huawei SUN2000 200kWh / 100kW |
| Nodo SEN | **Maitencillo_220** (Norte Chico) |
| Período | 48 días continuos |
| Resolución | 5 minutos (288 puntos/día) |
| Total puntos | 13.824 |
| Fuente datos | API CEN Chile — datos CMg oficiales |
| Actualizado | 2026-02-28 |

> 📊 **Trazabilidad:** Los mismos datos CMg del nodo Maitencillo_220 son visibles en el [Dashboard Analítico](https://bessai.io/analytics.html) en tiempo real.

---

### Resultados comparativos

| Métrica | Rule-Based | MILP | **DRL BESSAI ★** |
|---------|-----------|------|------------------|
| Revenue promedio diario | Base 100% | +18.2% | **+33.5%** |
| Revenue estimado / mes | $2.127 USD | $2.514 USD | **$2.840 USD** |
| Decisiones por día | 288 fijas | 288 optimizadas | 288 optimizadas |
| Latencia por decisión | <1ms | ~2.000ms | **<50ms ONNX** |
| Degradación batería | 0.082%/mes | 0.071%/mes | **0.068%/mes** |
| Requiere forecast | No | Sí (24h) | **No (reactivo)** |
| Safety violations | 0 | 0 | **0** |
| Explicabilidad (SHAP) | No | Parcial | **✅ BEP-0301** |

---

### Estadísticas del nodo Maitencillo_220 (período analizado)

| Indicador | Valor | Interpretación BESS |
|-----------|-------|---------------------|
| Media CMg | 127 USD/MWh | Precio base del período |
| Máximo CMg | 280 USD/MWh | Pico de escasez |
| Mínimo CMg | 5 USD/MWh | Duck curve solar |
| P95 | 221 USD/MWh | Umbral descarga BESS (señal venta) |
| P25 | 68 USD/MWh | Umbral carga BESS (señal compra solar) |
| **Spread P95−P25** | **153 USD/MWh** | Motor económico del arbitraje |
| Volatilidad σ | 58.4 USD/MWh | Alta → alto potencial arbitraje |
| Ventanas de arbitraje | 14 | Períodos donde spread > umbral rentabilidad |

---

## BENCHMARK-005: Inferencia ONNX P99

| Métrica | Valor |
|---------|-------|
| Latencia P99 | **42ms** |
| Hardware de prueba | Raspberry Pi 4 (8GB RAM) |
| Runtime | ONNX Runtime 1.17 |
| Modelo | PPO policy network (MLP 3 capas) |

---

## BENCHMARK-006: API REST Throughput P95

| Métrica | Valor |
|---------|-------|
| Throughput P95 | **1.200 req/s** |
| Rate limit (SR 7.1) | 1.200 req/min por IP |
| Autenticación | Bearer token opcional |
| Protocolo | HTTP/1.1 + HTTP/2 |

---

## BENCHMARK-007: RAM footprint — Raspberry Pi 4

| Métrica | Valor |
|---------|-------|
| RAM RSS total | **<180MB** |
| RAM RSS sistema BESSAI | ~140MB |
| RAM RSS ONNX Runtime | ~40MB |
| Swap utilizado | 0MB |

---

## Metodología

### Revenue
```
Revenue = Σ (CMg_t × ΔP_t × Δt)
```
- `CMg_t` = precio spot del CEN en el instante t (USD/MWh)
- `ΔP_t` = potencia inyectada/consumida (kW, positivo = inyección)  
- `Δt` = 5 minutos = 1/12 hora
- Todos los valores usan datos CEN oficiales sin ajustes ni interpolación

### Degradación de batería (Steinbuch dual)
- **Calendar aging**: función de temperatura (Arrhenius)
- **Cycle aging**: función de DoD (Depth of Discharge) y C-rate
- Implementación: `src/agents/degradation_model.py`
- Los tres algoritmos se evaluaron con el **mismo modelo** para comparación justa

### Safety constraints (BEP-0200)
Cada setpoint pasa por `SafetyGuard` antes de escribirse al hardware:
- SOC ∈ [10%, 90%]
- Temperatura < 45°C
- Potencia ≤ capacidad nominal

Si el DRL propone un setpoint fuera de rango, el guardrail lo clipea. **0 eventos alterados en este benchmark.**

---

## Explicabilidad SHAP (BEP-0301)

Los valores SHAP por feature para decisiones representativas del dataset:

| Feature | Importancia SHAP | Interpretación |
|---------|-----------------|----------------|
| SOC actual | 72% | Estado de carga domina la decisión |
| CMg Δ (cambio precio) | 58% | Tendencia de precio reciente |
| Hora del día | 35% | Patrón intra-día (duck curve) |
| Temperatura BMS | 18% | Restricción de seguridad secundaria |

> Los valores SHAP son ilustrativos basados en decisiones representativas del dataset de 48 días.

---

## Reproducir este benchmark

```bash
# Clonar repositorio
git clone https://github.com/bess-solutions/open-bess-edge.git
cd open-bess-edge

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar backtesting con datos CEN
python scripts/run_backtest.py --node MAITENCILLO_220 --days 48

# Ver resultados
cat results/benchmark_004_results.json
```

---

*Generado automáticamente por BESSAI Pipeline · Datos: CEN Chile API oficial*  
*Código y metodología: Apache 2.0 License · Pull requests bienvenidos · [Reproducir benchmark](../Makefile)*
