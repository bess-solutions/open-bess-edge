"""Tipos de datos compartidos entre driver, envolvente de seguridad y control."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


def finite(x: Optional[float]) -> bool:
    """True si ``x`` es un número real finito (rechaza None, NaN e inf)."""
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


@dataclass(frozen=True, slots=True)
class Telemetry:
    """Instantánea de telemetría en convención interna (ver ``open_bess_edge``).

    Un campo ``None`` significa *no disponible o inválido*; nunca se rellena con
    un valor "razonable". ``invalid`` lista las señales que se leyeron pero
    fueron descartadas por no ser finitas o por estar fuera de rango físico.
    """

    t_mono: float                      # instante de adquisición (reloj monotónico)
    t_wall: float                      # instante de adquisición (epoch, sólo para registro)
    frequency_hz: Optional[float] = None
    v_grid_v: Optional[float] = None
    p_kw: Optional[float] = None
    q_kvar: Optional[float] = None
    soc_pct: Optional[float] = None
    soh_pct: Optional[float] = None
    cell_v_min_v: Optional[float] = None
    cell_v_max_v: Optional[float] = None
    cell_t_max_c: Optional[float] = None
    cell_t_min_c: Optional[float] = None
    isolation_kohm: Optional[float] = None
    string_v_v: Optional[float] = None
    ambient_c: Optional[float] = None
    p_grid_kw: Optional[float] = None   # potencia neta en el PCC: + importación, - exportación
    invalid: tuple[str, ...] = ()

    def age_s(self, now_mono: float) -> float:
        return max(0.0, now_mono - self.t_mono)


class NodeState(str, Enum):
    INIT = "INIT"
    STARTING = "STARTING"          # validando telemetría, salida forzada a 0
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"          # pérdida de datos dentro de la ventana de retención
    SAFE_STATE = "SAFE_STATE"      # salida en 0 por pérdida de datos/escritura
    TRIPPED = "TRIPPED"            # disparo de seguridad enclavado
    MONITOR_ONLY = "MONITOR_ONLY"  # sin capacidad de control (perfil sólo lectura)
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"            # alarma sin recorte
    DERATE = "DERATE"              # recorte de potencia
    TRIP = "TRIP"                  # salida a 0 (enclavada)
    DATA = "DATA"                  # dato inválido: salida a 0 (no enclavada)


@dataclass(frozen=True, slots=True)
class Fault:
    code: str
    name: str
    severity: Severity
    detail: str = ""
    latched: bool = False


@dataclass(frozen=True, slots=True)
class SafetyVerdict:
    """Resultado de un ciclo de evaluación de la envolvente de seguridad."""

    faults: tuple[Fault, ...]
    allow_output: bool              # False => consigna forzada a 0 kW / 0 kvar
    p_discharge_max_kw: float       # >= 0, límite de inyección permitido
    p_charge_max_kw: float          # >= 0, límite de absorción permitido (magnitud)
    derate_factor: float            # 1.0 = sin recorte
    tripped: bool

    @property
    def status(self) -> str:
        if self.tripped:
            return "CRITICAL_TRIP"
        if any(f.severity is Severity.DATA for f in self.faults):
            return "DATA_FAULT"
        if any(f.severity is Severity.DERATE for f in self.faults):
            return "DERATED"
        if self.faults:
            return "WARNING"
        return "SAFE_NORMAL"

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(f.code for f in self.faults)


@dataclass(frozen=True, slots=True)
class Command:
    """Consigna final (post-límites) en convención interna."""

    p_kw: float
    q_kvar: float
    p_clipped: bool = False
    q_clipped: bool = False
    reason: str = "OK"


@dataclass(slots=True)
class WriteResult:
    ok: bool
    detail: str = ""
    verified: Optional[bool] = None   # None = no se intentó verificar
    latency_ms: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)
