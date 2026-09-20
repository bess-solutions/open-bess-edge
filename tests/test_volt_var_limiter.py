import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from open_bess_edge.config import ReactiveMode
from open_bess_edge.control.limiter import apply_limits
from open_bess_edge.control.volt_var import VoltVarController
from open_bess_edge.models import SafetyVerdict


def vv(**kw):
    base = dict(q_max_kvar=600.0, v_nominal_v=400.0, p_nominal_kw=1000.0)
    base.update(kw)
    return VoltVarController(**base)


def test_qv_curve_deadband_and_slope():
    c = vv()
    assert c.update(0.0, 402.0, 0.0).q_kvar == 0.0 and c.update(0.1, 392.0, 0.0).q_kvar == 0.0
    o = c.update(0.2, 380.0, 0.0)
    assert o.status == "UNDERVOLTAGE_INJECTING_Q" and o.q_kvar == pytest.approx(0.03 * 10 * 600)
    o = c.update(0.3, 420.0, 0.0)
    assert o.status == "OVERVOLTAGE_ABSORBING_Q" and o.q_kvar == pytest.approx(-0.03 * 10 * 600)
    assert c.update(0.4, 300.0, 0.0).q_kvar == 600.0 and c.update(0.5, 500.0, 0.0).q_kvar == -600.0


def test_qv_invalid_voltage_hold_then_zero():
    c = vv(invalid_hold_s=1.0)
    c.update(0.0, 380.0, 0.0)
    o = c.update(0.5, None, 0.0)
    assert o.status == "V_INVALID_HOLD" and o.q_kvar == pytest.approx(180.0)
    o = c.update(1.5, math.nan, 0.0)
    assert o.status == "V_INVALID" and o.q_kvar == 0.0
    assert vv().update(0.0, -5.0, 0.0).status == "V_INVALID"


def test_fixed_q_and_disabled():
    assert vv(mode=ReactiveMode.FIXED_Q, fixed_q_kvar=250.0).update(0, None, 0).q_kvar == 250.0
    assert vv(mode=ReactiveMode.FIXED_Q, fixed_q_kvar=9999.0).update(0, None, 0).q_kvar == 600.0
    assert vv(mode=ReactiveMode.DISABLED).update(0, 300.0, 500.0).q_kvar == 0.0


def test_power_factor_signs():
    cap = vv(mode=ReactiveMode.POWER_FACTOR, power_factor=0.95, pf_excitation="capacitive")
    ind = vv(mode=ReactiveMode.POWER_FACTOR, power_factor=0.95, pf_excitation="inductive")
    q = 1000.0 * math.tan(math.acos(0.95))
    assert cap.update(0, 400.0, 1000.0).q_kvar == pytest.approx(min(q, 600.0)) and ind.update(0, 400.0, 1000.0).q_kvar < 0
    assert cap.update(0.1, 400.0, 0.0).q_kvar == 0.0
    assert cap.update(0.2, 400.0, -1000.0).q_kvar > 0                 # también al cargar (usa |P|)


def test_cos_phi_p_curve_interpolates():
    c = vv(mode=ReactiveMode.COS_PHI_P, cos_phi_p_curve=((0.0, 1.0), (0.5, 1.0), (1.0, 0.9)), cos_phi_p_excitation="inductive",
           q_max_kvar=900.0)
    assert c.update(0, 400, 400.0).q_kvar == 0.0                       # P/Pn=0.4 -> cosφ=1
    o = c.update(0.1, 400, 1000.0)
    assert o.q_kvar == pytest.approx(-1000.0 * math.tan(math.acos(0.9)), rel=1e-6)
    mid = c.update(0.2, 400, 750.0).q_kvar
    assert -750.0 * math.tan(math.acos(0.9)) < mid < 0


def test_capability_circle_priority_to_p():
    c = vv(q_max_kvar=600.0, s_max_kva=1100.0, mode=ReactiveMode.FIXED_Q, fixed_q_kvar=600.0)
    assert c.update(0, 400, 1000.0).q_kvar == pytest.approx(math.sqrt(1100**2 - 1000**2))
    assert c.update(1, 400, 1100.0).q_kvar == pytest.approx(0.0, abs=1e-9)


def test_q_ramp_limit():
    c = vv(mode=ReactiveMode.FIXED_Q, fixed_q_kvar=500.0, q_ramp_kvar_per_s=100.0)
    c.update(0.0, 400, 0.0)
    assert c.update(1.0, 400, 0.0).q_kvar == pytest.approx(100.0)
    assert c.update(2.0, 400, 0.0).q_kvar == pytest.approx(200.0)


def test_constructor_validation():
    for kw in [dict(q_max_kvar=-1.0), dict(v_nominal_v=0.0), dict(p_nominal_kw=0.0), dict(power_factor=0.0)]:
        with pytest.raises(ValueError):
            vv(**kw)


@settings(max_examples=300, deadline=None)
@given(v=st.floats(min_value=100, max_value=600), p=st.floats(min_value=-1500, max_value=1500))
def test_property_q_within_capability(v, p):
    c = vv(q_max_kvar=600.0, s_max_kva=1166.0)
    q = c.update(0.0, v, p).q_kvar
    assert abs(q) <= 600.0 + 1e-9
    assert q * q + min(abs(p), 1166.0) ** 2 <= 1166.0 ** 2 + 1e-6


def verdict(**kw):
    d = dict(faults=(), allow_output=True, p_discharge_max_kw=800.0, p_charge_max_kw=300.0, derate_factor=1.0, tripped=False)
    d.update(kw)
    return SafetyVerdict(**d)


def test_limiter_clips_and_flags():
    c = apply_limits(1000.0, 100.0, verdict(), s_max_kva=1166.0, q_max_kvar=600.0)
    assert c.p_kw == 800.0 and c.p_clipped and c.reason == "CLIPPED"
    c = apply_limits(-900.0, 0.0, verdict(), s_max_kva=1166.0, q_max_kvar=600.0)
    assert c.p_kw == -300.0
    c = apply_limits(100.0, 50.0, verdict(), s_max_kva=1166.0, q_max_kvar=600.0)
    assert (c.p_kw, c.q_kvar, c.reason) == (100.0, 50.0, "OK")


def test_limiter_interlock_and_non_finite():
    c = apply_limits(500.0, 100.0, verdict(allow_output=False, p_discharge_max_kw=0, p_charge_max_kw=0),
                     s_max_kva=1166.0, q_max_kvar=600.0)
    assert (c.p_kw, c.q_kvar, c.reason) == (0.0, 0.0, "SAFETY_INTERLOCK")
    for bad in (math.nan, math.inf):
        c = apply_limits(bad, 0.0, verdict(), s_max_kva=1166.0, q_max_kvar=600.0)
        assert (c.p_kw, c.q_kvar, c.reason) == (0.0, 0.0, "NON_FINITE_SETPOINT")
        c = apply_limits(0.0, bad, verdict(), s_max_kva=1166.0, q_max_kvar=600.0)
        assert c.reason == "NON_FINITE_SETPOINT"


def test_limiter_q_capability_reduces_with_p():
    c = apply_limits(800.0, 600.0, verdict(), s_max_kva=1000.0, q_max_kvar=600.0)
    assert c.q_kvar == pytest.approx(600.0) and c.q_clipped is False
    c = apply_limits(800.0, 700.0, verdict(p_discharge_max_kw=900), s_max_kva=1000.0, q_max_kvar=800.0)
    assert c.q_kvar == pytest.approx(600.0)
