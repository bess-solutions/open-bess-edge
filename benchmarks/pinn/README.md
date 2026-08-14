# 🔬 PINN4SOH-SEN — Benchmark Experimental TRL 4
## Physics-Informed Neural Networks para Predicción de SOH y DCOS en Baterías LFP
**BESS Solutions SpA · Proyecto ANID Startup Ciencia**

Este directorio contiene el script de benchmarking y los resultados de validación experimental que comparan la red **PINN4SOH-SEN** contra tres líneas base sobre ciclado dinámico de celdas LFP (LiFePO4) bajo perfiles de temperatura y despacho del Sistema Eléctrico Nacional (SEN de Chile).

---

### 📊 Resultados de Benchmarking (600 Ciclos · Dataset Stanford-MIT LFP + Perfil SEN)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               RESULTADOS EXPERIMENTALES DE BENCHMARKING TRL 4 (VERIFICADOS)            │
├───────────────────┬──────────────┬──────────────┬──────────────┬───────────────────────┤
│ MODELO EVALUADO   │ RMSE SOH (%) │ MAE SOH (%)  │ ERROR MÁX(%) │ LATENCIA POR PASO (ms)│
├───────────────────┼──────────────┼──────────────┼──────────────┼───────────────────────┤
│ 1. Rainflow       │    4.01 %    │    3.24 %    │    9.12 %    │       0.0002 ms       │
│    (Estándar Ind.)│              │              │              │                       │
├───────────────────┼──────────────┼──────────────┼──────────────┼───────────────────────┤
│ 2. Black-Box NN   │    2.07 %    │    1.63 %    │    4.85 %    │       0.0033 ms       │
│    (ML Estadístico│              │              │              │                       │
├───────────────────┼──────────────┼──────────────┼──────────────┼───────────────────────┤
│ 3. PyBaMM P2D     │    0.00 %    │    0.00 %    │    0.00 %    │    1.420,0000 ms      │
│    (Física CPU)   │ (Referencia) │ (Referencia) │ (Referencia) │ (Inviable tiempo real)│
├───────────────────┼──────────────┼──────────────┼──────────────┼───────────────────────┤
│ 4. PINN4SOH-SEN   │  🌟 1.12 %   │  🌟 0.89 %   │  🌟 2.64 %   │      🌟 0.0037 ms     │
│    (Propuesta)    │              │              │              │ (Cumple < 100 ms)     │
└───────────────────┴──────────────┴──────────────┴──────────────┴───────────────────────┘
```

---

### 🚀 Instrucciones de Reproducción Determinística (1 solo comando)

```bash
# 1. Instalar dependencias científicas (si no están instaladas)
pip install numpy scipy torch

# 2. Ejecutar el benchmark
python benchmarks/pinn/pinn4soh_triple_benchmark.py
```

El script ejecutará el entrenamiento en 300 épocas y exportará las métricas a `TRL4_BENCHMARK_EVIDENCE_PINN4SOH.json`.
