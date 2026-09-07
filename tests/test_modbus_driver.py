#!/usr/bin/env python3
"""
open-bess-edge/tests/test_modbus_driver.py
==============================================================================
Pruebas unitarias para el driver Modbus TCP/RTU industrial de BESS
==============================================================================
"""

import sys
from pathlib import Path

import pytest

EDGE_DIR = Path(__file__).resolve().parent.parent
if str(EDGE_DIR) not in sys.path:
    sys.path.insert(0, str(EDGE_DIR))

from src.config import ModbusConfig
from src.drivers.modbus_client import BESSReadings, ModbusBESSClient


@pytest.mark.asyncio
async def test_modbus_simulation_connection():
    cfg = ModbusConfig(simulation_mode=True)
    client = ModbusBESSClient(cfg)
    connected = await client.connect()
    assert connected is True

    readings = await client.read_telemetry()
    assert isinstance(readings, BESSReadings)
    assert readings.read_ok is True
    assert readings.f_measured_hz == 50.0
    assert readings.soc_pct > 0.0

    await client.disconnect()


@pytest.mark.asyncio
async def test_modbus_write_setpoints_simulation():
    cfg = ModbusConfig(simulation_mode=True)
    client = ModbusBESSClient(cfg)
    await client.connect()

    ok, msg = await client.write_setpoints(p_kw=250.0, q_kvar=-50.0)
    assert ok is True
    assert "SIMULATION" in msg

    readings = await client.read_telemetry()
    assert readings.p_actual_kw == 250.0
    assert readings.q_actual_kvar == -50.0

    await client.disconnect()


@pytest.mark.asyncio
async def test_modbus_injected_event():
    cfg = ModbusConfig(simulation_mode=True)
    client = ModbusBESSClient(cfg)
    await client.connect()

    client.inject_simulated_grid_event(f_hz=49.75, v_v=395.0)
    readings = await client.read_telemetry()
    assert readings.f_measured_hz == 49.75
    assert readings.v_grid_v == 395.0

    # Test reconexión en simulación
    reconnected = await client.reconnect_with_backoff()
    assert reconnected is True

    await client.disconnect()


def test_modbus_numeric_conversions():
    """Verifica conversiones 16-bit signed/unsigned."""
    # Positivo
    u_pos = ModbusBESSClient._to_unsigned16(500)
    assert u_pos == 500
    assert ModbusBESSClient._signed16(u_pos) == 500

    # Negativo (complemento a 2 en 16 bits)
    u_neg = ModbusBESSClient._to_unsigned16(-500)
    assert u_neg == 65536 - 500
    assert ModbusBESSClient._signed16(u_neg) == -500
