# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/drivers/sungrow_driver.py
================================
BESSAI Edge Gateway — Sungrow PowerTitan 1500V Utility BESS Driver.

Communicates with Sungrow PowerTitan / PowerStack utility-scale BESS
(ST2752UX / SC5000UD-MV series) via Modbus TCP (typical slave_id=1).

Register addresses mapped according to:
Sungrow Utility-Scale BESS Modbus Interface Protocol Specification (1500V DC Architecture).

Usage::

    async with SungrowDriver(host="192.168.1.150", port=502, slave_id=1) as drv:
        tel = await drv.read_telemetry()
        await drv.set_active_power(power_kw=-2500.0)  # Discharge 2.5 MW
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import structlog

__all__ = ["SungrowDriver", "SungrowTelemetry", "SungrowWorkingMode", "SungrowAlarmState"]

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Register addresses (Sungrow 1500V Modbus Protocol Map)
# ---------------------------------------------------------------------------
# Telemetry registers (Read-Only 5000 range)
REG_SUNGROW_DC_VOLTAGE = 5000       # UINT16 /10 V (e.g. 13500 -> 1350.0 V)
REG_SUNGROW_DC_CURRENT = 5001       # INT16  /10 A (+ = charge, - = discharge)
REG_SUNGROW_ACTIVE_POWER = 5002     # INT32  (2 regs) /10 kW (e.g. 27500 -> 2750.0 kW)
REG_SUNGROW_REACTIVE_POWER = 5004   # INT32  (2 regs) /10 kVAR
REG_SUNGROW_SOC = 5006              # UINT16 /10 % (0.0 - 100.0%)
REG_SUNGROW_SOH = 5007              # UINT16 /10 % (0.0 - 100.0%)
REG_SUNGROW_MAX_CELL_TEMP = 5008    # INT16  /10 °C
REG_SUNGROW_MIN_CELL_TEMP = 5009    # INT16  /10 °C
REG_SUNGROW_MAX_CELL_VOLT = 5010    # UINT16 mV (e.g. 3350 mV)
REG_SUNGROW_MIN_CELL_VOLT = 5011    # UINT16 mV (e.g. 3310 mV)
REG_SUNGROW_CYCLE_COUNT = 5012      # UINT32 (2 regs) total cycles
REG_SUNGROW_RATED_CAPACITY = 5014   # UINT32 (2 regs) /10 kWh (e.g. 27520 -> 2752.0 kWh)
REG_SUNGROW_LIQUID_PUMP_RUN = 5016  # UINT16 0=Stop, 1=Running, 2=Fault
REG_SUNGROW_HVAC_STATUS = 5017      # UINT16 0=Off, 1=Cooling, 2=Heating, 3=Fault
REG_SUNGROW_ALARM_CODE = 5018       # UINT32 (2 regs) Bitfield alarm flags
REG_SUNGROW_WORK_MODE = 5020        # UINT16 System status / mode

# Control registers (Read/Write)
REG_SUNGROW_CTRL_POWER_SET = 6000   # INT32  (2 regs) /10 kW target active power
REG_SUNGROW_CTRL_Q_SET = 6002       # INT32  (2 regs) /10 kVAR target reactive power
REG_SUNGROW_CTRL_RUN_CMD = 6004     # UINT16 0xAA=Start, 0x55=Stop, 0xEE=Emergency Stop
REG_SUNGROW_CTRL_SOC_MAX = 6005     # UINT16 /10 % Max Charge SOC Limit
REG_SUNGROW_CTRL_SOC_MIN = 6006     # UINT16 /10 % Min Discharge SOC Limit


class SungrowWorkingMode(IntEnum):
    """Sungrow PowerTitan working modes."""

    STANDBY = 0
    CHARGING = 1
    DISCHARGING = 2
    FAULT = 3
    MAINTENANCE = 4
    GRID_FORMING_VSM = 5


class SungrowAlarmState:
    """Decodes 32-bit alarm bitmap for utility diagnostics."""

    OVER_TEMP: int = 1 << 0
    UNDER_TEMP: int = 1 << 1
    OVER_VOLT: int = 1 << 2
    UNDER_VOLT: int = 1 << 3
    LIQUID_LEAK: int = 1 << 4
    SMOKE_ALARM: int = 1 << 5
    INSULATION_FAULT: int = 1 << 6
    PUMP_FAIL: int = 1 << 7

    @classmethod
    def get_active_alarms(cls, code: int) -> list[str]:
        alarms = []
        if code & cls.OVER_TEMP:
            alarms.append("OVER_TEMPERATURE")
        if code & cls.UNDER_TEMP:
            alarms.append("UNDER_TEMPERATURE")
        if code & cls.OVER_VOLT:
            alarms.append("OVER_VOLTAGE_1500V")
        if code & cls.UNDER_VOLT:
            alarms.append("UNDER_VOLTAGE")
        if code & cls.LIQUID_LEAK:
            alarms.append("LIQUID_COOLING_LEAKAGE")
        if code & cls.SMOKE_ALARM:
            alarms.append("FIRE_SMOKE_DETECTED")
        if code & cls.INSULATION_FAULT:
            alarms.append("INSULATION_RESISTANCE_LOW")
        if code & cls.PUMP_FAIL:
            alarms.append("COOLING_PUMP_FAILURE")
        return alarms


