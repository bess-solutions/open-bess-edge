# OCPP 2.0.1 — Ruta de Compatibilidad V2G

> **BEP:** BEP-0202 (Protocol Registry)  
> **Referencia:** https://www.openchargealliance.org/protocols/ocpp-201/  
> **Estado:** 📋 Propuesto — implementación en v3.1.0

---

## Contexto

**OCPP 2.0.1** (Open Charge Point Protocol) es el estándar de comunicación entre
estaciones de carga de vehículos eléctricos y sistemas de gestión (CSMS).

La relevancia para BESSAI surge de **Vehicle-to-Grid (V2G)**: cuando un vehículo eléctrico
actúa como fuente de almacenamiento (bidireccional), BESSAI debe poder:
1. Leer el estado del VE (SOC, capacidad disponible) vía OCPP
2. Comandar carga/descarga del VE como parte de la estrategia de arbitraje DRL

---

## Posición en la arquitectura

```
[Vehículo Eléctrico]
       │  CCS / CHAdeMO
       ▼
[EVSE / Charging Station]
       │  OCPP 2.0.1 (WebSocket)
       ▼
[BESSAI OCPP Adapter]  ←  nuevo módulo (BEP-0202 Fase 5)
       │
       ├── Lee SOC del VE → obs vector del DRL Agent
       │   (reemplaza o complementa temp_bateria_c en BESSArbitrageEnv)
       └── Envía setpoint de carga/descarga ← DRL policy output
```

---

## Mensajes OCPP relevantes

| Mensaje OCPP | Dirección | Uso en BESSAI |
|---|---|---|
| `StatusNotification` | EVSE → BESSAI | Estado del punto de carga |
| `MeterValues` | EVSE → BESSAI | Telemetría V (SOC, potencia, energía) |
| `RequestStartTransaction` | BESSAI → EVSE | Iniciar sesión de carga |
| `RequestStopTransaction` | BESSAI → EVSE | Detener sesión |
| `SetChargingProfile` | BESSAI → EVSE | Perfil de carga (límite de potencia) |
| `GetCompositeSchedule` | BESSAI → EVSE | Consulta planificación |

---

## Mapeo OCPP → BESSAI tags

| OCPP MeterValue | BESSAI tag | Escala |
|---|---|---|
| `Energy.Active.Import.Register` (Wh) | `energy_charged_kwh` | ÷1000 |
| `Power.Active.Import` (W) | `active_power_kw` | ÷1000 |
| `SoC` (%) | `soc_pct` | directo |
| `Voltage` (V) | `voltage_v` | directo |
| `Current.Import` (A) | `current_a` | directo |

---

## Consideraciones de seguridad

- OCPP 2.0.1 requiere TLS 1.2+ mandatorio → compatible con política BESSAI (IEC 62443)
- Autenticación básica por EVSE ID + contraseña → integrar con `totp_auth.py`
- Logging de todas las transacciones → structlog + Prometheus counters

---

## Dependencias

```toml
# pyproject.toml — extras [v2g]
v2g = ["ocpp>=2.0.0", "websockets>=12.0"]
```

---

## Tests requeridos

- [ ] `tests/drivers/test_ocpp_adapter.py` — mock EVSE, mensajes básicos
- [ ] `tests/interop/test_v2g_interop.py` — V2G roundtrip con OCPP 2.0.1 simulator

---

## Referencias

- [BEP-0202](../bep/BEP-0202.md)
- [BESSAI-SPEC-001](../specs/BESSAI-SPEC-001.md) — BESSDriver interface (OCPP adapter debe cumplirla)
- Open Charge Alliance: https://www.openchargealliance.org/
- Python ocpp library: https://github.com/mobilityhouse/ocpp
