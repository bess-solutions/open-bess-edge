"""Codificación/decodificación de registros Modbus (16 bit) a valores tipados.

Soporta los tipos que usan los perfiles de ``registry/``: UINT16, INT16, ENUM16,
UINT32, INT32, UINT64, INT64, FLOAT32 y FLOAT64, con orden de bytes (dentro de
cada registro) y de palabras (entre registros) configurables.

Garantías:
* ``encode`` **nunca** envuelve (wrap-around) un desborde: lanza ``CodecError``.
* ``decode`` acepta únicamente enteros 0..0xFFFF por registro.
* Valores FLOAT no finitos se devuelven tal cual (NaN/inf); es responsabilidad
  del driver marcarlos como inválidos.
"""

from __future__ import annotations

import math
import struct
from enum import Enum
from typing import Sequence

from ..errors import CodecError


class RegType(str, Enum):
    UINT16 = "UINT16"
    INT16 = "INT16"
    ENUM16 = "ENUM16"
    UINT32 = "UINT32"
    INT32 = "INT32"
    UINT64 = "UINT64"
    INT64 = "INT64"
    FLOAT32 = "FLOAT32"
    FLOAT64 = "FLOAT64"

    @property
    def width(self) -> int:
        """Cantidad de registros de 16 bit que ocupa el tipo."""
        return _WIDTH[self]

    @property
    def is_float(self) -> bool:
        return self in (RegType.FLOAT32, RegType.FLOAT64)

    @property
    def is_signed(self) -> bool:
        return self in (RegType.INT16, RegType.INT32, RegType.INT64)


_WIDTH = {
    RegType.UINT16: 1, RegType.INT16: 1, RegType.ENUM16: 1,
    RegType.UINT32: 2, RegType.INT32: 2, RegType.FLOAT32: 2,
    RegType.UINT64: 4, RegType.INT64: 4, RegType.FLOAT64: 4,
}

_STRUCT = {
    RegType.UINT16: ">H", RegType.INT16: ">h", RegType.ENUM16: ">H",
    RegType.UINT32: ">I", RegType.INT32: ">i", RegType.FLOAT32: ">f",
    RegType.UINT64: ">Q", RegType.INT64: ">q", RegType.FLOAT64: ">d",
}

_INT_RANGE = {
    RegType.UINT16: (0, 0xFFFF), RegType.ENUM16: (0, 0xFFFF), RegType.INT16: (-0x8000, 0x7FFF),
    RegType.UINT32: (0, 0xFFFFFFFF), RegType.INT32: (-0x80000000, 0x7FFFFFFF),
    RegType.UINT64: (0, 2**64 - 1), RegType.INT64: (-(2**63), 2**63 - 1),
}


class Order(str, Enum):
    BIG = "BIG"
    LITTLE = "LITTLE"


def _to_bytes(regs: Sequence[int], byte_order: Order, word_order: Order) -> bytes:
    words = list(regs)
    if word_order is Order.LITTLE:
        words.reverse()
    out = bytearray()
    for w in words:
        b = int(w).to_bytes(2, "big")
        out += b[::-1] if byte_order is Order.LITTLE else b
    return bytes(out)


def _from_bytes(raw: bytes, byte_order: Order, word_order: Order) -> list[int]:
    words = []
    for i in range(0, len(raw), 2):
        b = raw[i : i + 2]
        if byte_order is Order.LITTLE:
            b = b[::-1]
        words.append(int.from_bytes(b, "big"))
    if word_order is Order.LITTLE:
        words.reverse()
    return words


def decode(
    regs: Sequence[int],
    rtype: RegType,
    byte_order: Order = Order.BIG,
    word_order: Order = Order.BIG,
) -> int | float:
    """Decodifica ``rtype.width`` registros a un valor crudo (sin escala)."""
    if len(regs) != rtype.width:
        raise CodecError(f"{rtype.value} requiere {rtype.width} registro(s), se recibieron {len(regs)}")
    for r in regs:
        if not isinstance(r, int) or isinstance(r, bool) or not 0 <= r <= 0xFFFF:
            raise CodecError(f"registro fuera de rango 0..65535: {r!r}")
    raw = _to_bytes(regs, byte_order, word_order)
    return struct.unpack(_STRUCT[rtype], raw)[0]


def encode(
    value: float,
    rtype: RegType,
    byte_order: Order = Order.BIG,
    word_order: Order = Order.BIG,
) -> list[int]:
    """Codifica un valor crudo a registros. Lanza ``CodecError`` en desborde o valor no finito."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CodecError(f"valor no numérico: {value!r}")
    if not math.isfinite(value):
        raise CodecError(f"valor no finito no codificable: {value!r}")
    if rtype.is_float:
        try:
            raw = struct.pack(_STRUCT[rtype], float(value))
        except (OverflowError, struct.error) as exc:
            raise CodecError(f"{value!r} no representable como {rtype.value}") from exc
        if rtype is RegType.FLOAT32 and math.isinf(struct.unpack(">f", raw)[0]):
            raise CodecError(f"{value!r} desborda FLOAT32")
    else:
        iv = int(round(value))
        lo, hi = _INT_RANGE[rtype]
        if not lo <= iv <= hi:
            raise CodecError(f"{value!r} fuera del rango {rtype.value} [{lo}, {hi}]")
        raw = struct.pack(_STRUCT[rtype], iv)
    return _from_bytes(raw, byte_order, word_order)
