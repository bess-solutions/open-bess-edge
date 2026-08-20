# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/drivers/ingeteam_driver.py
===============================
BESSAI Edge Gateway — Ingeteam Ingecon Sun Storage 1500V Driver.

Communicates with Ingeteam Ingecon Sun Storage B-Series / Power Station inverters
via Modbus TCP (standard port 502, slave_id=1).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog

__all__ = ["IngeteamDriver", "IngeteamTelemetry", "IngeteamOperatingState"]

log = structlog.get_logger(__name__)

# Register Addresses (Ingeteam Modbus Protocol Map)
REG_INGETEAM_STATUS = 3000          # UINT16 Inverter operating state
REG_INGETEAM_ALARM_FLAGS = 3001     # UINT32 (2 regs) Safety & grid fault alarms
REG_INGETEAM_AC_ACTIVE_POWER = 3003 # INT32  (2 regs) /100 kW active power
REG_INGETEAM_AC_REACTIVE_POWER = 3005 # INT32 (2 regs) /100 kVAR reactive power
REG_INGETEAM_AC_FREQUENCY = 3007    # UINT16 /100 Hz (e.g. 5000 -> 50.00 Hz)
REG_INGETEAM_DC_VOLTAGE = 3008      # UINT16 /10 V (e.g. 14200 -> 1420.0 V)
REG_INGETEAM_DC_CURRENT = 3009      # INT16  /10 A
REG_INGETEAM_SOC = 3010             # UINT16 /10 %
REG_INGETEAM_SOH = 3011             # UINT16 /10 %
REG_INGETEAM_CABINET_TEMP = 3012    # INT16  /10 °C
REG_INGETEAM_IGBT_MAX_TEMP = 3013   # INT16  /10 °C

# Control Registers
REG_INGETEAM_CTRL_P_REF = 4000      # INT32  (2 regs) /100 kW target active power
REG_INGETEAM_CTRL_Q_REF = 4002      # INT32  (2 regs) /100 kVAR target reactive power
REG_INGETEAM_CTRL_CMD = 4004        # UINT16 1=Start, 2=Stop, 3=Emergency Stop


class IngeteamOperatingState(IntEnum):
    STOPPED = 0
    STARTING = 1
    RUNNING = 2
    GRID_MONITORING = 3
    FAULT = 4


@dataclass
class IngeteamTelemetry:
    """Telemetry snapshot from Ingeteam 1500V Storage Inverter."""
    status: IngeteamOperatingState
    active_power_kw: float
    reactive_power_kvar: float
    grid_frequency_hz: float
    dc_voltage_v: float
    dc_current_a: float
    soc_pct: float
    soh_pct: float
    cabinet_temp_c: float
    igbt_temp_c: float
    alarm_code: int
    timestamp: float = field(default_factory=time.time)

    @property
    def is_discharging(self) -> bool:
        return self.active_power_kw < -0.05

    @property
    def is_charging(self) -> bool:
        return self.active_power_kw > 0.05

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.name,
            "active_power_kw": round(self.active_power_kw, 2),
            "reactive_power_kvar": round(self.reactive_power_kvar, 2),
            "grid_frequency_hz": round(self.grid_frequency_hz, 2),
            "dc_voltage_v": round(self.dc_voltage_v, 1),
            "dc_current_a": round(self.dc_current_a, 2),
            "soc_pct": round(self.soc_pct, 1),
            "soh_pct": round(self.soh_pct, 1),
            "cabinet_temp_c": round(self.cabinet_temp_c, 1),
            "igbt_temp_c": round(self.igbt_temp_c, 1),
            "alarm_code": self.alarm_code,
            "timestamp": self.timestamp,
        }


class IngeteamDriver:
    """Async Modbus TCP Driver for Ingeteam Storage Inverters."""

    def __init__(self, host: str = "192.168.1.170", port: int = 502, slave_id: int = 1):
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self._connected = False
        self._client: Any = None
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        async with self._lock:
            try:
                from pymodbus.client import AsyncModbusTcpClient
                self._client = AsyncModbusTcpClient(host=self.host, port=self.port, timeout=3.0)
                self._connected = bool(await self._client.connect())
                return self._connected
            except Exception:
                self._connected = False
                return False

    async def disconnect(self) -> None:
        async with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
            self._connected = False

    async def __aenter__(self) -> "IngeteamDriver":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def read_telemetry(self) -> IngeteamTelemetry:
        if not self._connected or not self._client:
            raise RuntimeError("IngeteamDriver not connected")

        async with self._lock:
            res = await self._client.read_holding_registers(address=REG_INGETEAM_STATUS, count=14, slave=self.slave_id)
            if res.isError() or not hasattr(res, "registers"):
                raise RuntimeError("Modbus read error on Ingeteam inverter")

            r = res.registers

            def _to_int16(val: int) -> int:
                return val - 65536 if val > 32767 else val

            def _to_int32(hi: int, lo: int) -> int:
                val = (hi << 16) | lo
                return val - 4294967296 if val > 2147483647 else val

            return IngeteamTelemetry(
                status=IngeteamOperatingState(r[0]) if r[0] <= 4 else IngeteamOperatingState.FAULT,
                alarm_code=(r[1] << 16) | r[2],
                active_power_kw=_to_int32(r[3], r[4]) * 0.01,
                reactive_power_kvar=_to_int32(r[5], r[6]) * 0.01,
                grid_frequency_hz=r[7] * 0.01,
                dc_voltage_v=r[8] * 0.1,
                dc_current_a=_to_int16(r[9]) * 0.1,
                soc_pct=r[10] * 0.1,
                soh_pct=r[11] * 0.1,
                cabinet_temp_c=_to_int16(r[12]) * 0.1,
                igbt_temp_c=_to_int16(r[13]) * 0.1,
            )

    async def set_active_power(self, power_kw: float) -> bool:
        if not self._connected or not self._client:
            return False

        async with self._lock:
            scaled = int(round(power_kw * 100.0))
            if scaled < 0:
                scaled += 4294967296
            hi = (scaled >> 16) & 0xFFFF
            lo = scaled & 0xFFFF
            res = await self._client.write_registers(address=REG_INGETEAM_CTRL_P_REF, values=[hi, lo], slave=self.slave_id)
            return not res.isError()
