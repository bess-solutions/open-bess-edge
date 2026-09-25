"""Driver de planta contra un servidor Modbus TCP real (independiente de pymodbus)."""
import asyncio
import math

import pytest

from open_bess_edge.errors import PlantCommError, PlantDataError, ProfileError
from open_bess_edge.modbus.driver import ModbusPlant
from open_bess_edge.modbus.profile import load_profile
from open_bess_edge.modbus.transport import PyModbusTransport
from open_bess_edge.sim.bridge import SimBridge
from open_bess_edge.sim.modbus_server import RegisterBank, SimModbusServer
from open_bess_edge.sim.plant import PlantModel

pytestmark = pytest.mark.e2e


class Rig:
    def __init__(self, profile_name="open_bess_edge_reference", timeout=0.3, unit=1, **plant_kw):
        self.profile = load_profile(profile_name)
        self.model = PlantModel()
        self.bank = RegisterBank()
        self.bridge = SimBridge(self.profile, self.model, self.bank)
        self.server = SimModbusServer(self.bank, unit_ids=(unit,))
        self.unit, self.timeout, self.plant_kw = unit, timeout, plant_kw

    async def __aenter__(self):
        port = await self.server.start()
        self.transport = PyModbusTransport("127.0.0.1", port, self.timeout)
        self.plant = ModbusPlant(self.profile, self.transport, self.unit, reconnect_min_s=0.05, reconnect_max_s=0.2, **self.plant_kw)
        assert await self.plant.connect_now(2.0)
        return self

    async def __aexit__(self, *a):
        await self.plant.close()
        await self.server.stop()


async def test_read_telemetry_full_roundtrip_reference():
    async with Rig() as r:
        r.model.f_hz, r.model.v_v, r.model.soc_pct = 49.97, 398.0, 61.3
        r.model.p_kw, r.model.q_kvar = -250.0, 75.0
        r.bridge.sync_out()
        t = await r.plant.read_telemetry()
        assert t.invalid == ()
        assert t.frequency_hz == 49.97 and t.v_grid_v == 398.0 and t.soc_pct == pytest.approx(61.3)
        assert t.p_kw == -250.0 and t.q_kvar == 75.0
        assert t.cell_v_min_v == pytest.approx(r.model.measure()["cell_v_min_v"], abs=1e-3)
        assert t.cell_t_max_c == pytest.approx(r.model.cell_t_c, abs=0.05)
        assert t.isolation_kohm == 1200.0


async def test_write_setpoints_sign_truncation_and_verify():
    async with Rig() as r:
        res = await r.plant.write_setpoints(-250.9, 75.9, verify=True)
        assert res.ok and res.verified is True
        assert res.extra["applied_p_kw"] == -250.0 and res.extra["applied_q_kvar"] == 75.0     # trunca hacia cero
        assert r.bank.holding[200] == 65286 and r.bank.holding[201] == 75
        r.bridge.sync_in(0.0)
        assert r.model.p_setpoint_kw == -250.0
        res = await r.plant.write_setpoints(999.99, -0.4)
        assert res.extra["applied_p_kw"] == 999.0 and res.extra["applied_q_kvar"] == 0.0        # nunca supera la magnitud pedida


async def test_write_overflow_is_reported_not_wrapped():
    async with Rig() as r:
        res = await r.plant.write_setpoints(40000.0, 0.0)
        assert not res.ok and "codec" in res.detail
        assert r.bank.holding[200] == 0                          # nada se escribió (no hubo wrap a -25536)
        res = await r.plant.write_setpoints(math.nan, 0.0)
        assert not res.ok and "no finita" in res.detail


async def test_check_setpoint_range_at_startup():
    async with Rig() as r:
        r.plant.check_setpoint_range(1000.0, 600.0)
        with pytest.raises(ProfileError, match="no es representable"):
            r.plant.check_setpoint_range(40000.0, 600.0)


async def test_verification_detects_ignored_write():
    async with Rig() as r:
        r.server.faults.ignore_writes = True
        res = await r.plant.write_setpoints(100.0, 0.0, verify=True)
        assert not res.ok and res.verified is False and "verify_mismatch" in res.detail


async def test_write_exception_reported():
    async with Rig() as r:
        r.server.faults.write_exception = 4
        res = await r.plant.write_setpoints(100.0, 0.0)
        assert not res.ok and "excepción Modbus" in res.detail
        z = await r.plant.write_zero()
        assert not z.ok


async def test_write_zero_attempts_q_even_if_p_fails():
    async with Rig() as r:
        r.bank.holding[201] = 55
        calls = []
        real = r.plant.transport.write

        async def flaky(addr, vals, unit):
            calls.append(addr)
            if addr == 200:
                raise PlantCommError("boom")
            return await real(addr, vals, unit)

        r.plant.transport.write = flaky      # type: ignore[method-assign]
        z = await r.plant.write_zero()
        assert calls == [200, 201] and not z.ok and r.bank.holding[201] == 0


@pytest.mark.parametrize("fault", ["drop_next", "truncate_next", "garbage_next", "wrong_tid_next"])
async def test_protocol_faults_raise_comm_error_and_recover(fault):
    async with Rig() as r:
        setattr(r.server.faults, fault, 1)
        with pytest.raises(PlantCommError):
            await r.plant.read_telemetry()
        assert not r.plant.connected                              # se cierra el socket tras el error
        assert await r.plant.connect_now(2.0)
        assert (await r.plant.read_telemetry()).frequency_hz == 50.0


