#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
open-bess-edge/src/safety/safety_envelope_evaluator.py
==============================================================================
Open BESS Edge — Deterministic Safety Envelope Evaluator
==============================================================================
Evaluador determinístico de envolvente de seguridad de hardware en tiempo real.
Implementa códigos BESS-GUARD-001 a 005 bajo estándares SEC RIC N° 01/02 y NFPA 855.
==============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

EDGE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BASELINE = EDGE_ROOT / "data" / "bess_safety_baseline.json"


class SafetyEnvelopeEvaluator:
    """
    Evalúa telemetría de celdas, rack e inversor contra límites físicos absolutos.
    Garantiza tiempo de respuesta sub-milisegundo y enclavamiento seguro.
    """

    def __init__(self, baseline_path: Optional[Path] = None):
        self.baseline_path = baseline_path or DEFAULT_BASELINE
        self.baseline = self._load_baseline()

    def _load_baseline(self) -> Dict[str, Any]:
        if self.baseline_path.exists():
            try:
                return json.loads(self.baseline_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "cell_limits": {
                "voltage_min_v": 2.50,
                "voltage_max_v": 3.65,
                "temp_max_c": 50.0,
                "max_cell_imbalance_mv": 50.0,
            },
            "rack_limits": {
                "max_charge_c_rate": 0.50,
                "max_discharge_c_rate": 1.00,
                "dc_isolation_min_kohm": 500.0,
            }
        }

    def evaluate_cell_telemetry(
        self,
        v_min_v: float,
        v_max_v: float,
        t_max_c: float,
        isolation_kohm: float = 1000.0,
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Evalúa las mediciones extremas de celdas y resistencia de aislamiento.
        
        Retorna:
            (is_safe, list_of_fault_codes, metadata)
        """
        cell_limits = self.baseline.get("cell_limits", {})
        rack_limits = self.baseline.get("rack_limits", {})

        v_min_limit = cell_limits.get("voltage_min_v", 2.50)
        v_max_limit = cell_limits.get("voltage_max_v", 3.65)
        t_max_limit = cell_limits.get("temp_max_c", 50.0)
        imbalance_limit_mv = cell_limits.get("max_cell_imbalance_mv", 50.0)
        iso_min_limit = rack_limits.get("dc_isolation_min_kohm", 500.0)

        faults: List[str] = []

        # BESS-GUARD-001: Subtensión de celda
        if v_min_v < v_min_limit:
            faults.append(f"BESS-GUARD-001: CELL_UNDERVOLTAGE ({v_min_v:.3f}V < {v_min_limit}V)")

        # BESS-GUARD-002: Sobretensión de celda
        if v_max_v > v_max_limit:
            faults.append(f"BESS-GUARD-002: CELL_OVERVOLTAGE ({v_max_v:.3f}V > {v_max_limit}V)")

        # BESS-GUARD-003: Sobretemperatura de celda
        if t_max_c > t_max_limit:
            faults.append(f"BESS-GUARD-003: CELL_OVERTEMPERATURE ({t_max_c:.1f}°C > {t_max_limit}°C)")

        # BESS-GUARD-004: Falla de aislamiento DC
        if isolation_kohm < iso_min_limit:
            faults.append(f"BESS-GUARD-004: DC_ISOLATION_FAULT ({isolation_kohm:.1f}kOhm < {iso_min_limit}kOhm)")

        # BESS-GUARD-005: Desbalance excesivo entre celdas (Delta V)
        delta_v_mv = (v_max_v - v_min_v) * 1000.0
        if delta_v_mv > imbalance_limit_mv:
            faults.append(f"BESS-GUARD-005: CELL_IMBALANCE_WARNING (Delta {delta_v_mv:.1f}mV > {imbalance_limit_mv}mV)")

        is_safe = len([f for f in faults if "BESS-GUARD-005" not in f]) == 0  # Imbalance es warning inicial

        meta = {
            "v_min_v": v_min_v,
            "v_max_v": v_max_v,
            "delta_v_mv": delta_v_mv,
            "t_max_c": t_max_c,
            "isolation_kohm": isolation_kohm,
            "faults_count": len(faults),
            "status": "SAFE_NORMAL" if not faults else ("WARNING" if is_safe else "CRITICAL_TRIP"),
        }

        return is_safe, faults, meta

    def evaluate_inverter_setpoint(
        self,
        p_target_kw: float,
        q_target_kvar: float,
        e_nominal_kwh: float,
        isolation_kohm: float = 1000.0,
    ) -> Tuple[bool, float, str]:
        """
        Valida y recorta la consigna del inversor si viola límites de C-rate o aislamiento.
        
        Convención de signos:
            + P : Descarga (inyección a la red)
            - P : Carga (absorción de la red)
        """
        rack_limits = self.baseline.get("rack_limits", {})
        min_iso = rack_limits.get("dc_isolation_min_kohm", 500.0)

        if isolation_kohm < min_iso:
            return False, 0.0, f"BESS-GUARD-004: Interlock de aislamiento activo ({isolation_kohm:.1f}kOhm < {min_iso}kOhm)"

        max_charge_kw = e_nominal_kwh * rack_limits.get("max_charge_c_rate", 0.50)
        max_discharge_kw = e_nominal_kwh * rack_limits.get("max_discharge_c_rate", 1.00)

        # Recorte de carga (-P)
        if p_target_kw < -max_charge_kw:
            return True, -max_charge_kw, f"CLIPPED_MAX_CHARGE_C_RATE (-{max_charge_kw:.1f} kW)"

        # Recorte de descarga (+P)
        if p_target_kw > max_discharge_kw:
            return True, max_discharge_kw, f"CLIPPED_MAX_DISCHARGE_C_RATE (+{max_discharge_kw:.1f} kW)"

        return True, p_target_kw, "SETPOINT_APPROVED"
