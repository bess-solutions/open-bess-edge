
import pytest
from tests.conftest import make_cfg
from tests.harness import Harness

from open_bess_edge.errors import ConfigError
from open_bess_edge.modbus.profile import load_profile
from open_bess_edge.models import NodeState

pytestmark = [pytest.mark.e2e]


@pytest.fixture
async def h():
    hh = await Harness().start()
    yield hh
    await hh.stop()


async def test_startup_forces_zero_then_validates_before_running(h):
    assert h.node.state is NodeState.STARTING and h.p_reg == 0
    r1 = await h.cycle()
    r2 = await h.cycle()
    assert r1.status == "STARTUP_VALIDATING" and r2.status == "STARTUP_VALIDATING" and h.p_reg == 0
    r3 = await h.cycle()
    assert r3.state == "RUNNING" and r3.status == "OK"


async def test_startup_never_commands_output_even_under_contingency(h):
    h.set_freq(49.5)
    for _ in range(2):
        await h.cycle()
        assert h.p_reg == 0
    r = await h.cycle()
    assert r.state == "RUNNING" and r.p_setpoint_kw > 0


async def test_idle_at_nominal(h):
    await h.cycle(5)
    r = await h.cycle()
    assert (r.p_setpoint_kw, r.q_setpoint_kvar, r.ffr_status) == (0.0, 0.0, "IDLE_DEADBAND")
    assert r.safety_status == "SAFE_NORMAL" and h.p_reg == 0


async def test_contingency_closed_loop_stable_and_recovers(h):
    await h.cycle(4)
    h.set_freq(49.65)
    r = await h.cycle()
    assert r.is_ffr_emergency and r.status == "FFR_CONTINGENCY"
    assert r.p_setpoint_kw == pytest.approx(213.0, abs=0.5) and h.p_reg == 213      # trunca 213.33 hacia 0
    for _ in range(300):                                    # 30 s: sin integrador aunque la planta siga la consigna
        r = await h.cycle()
    assert r.p_setpoint_kw == pytest.approx(213.33, abs=0.4)
    assert h.env.plant.p_kw == pytest.approx(213.0, abs=1.0)
    h.set_freq(50.0)
    r = await h.cycle()
    assert r.p_setpoint_kw == 0.0 and not r.is_ffr_emergency and h.p_reg == 0


async def test_overfrequency_absorbs_and_respects_soc_limit():
    hh = await Harness().start()
    try:
        await hh.cycle(4)
        hh.set_freq(50.35)
        r = await hh.cycle()
        assert r.p_setpoint_kw == pytest.approx(-213.0, abs=0.5)
        hh.env.plant.soc_pct = 95.0                             # batería llena: prohibido cargar
        r = await hh.cycle()
        assert r.p_setpoint_kw == 0.0 and "BESS-GUARD-010" in r.faults
    finally:
        await hh.stop()


async def test_low_soc_blocks_discharge_but_allows_charge(h):
    await h.cycle(4)
    h.env.plant.soc_pct = 4.0
    h.set_freq(49.6)
    r = await h.cycle()
    assert r.p_setpoint_kw == 0.0
    h.set_freq(50.4)
    assert (await h.cycle()).p_setpoint_kw < 0


async def test_volt_var_written_and_sign(h):
    await h.cycle(4)
    h.set_volt(380.0)
    r = await h.cycle()
    assert r.q_setpoint_kvar == pytest.approx(180.0) and h.q_reg == 180
    h.set_volt(420.0)
    r = await h.cycle()
    assert r.q_setpoint_kvar == pytest.approx(-180.0) and h.q_reg == -180


async def test_trip_zeroes_output_latches_and_reset_resumes(h):
    await h.cycle(4)
    h.set_freq(49.6)
    r = await h.cycle()
    assert h.p_reg > 0
    h.env.plant.overrides["cell_t_max_c"] = 58.0
    r = await h.cycle()
    assert r.status == "SAFETY_TRIP_INTERLOCK" and r.state == "TRIPPED" and "BESS-GUARD-003" in r.faults
    assert h.p_reg == 0 and r.p_setpoint_kw == 0.0
    h.env.plant.overrides["cell_t_max_c"] = 30.0
    for _ in range(10):
        r = await h.cycle()
        assert r.state == "TRIPPED" and h.p_reg == 0          # enclavado aunque la temperatura baje
    ok, msg = h.node.request_reset()
    assert ok, msg
    seen = [(await h.cycle()).status for _ in range(4)]
    assert seen[0] == "STARTUP_VALIDATING"
    assert seen[-1] == "FFR_CONTINGENCY" and h.p_reg > 0
    assert h.node.metrics.trips == 1


