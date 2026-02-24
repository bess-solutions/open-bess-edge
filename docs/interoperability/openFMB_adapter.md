# OpenFMB Adapter — Guía de integración

> **BEP:** BEP-0202 (Protocol Registry)  
> **Estado:** 📋 Diseño — implementación en v3.0.0  
> **Referencia:** https://openfmb.io · LF Energy

---

## ¿Qué es OpenFMB?

**Open Field Message Bus** es el estándar de mensajería para la red eléctrica moderna,
desarrollado en Linux Foundation Energy. Define modelos de datos basados en IEC 61968/61970
(CIM) sobre transporte NATS, MQTT, DDS o Zenoh.

Es el "lenguaje común" entre:
- Medidores inteligentes, inversores, BESS
- DERMS / VPP Orchestrators
- Sistemas SCADA de utilities (EE.UU., Canadá, Australia)

---

## Integración con BESSAI

### Posición en la arquitectura

```
[BESS Hardware]
      │  Modbus TCP (existente)
      ▼
[BESSAI Edge Gateway]
      │
      ├── BESSAI internal telemetry (structlog + Prometheus)
      │
      └── OpenFMB Publisher (BEP-0202)
              │  NATS / MQTT topic: openfmb/BatteryModuleReadingProfile
              ▼
      [OpenFMB Message Bus]
              │
              ├── VPP Orchestrator (OpenADR 3.0)
              ├── DERMS (IEEE 2030.5 ↔ OpenFMB bridge)
              └── SCADA / DMS utilities
```

### Mapeo de datos BESSAI → OpenFMB

| BESSAI tag | OpenFMB Profile | Campo |
|---|---|---|
| `soc_pct` | `BatteryModuleReadingProfile` | `BatteryStatus.stVal` |
| `active_power_kw` | `BatteryModuleReadingProfile` | `W.mag` |
| `voltage_v` | `BatteryModuleReadingProfile` | `Vol.mag` |
| `current_a` | `BatteryModuleReadingProfile` | `A.mag` |
| `temp_c` | `BatteryModuleReadingProfile` | `BatteryStatus.Tmp` |
| Setpoint DRL (`p_pu`) | `BatteryModuleControlProfile` | `DBDI.setMag.f` |

---

## Implementación técnica (draft)

```python
# src/drivers/openfmb_driver.py  (futuro — BEP-0202 Fase 3)

import nats
from openfmb.battermodule import BatteryModuleReadingProfile

class OpenFMBPublisher:
    """Publica telemetría BESSAI al bus OpenFMB via NATS."""
    
    def __init__(self, nats_url: str, site_id: str):
        self._nats_url = nats_url
        self._site_id = site_id
        self._nc: nats.NATS | None = None
    
    async def connect(self) -> None:
        self._nc = await nats.connect(self._nats_url)
    
    async def publish_reading(self, telemetry: dict) -> None:
        profile = BatteryModuleReadingProfile()
        profile.messageInfo.messageUuid.value = self._site_id
        profile.batteryModuleReading.W.mag.f = telemetry["active_power_kw"] * 1000
        # ... mapear resto de tags
        
        subject = f"openfmb.battermodule.BatteryModuleReadingProfile.{self._site_id}"
        await self._nc.publish(subject, profile.SerializeToString())
```

---

## Dependencias

```toml
# pyproject.toml — extras [openfmb]
openfmb = ["nats-py>=2.6", "openfmb>=0.1.0", "protobuf>=4.0"]
```

---

## Tests requeridos

- [ ] `tests/drivers/test_openfmb_publisher.py` — publicación en NATS local
- [ ] `tests/interop/test_openfmb_interop.py` — validación contra OpenFMB test harness

---

## Referencias

- [BEP-0202](../bep/BEP-0202.md) — Protocol Registry
- [BESSAI-SPEC-003](../specs/BESSAI-SPEC-003.md) — Telemetry Schema (fuente de datos)
- LF Energy OpenFMB: https://openfmb.io/documentation
- OpenFMB GitHub: https://github.com/openfmb
