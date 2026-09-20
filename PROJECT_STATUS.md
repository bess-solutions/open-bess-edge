# Estado del proyecto — Open BESS Edge v3.0.0

<!-- tests:230 -->
Pruebas: ver marcador (verificado por `scripts/verify_claims.py`).

| Componente | Madurez | Evidencia |
|---|---|---|
| Códec, perfiles, driver Modbus | probado con emulador independiente | tests unitarios, propiedades, E2E, matriz pymodbus 3.9.2–3.15.0 |
| Envolvente de seguridad | probada (fail-closed) | unitarios, propiedades, fuzz |
| FFR/droop, Volt/VAR | probados numéricamente y en lazo cerrado | unitarios, propiedades, E2E |
| Nodo (fail-safe, auditoría, salud) | probado E2E | `tests/test_node.py`, fuzz, latencia loopback |
| CAN/DBC, IEC 104, GOOSE | experimental | ver README |
| Hardware real, NTSyCS, ciberseguridad OT | **no validado** | — |

Pendiente conocido: `infrastructure/docker/Dockerfile*`, `README.en.md`, `SECURITY.md` y varios `docs/` aún describen v2;
la imagen Docker nueva no se construyó en el entorno de desarrollo.
