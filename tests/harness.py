"""Arnés: nodo real + servidor Modbus TCP real + planta simulada, con reloj manual determinista."""
from __future__ import annotations

import asyncio
from typing import Optional

from tests.conftest import make_cfg

from open_bess_edge.config import EdgeConfig
from open_bess_edge.runtime.clock import ManualClock
from open_bess_edge.runtime.factory import build_node
from open_bess_edge.sim.plant import PlantParams
from open_bess_edge.sim.runner import SimEnvironment


def s16(v: int) -> int:
    return v - 65536 if v >= 32768 else v


class Harness:
    def __init__(self, cfg: Optional[EdgeConfig] = None, profile=None, params: Optional[PlantParams] = None,
                 pcs_watchdog_s: Optional[float] = None, unit: int = 1):
        self.cfg = cfg or make_cfg()
        self.clock = ManualClock()
        self.env = SimEnvironment(self.cfg, profile=profile, params=params, pcs_watchdog_s=pcs_watchdog_s, unit_id=unit)
        self.node = None
        self.results = []

    async def start(self, start_node: bool = True):
        port = await self.env.start(realtime=False)
        self.node = build_node(self.cfg, host="127.0.0.1", port=port, clock=self.clock,
                               meter_port=self.env.meter_port if self.env.meter_server is not None else None)
        # el nodo resuelve el unit_id del perfil salvo configuración explícita
        if start_node:
            assert await self.node.start(timeout_s=2.0)
        return self

    async def stop(self):
        try:
            await self.node.stop()
        finally:
            await self.env.stop()

    async def cycle(self, n: int = 1, dt: float = 0.1, settle: float = 0.0):
        res = None
        for _ in range(n):
            self.clock.advance(dt)
            self.env.step(dt)
            res = await self.node.step()
            self.results.append(res)
            if settle:
                await asyncio.sleep(settle)
        return res

    # accesos rápidos a los registros del PCS simulado
    @property
    def p_reg(self) -> int:
        return s16(self.env.bank.holding[200])

    @property
    def q_reg(self) -> int:
        return s16(self.env.bank.holding[201])

    def set_freq(self, f: float):
        self.env.plant.f_profile = None
        self.env.plant.f_hz = f

    def set_volt(self, v: float):
        self.env.plant.v_profile = None
        self.env.plant.v_v = v
