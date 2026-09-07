"""
open-bess-edge/src/controllers/ffr_droop_controller.py
==============================================================================
Fast Frequency Response (FFR) & Droop Controller (NTSyCS Cap. 3 & CEN CFyDR)
==============================================================================
Controlador determinístico sub-500ms con estatismo configurable (2% a 5%),
banda muerta estricta (+/- 30 mHz) y detección de contingencias severas
según los estándares del Coordinador Eléctrico Nacional (SEN de Chile).
==============================================================================
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any


class FFRDroopController:
    """
    Controlador de frecuencia primaria y respuesta rápida para inversores BESS.
    Cumple con el Capítulo 3 de la NTSyCS (Res. CNE N° 343) y el Estudio CFyDR 2026.
    """

    def __init__(
        self,
        p_nominal_kw: float = 1000.0,
        f_nominal_hz: float = 50.0,
        droop_r: float = 0.03,  # Estatismo s = 3% (rango 0.02 - 0.05)
        deadband_hz: float = 0.03,  # Banda muerta oficial CEN: +/- 30 mHz
        ffr_contingency_threshold_hz: float = 0.30,  # Umbral FFR de emergencia: +/- 300 mHz
        normal_ramp_limit_pct_min: float = 20.0,  # Rampa normal en cuasiestacionario: <= 20% Pn/min
        min_soc_pct: float = 5.0,
        max_soc_pct: float = 95.0,
    ):
        if not (0.01 <= droop_r <= 0.10):
            raise ValueError(f"Droop {droop_r} fuera de límites técnicos admisibles (0.01 a 0.10)")

        self.p_nominal_kw = p_nominal_kw
        self.f_nominal_hz = f_nominal_hz
        self.droop_r = droop_r
        self.deadband_hz = deadband_hz
        self.ffr_threshold_hz = ffr_contingency_threshold_hz
        self.normal_ramp_rate_kw_per_sec = (normal_ramp_limit_pct_min / 100.0 * p_nominal_kw) / 60.0
        self.min_soc = min_soc_pct
        self.max_soc = max_soc_pct

        self.last_execution_time: float = time.monotonic()
        self.last_p_kw: float = 0.0

        # Registro de contingencia para auditar Aporte @10s y @2min
        self.contingency_active: bool = False
        self.contingency_start_time: float | None = None
        self.event_history: deque = deque(maxlen=3600)  # búfer de 1 hora a 1 Hz
        self.aporte_10s_kw: float | None = None
        self.aporte_2min_kw: float | None = None

    def compute_response(
        self,
        f_measured_hz: float,
        p_base_kw: float = 0.0,
        soc_pct: float = 50.0,
    ) -> tuple[float, dict[str, Any]]:
        """
        Calcula la consigna de potencia activa de acuerdo a la desviación de frecuencia.

        Retorna:
            (p_target_kw, telemetry_dict)
        """
        now = time.monotonic()
        dt_s = max(1e-4, now - self.last_execution_time)
        self.last_execution_time = now

        df = f_measured_hz - self.f_nominal_hz

        # 1. Evaluación de banda muerta (Insensibilidad)
        active_df = 0.0
        if df > self.deadband_hz:
            active_df = df - self.deadband_hz
        elif df < -self.deadband_hz:
            active_df = df + self.deadband_hz

        # 2. Detección de Contingencia Severa (FFR)
        is_ffr_emergency = abs(df) >= self.ffr_threshold_hz

        if is_ffr_emergency and not self.contingency_active:
            self.contingency_active = True
            self.contingency_start_time = now
            self.aporte_10s_kw = None
            self.aporte_2min_kw = None
        elif not is_ffr_emergency and abs(df) < self.deadband_hz:
            self.contingency_active = False
            self.contingency_start_time = None

        # 3. Formulación Canónica de Estatismo: Delta P = - (P_nom / (s * f_nom)) * active_df
        # Ganancia estática K_p = P_nom / (s * f_nom) [kW/Hz]
        gain = self.p_nominal_kw / (self.droop_r * self.f_nominal_hz)
        unclamped_delta_p = -gain * active_df

        # 4. Manejo de estado previo de carga (Desconexión de Carga como recurso FFR)
        # Si el BESS estaba cargando (p_base_kw < 0) y hay subfrecuencia (active_df < 0):
        # primero suprime la carga a cero antes de inyectar potencia.
        effective_p_base = p_base_kw
        if active_df < 0 and p_base_kw < 0:
            effective_p_base = 0.0  # Desconexión inmediata de consumo

        raw_target_p = effective_p_base + unclamped_delta_p

        # 5. Envolvente por Estado de Carga (SoC Protection)
        # Si subfrecuencia y SoC crítico, no se puede descargar
        if (
            raw_target_p > 0
            and soc_pct <= self.min_soc
            or raw_target_p < 0
            and soc_pct >= self.max_soc
        ):
            raw_target_p = 0.0

        # Saturación a límites nominales de placa del inversor [-P_nom, +P_nom]
        saturated_target = max(-self.p_nominal_kw, min(self.p_nominal_kw, raw_target_p))

        # 6. Limitador de Rampa:
        # - En contingencia FFR: Rampa liberada para inyección sub-500ms (máxima velocidad del convertidor).
        # - En cuasiestacionario: Aplicación estricta de <= 20% Pn/min para estabilidad de red.
        if is_ffr_emergency:
            approved_p = saturated_target
            ramp_mode = "FFR_EMERGENCY_FAST"
        else:
            max_delta_p = self.normal_ramp_rate_kw_per_sec * dt_s
            delta_requested = saturated_target - self.last_p_kw
            if abs(delta_requested) > max_delta_p:
                step = max_delta_p if delta_requested > 0 else -max_delta_p
                approved_p = self.last_p_kw + step
                ramp_mode = "NORMAL_RAMP_LIMITED"
            else:
                approved_p = saturated_target
                ramp_mode = "NORMAL_FOLLOW"

        self.last_p_kw = approved_p

        # 7. Métricas de Auditoría CEN (@10s y @2min)
        if self.contingency_active and self.contingency_start_time:
            elapsed = now - self.contingency_start_time
            if elapsed >= 10.0 and self.aporte_10s_kw is None:
                self.aporte_10s_kw = approved_p
            if elapsed >= 120.0 and self.aporte_2min_kw is None:
                self.aporte_2min_kw = approved_p

        status = "IDLE_DEADBAND"
        if is_ffr_emergency:
            status = "FFR_CONTINGENCY_TRIP"
        elif active_df != 0.0:
            status = "PRIMARY_DROOP_ACTIVE"

        telemetry = {
            "f_measured_hz": f_measured_hz,
            "delta_f_hz": df,
            "active_df_hz": active_df,
            "gain_kw_hz": gain,
            "p_base_kw": p_base_kw,
            "effective_p_base_kw": effective_p_base,
            "p_target_kw": approved_p,
            "droop_pct": self.droop_r * 100.0,
            "status": status,
            "ramp_mode": ramp_mode,
            "is_ffr_emergency": is_ffr_emergency,
            "aporte_10s_kw": self.aporte_10s_kw,
            "aporte_2min_kw": self.aporte_2min_kw,
            "dt_ms": dt_s * 1000.0,
        }

        self.event_history.append((now, f_measured_hz, approved_p))

        return approved_p, telemetry
