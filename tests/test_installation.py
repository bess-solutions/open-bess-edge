"""Contexto de instalación BTM: restricciones dinámicas, peak shaving, medidor de red y BESS-GUARD-091."""
import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from open_bess_edge.config import InstallationConstraints, parse_config
from open_bess_edge.control.peak_shaving import site_window
from open_bess_edge.errors import ConfigError
from open_bess_edge.modbus.profile import load_profile
from open_bess_edge.models import NodeState
from open_bess_edge.runtime.health import HealthServer
from tests.conftest import make_cfg
from tests.harness import Harness

PLANT = {"p_nominal_kw": 1000.0, "e_nominal_kwh": 2000.0, "v_nominal_v": 400.0}


def btm_cfg(**over):
    base = dict(
        installation={"role": "btm_peak_shaving",
                      "constraints": {"max_grid_import_kw": 1200.0, "max_grid_export_kw": 0.0, "soc_reserve_pct": 20.0,
                                      "p_grid_timeout_s": 2.0},
                      "dispatch_sources": [{"type": "http_bearer"}],
                      "metadata": {"policy_compiler": "open-bess-sandbox", "rule_set_id": "CL-PEAK-TARIFF-2026",
                                   "status": "SUPUESTO"},
                      "accept_unverified_rule_set": True},
        grid_meter={"port": 1502}, volt_var={"mode": "DISABLED"})
    base.update(over)
    return make_cfg(**base)


def raw(**inst):
    return {"plant": PLANT, "volt_var": {"mode": "DISABLED"}, **inst}


# ------------------------------------------------------------------ configuración
@pytest.mark.parametrize("patch,msg", [
    ({"installation": {"role": "btm_peak_shaving"}, "grid_meter": {}}, "max_grid_import_kw"),
    ({"installation": {"role": "btm_peak_shaving", "constraints": {"max_grid_import_kw": 1000}}, "grid_meter": {},
      "ffr": {"enabled": True}}, "ffr.enabled=true"),
    ({"installation": {"constraints": {"max_grid_export_kw": 0.0}}}, "grid_meter"),
    ({"installation": {"constraints": {"max_grid_import_kw": 1000}}}, "grid_meter"),
    ({"installation": {"metadata": {"rule_set_id": "X", "status": "SUPUESTO"}}}, "accept_unverified_rule_set"),
    ({"installation": {"metadata": {"rule_set_id": "X", "status": "EN_EVALUACION"}}}, "EN_EVALUACION"),
    ({"installation": {"metadata": {"rule_set_id": "X", "status": "INVENTADO"}}}, "status"),
    ({"installation": {"constraints": {"max_grid_import_kw": -5}}, "grid_meter": {}}, "max_grid_import_kw"),
    ({"installation": {"constraints": {"soc_reserve_pct": 120}}}, "soc_reserve_pct"),
    ({"installation": {"typo": 1}}, "typo"),
    ({"dispatch_api": {"enabled": True}}, "dispatch_sources"),
    ({"installation": {"dispatch_sources": [{"type": "mqtt"}]}}, "type"),
])
def test_installation_config_rejections(patch, msg):
    with pytest.raises(ConfigError, match=msg):
        parse_config(raw(**patch))


def test_installation_config_accepts_and_derives_ffr():
    c = parse_config(raw(installation={"metadata": {"rule_set_id": "X", "status": "VIGENTE"}}))
    assert c.ffr_enabled is True and c.unverified_regulatory_rules is False        # sin rol: FFR habilitado
    b = btm_cfg()
    assert b.ffr_enabled is False and b.unverified_regulatory_rules is True
    assert parse_config(raw(installation={"role": "utility_sscc"})).ffr_enabled is True
    assert parse_config(raw(ffr={"enabled": False})).ffr_enabled is False


# ------------------------------------------------------------------ ventana dinámica (función pura)
def cons(**kw):
    return InstallationConstraints(**kw)


