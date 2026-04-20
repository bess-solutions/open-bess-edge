# Instalación de Software de Configuración y Controladores

Para que la computadora reconozca la placa clon **SainSmart UNO** y para poder compilar y enviar el código, necesitas tres herramientas clave de software. A continuación te indico cuáles son y cómo instalarlas:

## 1. Controlador (Driver) CH340 para SainSmart UNO
Las placas Arduino originales usan un chip distinto, pero la mayoría de los clones (incluyendo SainSmart) utilizan el chip adaptador USB-Serial **CH340/CH341**. Si conectas el Arduino a la placa y Windows no lo reconoce o aparece en el administrador de dispositivos con un signo de exclamación amarillo, **te falta este driver**.

- **Descarga oficial:** [Sitio de WCH (Fabricante del chip)](https://www.wch-ic.com/downloads/CH341SER_EXE.html) o busca en Google `CH340 Driver Windows`.
- **Instalación:** Ejecuta el instalador descargado (`CH341SER.EXE`) y dale clic a **Install**. Luego, desconecta y vuelve a conectar tu SainSmart UNO. Debería aparecer como `USB-SERIAL CH340 (COM X)` en tu Administrador de Dispositivos.

## 2. Entorno de Desarrollo (Arduino IDE)
Es el software oficial usado para abrir el archivo `bessai_modbus_slave.ino` e "inyectar" ese código a la placa física.

- **Descarga:** [Descargar Arduino IDE](https://www.arduino.cc/en/software)
- **Configuración rápida:** 
  1. Al abrirlo, ve a `Herramientas -> Placa` y selecciona **Arduino Uno**.
  2. Ve a `Herramientas -> Puerto` y selecciona el puerto `COM` que apareció tras instalar el driver CH340.
  3. Ve a `Sketch -> Include Library -> Manage Libraries...` y busca "ModbusRTUSlave" (de CMB27) e instálala.
  4. Presiona el botón de **Subir** (flecha derecha) para flashear la placa.

## 3. Dependencias de Python (`requirements.txt`)
Para levantar el script que hace de puente entre el Arduino y BESSAI (`rtu_to_tcp_bridge.py`), la computadora necesita instalar el software de comunicación pyModbus. Para automatizarlo, diseñamos un archivo `requirements.txt`.

Abre una consola (Terminal o CMD) dentro de esta carpeta y ejecuta:

```bash
pip install -r requirements.txt
```

## (Opcional) ModbusPoll / QModBus
Si quieres probar manualmente que tu Arduino está leyendo tus potenciómetros antes de conectarlo a todo el ecosistema de IA de BESSAI:
- Puedes instalar QModBus (Open Source) o ModbusPoll.
- Conéctate en modo "Serial Port / RTU", pon el puerto COM de tu Arduino, velocidad `9600` e ID de esclavo `1`.
- Al solicitar los "Holding Registers", deberías de ver los valores de tus potenciómetros y relés cambiando cuando los interactúas físicamente.
