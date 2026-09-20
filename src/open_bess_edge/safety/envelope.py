"""Envolvente de seguridad BESS-GUARD (evaluación determinista, *fail-closed*).

Códigos de guarda
-----------------
======================  =========  ================================================
Código                  Severidad  Condición
======================  =========  ================================================
BESS-GUARD-001          TRIP       Subtensión de celda (V_min < límite)
BESS-GUARD-002          TRIP       Sobretensión de celda (V_max > límite)
BESS-GUARD-003          TRIP       Sobretemperatura de celda (T_max > límite)
BESS-GUARD-004          TRIP       Falla de aislamiento DC (R_iso < límite)
BESS-GUARD-005          WARNING    Desbalance entre celdas (ΔV > límite)
BESS-GUARD-006          DERATE     Temperatura de celda alta (recorte 50 %)
BESS-GUARD-007          DERATE     Temperatura de celda baja (inhibe carga)
BESS-GUARD-008          TRIP       Tensión de string fuera de ventana (si hay señal)
BESS-GUARD-009          DERATE     Temperatura ambiente alta (recorte 50 %)
BESS-GUARD-010          DERATE     SOC en límite: inhibe descarga (≤ min) o carga (≥ max)
BESS-GUARD-020/021      WARNING    Frecuencia / tensión de red fuera de umbral de alarma
BESS-GUARD-090          DATA       Señal requerida ausente, no finita o implausible
======================  =========  ================================================

Reglas:
* Los disparos (TRIP) se **enclavan**: sólo se liberan con ``reset_trips`` y
  únicamente si las condiciones están despejadas con histéresis (o tras
  ``timing.auto_reset_after_s`` si está configurado).
* Un dato requerido inválido fuerza salida 0 (fail-closed) y se recupera tras
  ``timing.recovery_valid_cycles`` ciclos consecutivos válidos.
* La comparación con NaN nunca "pasa": un NaN es dato inválido, no valor seguro.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from ..config import PlantConfig
from ..models import Fault, SafetyVerdict, Severity, Telemetry, finite
from .limits import SafetyLimits

G001, G002, G003, G004, G005 = (f"BESS-GUARD-00{i}" for i in range(1, 6))
G006, G007, G008, G009 = "BESS-GUARD-006", "BESS-GUARD-007", "BESS-GUARD-008", "BESS-GUARD-009"
G010, G020, G021, G090 = "BESS-GUARD-010", "BESS-GUARD-020", "BESS-GUARD-021", "BESS-GUARD-090"

_TRIP_NAMES = {
    G001: "CELL_UNDERVOLTAGE_TRIP",
    G002: "CELL_OVERVOLTAGE_TRIP",
    G003: "CELL_OVERTEMPERATURE_TRIP",
    G004: "DC_ISOLATION_FAULT",
    G008: "STRING_VOLTAGE_OUT_OF_WINDOW",
}


@dataclass(slots=True)
class _Latched:
    since: float
    detail: str


def _f(x: Optional[float], nd: int = 1) -> str:
    """Formatea de forma segura (un dato puede haber desaparecido con el estado de recorte aún activo)."""
    return f"{x:.{nd}f}" if finite(x) else "n/d"


class SafetyEnvelope:
    def __init__(self, limits: SafetyLimits, plant: PlantConfig, f_nominal_hz: float = 50.0,
                 v_nominal_v: Optional[float] = None) -> None:
        self.limits = limits
        self.plant = plant
        self.f_nominal_hz = f_nominal_hz
        self.v_nominal_v = v_nominal_v if v_nominal_v is not None else plant.v_nominal_v
        self._latched: dict[str, _Latched] = {}
        self._trip_counts: dict[str, int] = {}
        self._thermal_derate = False
        self._ambient_derate = False
        self._lowtemp = False
        self._data_fault = False
        self._ok_streak = 0
        self._last_tel: Optional[Telemetry] = None

    # ------------------------------------------------------------------
    # Plausibilidad
    # ------------------------------------------------------------------
    def _plausibility(self, tel: Telemetry) -> list[str]:
        c = self.limits.cell
        bad: list[str] = []
        vlo, vhi = c.plausible_voltage_v
        tlo, thi = c.plausible_temp_c
        for sig in ("cell_v_min_v", "cell_v_max_v"):
            v = getattr(tel, sig)
            if finite(v) and not vlo <= v <= vhi:
                bad.append(f"{sig}={v}")
        for sig in ("cell_t_max_c", "cell_t_min_c"):
            v = getattr(tel, sig)
            if finite(v) and not tlo <= v <= thi:
                bad.append(f"{sig}={v}")
        if finite(tel.soc_pct) and not 0.0 <= tel.soc_pct <= 100.0:  # type: ignore[operator]
            bad.append(f"soc_pct={tel.soc_pct}")
        if finite(tel.isolation_kohm) and tel.isolation_kohm < 0:  # type: ignore[operator]
            bad.append(f"isolation_kohm={tel.isolation_kohm}")
        if finite(tel.cell_v_min_v) and finite(tel.cell_v_max_v) and tel.cell_v_max_v < tel.cell_v_min_v - 1e-9:  # type: ignore[operator]
            bad.append("cell_v_max<cell_v_min")
        return bad

    # ------------------------------------------------------------------
    # Condiciones de disparo (puras) y su "despeje" con histéresis
    # ------------------------------------------------------------------
    def _trip_state(self, tel: Telemetry) -> dict[str, tuple[bool, bool, str]]:
        """code -> (activa, despejada_con_histéresis, detalle). Sólo señales finitas."""
        c, r, t = self.limits.cell, self.limits.rack, self.limits.timing
        out: dict[str, tuple[bool, bool, str]] = {}

        def add(code: str, active: bool, clear: bool, detail: str) -> None:
            out[code] = (active, clear, detail)

        if finite(tel.cell_v_min_v):
            v = tel.cell_v_min_v
            add(G001, v < c.voltage_min_v, v >= c.voltage_min_v + t.voltage_hysteresis_v,  # type: ignore[operator]
                f"V_celda_min={v:.3f} V < {c.voltage_min_v} V")
        if finite(tel.cell_v_max_v):
            v = tel.cell_v_max_v
            add(G002, v > c.voltage_max_v, v <= c.voltage_max_v - t.voltage_hysteresis_v,  # type: ignore[operator]
                f"V_celda_max={v:.3f} V > {c.voltage_max_v} V")
        if finite(tel.cell_t_max_c):
            v = tel.cell_t_max_c
            add(G003, v > c.temp_max_c, v <= c.temp_max_c - t.temp_hysteresis_c,  # type: ignore[operator]
                f"T_celda_max={v:.1f} °C > {c.temp_max_c} °C")
        if finite(tel.isolation_kohm):
            v = tel.isolation_kohm
            add(G004, v < r.dc_isolation_min_kohm, v >= r.dc_isolation_min_kohm + t.isolation_hysteresis_kohm,  # type: ignore[operator]
                f"R_aislamiento={v:.1f} kΩ < {r.dc_isolation_min_kohm} kΩ")
        if finite(tel.string_v_v) and (r.string_voltage_min_v is not None or r.string_voltage_max_v is not None):
            v = tel.string_v_v
            lo = r.string_voltage_min_v if r.string_voltage_min_v is not None else -math.inf
            hi = r.string_voltage_max_v if r.string_voltage_max_v is not None else math.inf
            hv = t.voltage_hysteresis_v * 100.0
            add(G008, not lo <= v <= hi, lo + hv <= v <= hi - hv,  # type: ignore[operator]
                f"V_string={v:.1f} V fuera de [{lo}, {hi}]")
        return out

    # ------------------------------------------------------------------
    # Evaluación
    # ------------------------------------------------------------------
    def evaluate(self, tel: Optional[Telemetry], now: float, *, max_age_s: Optional[float] = None) -> SafetyVerdict:
        lim, c, t = self.limits, self.limits.cell, self.limits.timing
        faults: list[Fault] = []

        if tel is not None and max_age_s is not None and tel.age_s(now) > max_age_s:
            tel = None
        self._last_tel = tel

        # ---- 1. Validez de datos requeridos ------------------------------
        data_problems: list[str] = []
        if tel is None:
            data_problems.append("sin telemetría vigente")
        else:
            for sig in lim.required_signals:
                if not finite(getattr(tel, sig, None)):
                    data_problems.append(f"{sig} ausente/no finita")
            data_problems += [f"implausible: {b}" for b in self._plausibility(tel)]

        if data_problems:
            self._data_fault = True
            self._ok_streak = 0
        elif self._data_fault:
            self._ok_streak += 1
            if self._ok_streak >= t.recovery_valid_cycles:
                self._data_fault = False
        data_active = self._data_fault
        if data_active:
            detail = "; ".join(data_problems) if data_problems else (
                f"recuperando ({self._ok_streak}/{t.recovery_valid_cycles} ciclos válidos)")
            faults.append(Fault(G090, "REQUIRED_SIGNAL_INVALID", Severity.DATA, detail))

        # ---- 2. Disparos enclavados -------------------------------------
        if tel is not None:
            state = self._trip_state(tel)
            for code, (active, _clear, detail) in state.items():
                if active:
                    n = self._trip_counts.get(code, 0) + 1
                    self._trip_counts[code] = n
                    if n >= t.trip_debounce_cycles and code not in self._latched:
                        self._latched[code] = _Latched(now, detail)
                else:
                    self._trip_counts[code] = 0
            if t.auto_reset_after_s is not None:
                for code in list(self._latched):
                    st = state.get(code)
                    if st is not None and st[1] and now - self._latched[code].since >= t.auto_reset_after_s:
                        del self._latched[code]
        for code, lt in self._latched.items():
            faults.append(Fault(code, _TRIP_NAMES[code], Severity.TRIP, lt.detail, latched=True))
        tripped = bool(self._latched)

        # ---- 3. Advertencias / recortes (sólo con datos válidos) ---------
        derate = 1.0
        soc_dis = soc_chg = 1.0
        charge_inhibit_temp = False
        if tel is not None and not data_active:
            # Desbalance
            if finite(tel.cell_v_min_v) and finite(tel.cell_v_max_v):
                dv_mv = (tel.cell_v_max_v - tel.cell_v_min_v) * 1000.0  # type: ignore[operator]
                if dv_mv > c.max_cell_imbalance_mv:
                    faults.append(Fault(G005, "CELL_IMBALANCE_WARNING", Severity.WARNING,
                                        f"ΔV={dv_mv:.1f} mV > {c.max_cell_imbalance_mv} mV"))
            # Derate térmico con histéresis
            tm = tel.cell_t_max_c
            if finite(tm):
                if tm >= c.temp_derate_c:  # type: ignore[operator]
                    self._thermal_derate = True
                elif tm <= c.temp_derate_c - t.temp_hysteresis_c:  # type: ignore[operator]
                    self._thermal_derate = False
            if self._thermal_derate:
                derate = min(derate, 0.5)
                faults.append(Fault(G006, "CELL_TEMP_DERATE_50", Severity.DERATE,
                                    f"T_celda_max={_f(tm)} °C ≥ {c.temp_derate_c} °C"))
            # Temperatura baja (opcional)
            tmin = tel.cell_t_min_c
            if finite(tmin):
                if tmin < c.temp_min_c:  # type: ignore[operator]
                    self._lowtemp = True
                elif tmin >= c.temp_min_c + t.temp_hysteresis_c:  # type: ignore[operator]
                    self._lowtemp = False
            if self._lowtemp:
                charge_inhibit_temp = True
                faults.append(Fault(G007, "CELL_LOW_TEMP_CHARGE_INHIBIT", Severity.DERATE,
                                    f"T_celda_min={_f(tmin)} °C < {c.temp_min_c} °C"))
            # Ambiente (opcional)
            amb = tel.ambient_c
            mx = lim.rack.max_ambient_temp_c
            if finite(amb) and mx is not None:
                if amb > mx:  # type: ignore[operator]
                    self._ambient_derate = True
                elif amb <= mx - t.temp_hysteresis_c:  # type: ignore[operator]
                    self._ambient_derate = False
            if self._ambient_derate:
                derate = min(derate, 0.5)
                faults.append(Fault(G009, "AMBIENT_TEMP_DERATE_50", Severity.DERATE, f"T_ambiente={_f(amb)} °C > {mx} °C"))
            # SOC
            soc = tel.soc_pct
            s = lim.soc
            if finite(soc):
                if soc <= s.min_pct:  # type: ignore[operator]
                    soc_dis = 0.0
                elif s.taper_pct > 0 and soc < s.min_pct + s.taper_pct:  # type: ignore[operator]
                    soc_dis = (soc - s.min_pct) / s.taper_pct  # type: ignore[operator]
                if soc >= s.max_pct:  # type: ignore[operator]
                    soc_chg = 0.0
                elif s.taper_pct > 0 and soc > s.max_pct - s.taper_pct:  # type: ignore[operator]
                    soc_chg = (s.max_pct - soc) / s.taper_pct  # type: ignore[operator]
                if soc_dis < 1.0:
                    faults.append(Fault(G010, "SOC_LOW_DISCHARGE_LIMIT", Severity.DERATE,
                                        f"SOC={soc:.1f} % ≤ {s.min_pct + s.taper_pct} % (descarga {soc_dis:.0%})"))
                if soc_chg < 1.0:
                    faults.append(Fault(G010, "SOC_HIGH_CHARGE_LIMIT", Severity.DERATE,
                                        f"SOC={soc:.1f} % ≥ {s.max_pct - s.taper_pct} % (carga {soc_chg:.0%})"))
            # Alarmas de red (sólo alarma)
            g = lim.grid
            f = tel.frequency_hz
            if finite(f) and ((g.f_alarm_low_hz is not None and f < g.f_alarm_low_hz)  # type: ignore[operator]
                              or (g.f_alarm_high_hz is not None and f > g.f_alarm_high_hz)):  # type: ignore[operator]
                faults.append(Fault(G020, "GRID_FREQUENCY_ALARM", Severity.WARNING, f"f={f:.3f} Hz"))
            v = tel.v_grid_v
            if finite(v) and self.v_nominal_v > 0:
                pu = v / self.v_nominal_v  # type: ignore[operator]
                if ((g.v_alarm_low_pu is not None and pu < g.v_alarm_low_pu)
                        or (g.v_alarm_high_pu is not None and pu > g.v_alarm_high_pu)):
                    faults.append(Fault(G021, "GRID_VOLTAGE_ALARM", Severity.WARNING, f"V={pu:.3f} pu"))

        # ---- 4. Límites de salida ----------------------------------------
        allow = not tripped and not data_active
        if allow:
            p_dis = self.plant.p_discharge_cap_kw * derate * soc_dis
            p_chg = self.plant.p_charge_cap_kw * derate * soc_chg * (0.0 if charge_inhibit_temp else 1.0)
        else:
            p_dis = p_chg = 0.0
            derate = 0.0
        return SafetyVerdict(
            faults=tuple(faults),
            allow_output=allow,
            p_discharge_max_kw=p_dis,
            p_charge_max_kw=p_chg,
            derate_factor=derate,
            tripped=tripped,
        )

    # ------------------------------------------------------------------
    # Operación
    # ------------------------------------------------------------------
    @property
    def latched_codes(self) -> tuple[str, ...]:
        return tuple(self._latched)

    def reset_trips(self, now: float) -> tuple[bool, str]:
        """Libera disparos enclavados si (y sólo si) la última telemetría está despejada."""
        if not self._latched:
            return True, "sin disparos enclavados"
        tel = self._last_tel
        if tel is None:
            return False, "sin telemetría vigente: no se puede verificar que la condición esté despejada"
        state = self._trip_state(tel)
        blocking = []
        for code in self._latched:
            st = state.get(code)
            if st is None:
                blocking.append(f"{code}: señal no disponible")
            elif not st[1]:
                blocking.append(f"{code}: {st[2]} (aún no despejada con histéresis)")
        if blocking:
            return False, "; ".join(blocking)
        cleared = tuple(self._latched)
        self._latched.clear()
        self._trip_counts.clear()
        return True, f"liberados: {', '.join(cleared)}"
