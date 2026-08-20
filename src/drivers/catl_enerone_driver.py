# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/drivers/catl_enerone_driver.py
===================================
BESSAI Edge Gateway — CATL EnerOne / EnerX Utility BESS Driver.

Communicates with CATL EnerOne (Outdoor Liquid Cooling BESS) via Modbus TCP.
Designed for 280Ah/306Ah LFP chemistry with individual rack BMS telemetry.

Usage::

    async with CATLEnerOneDriver(host="192.168.1.160", port=502) as drv:
        tel = await drv.read_telemetry()
        await drv.set_liquid_cooling_target(temp_c=25.0)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog

__all__ = ["CATLEnerOneDriver", "CATLTelemetry", "CATLBmsState"]

log = structlog.get_logger(__name__)

# Register addresses (CATL EnerOne Modbus Protocol Map)
REG_CATL_DC_VOLTAGE = 1000      # UINT16 /10 V (e.g. 12800 -> 1280.0 V)
REG_CATL_DC_CURRENT = 1001      # INT16  /10 A (+ = charge, - = discharge)
REG_CATL_ACTIVE_POWER = 1002    # INT32  (2 regs) /10 kW
REG_CATL_SOC = 1004             # UINT16 /10 %
REG_CATL_SOH = 1005             # UINT16 /10 %
REG_CATL_MAX_CELL_TEMP = 1006   # INT16  /10 °C
REG_CATL_MIN_CELL_TEMP = 1007   # INT16  /10 °C
REG_CATL_MAX_CELL_VOLT = 1008   # UINT16 mV (e.g. 3340 mV)
REG_CATL_MIN_CELL_VOLT = 1009   # UINT16 mV (e.g. 3310 mV)
REG_CATL_INSULATION_RES = 1010  # UINT16 kOhm (e.g. 5000 kOhm)
REG_CATL_RACK_COUNT = 1011      # UINT16 Active racks (e.g. 8)
REG_CATL_COOLANT_TEMP_IN = 1012 # INT16  /10 °C Inflow coolant
REG_CATL_COOLANT_TEMP_OUT = 1013# INT16  /10 °C Outflow coolant
REG_CATL_COOLANT_PRESSURE = 1014# UINT16 /100 Bar (e.g. 150 -> 1.50 Bar)
REG_CATL_ALARM_BITMAP = 1015    # UINT32 (2 regs) Safety flags


class CATLBmsState(IntEnum):
    STANDBY = 0
    NORMAL_OPERATION = 1
    WARNING = 2
    PROTECTION_TRIP = 3
    MAINTENANCE = 4


@dataclass
class CATLTelemetry:
    """Telemetry from CATL EnerOne Container."""
    soc_pct: float
    soh_pct: float
    active_power_kw: float
    dc_voltage_v: float
    dc_current_a: float
    max_cell_temp_c: float
    min_cell_temp_c: float
    max_cell_volt_mv: int
    min_cell_volt_mv: int
    insulation_kohm: int
    active_racks: int
    coolant_in_c: float
    coolant_out_c: float
    coolant_pressure_bar: float
    alarm_code: int
    bms_state: CATLBmsState = CATLBmsState.NORMAL_OPERATION
    timestamp: float = field(default_factory=time.time)

    @property
    def delta_temp_coolant(self) -> float:
        return round(self.coolant_out_c - self.coolant_in_c, 2)

    @property
    def is_thermal_balanced(self) -> bool:
        return (self.max_cell_temp_c - self.min_cell_temp_c) <= 3.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "soc_pct": round(self.soc_pct, 1),
            "soh_pct": round(self.soh_pct, 1),
            "active_power_kw": round(self.active_power_kw, 2),
            "dc_voltage_v": round(self.dc_voltage_v, 1),
            "dc_current_a": round(self.dc_current_a, 2),
            "max_cell_temp_c": round(self.max_cell_temp_c, 1),
            "min_cell_temp_c": round(self.min_cell_temp_c, 1),
            "max_cell_volt_mv": self.max_cell_volt_mv,
            "min_cell_volt_mv": self.min_cell_volt_mv,
            "insulation_kohm": self.insulation_kohm,
            "active_racks": self.active_racks,
            "coolant_in_c": self.coolant_in_c,
            "coolant_out_c": self.coolant_out_c,
            "delta_temp_coolant_c": self.delta_temp_coolant,
            "coolant_pressure_bar": self.coolant_pressure_bar,
            "is_thermal_balanced": self.is_thermal_balanced,
            "bms_state": self.bms_state.name,
            "timestamp": self.timestamp,
        }


class CATLEnerOneDriver:
    """Async Modbus TCP driver for CATL EnerOne BESS."""
    def __init__(self, host: str = "192.168.1.160", port: int = 502, slave_id: int = 1):
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

    async def __aenter__(self) -> "CATLEnerOneDriver":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def read_telemetry(self) -> CATLTelemetry:
        if not self._connected or not self._client:
            raise RuntimeError("CATLEnerOneDriver not connected")

        async with self._lock:
            res = await self._client.read_holding_registers(address=REG_CATL_DC_VOLTAGE, count=17, slave=self.slave_id)
            if res.isError() or not hasattr(res, "registers"):
                raise RuntimeError("Modbus read error on CATL EnerOne")

            r = res.registers

            def _to_int16(val: int) -> int:
                return val - 65536 if val > 32767 else val

            def _to_int32(hi: int, lo: int) -> int:
                val = (hi << 16) | lo
                return val - 4294967296 if val > 2147483647 else val

            return CATLTelemetry(
                dc_voltage_v=r[0] * 0.1,
                dc_current_a=_to_int16(r[1]) * 0.1,
                active_power_kw=_to_int32(r[2], r[3]) * 0.1,
                soc_pct=r[4] * 0.1,
                soh_pct=r[5] * 0.1,
                max_cell_temp_c=_to_int16(r[6]) * 0.1,
                min_cell_temp_c=_to_int16(r[7]) * 0.1,
                max_cell_volt_mv=r[8],
                min_cell_volt_mv=r[9],
                insulation_kohm=r[10],
                active_racks=r[11],
                coolant_in_c=_to_int16(r[12]) * 0.1,
                coolant_out_c=_to_int16(r[13]) * 0.1,
                coolant_pressure_bar=r[14] * 0.01,
                alarm_code=(r[15] << 16) | r[16],
            )
