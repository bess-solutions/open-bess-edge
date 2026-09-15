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


@pytest.mark.asyncio
async def test_modbus_real_client_read_and_write():
    from unittest.mock import AsyncMock, MagicMock

    cfg = ModbusConfig(simulation_mode=False)
    client = ModbusBESSClient(cfg)
    client._connected = True

    mock_client = AsyncMock()
    mock_client.close = MagicMock()
    mock_res = MagicMock()
    mock_res.isError.return_value = False
    mock_res.registers = [5000, 400, 100, 50, 800, 950, 3200, 3250, 250, 1000]
    mock_client.read_holding_registers.return_value = mock_res

    mock_write_res = MagicMock()
    mock_write_res.isError.return_value = False
    mock_client.write_register.return_value = mock_write_res

    client._client = mock_client

    readings = await client.read_telemetry()
    assert readings.read_ok is True
    assert readings.f_measured_hz == 50.0
    assert readings.v_grid_v == 400.0
    assert readings.p_actual_kw == 100.0
    assert readings.soc_pct == 80.0

    # Write setpoints
    ok, msg = await client.write_setpoints(p_kw=100.0, q_kvar=50.0)
    assert ok is True
    assert msg == "SETPOINTS_COMMITTED"

    # Write error
    mock_write_err = MagicMock()
    mock_write_err.isError.return_value = True
    mock_client.write_register.return_value = mock_write_err
    ok_err, _ = await client.write_setpoints(p_kw=100.0, q_kvar=50.0)
    assert ok_err is False

    # Read error
    mock_read_err = MagicMock()
    mock_read_err.isError.return_value = True
    mock_client.read_holding_registers.return_value = mock_read_err
    readings_err = await client.read_telemetry()
    assert readings_err.read_ok is False

    await client.disconnect()
    assert client._connected is False


@pytest.mark.asyncio
async def test_modbus_connect_failure():
    from unittest.mock import patch

    cfg = ModbusConfig(simulation_mode=False)
    client = ModbusBESSClient(cfg)

    with patch("src.drivers.modbus_client.AsyncModbusTcpClient") as mock_cls:
        instance = mock_cls.return_value
        instance.connect.side_effect = ConnectionRefusedError("Offline")
        ok = await client.connect()
        assert ok is False
        assert client._connected is False
