# Open BESS Edge — Arquitectura del Simulador Determinado

> **Estado:** Activo (v3.x)  
> **Ubicación en código:** `src/open_bess_edge/sim/`  
> **Propósito:** Entorno de verificación física determinista acoplado por loopback TCP.

---

## 1. Filosofía de Simulación v3

A diferencia de entornos que emplean simulaciones desconectadas o "mocks" en memoria, Open BESS Edge implementa una arquitectura donde **el nodo de control corre exactamente el mismo código que en producción**, conectándose a través de **sockets TCP reales**:

```
┌────────────────────────────────┐            ┌────────────────────────────────┐
│      EdgeNode (Producción)     │            │    SimEnvironment (In-Tree)    │
│  - Driver Modbus TCP           │──(TCP)────▶│  - SimModbusServer (Port 0)    │
│  - SafetyEnvelope              │            │  - RegisterBank (Holding/Input)│
│  - Control FFR / Q(V)          │◀──(TCP)────│  - PlantModel (Física BESS)    │
└────────────────────────────────┘            └────────────────────────────────┘
```

---

## 2. Componentes del Módulo `sim/`

| Componente | Archivo | Responsabilidad |
|---|---|---|
| **`PlantModel`** | `sim/plant.py` | Modela la dinámica física de la batería: estado de carga (SOC), tensión de celdas según curvas OCV, temperatura de celda/ambiente con balance térmico, y respuesta de frecuencia/tensión de red. |
| **`SimBridge`** | `sim/bridge.py` | Vincula el modelo de planta (`PlantModel`) con el banco de registros Modbus (`RegisterBank`), convirtiendo variables de ingeniería a palabras binarias según el perfil activo. |
| **`SimModbusServer`** | `sim/modbus_server.py` | Servidor Modbus TCP asíncrono multi-unidad que escucha en loopback (`127.0.0.1`), respondiendo solicitudes de lectura/escritura de registros reales. |
| **`SimEnvironment`** | `sim/runner.py` | Orquestador de pruebas que integra planta, banco y servidor, ofreciendo método `.step(dt)` determinista o ejecución a tiempo real. |
| **`Harness`** | `tests/harness.py` | Arnés de pruebas automatizadas con reloj manual (`ManualClock`) que avanza de forma determinista el nodo y la física sin carreras temporales. |

---

## 3. Escenarios de Prueba Cubiertos por el Simulador

1. **Contingencias de Frecuencia (FFR)**:
   - Escalones de frecuencia (ej. caída a 49.5 Hz) verificando aporte proporcional de potencia en <500 ms y normalización tras recuperación.
2. **Disparos Térmicos y de Celda**:
   - Sobretensión celular (>3.65 V) o temperatura crítica (>50 °C) disparando `BESS-GUARD-001` / `003` con bloqueo de consigna a cero.
3. **Pérdida de Comunicación**:
   - Detención abrupta del servidor TCP o inyección de excepciones Modbus simulando corte de fibra o caída de inversor, validando transición segura tras 2 segundos.
4. **Fuzzing de Invariantes**:
   - Inyección de miles de perturbaciones aleatorias continuas (7,500 ciclos) verificando que jamás se viole la envolvente de seguridad.
