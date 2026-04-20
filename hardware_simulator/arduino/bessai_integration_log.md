# Registro de Integración: Simulador BESSAI (Hardware-in-the-Loop)

_Este documento registra todas las decisiones arquitectónicas, configuraciones y parches aplicados para habilitar el simulador físico de BESSAI en Windows usando una placa SainSmart UNO (Arduino)._

## 1. Arquitectura de Hardware y Software
Decidimos implementar una topología de "Puente" debido a las limitaciones físicas del Arduino UNO:
- **Dispositivo BESS Físico:** Clon SainSmart UNO con un Firmware C++ (`bessai_modbus_slave.ino`) que levanta un servidor Modbus RTU (Serial).
- **Traductor de Nivel (Edge):** Un script en Python (`rtu_to_tcp_bridge.py`) alojado en la misma carpeta que actúa como servidor pasarela bidireccional. Escucha peticiones TCP en `127.0.0.1:5020` y las serializa por el puerto `COM3` o equivalente.

## 2. Preparación del Entorno BESSAI
BESSAI Edge espera inherentemente un despliegue Docker y perfiles industriales. Se aplicaron adaptaciones para que funcione localmente (Al Desnudo/Bare Metal):
- **Adición de Perfil de Memoria:**
  - Se configuró `registry/simulator.json` para que el cerebro BESSAI deje de esperar métricas de baterías Huawei LUNA2000 y asuma un mapeo base de 4 registros: `SOC`, `Temperatura`, `Potencia` y `Estado`.
  - Se respetó estrictamente el esquema JSON v2 (`$schema`: `"https://bessai.io/schemas/device-profile/v2.json"`) implementando los bloques `"device"`, `"connection"` (TCP) y `"registers"`.
- **Modificación del GPS (.env):**
  - Se ajustó el archivo de variables maestras ubicado en `config/.env`:
    - `INVERTER_IP`: `127.0.0.1` 
    - `INVERTER_PORT`: `5020`
    - `DRIVER_PROFILE_PATH`: `registry/simulator.json`
    - Variables ficticias (Dummy) en GCP Publicador para eludir validaciones de Start-Up.
- **Preparación de Dependencias Local (.venv):**
  - En vista de que no se contaba con Docker Desktop activo en la estación, instalamos todas las suites dependientes (`Gymnasium` para IA, `SQLAlchemy`, etc.) forzando un despliegue mediante el entorno virtual de Python `.venv\Scripts\python.exe` y sus dependientes locales en el archivo `requirements.txt`.

## 3. Parches Core (Compatibilidad Windows)
Dado que BESSAI está ideado de primera línea para sistemas Linux/Debian usados en instrumentación real (armarios eléctricos), el motor arrojó incompatibilidad en su plancha C-Base con señales POSIX.
- **Archivo Modificado:** `src/core/main.py`
- **Operación:** Se blindó la función de cierre elegante protegiéndola bajo un bloque interactivo `try/except NotImplementedError` en la línea ~225. Esto obliga a BESSAI a saltar la lectura de la señal de muerte `SIGTERM` para que en Sistemas Windows pueda proceder el arranque del Loop Infinito.
