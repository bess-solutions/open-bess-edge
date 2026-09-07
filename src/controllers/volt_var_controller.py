#!/usr/bin/env python3
"""
open-bess-edge/src/controllers/volt_var_controller.py
==============================================================================
Volt/VAR & Reactive Power Controller (NTSyCS Cap. 3)
==============================================================================
Control dinámico de potencia reactiva Q(V) y factor de potencia para
soporte de tensión en el punto de conexión (PCC) según el Código de Red SEN.
==============================================================================
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any


class ReactiveControlMode(str, Enum):
    VOLT_VAR_Q_V = "VOLT_VAR_Q_V"
    FIXED_Q = "FIXED_Q"
    POWER_FACTOR = "POWER_FACTOR"


class VoltVarController:
    """
    Controlador de tensión y potencia reactiva dinámico para convertidores BESS.
    Implementa la curva característica Q(V) según exigencias de la NTSyCS.
    """

    def __init__(
        self,
        q_max_kvar: float = 600.0,
        v_nominal_v: float = 400.0,
        deadband_pct: float = 2.0,  # +/- 2% de banda muerta en tensión
        slope_k_q: float = 10.0,  # Pendiente de estatismo reactivo (% Qmax / % V)
        mode: ReactiveControlMode = ReactiveControlMode.VOLT_VAR_Q_V,
    ):
        self.q_max_kvar = q_max_kvar
        self.v_nominal_v = v_nominal_v
        self.deadband_pu = deadband_pct / 100.0
        self.slope_k_q = slope_k_q
        self.mode = mode

        self.last_execution_time: float = time.monotonic()
        self.last_q_kvar: float = 0.0

    def compute_reactive_power(
        self,
        v_measured_v: float,
        p_actual_kw: float = 0.0,
        target_cos_phi: float = 1.0,
        fixed_q_setpoint_kvar: float = 0.0,
    ) -> tuple[float, dict[str, Any]]:
        """
        Calcula la consigna de potencia reactiva según el modo operativo.
        Convención de signos:
            + Q : Inyección de reactivos capacitivos (eleva la tensión ante baja tensión).
            - Q : Absorción de reactivos inductivos (reduce la tensión ante sobretensión).
        """
        now = time.monotonic()
        dt_ms = (now - self.last_execution_time) * 1000.0
        self.last_execution_time = now

        v_pu = v_measured_v / self.v_nominal_v
        dv_pu = v_pu - 1.0

        q_target_kvar = 0.0
        status = "NORMAL"

        if self.mode == ReactiveControlMode.VOLT_VAR_Q_V:
            # Evaluación de banda muerta
            active_dv_pu = 0.0
            if dv_pu > self.deadband_pu:
                active_dv_pu = dv_pu - self.deadband_pu
                status = "OVERVOLTAGE_ABSORBING_Q"
            elif dv_pu < -self.deadband_pu:
                active_dv_pu = dv_pu + self.deadband_pu
                status = "UNDERVOLTAGE_INJECTING_Q"
            else:
                status = "VOLT_VAR_DEADBAND_IDLE"

            # Curva Q(V): Q = - K_q * Q_max * active_dv_pu
            q_target_kvar = -(self.slope_k_q * self.q_max_kvar * active_dv_pu)

        elif self.mode == ReactiveControlMode.FIXED_Q:
            q_target_kvar = fixed_q_setpoint_kvar
            status = "FIXED_Q_DISPATCH"

        elif self.mode == ReactiveControlMode.POWER_FACTOR:
            # Q = P * tan(acos(cos_phi))
            cos_phi = max(0.8, min(1.0, abs(target_cos_phi)))
            import math

            tan_phi = math.tan(math.acos(cos_phi))
            # Si target_cos_phi negativo, modo inductivo
            sign = 1.0 if target_cos_phi >= 0 else -1.0
            q_target_kvar = abs(p_actual_kw) * tan_phi * sign
            status = "COS_PHI_REGULATION"

        # Saturación a capacidad máxima de convertidor Qmax
        approved_q = max(-self.q_max_kvar, min(self.q_max_kvar, q_target_kvar))
        self.last_q_kvar = approved_q

        telemetry = {
            "v_measured_v": v_measured_v,
            "v_pu": v_pu,
            "dv_pu": dv_pu,
            "mode": self.mode.value,
            "status": status,
            "q_target_kvar": approved_q,
            "q_max_kvar": self.q_max_kvar,
            "execution_dt_ms": dt_ms,
        }

        return approved_q, telemetry
