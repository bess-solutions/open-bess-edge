import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from open_bess_edge.control.ffr_droop import FFRDroopController


def ctrl(**kw):
    return FFRDroopController(p_nominal_kw=1000.0, **kw)


def test_deadband_insensitivity_both_sides_including_edges():
    c = ctrl()
    for i, f in enumerate([49.98, 50.02, 49.97, 50.03, 50.0]):     # 49.97 / 50.03 = borde exacto
        o = c.update(float(i), f, 0.0)
        assert o.p_kw == 0.0 and o.status == "IDLE_DEADBAND", f


def test_droop_gain_matches_spec():
    c = ctrl()
    o = c.update(0.0, 49.85, 0.0)
    assert o.gain_kw_per_hz == pytest.approx(666.6667, abs=1e-3)
    assert o.p_kw == pytest.approx(80.0, abs=1e-6) and o.status == "PRIMARY_DROOP_ACTIVE"
    assert c.update(1.0, 50.15, 0.0).p_kw == pytest.approx(-80.0, abs=1e-6)     # sobrefrecuencia: absorbe


def test_contingency_threshold_and_status():
    c = ctrl()
    o = c.update(0.0, 49.70, 0.0)
    assert o.contingency and o.status == "FFR_CONTINGENCY" and o.p_kw == pytest.approx(0.27 * 666.6667, abs=1e-3)
    assert not ctrl().update(0.0, 49.7001, 0.0).contingency
    o = c.update(1.0, 50.00, 0.0)
    assert not o.contingency and o.p_kw == 0.0


def test_saturates_at_nominal():
    c = ctrl()
    assert c.update(0.0, 47.0, 0.0).p_kw == 1000.0
    assert c.update(1.0, 53.0, 0.0).p_kw == -1000.0


def test_no_windup_with_first_order_plant():
    """Regresión v2: usar P medida como base creaba un integrador. Aquí la consigna es estacionaria."""
    c = ctrl()
    p_plant, outs = 0.0, []
    for i in range(600):
        o = c.update(i * 0.1, 49.90, 0.0)
        p_plant += (o.p_kw - p_plant) * (1 - math.exp(-0.1 / 0.15))
        outs.append(o.p_kw)
    assert max(outs) == pytest.approx(46.6667, abs=1e-3) and min(outs) == pytest.approx(46.6667, abs=1e-3)
    assert p_plant == pytest.approx(46.6667, abs=1e-2)


def test_load_relief_is_symmetric_and_instantaneous():
    c = ctrl()
    c._base = -500.0                                   # cargando 500 kW por despacho
    o = c.update(0.0, 49.85, -500.0)
    assert o.load_relief and o.p_base_kw == 0.0 and o.p_kw == pytest.approx(80.0)
    c2 = ctrl()
    c2._base = 400.0                                   # descargando por despacho y sube la frecuencia
    o = c2.update(0.0, 50.15, 400.0)
    assert o.load_relief and o.p_base_kw == 0.0 and o.p_kw == pytest.approx(-80.0)
    c3 = ctrl()
    c3._base = -300.0                                  # cargando y sube la frecuencia: no hay alivio, sigue cargando más
    o = c3.update(0.0, 50.15, -300.0)
    assert not o.load_relief and o.p_kw == pytest.approx(-380.0)


def test_base_follows_dispatch_with_ramp_limit_and_droop_does_not():
    c = ctrl(ramp_pct_per_min=6.0)                     # 6 %/min de 1000 kW = 1 kW/s
    c.update(0.0, 50.0, 0.0)
    o = c.update(10.0, 50.0, 500.0)
    assert o.p_base_kw == pytest.approx(10.0)          # 10 s * 1 kW/s
    o = c.update(20.0, 49.85, 500.0)                   # con evento: droop inmediato + base rampeada
    assert o.p_base_kw == pytest.approx(20.0) and o.p_droop_kw == pytest.approx(80.0)
    assert o.p_kw == pytest.approx(100.0)


def test_ramp_from_zero_on_first_cycle_and_reset():
    c = ctrl()
    assert c.update(0.0, 50.0, 800.0).p_base_kw == 0.0   # no salta al despacho en el primer ciclo
    c.reset(0.0)
    assert c.update(5.0, 50.0, 0.0).p_kw == 0.0


def test_invalid_frequency_hold_then_zero():
    c = ctrl(freq_invalid_hold_s=1.0)
    c.update(0.0, 49.85, 0.0)
    o = c.update(0.5, None, 0.0)
    assert o.status == "FREQ_INVALID_HOLD" and o.p_droop_kw == pytest.approx(80.0)
    o = c.update(1.6, math.nan, 0.0)
    assert o.status == "FREQ_INVALID" and o.p_kw == 0.0
    assert ctrl().update(0.0, None, 0.0).status == "FREQ_INVALID"
    assert ctrl().update(0.0, 0.0, 0.0).status == "FREQ_INVALID"           # 0 Hz: lectura basura, no contingencia
    assert ctrl().update(0.0, 80.0, 0.0).status == "FREQ_INVALID"


def test_disabled_controller_only_follows_base():
    c = ctrl(enabled=False)
    o = c.update(0.0, 49.0, 0.0)
    assert o.status == "DISABLED" and o.p_droop_kw == 0.0


def test_contingency_record_aporte_10s_and_2min():
    c = ctrl()
    c.update(0.0, 50.0, 0.0)
    c.observe_applied(0.0)
    for t in range(1, 130):
        o = c.update(float(t), 49.60, 0.0, wall=1000.0 + t)
        c.observe_applied(o.p_kw)
    c.update(130.0, 50.0, 0.0)
    recs = c.pop_finished()
    assert len(recs) == 1
    r = recs[0]
    assert r.direction == "UNDERFREQUENCY" and r.f_extreme_hz == pytest.approx(49.60)
    assert r.aporte_10s_kw == pytest.approx(0.37 * 666.6667, abs=1e-3) and r.aporte_2min_kw == r.aporte_10s_kw
    assert c.pop_finished() == []
    d = r.as_dict()
    assert d["duration_s"] == pytest.approx(129.0)


def test_constructor_validation():
    for kw in [dict(droop_r=0.0), dict(droop_r=1.5), dict(deadband_hz=-1.0), dict(deadband_hz=0.5, contingency_threshold_hz=0.3),
               dict(ramp_pct_per_min=0.0)]:
        with pytest.raises(ValueError):
            ctrl(**kw)
    with pytest.raises(ValueError):
        FFRDroopController(p_nominal_kw=0.0)


@settings(max_examples=300, deadline=None)
@given(f=st.floats(min_value=46.0, max_value=54.0), base=st.floats(min_value=-1000, max_value=1000))
def test_property_output_bounded_and_monotonic_in_frequency(f, base):
    c = ctrl()
    o = c.update(0.0, f, base)
    assert -1000.0 <= o.p_kw <= 1000.0 and math.isfinite(o.p_kw)
    lo = ctrl().update(0.0, f - 0.05, 0.0).p_droop_kw
    hi = ctrl().update(0.0, f, 0.0).p_droop_kw
    assert lo >= hi - 1e-9                       # menor frecuencia => igual o más inyección


@settings(max_examples=200, deadline=None)
@given(df=st.floats(min_value=0.0, max_value=4.0))
def test_property_droop_antisymmetric(df):
    up = ctrl().update(0.0, 50.0 + df, 0.0).p_droop_kw
    dn = ctrl().update(0.0, 50.0 - df, 0.0).p_droop_kw
    assert up == pytest.approx(-dn, abs=1e-6)