async def test_reset_refused_while_condition_active(h):
    await h.cycle(4)
    h.env.plant.overrides["isolation_kohm"] = 100.0
    await h.cycle()
    ok, msg = h.node.request_reset()
    assert not ok and "BESS-GUARD-004" in msg


@pytest.mark.parametrize("override", [{"cell_v_min_v": 0.0}, {"soc_pct": 120.0}, {"cell_t_max_c": 400.0}])
async def test_implausible_data_forces_zero_and_recovers(h, override):
    await h.cycle(4)
    h.set_freq(49.6)
    await h.cycle()
    assert h.p_reg > 0
    h.env.plant.overrides.update(override)
    r = await h.cycle()
    assert r.status in ("SAFETY_DATA_INTERLOCK", "SAFETY_TRIP_INTERLOCK") and h.p_reg == 0
    h.env.plant.overrides.clear()
    if r.state == "TRIPPED":
        return                                                # un valor 0 V de celda es además una subtensión
    for _ in range(8):
        r = await h.cycle()
    assert r.state == "RUNNING" and h.p_reg > 0


async def test_short_comm_glitch_holds_last_setpoint_without_dropping_ffr(h):
    await h.cycle(4)
    h.set_freq(49.6)
    await h.cycle(3)
    before = h.p_reg
    assert before > 0
    await h.env.server.stop()
    h.env.server.kick_all()
    statuses = []
    for _ in range(10):                                       # 1.0 s < comm_loss_hold_s (2.0)
        statuses.append((await h.cycle()).status)
    assert set(statuses) == {"COMM_HOLD"} and h.node.state is NodeState.DEGRADED
    assert h.p_reg == before                                  # el PCS conserva la última consigna
    await h.env.server.start()
    h.node.plant.transport.port = h.env.server.port
    for _ in range(60):
        r = await h.cycle(settle=0.02)
        if r.state == "RUNNING":
            break
    assert r.state == "RUNNING" and h.p_reg > 0


async def test_long_comm_loss_enters_safe_state_and_recovers_with_zero_first(h):
    await h.cycle(4)
    h.set_freq(49.6)
    await h.cycle(3)
    await h.env.server.stop()
    h.env.server.kick_all()
    last = None
    for _ in range(30):                                       # 3 s > hold
        last = await h.cycle()
    assert last.state == "SAFE_STATE" and last.status == "TELEMETRY_COMM_ERROR" and last.commit_ok is False
    assert h.node.metrics.safe_state_entries >= 1
    await h.env.server.start()
    h.node.plant.transport.port = h.env.server.port
    h.set_freq(49.6)
    n0 = len(h.env.server.write_log)
    for _ in range(80):
        r = await h.cycle(settle=0.02)
        if r.state == "RUNNING":
            break
    p_writes = [v for (_, a, v) in h.env.server.write_log[n0:] if a == 200]
    assert p_writes and p_writes[0] == [0], "la primera escritura tras reconectar debe ser 0 kW"
    assert r.state == "RUNNING" and h.p_reg > 0


async def test_pcs_watchdog_uses_heartbeat_to_fail_safe_even_if_node_cannot_write():
    hh = Harness(pcs_watchdog_s=0.5)
    await hh.start()
    try:
        await hh.cycle(4)
        hh.set_freq(49.6)
        await hh.cycle(20)
        assert hh.env.plant.p_setpoint_kw > 0 and not hh.env.bridge.watchdog_tripped
        await hh.env.server.stop()
        hh.env.server.kick_all()
        for _ in range(10):
            await hh.cycle()
        assert hh.env.bridge.watchdog_tripped and hh.env.plant.p_setpoint_kw == 0.0
    finally:
        await hh.stop()


async def test_repeated_write_failures_enter_safe_state_then_recover(h):
    await h.cycle(4)
    h.set_freq(49.6)
    await h.cycle()
    h.env.server.faults.write_exception = 4
    rs = [await h.cycle() for _ in range(4)]
    assert rs[0].status == "WRITE_FAILURE" and rs[-1].state == "SAFE_STATE" and h.node.metrics.write_failures >= 3
    h.env.server.faults.write_exception = None
    for _ in range(8):
        r = await h.cycle()
    assert r.state == "RUNNING" and h.p_reg > 0