@dataclass
class SungrowTelemetry:
    """Telemetry snapshot from Sungrow PowerTitan 1500V BESS."""

    soc_pct: float                      # 0.0 - 100.0 %
    soh_pct: float                      # 0.0 - 100.0 %
    active_power_kw: float              # + = charge, - = discharge
    reactive_power_kvar: float          # Reactive support
    dc_voltage_v: float                 # Pack DC voltage (up to 1500.0 V)
    dc_current_a: float                 # Pack DC current
    max_cell_temp_c: float              # Max LFP cell temperature
    min_cell_temp_c: float              # Min LFP cell temperature
    max_cell_volt_mv: int               # Max cell voltage in millivolts
    min_cell_volt_mv: int               # Min cell voltage in millivolts
    cycle_count: int                    # Cumulative full equivalent cycles
    capacity_kwh: float                 # Usable total capacity (e.g. 2752.0 kWh)
    liquid_pump_running: bool           # Liquid cooling pump status
    hvac_status: int                    # HVAC mode
    alarm_code: int                     # Raw 32-bit alarm bitmap
    working_mode: SungrowWorkingMode = SungrowWorkingMode.STANDBY
    timestamp: float = field(default_factory=time.time)

    @property
    def is_charging(self) -> bool:
        return self.active_power_kw > 0.05

    @property
    def is_discharging(self) -> bool:
        return self.active_power_kw < -0.05

    @property
    def is_idle(self) -> bool:
        return not self.is_charging and not self.is_discharging

    @property
    def delta_cell_temp(self) -> float:
        """Thermal dispersion across LFP container in °C."""
        return round(self.max_cell_temp_c - self.min_cell_temp_c, 2)

    @property
    def delta_cell_volt_mv(self) -> int:
        """Cell balancing dispersion in mV."""
        return self.max_cell_volt_mv - self.min_cell_volt_mv

    @property
    def active_alarms(self) -> list[str]:
        return SungrowAlarmState.get_active_alarms(self.alarm_code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "soc_pct": round(self.soc_pct, 1),
            "soh_pct": round(self.soh_pct, 1),
            "active_power_kw": round(self.active_power_kw, 2),
            "reactive_power_kvar": round(self.reactive_power_kvar, 2),
            "dc_voltage_v": round(self.dc_voltage_v, 1),
            "dc_current_a": round(self.dc_current_a, 2),
            "max_cell_temp_c": round(self.max_cell_temp_c, 1),
            "min_cell_temp_c": round(self.min_cell_temp_c, 1),
            "delta_cell_temp_c": self.delta_cell_temp,
            "max_cell_volt_mv": self.max_cell_volt_mv,
            "min_cell_volt_mv": self.min_cell_volt_mv,
            "delta_cell_volt_mv": self.delta_cell_volt_mv,
            "cycle_count": self.cycle_count,
            "capacity_kwh": round(self.capacity_kwh, 1),
            "liquid_pump_running": self.liquid_pump_running,
            "working_mode": self.working_mode.name,
            "active_alarms": self.active_alarms,
            "is_charging": self.is_charging,
            "is_discharging": self.is_discharging,
            "timestamp": self.timestamp,
        }


