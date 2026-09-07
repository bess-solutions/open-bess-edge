# -*- coding: utf-8 -*-
"""
open-bess-edge/research/physics_informed_twin.py
Gemelo Digital en Tiempo Real para Borde (Edge Physics-Informed Digital Twin).
Combina el estándar BPX de Faraday con estimación rápida de resistencia interna y salud (SoH).
"""

import time
import math
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

try:
    from .bpx_parameter_store import BPXParameterStore, CellBPXParameters
except ImportError:
    from bpx_parameter_store import BPXParameterStore, CellBPXParameters

logger = logging.getLogger("OpenBESSEdge.Research.PhysicsTwin")

@dataclass
class EdgeTelemetrySnapshot:
    timestamp_unix: float
    pack_voltage_v: float
    pack_current_a: float # Positivo: Descarga | Negativo: Carga
    cell_min_voltage_v: float
    cell_max_voltage_v: float
    cell_avg_temp_c: float
    cell_max_temp_c: float
    bms_soc_reported: float

@dataclass
class PhysicsTwinDiagnostic:
    timestamp: float
    estimated_soh_pct: float
    estimated_internal_resistance_mohm: float
    thermal_gradient_c: float
    lithium_plating_risk_level: str # 'NORMAL', 'WARNING', 'CRITICAL'
    degradation_rate_micro_pct_per_cycle: float
    anomalies_detected: list

class PhysicsInformedEdgeTwin:
    """
    Gemelo Digital electroquímico embebido en el Edge IPC de Open BESS Edge.
    Calcula en tiempo real la resistencia interna dinámica, deriva de tensión y
    riesgo electroquímico sin depender de la nube.
    """
    def __init__(self, cell_profile_id: str = "LFP_314Ah_Prismatic_C&I"):
        self.store = BPXParameterStore()
        self.cell_params = self.store.get_profile(cell_profile_id)
        self.cycle_count = 0
        self.accumulated_energy_mwh = 0.0
        self.last_snapshot: Optional[EdgeTelemetrySnapshot] = None
        self.base_soh = 100.0

    def evaluate_step(self, snapshot: EdgeTelemetrySnapshot) -> PhysicsTwinDiagnostic:
        now = snapshot.timestamp_unix
        anomalies = []

        # 1. Gradiente térmico entre celdas del rack
        thermal_gradient = snapshot.cell_max_temp_c - snapshot.cell_avg_temp_c
        if thermal_gradient > 3.0:
            anomalies.append(f"Gradiente térmico excesivo en rack: {thermal_gradient:.2f}°C (>3.0°C)")

        # 2. Estimación de resistencia interna dinámica (dV / dI)
        r_int_est = self.cell_params.internal_resistance_mohm
        if self.last_snapshot is not None:
            di = abs(snapshot.pack_current_a - self.last_snapshot.pack_current_a)
            dv = abs(snapshot.pack_voltage_v - self.last_snapshot.pack_voltage_v)
            dt = now - self.last_snapshot.timestamp_unix
            
            # Si hubo un escalón de corriente significativo en < 2 segundos
            if di > 20.0 and dt < 2.0:
                # Normalizar a nivel de celda (asumiendo 224 celdas en serie)
                r_int_calc = (dv / di) / 224.0 * 1000.0 # en mOhm
                if 0.05 < r_int_calc < 2.0:
                    r_int_est = 0.9 * r_int_est + 0.1 * r_int_calc

        # 3. Detección de riesgo de litio enchapado (Lithium Plating)
        # Ocurre cuando se carga a altas corrientes con baja temperatura (<10°C) o a alto SoC (>85%)
        is_charging = snapshot.pack_current_a < -10.0
        c_rate = abs(snapshot.pack_current_a) / self.cell_params.nominal_capacity_ah
        
        plating_risk = "NORMAL"
        if is_charging:
            if snapshot.cell_avg_temp_c < 10.0 and c_rate > 0.2:
                plating_risk = "CRITICAL"
                anomalies.append("Riesgo crítico de Lithium Plating: Carga a baja temperatura (<10°C) @ >0.2C")
            elif snapshot.bms_soc_reported > 88.0 and c_rate > 0.4:
                plating_risk = "WARNING"
                anomalies.append("Riesgo moderado de sobretensión interfacial anódica @ SoC > 88%")

        # 4. Estimación continua de SoH (modelo de degradación SEI cuadrático)
        # Acumulación de Ah throughput
        if self.last_snapshot is not None:
            dt_hours = (now - self.last_snapshot.timestamp_unix) / 3600.0
            power_kw = abs(snapshot.pack_voltage_v * snapshot.pack_current_a) / 1000.0
            self.accumulated_energy_mwh += (power_kw * dt_hours) / 1000.0

        # Degradación típica LFP: 20% tras 6.000 ciclos completos (0.0033% por ciclo)
        # 1 ciclo completo = 2 * Capacidad nominal
        equivalent_cycles = (self.accumulated_energy_mwh * 1000.0) / (self.cell_params.nominal_capacity_ah * 3.2 * 224 / 1000.0 * 2)
        soh_calculated = max(70.0, 100.0 - (equivalent_cycles * 0.0033))

        self.last_snapshot = snapshot

        diagnostic = PhysicsTwinDiagnostic(
            timestamp=now,
            estimated_soh_pct=round(soh_calculated, 3),
            estimated_internal_resistance_mohm=round(r_int_est, 3),
            thermal_gradient_c=round(thermal_gradient, 2),
            lithium_plating_risk_level=plating_risk,
            degradation_rate_micro_pct_per_cycle=33.0,
            anomalies_detected=anomalies
        )
        return diagnostic

if __name__ == "__main__":
    twin = PhysicsInformedEdgeTwin()
    snap = EdgeTelemetrySnapshot(
        timestamp_unix=time.time(),
        pack_voltage_v=716.8,
        pack_current_a=-150.0, # Carga diurna 100 kW
        cell_min_voltage_v=3.20,
        cell_max_voltage_v=3.22,
        cell_avg_temp_c=24.5,
        cell_max_temp_c=25.2,
        bms_soc_reported=65.0
    )
    diag = twin.evaluate_step(snap)
    print(f"[OK] Physics Twin Step: SoH: {diag.estimated_soh_pct}% | R_int: {diag.estimated_internal_resistance_mohm} mOhm | Plating: {diag.lithium_plating_risk_level}")
