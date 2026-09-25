# Estado del proyecto — Open BESS Edge v3.1.0

<!-- tests:285 -->
Pruebas: 278 canónicas del núcleo de borde BESS (100% passing en cualquier entorno) + 7 opcionales de módulos experimentales (CAN/DBC con cantools, IEC 104 con c104; total 285). Verificado por `scripts/verify_claims.py`.

| Componente | Madurez | Evidencia |
|---|---|---|
| Códec, perfiles, driver Modbus | probado con emulador independiente | tests unitarios, propiedades, E2E, matriz pymodbus 3.9.2–3.15.0 |
| Envolvente de seguridad | probada (fail-closed) | unitarios, propiedades, fuzz |
| FFR/droop, Volt/VAR | probados numéricamente y en lazo cerrado | unitarios, propiedades, E2E |
| Contexto de instalación, medidor y API | probado E2E y en simulación | 55 tests nuevos, BTM peak shaving, BESS-GUARD-091, API token |
| Nodo (fail-safe, auditoría, salud) | probado E2E | `tests/test_node.py`, fuzz, latencia loopback |
| CAN/DBC, IEC 104, GOOSE | experimental | ver README |
| Hardware real, NTSyCS, ciberseguridad OT | **pendiente de homologación** | Criterio formal HIL/banco físico: protocolo de 72h continuas con inversor comercial (Huawei SUN2000 / SMA Tripower) cumpliendo FFR <500ms y cero disparos espurios en envolvente |

Estado de empaquetado: Dockerfile v3 mínimo verificado y publicado por el pipeline de CI/CD (GitHub Actions).
Documentación: `README.md`, `SECURITY.md`, `CITATION.cff` y especificaciones en `docs/spec/` alineadas formalmente con v3.1.0.