async def test_write_verification_catches_a_pcs_that_ignores_setpoints():
    cfg = make_cfg(modbus={"verify_every_n_cycles": 1, "verify_writes": True})
    hh = await Harness(cfg).start()
    try:
        await hh.cycle(4)
        hh.set_freq(49.6)
        hh.env.server.faults.ignore_writes = True
        rs = [await hh.cycle() for _ in range(4)]
        assert hh.node.metrics.verify_mismatches >= 3 and rs[-1].state == "SAFE_STATE"
    finally:
        await hh.stop()


async def test_external_dispatch_ramps_expires_and_is_capped():
    cfg = make_cfg(ffr={"ramp_pct_per_min": 6000.0}, dispatch={"external_timeout_s": 5.0})   # 1000 kW/s
    hh = await Harness(cfg).start()
    try:
        await hh.cycle(4)
        hh.node.set_dispatch(300.0)
        r = await hh.cycle(3)                                 # 100 kW por ciclo (1000 kW/s * 0.1 s)
        assert r.p_setpoint_kw == pytest.approx(300.0, abs=1.0)
        hh.node.set_dispatch(1e9)
        assert (await hh.cycle(10)).p_setpoint_kw == pytest.approx(1000.0, abs=1.0)     # limitada a la capacidad
        with pytest.raises(ValueError):
            hh.node.set_dispatch(float("nan"))
        for _ in range(60):
            r = await hh.cycle()
        assert r.p_setpoint_kw == 0.0                          # expiró y volvió a 0
        kinds = [e["kind"] for e in hh.node.audit.ring]
        assert "DISPATCH_EXPIRED" in kinds
    finally:
        await hh.stop()


async def test_dispatch_load_is_relieved_instantly_on_underfrequency():
    cfg = make_cfg(ffr={"ramp_pct_per_min": 6000.0})
    hh = await Harness(cfg).start()
    try:
        await hh.cycle(4)
        hh.node.set_dispatch(-500.0)
        r = await hh.cycle(6)
        assert r.p_setpoint_kw == pytest.approx(-500.0, abs=1.0)
        hh.set_freq(49.85)
        r = await hh.cycle()
        assert r.p_setpoint_kw == pytest.approx(80.0, abs=1.0)
    finally:
        await hh.stop()


async def test_shutdown_writes_zero_and_closes(h):
    await h.cycle(4)
    h.set_freq(49.6)
    await h.cycle(3)
    assert h.p_reg > 0
    await h.node.stop()
    assert h.p_reg == 0 and h.node.state is NodeState.STOPPED
    await h.env.stop()
    h.node = type(h.node)  # evita doble parada en el fixture
    h.stop = _noop


async def _noop():
    return None


async def test_unexpected_exception_never_kills_the_loop_and_goes_safe(h):
    await h.cycle(4)
    h.set_freq(49.6)
    await h.cycle(2)
    real_step, calls = h.node.step, {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] <= 3:
            raise RuntimeError("bug simulado")
        if calls["n"] == 6:
            h.node.request_stop()
        return await real_step()

    h.node.step = flaky
    await h.node.run()
    assert h.node.metrics.internal_errors == 3 and h.p_reg == 0 or h.node.state in (NodeState.SAFE_STATE, NodeState.RUNNING)
    kinds = [e["kind"] for e in h.node.audit.ring]
    assert kinds.count("INTERNAL_ERROR") == 3


async def test_run_loop_overruns_counted_and_stop_is_graceful(h):
    calls = {"n": 0}
    real = h.node.step

    async def slow():
        calls["n"] += 1
        if calls["n"] == 2:
            h.clock.advance(0.5)                              # ciclo que excede el período (100 ms)
        if calls["n"] == 5:
            h.node.request_stop()
        return await real()

    h.node.step = slow
    await h.node.run()
    assert h.node.metrics.overruns >= 1 and calls["n"] == 5


async def test_contingency_audit_record_with_aporte(h):
    await h.cycle(4)
    h.set_freq(49.6)
    await h.cycle(1300)                                        # 130 s
    h.set_freq(50.0)
    await h.cycle(2)
    ev = [e for e in h.node.audit.ring if e["kind"] == "CONTINGENCY"]
    assert len(ev) == 1
    d = ev[0]["data"]
    assert d["direction"] == "UNDERFREQUENCY" and d["f_extreme_hz"] == pytest.approx(49.6)
    assert d["aporte_10s_kw"] == pytest.approx(246.0, abs=1.0) and d["aporte_2min_kw"] == pytest.approx(246.0, abs=1.0)


