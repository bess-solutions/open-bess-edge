import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from open_bess_edge.models import Severity, Telemetry
from open_bess_edge.safety.envelope import (
    G001,
    G002,
    G003,
    G004,
    G005,
    G006,
    G007,
    G008,
    G009,
    G010,
    G020,
    G021,
    G090,
    SafetyEnvelope,
)
from open_bess_edge.safety.limits import load_limits
from tests.conftest import make_cfg, tel


def env(**limits):
    cfg = make_cfg(safety={"limits": limits} if limits else {})
    return SafetyEnvelope(cfg.safety.limits, cfg.plant), cfg


def test_normal_operation_full_limits():
    e, cfg = env()
    v = e.evaluate(tel(), 0.0)
    assert v.status == "SAFE_NORMAL" and v.allow_output and not v.tripped
    assert v.p_discharge_max_kw == 1000.0 and v.p_charge_max_kw == 1000.0 and v.faults == ()


@pytest.mark.parametrize("kw,code", [
    (dict(cell_v_min_v=2.49), G001), (dict(cell_v_max_v=3.66, cell_v_min_v=3.2), G002),
    (dict(cell_t_max_c=50.1), G003), (dict(isolation_kohm=499.9), G004)])
def test_trip_guards_latch_and_zero_output(kw, code):
    e, _ = env()
    v = e.evaluate(tel(**kw), 0.0)
    assert code in v.codes and v.tripped and not v.allow_output
    assert v.p_discharge_max_kw == 0 and v.p_charge_max_kw == 0 and v.status == "CRITICAL_TRIP"
    # el disparo permanece aunque la medida vuelva a la normalidad
    v2 = e.evaluate(tel(), 1.0)
    assert code in v2.codes and not v2.allow_output


@pytest.mark.parametrize("kw", [dict(cell_v_min_v=2.5), dict(cell_v_max_v=3.65, cell_v_min_v=3.6),
                                dict(cell_t_max_c=50.0), dict(isolation_kohm=500.0)])
def test_exact_limit_is_not_a_trip(kw):
    e, _ = env()
    assert not e.evaluate(tel(**kw), 0.0).tripped


def test_reset_requires_cleared_with_hysteresis():
    e, _ = env()
    e.evaluate(tel(cell_t_max_c=55.0), 0.0)
    ok, msg = e.reset_trips(1.0)                       # todavía caliente
    assert not ok and "BESS-GUARD-003" in msg
    e.evaluate(tel(cell_t_max_c=49.0), 2.0)            # bajo el límite pero dentro de la histéresis (2 °C)
    assert not e.reset_trips(2.0)[0]
    e.evaluate(tel(cell_t_max_c=40.0), 3.0)
    ok, msg = e.reset_trips(3.0)
    assert ok
    assert e.evaluate(tel(cell_t_max_c=40.0), 4.0).allow_output


def test_reset_without_telemetry_refused():
    e, _ = env()
    e.evaluate(tel(cell_t_max_c=55.0), 0.0)
    e.evaluate(None, 1.0)
    ok, msg = e.reset_trips(1.0)
    assert not ok and "telemetría" in msg


def test_reset_noop_when_nothing_latched():
    e, _ = env()
    assert e.reset_trips(0.0)[0]


def test_debounce():
    e, _ = env(timing={"trip_debounce_cycles": 3})
    assert not e.evaluate(tel(cell_t_max_c=60.0), 0.0).tripped
    assert not e.evaluate(tel(cell_t_max_c=60.0), 0.1).tripped
    assert e.evaluate(tel(cell_t_max_c=60.0), 0.2).tripped
    e2, _ = env(timing={"trip_debounce_cycles": 3})
    e2.evaluate(tel(cell_t_max_c=60.0), 0.0)
    e2.evaluate(tel(), 0.1)                            # se interrumpe: reinicia contador
    e2.evaluate(tel(cell_t_max_c=60.0), 0.2)
    assert not e2.evaluate(tel(cell_t_max_c=60.0), 0.3).tripped


