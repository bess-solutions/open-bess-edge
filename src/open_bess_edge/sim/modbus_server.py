"""Servidor Modbus TCP mínimo, independiente de pymodbus, con inyección de fallas.

Implementa FC03, FC04, FC06 y FC16 sobre un banco de registros que sólo expone las
direcciones mapeadas (leer una dirección no mapeada devuelve la excepción 0x02,
como haría un dispositivo real). Al ser una implementación *independiente* del
cliente, sirve también como segunda opinión de interoperabilidad.
"""

from __future__ import annotations

import asyncio
import logging
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

log = logging.getLogger("open_bess_edge.sim.modbus")


class IllegalAddress(Exception):
    pass


@dataclass
class RegisterBank:
    holding: dict[int, int] = field(default_factory=dict)
    input: dict[int, int] = field(default_factory=dict)

    def define(self, function: str, address: int, count: int, value: int = 0) -> None:
        store = self.holding if function == "holding" else self.input
        for a in range(address, address + count):
            store.setdefault(a, value)

    def read(self, function: str, address: int, count: int) -> list[int]:
        store = self.holding if function == "holding" else self.input
        try:
            return [store[a] for a in range(address, address + count)]
        except KeyError as exc:
            raise IllegalAddress(str(exc)) from exc

    def write(self, address: int, values: Iterable[int]) -> None:
        vals = list(values)
        for i in range(len(vals)):
            if address + i not in self.holding:
                raise IllegalAddress(str(address + i))
        for i, v in enumerate(vals):
            self.holding[address + i] = v & 0xFFFF


@dataclass
class Faults:
    delay_s: float = 0.0
    stall: bool = False                     # acepta la petición y no responde
    drop_next: int = 0                      # cierra la conexión sin responder
    truncate_next: int = 0                  # responde a medias y cierra
    garbage_next: int = 0                   # responde bytes aleatorios
    wrong_tid_next: int = 0                 # responde con transaction id equivocado
    exception_next: list[int] = field(default_factory=list)   # códigos a devolver en las próximas peticiones
    write_exception: Optional[int] = None   # excepción permanente en escrituras
    ignore_writes: bool = False             # confirma la escritura pero no la aplica
    ignore_unknown_unit: bool = True


class SimModbusServer:
    def __init__(self, bank: RegisterBank, unit_ids: Iterable[int] = (1,), host: str = "127.0.0.1", port: int = 0):
        self.bank = bank
        self.unit_ids = set(unit_ids)
        self.host, self.port = host, port
        self.faults = Faults()
        self.requests = 0
        self.write_log: list[tuple[float, int, list[int]]] = []
        self.on_write: list[Callable[[int, list[int]], None]] = []
        self._server: Optional[asyncio.AbstractServer] = None
        self._writers: set[asyncio.StreamWriter] = set()

    async def start(self) -> int:
        self._server = await asyncio.start_server(self._client, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            self.kick_all()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
            self._server = None

    def kick_all(self) -> None:
        """Cierra todas las conexiones de cliente (simula caída de enlace)."""
        for w in list(self._writers):
            try:
                w.close()
            except Exception:  # noqa: BLE001 # nosec B110
                pass
        self._writers.clear()

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._writers.add(writer)
        try:
            while True:
                header = await reader.readexactly(7)
                tid, pid, length, unit = struct.unpack(">HHHB", header)
                if pid != 0 or not 2 <= length <= 254:
                    break
                pdu = await reader.readexactly(length - 1)
                self.requests += 1
                reply = await self._handle(tid, unit, pdu, writer)
                if reply is None:
                    continue
                if reply == b"":
                    break
                writer.write(reply)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            self._writers.discard(writer)
            try:
                writer.close()
            except Exception:  # noqa: BLE001 # nosec B110
                pass

    @staticmethod
    def _mbap(tid: int, unit: int, pdu: bytes) -> bytes:
        return struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu

    @staticmethod
    def _exc(fc: int, code: int) -> bytes:
        return bytes([fc | 0x80, code])

    async def _handle(self, tid: int, unit: int, pdu: bytes, writer: asyncio.StreamWriter) -> Optional[bytes]:
        f = self.faults
        if f.stall:
            return None
        if unit not in self.unit_ids and f.ignore_unknown_unit:
            return None
        if f.delay_s > 0:
            await asyncio.sleep(f.delay_s)
        if f.drop_next > 0:
            f.drop_next -= 1
            return b""
        if f.garbage_next > 0:
            f.garbage_next -= 1
            writer.write(os.urandom(11))
            await writer.drain()
            return None

        fc = pdu[0]
        try:
            body = self._execute(fc, pdu)
        except IllegalAddress:
            body = self._exc(fc, 0x02)
        except ValueError:
            body = self._exc(fc, 0x03)
        if f.exception_next:
            body = self._exc(fc, int(f.exception_next.pop(0)))
        rtid = (tid + 1) & 0xFFFF if f.wrong_tid_next > 0 else tid
        if f.wrong_tid_next > 0:
            f.wrong_tid_next -= 1
        frame = self._mbap(rtid, unit, body)
        if f.truncate_next > 0:
            f.truncate_next -= 1
            writer.write(frame[: max(1, len(frame) // 2)])
            await writer.drain()
            return b""
        return frame

    def _execute(self, fc: int, pdu: bytes) -> bytes:
        f = self.faults
        if fc in (3, 4):
            if len(pdu) != 5:
                raise ValueError
            addr, count = struct.unpack(">HH", pdu[1:5])
            if not 1 <= count <= 125:
                raise ValueError
            regs = self.bank.read("holding" if fc == 3 else "input", addr, count)
            return bytes([fc, count * 2]) + struct.pack(f">{count}H", *regs)
        if fc == 6:
            if len(pdu) != 5:
                raise ValueError
            addr, val = struct.unpack(">HH", pdu[1:5])
            if f.write_exception is not None:
                return self._exc(fc, f.write_exception)
            self._apply_write(addr, [val])
            return pdu
        if fc == 16:
            if len(pdu) < 6:
                raise ValueError
            addr, count, bc = struct.unpack(">HHB", pdu[1:6])
            if not 1 <= count <= 123 or bc != count * 2 or len(pdu) != 6 + bc:
                raise ValueError
            if f.write_exception is not None:
                return self._exc(fc, f.write_exception)
            vals = list(struct.unpack(f">{count}H", pdu[6:]))
            self._apply_write(addr, vals)
            return struct.pack(">BHH", fc, addr, count)
        return self._exc(fc, 0x01)

    def _apply_write(self, addr: int, vals: list[int]) -> None:
        if self.faults.ignore_writes:
            # valida direcciones pero no aplica
            for i in range(len(vals)):
                if addr + i not in self.bank.holding:
                    raise IllegalAddress(str(addr + i))
            return
        self.bank.write(addr, vals)
        self.write_log.append((time.monotonic(), addr, list(vals)))
        for cb in self.on_write:
            cb(addr, list(vals))
