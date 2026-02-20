"""
src/drivers/modbus_driver.py
============================
Universal Modbus TCP driver for BESSAI Edge Gateway.

Implements a device-agnostic driver that loads its register map
from a JSON profile (e.g. ``registry/huawei_sun2000.json``) and
exposes typed async read/write operations.

Design principles
-----------------
* **Async-first**: every I/O operation is a coroutine.
* **Profile-driven**: all register metadata comes from JSON — the
  driver itself contains zero hardware-specific knowledge.
* **Resilient**: connection retries with exponential back-off;
  per-operation exception handling with structured logging.
* **Type-safe**: full ``mypy --strict`` compliance.
"""

from __future__ import annotations

import asyncio
import json
import struct
from pathlib import Path
from typing import Any, Final

import structlog
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MAX_CONNECT_RETRIES: Final[int] = 3
_RETRY_BACKOFF_BASE_S: Final[float] = 2.0  # seconds; doubles each retry

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
log: structlog.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
RegisterProfile = dict[str, Any]
DeviceProfile = dict[str, Any]


class DriverConfigError(Exception):
    """Raised when the device profile JSON is malformed or missing."""


class TagNotFoundError(KeyError):
    """Raised when a requested tag name is not defined in the profile."""


class ModbusReadError(IOError):
    """Raised when a Modbus read operation fails after retries."""


class ModbusWriteError(IOError):
    """Raised when a Modbus write operation fails."""


# ---------------------------------------------------------------------------
# Helper: map JSON endianness strings → struct format prefix
# ---------------------------------------------------------------------------
_ENDIAN_MAP: dict[str, str] = {
    "BIG": ">",
    "LITTLE": "<",
}


def _resolve_endian(value: str, field: str) -> str:
    try:
        return _ENDIAN_MAP[value.upper()]
    except KeyError:
        raise DriverConfigError(f"Invalid {field} '{value}'. Must be 'BIG' or 'LITTLE'.") from None


# ---------------------------------------------------------------------------
# Main driver class
# ---------------------------------------------------------------------------


