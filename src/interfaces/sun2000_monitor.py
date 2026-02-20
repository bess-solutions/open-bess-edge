"""
src/interfaces/sun2000_monitor.py
===================================
BESSAI Edge Gateway — Huawei SUN2000 Full Telemetry Monitor.

Aggregates telemetry from both the SUN2000 PV inverter and the connected
LUNA2000 battery ESS into a unified snapshot. Decodes alarm bitmasks and
routes active alarms to the AlertManager.

Usage::

    monitor = SUN2000Monitor(host="192.168.1.100", slave_id=3, site_id="CL-001")
    async with monitor:
        tel = await monitor.read()
        print(tel.to_dict())
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum

import structlog

from .alert_manager import AlertLevel, AlertManager
from .metrics import (
    LAST_POWER_KW,
    LAST_SOC_PERCENT,
)

__all__ = [
    "SUN2000Monitor",
    "SUN2000Telemetry",
    "InverterState",
    "PVStringData",
]

log = structlog.get_logger(__name__)

# Alarm bitmask decoder (Alarm Register 32008 bits)
_ALARM1_BITS: dict[int, str] = {
    0:  "High String Input Reverse",
    1:  "Module Protection",
    2:  "Grounding Error",
    3:  "Low Insulation Resistance",
    4:  "DC Overvoltage",
    5:  "AC Grid Overvoltage",
    6:  "AC Grid Undervoltage",
    7:  "Grid Overfrequency",
    8:  "Grid Underfrequency",
    9:  "Unstable Grid",
    10: "Output Overcurrent",
    11: "Output DC Component Too High",
    12: "Anti-Islanding",
    14: "Disconnection",
    15: "Reserved",
}

_ALARM2_BITS: dict[int, str] = {
    0:  "AFCI Self-Check Fault",
    1:  "DC Arc Fault",
    2:  "PV String Reverse Connection",
    5:  "Battery Overtemperature",
    6:  "Battery Undertemperature",
    7:  "Battery Overcharge",
    8:  "Battery Overdischarge",
    9:  "Battery Abnormal",
    15: "RCMU Alarm",
}

# Register addresses — SUN2000 Interface Definition v3.0
REG_STATE     = 32089
REG_PV1_V     = 32016
REG_PV1_I     = 32017
REG_PV2_V     = 32018
REG_PV2_I     = 32019
REG_PV_POWER  = 32064  # INT32 (2 regs)
REG_AC_V      = 32069
REG_AC_I      = 32072  # INT32 (2 regs)
REG_AC_POWER  = 32080  # INT32 (2 regs)
REG_FREQ      = 32085
REG_TEMP      = 32087
REG_TOTAL_E   = 32106  # UINT32 (2 regs) /0.01 kWh
REG_DAILY_E   = 32114  # UINT32 (2 regs) /0.01 kWh
REG_ALARM1    = 32008
REG_ALARM2    = 32009

# LUNA2000
REG_LUNA_SOC  = 37760
REG_LUNA_PWR  = 37765  # INT32 (2 regs)
REG_LUNA_TEMP = 37752


class InverterState(IntEnum):
    """SUN2000 working state codes (register 32089)."""
    STANDBY         = 0
    GRID_CONNECTED  = 256
    FAULT           = 512
    SLEEP           = 1024
    UNKNOWN         = 9999

    @classmethod
    def from_raw(cls, raw: int) -> InverterState:
        try:
            return cls(raw)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class PVStringData:
    """One PV MPPT string measurement."""
    string_id: int
    voltage_v: float
    current_a: float

    @property
    def power_w(self) -> float:
        return self.voltage_v * self.current_a


@dataclass
class SUN2000Telemetry:
    """Complete SUN2000 + LUNA2000 telemetry snapshot."""

    site_id: str = "edge"
    timestamp: float = field(default_factory=time.time)

    # Inverter state
    state: InverterState = InverterState.UNKNOWN
    active_alarms: list[str] = field(default_factory=list)

    # PV inputs
    pv_strings: list[PVStringData] = field(default_factory=list)
    pv_total_power_kw: float = 0.0

    # AC output
    ac_voltage_v: float = 0.0
    ac_power_kw: float = 0.0
    ac_frequency_hz: float = 50.0

    # Inverter vitals
    temperature_c: float = 25.0
    daily_energy_kwh: float = 0.0
    total_energy_kwh: float = 0.0

    # LUNA2000 battery (None if not connected)
    batt_soc_pct: float | None = None
    batt_power_kw: float | None = None
    batt_temperature_c: float | None = None

    @property
    def is_safe(self) -> bool:
        """True if inverter is running without critical alarms."""
        critical = {"Grounding Error", "DC Arc Fault", "Battery Overtemperature",
                    "Battery Overdischarge", "Output Overcurrent"}
        return self.state != InverterState.FAULT and not any(
            a in critical for a in self.active_alarms
        )

    def to_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "timestamp": self.timestamp,
            "state": self.state.name,
            "is_safe": self.is_safe,
            "active_alarms": self.active_alarms,
            "pv": {
                "strings": [
                    {"id": s.string_id, "v": round(s.voltage_v, 1),
                     "a": round(s.current_a, 2), "w": round(s.power_w, 1)}
                    for s in self.pv_strings
                ],
                "total_kw": round(self.pv_total_power_kw, 3),
            },
            "ac": {
                "voltage_v": round(self.ac_voltage_v, 1),
                "power_kw": round(self.ac_power_kw, 3),
                "frequency_hz": round(self.ac_frequency_hz, 2),
            },
            "temperature_c": round(self.temperature_c, 1),
            "energy": {
                "daily_kwh": round(self.daily_energy_kwh, 2),
                "total_kwh": round(self.total_energy_kwh, 2),
            },
            "battery": {
                "soc_pct": round(self.batt_soc_pct, 1) if self.batt_soc_pct is not None else None,
                "power_kw": round(self.batt_power_kw, 3) if self.batt_power_kw is not None else None,
                "temperature_c": round(self.batt_temperature_c, 1) if self.batt_temperature_c is not None else None,
            },
        }


def decode_alarm_register(raw: int, bit_map: dict[int, str]) -> list[str]:
    """Decode bitmask register into list of active alarm names."""
    return [name for bit, name in bit_map.items() if raw & (1 << bit)]


class SUN2000Monitor:
    """Full telemetry monitor for SUN2000 + LUNA2000 system.

    Parameters:
        host:      SUN2000 inverter IP.
        port:      Modbus TCP port (default 502).
        slave_id:  Modbus slave address (default 3).
        site_id:   Site identifier for Prometheus labels.
        alert_mgr: Optional AlertManager to route hardware alarms.
    """

    def __init__(
        self,
        host: str = "192.168.1.100",
        port: int = 502,
        slave_id: int = 3,
        site_id: str = "edge",
        alert_mgr: AlertManager | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.site_id = site_id
        self.alert_mgr = alert_mgr or AlertManager(site_id)
        self._client: object | None = None

    # ------------------------------------------------------------------
    # Modbus helpers
    # ------------------------------------------------------------------

    def _read(self, address: int, count: int) -> list[int]:
        assert self._client is not None
        r = self._client.read_holding_registers(  # type: ignore
            address=address, count=count, slave=self.slave_id
        )
        if r.isError():
            raise OSError(f"read error addr={address}: {r}")
        return list(r.registers)

    @staticmethod
    def _i32(hi: int, lo: int) -> int:
        raw = (hi << 16) | lo
        return raw - (1 << 32) if raw >= (1 << 31) else raw

    @staticmethod
    def _u32(hi: int, lo: int) -> int:
        return (hi << 16) | lo

    @staticmethod
    def _i16(raw: int) -> int:
        return raw - (1 << 16) if raw >= (1 << 15) else raw

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> SUN2000Monitor:
        from pymodbus.client import ModbusTcpClient  # type: ignore
        self._client = ModbusTcpClient(self.host, port=self.port, timeout=3)
        ok = await asyncio.get_event_loop().run_in_executor(
            None, self._client.connect  # type: ignore
        )
        if not ok:
            raise ConnectionError(f"Cannot connect to {self.host}:{self.port}")
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await asyncio.get_event_loop().run_in_executor(
                None, self._client.close  # type: ignore
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def read(self) -> SUN2000Telemetry:
        """Read a full telemetry snapshot from SUN2000 + LUNA2000."""
        loop = asyncio.get_event_loop()

        def _read_all() -> SUN2000Telemetry:
            tel = SUN2000Telemetry(site_id=self.site_id)

            # State
            state_raw = self._read(REG_STATE, 1)[0]
            tel.state = InverterState.from_raw(state_raw)

            # PV strings
            pv1_v = self._read(REG_PV1_V, 1)[0] * 0.1
            pv1_i = self._i16(self._read(REG_PV1_I, 1)[0]) * 0.01
            pv2_v = self._read(REG_PV2_V, 1)[0] * 0.1
            pv2_i = self._i16(self._read(REG_PV2_I, 1)[0]) * 0.01
            tel.pv_strings = [
                PVStringData(1, pv1_v, pv1_i),
                PVStringData(2, pv2_v, pv2_i),
            ]

            # PV total power
            pv_regs = self._read(REG_PV_POWER, 2)
            tel.pv_total_power_kw = self._i32(*pv_regs) * 0.001

            # AC
            tel.ac_voltage_v = self._read(REG_AC_V, 1)[0] * 0.1
            ac_pwr_regs = self._read(REG_AC_POWER, 2)
            tel.ac_power_kw = self._i32(*ac_pwr_regs) * 0.001
            tel.ac_frequency_hz = self._read(REG_FREQ, 1)[0] * 0.01

            # Temperature
            temp_raw = self._read(REG_TEMP, 1)[0]
            tel.temperature_c = self._i16(temp_raw) * 0.1

            # Energy
            daily_regs = self._read(REG_DAILY_E, 2)
            tel.daily_energy_kwh = self._u32(*daily_regs) * 0.01
            total_regs = self._read(REG_TOTAL_E, 2)
            tel.total_energy_kwh = self._u32(*total_regs) * 0.01

            # Alarms
            a1 = self._read(REG_ALARM1, 1)[0]
            a2 = self._read(REG_ALARM2, 1)[0]
            tel.active_alarms = (
                decode_alarm_register(a1, _ALARM1_BITS) +
                decode_alarm_register(a2, _ALARM2_BITS)
            )

            # LUNA2000 (best-effort)
            try:
                soc_raw = self._read(REG_LUNA_SOC, 1)[0]
                tel.batt_soc_pct = soc_raw * 0.1
                pwr_regs = self._read(REG_LUNA_PWR, 2)
                tel.batt_power_kw = self._i32(*pwr_regs) * 0.001
                bt_raw = self._read(REG_LUNA_TEMP, 1)[0]
                tel.batt_temperature_c = self._i16(bt_raw) * 0.1
            except OSError:
                log.debug("sun2000.luna_not_connected")

            return tel

        tel = await loop.run_in_executor(None, _read_all)

        # Prometheus
        soc = tel.batt_soc_pct if tel.batt_soc_pct is not None else 0.0
        LAST_SOC_PERCENT.labels(site_id=self.site_id).set(soc)
        LAST_POWER_KW.labels(site_id=self.site_id).set(tel.ac_power_kw)

        # Route alarms
        for alarm_name in tel.active_alarms:
            level = AlertLevel.CRITICAL if "Arc" in alarm_name or "Overtemperature" in alarm_name \
                else AlertLevel.WARNING
            self.alert_mgr.fire(level, f"HW_{alarm_name.replace(' ', '_').upper()}", alarm_name)

        log.debug(
            "sun2000.read_ok",
            state=tel.state.name,
            soc=tel.batt_soc_pct,
            ac_kw=tel.ac_power_kw,
            alarms=len(tel.active_alarms),
        )
        return tel
