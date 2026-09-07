#!/usr/bin/env python3
"""
open-bess-edge/src/edge_node.py
==============================================================================
Open BESS Edge — Núcleo Operativo del Nodo de Borde Industrial
==============================================================================
Orquesta el lazo cerrado de control en tiempo real:
    Lectura Modbus -> Evaluación de Seguridad -> Control FFR/Droop & Volt/VAR -> Consigna Modbus
==============================================================================
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

EDGE_DIR = Path(__file__).resolve().parent.parent
if str(EDGE_DIR) not in sys.path:
    sys.path.insert(0, str(EDGE_DIR))

import structlog

from src.config import EdgeConfig, edge_settings
from src.controllers.ffr_droop_controller import FFRDroopController
from src.controllers.volt_var_controller import VoltVarController
from src.drivers.modbus_client import BESSReadings, ModbusBESSClient
from src.safety.safety_envelope_evaluator import SafetyEnvelopeEvaluator

logger = structlog.get_logger(__name__)


class BESSEdgeNode:
    """
    Nodo de cómputo autónomo de borde para subestaciones BESS.
    Ejecuta el lazo determinístico de control de frecuencia y tensión.
    """

    def __init__(self, config: EdgeConfig | None = None):
        self.cfg = config or edge_settings

        self.driver = ModbusBESSClient(self.cfg.modbus)
        self.safety = SafetyEnvelopeEvaluator()

        # Inicialización de controladores con parámetros oficiales CEN
        p_nominal_kw = self.cfg.bess.p_nominal_mw * 1000.0
        self.ffr_controller = FFRDroopController(
            p_nominal_kw=p_nominal_kw,
            f_nominal_hz=self.cfg.grid.f_nominal_hz,
            droop_r=self.cfg.grid.droop_r,
            deadband_hz=self.cfg.grid.deadband_hz,
            ffr_contingency_threshold_hz=self.cfg.grid.ffr_contingency_threshold_hz,
            normal_ramp_limit_pct_min=self.cfg.grid.normal_ramp_limit_pct_min,
        )

        q_max_kvar = self.cfg.grid.q_max_mvar * 1000.0
        self.volt_var_controller = VoltVarController(
            q_max_kvar=q_max_kvar,
            v_nominal_v=self.cfg.bess.v_nominal_ac_v,
            deadband_pct=self.cfg.grid.volt_var_deadband_pct,
        )

        self._running = False
        self._loop_task: asyncio.Task | None = None
        self.cycle_count: int = 0
        self.last_telemetry: dict[str, Any] | None = None

    async def start(self) -> bool:
        """Inicia el enlace de comunicaciones y el lazo de control en tiempo real."""
        logger.info(
            "edge_node_starting",
            device_id=self.cfg.bess.device_id,
            site=self.cfg.bess.site_name,
            p_nominal_mw=self.cfg.bess.p_nominal_mw,
        )
        ok = await self.driver.connect()
        if not ok:
            logger.error("edge_node_modbus_init_failed")
            return False

        self._running = True
        return True

    async def stop(self) -> None:
        """Detiene el lazo y desconecta el cliente Modbus de forma segura."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
        await self.driver.disconnect()
        logger.info("edge_node_stopped_safely")

    async def step(self) -> dict[str, Any]:
        """
        Ejecuta un ciclo discreto de control (Paso determinístico).
        Retorna la telemetría consolidada del ciclo.
        """
        t0 = time.monotonic()
        self.cycle_count += 1

        # 1. Lectura de telemetría de hardware
        readings: BESSReadings = await self.driver.read_telemetry()
        if not readings.read_ok:
            logger.warning("edge_node_telemetry_degraded", error=readings.error_msg)
            return {"status": "TELEMETRY_COMM_ERROR", "error": readings.error_msg}

        # 2. Evaluación de Envolvente de Seguridad de Celdas y Rack
        is_safe, faults, safety_meta = self.safety.evaluate_cell_telemetry(
            v_min_v=readings.cell_v_min_mv / 1000.0,
            v_max_v=readings.cell_v_max_mv / 1000.0,
            t_max_c=readings.cell_t_max_c,
            isolation_kohm=readings.dc_isolation_kohm,
        )

        # Si hay disparo crítico de hardware, consigna a cero de inmediato
        if not is_safe:
            logger.critical("safety_trip_triggered", faults=faults)
            await self.driver.write_setpoints(0.0, 0.0)
            return {
                "status": "SAFETY_TRIP_INTERLOCK",
                "faults": faults,
                "readings": readings.__dict__,
            }

        # 3. Lazo de Control de Frecuencia (FFR / Droop CEN)
        p_target_kw, ffr_meta = self.ffr_controller.compute_response(
            f_measured_hz=readings.f_measured_hz,
            p_base_kw=readings.p_actual_kw,
            soc_pct=readings.soc_pct,
        )

        # 4. Lazo de Control de Tensión (Volt/VAR Q(V) NTSyCS)
        q_target_kvar, _vv_meta = self.volt_var_controller.compute_reactive_power(
            v_measured_v=readings.v_grid_v,
            p_actual_kw=p_target_kw,
        )

        # 5. Validación de Envolvente de Consigna Inversor (C-Rate y Aislamiento)
        capacity_kwh = self.cfg.bess.e_nominal_mwh * 1000.0
        _approved, p_approved_kw, _reason = self.safety.evaluate_inverter_setpoint(
            p_target_kw=p_target_kw,
            q_target_kvar=q_target_kvar,
            e_nominal_kwh=capacity_kwh,
            isolation_kohm=readings.dc_isolation_kohm,
        )

        # 6. Despacho de Consignas al PCS vía Modbus
        commit_ok, _commit_msg = await self.driver.write_setpoints(
            p_approved_kw, q_target_kvar
        )

        dt_total_ms = (time.monotonic() - t0) * 1000.0

        cycle_summary = {
            "cycle": self.cycle_count,
            "timestamp": readings.timestamp_utc,
            "f_grid_hz": readings.f_measured_hz,
            "v_grid_v": readings.v_grid_v,
            "soc_pct": readings.soc_pct,
            "p_setpoint_kw": p_approved_kw,
            "q_setpoint_kvar": q_target_kvar,
            "ffr_status": ffr_meta["status"],
            "ffr_mode": ffr_meta["ramp_mode"],
            "is_ffr_emergency": ffr_meta["is_ffr_emergency"],
            "safety_status": safety_meta["status"],
            "commit_ok": commit_ok,
            "latency_ms": dt_total_ms,
        }

        self.last_telemetry = cycle_summary
        return cycle_summary


if __name__ == "__main__":

    async def demo():
        node = BESSEdgeNode()
        await node.start()
        print("--- Ciclo Normal (50.00 Hz) ---")
        res1 = await node.step()
        print(
            f"P Setpoint: {res1['p_setpoint_kw']} kW | Latencia: {res1['latency_ms']:.2f} ms"
        )

        print("\n--- Contingencia Severa SEN (49.65 Hz) ---")
        node.driver.inject_simulated_grid_event(49.65)
        res2 = await node.step()
        print(
            f"P Setpoint: {res2['p_setpoint_kw']} kW | Modo: {res2['ffr_mode']} | Latencia: {res2['latency_ms']:.2f} ms"
        )
        await node.stop()

    asyncio.run(demo())
