# 🔬 Open BESS Edge — Módulo de Investigación & Física Avanzada (Research Core)

El módulo `open-bess-edge/research` integra los estándares científicos mundiales de **The Faraday Institution** y los protocolos abiertos de **Linux Foundation Energy (LF Energy)** dentro del controlador de borde de BESS Solutions:

---

## 📦 Componentes del Módulo

| Módulo | Estándar Internacional | Descripción |
|---|---|---|
| [`bpx_parameter_store.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/bessai-pilot/open-bess-edge/research/bpx_parameter_store.py) | **BPX v1.1.1** (Faraday / BMW) | Repositorio de parámetros electroquímicos de celdas LFP/NMC sin revelar secretos de fabricación. |
| [`physics_informed_twin.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/bessai-pilot/open-bess-edge/research/physics_informed_twin.py) | **PINN & PyECN** (Imperial / Oxford) | Gemelo digital electroquímico de borde que detecta resistencia interna dinámica ($R_{int}$), riesgo de *Lithium Plating* y deriva de salud (SoH). |
| [`bdf_telemetry_streamer.py`](file:///c:/Users/lenovo/OneDrive/Desktop/02_Proyectos_Tech/01_BESS_Tech/bessai-pilot/open-bess-edge/research/bdf_telemetry_streamer.py) | **Battery Data Format (BDF)** (LF Energy) | Streamer de telemetría de alta resolución empaquetada en lotes estándar interoperables con `batterydf` y PyBaMM. |

---

## 🚀 Ejecución y Validación Local

```bash
# Validar el módulo de gestión de parámetros BPX
.venv\Scripts\python open-bess-edge\research\bpx_parameter_store.py

# Validar el gemelo digital físico de borde
.venv\Scripts\python open-bess-edge\research\physics_informed_twin.py

# Validar el streamer BDF
.venv\Scripts\python open-bess-edge\research\bdf_telemetry_streamer.py
```
