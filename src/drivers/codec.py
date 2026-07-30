# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
src/drivers/codec.py
====================
Unifies profile loading and raw Modbus payload encoding/decoding.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DriverConfigError(Exception):
    """Raised when the device profile JSON is malformed or missing."""


class TagNotFoundError(KeyError):
    """Raised when a requested tag name is not defined in the profile."""


# ---------------------------------------------------------------------------
# Endianness Mapping
# ---------------------------------------------------------------------------

_ENDIAN_MAP: Final[dict[str, str]] = {
    "BIG": ">",
    "LITTLE": "<",
}


def resolve_endian(value: str, field: str) -> str:
    try:
        return _ENDIAN_MAP[value.upper()]
    except KeyError:
        raise DriverConfigError(f"Invalid {field} '{value}'. Must be 'BIG' or 'LITTLE'.") from None


# ---------------------------------------------------------------------------
# Register Codec
# ---------------------------------------------------------------------------

class RegisterCodec:
    """
    Handles BESS profile loading, register lookup, and raw Modbus word
    encoding/decoding.
    """

    def __init__(self, profile_path: Path | str) -> None:
        self.profile_path = Path(profile_path)
        self.profile = self._load_profile(self.profile_path)
        self.registers: dict[str, dict[str, Any]] = self.profile["registers"]

        conn = self.profile.get("connection", {})
        self.byte_order = resolve_endian(conn.get("byte_order", "BIG"), "byte_order")
        self.word_order = resolve_endian(conn.get("word_order", "BIG"), "word_order")

    @staticmethod
    def _load_profile(path: Path) -> dict[str, Any]:
        """Load and validate the JSON device profile."""
        if not path.exists():
            raise DriverConfigError(f"Device profile not found: {path}")
        try:
            with path.open("r", encoding="utf-8") as fh:
                profile: dict[str, Any] = json.load(fh)
        except json.JSONDecodeError as exc:
            raise DriverConfigError(f"Device profile JSON is invalid: {path}") from exc

        for required in ("connection", "registers"):
            if required not in profile:
                raise DriverConfigError(
                    f"Device profile missing required key '{required}': {path}"
                )
        return profile

    def get_register(self, tag_name: str) -> dict[str, Any]:
        """Return the register metadata for *tag_name* or raise."""
        try:
            return self.registers[tag_name]
        except KeyError:
            raise TagNotFoundError(
                f"Tag '{tag_name}' is not defined in the device profile. "
                f"Available tags: {list(self.registers.keys())}"
            ) from None

    def decode_value(self, registers: list[int], reg_type: str, scale: float) -> float:
        """
        Decode raw Modbus register words into a scaled Python float.
        """
        # Convert register words → raw bytes (each register = 2 bytes, big-endian)
        raw_bytes = b"".join(r.to_bytes(2, byteorder="big") for r in registers)
        bo = self.byte_order  # '>' or '<'
        raw: int | float
        match reg_type.upper():
            case "INT32":
                (raw,) = struct.unpack(f"{bo}i", raw_bytes)
            case "UINT32":
                (raw,) = struct.unpack(f"{bo}I", raw_bytes)
            case "FLOAT32":
                (raw,) = struct.unpack(f"{bo}f", raw_bytes)
            case "UINT16":
                (raw,) = struct.unpack(f"{bo}H", raw_bytes)
            case "INT16":
                (raw,) = struct.unpack(f"{bo}h", raw_bytes)
            case _:
                raise DriverConfigError(f"Unsupported register type: '{reg_type}'")
        return float(raw) * scale

    def encode_value(self, value: float, reg_type: str, scale: float) -> list[int]:
        """
        Encode a scaled Python value back into Modbus register words.
        """
        raw = value / scale  # inverse scale
        bo = self.byte_order  # '>' or '<'
        packed: bytes
        match reg_type.upper():
            case "INT32":
                packed = struct.pack(f"{bo}i", int(raw))
            case "UINT32":
                packed = struct.pack(f"{bo}I", int(raw))
            case "FLOAT32":
                packed = struct.pack(f"{bo}f", float(raw))
            case "UINT16":
                packed = struct.pack(f"{bo}H", int(raw))
            case "INT16":
                packed = struct.pack(f"{bo}h", int(raw))
            case _:
                raise DriverConfigError(f"Unsupported register type: '{reg_type}'")
        # Convert packed bytes back to list of 16-bit register values
        return [
            int.from_bytes(packed[i : i + 2], byteorder="big")
            for i in range(0, len(packed), 2)
        ]