def test_auto_reset_after_timeout_only_when_clear():
    e, _ = env(timing={"auto_reset_after_s": 10.0})
    e.evaluate(tel(cell_t_max_c=60.0), 0.0)
    assert e.evaluate(tel(cell_t_max_c=60.0), 20.0).tripped          # sigue caliente: no libera
    e.evaluate(tel(cell_t_max_c=30.0), 21.0)
    assert not e.evaluate(tel(cell_t_max_c=30.0), 31.0).tripped      # despejado y transcurrido el plazo


def test_imbalance_warning_only():
    e, _ = env()
    v = e.evaluate(tel(cell_v_min_v=3.20, cell_v_max_v=3.26), 0.0)
    assert G005 in v.codes and v.allow_output and v.faults[0].severity is Severity.WARNING


def test_thermal_derate_with_hysteresis():
    e, _ = env()
    assert e.evaluate(tel(cell_t_max_c=44.9), 0).derate_factor == 1.0
    v = e.evaluate(tel(cell_t_max_c=45.0), 1)
    assert G006 in v.codes and v.derate_factor == 0.5 and v.p_discharge_max_kw == 500.0 and v.p_charge_max_kw == 500.0
    assert e.evaluate(tel(cell_t_max_c=43.5), 2).derate_factor == 0.5    # dentro de histéresis
    assert e.evaluate(tel(cell_t_max_c=42.9), 3).derate_factor == 1.0


def test_low_temperature_inhibits_charge_only():
    e, _ = env()
    v = e.evaluate(tel(cell_t_min_c=-11.0), 0)
    assert G007 in v.codes and v.p_charge_max_kw == 0.0 and v.p_discharge_max_kw == 1000.0
    assert e.evaluate(tel(cell_t_min_c=-9.0), 1).p_charge_max_kw == 0.0   # histéresis
    assert e.evaluate(tel(cell_t_min_c=-7.0), 2).p_charge_max_kw == 1000.0


def test_ambient_and_string_voltage_optional_guards():
    e, _ = env(rack={"max_ambient_temp_c": 45.0, "string_voltage_min_v": 1040.0, "string_voltage_max_v": 1518.4})
    assert G009 in e.evaluate(tel(ambient_c=46.0, string_v_v=1300.0), 0).codes
    v = e.evaluate(tel(string_v_v=1600.0), 1)
    assert G008 in v.codes and v.tripped


def test_soc_limits_hard_and_taper():
    e, _ = env()
    v = e.evaluate(tel(soc_pct=5.0), 0)
    assert G010 in v.codes and v.p_discharge_max_kw == 0 and v.p_charge_max_kw == 1000.0
    v = e.evaluate(tel(soc_pct=95.0), 1)
    assert v.p_charge_max_kw == 0 and v.p_discharge_max_kw == 1000.0
    e2, _ = env(soc={"min_pct": 10.0, "max_pct": 90.0, "taper_pct": 10.0})
    assert e2.evaluate(tel(soc_pct=15.0), 0).p_discharge_max_kw == pytest.approx(500.0)
    assert e2.evaluate(tel(soc_pct=85.0), 1).p_charge_max_kw == pytest.approx(500.0)
    assert e2.evaluate(tel(soc_pct=50.0), 2).p_charge_max_kw == 1000.0


@pytest.mark.parametrize("sig", ["soc_pct", "cell_v_min_v", "cell_v_max_v", "cell_t_max_c", "isolation_kohm"])
@pytest.mark.parametrize("bad", [None, math.nan, math.inf, -math.inf])
def test_required_signal_invalid_is_fail_closed(sig, bad):
    e, _ = env()
    v = e.evaluate(tel(**{sig: bad}), 0)
    assert not v.allow_output and G090 in v.codes and not v.tripped
    assert v.p_discharge_max_kw == 0 and v.p_charge_max_kw == 0
    assert v.status == "DATA_FAULT"


@pytest.mark.parametrize("kw", [dict(cell_v_min_v=0.0), dict(cell_v_max_v=9.0), dict(cell_t_max_c=500.0),
                                dict(soc_pct=101.0), dict(soc_pct=-1.0), dict(isolation_kohm=-5.0),
                                dict(cell_v_min_v=3.3, cell_v_max_v=3.2)])
