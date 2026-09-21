"""Latencia real (reloj del sistema, TCP loopback): muestra de frecuencia -> escritura de consigna."""
import asyncio
import time

import pytest

from open_bess_edge.runtime.factory import build_node
from open_bess_edge.sim.runner import SimEnvironment
from tests.conftest import make_cfg

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


async def test_frequency_step_to_setpoint_write_within_500ms_budget_realtime():
    cfg = make_cfg(runtime={"cycle_ms": 100})
    env = SimEnvironment(cfg, tick_s=0.01)
    port = await env.start(realtime=True)
    node = build_node(cfg, host="127.0.0.1", port=port)
    assert await node.start()
    task = asyncio.ensure_future(node.run())
    try:
        await asyncio.sleep(0.8)                                  # arranque y validación
        lat = []
        for k in range(12):
            env.server.write_log.clear()
            await asyncio.sleep(0.137 * (k % 3 + 1))               # fases aleatorias respecto al ciclo de 100 ms
            t_event = time.monotonic()
            env.plant.f_profile = None
            env.plant.f_hz = 49.5
            for _ in range(400):
                await asyncio.sleep(0.002)
                hit = [t for (t, a, v) in env.server.write_log if a == 200 and v != [0]]
                if hit:
                    lat.append(hit[0] - t_event)
                    break
            env.plant.f_hz = 50.0
            await asyncio.sleep(0.3)
        assert len(lat) == 12, "no toda contingencia produjo respuesta"
        # presupuesto: 500 ms (ciclo 100 ms + lectura + escritura + tick de la planta simulada de 10 ms)
        assert max(lat) < 0.5, [round(x, 3) for x in lat]
        assert node.metrics.ffr_budget_exceeded == 0
        print("\nlatencia evento->escritura [ms]:", sorted(round(x * 1000) for x in lat))
    finally:
        node.request_stop()
        await task
        await node.stop()
        await env.stop()
