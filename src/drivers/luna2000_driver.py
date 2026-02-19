"""
src/drivers/luna2000_driver.py
================================
BESSAI Edge Gateway — Huawei LUNA2000 Battery ESS Driver.

Communicates with a LUNA2000-(7,14,21)-S1 ESS connected to a SUN2000 inverter
via Modbus TCP (through the inverter as gateway, slave_id=3 typically).

Register addresses from: Huawei SUN2000 Modbus Interface Definition v3.0 (2024)
Battery registers start at 37xxx.

Usage::

    async with LUNADriver(host="192.168.1.100", port=502, slave_id=3) as drv:
        tel = await drv.read_telemetry()
        await drv.set_mode(BatteryMode.MAX_SELF_CONSUMPTION)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

import structlog

__all__ = ["LUNADriver", "LUNATelemetry", "BatteryMode"]

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Register addresses (Huawei SUN2000 Interface Definition v3.0)
# ---------------------------------------------------------------------------
REG_LUNA_TEMP        = 37752   # INT16  /10 °C
REG_LUNA_SOC         = 37760   # UINT16 /10 %
REG_LUNA_SOH         = 37761   # UINT16 /10 %
REG_LUNA_CYCLE_COUNT = 37762   # UINT16 cycles
REG_LUNA_CAPACITY_HI = 37758   # UINT32 (2 regs) /0.001 kWh
REG_LUNA_POWER_HI    = 37765   # INT32  (2 regs) /0.001 kW, + = charging
REG_LUNA_VOLTAGE     = 37800   # UINT16 /10 V
REG_LUNA_CURRENT     = 37801   # INT16  /10 A

REG_LUNA_MODE        = 47086   # UINT16 RW working mode
REG_LUNA_TARGET_SOC  = 47087   # UINT16 RW /10 % charge target


class BatteryMode(IntEnum):
    """LUNA2000 working mode codes (register 47086)."""
    MAX_SELF_CONSUMPTION = 0
    FULLY_CHARGED        = 1
    TIME_OF_USE          = 2
    REMOTE_DISPATCH      = 3


@dataclass
class LUNATelemetry:
    """Single telemetry snapshot from the LUNA2000 ESS."""

    soc_pct: float           # State of charge 0.0–100.0 %
    soh_pct: float           # State of health 0.0–100.0 %
    power_kw: float          # Positive = charging, negative = discharging
    voltage_v: float         # Pack voltage in V (350–560 V)
    current_a: float         # Pack current in A
    temperature_c: float     # Pack temperature in °C
    cycle_count: int         # Cumulative cycle count
    capacity_kwh: float      # Usable capacity in kWh
    working_mode: BatteryMode = BatteryMode.MAX_SELF_CONSUMPTION
    timestamp: float = field(default_factory=time.time)

    @property
    def is_charging(self) -> bool:
        return self.power_kw > 0.01

    @property
    def is_discharging(self) -> bool:
        return self.power_kw < -0.01

    @property
    def is_idle(self) -> bool:
        return not self.is_charging and not self.is_discharging

    def to_dict(self) -> dict:
        return {
            "soc_pct": round(self.soc_pct, 1),
            "soh_pct": round(self.soh_pct, 1),
            "power_kw": round(self.power_kw, 3),
            "voltage_v": round(self.voltage_v, 1),
            "current_a": round(self.current_a, 2),
            "temperature_c": round(self.temperature_c, 1),
            "cycle_count": self.cycle_count,
            "capacity_kwh": round(self.capacity_kwh, 3),
            "working_mode": self.working_mode.name,
            "is_charging": self.is_charging,
            "is_discharging": self.is_discharging,
            "timestamp": self.timestamp,
        }


class LUNADriver:
    """Async Modbus driver for the LUNA2000 battery ESS.

    Connects through the SUN2000 inverter acting as Modbus gateway.
    The inverter exposes LUNA2000 registers on its own slave_id.

    Parameters:
        host:      IP address of the SUN2000 inverter.
        port:      Modbus TCP port (default 502).
        slave_id:  Modbus slave ID (default 3 for SUN2000).
    """

    def __init__(
        self,
        host: str = "192.168.1.100",
        port: int = 502,
        slave_id: int = 3,
    ) -> None:
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self._client: Optional[object] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_client(self) -> object:
        try:
            from pymodbus.client import ModbusTcpClient  # type: ignore
            return ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=3,
                retries=2,
            )
        except ImportError:
            raise RuntimeError("pymodbus not installed")

    def _read_regs(self, address: int, count: int) -> list[int]:
        """Read holding registers (FC03). Returns list of raw uint16 values."""
        assert self._client is not None
        result = self._client.read_holding_registers(  # type: ignore
            address=address, count=count, slave=self.slave_id
        )
        if result.isError():
            raise IOError(f"Modbus read error addr={address}: {result}")
        return list(result.registers)

    def _write_reg(self, address: int, value: int) -> None:
        """Write single holding register (FC06)."""
        assert self._client is not None
        result = self._client.write_register(  # type: ignore
            address=address, value=value, slave=self.slave_id
        )
        if result.isError():
            raise IOError(f"Modbus write error addr={address}: {result}")

    @staticmethod
    def _to_int32(hi: int, lo: int) -> int:
        raw = (hi << 16) | lo
        return raw - (1 << 32) if raw >= (1 << 31) else raw

    @staticmethod
    def _to_uint32(hi: int, lo: int) -> int:
        return (hi << 16) | lo

    @staticmethod
    def _to_int16(raw: int) -> int:
        return raw - (1 << 16) if raw >= (1 << 15) else raw

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "LUNADriver":
        self._client = self._make_client()
        connected = await asyncio.get_event_loop().run_in_executor(
            None, self._client.connect  # type: ignore
        )
        if not connected:
            raise ConnectionError(f"Cannot connect to SUN2000 at {self.host}:{self.port}")
        log.info("luna.connected", host=self.host, slave_id=self.slave_id)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await asyncio.get_event_loop().run_in_executor(
                None, self._client.close  # type: ignore
            )
        log.info("luna.disconnected")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def read_telemetry(self) -> LUNATelemetry:
        """Read a full LUNA2000 telemetry snapshot.

        Returns:
            LUNATelemetry with all measured values.
        """
        loop = asyncio.get_event_loop()

        def _read() -> LUNATelemetry:
            temp_raw  = self._read_regs(REG_LUNA_TEMP, 1)[0]
            soc_raw   = self._read_regs(REG_LUNA_SOC, 1)[0]
            soh_raw   = self._read_regs(REG_LUNA_SOH, 1)[0]
            cycles    = self._read_regs(REG_LUNA_CYCLE_COUNT, 1)[0]
            cap_regs  = self._read_regs(REG_LUNA_CAPACITY_HI, 2)
            pwr_regs  = self._read_regs(REG_LUNA_POWER_HI, 2)
            volt_raw  = self._read_regs(REG_LUNA_VOLTAGE, 1)[0]
            curr_raw  = self._read_regs(REG_LUNA_CURRENT, 1)[0]
            mode_raw  = self._read_regs(REG_LUNA_MODE, 1)[0]

            return LUNATelemetry(
                soc_pct       = soc_raw * 0.1,
                soh_pct       = soh_raw * 0.1,
                power_kw      = self._to_int32(*pwr_regs) * 0.001,
                voltage_v     = volt_raw * 0.1,
                current_a     = self._to_int16(curr_raw) * 0.1,
                temperature_c = self._to_int16(temp_raw) * 0.1,
                cycle_count   = cycles,
                capacity_kwh  = self._to_uint32(*cap_regs) * 0.001,
                working_mode  = BatteryMode(min(mode_raw, 3)),
            )

        return await loop.run_in_executor(None, _read)

    async def set_mode(self, mode: BatteryMode) -> None:
        """Set LUNA2000 working mode (FC06 write to register 47086).

        Args:
            mode: BatteryMode enum value.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self._write_reg(REG_LUNA_MODE, int(mode))
        )
        log.info("luna.mode_set", mode=mode.name)

    async def set_charge_target_soc(self, target_pct: float) -> None:
        """Set charge cutoff SOC target (0–100%).

        Args:
            target_pct: Target SOC in percent (e.g., 80.0).
        """
        if not 0.0 <= target_pct <= 100.0:
            raise ValueError(f"target_pct must be 0–100, got {target_pct}")
        raw = int(round(target_pct * 10))
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self._write_reg(REG_LUNA_TARGET_SOC, raw)
        )
        log.info("luna.charge_target_set", target_pct=target_pct)
