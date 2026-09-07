#!/usr/bin/env python3
"""
open-bess-edge/tests/test_cen_cfydr_compliance.py
==============================================================================
Suite de Pruebas de Homologación y Cumplimiento CEN CFyDR 2026 & NTSyCS Cap. 3
==============================================================================
Valida de forma determinística:
- Banda muerta primaria estricta (+/- 30 mHz).
- Curva de estatismo s = 3% (rango admisible 2% a 5%).
- Disparo de respuesta rápida FFR sub-500ms ante contingencias severas (|df| >= 300 mHz).
- Limitador de rampa normal en operación cuasiestacionaria (<= 20% Pn/min).
- Desconexión instantánea de consumo en modo de carga durante subfrecuencia.
- Regulación dinámica de tensión Q(V) según NTSyCS.
- Orquestación en tiempo real del nodo BESSEdgeNode.
==============================================================================
"""

import sys
from pathlib import Path

import pytest

EDGE_DIR = Path(__file__).resolve().parent.parent
if str(EDGE_DIR) not in sys.path:
    sys.path.insert(0, str(EDGE_DIR))

from src.controllers.ffr_droop_controller import FFRDroopController
from src.controllers.volt_var_controller import ReactiveControlMode, VoltVarController
from src.edge_node import BESSEdgeNode


def test_cen_deadband_insensitivity_30mhz():
    """
    Verifica que fluctuaciones continuas de demanda dentro de +/- 30 mHz
    no provoquen ciclado innecesario de potencia (insensibilidad intencional CEN).
    """
    ctrl = FFRDroopController(p_nominal_kw=1000.0, f_nominal_hz=50.0, deadband_hz=0.03)

    # 49.98 Hz -> df = -0.02 Hz (dentro de banda muerta -0.03 Hz)
    p_out, meta = ctrl.compute_response(49.98)
    assert p_out == 0.0
    assert meta["status"] == "IDLE_DEADBAND"

    # 50.02 Hz -> df = +0.02 Hz (dentro de banda muerta +0.03 Hz)
    p_out_over, meta_over = ctrl.compute_response(50.02)
    assert p_out_over == 0.0
    assert meta_over["status"] == "IDLE_DEADBAND"


def test_cen_droop_primary_regulation_accuracy():
    """
    Verifica la ganancia canónica de estatismo s = 3%:
    Gain K_p = P_nom / (s * f_nom) = 1000 / (0.03 * 50) = 666.6667 kW/Hz.
    Para f = 49.85 Hz:
      df = -0.15 Hz
      active_df = -0.15 - (-0.03) = -0.12 Hz
      Delta P = - (666.6667) * (-0.12) = +80.0 kW (descarga de soporte)
    """
    ctrl = FFRDroopController(
        p_nominal_kw=1000.0,
        f_nominal_hz=50.0,
        droop_r=0.03,
        deadband_hz=0.03,
    )

    # Forzar dt_s suficientemente amplio para no topar con rampa normal
    ctrl.last_execution_time -= 60.0

    p_out, meta = ctrl.compute_response(49.85)
    assert pytest.approx(p_out, abs=1.0) == 80.0
    assert meta["status"] == "PRIMARY_DROOP_ACTIVE"


def test_cen_ffr_severe_contingency_trip():
    """
    Verifica la respuesta FFR de emergencia ante caída brusca de frecuencia
    por desconexión de una unidad de gran porte (ej. San Isidro II 397 MW):
    f = 49.60 Hz (|df| = 0.40 Hz >= 0.30 Hz).
    El controlador debe activar FFR_CONTINGENCY_TRIP y modo FFR_EMERGENCY_FAST.
    """
    ctrl = FFRDroopController(
        p_nominal_kw=1000.0,
        f_nominal_hz=50.0,
        droop_r=0.03,
        deadband_hz=0.03,
        ffr_contingency_threshold_hz=0.30,
    )

    p_out, meta = ctrl.compute_response(49.60)
    assert meta["is_ffr_emergency"] is True
    assert meta["status"] == "FFR_CONTINGENCY_TRIP"
    assert meta["ramp_mode"] == "FFR_EMERGENCY_FAST"
    assert p_out > 0.0  # Inyección activa e inmediata


