"""Modelo determinista de planta BESS para simulación y pruebas.

No pretende ser un modelo electroquímico: su objetivo es cerrar el lazo de
control de forma realista *para el gateway* (respuesta de primer orden del PCS a
la consigna, integración de SOC, temperatura y tensiones de celda), con puntos de
inyección de fallas (``overrides``) y de perturbaciones de red.

Convención interna: P + = descarga. Toda la física usa esa convención.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class PlantParams:
    p_nominal_kw: float = 1000.0
    e_nominal_kwh: float = 2000.0
    q_max_kvar: float = 600.0
    tau_p_s: float = 0.15            # constante de tiempo de la respuesta de P del PCS
    tau_q_s: float = 0.15
    ramp_kw_per_s: float = 1.0e9     # límite de rampa del PCS (por defecto sin límite)
    eta: float = 0.98                # rendimiento por sentido (carga y descarga)
    soc0_pct: float = 60.0
    soh_pct: float = 98.5
    cell_v_nominal: float = 3.20
    cell_imbalance_mv: float = 25.0
    ambient_c: float = 25.0
    thermal_k_c_per_kw2: float = 5.0e-6   # calentamiento ~ k * P^2
    thermal_tau_s: float = 600.0
    isolation_kohm: float = 1200.0
    v_grid_v: float = 400.0
    f_grid_hz: float = 50.0


@dataclass
class PlantModel:
    params: PlantParams = field(default_factory=PlantParams)
    t: float = 0.0
    p_setpoint_kw: float = 0.0
    q_setpoint_kvar: float = 0.0
    p_kw: float = 0.0
    q_kvar: float = 0.0
    soc_pct: float = 0.0
    cell_t_c: float = 0.0
    f_hz: float = 0.0
    v_v: float = 0.0
    # Función opcional f(t) para perfiles de frecuencia/tensión.
    f_profile: Optional[Callable[[float], float]] = None
    v_profile: Optional[Callable[[float], float]] = None
    # Sobrescrituras de medición (inyección de fallas): nombre -> valor físico.
    overrides: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        p = self.params
        self.soc_pct = p.soc0_pct
        self.cell_t_c = p.ambient_c + 1.5
        self.f_hz = p.f_grid_hz
        self.v_v = p.v_grid_v

    def tick(self, dt: float) -> None:
        p = self.params
        if dt <= 0:
            return
        self.t += dt
        if self.f_profile is not None:
            self.f_hz = self.f_profile(self.t)
        if self.v_profile is not None:
            self.v_v = self.v_profile(self.t)

        # Respuesta del PCS: primer orden + límite de rampa + límites de placa.
        target_p = max(-p.p_nominal_kw, min(p.p_nominal_kw, self.p_setpoint_kw))
        alpha = 1.0 - math.exp(-dt / p.tau_p_s) if p.tau_p_s > 0 else 1.0
        step = (target_p - self.p_kw) * alpha
        max_step = p.ramp_kw_per_s * dt
        self.p_kw += max(-max_step, min(max_step, step))
        target_q = max(-p.q_max_kvar, min(p.q_max_kvar, self.q_setpoint_kvar))
        alpha_q = 1.0 - math.exp(-dt / p.tau_q_s) if p.tau_q_s > 0 else 1.0
        self.q_kvar += (target_q - self.q_kvar) * alpha_q

        # SOC: descarga (P>0) consume energía/eta; carga (P<0) almacena energía*eta.
        e_kwh = self.p_kw * dt / 3600.0
        d_soc = (-(e_kwh / p.eta) if e_kwh > 0 else -(e_kwh * p.eta)) / p.e_nominal_kwh * 100.0
        self.soc_pct = max(0.0, min(100.0, self.soc_pct + d_soc))

        # Térmica de primer orden hacia ambient + k P^2.
        t_ss = p.ambient_c + 1.5 + p.thermal_k_c_per_kw2 * self.p_kw ** 2
        self.cell_t_c += (t_ss - self.cell_t_c) * (1.0 - math.exp(-dt / p.thermal_tau_s))

    # -- magnitudes físicas medidas (con sobrescrituras) --------------------
    def measure(self) -> dict[str, float]:
        p = self.params
        half = p.cell_imbalance_mv / 2000.0
        v_cell = p.cell_v_nominal + (self.soc_pct - 50.0) * 0.002
        m = {
            "frequency_hz": self.f_hz,
            "v_grid_v": self.v_v,
            "p_kw": self.p_kw,
            "q_kvar": self.q_kvar,
            "soc_pct": self.soc_pct,
            "soh_pct": p.soh_pct,
            "cell_v_min_v": v_cell - half,
            "cell_v_max_v": v_cell + half,
            "cell_t_max_c": self.cell_t_c,
            "cell_t_min_c": self.cell_t_c - 2.0,
            "isolation_kohm": p.isolation_kohm,
            "string_v_v": 1300.0,
            "ambient_c": p.ambient_c,
        }
        m.update(self.overrides)
        return m