async def test_setpoint_and_state_audit_trail(h):
    await h.cycle(4)
    h.set_freq(49.6)
    await h.cycle(5)
    kinds = [e["kind"] for e in h.node.audit.ring]
    assert kinds[0] == "NODE_START" and "STATE" in kinds and "SETPOINT" in kinds


async def test_pcs_not_tracking_alarm():
    cfg = make_cfg(runtime={"tracking_alarm_s": 1.0})
    hh = await Harness(cfg).start()
    try:
        await hh.cycle(4)
        hh.env.plant.params.tau_p_s = 1e9                      # PCS que no sigue la consigna
        hh.set_freq(49.6)
        await hh.cycle(30)
        assert any(e["kind"] == "PCS_NOT_TRACKING" for e in hh.node.audit.ring)
    finally:
        await hh.stop()


# -- capacidades / modo monitor ------------------------------------------------------------------
async def test_monitor_only_profile_never_writes_and_reports():
    cfg = make_cfg(modbus={"profile": "huawei_sun2000"}, runtime={"monitor_only": True}, volt_var={"mode": "DISABLED"})
    hh = await Harness(cfg, profile=load_profile("huawei_sun2000"), unit=3).start()
    try:
        for _ in range(5):
            r = await hh.cycle()
        assert r.state == "MONITOR_ONLY" and r.status == "MONITOR" and hh.env.server.write_log == []
        assert "BESS-GUARD-090" in r.faults                    # faltan señales de celda: se informa, no se oculta
    finally:
        await hh.stop()


async def test_control_refused_on_monitor_only_profile():
    cfg = make_cfg(modbus={"profile": "huawei_sun2000"}, volt_var={"mode": "DISABLED"})
    hh = Harness(cfg, profile=load_profile("huawei_sun2000"), unit=3)
    await hh.start(start_node=False)
    try:
        with pytest.raises(ConfigError, match="no puede controlarse"):
            await hh.node.start(timeout_s=1.0)
    finally:
        await hh.env.stop()


async def test_missing_frequency_binding_or_q_binding_refused():
    hh = Harness(make_cfg(ffr={"enabled": True}))
    await hh.start(start_node=False)
    try:
        prof = hh.node.plant.profile
        from dataclasses import replace
        no_f = replace(prof, bindings={k: v for k, v in prof.bindings.items() if k != "frequency_hz"}, _plan_cache={})
        hh.node.plant.profile = no_f
        with pytest.raises(ConfigError, match="frequency_hz"):
            await hh.node.start(timeout_s=1.0)
        no_q = replace(prof, bindings={k: v for k, v in prof.bindings.items() if k != "q_setpoint_kvar"}, _plan_cache={})
        hh.node.plant.profile = no_q
        with pytest.raises(ConfigError, match="q_setpoint_kvar"):
            await hh.node.start(timeout_s=1.0)
    finally:
        await hh.env.stop()


async def test_register_range_too_small_for_plant_refused_at_start():
    cfg = make_cfg(plant={"p_nominal_kw": 40000.0, "e_nominal_kwh": 80000.0}, volt_var={"q_max_kvar": 600.0})
    hh = Harness(cfg)
    await hh.start(start_node=False)
    try:
        from open_bess_edge.errors import ProfileError
        with pytest.raises(ProfileError, match="no es representable"):
            await hh.node.start(timeout_s=1.0)
    finally:
        await hh.env.stop()


async def test_start_without_connection_stays_safe():
    hh = Harness()
    await hh.start(start_node=False)
    await hh.env.stop()
    ok = await hh.node.start(timeout_s=0.4)
    assert ok is False and hh.node.state is NodeState.SAFE_STATE
    await hh.node.plant.close()


async def test_q_not_bound_profile_zeroes_q(h):
    await h.cycle(4)
    from dataclasses import replace
    prof = h.node.plant.profile
    h.node.plant.profile = replace(prof, bindings={k: v for k, v in prof.bindings.items() if k != "q_setpoint_kvar"}, _plan_cache={})
    h.set_volt(380.0)
    r = await h.cycle()
    assert r.q_setpoint_kvar == 0.0 and h.q_reg == 0
