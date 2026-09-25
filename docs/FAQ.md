# Open BESS Edge — Preguntas Frecuentes (FAQ)

> Respuestas directas y técnicas sobre la arquitectura, alcance y despliegue de Open BESS Edge v3.

---

## Integración y Soporte de Hardware

### ¿Con qué inversores y sistemas BMS es compatible?

Open BESS Edge utiliza perfiles JSON estandarizados en la carpeta [`registry/`](../registry/) para mapear registros Modbus TCP a señales canónicas. 

Los perfiles incluidos son:
- **`open_bess_edge_reference`**: Perfil canónico con capacidad de control activo y reactivo (P/Q) y verificación de latido (*heartbeat*).
- **Perfiles vendor en modo monitor**: `huawei_sun2000`, `sma_sunny_tripower`, `fronius_gen24_byd`, `solaredge_storedge`, `victron_multiplus2`.

> **Nota de honestidad técnica:** Los perfiles de fabricantes comerciales están definidos en modo *monitor-only* para lectura de telemetría hasta que completen el protocolo formal de homologación física en banco HIL (72 horas sin fallas).

---

### ¿Cuál es la latencia de respuesta ante contingencias de red?

El ciclo de ejecución principal del gateway corre a **100 ms** (configurable mediante `runtime.cycle_ms`).

La respuesta a escalones de frecuencia para control FFR cumple con el presupuesto normativo de la NTSyCS (**< 500 ms** desde la detección del evento de frecuencia hasta la emisión del comando de setpoint al PCS sobre Modbus TCP).

---

### ¿Requiere conexión a internet o servicios en la nube para operar?

**No.** Open BESS Edge está diseñado para operar de manera **100% autónoma y determinista en el borde (OT)**:
- Toda la lógica de protección (`SafetyEnvelope`, `BESS-GUARD-001..091`) se ejecuta localmente.
- Si se pierde la comunicación con el medidor de red o con el PCS, el nodo entra de inmediato en estado seguro (`SAFE_STATE`) fijando la potencia en cero.
- No existen dependencias de nube ni llamadas a APIs externas en el lazo de control crítico.

---

## Operación y Arquitectura

### ¿Incluye modelos de Machine Learning (LLMs o DRL) en el gateway?

**No.** Open BESS Edge v3 se enfoca de manera estricta en el guardarraíl determinista de protección y control primario de frecuencia.
- Los modelos de optimización de mercado, arbitraje o pronóstico pertenecen a sistemas superiores (EMS / Cloud) y pueden interactuar con el gateway mediante consignas de despacho limitadas por tiempo (TTL) y acotadas por la envolvente de seguridad física.
- El gateway jamás delega la seguridad física ni el disparo a algoritmos de caja negra.

---

### ¿Cómo se prueba el sistema sin hardware físico?

El repositorio incluye un simulador determinista (`SimEnvironment` y `Harness`) acoplado por loopback TCP real. Esto permite ejecutar la suite de 278 pruebas canónicas simulando perturbaciones de frecuencia, transitorios térmicos, fallas de comunicación y desbalances de celdas sin requerir mocks en el driver Modbus.

---

## Licencia y Uso

### ¿Bajo qué licencia se distribuye el código?

Open BESS Edge se publica bajo la licencia de código abierto **Apache 2.0**. Puede ser utilizado, auditado e integrado libremente tanto en entornos de prueba como en instalaciones industriales.
