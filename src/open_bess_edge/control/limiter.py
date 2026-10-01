"""Aplicación final de límites de seguridad y de capacidad a la consigna P/Q."""

from __future__ import annotations

import math

from ..models import Command, SafetyVerdict


def apply_limits(
    p_kw: float,
    q_kvar: float,
    verdict: SafetyVerdict,
    *,
    s_max_kva: float,
    q_max_kvar: float,
    priority: str = "P",
) -> Command:
    """Recorta P/Q a la envolvente y círculo de capacidad.

    priority:
      * 'P': Prioridad a potencia activa (cuasiestacionario convencional).
      * 'Q': Prioridad a reactivos obligatoria ante perturbaciones de tensión (LVRT/FRT,
             NTSyCS Cap. 3-4 e IEEE 2800-2022). Subordina P a la capacidad restante P_cap = sqrt(S_max^2 - Q^2).
    Consigna no finita => 0 (fail-closed).
    """
    if not verdict.allow_output:
        return Command(0.0, 0.0, p_clipped=p_kw != 0.0, q_clipped=q_kvar != 0.0, reason="SAFETY_INTERLOCK")
    if not (math.isfinite(p_kw) and math.isfinite(q_kvar)):
        return Command(0.0, 0.0, True, True, reason="NON_FINITE_SETPOINT")

    if priority == "Q":
        q_lim = min(q_max_kvar, s_max_kva)
        q = max(-q_lim, min(q_lim, q_kvar))
        p_cap = math.sqrt(max(0.0, s_max_kva ** 2 - min(abs(q), s_max_kva) ** 2))
        p_chg = min(verdict.p_charge_max_kw, p_cap)
        p_dis = min(verdict.p_discharge_max_kw, p_cap)
        p = max(-p_chg, min(p_dis, p_kw))
    else:
        p = max(-verdict.p_charge_max_kw, min(verdict.p_discharge_max_kw, p_kw))
        q_cap = math.sqrt(max(0.0, s_max_kva ** 2 - min(abs(p), s_max_kva) ** 2))
        q_lim = min(q_max_kvar, q_cap)
        q = max(-q_lim, min(q_lim, q_kvar))

    p_clipped = abs(p - p_kw) > 1e-9
    q_clipped = abs(q - q_kvar) > 1e-9
    reason = "CLIPPED" if (p_clipped or q_clipped) else "OK"
    return Command(p, q, p_clipped, q_clipped, reason)
