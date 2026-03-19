# 🇨🇱 sec-bess-ingestor

> [!WARNING]
> **MÓDULO DEPRECADO — Marzo 2026**
>
> Este módulo ha sido superado por el pipeline de datos CEN production-grade
> en [`bessai-cen-data`](https://github.com/bess-solutions/bessai-cen-data).
>
> **Los GAPs normativos listados abajo están todos cerrados en v2.16.0.**
> La herramienta SEC scraper sigue siendo funcional para monitoreo de cambios
> normativos, pero ya no es el motor principal del sistema de compliance.

---

## Estado actual del compliance (v2.16.0)

Todos los GAPs identificados originalmente por este módulo han sido cerrados
en sucesivas versiones de `open-bess-edge`. El módulo `compliance_stack.py`
en `src/core/` es el motor de compliance activo.

| GAP | Norma | Prioridad | Estado v2.16.0 |
|-----|-------|-----------|----------------|
| GAP-001 | NTSyCS Cap. 4.2 — Ramp Rate Limiting | 🔴 Crítico | ✅ Cerrado — `SafetyGuard` ≤10%/min |
| GAP-002 | NTSyCS Cap. 4.3 — PFR Droop Curve | 🔴 Crítico | ✅ Cerrado — `FrequencyResponseAgent` <2s |
| GAP-003 | NTSyCS Cap. 6.1 — Telemetría CEN | 🔴 Crítico | ✅ Cerrado — `CENPublisher` mTLS |
| GAP-004 | NTSyCS Cap. 6.2 — IEC 60870-5-104 SCADA | 🔴 Crítico | ✅ Cerrado — `IEC104Driver` |
| GAP-005 | NTSyCS 2024 — Canal TLS mTLS→CEN | 🟡 Medio | ✅ Cerrado — `SecurityNotifier` |
| GAP-006 | IEEE 2030.5 — DER en distribución | 🟡 Medio | ✅ Cerrado — BEP-0100, 10 endpoints |
| GAP-007 | Decreto 88/2023 — PMGD con BESS | 🟡 Medio | ✅ Cerrado — `PMGDComplianceEngine` |
| GAP-008 | Ley 21.185 — ERNC almacenamiento | 🟢 Bajo | ✅ Cerrado — `ERNCRegistry` |
| GAP-009 | Res. SEC 2024 — IEC 62443 SL-2 | 🟡 Medio | ✅ Cerrado — `SL2SecurityGate` HMAC-SHA256 |
| GAP-010 | NTCSE — Calidad de Energía THD/Flicker | 🟡 Medio | ✅ Cerrado — `PowerQualityMonitor` |
| GAP-011 | NTSyCS Cap. 4.4 — Control Potencia Reactiva | 🟡 Medio | ✅ Cerrado — `ReactiveController` |

→ Evidencia en [`docs/compliance/`](../docs/compliance/)

---

## Stack actual de datos de mercado

El pipeline de datos de mercado ha evolucionado significativamente desde
que este módulo fue creado. El sistema actual:

```
CEN API (oficial)
    ↓ ingest_all_cen_data.py
bessai_cen.db (DuckDB)
    ├── cmg_historico      ← 111,100 pts horarios (4 nodos, 2023-2026)
    ├── prediction_log     ← log inmutable append-only (SHA-256 encadenado)
    └── cmg_programado     ← day-ahead CEN (pendiente token)
         ↓ write_prediction_log.py (cada hora, schtasks)
         ↓ train_price_model.py (Ridge/LightGBM/Ensemble, 22 features)
         ↓ api/predictions_latest.json → terminal en vivo en bessai-web
```

**Repositorios activos:**
- [`bess-solutions/bessai-cen-data`](https://github.com/bess-solutions/bessai-cen-data) — pipeline de datos privado
- [`bess-solutions/bessai-academic`](https://github.com/bess-solutions/bessai-academic) — dataset CC-BY 4.0 (111,100 pts)

---

## Dataset académico público (CC-BY 4.0)

Para investigación y publicaciones, el dataset de CMg horario está disponible
públicamente en `bessai-academic`:

```python
import pandas as pd
df = pd.read_parquet("cmg_4nodos_2023_2026.parquet")
# 111,100 filas | 4 nodos | Ene 2023 — Mar 2026
```

**Citar como:**
```bibtex
@dataset{bessai_cmg_2026,
  author  = {BESS Solutions},
  title   = {BESSAI CMg Dataset — SEN Chile 2023-2026},
  year    = {2026},
  version = {v1.0.0},
  url     = {https://github.com/bess-solutions/bessai-academic},
  license = {CC-BY 4.0}
}
```

---

## Uso del SEC scraper (referencia histórica)

El módulo sigue siendo funcional para monitorear cambios normativos en la SEC.
Si necesitas ejecutarlo para tracking de nuevas resoluciones:

```bash
cd sec-bess-ingestor
pip install -r requirements.txt

# Raspar SEC Chile (solo lectura)
python cli.py scrape --bess-only

# Analizar brechas vs normativa actual
python cli.py analyze

# Ver reporte
python cli.py report --print
```

> **Nota:** Para publicar al repo vía PR se requiere `GITHUB_TOKEN` con scope `repo`.

---

## Marco normativo cubierto

- **NTSyCS 2022/2024** — Norma Técnica de Seguridad y Calidad del Servicio (CEN)
- **Decreto N°88/2020** (mod. 2023) — Reglamento PMGD
- **Ley N°21.185** — ERNC y almacenamiento
- **Resolución Exenta SEC 2024** — Ciberseguridad infraestructura crítica
- **IEC 62443 SL-1/SL-2** — Ciberseguridad sistemas industriales
- **IEC 60870-5-104** — Protocolo SCADA
- **IEEE 2030.5 / SEP 2.0** — Comunicación DER en distribución
- **NTCSE** — Norma Técnica de Calidad de Servicio Eléctrico
- **Ley 21.663/2024** — Ciberseguridad infraestructura crítica (CSIRT ≤3h)

---

*Módulo histórico de BESSAI Edge Gateway · Estado: Mantenimiento pasivo desde v2.16.0 · 2026*
