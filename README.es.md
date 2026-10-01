# Open BESS Edge v3 (Español)

[English Version](README.md) | **Español**

Gateway de borde para sistemas de almacenamiento de energía en baterías (BESS): adquiere telemetría mediante Modbus TCP, evalúa una envolvente de seguridad *fail-closed* en tiempo real, calcula la respuesta rápida en frecuencia (FFR / droop) y soporte de reactivos (Volt/VAR), y escribe consignas verificadas de P/Q al convertidor de potencia (PCS). Parámetros y convenciones técnicas: `docs/spec/CONTROL.md`.

> **Estado técnico honesto:** Validado exhaustivamente frente a emuladores industriales y un servidor Modbus independiente con inyección de fallas por TCP real. Pendiente de homologación física en banco con inversores comerciales reales (criterio formal: prueba continua de 72 horas con PCS comercial cumpliendo FFR <500 ms y cero disparos espurios). Ver `PROJECT_STATUS.md`.

---

## Inicio Rápido

```bash
pip install .                       # o modo desarrollo: pip install -e ".[dev]"
open-bess-edge simulate             # simulación completa: planta + Modbus TCP + nodo (contingencia 49,65 Hz)
open-bess-edge check-config config/edge_config.yaml
open-bess-edge run --config config/edge_config.yaml
open-bess-edge profile-info open_bess_edge_reference
open-bess-edge verify-audit /var/lib/open-bess-edge/audit.jsonl
```

---

## Convención Física Universal
* **P (+):** Descarga / inyección a la red.
* **P (−):** Carga / consumo desde la red.
* **Q (+):** Capacitivo (inyecta reactivos, eleva tensión).
* **Q (−):** Inductivo (absorbe reactivos, reduce tensión).

La conversión desde la convención de cada fabricante se realiza estrictamente en el perfil de registro (`sign`, `factor`).

---

## Ciclo de Control Determinista
`Lectura Modbus → Envolvente de Seguridad → FFR/Droop → Volt/VAR → Limitador P/Q → Escritura (+Verificación) → Latido (Heartbeat) → Auditoría Criptográfica`

Garantías operativas respaldadas por 278 tests automatizados (`tests/test_node.py`, `tests/test_fuzz_invariants.py`):
- **Arranque en 0 kW** con validación obligatoria de `startup_valid_cycles` antes de operar.
- **Pérdida de telemetría:** retiene consigna durante `comm_loss_hold_s` (2 s); luego fuerza de inmediato a 0 kW hasta confirmación.
- **Datos inválidos o ausentes:** si la telemetría es nula, NaN, infinita o implausible, la salida se fuerza a 0 (nunca un valor aproximado).
- **Disparos enclavados (Latched Trips):** solo se despejan mediante comando de reset explícito con condición normalizada bajo histéresis.
- **Consignas truncadas hacia cero:** ante desbordes de registro o error numérico, se fuerza estado seguro sin wrap-around.
- **Resiliencia ante fallos internos:** errores inesperados no detienen el lazo principal; conducen a `SAFE_STATE` con registro en auditoría.

---

## Guardas de Seguridad de la Envolvente

| Código | Condición Monitoreada | Efecto Inmediato |
|---|---|---|
| BESS-GUARD-001 | Subtensión de celda crítica | Disparo enclavado a 0 kW |
| BESS-GUARD-002 | Sobretensión de celda crítica | Disparo enclavado a 0 kW |
| BESS-GUARD-003 | Sobretemperatura de celda | Disparo enclavado a 0 kW |
| BESS-GUARD-004 | Falla de aislamiento DC | Disparo enclavado a 0 kW |
| BESS-GUARD-005 | Desbalance de tensión de celdas | Advertencia (Warning) |
| BESS-GUARD-006 | Temperatura alta de celdas | Recorte térmico (Derating 50%) |
| BESS-GUARD-007 | Temperatura baja de celdas | Inhibición de carga (0 kW si P < 0) |
| BESS-GUARD-008 | Tensión de string fuera de rango | Disparo enclavado a 0 kW |
| BESS-GUARD-009 | Alta temperatura ambiente | Recorte preventivo (Derating 50%) |
| BESS-GUARD-010 | Límites operativos de SOC alcanzados | Inhibición direccional de carga o descarga |
| BESS-GUARD-020 | Alarma de frecuencia de red fuera de ventana | Alarma / disparo condicional |
| BESS-GUARD-021 | Alarma de tensión de red fuera de ventana | Alarma / disparo condicional |
| BESS-GUARD-090 | Telemetría requerida inválida o estancada | Salida forzada a 0 kW |
| BESS-GUARD-091 | Medidor de red (PCC) sin datos vigentes | Salida forzada a 0 kW |

---

## Perfiles de Dispositivos (`registry/`)

Un perfil de dispositivo únicamente autoriza el modo **control** si declara explícitamente consignas activas y todas las señales de seguridad requeridas. Los perfiles comerciales se configuran en modo **monitor** con nivel `unverified` hasta su contraste en banco real.

| Perfil | Modo | Nivel de Validación |
|---|---|---|
| `open_bess_edge_reference` | control | reference (mapa industrial canónico del proyecto) |
| `huawei_sun2000` | monitor | unverified (mapeo derivado de especificación técnica) |
| `sma_sunny_tripower` | monitor | unverified (mapeo derivado de especificación técnica) |
| `fronius_gen24_byd` | monitor | unverified (mapeo derivado de especificación técnica) |
| `solaredge_storedge` | monitor | unverified (mapeo derivado de especificación técnica) |
| `victron_multiplus2` | monitor | unverified (mapeo derivado de especificación técnica) |
| `open_bess_edge_meter_reference` | monitor | reference (medidor de frontera PCC) |

---

## Contexto de Instalación (BTM Peak Shaving)

El subsistema `installation` gestiona restricciones de planta (`max_grid_import_kw`, `max_grid_export_kw`, `soc_reserve_pct`) monitoreadas en el punto de acoplamiento común (PCC). Si el medidor falla o pierde vigencia, el gateway fuerza la salida a 0 kW (BESS-GUARD-091). Configuración de referencia: `config/installation_btm_peak_shaving.yaml`.

---

## Módulos Experimentales (`open_bess_edge.experimental`)

* **CAN Bus / DBC:** Decodificación de tramas automotrices/estacionarias (validado con `cantools`).
* **IEC 60870-5-104:** Cliente/servidor telecontrol con soporte de secuencias STARTDT e interrogación general.
* **GOOSE Codec:** Serialización ligera sobre transporte UDP en bucle local.

---

## Licencia y Gobernanza
Distribuido bajo licencia de código abierto **Apache 2.0**.
