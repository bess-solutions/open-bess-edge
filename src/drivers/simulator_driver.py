"""
src/drivers/simulator_driver.py
================================
BESSAI Edge Gateway — SimulatorDriver (Sim-First DataProvider).

Drop-in replacement for ModbusDriver that generates synthetic BESS
telemetry without any hardware or network connection.

Design goals
------------
- **Realistic physics**: SOC drifts based on simulated power flow.
  Temperature follows SOC. Cycle count increments on charge/discharge reversal.
- **Per-profile config**: reads the same JSON profile used by ModbusDriver,
  so tag names are identical and the swap is transparent.
- **Configurable modes**: ``NORMAL``, ``STRESS`` (high cycles, hot), ``FAULT``
  (triggers AI-IDS alarms), ``IDLE`` (steady state, no action).
- **No external deps**: only stdlib + numpy (already in requirements.txt).

Usage::

    driver = SimulatorDriver(profile="huawei_sun2000", mode="normal")
    await driver.connect()
    soc = await driver.read_tag("luna_soc")    # → float, e.g. 72.3
    await driver.write_tag("luna_working_mode", 3)  # → no-op, logged

Environment variable::

    BESSAI_MODE=demo       → main.py picks SimulatorDriver automatically
    BESSAI_SIM_MODE=stress → sets SimulatorDriver.mode at runtime
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

import structlog

from src.drivers.base import DataProviderError

__all__ = ["SimulatorDriver", "SimMode"]

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Simulation modes
# ---------------------------------------------------------------------------


class SimMode:
    """Simulation scenario presets."""

    NORMAL = "normal"  # typical BESS day — charge at night, discharge at peak
    STRESS = "stress"  # high thermal, rapid cycling (tests AI-IDS)
    FAULT = "fault"  # anomalous values — triggers AI-IDS alarm
    IDLE = "idle"  # steady state: SOC=80%, power=0, temp=25°C


# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------

_TICK_S = 5.0  # simulated seconds per real second
_CAPACITY_KWH = 200.0  # nominal BESS capacity (kWh) — configurable
_MAX_POWER_KW = 100.0  # peak charge/discharge power (kW)
_ETA_CHG = 0.96  # round-trip charge efficiency
_ETA_DIS = 0.96  # round-trip discharge efficiency

# Typical daily dispatch schedule: hour → power fraction (-1=discharge, +1=charge)
_NORMAL_SCHEDULE: dict[int, float] = {
    0: 0.8,
    1: 0.9,
    2: 0.9,
    3: 0.9,
    4: 0.5,
    5: 0.0,  # night: charge
    6: 0.0,
    7: -0.3,
    8: -0.6,
    9: -0.8,  # morning peak: discharge
    10: -0.5,
    11: -0.3,
    12: 0.3,
    13: 0.5,
    14: 0.3,
    15: -0.3,  # midday solar
    16: -0.5,
    17: -0.8,
    18: -0.9,
    19: -0.7,
    20: -0.4,
    21: -0.2,  # evening peak
    22: 0.4,
    23: 0.7,  # late night: charge
}


class SimulatorDriver:
    """
    Synthetic BESS data provider.

    Implements the ``DataProvider`` protocol — can be used anywhere
    ``ModbusDriver`` or ``UniversalDriver`` is expected.

    Parameters
    ----------
    profile:
        Device profile name (without .json), e.g. ``"huawei_sun2000"`` or
        ``"victron_multiplus2"``. Used to resolve valid tag names.
    mode:
        Simulation scenario: ``"normal"``, ``"stress"``, ``"fault"``, ``"idle"``.
        Can also be set via ``BESSAI_SIM_MODE`` env variable.
    initial_soc:
        Starting State of Charge in percent (0–100). Default: 65.0.
    capacity_kwh:
        Simulated BESS capacity in kWh. Default: 200.0.
    registry_dir:
        Path to the registry/ directory containing device profile JSONs.
    """

    def __init__(
        self,
        profile: str = "huawei_sun2000",
        mode: str | None = None,
        initial_soc: float = 65.0,
        capacity_kwh: float = _CAPACITY_KWH,
        registry_dir: str | Path = "registry",
    ) -> None:
        self._profile_name = profile
        self._mode = (mode or os.getenv("BESSAI_SIM_MODE") or SimMode.NORMAL).lower()
        self._capacity_kwh = capacity_kwh
        self._registry_dir = Path(registry_dir)

        # Physics state
        self._soc: float = initial_soc  # %
        self._power_kw: float = 0.0  # kW (+charge, -discharge)
        self._temp_c: float = 25.0 + random.uniform(-3, 3)  # °C
        self._voltage: float = 48.0 * (0.8 + initial_soc / 500)  # V
        self._current: float = 0.0  # A
        self._cycle_count: int = random.randint(50, 500)
        self._last_power_sign: float = 0.0  # for cycle counting
        self._daily_energy_kwh: float = 0.0
        self._total_energy_kwh: float = random.uniform(5000, 50000)
        self._ac_power_w: float = 0.0
        self._ac_voltage_v: float = 230.0 + random.uniform(-5, 5)
        self._frequency_hz: float = 50.0

        # Timing
        self._connected: bool = False
        self._start_ts: float = time.time()
        self._last_tick_ts: float = time.time()
        self._grid_relay: int = 51  # 51=closed

        # Load profile tags
        self._tags: dict[str, dict] = {}
        self._writable: set[str] = set()
        self._load_profile()

    # -----------------------------------------------------------------------
    # Profile loading
    # -----------------------------------------------------------------------

    def _load_profile(self) -> None:
        profile_path = self._registry_dir / f"{self._profile_name}.json"
        if not profile_path.exists():
            log.warning(
                "simulator.profile_not_found",
                profile=self._profile_name,
                path=str(profile_path),
            )
            return
        with profile_path.open() as f:
            data = json.load(f)
        self._tags = data.get("registers", {})
        self._writable = {k for k, v in self._tags.items() if v.get("access") == "RW"}
        log.info(
            "simulator.profile_loaded",
            profile=self._profile_name,
            tags=len(self._tags),
            writable=len(self._writable),
        )

    # -----------------------------------------------------------------------
    # DataProvider protocol implementation
    # -----------------------------------------------------------------------

    async def connect(self) -> None:
        await asyncio.sleep(0.05)  # simulate handshake latency
        self._connected = True
        self._start_ts = time.time()
        log.info(
            "simulator.connected",
            profile=self._profile_name,
            mode=self._mode,
            soc=round(self._soc, 1),
        )

    async def disconnect(self) -> None:
        self._connected = False
        log.info("simulator.disconnected", profile=self._profile_name)

    async def read_tag(self, tag_name: str) -> float:
        if not self._connected:
            raise DataProviderError("SimulatorDriver not connected — call connect() first")
        self._tick()
        value = self._read_value(tag_name)
        await asyncio.sleep(0.001)  # simulate Modbus RTT
        return value

    async def write_tag(self, tag_name: str, value: float) -> None:
        if not self._connected:
            raise DataProviderError("SimulatorDriver not connected")
        if tag_name not in self._writable and self._tags:
            log.warning("simulator.write_readonly", tag=tag_name)
        log.debug("simulator.write_tag", tag=tag_name, value=value)
        # Apply writable commands that affect simulation state
        if tag_name in ("luna_charge_target_soc", "storage_minimum_soc", "minimum_soc"):
            pass  # noted but no physics effect in sim
        if tag_name in ("luna_working_mode", "operating_mode", "storage_control_mode"):
            pass  # mode changes acknowledged
        if tag_name in ("ess_setpoint", "storage_setpoint_power", "active_power_limit"):
            self._power_kw = max(-_MAX_POWER_KW, min(_MAX_POWER_KW, value / 1000.0))
        await asyncio.sleep(0.001)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def source_description(self) -> str:
        return f"Simulator[{self._profile_name}][{self._mode}]"

    # -----------------------------------------------------------------------
    # Physics simulation
    # -----------------------------------------------------------------------

    def _tick(self) -> None:
        """Advance physics simulation since last tick."""
        now = time.time()
        elapsed_real = now - self._last_tick_ts
        self._last_tick_ts = now

        # Simulated time advances faster in stress mode
        sim_elapsed_s = elapsed_real * _TICK_S

        if self._mode == SimMode.IDLE:
            self._power_kw = 0.0
        elif self._mode == SimMode.FAULT:
            # Anomalous: temperature spike + random power
            self._temp_c = 58.0 + random.uniform(0, 10)
            self._power_kw = random.uniform(-_MAX_POWER_KW, _MAX_POWER_KW)
        elif self._mode == SimMode.STRESS:
            # Aggressive cycling
            hour_phase = (time.time() % 600) / 600  # 10-min fast cycle
            self._power_kw = _MAX_POWER_KW * math.sin(2 * math.pi * hour_phase)
        else:
            # Normal: follow daily schedule
            hour = int(time.gmtime(time.time() - 10800).tm_hour)  # Chile UTC-3
            fraction = _NORMAL_SCHEDULE.get(hour, 0.0)
            self._power_kw = _MAX_POWER_KW * fraction * (1 + random.uniform(-0.05, 0.05))

        # Clamp power
        self._power_kw = max(-_MAX_POWER_KW, min(_MAX_POWER_KW, self._power_kw))

        # SOC physics: ΔE = P × Δt / capacity
        if self._power_kw > 0:  # charging
            d_soc = (self._power_kw * _ETA_CHG * sim_elapsed_s / 3600) / self._capacity_kwh * 100
        else:  # discharging
            d_soc = (self._power_kw / _ETA_DIS * sim_elapsed_s / 3600) / self._capacity_kwh * 100

        self._soc = max(5.0, min(98.0, self._soc + d_soc))

        # Temperature: follows SOC and power (higher activity = higher temp)
        target_temp = 25.0 + abs(self._power_kw) / _MAX_POWER_KW * 18.0
        if self._mode != SimMode.FAULT:
            self._temp_c += (target_temp - self._temp_c) * 0.02 + random.uniform(-0.2, 0.2)
            self._temp_c = max(20.0, min(55.0, self._temp_c))

        # Voltage: linear with SOC (rough approximation)
        self._voltage = 400.0 + (self._soc - 50) * 1.6 + random.uniform(-2, 2)

        # Current: I = P / V
        if self._voltage > 0:
            self._current = (self._power_kw * 1000) / self._voltage

        # AC power
        self._ac_power_w = -self._power_kw * 1000 * 0.98  # inverter loss ~2%

        # Cycle count: increment on power direction reversal
        current_sign = 1.0 if self._power_kw > 5 else (-1.0 if self._power_kw < -5 else 0.0)
        if (
            current_sign != 0
            and self._last_power_sign != 0
            and current_sign != self._last_power_sign
        ):
            self._cycle_count += 1
        if current_sign != 0:
            self._last_power_sign = current_sign

        # Energy counters
        energy_kwh = abs(self._power_kw) * sim_elapsed_s / 3600
        self._daily_energy_kwh += energy_kwh if self._power_kw > 0 else 0
        self._total_energy_kwh += energy_kwh

    def _read_value(self, tag_name: str) -> float:
        """Map tag names to current simulation state values."""

        def noise(s=0.5):
            return random.uniform(-s, s)

        mapping: dict[str, float] = {
            # State of charge / health
            "luna_soc": self._soc + noise(0.1),
            "battery_soc": self._soc + noise(0.1),
            "luna_soh": 97.5 - self._cycle_count * 0.008 + noise(0.1),
            "battery_soh": 97.5 - self._cycle_count * 0.008 + noise(0.1),
            # Power — battery side
            "luna_power": self._power_kw + noise(0.05),
            "battery_power": self._power_kw * 1000 + noise(50),  # W for some profiles
            "pv_power": max(0.0, random.gauss(15, 3)),  # kW solar
            # Voltage & current
            "luna_voltage": self._voltage + noise(2),
            "battery_voltage": self._voltage + noise(2),
            "luna_current": self._current + noise(0.5),
            "battery_current": self._current + noise(0.5),
            # Temperature
            "luna_temperature": self._temp_c + noise(0.2),
            "battery_temperature": self._temp_c + noise(0.2),
            "internal_temperature": self._temp_c - 3 + noise(0.5),  # inverter cooler
            # AC grid side
            "active_power": self._ac_power_w / 1000 + noise(0.02),  # kW
            "ac_power_total": self._ac_power_w + noise(10),  # W
            "ac_voltage": self._ac_voltage_v + noise(0.5),
            "ac_voltage_l1": self._ac_voltage_v + noise(0.5),
            "ac_voltage_l2": self._ac_voltage_v + noise(0.5),
            "ac_voltage_l3": self._ac_voltage_v + noise(0.5),
            "ac_current": abs(self._current) * 0.7 + noise(0.1),
            "ac_current_total": abs(self._current) * 0.7 + noise(0.1),
            "grid_frequency": self._frequency_hz + noise(0.02),
            "frequency": self._frequency_hz + noise(0.02),
            "grid_power": self._ac_power_w + noise(20),  # W
            # DC input
            "dc_power": abs(self._power_kw) * 1000 * 1.02,
            "dc_voltage": self._voltage * 2.5 + noise(5),
            "pv_total_power": max(0.0, random.gauss(12, 2)),  # kW
            "pv1_voltage": 280 + noise(5),
            "pv1_current": max(0.0, random.gauss(8, 1)),
            "pv2_voltage": 280 + noise(5),
            "pv2_current": max(0.0, random.gauss(8, 1)),
            # Power factor
            "power_factor": 0.98 + noise(0.01),
            "reactive_power": noise(5),
            # Capacity & energy
            "luna_capacity": self._capacity_kwh * 0.95,
            "battery_charge_total": self._total_energy_kwh * 3600,  # Wh total charge
            "battery_discharge_total": self._total_energy_kwh * 3600,
            "daily_energy": self._daily_energy_kwh,
            "total_energy": self._total_energy_kwh,
            # Cycles
            "luna_cycle_count": float(self._cycle_count),
            # State / status (enums as floats)
            "inverter_state": 1392.0 if self._mode != SimMode.FAULT else 307.0,  # SMA: 1392=OK
            "device_status": 1392.0 if self._mode != SimMode.FAULT else 307.0,
            "battery_status": 3.0 if self._power_kw > 0 else 2.0,  # 3=charging, 2=discharging
            "grid_relay_status": 51.0,  # 51=closed
            # AC output (Victron / off-grid)
            "ac_output_voltage": self._ac_voltage_v + noise(0.3),
            "ac_output_current": abs(self._current) * 0.6 + noise(0.1),
            "ac_output_power": abs(self._ac_power_w) * 0.8 + noise(20),
            "ac_input_voltage": self._ac_voltage_v + noise(1),
            "ac_input_current": abs(self._current) * 0.3 + noise(0.1),
            "ac_input_power": self._ac_power_w * 0.5 + noise(30),
            # Victron specifics
            "battery_consumed_ah": max(0.0, (100 - self._soc) * self._capacity_kwh * 10 / 48),
            "time_to_go": max(
                0.0, self._soc / 100 * self._capacity_kwh / max(0.1, abs(self._power_kw))
            ),
            "ess_setpoint": self._power_kw * 1000,
            "minimum_soc": 10.0,
            # Alarms (0 = no alarm)
            "alarm1": 0.0 if self._mode != SimMode.FAULT else 16.0,
            "alarm2": 0.0 if self._mode != SimMode.FAULT else 512.0,
            "alarm3": 0.0,
            "vebus_error": 0.0,
            # Watchdog / heartbeat (read back what was last written)
            "watchdog_heartbeat": 1.0,
            # Control registers (readable current setpoints)
            "luna_working_mode": 2.0,  # TOU
            "luna_charge_target_soc": 90.0,
            "operating_mode": 1467.0,
            "storage_control_mode": 1.0,  # Auto
            "storage_setpoint_power": self._power_kw * 1000,
            "storage_minimum_soc": 10.0,
            "active_power_limit": _MAX_POWER_KW * 1000,
        }

        if tag_name not in mapping:
            if tag_name in self._tags:
                # Unknown tag but exists in profile — return plausible default
                log.debug("simulator.unknown_tag_default", tag=tag_name)
                return 0.0
            raise DataProviderError(
                f"SimulatorDriver: tag '{tag_name}' is not in profile '{self._profile_name}'"
            )

        return round(mapping[tag_name], 4)

    # -----------------------------------------------------------------------
    # Factory helpers
    # -----------------------------------------------------------------------

    @classmethod
    def for_profile(cls, profile: str, **kwargs: Any) -> SimulatorDriver:
        """Convenience factory. ``SimulatorDriver.for_profile("sma_sunny_tripower")``."""
        return cls(profile=profile, **kwargs)
