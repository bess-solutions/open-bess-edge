"""
open-bess-edge/src/drivers/modbus_client.py
==============================================================================
Driver Modbus TCP/RTU Asíncrono Industrial para BESS PCS y BMS
==============================================================================
Comunicación con inversores de potencia (PCS) y sistema de gestión de baterías (BMS).
Soporta reconexión por backoff exponencial y modo simulación determinístico.
==============================================================================
"""

from __future__ import annotations

import asyncio
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

EDGE_DIR = Path(__file__).resolve().parent.parent
if str(EDGE_DIR) not in sys.path:
    sys.path.insert(0, str(EDGE_DIR))

import structlog
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from src.config import ModbusConfig, edge_settings

logger = structlog.get_logger(__name__)


@dataclass
class BESSReadings:
    """Snapshot completo de mediciones físicas del PCS y BMS en un instante."""

    timestamp_utc: float
    device_id: str
    f_measured_hz: float  # Frecuencia de red instantánea (Hz)
    v_grid_v: float  # Tensión de red RMS (V)
    p_actual_kw: float  # Potencia activa instantánea (+ = carga, - = descarga)
    q_actual_kvar: float  # Potencia reactiva (+ = inductivo, - = capacitivo)
    soc_pct: float  # State of Charge (0.0 a 100.0 %)
    soh_pct: float  # State of Health (0.0 a 100.0 %)
    cell_v_min_mv: float  # Voltaje mínimo de celda (mV)
    cell_v_max_mv: float  # Voltaje máximo de celda (mV)
    cell_t_max_c: float  # Temperatura máxima de celda (°C)
    dc_isolation_kohm: float  # Resistencia de aislamiento DC (kOhm)
    read_ok: bool = True
    error_msg: str = ""