def test_implausible_values_are_data_faults_not_safe_values(kw):
    e, _ = env()
    v = e.evaluate(tel(**kw), 0)
    assert not v.allow_output and G090 in v.codes


def test_data_fault_recovers_after_n_valid_cycles():
    e, _ = env(timing={"recovery_valid_cycles": 3})
    assert not e.evaluate(tel(soc_pct=math.nan), 0).allow_output
    assert not e.evaluate(tel(), 1).allow_output
    assert not e.evaluate(tel(), 2).allow_output
    assert e.evaluate(tel(), 3).allow_output
    e.evaluate(tel(soc_pct=math.nan), 4)
    assert not e.evaluate(tel(), 5).allow_output               # el contador se reinició


def test_no_telemetry_and_stale_telemetry():
    e, _ = env()
    assert not e.evaluate(None, 0).allow_output
    assert not e.evaluate(tel(t_mono=0.0), 10.0, max_age_s=1.0).allow_output
    e2, _ = env()
    assert e2.evaluate(tel(t_mono=9.5), 10.0, max_age_s=1.0).allow_output


def test_grid_alarms_only_warn():
    e, _ = env(grid={"f_alarm_low_hz": 49.0, "f_alarm_high_hz": 51.0, "v_alarm_low_pu": 0.9, "v_alarm_high_pu": 1.1})
    v = e.evaluate(tel(frequency_hz=48.5, v_grid_v=450.0), 0)
    assert G020 in v.codes and G021 in v.codes and v.allow_output
    assert e.evaluate(tel(), 1).faults == ()
    # sin umbrales configurados no hay alarma
    e2, _ = env()
    assert e2.evaluate(tel(frequency_hz=40.0, v_grid_v=100.0), 0).allow_output


def test_c_rate_caps_from_plant():
    cfg = make_cfg(plant={"e_nominal_kwh": 400.0})     # 400 kWh * 1C = 400 kW < 1000 kW PCS
    e = SafetyEnvelope(cfg.safety.limits, cfg.plant)
    v = e.evaluate(tel(), 0)
    assert v.p_discharge_max_kw == 400.0 and v.p_charge_max_kw == 200.0


def test_load_limits_strict(tmp_path):
    from pathlib import Path

    from open_bess_edge.errors import ConfigError
    lim = load_limits(Path(__file__).resolve().parents[1] / "data" / "bess_safety_baseline.json")
    assert lim.cell.voltage_max_v == 3.65 and lim.rack.string_voltage_max_v == 1518.4
    for content, msg in [("", "JSON"), ("[]", "objeto"), ('{"cell": {"nope": 1}}', "inválido")]:
        f = tmp_path / "b.json"
        f.write_text(content)
        with pytest.raises(ConfigError, match=msg):
            load_limits(f)
    with pytest.raises(ConfigError, match="no encontrado"):
        load_limits(tmp_path / "x.json")


finite = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e4, max_value=1e4)
maybe = st.one_of(finite, st.just(math.nan), st.just(math.inf), st.none())


@settings(max_examples=400, deadline=None)
@given(v_min=maybe, v_max=maybe, t=maybe, iso=maybe, soc=maybe, f=maybe, v=maybe)
def test_property_verdict_invariants(v_min, v_max, t, iso, soc, f, v):
    e, cfg = env()
    verdict = e.evaluate(Telemetry(0.0, 0.0, frequency_hz=f, v_grid_v=v, soc_pct=soc, cell_v_min_v=v_min,
                                   cell_v_max_v=v_max, cell_t_max_c=t, isolation_kohm=iso), 0.0)
    assert 0.0 <= verdict.p_discharge_max_kw <= cfg.plant.p_discharge_cap_kw
    assert 0.0 <= verdict.p_charge_max_kw <= cfg.plant.p_charge_cap_kw
    ok = lambda x: x is not None and math.isfinite(x)  # noqa: E731
    # Nunca se permite salida con un dato requerido no válido.
    if not all(ok(x) for x in (v_min, v_max, t, iso, soc)):
        assert not verdict.allow_output
    if not verdict.allow_output:
        assert verdict.p_discharge_max_kw == 0 and verdict.p_charge_max_kw == 0
    if verdict.tripped:
        assert not verdict.allow_output
