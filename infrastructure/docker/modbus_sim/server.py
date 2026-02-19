"""
infrastructure/docker/modbus_sim/server.py
==========================================
Simulador Modbus TCP para BESSAI Edge Gateway (dev/test).
Usa pymodbus 3.x (mismo del proyecto) y simula todos los registros
SUN2000 + LUNA2000 con valores realistas.

Puerto: 502  (mapeado a 5020 en el host)
Unit ID: 1   (gateway-sim usa slave_id=1, gateway usa 3)
"""
from __future__ import annotations

import asyncio
import struct
import logging
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.server import StartAsyncTcpServer
from pymodbus.device import ModbusDeviceIdentification

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bessai-sim")

# ---------------------------------------------------------------------------
# Register values — SUN2000-2-6KTL-L1 + LUNA2000 (realistic sunny day)
# ---------------------------------------------------------------------------
# Modbus holding registers are addressed 0-based internally in pymodbus,
# but the Modbus protocol uses 1-based, pymodbus handles the offset.
# We use address as-is matching the device spec (40001 offset not needed
# for read_holding_registers which is 0-based internally).
# We create a block large enough to cover all registers (0 to 50000).

def _make_block() -> ModbusSequentialDataBlock:
    """Build a large zero-filled block and set known register values."""
    SIZE = 50000
    data = [0] * SIZE

    # ── Inverter state ──────────────────────────────────────────────────────
    data[32089] = 256          # Running / Grid Connected

    # ── PV strings ───────────────────────────────────────────────────────────
    data[32016] = 3600         # PV1 voltage 360.0V (INT16, *0.1)
    data[32017] = 850          # PV1 current 8.50A  (INT16, *0.01)
    data[32018] = 3550         # PV2 voltage 355.0V
    data[32019] = 820          # PV2 current 8.20A

    # ── PV total power INT32 5800W = 5.8kW ──────────────────────────────────
    pv_power = struct.pack(">i", 5800)
    data[32064] = int.from_bytes(pv_power[0:2], "big")
    data[32065] = int.from_bytes(pv_power[2:4], "big")

    # ── AC output ────────────────────────────────────────────────────────────
    data[32069] = 2300         # AC voltage 230.0V  (UINT16, *0.1)
    # AC power INT32 5750W = 5.75kW
    ac_power = struct.pack(">i", 5750)
    data[32080] = int.from_bytes(ac_power[0:2], "big")
    data[32081] = int.from_bytes(ac_power[2:4], "big")
    data[32085] = 5000         # Frequency 50.00Hz  (UINT16, *0.01)
    data[32087] = 420          # Temp 42.0°C        (INT16, *0.1)

    # ── Alarms (none) ────────────────────────────────────────────────────────
    data[32008] = 0x0000
    data[32009] = 0x0000

    # ── Energy ───────────────────────────────────────────────────────────────
    # daily_energy: 28.50 kWh → UINT32 = 2850 (scale 0.01)
    daily = struct.pack(">I", 2850)
    data[32114] = int.from_bytes(daily[0:2], "big")
    data[32115] = int.from_bytes(daily[2:4], "big")
    # total_energy: 5280.00 kWh → UINT32 = 528000
    total = struct.pack(">I", 528000)
    data[32106] = int.from_bytes(total[0:2], "big")
    data[32107] = int.from_bytes(total[2:4], "big")

    # ── LUNA2000 battery ─────────────────────────────────────────────────────
    data[37752] = 260          # temperature 26.0°C (INT16, *0.1)
    data[37760] = 750          # SOC  75.0%         (UINT16, *0.1)
    data[37761] = 980          # SOH  98.0%         (UINT16, *0.1)
    data[37762] = 88           # cycle count
    # luna_capacity UINT32 14000 Wh = 14.0 kWh (scale 0.001)
    cap = struct.pack(">I", 14000)
    data[37758] = int.from_bytes(cap[0:2], "big")
    data[37759] = int.from_bytes(cap[2:4], "big")
    # luna_power INT32 -2500 W = -2.5 kW discharging (scale 0.001)
    pwr = struct.pack(">i", -2500)
    data[37765] = int.from_bytes(pwr[0:2], "big")
    data[37766] = int.from_bytes(pwr[2:4], "big")
    data[37800] = 4750         # voltage 475.0V (UINT16, *0.1)
    data[37801] = 0xFFCE       # current -5.0A  (INT16 two's complement -50, *0.1)

    # ── Working mode (RW) ────────────────────────────────────────────────────
    data[47086] = 0            # MAX_SELF_CONSUMPTION
    data[47087] = 900          # target SOC 90.0%

    # ── Watchdog heartbeat (RW) ───────────────────────────────────────────────
    data[40900] = 0

    return ModbusSequentialDataBlock(0, data)


async def run_server() -> None:
    block = _make_block()

    # One slave for all unit IDs (gateway uses 3, gateway-sim uses 1)
    slave = ModbusSlaveContext(hr=block)
    context = ModbusServerContext(slaves={1: slave, 3: slave}, single=False)

    identity = ModbusDeviceIdentification()
    identity.VendorName = "BESSAI-SIM"
    identity.ProductCode = "SUN2000-SIM"
    identity.VendorUrl = "https://github.com/bess-solutions/open-bess-edge"
    identity.ProductName = "BESSAI Modbus Simulator"
    identity.ModelName = "SUN2000-2-6KTL-L1-SIM"
    identity.MajorMinorRevision = "v1.0.0"

    log.info("Starting BESSAI Modbus simulator on 0.0.0.0:502")
    await StartAsyncTcpServer(
        context=context,
        identity=identity,
        address=("0.0.0.0", 502),
    )


if __name__ == "__main__":
    asyncio.run(run_server())
