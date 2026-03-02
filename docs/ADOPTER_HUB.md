# 🚀 BESSAI Adopter Hub — Punto de Entrada para Adopters

> **¿Por dónde empiezo?** Esta página te lleva al camino correcto en menos de 2 minutos.

---

## ¿Qué quieres hacer hoy?

```
┌─────────────────────────────────────────────────────────────────┐
│                    ¿Cuál es tu objetivo?                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
         ┌─────────────┼─────────────────┐
         ▼             ▼                 ▼
  [A] Quiero      [B] Quiero        [C] Quiero
   probar/         desplegar en      contribuir
   evaluar         producción        al código
```

---

## Camino A — "Quiero probarlo primero" ⚡

**Tiempo estimado: 5–10 minutos. Solo necesitas Docker.**

| Paso | Qué hacer | Recurso |
|------|-----------|---------|
| 1 | Demo local completa (simulador + Grafana) | [quickstart_5min.md](tutorials/quickstart_5min.md) |
| 2 | Entender la arquitectura general | [architecture.md](architecture.md) |
| 3 | Ver benchmarks reales en campo | [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) |
| 4 | ¿Funciona en mi caso? → FAQ | [FAQ.md](FAQ.md) |
| 5 | ¿Quiero seguir? → Camino B | ↓ abajo |

---

## Camino B — "Quiero desplegarlo en producción" 🏭

**Tiempo estimado: Día 0 a Día 7. Necesitas hardware real o simulado.**

| Paso | Qué hacer | Recurso |
|------|-----------|---------|
| 1 | Roadmap completo día a día | [ONBOARDING_7DAYS.md](ONBOARDING_7DAYS.md) |
| 2 | Requisitos hardware | [PILOT_GUIDE.md → Hardware](PILOT_GUIDE.md#requerimientos-de-hardware) |
| 3 | Conectar tu inversor (Huawei, SolarEdge, etc.) | [tutorials/connecting_real_hardware.md](tutorials/connecting_real_hardware.md) |
| 4 | Configurar `.env` con tus valores | [.env.example](../.env.example) |
| 5 | Guía piloto completa (CEN, compliance, SC bidder) | [PILOT_GUIDE.md](PILOT_GUIDE.md) |
| 6 | Deploy en Raspberry Pi 4/5 | [quickstart_rpi.md](quickstart_rpi.md) |
| 7 | Únete al programa Early Adopters | [early_adopters.md](early_adopters.md) |

---

## Camino C — "Quiero contribuir código o investigación" 🔬

| Paso | Qué hacer | Recurso |
|------|-----------|---------|
| 1 | Setup entorno de desarrollo | [local_development.md](local_development.md) |
| 2 | Issues de bienvenida (Good first issues) | [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md) |
| 3 | Convenciones de commits y PR | [../CONTRIBUTING.md](../CONTRIBUTING.md) |
| 4 | Temas de investigación abiertos | [research_topics.md](research_topics.md) |
| 5 | Colaboración académica | [academic_collaboration.md](academic_collaboration.md) |

---

## Mapa de documentación completo

### 📦 Para Adopters
| Documento | Descripción |
|-----------|-------------|
| [early_adopters.md](early_adopters.md) | Programa Early Adopters — beneficios, perfiles, cómo postular |
| [adopters.md](adopters.md) | Registro de organizaciones que usan BESSAI |
| [FAQ.md](FAQ.md) | Preguntas frecuentes técnicas |
| [ONBOARDING_7DAYS.md](ONBOARDING_7DAYS.md) | Roadmap día 0 → producción |

### ⚡ Inicio rápido
| Documento | Descripción |
|-----------|-------------|
| [tutorials/quickstart_5min.md](tutorials/quickstart_5min.md) | Demo local sin hardware en 5 min |
| [quickstart_rpi.md](quickstart_rpi.md) | Deploy en Raspberry Pi 4/5 |
| [tutorials/integration_homeassistant.md](tutorials/integration_homeassistant.md) | Integración con Home Assistant |

### 🏭 Deployo en producción
| Documento | Descripción |
|-----------|-------------|
| [PILOT_GUIDE.md](PILOT_GUIDE.md) | Guía piloto completa (Chile/CEN) |
| [tutorials/connecting_real_hardware.md](tutorials/connecting_real_hardware.md) | Conexión a hardware real |
| [SETUP_GCP.md](SETUP_GCP.md) | Configuración GCP (telemetría cloud) |
| [API.md](API.md) | Referencia de API REST |

### 🤖 IA y optimización
| Documento | Descripción |
|-----------|-------------|
| [tutorials/training_custom_drl.md](tutorials/training_custom_drl.md) | Entrenamiento DRL personalizado |
| [BESSAI_EVOLVE.md](BESSAI_EVOLVE.md) | Motor de auto-mejora BESSAIEvolve |
| [ai_audit_report.md](ai_audit_report.md) | Auditoría y explicabilidad de modelos IA |

### 📐 Arquitectura y cumplimiento
| Documento | Descripción |
|-----------|-------------|
| [architecture.md](architecture.md) | Arquitectura completa del sistema |
| [compliance/](compliance/) | Mapeo NTSyCS, IEC 62443, OpenSSF |
| [ROADMAP.md](ROADMAP.md) | Roadmap 2026–2027 |

---

## Hardware certificado BESSAI-Compatible

| Fabricante | Modelo | Protocolo | Estado |
|------------|--------|-----------|--------|
| Huawei | SUN2000 + LUNA2000 | Modbus TCP | ✅ Certificado (referencia) |
| SolarEdge | StorEdge | SunSpec Modbus | ✅ Certificado |
| BYD | Battery-Box Premium | CAN bus | ✅ Certificado |
| Tesla | Powerwall 3 | REST API local | ✅ Certificado |
| Cualquier inversor | — | Modbus TCP genérico | ⚙️ Via perfil JSON personalizado |

> Más detalles en [`registry/`](../registry/) y la guía [hardware_profile_contribution.md](tutorials/hardware_profile_contribution.md).

---

## Mercados soportados

| País / Mercado | Estado | Protocolo de mercado |
|----------------|--------|---------------------|
| 🇨🇱 Chile (SEN) | ✅ Producción | NTSyCS · CEN API v2 · SC Bidder |
| 🇲🇽 México (MEM/GDMTH) | ⚙️ Módulo tarifario disponible | CENACE (manual) |
| 🌍 Cualquier mercado | ⚙️ via `.env` custom | Configuración manual de precios |

> ¿Tu mercado no está listado? Lee [FAQ.md → Mi mercado no es Chile](FAQ.md).

---

## Soporte

| Canal | Para qué |
|-------|----------|
| [GitHub Issues](https://github.com/bess-solutions/open-bess-edge/issues) | Bugs, errores técnicos |
| [GitHub Discussions → Early Adopters](https://github.com/bess-solutions/open-bess-edge/discussions) | Postular, preguntas generales |
| `ingenieria@bess-solutions.cl` | Soporte directo para adopters registrados |

---

*¿Algo no está claro? [Abre un issue](https://github.com/bess-solutions/open-bess-edge/issues/new) con la etiqueta `documentation`.*
