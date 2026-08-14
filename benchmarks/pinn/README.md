# 🔬 PINN4SOH-SEN — Prototipo de Validación Conceptual TRL 4
## Physics-Informed Neural Network con Regularización Física de Arrhenius y Monotonicidad para Celdas LFP
**BESS Solutions SpA · Proyecto ANID Startup Ciencia**

---

### 📌 Alcance del Prototipo TRL 4 (Estado de Entrada)

Este repositorio contiene la **prueba de concepto experimental de nivel TRL 4** que valida la viabilidad del enfoque de Redes Neuronales Informadas por la Física (PINN) para la predicción de degradación en celdas de almacenamiento de energía (LFP):

* **Formulación TRL 4 (Entrada)**: Red neuronal que incorpora en su función de pérdida penalizaciones de consistencia física (tasa de degradación térmica regida por la ley de Arrhenius y restricción de monotonicidad termodinámica de capacidad).
* **Desarrollo I+D Financiado por ANID (Salida TRL 6)**: El proyecto financiado por Startup Ciencia desarrollará el acoplamiento completo de las ecuaciones diferenciales parciales de difusión en estado sólido (Ley de Fick), sobrepotencial interfacial (ecuación de Butler-Volmer) y crecimiento cinético de capa SEI, calibrados con datasets de laboratorio y perfiles de subestaciones del SEN.

---

### 📊 Resultados del Benchmarking TRL 4 (Dataset LFP & Perfil Térmico SEN)

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
│ 3. Modelo P2D CPU │    0.00 %    │    0.00 %    │    0.00 %    │    1.420,0000 ms      │
│    (Física Teórica│ (Referencia) │ (Referencia) │ (Referencia) │ (Inviable tiempo real)│
├───────────────────┼──────────────┼──────────────┼──────────────┼───────────────────────┤
│ 4. PINN4SOH-SEN   │  🌟 1.12 %   │  🌟 0.89 %   │  🌟 2.64 %   │      🌟 0.0037 ms     │
│    (Prototipo TRL4│              │              │              │ (Cumple < 100 ms)     │
└───────────────────┴──────────────┴──────────────┴──────────────┴───────────────────────┘
```

---

### 🚀 Instrucciones de Reproducción (1 solo comando)

```bash
# 1. Instalar dependencias científicas
pip install numpy scipy torch

# 2. Ejecutar el benchmark
python benchmarks/pinn/pinn4soh_triple_benchmark.py
```

El script ejecuta el entrenamiento en 300 épocas y exporta las métricas verificadas a `TRL4_BENCHMARK_EVIDENCE_PINN4SOH.json`.
