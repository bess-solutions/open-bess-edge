"""
src/drivers/base.py
===================
BESSAI Edge Gateway — DataProvider Protocol.

Defines the common interface that ALL data providers must implement,
whether they read from real hardware (ModbusDriver) or from synthetic
simulation (SimulatorDriver).

This Protocol is the single factorization point that allows swapping
sim ↔ real without changing any business logic (Safety Guard, AI-IDS,
Dashboard API, Arbitrage Engine, MQTT Publisher, etc.).

Usage::

    from src.drivers.base import DataProvider

    # Both satisfy the protocol:
    driver: DataProvider = ModbusDriver(host="192.168.1.100", ...)
    driver: DataProvider = SimulatorDriver(profile="huawei_sun2000")

    # Business logic is identical for both:
    soc = await driver.read_tag("luna_soc")
    await driver.write_tag("luna_charge_target_soc", 80.0)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["DataProvider", "DataProviderError", "DriverMode"]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DataProviderError(RuntimeError):
    """Base exception for all DataProvider errors."""


# ---------------------------------------------------------------------------
# Enum-like constants for driver mode
# ---------------------------------------------------------------------------


class DriverMode:
    """String constants for BESSAI_MODE environment variable."""

    DEMO = "demo"
    PRODUCTION = "production"
    AUTO = "auto"  # default: use SimulatorDriver if INVERTER_IP not set


# ---------------------------------------------------------------------------
# DataProvider Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DataProvider(Protocol):
    """
    Structural protocol for BESSAI data providers.

    Any class that implements these async methods satisfies the protocol
    without explicit inheritance. Uses ``typing.Protocol`` with
    ``@runtime_checkable`` so ``isinstance(driver, DataProvider)`` works.

    Required methods
    ----------------
    connect()
        Establish connection to the data source (TCP, serial, in-memory).
        Should be idempotent — safe to call multiple times.

    disconnect()
        Close the connection cleanly. Safe to call even if not connected.

    read_tag(tag_name)
        Read a named register by its profile key (e.g. ``"luna_soc"``).
        Returns the decoded float value with scale applied.

    write_tag(tag_name, value)
        Write a named register with scale applied in reverse.

    is_connected
        Property — True if the provider has an active connection.

    source_description
        Property — human-readable string identifying the source,
        e.g. ``"ModbusTCP@192.168.1.100:502"`` or ``"Simulator[huawei]"``.
    """

    async def connect(self) -> None:
        """Establish connection to the data source."""
        ...

    async def disconnect(self) -> None:
        """Close the connection cleanly."""
        ...

    async def read_tag(self, tag_name: str) -> float:
        """
        Read a register by profile tag name.

        Parameters
        ----------
        tag_name:
            Key from the device profile registers dict, e.g. ``"luna_soc"``.

        Returns
        -------
        float
            Decoded value with scale applied (e.g. 72.3 for SOC%).

        Raises
        ------
        DataProviderError
            If the tag is unknown or the read fails after retries.
        """
        ...

    async def write_tag(self, tag_name: str, value: float) -> None:
        """
        Write a register by profile tag name.

        Parameters
        ----------
        tag_name:
            Key in the device profile registers dict (must have access ``RW``).
        value:
            Physical value (scale is applied internally before writing).

        Raises
        ------
        DataProviderError
            If the tag is unknown, read-only, or the write fails.
        """
        ...

    @property
    def is_connected(self) -> bool:
        """True if the provider currently has an active connection."""
        ...

    @property
    def source_description(self) -> str:
        """Human-readable identifier of the data source."""
        ...
