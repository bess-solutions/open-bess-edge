"""Control primario de frecuencia (estatismo) y respuesta rápida FFR.

Modelo (convención interna, P + = descarga)::

    Δf         = f − f0
    Δf_activo  = Δf ∓ banda_muerta   (0 dentro de la banda muerta)
    ΔP_droop   = −(P_nom / (s · f0)) · Δf_activo
    P_objetivo = P_base_rampeada + ΔP_droop        (saturado a ±P_nom)

Diferencias de diseño respecto de la versión 2.x (documentadas en
``docs/spec/CONTROL.md``):

* ``P_base`` es la **consigna de despacho** (programa/AGC), *nunca* la potencia
  medida. Usar la medida como base creaba un integrador (la consigna crecía en
  cada ciclo mientras persistiera la desviación de frecuencia).
* La rampa (≤ X % Pn/min) se aplica al **cambio de la base** (régimen
  cuasiestacionario); la componente droop responde sin rampa, ya que es la
  respuesta a un evento de frecuencia.
* Alivio instantáneo simétrico: en subfrecuencia se anula de inmediato una base
  de *carga*; en sobrefrecuencia se anula de inmediato una base de *descarga*.
* Sin lectura válida de frecuencia, la componente droop se mantiene
  ``freq_invalid_hold_s`` y luego se anula (estado ``FREQ_INVALID``).
* El reloj es explícito (``now``): el controlador es determinista y testeable.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

EPS = 1e-9
MAX_PLAUSIBLE_DF_HZ = 5.0


@dataclass(frozen=True, slots=True)
class FFROutput:
    p_kw: float
    p_base_kw: float
    p_droop_kw: float
    status: str
    df_hz: Optional[float]
    active_df_hz: float
    gain_kw_per_hz: float
    contingency: bool
    load_relief: bool


@dataclass
class ContingencyRecord:
    """Registro de auditoría de un evento de contingencia (aporte @10 s y @2 min)."""

    start_mono: float
    start_wall: float
    direction: str                     # "UNDERFREQUENCY" | "OVERFREQUENCY"
    p_pre_kw: float
    f_extreme_hz: float
    aporte_10s_kw: Optional[float] = None
    aporte_2min_kw: Optional[float] = None
    end_mono: Optional[float] = None
    reported: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_wall": self.start_wall,
            "direction": self.direction,
            "p_pre_kw": self.p_pre_kw,
            "f_extreme_hz": self.f_extreme_hz,
            "aporte_10s_kw": self.aporte_10s_kw,
            "aporte_2min_kw": self.aporte_2min_kw,
            "duration_s": None if self.end_mono is None else self.end_mono - self.start_mono,
        }


class FFRDroopController:
    def __init__(
        self,
        p_nominal_kw: float,
        f_nominal_hz: float = 50.0,
        droop_r: float = 0.03,
        deadband_hz: float = 0.03,
        contingency_threshold_hz: float = 0.30,
        ramp_pct_per_min: float = 20.0,
        freq_invalid_hold_s: float = 1.0,
        enabled: bool = True,
    ) -> None:
        if not (math.isfinite(p_nominal_kw) and p_nominal_kw > 0):
            raise ValueError("p_nominal_kw debe ser > 0")
        if not 0.0 < droop_r <= 1.0:
            raise ValueError(f"Droop {droop_r} fuera de límites (0 < s <= 1)")
        if deadband_hz < 0 or contingency_threshold_hz <= deadband_hz:
            raise ValueError("se exige 0 <= banda muerta < umbral de contingencia")
        if ramp_pct_per_min <= 0:
            raise ValueError("ramp_pct_per_min debe ser > 0")
        self.p_nom = float(p_nominal_kw)
        self.f0 = float(f_nominal_hz)
        self.s = float(droop_r)
        self.db = float(deadband_hz)
        self.thr = float(contingency_threshold_hz)
        self.ramp_kw_s = ramp_pct_per_min / 100.0 * self.p_nom / 60.0
        self.hold_s = float(freq_invalid_hold_s)
        self.enabled = enabled
        self.gain = self.p_nom / (self.s * self.f0)

        self._t_last: Optional[float] = None
        self._base = 0.0
        self._droop = 0.0
        self._last_valid_f_t: Optional[float] = None
        self._contingency = False
        self._last_out = 0.0
        self._applied_last = 0.0
        self.record: Optional[ContingencyRecord] = None
        self.history: deque[ContingencyRecord] = deque(maxlen=200)

    # ------------------------------------------------------------------
    def reset(self, base_kw: float = 0.0) -> None:
        """Reinicia estado interno (p. ej. tras SAFE_STATE): parte de ``base_kw`` con droop 0."""
        self._t_last = None
        self._base = base_kw
        self._droop = 0.0
        self._last_out = base_kw
        self._applied_last = base_kw

    def _active_df(self, df: float) -> float:
        if df > self.db + EPS:
            return df - self.db
        if df < -(self.db + EPS):
            return df + self.db
        return 0.0

    def update(self, now: float, f_hz: Optional[float], p_base_kw: float, *, wall: float = 0.0) -> FFROutput:
        dt = 0.0 if self._t_last is None else max(0.0, now - self._t_last)
        self._t_last = now

        # ---- base de despacho con rampa (cuasiestacionario) ------------
        step = self.ramp_kw_s * dt
        delta = p_base_kw - self._base
        self._base += max(-step, min(step, delta)) if dt > 0 else 0.0
        if dt == 0.0 and self._base == 0.0 and p_base_kw == 0.0:
            self._base = 0.0

        # ---- frecuencia -------------------------------------------------
        valid = (
            f_hz is not None and isinstance(f_hz, (int, float)) and math.isfinite(f_hz)
            and abs(f_hz - self.f0) <= MAX_PLAUSIBLE_DF_HZ
        )
        load_relief = False
        status: str
        df: Optional[float] = None
        active_df = 0.0

        if not self.enabled:
            self._droop = 0.0
            status = "DISABLED"
        elif valid:
            df = float(f_hz) - self.f0  # type: ignore[arg-type]
            active_df = self._active_df(df)
            self._last_valid_f_t = now
            self._droop = max(-self.p_nom, min(self.p_nom, -self.gain * active_df))
            # Alivio instantáneo simétrico de la base
            if active_df < 0 and self._base < 0:
                self._base, load_relief = 0.0, True
            elif active_df > 0 and self._base > 0:
                self._base, load_relief = 0.0, True
            # Máquina de estados de contingencia (histéresis: sale al volver a banda muerta)
            if abs(df) >= self.thr - EPS:
                if not self._contingency:
                    self._begin_contingency(now, wall, df)
                self._contingency = True
                self._track_extreme(df)
            elif abs(df) <= self.db + EPS:
                if self._contingency:
                    self._end_contingency(now)
                self._contingency = False
            status = ("FFR_CONTINGENCY" if self._contingency
                      else "PRIMARY_DROOP_ACTIVE" if active_df != 0.0 else "IDLE_DEADBAND")
        else:
            held = (self._last_valid_f_t is not None and now - self._last_valid_f_t <= self.hold_s)
            if held:
                status = "FREQ_INVALID_HOLD"
            else:
                self._droop = 0.0
                status = "FREQ_INVALID"

        p = max(-self.p_nom, min(self.p_nom, self._base + self._droop))
        self._last_out = p
        self._update_aporte(now)
        return FFROutput(
            p_kw=p, p_base_kw=self._base, p_droop_kw=self._droop, status=status, df_hz=df,
            active_df_hz=active_df, gain_kw_per_hz=self.gain,
            contingency=self._contingency, load_relief=load_relief,
        )

    # ------------------------------------------------------------------
    # Auditoría de contingencias
    # ------------------------------------------------------------------
    def observe_applied(self, p_applied_kw: float) -> None:
        """Informa la consigna *finalmente aplicada* (post límites) para medir el aporte."""
        self._applied_last = p_applied_kw

    def _begin_contingency(self, now: float, wall: float, df: float) -> None:
        self.record = ContingencyRecord(
            start_mono=now, start_wall=wall,
            direction="UNDERFREQUENCY" if df < 0 else "OVERFREQUENCY",
            p_pre_kw=self._applied_last, f_extreme_hz=self.f0 + df,
        )

    def _track_extreme(self, df: float) -> None:
        r = self.record
        if r is None:
            return
        if (df < 0 and self.f0 + df < r.f_extreme_hz) or (df > 0 and self.f0 + df > r.f_extreme_hz):
            r.f_extreme_hz = self.f0 + df

    def _update_aporte(self, now: float) -> None:
        r = self.record
        if r is None or r.end_mono is not None:
            return
        el = now - r.start_mono
        if r.aporte_10s_kw is None and el >= 10.0:
            r.aporte_10s_kw = self._applied_last - r.p_pre_kw
        if r.aporte_2min_kw is None and el >= 120.0:
            r.aporte_2min_kw = self._applied_last - r.p_pre_kw

    def _end_contingency(self, now: float) -> None:
        r = self.record
        if r is not None:
            r.end_mono = now
            self.history.append(r)
        self.record = None

    def pop_finished(self) -> list[ContingencyRecord]:
        out = [r for r in self.history if not r.reported]
        for r in out:
            r.reported = True
        return out