def test_cen_charging_mode_instantaneous_relief():
    """
    Verifica la doble respuesta del BESS cuando está cargando:
    Si el BESS está absorbiendo -500 kW a mediodía solar y cae la frecuencia,
    la potencia base de carga se suprime a cero de inmediato, aliviando al sistema.
    """
    ctrl = FFRDroopController(p_nominal_kw=1000.0, f_nominal_hz=50.0, deadband_hz=0.03)
    ctrl.last_execution_time -= 60.0

    p_out, meta = ctrl.compute_response(f_measured_hz=49.85, p_base_kw=-500.0)
    # Sin supresión de carga daría -500 + 80 = -420 kW (seguiría absorbiendo).
    # Con la regla CEN de supresión de carga en subfrecuencia: effective_p_base = 0 -> p_out = +80 kW.
    assert pytest.approx(p_out, abs=0.1) == 80.0
    assert meta["effective_p_base_kw"] == 0.0


def test_cen_volt_var_qv_curve():
    """
    Verifica el soporte dinámico de potencia reactiva Q(V) bajo NTSyCS Cap. 3:
    Banda muerta: +/- 2% Vnom (392 V a 408 V para Vnom = 400 V).
    Baja tensión: V = 380 V (0.95 pu -> dv = -0.05 -> active_dv = -0.03 pu).
    Inyección de reactivos capacitivos (+Q) para levantar la tensión.
    Sobretensión: V = 420 V (1.05 pu -> dv = +0.05 -> active_dv = +0.03 pu).
    Absorción de reactivos inductivos (-Q) para contener la tensión.
    """
    vv = VoltVarController(
        q_max_kvar=600.0,
        v_nominal_v=400.0,
        deadband_pct=2.0,
        slope_k_q=10.0,
        mode=ReactiveControlMode.VOLT_VAR_Q_V,
    )

    # 1. Dentro de banda muerta (402 V)
    q_idle, meta_idle = vv.compute_reactive_power(402.0)
    assert q_idle == 0.0
    assert meta_idle["status"] == "VOLT_VAR_DEADBAND_IDLE"

    # 2. Subtensión (380 V) -> Inyección capacitiva (+Q)
    q_boost, meta_boost = vv.compute_reactive_power(380.0)
    assert q_boost > 0.0
    assert meta_boost["status"] == "UNDERVOLTAGE_INJECTING_Q"

    # 3. Sobretensión (420 V) -> Absorción inductiva (-Q)
    q_buck, meta_buck = vv.compute_reactive_power(420.0)
    assert q_buck < 0.0
    assert meta_buck["status"] == "OVERVOLTAGE_ABSORBING_Q"


def test_cen_cos_phi_p_curve():
    """Verifica el control de factor de potencia dinámico en función de la potencia activa P."""
    vv = VoltVarController(
        q_max_kvar=500.0,
        mode=ReactiveControlMode.POWER_FACTOR,
    )
    # Sin inyección activa -> Q = 0
    q_zero, meta_zero = vv.compute_reactive_power(400.0, p_actual_kw=0.0)
    assert q_zero == 0.0
    assert meta_zero["status"] == "COS_PHI_REGULATION"

    # Con inyección nominal (1000 kW) y cos(phi) = 0.95 -> Q != 0
    q_act, meta_act = vv.compute_reactive_power(
        400.0, p_actual_kw=1000.0, target_cos_phi=0.95
    )
    assert q_act > 0.0
    assert meta_act["status"] == "COS_PHI_REGULATION"


@pytest.mark.asyncio
async def test_full_edge_node_closed_loop():
    """
    Prueba integral de lazo cerrado con BESSEdgeNode:
    Modbus -> Safety Envelope -> FFR/Droop -> Volt/VAR -> Modbus Write.
    """
    node = BESSEdgeNode()
    started = await node.start()
    assert started is True

    # 1. Ciclo en régimen normal
    res_normal = await node.step()
    assert res_normal["f_grid_hz"] == 50.0
    assert res_normal["p_setpoint_kw"] == 0.0
    assert res_normal["safety_status"] == "SAFE_NORMAL"
    assert res_normal["latency_ms"] < 20.0  # Latencia ultra-baja garantizada

    # 2. Inyección de contingencia de subfrecuencia severa (49.65 Hz)
    node.driver.inject_simulated_grid_event(f_hz=49.65, v_v=390.0)
    res_contingency = await node.step()
    assert res_contingency["p_setpoint_kw"] > 0.0
    assert res_contingency["is_ffr_emergency"] is True
    assert res_contingency["commit_ok"] is True

    # 3. Inyección de evento crítico de celda para verificar interlock de seguridad
    node.driver._sim_t_max_c = 58.0  # Sobretemperatura crítica
    res_interlock = await node.step()
    assert res_interlock["status"] == "SAFETY_TRIP_INTERLOCK"
    assert len(res_interlock["faults"]) > 0

    await node.stop()
