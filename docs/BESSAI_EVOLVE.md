# 🧬 BESSAIEvolve — IA que se mejora sola

> **Inspirado en AlphaEvolve (Google DeepMind, 2025)**  
> Especificación técnica completa: [BEP-0303](bep/BEP-0303.md)

---

## ¿Qué es AlphaEvolve?

AlphaEvolve es un sistema creado por Google DeepMind que usa un LLM (Gemini) para **proponer mejoras a programas de forma evolutiva**, evaluarlas automáticamente, y conservar sólo las que funcionan mejor. El resultado: programas que se auto-optimizan continuamente sin intervención humana.

Sus principios son simples:

```
Generar mutaciones → Evaluar automáticamente → Conservar al ganador → Repetir
```

---

## ¿Qué implementamos en BESSAI?

Aplicamos los mismos principios a un problema real: **¿cuándo cargar y descargar una batería BESS para maximizar ingresos en el mercado eléctrico chileno?**

```
┌─────────────────────────────────────────────────────────────────┐
│                     BESSAIEvolve — Ciclo semanal                 │
│                                                                   │
│  Generación 0: 10 políticas candidatas                           │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│  │ Baseline │   │Mutante 1 │   │Mutante 2 │   │   ...    │     │
│  │(producción)  │ σ=±10%   │   │ σ=±10%   │   │          │     │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘     │
│        │               │               │                         │
│        └───────────────┴───────────────┘                        │
│                        ▼                                         │
│          🔬 Sandbox: 30 días de precios CMg CEN Chile            │
│          (288 timesteps/día × 30 días = 8.640 pasos)             │
│                        ▼                                         │
│          📊 Fitness = Ingresos / Ingresos_Baseline               │
│                                                                   │
│          🏆 Selección por torneo → top 3 padres                  │
│          🧬 7 nuevos mutantes → siguiente generación             │
│                        ▼                                         │
│          5 generaciones × 10 candidatos = 50 evaluaciones        │
│                        ▼                                         │
│  Si ganador > 5% sobre baseline + 0 violaciones de seguridad:    │
│  📬 Pull Request automático con la política mejorada             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Correspondencia exacta con AlphaEvolve

| Componente AlphaEvolve | Implementación BESSAI | Archivo |
|---|---|---|
| **LLM como mutador** | Perturbación Gaussiana de parámetros *(Gemini en v2)* | `candidate_generator.py` |
| **Base de datos de programas** | `population.json` + `history.jsonl` | `population_manager.py` |
| **Evaluador automatizado** | `BESSArbitrageEnv` + 30 días CMg CEN | `fitness_evaluator.py` |
| **Bucle evolutivo principal** | Estrategia (µ+λ): selección + mutación | `bessai_evolve.py` |
| **Trigger periódico** | GitHub Actions — lunes 00:00 UTC | `bessai-evolve.yml` |

---

## ¿Qué muta exactamente?

El "cromosoma" de cada política candidata son 6 parámetros:

| Parámetro | Significado | Rango |
|---|---|---|
| `cmg_low_threshold_norm` | CMg bajo el cual se carga (precio "barato") | 15–60 USD/MWh |
| `cmg_high_threshold_norm` | CMg sobre el cual se descarga (precio "caro") | 45–135 USD/MWh |
| `soc_min` | SoC mínimo antes de dejar de descargar | 8–25% |
| `soc_max` | SoC máximo antes de dejar de cargar | 85–98% |
| `battery_cost_usd_kwh` | Peso de la penalización por degradación | 150–450 USD/kWh |
| `noise_std` | Incertidumbre del precio observado | 0.5–5 USD/MWh |

---

## ¿Qué pasa cada lunes?

```
00:00 UTC  →  GitHub Actions dispara bessai-evolve.yml
           →  5 generaciones evolutivas en sandbox (~2-5 min)
           →  Artefactos guardados: population.json, history.jsonl
           →  Si hay ganador: PR automático abierto para revisión humana
```

**El modelo de producción no cambia automáticamente** — requiere que un humano revise y apruebe el PR. Esto es intencional: la IA propone, el humano decide.

---

## Garantías de seguridad

- ✅ La evolución ocurre **100% en sandbox** — nunca toca hardware real
- ✅ `SafetyGuard` valida cada paso (SOC, temperatura, potencia)
- ✅ Candidatos con **cualquier violación de seguridad** son rechazados automáticamente
- ✅ Solo mejoras ≥5% sobre baseline califican para PR
- ✅ Revisión humana obligatoria antes de producción

---

## Resultados esperados

Con la configuración actual (Gaussian mutation, 5 generaciones, 30 días):

| Métrica | Valor esperado |
|---|---|
| Evaluaciones por run | 50 (10 candidatos × 5 gen) |
| Tiempo por run | ~2–5 minutos |
| Mejora por generación | +1–3% sobre baseline |
| Mejora acumulada (anual) | **+5–15% de ingresos** sobre política estática |

---

## Hoja de ruta del sistema

| Versión | Mutador | Estado |
|---|---|---|
| **v1 (actual)** | Perturbación Gaussiana de parámetros | ✅ Implementado |
| **v2** | Gemini API propone variaciones del código de reward | 🔵 BEP-0303 planificado |
| **v3** | Federated: múltiples instalaciones BESS aprenden juntas | 🔵 BEP futuro |
