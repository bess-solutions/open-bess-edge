# Guía de Integración con BESSAI Edge

Ahora que tienes tu placa SainSmart UNO cableada y con el código Modbus cargado en memoria, y entiendes cómo funciona el componente puente (Bridge), estos son los últimos pasos para conectar el Arduino al Cerebro AI de BESS.

## Paso 1: Instala dependencias del Bridge

En una terminal en la computadora donde estés ejecutando BESSAI, entra a tu entorno virtual de Python (`.venv`) e instala `pymodbus`. (Si BESSAI ya está instalado, es probable que ya lo tengas).

```bash
pip install pymodbus pyserial
```

## Paso 2: Ejecutar el Proxy (Modbus RTU -> TCP)

Deberás identificar qué puerto le asignó tu computadora a la placa SainSmart (ej. `COM3` en Windows o `/dev/ttyUSB0` en macOS/Linux). 

Ejecuta el puente indicando tu puerto. Si dejas el puerto TCP por defecto, se exportará en el puerto local `5020`.

```bash
# Cambia COM3 por el puerto que corresponda a tu computadora
python rtu_to_tcp_bridge.py --port COM3 --tcp_port 5020
```

Verás una salida indicando que el puente se conectó:
`✅ Conectado al Arduino en COM3 a 9600 baudios`
`🚀 Iniciando Puente TCP en 127.0.0.1:5020 -> COM3`

> ⚠️ Déjalo corriendo en un segundo plano.

## Paso 3: Configurar Open BESS Edge

Ve a la ruta raíz de tu carpeta BESSAI y abre el archivo `config/.env` (o créalo a partir del `.env.example`).
Cambia estos valores para que BESSAI se comunique con el Bridge en vez de la subestación de un cliente real:

```dotenv
# .env de prueba simulador 

INVERTER_IP=127.0.0.1
INVERTER_PORT=5020
MODBUS_UNIT_ID=1

# DEVICE_PROFILE Puedes usar uno personalizado, o crear "sainsmart_demo" en la carpeta "registry/"
DEVICE_PROFILE=simulator 
```

## Paso 4: Encender BESSAI

Abre otra terminal en la raíz del proyecto y enciende BESSAI de la manera tradicional:

```bash
# Modo standalone/docker dependiendo de tu ambiente
docker compose up bessai-gateway
# O vía script
python src/core/main.py
```

BESSAI hará un "handshake" con la `127.0.0.1:5020`, el puente de Python tomará esa petición y la traducirá a impulsos eléctricos por el cable USB, y el SainSmart responderá con el valor numérico de cuánta resistencia estás aplicando con los potenciómetros físicos.

¡Felicitaciones! Acabas de montar un ecosistema BESS a escala sub-industrial en tu propia mesa.
