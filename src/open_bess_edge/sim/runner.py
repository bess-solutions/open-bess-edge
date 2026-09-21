"""Entorno de simulación completo: planta + banco de registros + servidor Modbus TCP.

El nodo se conecta por **TCP real** (mismo camino de código que en producción);
no existe un modo "simulación" dentro del driver.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from ..config import EdgeConfig
from ..modbus.profile import DeviceProfile, load_profile
from .bridge import SimBridge
from .modbus_server import RegisterBank, SimModbusServer
from .plant import PlantModel, PlantParams


class SimEnvironment:
    def __init__(self, cfg: EdgeConfig, profile: Optional[DeviceProfile] = None, params: Optional[PlantParams] = None,
                 pcs_watchdog_s: Optional[float] = None, unit_id: int = 1, tick_s: float = 0.02):
        self.cfg = cfg
        self.profile = profile or load_profile(cfg.modbus.profile)
        self.params = params or PlantParams(
            p_nominal_kw=cfg.plant.p_nominal_kw, e_nominal_kwh=cfg.plant.e_nominal_kwh,
            q_max_kvar=cfg.volt_var.q_max_kvar, v_grid_v=cfg.plant.v_nominal_v, f_grid_hz=cfg.grid.f_nominal_hz)
        self.plant = PlantModel(self.params)
        self.bank = RegisterBank()
        self.bridge = SimBridge(self.profile, self.plant, self.bank, pcs_watchdog_s=pcs_watchdog_s)
        self.server = SimModbusServer(self.bank, unit_ids=(unit_id,))
        self.meter_server: Optional[SimModbusServer] = None
        self.meter_bridge: Optional[SimBridge] = None
        if cfg.grid_meter is not None:
            mprof = load_profile(cfg.grid_meter.profile)
            mbank = RegisterBank()
            self.meter_bridge = SimBridge(mprof, self.plant, mbank)
            self.meter_server = SimModbusServer(
                mbank, unit_ids=(cfg.grid_meter.unit_id if cfg.grid_meter.unit_id is not None else (mprof.default_unit_id or 1),))
        self.tick_s = tick_s
        self._task: Optional[asyncio.Task[None]] = None
        self._last: Optional[float] = None
        self._now = 0.0

    @property
    def port(self) -> int:
        return self.server.port

    def step(self, dt: float) -> None:
        """Avance manual de la física (pruebas deterministas)."""
        self._now += dt
        self.bridge.sync_in(self._now)
        self.plant.tick(dt)
        self.bridge.sync_out()
        if self.meter_bridge is not None:
            self.meter_bridge.sync_out()

    @property
    def meter_port(self) -> int:
        assert self.meter_server is not None  # noqa: S101
        return self.meter_server.port

    async def start(self, realtime: bool = True) -> int:
        port = await self.server.start()
        if self.meter_server is not None:
            await self.meter_server.start()
        if realtime:
            self._task = asyncio.ensure_future(self._loop())
        return port

    async def _loop(self) -> None:
        loop = asyncio.get_running_loop()
        last = loop.time()
        while True:
            await asyncio.sleep(self.tick_s)
            now = loop.time()
            self.step(now - last)
            last = now

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.meter_server is not None:
            await self.meter_server.stop()
        await self.server.stop()
