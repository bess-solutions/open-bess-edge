# Tutorial: Entrenar y Desplegar un Agente DRL Personalizado

> **Dificultad**: Avanzado · **Tiempo estimado**: 2–4 horas  
> **BEP**: [BEP-0200](../bep/BEP-0200.md) · **Componente**: `src/agents/`

Este tutorial te lleva paso a paso desde la instalación de Ray RLlib hasta tener tu propio modelo ONNX corriendo en un dispositivo edge.

---

## Requisitos previos

- Python 3.11+
- BESSAI Edge Gateway instalado (`pip install -e .`)
- Al menos 8 GB de RAM (16 GB recomendado para entrenamiento)
- Datos de precios CMg (ver [bessai-cen-data](https://github.com/bess-solutions/bessai-cen-data)) o perfil sintético

---

## Paso 1: Instalar dependencias de entrenamiento

Las dependencias de Ray RLlib son **opcionales** y no se instalan con el gateway por defecto (para mantener la imagen edge liviana).

```bash
# Instalar Ray RLlib + PyTorch + ONNX export
pip install "ray[rllib]>=2.9" torch>=2.2 onnx>=1.15 onnxruntime>=1.17

# Verificar instalación
python -c "import ray; print('Ray:', ray.__version__)"
python -c "import torch; print('PyTorch:', torch.__version__)"
python -c "import onnxruntime; print('ORT:', onnxruntime.__version__)"
```

---

## Paso 2: Entender el entorno de entrenamiento (BESSArbitrageEnv)

El entorno `BESSArbitrageEnv` implementa la interfaz Gymnasium con:

**Espacio de observación** (8 variables):

| Variable | Descripción | Rango |
|---|---|---|
| `soc_pct` | Estado de carga de la batería | [0, 100] |
| `active_power_kw` | Potencia activa actual | [-max_kw, max_kw] |
| `cmg_actual` | Precio CMg actual (USD/MWh) | [0, 500] |
| `cmg_forecast_1h` | Pronóstico CMg +1h | [0, 500] |
| `cmg_forecast_4h` | Pronóstico CMg +4h | [0, 500] |
| `hora_del_dia` | Hora UTC | [0, 23] |
| `dia_semana` | Día de la semana | [0, 6] |
| `temp_bateria_c` | Temperatura de la batería | [0, 60] |

**Espacio de acción**: continuo, `[-1, 1]` → potencia en pu (negativo = carga, positivo = descarga).

**Función de recompensa**:

```python
reward = (
    power_kw * cmg_usd_mwh / 1000        # ingreso por despacho (USD)
    - degradacion_penalty(soc, cycles)    # penalización por degradación
    - safety_penalty(soc, temp)           # penalización por operar fuera de rango
)
```

---

## Paso 3: Preparar datos CMg personalizados

Puedes usar el **perfil sintético** (incluido por defecto) o **datos reales** del CEN Chile:

### Opción A: Perfil sintético (por defecto)

```python
from src.agents.bess_rl_env import BESSArbitrageEnv

# Sin datos → usa perfil sintético calibrado con CMg chileno 2023-2025
env = BESSArbitrageEnv(capacity_kwh=200.0, max_power_kw=100.0)
```

### Opción B: Datos reales CEN (recomendado para producción)

```python
import numpy as np

# Cargar datos desde bessai-cen-data (formato: array 1D de 8760 precios horarios)
cmg_data = np.load("data/cmg_horario_2024.npy")  # desde bessai-cen-data

env = BESSArbitrageEnv(
    capacity_kwh=200.0,
    max_power_kw=100.0,
    cmg_profile=cmg_data,          # perfil personalizado
)
```

### Opción C: Tu propio perfil de mercado

```python
# Para mercados distintos al chileno (ej. MISO, ERCOT, MIBEL)
my_prices = np.array([...])  # array de precios spot horarios en USD/MWh

env = BESSArbitrageEnv(
    capacity_kwh=500.0,    # tu capacidad BESS
    max_power_kw=250.0,    # tu potencia máxima
    cmg_profile=my_prices,
)
```

---

## Paso 4: Entrenar el agente PPO

```python
from src.agents.drl_agent import train_ppo
import numpy as np

# Opcional: cargar datos CMg reales
cmg_profile = np.load("data/cmg_horario_2024.npy")

# Entrenar (esto puede tomar 30–90 minutos según tu hardware)
checkpoint_path = train_ppo(
    cmg_profile=cmg_profile,      # None → usa perfil sintético
    capacity_kwh=200.0,
    max_power_kw=100.0,
    num_iterations=200,            # 200 iteraciones = convergencia estable
    checkpoint_dir="models/checkpoints/mi_agente",
    stop_reward=30.0,              # parar si reward medio supera 30 USD/episodio
    extra_config={
        # Ajustar hiperparámetros si lo necesitas:
        # "lr": 1e-4,              # tasa de aprendizaje más conservadora
        # "gamma": 0.995,          # mayor horizonte temporal
        # "num_env_runners": 4,    # más workers (requiere más RAM)
    },
)

print(f"Checkpoint guardado en: {checkpoint_path}")
```

> **Tip**: Para ajustar hiperparámetros, comienza con 50 iteraciones para verificar que el reward está creciendo antes de lanzar el entrenamiento completo.

---

## Paso 5: Exportar a ONNX para edge

```python
from src.agents.drl_agent import export_onnx

# Exportar el checkpoint entrenado a ONNX
onnx_path = export_onnx(
    checkpoint_path=checkpoint_path,
    output_path="models/mi_agente_v1.onnx",
    obs_dim=8,  # debe coincidir con BESSArbitrageEnv
)

print(f"Modelo ONNX exportado: {onnx_path}")
print(f"Tamaño: {onnx_path.stat().st_size / 1e6:.1f} MB")  # objetivo: < 50 MB
```

---

## Paso 6: Desplegar en el edge gateway

Copia el archivo `.onnx` al dispositivo edge (Raspberry Pi, NUC industrial, etc.) y configura el gateway:

### 6a. Via variable de entorno

En tu `.env`:

```env
# Activar el agente DRL personalizado
BESSAI_DRL_MODEL_PATH=/opt/bessai/models/mi_agente_v1.onnx
BESSAI_DRL_ENABLED=1
```

### 6b. Instanciar directamente en código

```python
from src.agents.drl_agent import ONNXArbitrageAgent
from src.agents.arbitrage_policy import ArbitragePolicy

# Fallback automático a rule-based si el modelo falla
fallback = ArbitragePolicy()
agent = ONNXArbitrageAgent(
    model_path="models/mi_agente_v1.onnx",
    fallback=fallback,
)

# Verificar que el agente cargó correctamente
if agent.is_available:
    print("✅ Agente DRL activo")
else:
    print("⚠️  Agente DRL no disponible — usando fallback rule-based")

# Inferencia (en el loop principal)
import numpy as np
obs = np.array([65.0, 0.0, 82.5, 75.0, 68.0, 14, 2, 27.0], dtype=np.float32)
p_pu, info = agent.predict(obs)
power_kw = p_pu * 100.0  # kW

print(f"Acción: {power_kw:.1f} kW (fuente: {info['source']})")
```

---

## Paso 7: Medir desempeño del agente en producción

Usa el `AgentBenchmarkReporter` para monitorear el rendimiento durante operación real:

```python
from src.agents.drl_agent import AgentBenchmarkReporter

reporter = AgentBenchmarkReporter(agent)

# Obtener métricas acumuladas
metrics = agent.metrics
print(f"Latencia media ONNX: {metrics['mean_inference_ms']:.2f} ms")
print(f"Tasa de fallback: {metrics['fallback_rate_pct']:.1f} %")
print(f"Ingresos acumulados: {metrics['total_revenue_usd']:.2f} USD")
```

---

## Solución de problemas frecuentes

| Problema | Solución |
|---|---|
| `ImportError: Ray RLlib not installed` | Ejecutar `pip install "ray[rllib]>=2.9"` |
| `ImportError: PyTorch required for ONNX export` | Ejecutar `pip install torch>=2.2` |
| Ray no inicializa con `num_env_runners=2` | Reducir a `num_env_runners=1` en hardware limitado |
| Reward no converge después de 100 iteraciones | Revisar que el perfil CMg tiene variabilidad suficiente (std > 10 USD/MWh) |
| Modelo ONNX > 50 MB | Reducir `fcnet_hiddens` a `[128, 128]` en `extra_config` |

---

## Recursos adicionales

- [BEP-0200: DRL Arbitrage Agent](../bep/BEP-0200.md)
- [BENCHMARK-004: Resultados de referencia](../benchmarks/BENCHMARK-004-drl-arbitrage.md)
- [bessai-cen-data: Datos históricos CMg Chile](https://github.com/bess-solutions/bessai-cen-data)
- [Ray RLlib docs](https://docs.ray.io/en/latest/rllib/index.html)
- [ONNX Runtime docs](https://onnxruntime.ai/)

---

*¿Necesitas ayuda? Abre un [GitHub Discussion](https://github.com/bess-solutions/open-bess-edge/discussions) con la etiqueta `drl-agent`.*