def test_site_window_examples():
    c = cons(max_grid_import_kw=1200.0, max_grid_export_kw=0.0, soc_reserve_pct=20.0)
    w = site_window(c, p_grid_kw=1500.0, p_bess_kw=0.0, soc_pct=60, dis_cap_kw=1000, chg_cap_kw=1000)
    assert (w.load_kw, w.p_shave_kw, w.dis_max_kw, w.chg_max_kw, w.shave_saturated) == (1500.0, 300.0, 1000.0, 0.0, False)
    w = site_window(c, p_grid_kw=900.0, p_bess_kw=300.0, soc_pct=60, dis_cap_kw=1000, chg_cap_kw=1000)   # L = 1200 (BESS ya descarga)
    assert w.load_kw == 1200.0 and w.p_shave_kw == 0.0 and w.chg_max_kw == 0.0 and w.dis_max_kw == 1000.0
    w = site_window(c, p_grid_kw=100.0, p_bess_kw=0.0, soc_pct=60, dis_cap_kw=1000, chg_cap_kw=1000)     # export 0: descarga <= L
    assert w.dis_max_kw == 100.0 and w.chg_max_kw == 1000.0
    w = site_window(c, p_grid_kw=-300.0, p_bess_kw=0.0, soc_pct=60, dis_cap_kw=1000, chg_cap_kw=1000)   # excedente FV: L<0
    assert w.dis_max_kw == 0.0
    w = site_window(c, p_grid_kw=1800.0, p_bess_kw=0.0, soc_pct=15, dis_cap_kw=1000, chg_cap_kw=1000)   # reserva de SOC
    assert w.dis_max_kw == 0.0 and w.shave_saturated is True
    w = site_window(c, p_grid_kw=2500.0, p_bess_kw=0.0, soc_pct=60, dis_cap_kw=1000, chg_cap_kw=1000)   # capacidad insuficiente
    assert w.shave_saturated is True
    w = site_window(cons(soc_reserve_pct=20.0), p_grid_kw=None, p_bess_kw=0.0, soc_pct=60, dis_cap_kw=1000, chg_cap_kw=1000)
    assert (w.dis_max_kw, w.chg_max_kw, w.p_shave_kw) == (1000.0, 1000.0, 0.0)          # sin medidor: sólo SOC


nums = st.floats(min_value=-5000, max_value=5000, allow_nan=False)


@settings(max_examples=500, deadline=None)
@given(p_grid=nums, p_bess=st.floats(min_value=-1000, max_value=1000), soc=st.floats(min_value=0, max_value=100),
       imp=st.floats(min_value=1, max_value=3000), exp=st.floats(min_value=0, max_value=500),
       frac=st.floats(min_value=0, max_value=1))
def test_property_window_never_worsens_the_violation(p_grid, p_bess, soc, imp, exp, frac):
    c = cons(max_grid_import_kw=imp, max_grid_export_kw=exp, soc_reserve_pct=20.0)
    w = site_window(c, p_grid_kw=p_grid, p_bess_kw=p_bess, soc_pct=soc, dis_cap_kw=1000.0, chg_cap_kw=1000.0)
    assert w.dis_max_kw >= 0 and w.chg_max_kw >= 0
    if soc <= 20.0:
        assert w.dis_max_kw == 0.0
    load = p_grid + p_bess
    for p in (-w.chg_max_kw, w.dis_max_kw, -w.chg_max_kw + frac * (w.chg_max_kw + w.dis_max_kw)):
        grid_after = load - p
        assert grid_after >= min(load, -exp) - 1e-6          # nunca exporta más de lo permitido (ni empeora)
        assert grid_after <= max(load, imp) + 1e-6           # nunca importa más de lo permitido (ni empeora)


# ------------------------------------------------------------------ extremo a extremo (nodo + PCS + medidor simulados)
pytestmark_e2e = pytest.mark.e2e


@pytest.fixture
async def h():
    hh = await Harness(btm_cfg(ffr={"ramp_pct_per_min": 6000.0})).start()
    hh.env.plant.site_load_kw = 800.0
    yield hh
    await hh.stop()


def grid(h):
    return h.env.plant.site_load_kw - h.env.plant.p_kw


