# Open BESS Edge v3

Gateway de borde para sistemas de almacenamiento (BESS): lee telemetría por Modbus TCP, evalúa una envolvente de
seguridad *fail-closed*, calcula la respuesta en frecuencia (droop/FFR) y el control de reactivos (Volt/VAR) y escribe
consignas P/Q verificadas al PCS. Español: este README; parámetros y convenciones en `docs/spec/CONTROL.md`.

> **Estado honesto.** Probado contra emuladores y un servidor Modbus independiente, **no contra hardware real** y sin
> validación regulatoria. Los parámetros de red provienen de la documentación del proyecto y deben ser confirmados por el
> titular contra la NTSyCS vigente antes de operar en el SEN. Ver `PROJECT_STATUS.md`.

## Inicio rápido

```bash
pip install .                       # o: pip install -e ".[dev]"
open-bess-edge simulate             # planta simulada + Modbus TCP + nodo (contingencia 49,65 Hz)
open-bess-edge check-config config/edge_config.yaml
open-bess-edge run --config config/edge_config.yaml
open-bess-edge profile-info open_bess_edge_reference
open-bess-edge verify-audit /var/lib/open-bess-edge/audit.jsonl
```

## Convención física (única en todo el código)
P + = descarga/inyección, − = carga. Q + = capacitivo (sube tensión). La conversión desde la convención de cada
fabricante se hace sólo en el perfil (`sign`, `factor`).

## Ciclo de control
`lectura → envolvente de seguridad → FFR/droop → Volt/VAR → limitador → escritura (+verificación) → latido → auditoría`

Garantías, cada una con test (`tests/test_node.py`, `tests/test_fuzz_invariants.py`):
- Arranque en 0 kW y validación de `startup_valid_cycles` ciclos antes de operar.
- Pérdida de telemetría: retiene la consigna `comm_loss_hold_s` (2 s) y luego fuerza 0, reintentando el 0 hasta confirmarlo.
  Un PCS sin watchdog conserva la última consigna mientras el enlace esté caído: usar el registro de latido.
- Dato requerido ausente, NaN, infinito o físicamente imposible ⇒ salida 0 (nunca un valor "razonable").
- Disparos de seguridad enclavados; se liberan sólo con reset explícito y condición despejada con histéresis.
- Consigna con truncado hacia cero; desborde de registro ⇒ error, nunca *wrap-around*.
- Errores internos no matan el lazo: estado `SAFE_STATE` y auditoría.

## Guardas de seguridad
| Código | Efecto |
|---|---|
| BESS-GUARD-001 / 002 | Sub/sobretensión de celda: disparo enclavado |
| BESS-GUARD-003 | Sobretemperatura de celda: disparo enclavado |
| BESS-GUARD-004 | Aislamiento DC: disparo enclavado |
| BESS-GUARD-005 | Desbalance de celdas: advertencia |
| BESS-GUARD-006 / 009 | Temperatura de celda / ambiente altas: recorte 50 % |
| BESS-GUARD-007 | Temperatura baja: inhibe carga |
| BESS-GUARD-008 | Tensión de string fuera de ventana: disparo enclavado |
| BESS-GUARD-010 | SOC en límite: inhibe descarga o carga |
| BESS-GUARD-020 / 021 | Alarma de frecuencia / tensión de red (sólo si se configuran umbrales) |
| BESS-GUARD-090 | Dato requerido inválido: salida 0, se recupera tras N ciclos válidos |

## Perfiles de dispositivo (`registry/`)
Un perfil sólo permite **control** si declara consigna de P y las señales de seguridad requeridas. Ningún perfil de
fabricante lo hace hoy: son de **monitor** y su nivel es `unverified` (bindings derivados de las descripciones del perfil,
sin prueba contra el equipo real).

| Perfil | Modo | Nivel |
|---|---|---|
| `open_bess_edge_reference` | control | reference (mapa definido por el proyecto) |
| `huawei_sun2000` | monitor | unverified |
| `sma_sunny_tripower` | monitor | unverified |
| `fronius_gen24_byd` | monitor | unverified |
| `solaredge_storedge` | monitor | unverified |
| `victron_multiplus2` | monitor | unverified |

## Verificación
`make check` ejecuta lint, mypy estricto, pruebas, verificador de afirmaciones y seguridad. Cubre pruebas unitarias y de
propiedades, extremo a extremo por TCP real con inyección de fallas, fuzz de invariantes y latencia en tiempo real
(loopback, sin PCS). Compatible con pymodbus ≥ 3.9.2 (3.9.2 a 3.15.0 probadas; 3.8.x acepta respuestas con transaction
ID incorrecto y se excluye).

## Módulos experimentales (`open_bess_edge.experimental`, fuera de la ruta de control)
CAN/DBC (validado contra `cantools`), IEC 60870-5-104 (interopera en STARTDT e interrogación con `c104`; sin
temporizadores t1/t2/t3) y un códec tipo GOOSE sobre UDP de loopback (no es GOOSE de capa 2). No se afirma latencia.