class UniversalDriver:
    """
    Device-agnostic Modbus TCP driver configured via a JSON profile.

    Parameters
    ----------
    host:
        IPv4/IPv6 address or hostname of the Modbus endpoint.
    port:
        TCP port (default 502).
    profile_path:
        Path to the JSON device profile.

    Examples
    --------
    ::

        driver = UniversalDriver(
            host="192.168.1.100",
            profile_path=Path("registry/huawei_sun2000.json"),
        )
        await driver.connect()
        soc = await driver.read_tag("soc")
        await driver.write_tag("watchdog_heartbeat", 42)
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        profile_path: Path | str = Path("registry/huawei_sun2000.json"),
    ) -> None:
        self._host = host
        self._port = port
        self._profile: DeviceProfile = self._load_profile(Path(profile_path))
        self._registers: dict[str, RegisterProfile] = self._profile["registers"]

        # Connection byte / word order from profile (struct format prefix: '>' or '<')
        conn = self._profile.get("connection", {})
        self._byte_order: str = _resolve_endian(conn.get("byte_order", "BIG"), "byte_order")
        self._word_order: str = _resolve_endian(conn.get("word_order", "BIG"), "word_order")

        self._client = AsyncModbusTcpClient(host=self._host, port=self._port)
        log.info(
            "driver.initialized",
            host=host,
            port=port,
            profile=str(profile_path),
            registers=list(self._registers.keys()),
        )

    # ------------------------------------------------------------------
    # Profile loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_profile(path: Path) -> DeviceProfile:
        """Load and validate the JSON device profile."""
        if not path.exists():
            raise DriverConfigError(f"Device profile not found: {path}")
        try:
            with path.open("r", encoding="utf-8") as fh:
                profile: DeviceProfile = json.load(fh)
        except json.JSONDecodeError as exc:
            raise DriverConfigError(f"Device profile JSON is invalid: {path}") from exc

        for required in ("connection", "registers"):
            if required not in profile:
                raise DriverConfigError(
                    f"Device profile missing required key '{required}': {path}"
                )
        return profile

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """
        Establish the Modbus TCP connection with automatic retries.

        Attempts up to ``_MAX_CONNECT_RETRIES`` times with exponential
        back-off.  Raises ``ConnectionException`` if all attempts fail.
        """
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_CONNECT_RETRIES + 1):
            try:
                await self._client.connect()
                if self._client.connected:
                    log.info(
                        "driver.connected",
                        host=self._host,
                        port=self._port,
                        attempt=attempt,
                    )
                    return
            except Exception as exc:  # pymodbus may raise various base exceptions
                last_exc = exc
                wait = _RETRY_BACKOFF_BASE_S ** (attempt - 1)
                log.warning(
                    "driver.connect_failed",
                    host=self._host,
                    port=self._port,
                    attempt=attempt,
                    max_attempts=_MAX_CONNECT_RETRIES,
                    retry_in_s=wait,
                    error=str(exc),
                )
                if attempt < _MAX_CONNECT_RETRIES:
                    await asyncio.sleep(wait)

        raise ConnectionException(
            f"Could not connect to {self._host}:{self._port} after {_MAX_CONNECT_RETRIES} attempts"
        ) from last_exc

    async def disconnect(self) -> None:
        """Close the Modbus TCP connection gracefully."""
        self._client.close()
        log.info("driver.disconnected", host=self._host, port=self._port)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_register(self, tag_name: str) -> RegisterProfile:
        """Return the register metadata for *tag_name* or raise."""
        try:
            return self._registers[tag_name]
        except KeyError:
            raise TagNotFoundError(
                f"Tag '{tag_name}' is not defined in the device profile. "
                f"Available tags: {list(self._registers.keys())}"
            ) from None

    def _decode_value(self, registers: list[int], reg_type: str, scale: float) -> float:
        """
        Decode raw Modbus register words into a scaled Python float.

        Uses ``struct`` (stdlib) to unpack bytes, replacing the removed
        ``BinaryPayloadDecoder`` API from pymodbus < 3.7.
        """
        # Convert register words → raw bytes (each register = 2 bytes, big-endian)
        raw_bytes = b"".join(r.to_bytes(2, byteorder="big") for r in registers)
        bo = self._byte_order  # '>' or '<'
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

    def _encode_value(self, value: float, reg_type: str, scale: float) -> list[int]:
        """
        Encode a scaled Python value back into Modbus register words.

        Uses ``struct`` (stdlib), replacing the removed
        ``BinaryPayloadBuilder`` API from pymodbus < 3.7.
        """
        raw = value / scale  # inverse scale
        bo = self._byte_order  # '>' or '<'
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
            int.from_bytes(packed[i : i + 2], byteorder="big") for i in range(0, len(packed), 2)
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def read_tag(self, tag_name: str) -> float:
        """
        Read a named tag from the device.

        Parameters
        ----------
        tag_name:
            Key defined in the profile's ``registers`` section.

        Returns
        -------
        float
            The decoded and scaled engineering-unit value.

        Raises
        ------
        TagNotFoundError
            If *tag_name* is not in the profile.
        ModbusReadError
            If the Modbus transaction fails.
        """
        reg = self._get_register(tag_name)
        address: int = reg["address"]
        count: int = reg.get("count", 1)
        reg_type: str = reg["type"]
        scale: float = float(reg.get("scale", 1))

        log.debug("driver.read_tag.start", tag=tag_name, address=address, count=count)
        try:
            result = await self._client.read_holding_registers(address=address, count=count)
        except (ConnectionException, ModbusIOException) as exc:
            raise ModbusReadError(
                f"Modbus read failed for tag '{tag_name}' at address {address}: {exc}"
            ) from exc

        if result.isError():
            raise ModbusReadError(
                f"Modbus exception response for tag '{tag_name}' at address {address}: {result}"
            )

        value = self._decode_value(result.registers, reg_type, scale)
        log.debug("driver.read_tag.done", tag=tag_name, value=value)
        return value

    async def write_tag(self, tag_name: str, value: float) -> None:
        """
        Write a value to a named tag on the device.

        Parameters
        ----------
        tag_name:
            Key defined in the profile's ``registers`` section
            (must have ``"access": "RW"``).
        value:
            Engineering-unit value to write.  The inverse scale from the
            profile is applied before encoding.

        Raises
        ------
        TagNotFoundError
            If *tag_name* is not in the profile.
        PermissionError
            If the tag is read-only (``"access": "RO"``).
        ModbusWriteError
            If the Modbus write transaction fails.
        """
        reg = self._get_register(tag_name)

        if reg.get("access", "RO").upper() == "RO":
            raise PermissionError(f"Tag '{tag_name}' is read-only (access=RO). Cannot write.")

        address: int = reg["address"]
        reg_type: str = reg["type"]
        scale: float = float(reg.get("scale", 1))

        payload = self._encode_value(value, reg_type, scale)
        log.debug(
            "driver.write_tag.start",
            tag=tag_name,
            address=address,
            value=value,
            encoded=payload,
        )
        try:
            result = await self._client.write_registers(address=address, values=payload)
        except (ConnectionException, ModbusIOException) as exc:
            raise ModbusWriteError(
                f"Modbus write failed for tag '{tag_name}' at address {address}: {exc}"
            ) from exc

        if result.isError():
            raise ModbusWriteError(
                f"Modbus exception response writing tag '{tag_name}' "
                f"at address {address}: {result}"
            )

        log.debug("driver.write_tag.done", tag=tag_name, value=value)
