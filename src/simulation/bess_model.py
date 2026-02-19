"""
src/simulation/bess_model.py
=============================
BESSAI Edge Gateway — BESS Physics Model.

Models battery degradation (Rainflow counting approximation) and
thermal dynamics for use inside the Gymnasium simulation environment.

This is a simplified model suitable for DRL pre-training. Production
deployment would use a calibrated electrochemical model per cell-type.

References:
    - Rainflow counting: ASTM E1049-85
    - SEI growth model: Pinson & Bazant (2012)
    - Thermal: first-order RC model
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class BESSPhysicsModel:
    """Battery physics model for simulation.

    Parameters:
        capacity_kwh:       Total usable energy capacity in kWh.
        max_power_kw:       Maximum charge/discharge power in kW.
        initial_soc:        Initial State of Charge (0-1).
        round_trip_eff:     Round-trip charge efficiency (default 0.92).
        degradation_rate:   Capacity fade per full equivalent cycle (default 0.0003%).
        thermal_tau_min:    Thermal time constant in minutes (default 30).
        ambient_temp_c:     Ambient temperature in °C (default 25).
        max_temp_c:         Maximum safe operating temperature (default 50).
    """

    capacity_kwh: float = 100.0
    max_power_kw: float = 50.0
    initial_soc: float = 0.5
    round_trip_eff: float = 0.92
    degradation_rate: float = 0.0003       # fraction per FEC
    thermal_tau_min: float = 30.0
    ambient_temp_c: float = 25.0
    max_temp_c: float = 50.0

    # Runtime state (reset() initialises these)
    soc: float = field(init=False)
    temp_c: float = field(init=False)
    total_throughput_kwh: float = field(init=False)
    cumulative_degradation: float = field(init=False)

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset battery state to initial conditions."""
        self.soc = self.initial_soc
        self.temp_c = self.ambient_temp_c
        self.total_throughput_kwh = 0.0
        self.cumulative_degradation = 0.0

    def step(self, power_kw: float, dt_minutes: float = 15.0) -> dict:
        """Advance simulation by dt_minutes minutes with given power command.

        Args:
            power_kw:   Commanded power in kW (+ = charge, - = discharge).
            dt_minutes: Time step duration in minutes (default: 15).

        Returns:
            dict with keys: soc, temp_c, energy_kwh, degradation, clipped_power_kw
        """
        dt_h = dt_minutes / 60.0

        # Clip power to physical limits
        clipped_power = self._clip_power(power_kw)

        # Update SOC
        if clipped_power >= 0:  # charging
            energy_in = clipped_power * dt_h * math.sqrt(self.round_trip_eff)
            self.soc += energy_in / self.capacity_kwh
        else:  # discharging
            energy_out = abs(clipped_power) * dt_h / math.sqrt(self.round_trip_eff)
            self.soc -= energy_out / self.capacity_kwh

        self.soc = max(0.0, min(1.0, self.soc))

        # Throughput tracking
        energy_kwh = abs(clipped_power) * dt_h
        self.total_throughput_kwh += energy_kwh

        # Degradation — approx Rainflow per half-cycle
        fec = energy_kwh / (2.0 * self.capacity_kwh)
        dod_penalty = abs(0.5 - self.soc)  # higher DoD = more degradation
        degradation = fec * self.degradation_rate * (1.0 + dod_penalty)
        self.cumulative_degradation += degradation

        # Thermal model — first-order RC
        heat_kw = abs(clipped_power) * 0.02  # 2% resistive heating
        dt_s = dt_minutes * 60.0
        tau_s = self.thermal_tau_min * 60.0
        self.temp_c += (heat_kw * tau_s / self.capacity_kwh - (self.temp_c - self.ambient_temp_c)) * (dt_s / tau_s)
        self.temp_c = max(self.ambient_temp_c, self.temp_c)

        return {
            "soc": self.soc,
            "temp_c": self.temp_c,
            "energy_kwh": energy_kwh,
            "degradation": degradation,
            "clipped_power_kw": clipped_power,
        }

    def _clip_power(self, power_kw: float) -> float:
        """Clip power respecting SOC limits and max power."""
        # SOC limits: 10-90% (standard BESS operating range)
        if power_kw > 0 and self.soc >= 0.90:  # charging, already full
            return 0.0
        if power_kw < 0 and self.soc <= 0.10:  # discharging, already empty
            return 0.0
        return max(-self.max_power_kw, min(self.max_power_kw, power_kw))

    @property
    def remaining_capacity_kwh(self) -> float:
        """Current usable capacity accounting for degradation."""
        return self.capacity_kwh * (1.0 - self.cumulative_degradation)

    @property
    def is_safe(self) -> bool:
        """True if battery is within safe operating envelope."""
        return self.temp_c <= self.max_temp_c and 0.05 <= self.soc <= 0.95
