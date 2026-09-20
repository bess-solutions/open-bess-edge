"""IEC 60870-5-104 Telemetry Client & Server Driver for Chilean CEN SITR.

Designed for Open BESS Edge & BESSAI Distributed Intelligence Architecture.
Complies with DS N° 125/2017, Res. CNE N° 588, and CEN SITR Technical Standard.
Handles APCI (U/S/I frames), ASDU Types 1, 13, 36, 45, 50, 100, and CP56Time2a timestamps.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("open_bess_edge.experimental.iec104")


class APCIType(IntEnum):
    I_FORMAT = 0
    S_FORMAT = 1
    TESTFR_ACT = 0x43
    TESTFR_CON = 0x83
    STOPDT_ACT = 0x13
    STOPDT_CON = 0x23
    STARTDT_ACT = 0x07
    STARTDT_CON = 0x0B


class ASDUType(IntEnum):
    M_SP_NA_1 = 1  # Single-point information (Breaker status)
    M_ME_NA_1 = 9  # Measured value, normalized
    M_ME_NC_1 = 13  # Measured value, short floating point (P, Q, V, f, SoC)
    M_ME_TF_1 = 36  # Measured value, short float with CP56Time2a
    C_SC_NA_1 = 45  # Single command (Trip / Close)
    C_SE_NA_1 = 48  # Set-point command, normalized
    C_SE_NC_1 = 50  # Set-point command, short floating point (MW, MVAr)
    C_IC_NA_1 = 100  # Interrogation command (General Interrogation)


class CauseOfTransmission(IntEnum):
    PERIODIC = 1
    BACKGROUND = 2
    SPONTANEOUS = 3
    INITIALIZED = 4
    ACTIVATION = 6
    ACTIVATION_CON = 7
    DEACTIVATION = 8
    DEACTIVATION_CON = 9
    ACTIVATION_TERM = 10
    INTERROGATED_BY_GEN = 20


# Standard CEN SITR IOA Registry
CEN_IOA_MAP = {
    1001: ("GRID_FREQ_HZ", "Hz", ASDUType.M_ME_NC_1),
    1002: ("BUS_VOLTAGE_KV", "kV", ASDUType.M_ME_NC_1),
    1003: ("ACTIVE_POWER_MW", "MW", ASDUType.M_ME_NC_1),
    1004: ("REACTIVE_POWER_MVAR", "MVAr", ASDUType.M_ME_NC_1),
    1005: ("BESS_SOC_PCT", "%", ASDUType.M_ME_NC_1),
    1006: ("AVAIL_CHARGE_MWH", "MWh", ASDUType.M_ME_NC_1),
    1007: ("AVAIL_DISCHARGE_MWH", "MWh", ASDUType.M_ME_NC_1),
    2001: ("BREAKER_52G_STATUS", "state", ASDUType.M_SP_NA_1),
    3001: ("P_SETPOINT_CMD_MW", "MW", ASDUType.C_SE_NC_1),
    3002: ("Q_SETPOINT_CMD_MVAR", "MVAr", ASDUType.C_SE_NC_1),
}


def encode_cp56time2a(dt: Optional[datetime.datetime] = None) -> bytes:
    """Encode datetime into 7-byte IEC 60870-5-104 CP56Time2a binary timestamp."""
    if dt is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    ms = (dt.second * 1000) + (dt.microsecond // 1000)
    minute = dt.minute & 0x3F
    hour = dt.hour & 0x1F
    day_of_month = dt.day & 0x1F
    day_of_week = (dt.isoweekday() % 7) << 5
    day_byte = day_of_month | day_of_week
    month = dt.month & 0x0F
    year = (dt.year % 100) & 0x7F

    return struct.pack("<HBBBBB", ms, minute, hour, day_byte, month, year)


def decode_cp56time2a(data: bytes) -> datetime.datetime:
    """Decode 7-byte IEC 60870-5-104 CP56Time2a binary timestamp."""
    ms, minute, hour, day_byte, month, year = struct.unpack("<HBBBBB", data[:7])
    second = ms // 1000
    microsecond = (ms % 1000) * 1000
    day = day_byte & 0x1F
    full_year = 2000 + (year & 0x7F)
    return datetime.datetime(
        full_year, month & 0x0F, day, hour & 0x1F, minute & 0x3F, second, microsecond, tzinfo=datetime.timezone.utc
    )


@dataclass
class ASDUObject:
    ioa: int
    value: Any
    quality: int = 0x00  # 0x00 = valid, 0x80 = invalid, 0x40 = reserved
    timestamp: Optional[datetime.datetime] = None


@dataclass
class ASDU:
    type_id: ASDUType
    is_sequence: bool
    num_objects: int
    cot: CauseOfTransmission
    common_address: int
    objects: List[ASDUObject] = field(default_factory=list)

    def encode(self) -> bytes:
        vsq = (0x80 if self.is_sequence else 0x00) | (self.num_objects & 0x7F)
        # Header: type_id (1B), vsq (1B), cot (2B), common_address (2B)
        hdr = struct.pack("<BBHH", int(self.type_id), vsq, int(self.cot), self.common_address)
        body = bytearray()

        for obj in self.objects:
            ioa_bytes = struct.pack("<I", obj.ioa)[:3]
            body.extend(ioa_bytes)

            if self.type_id == ASDUType.M_SP_NA_1:
                val_byte = 1 if obj.value else 0
                body.append(val_byte | (obj.quality & 0xFE))
            elif self.type_id == ASDUType.M_ME_NC_1:
                val_bytes = struct.pack("<f", float(obj.value))
                body.extend(val_bytes)
                body.append(obj.quality)
            elif self.type_id == ASDUType.M_ME_TF_1:
                val_bytes = struct.pack("<f", float(obj.value))
                body.extend(val_bytes)
                body.append(obj.quality)
                body.extend(encode_cp56time2a(obj.timestamp))
            elif self.type_id == ASDUType.C_SE_NC_1:
                val_bytes = struct.pack("<f", float(obj.value))
                body.extend(val_bytes)
                body.append(0x00)  # QOS (select/execute)
            elif self.type_id == ASDUType.C_SC_NA_1:
                cmd_byte = 1 if obj.value else 0
                body.append(cmd_byte)
            elif self.type_id == ASDUType.C_IC_NA_1:
                body.append(20)  # QOI = 20 (General Interrogation)

        return bytes(hdr) + bytes(body)

    @classmethod
    def decode(cls, data: bytes) -> ASDU:
        if len(data) < 6:
            raise ValueError("ASDU data too short")
        type_id_raw, vsq, cot_raw, common_addr = struct.unpack("<BBHH", data[:6])
        type_id = ASDUType(type_id_raw)
        cot = CauseOfTransmission(cot_raw & 0x3F)
        is_seq = bool(vsq & 0x80)
        num_objs = vsq & 0x7F

        objects = []
        offset = 6

        for _ in range(num_objs):
            if offset + 3 > len(data):
                break
            ioa = struct.unpack("<I", data[offset : offset + 3] + b"\x00")[0]
            offset += 3

            if type_id == ASDUType.M_SP_NA_1:
                val = bool(data[offset] & 0x01)
                q = data[offset] & 0xFE
                offset += 1
                objects.append(ASDUObject(ioa=ioa, value=val, quality=q))
            elif type_id == ASDUType.M_ME_NC_1:
                val = struct.unpack("<f", data[offset : offset + 4])[0]
                q = data[offset + 4]
                offset += 5
                objects.append(ASDUObject(ioa=ioa, value=round(val, 4), quality=q))
            elif type_id == ASDUType.M_ME_TF_1:
                val = struct.unpack("<f", data[offset : offset + 4])[0]
                q = data[offset + 4]
                ts = decode_cp56time2a(data[offset + 5 : offset + 12])
                offset += 12
                objects.append(ASDUObject(ioa=ioa, value=round(val, 4), quality=q, timestamp=ts))
            elif type_id == ASDUType.C_SE_NC_1:
                val = struct.unpack("<f", data[offset : offset + 4])[0]
                qos = data[offset + 4]
                offset += 5
                objects.append(ASDUObject(ioa=ioa, value=round(val, 4), quality=qos))
            elif type_id == ASDUType.C_IC_NA_1:
                qoi = data[offset]
                offset += 1
                objects.append(ASDUObject(ioa=ioa, value=qoi))

        return cls(
            type_id=type_id,
            is_sequence=is_seq,
            num_objects=len(objects),
            cot=cot,
            common_address=common_addr,
            objects=objects,
        )


class IEC104Frame:
    """Represents a complete IEC 60870-5-104 APDU frame."""

    @staticmethod
    def build_u_frame(apci_type: APCIType) -> bytes:
        return struct.pack("<BBBBBB", 0x68, 0x04, int(apci_type), 0x00, 0x00, 0x00)

    @staticmethod
    def build_s_frame(receive_seq: int) -> bytes:
        nr_field = (receive_seq << 1) & 0xFFFE
        return struct.pack("<BBHH", 0x68, 0x04, 0x01, nr_field)

    @staticmethod
    def build_i_frame(send_seq: int, receive_seq: int, asdu_bytes: bytes) -> bytes:
        length = 4 + len(asdu_bytes)
        ns_field = (send_seq << 1) & 0xFFFE
        nr_field = (receive_seq << 1) & 0xFFFE
        apci = struct.pack("<BBHH", 0x68, length, ns_field, nr_field)
        return apci + asdu_bytes


class IEC104SITRServer:
    """IEC 60870-5-104 Outstation (Server) for CEN SITR Connection.

    Receives General Interrogations and Setpoints, streams real-time measurements.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 2404, common_address: int = 1):
        self.host = host
        self.port = port
        self.common_address = common_address
        self.send_seq = 0
        self.recv_seq = 0
        self.data_store: Dict[int, float] = {
            1001: 50.00,  # Grid Frequency (Hz)
            1002: 220.0,  # Bus Voltage (kV)
            1003: 0.0,  # Active Power (MW)
            1004: 0.0,  # Reactive Power (MVAr)
            1005: 85.0,  # SoC (%)
            1006: 12.5,  # Available Charge (MWh)
            1007: 35.0,  # Available Discharge (MWh)
            2001: 1.0,  # 52G Breaker Closed (1)
        }
        self.server: Optional[asyncio.Server] = None
        self.active_writer: Optional[asyncio.StreamWriter] = None
        self.setpoint_callback: Optional[Callable[[int, float], None]] = None
        self.is_started = False
        self.rejected_frames = 0

    def update_measurement(self, ioa: int, value: float) -> None:
        self.data_store[ioa] = value

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self.is_started = True
        logger.info(f"IEC 60870-5-104 SITR Server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            if self.active_writer is not None:          # Python >= 3.12: wait_closed espera a las conexiones abiertas
                self.active_writer.close()
            await asyncio.wait_for(self.server.wait_closed(), timeout=3.0)
            self.is_started = False
            logger.info("IEC 60870-5-104 SITR Server stopped.")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.active_writer = writer
        logger.info(f"New CEN SITR Client connection from {writer.get_extra_info('peername')}")

        try:
            while True:
                # Read start byte 0x68
                b1 = await reader.read(1)
                if not b1:
                    break
                if b1 != b"\x68":
                    continue

                len_byte = await reader.read(1)
                if not len_byte:
                    break
                apdu_len = len_byte[0]
                apdu_rest = await reader.readexactly(apdu_len)
                await self._process_frame(apdu_rest, writer)

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            self.active_writer = None

    async def _process_frame(self, data: bytes, writer: asyncio.StreamWriter) -> None:
        if len(data) < 4:
            self.rejected_frames += 1
            return
        ctrl1 = data[0]

        # Check U-format (bits 0-1 = 11)
        if (ctrl1 & 0x03) == 0x03:
            if ctrl1 == APCIType.STARTDT_ACT:
                logger.info("[IEC104] Received STARTDT ACT -> Sending STARTDT CON")
                writer.write(IEC104Frame.build_u_frame(APCIType.STARTDT_CON))
                await writer.drain()
            elif ctrl1 == APCIType.TESTFR_ACT:
                writer.write(IEC104Frame.build_u_frame(APCIType.TESTFR_CON))
                await writer.drain()
            return

        # Check S-format (bits 0-1 = 01)
        if (ctrl1 & 0x03) == 0x01:
            nr = struct.unpack("<H", data[2:4])[0] >> 1
            self.recv_seq = nr
            return

        # I-format (bit 0 = 0)
        ns = struct.unpack("<H", data[0:2])[0] >> 1
        nr = struct.unpack("<H", data[2:4])[0] >> 1
        self.recv_seq = ns + 1

        # Send S-frame acknowledge
        writer.write(IEC104Frame.build_s_frame(self.recv_seq))
        await writer.drain()

        # Parse ASDU
        asdu_data = data[4:]
        if asdu_data:
            try:
                asdu = ASDU.decode(asdu_data)
            except (ValueError, struct.error) as exc:
                # Tipo/estructura no soportados (p. ej. C_CS_NA_1 de sincronización de reloj): se ignora sin
                # cerrar la conexión. Una implementación completa respondería COT=44 (tipo desconocido).
                self.rejected_frames += 1
                logger.warning("[IEC104] ASDU no soportado/ inválido descartado: %s", exc)
                return
            await self._handle_asdu(asdu, writer)

    async def _handle_asdu(self, asdu: ASDU, writer: asyncio.StreamWriter) -> None:
        if asdu.type_id == ASDUType.C_IC_NA_1:
            logger.info("[IEC104] Interrogation Command (General Interrogation) received.")
            # 1. Activation Con
            asdu_actcon = ASDU(
                type_id=ASDUType.C_IC_NA_1,
                is_sequence=False,
                num_objects=1,
                cot=CauseOfTransmission.ACTIVATION_CON,
                common_address=self.common_address,
                objects=[ASDUObject(ioa=0, value=20)],
            )
            i_frame_actcon = IEC104Frame.build_i_frame(self.send_seq, self.recv_seq, asdu_actcon.encode())
            self.send_seq += 1
            writer.write(i_frame_actcon)
            await writer.drain()

            # 2. Transmit all current measurements (ASDU 13)
            objs = [
                ASDUObject(ioa=ioa, value=val)
                for ioa, val in self.data_store.items()
                if ioa in [1001, 1002, 1003, 1004, 1005, 1006, 1007]
            ]
            asdu_resp = ASDU(
                type_id=ASDUType.M_ME_NC_1,
                is_sequence=False,
                num_objects=len(objs),
                cot=CauseOfTransmission.INTERROGATED_BY_GEN,
                common_address=self.common_address,
                objects=objs,
            )
            i_frame_resp = IEC104Frame.build_i_frame(self.send_seq, self.recv_seq, asdu_resp.encode())
            self.send_seq += 1
            writer.write(i_frame_resp)
            await writer.drain()

            # 3. Activation Termination
            asdu_term = ASDU(
                type_id=ASDUType.C_IC_NA_1,
                is_sequence=False,
                num_objects=1,
                cot=CauseOfTransmission.ACTIVATION_TERM,
                common_address=self.common_address,
                objects=[ASDUObject(ioa=0, value=20)],
            )
            i_frame_term = IEC104Frame.build_i_frame(self.send_seq, self.recv_seq, asdu_term.encode())
            self.send_seq += 1
            writer.write(i_frame_term)
            await writer.drain()

        elif asdu.type_id in (ASDUType.C_SE_NC_1, ASDUType.C_SC_NA_1):
            # Setpoint or single command from CEN Despacho
            for obj in asdu.objects:
                logger.info(f"[IEC104 Command] CEN Setpoint IOA {obj.ioa} -> {obj.value}")
                if self.setpoint_callback:
                    self.setpoint_callback(obj.ioa, float(obj.value))
                self.data_store[obj.ioa] = float(obj.value)

            # Echo Activation Confirmation
            asdu.cot = CauseOfTransmission.ACTIVATION_CON
            i_frame = IEC104Frame.build_i_frame(self.send_seq, self.recv_seq, asdu.encode())
            self.send_seq += 1
            writer.write(i_frame)
            await writer.drain()


class IEC104SITRClient:
    """IEC 60870-5-104 Client for testing or polling SITR RTUs."""

    def __init__(self, host: str = "127.0.0.1", port: int = 2404, common_address: int = 1):
        self.host = host
        self.port = port
        self.common_address = common_address
        self.send_seq = 0
        self.recv_seq = 0
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.received_telemetry: Dict[int, float] = {}

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        # Send STARTDT ACT
        self.writer.write(IEC104Frame.build_u_frame(APCIType.STARTDT_ACT))
        await self.writer.drain()

        # Read STARTDT CON
        b1 = await self.reader.read(1)
        if b1 == b"\x68":
            frame_length = (await self.reader.read(1))[0]
            resp = await self.reader.readexactly(frame_length)
            if resp[0] == APCIType.STARTDT_CON:
                logger.info("[Client] STARTDT handshake verified!")

    async def send_general_interrogation(self) -> None:
        if not self.writer:
            raise RuntimeError("Client not connected")
        asdu_gi = ASDU(
            type_id=ASDUType.C_IC_NA_1,
            is_sequence=False,
            num_objects=1,
            cot=CauseOfTransmission.ACTIVATION,
            common_address=self.common_address,
            objects=[ASDUObject(ioa=0, value=20)],
        )
        frame = IEC104Frame.build_i_frame(self.send_seq, self.recv_seq, asdu_gi.encode())
        self.send_seq += 1
        self.writer.write(frame)
        await self.writer.drain()

    async def send_setpoint(self, ioa: int, value: float) -> None:
        if not self.writer:
            raise RuntimeError("Client not connected")
        asdu_sp = ASDU(
            type_id=ASDUType.C_SE_NC_1,
            is_sequence=False,
            num_objects=1,
            cot=CauseOfTransmission.ACTIVATION,
            common_address=self.common_address,
            objects=[ASDUObject(ioa=ioa, value=value)],
        )
        frame = IEC104Frame.build_i_frame(self.send_seq, self.recv_seq, asdu_sp.encode())
        self.send_seq += 1
        self.writer.write(frame)
        await self.writer.drain()

    async def read_responses(self, timeout_sec: float = 2.0) -> List[ASDU]:
        results: List[ASDU] = []
        end_time = time.time() + timeout_sec
        while time.time() < end_time and self.reader:
            try:
                b1 = await asyncio.wait_for(self.reader.read(1), timeout=0.5)
                if not b1 or b1 != b"\x68":
                    continue
                apdu_len = (await self.reader.read(1))[0]
                apdu = await self.reader.readexactly(apdu_len)

                ctrl1 = apdu[0]
                if (ctrl1 & 0x01) == 0:  # I-format
                    ns = struct.unpack("<H", apdu[0:2])[0] >> 1
                    self.recv_seq = ns + 1
                    asdu_data = apdu[4:]
                    asdu = ASDU.decode(asdu_data)
                    results.append(asdu)
                    for obj in asdu.objects:
                        if isinstance(obj.value, (int, float)):
                            self.received_telemetry[obj.ioa] = float(obj.value)

            except asyncio.TimeoutError:
                break
        return results

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()


async def _run_self_test():
    import json

    print("=== IEC 60870-5-104 SITR CEN Driver Self-Test ===")
    server = IEC104SITRServer(host="127.0.0.1", port=24040, common_address=1)
    await server.start()

    # Update server measurements with live Linares BESS operational values
    server.update_measurement(1001, 50.012)  # Grid Frequency 50.012 Hz
    server.update_measurement(1002, 220.45)  # Bus Voltage 220.45 kV
    server.update_measurement(1003, -15.5)  # Active Power -15.5 MW (Charging during solar peak)
    server.update_measurement(1004, 2.1)  # Reactive Power 2.1 MVAr (Capacitive voltage support)
    server.update_measurement(1005, 78.4)  # SoC 78.4%

    client = IEC104SITRClient(host="127.0.0.1", port=24040, common_address=1)
    await client.connect()

    # Send General Interrogation (GI)
    print("[Client] Sending General Interrogation to SITR Outstation...")
    await client.send_general_interrogation()
    asdus = await client.read_responses(timeout_sec=1.5)
    print(f"[Client] Received {len(asdus)} ASDU responses.")
    print(f"[Client] SITR Telemetry Table:\n{json.dumps(client.received_telemetry, indent=2)}")

    # Send Setpoint ASDU 50 (Dispatch instruction from CEN Despacho)
    print("[Client] Sending CEN Dispatch Setpoint IOA 3001 = 20.0 MW (Discharge)...")
    await client.send_setpoint(3001, 20.0)
    ack_asdus = await client.read_responses(timeout_sec=1.0)
    print(f"[Client] Setpoint Ack ASDUs: {len(ack_asdus)}")
    print(f"[Server Store] IOA 3001 value is now: {server.data_store.get(3001)} MW")

    await client.close()
    await server.stop()
    print("=== IEC 60870-5-104 SITR Driver Test Passed Successfully ===")


if __name__ == "__main__":
    asyncio.run(_run_self_test())
