# Contexto de instalación (v3.1)

El edge no conoce leyes ni tarifas: aplica **restricciones operativas genéricas** y audita su procedencia.

## Ley de control (BTM peak shaving) — sin integrador
`L = p_grid + P_bess` · `P_shave = max(0, L − max_import)` · `dis_max = min(cap, max(0, L + max_export))` (0 si SOC ≤ reserva) ·
`chg_max = min(cap, max(0, max_import − L))`. Prioridad: BESS-GUARD ≻ ventana de instalación ≻ FFR (sólo si el rol lo permite)
≻ peak shaving local ≻ programa del EMS. Con demanda sobre el umbral: `P = max(P_shave, P_base)`.

## Decisiones que conviene confirmar
1. `max(P_shave, P_base)` (no reemplaza el programa del EMS si éste ya descarga más de lo necesario).
2. BESS-GUARD-091 **no se enclava**: sale de falta tras `recovery_valid_cycles` (3) ciclos válidos (se pidió "enclavar" y "3 ciclos"; son excluyentes).
3. Dentro de `p_grid_timeout_s` (2 s) se usa el último valor del medidor: la estimación de L puede estar hasta 2 s desfasada.
4. La consigna se trunca hacia cero (1 kW de cuantización en el mapa de referencia): la importación puede quedar 1 kW sobre el umbral.
5. La API HTTP recorta a capacidad al aceptar; el resultado por ciclo (límites de seguridad e instalación) queda en los eventos SETPOINT.

## Límites conocidos (no resueltos)
- Sin TLS: la API sólo escucha en loopback (un proxy TLS debe terminar fuera del nodo).
- `authorized_roles` es declarativo (un único token = un rol). Sin rotación de tokens.
- El perfil `open_bess_edge_meter_reference` es un mapa del proyecto; ningún medidor comercial está mapeado ni verificado.
- Sin sincronización de reloj entre medidor y PCS: el retardo entre muestras no se compensa.
- Falta un fuzz de invariantes específico del contexto (la suite actual cubre propiedades de la ventana y escenarios E2E).
- `metadata.status` no se contrasta con ninguna fuente normativa: es una etiqueta del compilador de políticas.
