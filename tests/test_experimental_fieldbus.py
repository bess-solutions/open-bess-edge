"""Módulos experimentales: se verifica lo que SÍ está demostrado; los límites quedan documentados."""
import asyncio
import struct
import threading
import time

import pytest

from open_bess_edge.experimental.goose import GOOSEMessage, TripCause
from open_bess_edge.experimental.iec104 import APCIType, IEC104Frame, IEC104SITRServer

c104 = pytest.importorskip("c104")


async def test_iec104_interop_with_independent_client_startdt_and_general_interrogation():
    srv = IEC104SITRServer(host="127.0.0.1", port=24781, common_address=1)
    await srv.start()
    srv.update_measurement(1001, 49.97)
    out: dict = {}

    def client():
        cl = c104.Client(tick_rate_ms=100, command_timeout_ms=2000)
        conn = cl.add_connection(ip="127.0.0.1", port=24781, init=c104.Init.ALL)
        st = conn.add_station(common_address=1)
        pt = st.add_point(io_address=1001, type=c104.Type.M_ME_NC_1)
        cl.start()
        conn.connect()
        t0 = time.time()
        while conn.state != c104.ConnectionState.OPEN and time.time() - t0 < 3:
            time.sleep(0.05)
        out["state"] = conn.state
        conn.interrogation(common_address=1, cause=c104.Cot.ACTIVATION, wait_for_response=True)
        time.sleep(0.4)
        out["value"] = pt.value
        cl.stop()

    t = threading.Thread(target=client)
    t.start()
    while t.is_alive():
        await asyncio.sleep(0.05)
    try:
        assert out["state"] == c104.ConnectionState.OPEN                 # STARTDT act/con correcto
        assert out["value"] == pytest.approx(49.97, abs=1e-4)             # M_ME_NC_1 float32 correcto
        assert srv.rejected_frames >= 1                                   # C_CS_NA_1 (no soportado) descartado sin cerrar
    finally:
        await srv.stop()


async def test_iec104_server_survives_malformed_frames():
    srv = IEC104SITRServer(host="127.0.0.1", port=24782)
    await srv.start()
    try:
        r, w = await asyncio.open_connection("127.0.0.1", 24782)
        w.write(b"\x00\xff\x13garbage")                                   # ruido antes del inicio 0x68
        w.write(b"\x68\x02\x00\x00")                                      # APDU demasiado corta
        w.write(b"\x68\x0e" + struct.pack("<HH", 0, 0) + bytes([99, 1, 6, 0, 1, 0]) + b"\x00" * 4)   # ASDU tipo 99 (inexistente)
        w.write(IEC104Frame.build_u_frame(APCIType.STARTDT_ACT))
        await w.drain()
        got = b""
        while APCIType.STARTDT_CON not in got[2::6]:                      # salta los S-frames de acuse
            got += await asyncio.wait_for(r.read(6), 2.0)
        assert srv.rejected_frames >= 2                                    # sigue respondiendo con normalidad
        w.close()
    finally:
        await srv.stop()


def test_goose_codec_roundtrip_is_self_consistent_only():
    """Sólo prueba el códec propio (ida y vuelta). No hay oráculo independiente y NO se afirma latencia."""
    msg = GOOSEMessage(gocb_ref="X/LLN0$GO$gcb", trip_command=True, trip_cause=TripCause.UNDER_FREQUENCY_FFR)
    back = GOOSEMessage.decode_apdu(msg.encode_apdu())
    assert back.trip_command is True and back.gocb_ref == "X/LLN0$GO$gcb"