@pytest.mark.e2e
async def test_peak_shaving_holds_the_import_limit_after_a_load_step(h):
    await h.cycle(8)
    assert abs(h.p_reg) == 0 and h.node.state is NodeState.RUNNING                      # bajo el umbral: no actúa
    h.env.plant.site_load_kw = 1500.0
    settle, p_max, first_cmd = None, 0.0, None
    for i in range(25):
        r = await h.cycle()
        first_cmd = r.p_setpoint_kw if first_cmd is None else first_cmd
        p_max = max(p_max, h.env.plant.p_kw)
        if settle is None and grid(h) <= 1215.0:
            settle = i + 1
    assert h.env.plant.p_kw == pytest.approx(300.0, abs=1.5)
    assert grid(h) <= 1201.0 + 1e-6                                                     # 1 kW de cuantización (truncado a 0)
    assert first_cmd == pytest.approx(300.0, abs=1.0)                                   # el lazo ordena la corrección completa en 1 ciclo
    assert settle is not None and settle <= 7                                           # 95 % de la corrección en <= 0,7 s (limita el PCS: tau 0,15 s)
    assert p_max <= 302.0                                                               # sin sobrepaso: no descarga de más
    h.env.plant.site_load_kw = 700.0                                                    # baja la carga: deja de descargar
    for _ in range(25):
        await h.cycle()
    assert h.p_reg == 0 and grid(h) == pytest.approx(700.0, abs=1.0)


@pytest.mark.e2e
async def test_no_export_limits_discharge_to_site_load(h):
    await h.cycle(8)
    h.env.plant.site_load_kw = 100.0
    h.node.set_dispatch(900.0, ttl_s=60.0)                                              # el EMS pide descargar 900 kW
    for _ in range(25):
        await h.cycle()
    assert h.env.plant.p_kw <= 100.0 + 1e-6 and grid(h) >= -1e-6                        # exportación 0


@pytest.mark.e2e
async def test_charging_is_limited_by_import_headroom(h):
    await h.cycle(8)
    h.env.plant.site_load_kw = 1100.0
    h.node.set_dispatch(-500.0, ttl_s=60.0)                                             # el EMS pide cargar 500 kW
    for _ in range(25):
        await h.cycle()
    assert h.env.plant.p_kw == pytest.approx(-100.0, abs=1.5) and grid(h) <= 1200.0 + 1.5


@pytest.mark.e2e
async def test_soc_reserve_blocks_discharge_and_reports_saturation(h):
    await h.cycle(8)
    h.env.plant.soc_pct = 15.0
    h.env.plant.site_load_kw = 1500.0
    await h.cycle(15)
    assert h.p_reg == 0 and any(e["kind"] == "SHAVE_SATURATED" for e in h.node.audit.ring)
    h.env.plant.soc_pct = 60.0
    await h.cycle(25)
    assert h.p_reg > 0 and any(e["kind"] == "SHAVE_RECOVERED" for e in h.node.audit.ring)


@pytest.mark.e2e
async def test_ffr_is_off_in_peak_shaving_role(h):
    await h.cycle(8)
    h.set_freq(49.5)
    r = await h.cycle(3)
    assert r.ffr_status == "DISABLED" and r.p_setpoint_kw == 0.0


@pytest.mark.e2e
async def test_meter_loss_forces_zero_after_timeout_and_recovers(h):
    await h.cycle(8)
    h.env.plant.site_load_kw = 1500.0
    await h.cycle(20)
    assert h.p_reg > 250
    await h.env.meter_server.stop()
    h.env.meter_server.kick_all()
    seen_before, seen_after = [], []
    for i in range(30):                                                                 # 3 s con el medidor caído
        r = await h.cycle()
        (seen_before if i < 19 else seen_after).append((i, "BESS-GUARD-091" in r.faults))
    assert not any(f for _, f in seen_before)                                           # dentro de la retención de 2 s no hay falta
    seen_after = [f for i, f in seen_after if i >= 22]                                  # tras 2 s + margen de 2 ciclos
    assert all(seen_after) and h.p_reg == 0 and r.state == "SAFE_STATE"
    await h.env.meter_server.start()
    h.node.meter.transport.port = h.env.meter_server.port
    for _ in range(80):
        r = await h.cycle(settle=0.02)
        if r.state == "RUNNING":
            break
    assert r.state == "RUNNING" and "BESS-GUARD-091" not in r.faults
    await h.cycle(25)
    assert h.env.plant.p_kw == pytest.approx(300.0, abs=1.5)