class ModbusBESSClient:
    """
    Cliente Modbus TCP asíncrono de alta velocidad para control de borde BESS.
    Maneja lectura de telemetría y escritura de consignas de P y Q.
    """

    def __init__(self, config: ModbusConfig | None = None):
        self.cfg = config or edge_settings.modbus
        self._client: AsyncModbusTcpClient | None = None
        self._connected = False
        self._reconnect_delay = self.cfg.reconnect_delay_s

        # Variables internas para el simulador integrado en memoria
        self._sim_f_hz = 50.0
        self._sim_v_v = 400.0
        self._sim_p_kw = 0.0
        self._sim_q_kvar = 0.0
        self._sim_soc_pct = 65.0
        self._sim_soh_pct = 98.5
        self._sim_v_min_mv = 3280.0
        self._sim_v_max_mv = 3310.0
        self._sim_t_max_c = 26.5
        self._sim_isolation_kohm = 1200.0

    async def connect(self) -> bool:
        """Establece la conexión con el PCS/BMS. En modo simulación retorna True de inmediato."""
        if self.cfg.simulation_mode:
            self._connected = True
            logger.info("modbus_simulation_active", host=self.cfg.host, port=self.cfg.port)
            return True

        try:
            self._client = AsyncModbusTcpClient(
                host=self.cfg.host,
                port=self.cfg.port,
                timeout=self.cfg.timeout_s,
            )
            await self._client.connect()
            self._connected = self._client.connected
            if self._connected:
                self._reconnect_delay = self.cfg.reconnect_delay_s
                logger.info("modbus_connected_ok", host=self.cfg.host, port=self.cfg.port)
            return self._connected
        except Exception as exc:  # noqa: BLE001
            logger.error("modbus_connect_failed", error=str(exc))
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Cierra la conexión de red Modbus."""
        if self._client:
            self._client.close()
        self._connected = False

    async def reconnect_with_backoff(self) -> bool:
        """Intenta reconectar con backoff exponencial y jitter."""
        if self.cfg.simulation_mode:
            self._connected = True
            return True

        jitter = random.uniform(0.8, 1.2)
        sleep_time = min(self._reconnect_delay * jitter, self.cfg.max_reconnect_delay_s)
        logger.warning("modbus_reconnecting", delay_s=sleep_time)
        await asyncio.sleep(sleep_time)
        self._reconnect_delay = min(self._reconnect_delay * 2.0, self.cfg.max_reconnect_delay_s)
        return await self.connect()

    async def read_telemetry(self) -> BESSReadings:
        """Lee el bloque continuo de telemetría desde los registros de retención."""
        now = time.time()
        device_id = edge_settings.bess.device_id

        # Modo simulación determinístico
        if self.cfg.simulation_mode:
            return BESSReadings(
                timestamp_utc=now,
                device_id=device_id,
                f_measured_hz=self._sim_f_hz,
                v_grid_v=self._sim_v_v,
                p_actual_kw=self._sim_p_kw,
                q_actual_kvar=self._sim_q_kvar,
                soc_pct=self._sim_soc_pct,
                soh_pct=self._sim_soh_pct,
                cell_v_min_mv=self._sim_v_min_mv,
                cell_v_max_mv=self._sim_v_max_mv,
                cell_t_max_c=self._sim_t_max_c,
                dc_isolation_kohm=self._sim_isolation_kohm,
                read_ok=True,
            )

        if not self._connected:
            ok = await self.reconnect_with_backoff()
            if not ok:
                return BESSReadings(
                    timestamp_utc=now,
                    device_id=device_id,
                    f_measured_hz=50.0,
                    v_grid_v=0.0,
                    p_actual_kw=0.0,
                    q_actual_kvar=0.0,
                    soc_pct=0.0,
                    soh_pct=0.0,
                    cell_v_min_mv=0.0,
                    cell_v_max_mv=0.0,
                    cell_t_max_c=0.0,
                    dc_isolation_kohm=0.0,
                    read_ok=False,
                    error_msg="Modbus link offline",
                )

        try:
            # Lectura en bloque de 10 registros contiguos
            res = await self._client.read_holding_registers(
                address=self.cfg.reg_f_measured_x100,
                count=10,
                slave=self.cfg.unit_id,
            )
            if res.isError():
                raise ModbusException(f"Read error: {res}")

            regs = res.registers
            return BESSReadings(
                timestamp_utc=now,
                device_id=device_id,
                f_measured_hz=regs[0] / 100.0,
                v_grid_v=float(regs[1]),
                p_actual_kw=float(self._signed16(regs[2])),
                q_actual_kvar=float(self._signed16(regs[3])),
                soc_pct=regs[4] / 10.0,
                soh_pct=regs[5] / 10.0,
                cell_v_min_mv=float(regs[6]),
                cell_v_max_mv=float(regs[7]),
                cell_t_max_c=regs[8] / 10.0,
                dc_isolation_kohm=float(regs[9]),
                read_ok=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("modbus_read_failure", error=str(exc))
            self._connected = False
            return BESSReadings(
                timestamp_utc=now,
                device_id=device_id,
                f_measured_hz=50.0,
                v_grid_v=0.0,
                p_actual_kw=0.0,
                q_actual_kvar=0.0,
                soc_pct=0.0,
                soh_pct=0.0,
                cell_v_min_mv=0.0,
                cell_v_max_mv=0.0,
                cell_t_max_c=0.0,
                dc_isolation_kohm=0.0,
                read_ok=False,
                error_msg=str(exc),
            )

    async def write_setpoints(self, p_kw: float, q_kvar: float) -> tuple[bool, str]:
        """Escribe las consignas de potencia activa y reactiva calculadas por los controladores."""
        if self.cfg.simulation_mode:
            self._sim_p_kw = p_kw
            self._sim_q_kvar = q_kvar
            return True, "SIMULATION_SETPOINT_WRITTEN"

        if not self._connected:
            ok = await self.reconnect_with_backoff()
            if not ok:
                return False, "DISCONNECTED_CANNOT_WRITE"

        try:
            # Conversión a enteros con signo de 16-bit
            val_p = self._to_unsigned16(round(p_kw))
            val_q = self._to_unsigned16(round(q_kvar))

            res_p = await self._client.write_register(
                address=self.cfg.reg_p_setpoint_kw,
                value=val_p,
                slave=self.cfg.unit_id,
            )
            res_q = await self._client.write_register(
                address=self.cfg.reg_q_setpoint_kvar,
                value=val_q,
                slave=self.cfg.unit_id,
            )

            if res_p.isError() or res_q.isError():
                return False, f"Modbus write error: P={res_p}, Q={res_q}"

            return True, "SETPOINTS_COMMITTED"
        except Exception as exc:  # noqa: BLE001
            self._connected = False
            return False, f"Modbus exception: {exc}"

    def inject_simulated_grid_event(self, f_hz: float, v_v: float | None = None) -> None:
        """Método para pruebas dinámicas de hardware-in-the-loop / simulación."""
        self._sim_f_hz = f_hz
        if v_v is not None:
            self._sim_v_v = v_v

    @staticmethod
    def _signed16(value: int) -> int:
        return value if value < 32768 else value - 65536

    @staticmethod
    def _to_unsigned16(value: int) -> int:
        return value if value >= 0 else value + 65536
