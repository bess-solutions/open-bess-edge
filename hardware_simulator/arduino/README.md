# Simulador de Hardware BESSAI (Arduino / SainSmart UNO)

Este módulo te permite construir un entorno de pruebas **Hardware in the Loop (HIL)** para interactuar físicamente con Open BESS Edge utilizando electrónica de consumo básica.

En lugar de requerir que te conectes a un inversor BESS real (como un Huawei SUN2000 o Victron), este simulador levanta un inversor virtual dentro de un microcontrolador Arduino.

## ¿Cómo funciona la arquitectura central?

BESSAI Edge por defecto requiere de Modbus TCP (comunicación de red). Ya que la placa SainSmart UNO (basada en ATmega328P) carece de placa de red, la hemos configurado para trabajar usando **USB (Conexión Serial)** mediante el protocolo **Modbus RTU**.

1. **Hardware (El Inversor)**: El `SainSmart UNO` se conecta por cable USB (`/dev/ttyUSB0` o `COM3`) a la computadora. Este expone un esclavo Modbus RTU que registra valores analógicos (ej. voltaje, SOC) y controla salidas digitales (relés).
2. **Software Bridge (El Traductor)**: Incluimos un pequeño adaptador en local (escrito en Python) que intercepta de forma transparente el tráfico del puerto serial del Arduino y expone internamente un puerto `TCP 5020`. 
3. **BESSAI (El Cerebro)**: En tu archivo local `.env`, apuntas `INVERTER_IP=127.0.0.1` y `INVERTER_PORT=5020`. Para BESSAI, esto es completamente invisible: cree que está operando en la IP de un inversor Huawei real.

## Mapa de Archivos

- `bessai_modbus_slave/bessai_modbus_slave.ino` → Este es el código C++ (Sketch) que se compila y carga en la memoria del Arduino. Define todos los registros que BESSAI le pedirá.
- `rtu_to_tcp_bridge.py` → Script ejecutable con Python y la librería `pymodbus`. Reenviará los bits RTU USB a BESSAI por TCP.
- `wiring_diagram.md` → Especificaciones eléctricas de pines que deberás seguir con tu Breadboard (Placa de Pruebas).
- `integration_guide.md` → Guía rápida para lanzar todo con los comandos exactos.

## Requerimientos

- Placa base: SainSmart UNO o Arduino UNO R3 (o compatibles).
- Cable Serial USB tipo A/B estándar (Cable de Impresora) o Mini-USB.
- Entorno: Arduino IDE v2 instalado para compilar y flashear.
- Python 3.10+ para correr el Bridge.
