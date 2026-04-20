import serial
import time
import struct

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

print("Abriendo COM3...")
try:
    ser = serial.Serial('COM3', 9600, timeout=2.0)
    print("DTR activado. Esperando 3s para boot Arduino...")
    time.sleep(3)
    
    # Construir trama Modbus RTU: [Slave 1] [Function 3] [Start Addr 00 00] [Registers 00 06] [CRC L] [CRC H]
    payload = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x06])
    full_frame = payload + crc16(payload)
    
    print(f"TX: {full_frame.hex(' ')}")
    ser.write(full_frame)
    ser.flush()
    
    rx = ser.read(256)
    if not rx:
         print("RX: [SILENCIO ABSOLUTO DEL ARDUINO]")
    else:
         print(f"RX: {rx.hex(' ')}")
         
    ser.close()
except Exception as e:
    print(f"Error: {e}")
