"""Unit and Integration Tests for Industrial Edge Drivers & SITR Gateway.

Complies with Chilean Grid Code NTSyCS (Chapters 3 & 4), DS 125/2017, and IEC 61850-8-1.
"""

import asyncio
import struct
import sys
import time
from pathlib import Path
import pytest

EDGE_SRC = Path(__file__).resolve().parent.parent / "src"
if str(EDGE_SRC) not in sys.path:
    sys.path.insert(0, str(EDGE_SRC))

from drivers.can_bms_driver import IndustrialCANBMSDriver
from drivers.iec104_client import IEC104SITRServer, IEC104SITRClient
from drivers.goose_fast_trip import GOOSETransceiver, TripCause
from services.sitr_gateway import SITRGatewayService, GatewayConfig


def test_can_bms_dbc_parsing_and_telemetry():
    driver = IndustrialCANBMSDriver()
    assert len(driver.parsers) >= 3

    # Decode CATL Master frame: 1250V, -150A, 88.5% SoC, 99% SoH
    catl_payload = struct.pack("<HHHBB", 12500, 3500, 885, 99, 0x01)
    res = driver.decode_raw_frame(402908660, catl_payload)
    assert res["model"] == "catl_enerone_314ah"
    assert res["signals"]["Pack_Voltage"] == 1250.0
    assert res["signals"]["Pack_SOC"] == 88.5

    # Decode CATL Cell voltages: Cell1=3.285V, Cell2=3.290V, Cell3=3.288V
    catl_v_payload = struct.pack("<BBHHH", 1, 3, 3285, 3290, 3288)
    driver.decode_raw_frame(402777588, catl_v_payload)

    snap = driver.get_telemetry_snapshot()["safety_envelope"]
    assert snap["min_cell_voltage_v"] == 3.285
    assert snap["max_cell_voltage_v"] == 3.290
    assert snap["safety_trip_active"] is False


@pytest.mark.asyncio
async def test_iec104_sitr_handshake_and_setpoint():
    server = IEC104SITRServer(host="127.0.0.1", port=24060, common_address=1)
    await server.start()
    server.update_measurement(1001, 50.01)  # 50.01 Hz
    server.update_measurement(1003, 10.0)  # 10 MW

    client = IEC104SITRClient(host="127.0.0.1", port=24060, common_address=1)
    await client.connect()

    # General Interrogation
    await client.send_general_interrogation()
    asdus = await client.read_responses(timeout_sec=1.0)
    assert len(asdus) >= 1
    assert client.received_telemetry[1001] == 50.01

    # Send CEN Setpoint
    await client.send_setpoint(3001, 25.0)
    await client.read_responses(timeout_sec=0.5)
    assert server.data_store[3001] == 25.0

    await client.close()
    await server.stop()


@pytest.mark.asyncio
async def test_goose_fast_trip_sub_4ms():
    goose = GOOSETransceiver(interface="127.0.0.1", port=40020)
    goose.start_listener()

    received = []
    goose.add_subscriber_callback(lambda msg: received.append(msg))

    t0 = time.perf_counter()
    goose.publish_trip(cause=TripCause.UNDER_FREQUENCY_FFR)
    await goose.poll_incoming(timeout_sec=0.2)
    t1 = time.perf_counter()

    latency_ms = (t1 - t0) * 1000.0
    assert len(received) == 1
    assert received[0].trip_command is True
    max_latency = 4.0 if sys.platform.startswith("linux") else 10.0
    assert latency_ms < max_latency, f"Latency {latency_ms} ms exceeded {max_latency}ms limit"

    goose.close()


@pytest.mark.asyncio
async def test_sitr_gateway_orchestration_and_ffr():
    cfg = GatewayConfig(sitr_port=24061, goose_port=40021)
    gw = SITRGatewayService(cfg)
    await gw.start()
    await asyncio.sleep(0.3)

    # Underfrequency incident triggers FFR
    gw.grid_frequency_hz = 49.45
    await asyncio.sleep(0.05)
    assert gw.active_power_mw == 10.0

    await gw.stop()