class SungrowDriver:
    """Async Modbus TCP driver for Sungrow PowerTitan 1500V BESS."""

    def __init__(
        self,
        host: str = "192.168.1.150",
        port: int = 502,
        slave_id: int = 1,
        timeout: float = 3.0,
    ) -> None:
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.timeout = timeout
        self._client: Any = None
        self._connected = False
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def source_description(self) -> str:
        return f"SungrowPowerTitan@{self.host}:{self.port}:slave{self.slave_id}"

    async def connect(self) -> bool:
        """Establishes Modbus TCP connection to the Sungrow gateway."""
        async with self._lock:
            if self._connected and self._client:
                return True

            log.info("Connecting to Sungrow PowerTitan", host=self.host, port=self.port)
            try:
                from pymodbus.client import AsyncModbusTcpClient
                self._client = AsyncModbusTcpClient(
                    host=self.host,
                    port=self.port,
                    timeout=self.timeout,
                )
                connected = await self._client.connect()
                self._connected = bool(connected)
                if self._connected:
                    log.info("Connected to Sungrow PowerTitan successfully", source=self.source_description)
                else:
                    log.error("Failed to connect to Sungrow PowerTitan", host=self.host)
                return self._connected
            except Exception as exc:
                log.error("Modbus TCP connection exception", host=self.host, error=str(exc))
                self._connected = False
                return False

    async def disconnect(self) -> None:
        """Closes the connection safely."""
        async with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
            self._connected = False
            log.info("Disconnected from Sungrow PowerTitan", source=self.source_description)

    async def __aenter__(self) -> "SungrowDriver":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def read_telemetry(self) -> SungrowTelemetry:
        """Reads and decodes the complete 1500V telemetry register block."""
        if not self._connected or not self._client:
            raise RuntimeError(f"Cannot read telemetry: Sungrow driver not connected ({self.source_description})")

        async with self._lock:
            # Read block of 22 holding registers from 5000
            res = await self._client.read_holding_registers(
                address=REG_SUNGROW_DC_VOLTAGE,
                count=22,
                slave=self.slave_id,
            )

            if res.isError() or not hasattr(res, "registers"):
                raise RuntimeError(f"Modbus error reading Sungrow telemetry: {res}")

            regs = res.registers

            def _to_int16(val: int) -> int:
                return val - 65536 if val > 32767 else val

            def _to_int32(hi: int, lo: int) -> int:
                val = (hi << 16) | lo
                return val - 4294967296 if val > 2147483647 else val

            def _to_uint32(hi: int, lo: int) -> int:
                return (hi << 16) | lo

            dc_voltage = regs[0] * 0.1
            dc_current = _to_int16(regs[1]) * 0.1
            active_power = _to_int32(regs[2], regs[3]) * 0.1
            reactive_power = _to_int32(regs[4], regs[5]) * 0.1
            soc = regs[6] * 0.1
            soh = regs[7] * 0.1
            max_temp = _to_int16(regs[8]) * 0.1
            min_temp = _to_int16(regs[9]) * 0.1
            max_volt = regs[10]
            min_volt = regs[11]
            cycles = _to_uint32(regs[12], regs[13])
            capacity = _to_uint32(regs[14], regs[15]) * 0.1
            pump_status = regs[16] == 1
            hvac_mode = regs[17]
            alarm_code = _to_uint32(regs[18], regs[19])
            mode_val = regs[20]

            try:
                mode = SungrowWorkingMode(mode_val)
            except ValueError:
                mode = SungrowWorkingMode.STANDBY

            return SungrowTelemetry(
                soc_pct=soc,
                soh_pct=soh,
                active_power_kw=active_power,
                reactive_power_kvar=reactive_power,
                dc_voltage_v=dc_voltage,
                dc_current_a=dc_current,
                max_cell_temp_c=max_temp,
                min_cell_temp_c=min_temp,
                max_cell_volt_mv=max_volt,
                min_cell_volt_mv=min_volt,
                cycle_count=cycles,
                capacity_kwh=capacity,
                liquid_pump_running=pump_status,
                hvac_status=hvac_mode,
                alarm_code=alarm_code,
                working_mode=mode,
            )

    async def set_active_power(self, power_kw: float) -> bool:
        """Sets target active power in kW (+ for charge, - for discharge)."""
        if not self._connected or not self._client:
            raise RuntimeError(f"Cannot set power: Not connected to {self.source_description}")

        async with self._lock:
            scaled = int(round(power_kw * 10.0))
            if scaled < 0:
                scaled = scaled + 4294967296

            hi = (scaled >> 16) & 0xFFFF
            lo = scaled & 0xFFFF

            res = await self._client.write_registers(
                address=REG_SUNGROW_CTRL_POWER_SET,
                values=[hi, lo],
                slave=self.slave_id,
            )
            return not res.isError()

    async def set_reactive_power(self, q_kvar: float) -> bool:
        """Sets reactive power target in kVAR for voltage support."""
        if not self._connected or not self._client:
            raise RuntimeError(f"Cannot set reactive power: Not connected to {self.source_description}")

        async with self._lock:
            scaled = int(round(q_kvar * 10.0))
            if scaled < 0:
                scaled = scaled + 4294967296

            hi = (scaled >> 16) & 0xFFFF
            lo = scaled & 0xFFFF

            res = await self._client.write_registers(
                address=REG_SUNGROW_CTRL_Q_SET,
                values=[hi, lo],
                slave=self.slave_id,
            )
            return not res.isError()

    async def emergency_stop(self) -> bool:
        """Sends immediate hardware emergency trip command."""
        if not self._connected or not self._client:
            return False

        async with self._lock:
            res = await self._client.write_register(
                address=REG_SUNGROW_CTRL_RUN_CMD,
                value=0x00EE,
                slave=self.slave_id,
            )
            log.warn("EMERGENCY TRIP SIGNAL SENT TO SUNGROW POWERTITAN", source=self.source_description)
            return not res.isError()