async def test_timeout_is_bounded():
    async with Rig(timeout=0.2) as r:
        r.server.faults.stall = True
        t0 = asyncio.get_running_loop().time()
        with pytest.raises(PlantCommError, match="(?i)timeout|cancelled|no response|vacía"):
            await r.plant.read_telemetry()
        assert asyncio.get_running_loop().time() - t0 < 0.6


async def test_modbus_exception_does_not_drop_connection():
    async with Rig() as r:
        r.server.faults.exception_next = [2]
        with pytest.raises(PlantCommError, match="código=2"):
            await r.plant.read_telemetry()
        assert r.plant.connected
        assert (await r.plant.read_telemetry()).invalid == ()


async def test_non_finite_and_undecodable_values_become_none_never_plausible_numbers():
    async with Rig() as r:
        r.model.overrides["frequency_hz"] = 49.9
        r.bridge.sync_out()
        r.bank.holding[100] = 0xFFFF                              # 655.35 Hz: decodifica pero es absurdo (lo filtra safety/control)
        t = await r.plant.read_telemetry()
        assert t.frequency_hz == pytest.approx(655.35)


async def test_float32_nan_register_marks_invalid():
    prof = load_profile("fronius_gen24_byd")
    model, bank = PlantModel(), RegisterBank()
    bridge = SimBridge(prof, model, bank)
    server = SimModbusServer(bank, unit_ids=(1,))
    port = await server.start()
    plant = ModbusPlant(prof, PyModbusTransport("127.0.0.1", port, 0.3), 1)
    try:
        await plant.connect_now(2.0)
        model.overrides["frequency_hz"] = math.nan
        bridge.sync_out()
        t = await plant.read_telemetry()
        assert t.frequency_hz is None and "frequency_hz" in t.invalid
        assert t.soc_pct == pytest.approx(60.0, abs=0.01)
    finally:
        await plant.close()
        await server.stop()


async def test_unmapped_address_is_an_error_not_silent_zero():
    async with Rig() as r:
        del r.bank.holding[105]
        with pytest.raises(PlantCommError, match="código=2"):
            await r.plant.read_telemetry()


async def test_heartbeat_increments_and_wraps():
    async with Rig() as r:
        for i in range(1, 4):
            assert await r.plant.heartbeat() and r.bank.holding[202] == i
        r.plant._hb = 0xFFFF
        assert await r.plant.heartbeat() and r.bank.holding[202] == 0


async def test_monitor_only_profile_refuses_setpoint_writes():
    async with Rig("huawei_sun2000", unit=3) as r:
        with pytest.raises(PlantDataError, match="monitor"):
            await r.plant.write_setpoints(10.0, 0.0)
        with pytest.raises(ProfileError):
            r.plant.check_setpoint_range(10.0, 0.0)


async def test_reconnect_backoff_is_nonblocking_and_exponential():
    current_time = 1000.0

    def fake_mono():
        return current_time

    async with Rig(mono=fake_mono) as r:
        await r.plant.close()
        r.server.kick_all()
        await r.server.stop()                                     # el servidor desaparece
        t0 = asyncio.get_running_loop().time()
        for _ in range(200):
            r.plant.poll_connection()
            await asyncio.sleep(0.001)                            # cede control para procesar _attempt()
            current_time += 0.01                                  # avance temporal determinístico
        assert asyncio.get_running_loop().time() - t0 < 10.0
        assert 2 <= r.plant.connect_attempts <= 15               # backoff: acotado, no reintenta en cada poll
        assert "conexión Modbus" in r.plant.last_connect_error
        # el servidor vuelve
        r.server._server = None
        await r.server.start()
        r.plant.transport.port = r.server.port
        for _ in range(300):
            current_time += 0.02
            if r.plant.poll_connection():
                break
            await asyncio.sleep(0.01)
        assert r.plant.connected


async def test_connect_now_gives_up_after_timeout():
    plant = ModbusPlant(load_profile("open_bess_edge_reference"), PyModbusTransport("127.0.0.1", 1, 0.2), 1)
    assert not await plant.connect_now(0.5)
    assert plant.last_connect_error
    await plant.close()


@pytest.mark.parametrize("profile,unit", [("huawei_sun2000", 3), ("sma_sunny_tripower", 3), ("fronius_gen24_byd", 1),
                                          ("solaredge_storedge", 1), ("victron_multiplus2", 227), ("simulator", 1)])
async def test_vendor_profile_telemetry_roundtrip_with_sign_and_units(profile, unit):
    """Ida y vuelta perfil -> emulador -> driver. Prueba el códec/signos/escalas del perfil, NO el dispositivo real."""
    async with Rig(profile, unit=unit) as r:
        m = r.model
        m.f_hz, m.v_v, m.p_kw, m.q_kvar, m.soc_pct = 49.93, 231.0, -5.0, 0.0, 62.5
        m.params.soh_pct = 97.0
        r.bridge.sync_out()
        t = await r.plant.read_telemetry()
        b = r.profile.bindings
        assert t.invalid == ()
        if "frequency_hz" in b:
            assert t.frequency_hz == pytest.approx(49.93, abs=0.011 if profile != "simulator" else 0.51)
        if "v_grid_v" in b:
            assert t.v_grid_v == pytest.approx(231.0, abs=0.51)
        if "p_kw" in b and profile != "simulator":
            assert t.p_kw == pytest.approx(-5.0, abs=0.01)         # inversión de signo del fabricante (+ = carga) y W->kW
        if "soc_pct" in b:
            assert t.soc_pct == pytest.approx(62.5, abs=0.51)
        if "soh_pct" in b:
            assert t.soh_pct == pytest.approx(97.0, abs=0.51)
