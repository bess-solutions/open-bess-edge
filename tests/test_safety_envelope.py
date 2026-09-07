"""
open-bess-edge/tests/test_safety_envelope.py
==============================================================================
Pruebas de la Envolvente de Seguridad de Hardware (BESS-GUARD-001 a 005)
==============================================================================
"""

import sys
from pathlib import Path

EDGE_DIR = Path(__file__).resolve().parent.parent
if str(EDGE_DIR) not in sys.path:
    sys.path.insert(0, str(EDGE_DIR))

from src.safety.safety_envelope_evaluator import SafetyEnvelopeEvaluator


def test_safety_envelope_normal_operation():
    evaluator = SafetyEnvelopeEvaluator()
    # Parámetros normales LFP 314Ah: 3.20V a 3.25V, 25°C, 1200 kOhm
    safe, faults, meta = evaluator.evaluate_cell_telemetry(
        v_min_v=3.20,
        v_max_v=3.25,
        t_max_c=25.0,
        isolation_kohm=1200.0,
    )
    assert safe is True
    assert len(faults) == 0
    assert meta["status"] == "SAFE_NORMAL"


def test_bess_guard_001_undervoltage():
    evaluator = SafetyEnvelopeEvaluator()
    # Celda por debajo de 2.50V (ej. 2.35V)
    safe, faults, meta = evaluator.evaluate_cell_telemetry(
        v_min_v=2.35,
        v_max_v=3.20,
        t_max_c=25.0,
        isolation_kohm=1000.0,
    )
    assert safe is False
    assert any("BESS-GUARD-001" in f for f in faults)
    assert meta["status"] == "CRITICAL_TRIP"


def test_bess_guard_002_overvoltage():
    evaluator = SafetyEnvelopeEvaluator()
    # Celda por encima de 3.65V (ej. 3.72V)
    safe, faults, meta = evaluator.evaluate_cell_telemetry(
        v_min_v=3.20,
        v_max_v=3.72,
        t_max_c=25.0,
        isolation_kohm=1000.0,
    )
    assert safe is False
    assert any("BESS-GUARD-002" in f for f in faults)
    assert meta["status"] == "CRITICAL_TRIP"


def test_bess_guard_003_overtemperature():
    evaluator = SafetyEnvelopeEvaluator()
    # Temperatura por encima de 50.0°C (ej. 53.5°C)
    safe, faults, _meta = evaluator.evaluate_cell_telemetry(
        v_min_v=3.20,
        v_max_v=3.25,
        t_max_c=53.5,
        isolation_kohm=1000.0,
    )
    assert safe is False
    assert any("BESS-GUARD-003" in f for f in faults)


def test_bess_guard_004_isolation_fault():
    evaluator = SafetyEnvelopeEvaluator()
    # Aislamiento por debajo de 500 kOhm (ej. 320 kOhm)
    safe, faults, _meta = evaluator.evaluate_cell_telemetry(
        v_min_v=3.20,
        v_max_v=3.25,
        t_max_c=25.0,
        isolation_kohm=320.0,
    )
    assert safe is False
    assert any("BESS-GUARD-004" in f for f in faults)


def test_bess_guard_005_imbalance_warning():
    evaluator = SafetyEnvelopeEvaluator()
    # Desbalance mayor a 50 mV (ej. v_min=3.20V, v_max=3.28V -> Delta = 80 mV)
    _safe, faults, meta = evaluator.evaluate_cell_telemetry(
        v_min_v=3.20,
        v_max_v=3.28,
        t_max_c=25.0,
        isolation_kohm=1000.0,
    )
    assert any("BESS-GUARD-005" in f for f in faults)
    import pytest

    assert pytest.approx(meta["delta_v_mv"], abs=0.1) == 80.0


def test_inverter_setpoint_clipping_c_rate():
    evaluator = SafetyEnvelopeEvaluator()
    capacity_kwh = 2000.0  # 2 MWh

    # Descarga máxima: 1.0C = 2000 kW. Si se solicita 2500 kW, debe recortar a 2000 kW
    ok, p_clipped, reason = evaluator.evaluate_inverter_setpoint(
        p_target_kw=2500.0,
        q_target_kvar=0.0,
        e_nominal_kwh=capacity_kwh,
    )
    assert ok is True
    assert p_clipped == 2000.0
    assert "CLIPPED_MAX_DISCHARGE" in reason

    # Carga máxima: 0.5C = -1000 kW. Si se solicita -1500 kW, debe recortar a -1000 kW
    ok, p_clipped_ch, reason_ch = evaluator.evaluate_inverter_setpoint(
        p_target_kw=-1500.0,
        q_target_kvar=0.0,
        e_nominal_kwh=capacity_kwh,
    )
    assert ok is True
    assert p_clipped_ch == -1000.0
    assert "CLIPPED_MAX_CHARGE" in reason_ch


def test_safety_envelope_corrupted_baseline(tmp_path: Path):
    corrupted_file = tmp_path / "corrupted_baseline.json"
    corrupted_file.write_text("{ INVALID JSON CORRUPTED DATA !!!", encoding="utf-8")

    evaluator = SafetyEnvelopeEvaluator(baseline_path=corrupted_file)
    assert evaluator.baseline["cell_limits"]["voltage_min_v"] == 2.50
    assert evaluator.baseline["cell_limits"]["voltage_max_v"] == 3.65


def test_safety_envelope_missing_baseline(tmp_path: Path):
    missing_file = tmp_path / "non_existent_baseline.json"

    evaluator = SafetyEnvelopeEvaluator(baseline_path=missing_file)
    assert evaluator.baseline["rack_limits"]["dc_isolation_min_kohm"] == 500.0
