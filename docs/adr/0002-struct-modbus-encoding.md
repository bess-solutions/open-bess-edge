# ADR-0002: Use Python struct for Modbus Register Encoding/Decoding

## Status
✅ Accepted — 2026-02-19

## Context

The BESSAI Edge Gateway communicates with Huawei SUN2000/LUNA2000 inverters via **Modbus TCP** using `pymodbus`. Multi-register values (e.g., INT32, FLOAT32) require combining 16-bit Modbus registers into Python numeric types.

**pymodbus historically provided** `BinaryPayloadDecoder` and `BinaryPayloadBuilder` for this purpose. However, **these were removed in pymodbus 3.12** (released 2024), used by our target environment (Python 3.14+).

Alternatives after pymodbus 3.12:
1. **Python stdlib `struct`** — `struct.pack('>f', value)` / `struct.unpack`
2. **NumPy** — `np.frombuffer()` — adds a heavy dependency just for this use case
3. **Pin pymodbus < 3.12** — blocks security updates and Python 3.14 compatibility
4. **Manual bit shifting** — readable but error-prone for floating point

## Decision

Use **Python stdlib `struct`** for all Modbus register encoding/decoding.

Implementation in `src/drivers/modbus_driver.py`:
```python
# INT32: combine two consecutive 16-bit registers, big-endian
raw = (registers[0] << 16) | registers[1]
value = struct.unpack('>i', struct.pack('>I', raw))[0]

# FLOAT32: IEEE 754 representation
combined = (registers[0] << 16) | registers[1]
value = struct.unpack('>f', struct.pack('>I', combined))[0]
```

Supported data types: `INT32`, `UINT32`, `INT16`, `UINT16`, `FLOAT32`.

## Consequences

### Positive
- **Zero new dependencies**: `struct` is Python stdlib — always available
- **pymodbus 3.12+ compatible**: fully functional on latest releases including security patches
- **Python 3.14 compatible**: no deprecated API usage
- **Explicit byte order**: `>` (big-endian) matches Modbus register byte order specification
- **Auditable**: one-line encode/decode, easy to verify correctness

### Negative
- **Manual type dispatch**: `_decode_value()` has an `if/elif` chain for data types — must be extended for new types (e.g., STRING registers)
- **Less abstraction**: developers adding new register types must understand Modbus byte order

### Neutral
- FLOAT64 and STRING registers are not currently supported (not needed for SUN2000/LUNA2000 profiles)
- The device registry JSON format (`registry/*.json`) defines the data type per register, making it easy to add new types without changing core logic