@pytest.mark.e2e
async def test_meter_never_available_keeps_output_at_zero():
    hh = Harness(btm_cfg())
    await hh.start(start_node=False)
    await hh.env.meter_server.stop()
    assert await hh.node.start(timeout_s=1.0)
    try:
        hh.env.plant.site_load_kw = 2000.0
        for _ in range(12):
            r = await hh.cycle()
        assert "BESS-GUARD-091" in r.faults and hh.p_reg == 0 and r.status == "SAFETY_DATA_INTERLOCK"
    finally:
        await hh.stop()


@pytest.mark.e2e
async def test_meter_profile_without_p_grid_binding_is_refused_at_start():
    hh = Harness(btm_cfg(grid_meter={"port": 1502, "profile": "huawei_sun2000"}))
    await hh.start(start_node=False)
    try:
        with pytest.raises(ConfigError, match="p_grid_kw"):
            await hh.node.start(timeout_s=1.0)
    finally:
        await hh.env.stop()


@pytest.mark.e2e
async def test_unverified_rule_set_is_audited_and_exposed_in_status(h):
    kinds = {e["kind"]: e["data"] for e in h.node.audit.ring}
    assert kinds["UNVERIFIED_RULE_SET_ACCEPTED"]["status"] == "SUPUESTO"
    assert kinds["RULE_SET"]["rule_set_id"] == "CL-PEAK-TARIFF-2026" and kinds["NODE_START"]["role"] == "btm_peak_shaving"
    st_ = HealthServer(h.node).status()
    assert st_["unverified_regulatory_rules"] is True and st_["installation"]["role"] == "btm_peak_shaving"
    assert st_["installation"]["constraints"]["max_grid_import_kw"] == 1200.0 and st_["installation"]["grid_meter_connected"] is True


@pytest.mark.e2e
async def test_dispatch_program_expires_after_ttl(h):
    await h.cycle(8)
    h.env.plant.site_load_kw = 400.0
    assert h.node.set_dispatch(-150.0, ttl_s=3.0) == -150.0
    for _ in range(15):
        r = await h.cycle()
    assert r.p_setpoint_kw == pytest.approx(-150.0, abs=1.0)
    for _ in range(25):
        r = await h.cycle()
    assert r.p_setpoint_kw == 0.0
    for bad in (0.0, -1.0, math.nan, math.inf):
        with pytest.raises(ValueError):
            h.node.set_dispatch(10.0, ttl_s=bad)


@pytest.mark.e2e
async def test_physical_safety_still_wins_over_installation_constraints(h):
    await h.cycle(8)
    h.env.plant.site_load_kw = 1500.0
    await h.cycle(15)
    assert h.p_reg > 0
    h.env.plant.overrides["cell_t_max_c"] = 60.0                                        # disparo térmico
    r = await h.cycle()
    assert r.state == "TRIPPED" and h.p_reg == 0


def test_all_five_guard_codes_still_documented():
    from open_bess_edge.safety import envelope
    assert envelope.G091 == "BESS-GUARD-091"
    assert load_profile("open_bess_edge_meter_reference").telemetry_signals == ("p_grid_kw",)


def test_shipped_btm_example_config_is_valid(tmp_path):
    from pathlib import Path

    from open_bess_edge.config import load_config
    c = load_config(Path(__file__).resolve().parents[1] / "config" / "installation_btm_peak_shaving.yaml")
    assert c.installation.role == "btm_peak_shaving" and c.ffr_enabled is False and c.unverified_regulatory_rules is True
    assert c.installation.constraints.max_grid_export_kw == 0.0 and c.grid_meter is not None
