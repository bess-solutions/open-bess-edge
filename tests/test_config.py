import pytest
from tests.conftest import make_cfg

from open_bess_edge.config import ReactiveMode, load_config, parse_config, reference_config
from open_bess_edge.errors import ConfigError

BASE = {"plant": {"p_nominal_kw": 1000, "e_nominal_kwh": 2000, "v_nominal_v": 400}, "volt_var": {"mode": "DISABLED"}}


def with_(**kw):
    d = {k: dict(v) for k, v in BASE.items()}
    for k, v in kw.items():
        d.setdefault(k, {}).update(v)
    return d


def test_reference_config_valid():
    c = reference_config()
    assert c.plant.p_discharge_cap_kw == 1000.0
    assert c.s_max_kva == pytest.approx(1166.19, abs=0.01)


@pytest.mark.parametrize("patch", [
    {"plant": {"typo": 1}},                        # clave desconocida
    {"ffr": {"droop_r": 0.5}},                     # estatismo fuera del rango 2–5 %
    {"ffr": {"droop_r": 0.01}},
    {"ffr": {"deadband_hz": 0.5, "contingency_threshold_hz": 0.3}},
    {"plant": {"p_nominal_kw": -5}},
    {"modbus": {"port": 70000}},
    {"modbus": {"port": "abc"}},
    {"modbus": {"reconnect_min_s": 10, "reconnect_max_s": 1}},
    {"runtime": {"cycle_ms": 1}},
    {"runtime": {"comm_loss_hold_s": 0.01}},
    {"runtime": {"ffr_latency_budget_ms": 10, "cycle_ms": 100}},
    {"dispatch": {"p_base_kw": 5000}},
    {"volt_var": {"mode": "VOLT_VAR_Q_V", "q_max_kvar": 0}},
    {"plant": {"s_max_kva": 1100}, "volt_var": {"mode": "DISABLED", "q_max_kvar": 5000}},
    {"volt_var": {"mode": "COS_PHI_P", "q_max_kvar": 100, "cos_phi_p_curve": [[0.0, 1.0]]}},
    {"volt_var": {"mode": "COS_PHI_P", "q_max_kvar": 100, "cos_phi_p_curve": [[0.5, 1.0], [0.4, 0.9]]}},
    {"volt_var": {"mode": "COS_PHI_P", "q_max_kvar": 100, "cos_phi_p_curve": [[0.0, 1.0], [1.0, 0.2]]}},
    {"node": {"device_id": "bad id!"}},
    {"safety": {"limits": {"required_signals": ["nope"]}}},
    {"safety": {"limits": {"cell": {"voltage_min_v": 3.7}}}},
    {"safety": {"limits": {"soc": {"min_pct": 90, "max_pct": 10}}}},
])
def test_invalid_configs_rejected(patch):
    with pytest.raises(ConfigError):
        parse_config(with_(**patch))


def test_root_must_be_mapping():
    with pytest.raises(ConfigError):
        parse_config([1, 2])


def test_load_config_errors(tmp_path, monkeypatch):
    with pytest.raises(ConfigError, match="no encontrado"):
        load_config(tmp_path / "nope.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("plant: [unclosed")
    with pytest.raises(ConfigError, match="YAML"):
        load_config(bad)
    monkeypatch.delenv("OBE_CONFIG", raising=False)
    with pytest.raises(ConfigError, match="OBE_CONFIG"):
        load_config(None)
    ok = tmp_path / "ok.yaml"
    ok.write_text("plant: {p_nominal_kw: 500, e_nominal_kwh: 1000, v_nominal_v: 400}\nvolt_var: {mode: DISABLED}\n")
    monkeypatch.setenv("OBE_CONFIG", str(ok))
    assert load_config(None).plant.p_nominal_kw == 500
    invalid_type = tmp_path / "t.yaml"
    invalid_type.write_text("plant: {p_nominal_kw: abc, e_nominal_kwh: 1, v_nominal_v: 1}\n")
    with pytest.raises(ConfigError, match="p_nominal_kw"):
        load_config(invalid_type)


def test_baseline_path_strict(tmp_path):
    y = tmp_path / "c.yaml"
    y.write_text("plant: {p_nominal_kw: 500, e_nominal_kwh: 1000, v_nominal_v: 400}\nvolt_var: {mode: DISABLED}\n"
                 "safety: {baseline_path: missing.json}\n")
    with pytest.raises(ConfigError, match="no encontrado"):
        load_config(y)
    (tmp_path / "missing.json").write_text("{ no es json")
    with pytest.raises(ConfigError, match="JSON"):
        load_config(y)
    (tmp_path / "missing.json").write_text('{"cell_limits": {"voltage_min_v": 2.6, "bogus": 1}}')
    with pytest.raises(ConfigError):
        load_config(y)


def test_shipped_baseline_and_example_config_load():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    c = load_config(root / "config" / "edge_config.yaml")
    assert c.safety.limits.cell.voltage_min_v == 2.5
    assert c.safety.limits.rack.dc_isolation_min_kohm == 500.0
    assert c.ffr.deadband_hz == 0.03 and c.ffr.droop_r == 0.03
    assert c.volt_var.mode is ReactiveMode.VOLT_VAR_Q_V


def test_capacity_caps_use_c_rate():
    c = make_cfg(plant={"e_nominal_kwh": 1000.0, "max_charge_c_rate": 0.5, "max_discharge_c_rate": 1.0})
    assert c.plant.p_charge_cap_kw == 500.0 and c.plant.p_discharge_cap_kw == 1000.0
