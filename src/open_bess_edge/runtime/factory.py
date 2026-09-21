"""Ensamblado de un nodo a partir de la configuración."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..config import EdgeConfig
from ..modbus.driver import ModbusPlant
from ..modbus.profile import load_profile
from ..modbus.transport import ModbusTransport, PyModbusTransport
from .node import EdgeNode


def build_node(cfg: EdgeConfig, *, base_dir: Optional[Path] = None, transport: Optional[ModbusTransport] = None,
               clock: Any = None, host: Optional[str] = None, port: Optional[int] = None,
               meter_host: Optional[str] = None, meter_port: Optional[int] = None) -> EdgeNode:
    profile = load_profile(cfg.modbus.profile, base_dir)
    unit = cfg.modbus.unit_id if cfg.modbus.unit_id is not None else (profile.default_unit_id or 1)
    tr = transport or PyModbusTransport(host or cfg.modbus.host, port or cfg.modbus.port, cfg.modbus.timeout_s)
    kw = {}
    if clock is not None:
        kw = {"mono": clock.mono, "wall": clock.wall}
    plant = ModbusPlant(profile, tr, unit, max_read_gap=cfg.modbus.max_read_gap,
                        reconnect_min_s=cfg.modbus.reconnect_min_s, reconnect_max_s=cfg.modbus.reconnect_max_s, **kw)
    meter = None
    if cfg.grid_meter is not None:
        gm = cfg.grid_meter
        mprof = load_profile(gm.profile, base_dir)
        munit = gm.unit_id if gm.unit_id is not None else (mprof.default_unit_id or 1)
        mtr = PyModbusTransport(meter_host or gm.host, meter_port or gm.port, gm.timeout_s)
        meter = ModbusPlant(mprof, mtr, munit, reconnect_min_s=cfg.modbus.reconnect_min_s,
                            reconnect_max_s=cfg.modbus.reconnect_max_s, **kw)
    return EdgeNode(cfg, plant, clock=clock, meter=meter)
