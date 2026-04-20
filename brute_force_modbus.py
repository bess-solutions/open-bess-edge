import serial
import time
import struct
from itertools import product

def crc16(data: bytes):
    crc = 0xFFFF
    for pos in data:
        crc ^= pos 
        for i in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)

baudrates = [9600, 19200, 38400, 115200]
parities = ['N', 'E', 'O']
slave_ids = [1, 2, 3, 10, 255]

port_name = 'COM3'
print("Iniciando escaneo exhaustivo de Modbus RTU en", port_name)

found = False
for baud, parity, slave in product(baudrates, parities, slave_ids):
    print(f"Probando Baud={baud}, Parity={parity}, Slave={slave}...", end="\r")
    try:
        ser = serial.Serial(port=port_name, baudrate=baud, parity=parity, timeout=0.15)
        # Solo DTR en la primera conexion puede ser un problema, pero abriendo y cerrando lo reseteara.
        # Mejor desactivar dtr explicitamente si no queremos que resetee cada vez
        ser.dtr = False
        time.sleep(0.05)
        
        payload = bytes([slave, 0x03, 0x00, 0x00, 0x00, 0x06])
        frame = payload + crc16(payload)
        
        ser.write(frame)
        ser.flush()
        
        rx = ser.read(128)
        if len(rx) > 0:
            print(f"\n[!!! EXITO !!!] Arduino respondio en: Baud={baud}, Parity={parity}, Slave={slave}")
            print(f"RX Hex: {rx.hex(' ')}")
            found = True
            ser.close()
            break
        ser.close()
    except Exception as e:
        pass

if not found:
    print("\n[RESULTADO] Ninguna combinacion obtuvo respuesta. El Arduino NO esta corriendo el esclavo Modbus o esta bloqueado.")
