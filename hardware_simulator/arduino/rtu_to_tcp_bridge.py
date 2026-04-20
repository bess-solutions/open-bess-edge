import asyncio
import logging
import argparse
import time
import struct
import threading
from pymodbus.client import ModbusSerialClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bessai_bridge")

arduino_vars = [0]*10
lock = threading.Lock()

def serial_worker(serial_port):
    log.info(f"[Thread] Abriendo {serial_port} a 9600 baudios...")
    client = ModbusSerialClient(
        port=serial_port, 
        baudrate=9600, 
        bytesize=8, 
        parity='N', 
        stopbits=1, 
        timeout=1.5
    )
    if not client.connect():
        log.error(f"[Thread] ❌ No se pudo abrir {serial_port}.")
        return
        
    log.info("[Thread] ✅ Puerto abierto. Esperando 3s...")
    time.sleep(3.0)
    
    while True:
        try:
            response = client.read_holding_registers(address=0, count=6, device_id=1)
            if not getattr(response, 'isError', lambda: True)():
                log.info(f"Arduino -> {response.registers}")
                with lock:
                    for i, val in enumerate(response.registers):
                        arduino_vars[i] = val
            else:
                log.warning(f"[Thread] Arduino rebotó la trama: {response}")
        except Exception as e:
            pass
        time.sleep(1.0) 

async def handle_modbus_client(reader, writer):
    """
    Mini Modbus TCP Server robusto que sirva la variable arduino_vars
    sin problemas de cache de PyModbus 3.x
    """
    try:
        while True:
            header = await reader.readexactly(8)
            if not header:
                break
                
            tx_id, proto, length, unit, func = struct.unpack(">HHHBB", header)
            
            # Read remainder of request
            payload = await reader.readexactly(length - 2)
            
            if func == 0x03:
                start_addr, count = struct.unpack(">HH", payload)
                with lock:
                    data = [arduino_vars[i] for i in range(start_addr, start_addr + count)]
                
                # Construir respuesta
                byte_count = count * 2
                resp_payload = struct.pack(">B", byte_count)
                for val in data:
                    resp_payload += struct.pack(">H", val)
                    
                resp_len = 2 + len(resp_payload)
                resp_header = struct.pack(">HHHBB", tx_id, proto, resp_len, unit, func)
                writer.write(resp_header + resp_payload)
                await writer.drain()
            else:
                # Modbus Exception: Illegal Function
                writer.write(struct.pack(">HHHBBB", tx_id, proto, 3, unit, func | 0x80, 0x01))
                await writer.drain()
                
    except asyncio.IncompleteReadError:
        pass
    except Exception as e:
        log.error(f"TCP handler error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

async def run_server(serial_port, tcp_port):
    t = threading.Thread(target=serial_worker, args=(serial_port,), daemon=True)
    t.start()

    server = await asyncio.start_server(handle_modbus_client, '127.0.0.1', tcp_port)
    log.info(f"🚀 Iniciando Mini Servidor Puente Modbus TCP en 127.0.0.1:{tcp_port}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=str, default='COM3')
    parser.add_argument('--tcp_port', type=int, default=5020)
    args = parser.parse_args()
    try:
        asyncio.run(run_server(args.port, args.tcp_port))
    except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
        pass
