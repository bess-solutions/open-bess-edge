import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from open_bess_edge.errors import CodecError
from open_bess_edge.modbus.codec import Order, RegType, decode, encode

INT_TYPES = [t for t in RegType if not t.is_float]
RANGES = {
    RegType.UINT16: (0, 2**16 - 1), RegType.ENUM16: (0, 2**16 - 1), RegType.INT16: (-(2**15), 2**15 - 1),
    RegType.UINT32: (0, 2**32 - 1), RegType.INT32: (-(2**31), 2**31 - 1),
    RegType.UINT64: (0, 2**64 - 1), RegType.INT64: (-(2**63), 2**63 - 1),
}


@pytest.mark.parametrize("bo", list(Order))
@pytest.mark.parametrize("wo", list(Order))
@given(data=st.data())
def test_integer_roundtrip_all_orders(bo, wo, data):
    t = data.draw(st.sampled_from(INT_TYPES))
    lo, hi = RANGES[t]
    v = data.draw(st.integers(lo, hi))
    regs = encode(v, t, bo, wo)
    assert len(regs) == t.width and all(0 <= r <= 0xFFFF for r in regs)
    assert decode(regs, t, bo, wo) == v


@given(v=st.floats(width=32, allow_nan=False, allow_infinity=False), bo=st.sampled_from(list(Order)), wo=st.sampled_from(list(Order)))
def test_float32_roundtrip(v, bo, wo):
    assert decode(encode(v, RegType.FLOAT32, bo, wo), RegType.FLOAT32, bo, wo) == v


@given(v=st.floats(allow_nan=False, allow_infinity=False))
def test_float64_roundtrip(v):
    assert decode(encode(v, RegType.FLOAT64), RegType.FLOAT64) == v


def test_known_vectors():
    assert encode(0x12345678, RegType.UINT32) == [0x1234, 0x5678]
    assert encode(0x12345678, RegType.UINT32, word_order=Order.LITTLE) == [0x5678, 0x1234]
    assert encode(0x1234, RegType.UINT16, byte_order=Order.LITTLE) == [0x3412]
    assert encode(-250, RegType.INT16) == [65286]
    assert decode([0x42C8, 0x0000], RegType.FLOAT32) == 100.0   # IEEE 754


@pytest.mark.parametrize("t", INT_TYPES)
def test_overflow_is_rejected_never_wrapped(t):
    lo, hi = RANGES[t]
    with pytest.raises(CodecError):
        encode(hi + 1, t)
    with pytest.raises(CodecError):
        encode(lo - 1, t)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_rejected(bad):
    for t in RegType:
        with pytest.raises(CodecError):
            encode(bad, t)


def test_float32_overflow_rejected():
    with pytest.raises(CodecError):
        encode(1e39, RegType.FLOAT32)


def test_decode_rejects_bad_register_values_and_width():
    with pytest.raises(CodecError):
        decode([70000], RegType.UINT16)
    with pytest.raises(CodecError):
        decode([-1], RegType.INT16)
    with pytest.raises(CodecError):
        decode([1], RegType.UINT32)
    with pytest.raises(CodecError):
        decode([True], RegType.UINT16)


def test_decode_float_nan_passthrough():
    assert math.isnan(decode([0x7FC0, 0x0000], RegType.FLOAT32))


def test_encode_rejects_non_numeric():
    with pytest.raises(CodecError):
        encode("1", RegType.UINT16)  # type: ignore[arg-type]
    with pytest.raises(CodecError):
        encode(True, RegType.UINT16)
