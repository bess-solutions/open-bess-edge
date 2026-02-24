# Battery Data Format (BDF) — Alineación BESSAI-SPEC-003/004

> **BEP:** BEP-0202 (Protocol Registry)  
> **Referencia:** https://github.com/lfenergy/battery-data-format · LF Energy  
> **Estado:** 📋 Análisis de alineación — implementación en v2.9.0

---

## ¿Qué es BDF?

**Battery Data Format** es el estándar de LF Energy para representar datos de baterías de forma
interoperable entre fabricantes, operadores y herramientas de análisis. Define:

- Esquemas de datos para ciclos de carga/descarga, degradación, temperatura
- Formatos de exportación: Parquet, HDF5, JSON
- APIs para intercambio entre sistemas de gestión de baterías

---

## Alineación con BESSAI-SPEC

### BESSAI-SPEC-003 (Telemetry Schema) → BDF Cycle Data

| BESSAI campo | BDF equivalente | Notas |
|---|---|---|
| `soc_pct` | `state_of_charge` | Mismo concepto, escala 0-100 vs 0-1 |
| `active_power_kw` | `power_W` | BESSAI en kW, BDF en W (×1000) |
| `voltage_v` | `voltage_V` | Compatible directo |
| `current_a` | `current_A` | Compatible directo |
| `temp_c` | `temperature_C` | Compatible directo |
| `timestamp` (ISO 8601) | `time` (Unix epoch) | Conversión necesaria |

### BESSAI-SPEC-004 (BMS Data Model) → BDF Cell Data

| BESSAI campo | BDF equivalente | Notas |
|---|---|---|
| `cell_voltage_min_v` | `cell_voltage_min` | Compatible |
| `cell_voltage_max_v` | `cell_voltage_max` | Compatible |
| `cell_temp_max_c` | `cell_temperature_max` | Compatible |
| `soh_pct` | `state_of_health` | Compatible (escala) |
| `cycle_count` | `cycle_count` | Compatible |

---

## Exportador BDF (diseño)

```python
# src/interfaces/bdf_exporter.py  (futuro — BEP-0202)

import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime

BDF_SCHEMA = pa.schema([
    pa.field("time", pa.float64()),        # Unix epoch
    pa.field("voltage_V", pa.float32()),
    pa.field("current_A", pa.float32()),
    pa.field("temperature_C", pa.float32()),
    pa.field("state_of_charge", pa.float32()),  # 0..1
    pa.field("power_W", pa.float32()),
    pa.field("cycle_count", pa.uint32()),
    pa.field("state_of_health", pa.float32()),  # 0..1
])

class BDFExporter:
    """Exporta telemetría BESSAI en formato BDF (Parquet)."""
    
    @staticmethod
    def from_bessai_telemetry(records: list[dict]) -> pa.Table:
        return pa.table(
            {
                "time": [r["timestamp_epoch"] for r in records],
                "voltage_V": [r.get("voltage_v") for r in records],
                "current_A": [r.get("current_a") for r in records],
                "temperature_C": [r.get("temp_c") for r in records],
                "state_of_charge": [r.get("soc_pct", 0) / 100 for r in records],
                "power_W": [r.get("active_power_kw", 0) * 1000 for r in records],
                "cycle_count": [r.get("cycle_count", 0) for r in records],
                "state_of_health": [r.get("soh_pct", 100) / 100 for r in records],
            },
            schema=BDF_SCHEMA,
        )
    
    @staticmethod
    def save_parquet(table: pa.Table, path: str) -> None:
        pq.write_table(table, path, compression="snappy")
```

---

## Gaps identificados en BESSAI-SPEC-004

Los siguientes campos de BDF aún no están en BESSAI-SPEC-004 y deben añadirse:

| Campo BDF | Acción en BESSAI-SPEC-004 |
|---|---|
| `cycle_count` | Añadir como campo obligatorio |
| `state_of_health` | Añadir (ya hay `soh_pct` — renombrar) |
| `coulomb_count_Ah` | Añadir como campo opcional |
| `internal_resistance_mOhm` | Añadir como campo opcional |

---

## Dependencias

```toml
# pyproject.toml — extras [bdf]
bdf = ["pyarrow>=14.0", "pandas>=2.0"]
```

---

## Referencias

- [BESSAI-SPEC-003](../specs/BESSAI-SPEC-003.md) — Telemetry Schema
- [BESSAI-SPEC-004](../specs/BESSAI-SPEC-004.md) — BMS Data Model
- [BEP-0202](../bep/BEP-0202.md) — Protocol Registry
- LF Energy BDF: https://github.com/lfenergy/battery-data-format
- BDF Spec v0.2: https://lfenergy.github.io/battery-data-format/
