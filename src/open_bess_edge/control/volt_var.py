"""Control de tensión y potencia reactiva: Q(V), Q fijo, cosφ fijo y cosφ(P).

Convención: Q + = capacitivo (inyecta reactivos, eleva la tensión);
Q − = inductivo (absorbe reactivos, reduce la tensión).

Q(V)::

    dv        = V/Vn − 1
    dv_activo = dv ∓ banda_muerta            (0 dentro de la banda)
    Q         = −K · Qmax · dv_activo         (K en %Qmax por %V; saturado a ±Qmax)

Los límites Qmax y de capacidad del convertidor √(S² − P²) se aplican siempre
(prioridad a P). Sin lectura válida de tensión en modo Q(V) se mantiene Q
``invalid_hold_s`` y luego se anula.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from ..config import ReactiveMode

EPS = 1e-9


@dataclass(frozen=True, slots=True)
class VoltVarOutput:
    q_kvar: float
    status: str
    dv_pu: Optional[float]
    mode: str


def _interp(points: Sequence[tuple[float, float]], x: float) -> float:
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[-1][1]  # pragma: no cover


class VoltVarController:
    def __init__(
        self,
        *,
        mode: ReactiveMode = ReactiveMode.VOLT_VAR_Q_V,
        q_max_kvar: float,
        v_nominal_v: float,
        p_nominal_kw: float,
        s_max_kva: Optional[float] = None,
        deadband_pct: float = 2.0,
        slope_k_q: float = 10.0,
        fixed_q_kvar: float = 0.0,
        power_factor: float = 1.0,
        pf_excitation: str = "capacitive",
        cos_phi_p_curve: Sequence[tuple[float, float]] = ((0.0, 1.0), (1.0, 1.0)),
        cos_phi_p_excitation: str = "inductive",
        invalid_hold_s: float = 1.0,
        q_ramp_kvar_per_s: Optional[float] = None,
    ) -> None:
        if q_max_kvar < 0 or v_nominal_v <= 0 or p_nominal_kw <= 0:
            raise ValueError("parámetros de Volt/VAR inválidos")
        if not 0.0 < power_factor <= 1.0:
            raise ValueError("power_factor debe estar en (0, 1]")
        self.mode = mode
        self.q_max = float(q_max_kvar)
        self.vn = float(v_nominal_v)
        self.p_nom = float(p_nominal_kw)
        self.s_max = float(s_max_kva) if s_max_kva is not None else math.hypot(p_nominal_kw, q_max_kvar)
        self.db = deadband_pct / 100.0
        self.k = float(slope_k_q)
        self.fixed_q = float(fixed_q_kvar)
        self.pf = float(power_factor)
        self.pf_sign = 1.0 if pf_excitation == "capacitive" else -1.0
        self.curve = tuple(cos_phi_p_curve)
        self.curve_sign = 1.0 if cos_phi_p_excitation == "capacitive" else -1.0
        self.hold_s = float(invalid_hold_s)
        self.q_ramp = q_ramp_kvar_per_s
        self._t_last: Optional[float] = None
        self._t_last_valid_v: Optional[float] = None
        self._q_raw = 0.0
        self._q_out = 0.0

    def reset(self) -> None:
        self._t_last = None
        self._q_raw = 0.0
        self._q_out = 0.0

    def _q_target(self, v: Optional[float], p_kw: float, now: float) -> tuple[float, str, Optional[float]]:
        m = self.mode
        if m is ReactiveMode.DISABLED:
            return 0.0, "DISABLED", None
        if m is ReactiveMode.FIXED_Q:
            return self.fixed_q, "FIXED_Q_DISPATCH", None
        if m is ReactiveMode.POWER_FACTOR:
            return self.pf_sign * abs(p_kw) * math.tan(math.acos(self.pf)), "POWER_FACTOR", None
        if m is ReactiveMode.COS_PHI_P:
            pf = _interp(self.curve, min(1.0, abs(p_kw) / self.p_nom))
            return self.curve_sign * abs(p_kw) * math.tan(math.acos(pf)), "COS_PHI_P", None
        # Q(V)
        valid = v is not None and math.isfinite(v) and v > 0
        if not valid:
            held = self._t_last_valid_v is not None and now - self._t_last_valid_v <= self.hold_s
            return (self._q_raw, "V_INVALID_HOLD", None) if held else (0.0, "V_INVALID", None)
        self._t_last_valid_v = now
        dv = v / self.vn - 1.0  # type: ignore[operator]
        if dv > self.db + EPS:
            active, status = dv - self.db, "OVERVOLTAGE_ABSORBING_Q"
        elif dv < -(self.db + EPS):
            active, status = dv + self.db, "UNDERVOLTAGE_INJECTING_Q"
        else:
            active, status = 0.0, "VOLT_VAR_DEADBAND_IDLE"
        return -self.k * self.q_max * active, status, dv

    def update(self, now: float, v_v: Optional[float], p_kw: float) -> VoltVarOutput:
        dt = 0.0 if self._t_last is None else max(0.0, now - self._t_last)
        self._t_last = now
        q, status, dv = self._q_target(v_v, p_kw, now)
        self._q_raw = q
        q = max(-self.q_max, min(self.q_max, q))
        # Capacidad del convertidor: prioridad a P.
        q_cap = math.sqrt(max(0.0, self.s_max ** 2 - min(abs(p_kw), self.s_max) ** 2))
        q = max(-q_cap, min(q_cap, q))
        if self.q_ramp is not None:
            lim = self.q_ramp * dt
            q = self._q_out + max(-lim, min(lim, q - self._q_out))
        self._q_out = q
        return VoltVarOutput(q_kvar=q, status=status, dv_pu=dv, mode=self.mode.value)
