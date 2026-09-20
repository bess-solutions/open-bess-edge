"""Aplicación final de límites de seguridad y de capacidad a la consigna P/Q."""

from __future__ import annotations

import math

from ..models import Command, SafetyVerdict


def apply_limits(p_kw: float, q_kvar: float, verdict: SafetyVerdict, *, s_max_kva: float, q_max_kvar: float) -> Command:
    """Recorta P/Q a la envolvente. Consigna no finita => 0 (fail-closed)."""
    if not verdict.allow_output:
        return Command(0.0, 0.0, p_clipped=p_kw != 0.0, q_clipped=q_kvar != 0.0, reason="SAFETY_INTERLOCK")
    if not (math.isfinite(p_kw) and math.isfinite(q_kvar)):
        return Command(0.0, 0.0, True, True, reason="NON_FINITE_SETPOINT")
    p = max(-verdict.p_charge_max_kw, min(verdict.p_discharge_max_kw, p_kw))
    q_cap = math.sqrt(max(0.0, s_max_kva ** 2 - min(abs(p), s_max_kva) ** 2))
    q_lim = min(q_max_kvar, q_cap)
    q = max(-q_lim, min(q_lim, q_kvar))
    p_clipped = abs(p - p_kw) > 1e-9
    q_clipped = abs(q - q_kvar) > 1e-9
    reason = "CLIPPED" if (p_clipped or q_clipped) else "OK"
    return Command(p, q, p_clipped, q_clipped, reason)
