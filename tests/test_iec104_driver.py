# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_iec104_driver.py
============================
Unit tests for ``src.drivers.iec104_driver.IEC104Driver``
IEC 60870-5-104 SCADA Driver — NTSyCS Cap. 6.2 (GAP-004).
All tests run in stub mode — no native lib60870 required.
"""

from __future__ import annotations

import asyncio

import pytest
from src.drivers.iec104_driver import (
    IEC104ConnectionError,
    IEC104Driver,
    IEC104TagNotFoundError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def driver() -> IEC104Driver:
    return IEC104Driver(stub_mode=True)


@pytest.fixture()
def connected_driver() -> IEC104Driver:
    d = IEC104Driver(stub_mode=True)
    asyncio.run(d.connect())
    return d


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitialization:
    def test_initializes_without_lib60870(self, driver: IEC104Driver) -> None:
        assert driver is not None

    def test_not_connected_initially(self, driver: IEC104Driver) -> None:
        assert driver.is_connected is False

    def test_source_description_contains_stub(self) -> None:
        d = IEC104Driver(host="192.168.1.10", stub_mode=True)
        assert "stub" in d.source_description
        assert "192.168.1.10" in d.source_description

    def test_default_ioa_map_has_expected_tags(self, driver: IEC104Driver) -> None:
        tags = driver.registered_tags()
        for tag in ("soc", "p_kw", "grid_frequency", "p_setpoint", "watchdog_heartbeat"):
            assert tag in tags

    def test_custom_ioa_map_merged(self) -> None:
        d = IEC104Driver(ioa_map={"custom_tag": 9999}, stub_mode=True)
        tags = d.registered_tags()
        assert tags["custom_tag"] == 9999
        assert "soc" in tags


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestConnectionLifecycle:
    def test_connect_sets_connected(self, driver: IEC104Driver) -> None:
        asyncio.run(driver.connect())
        assert driver.is_connected is True

    def test_disconnect_clears_connected(self, connected_driver: IEC104Driver) -> None:
        asyncio.run(connected_driver.disconnect())
        assert connected_driver.is_connected is False

    def test_read_without_connect_raises(self, driver: IEC104Driver) -> None:
        with pytest.raises(IEC104ConnectionError):
            asyncio.run(driver.read_tag("soc"))

    def test_write_without_connect_raises(self, driver: IEC104Driver) -> None:
        with pytest.raises(IEC104ConnectionError):
            asyncio.run(driver.write_tag("p_setpoint", 500.0))


# ---------------------------------------------------------------------------
# Read / Write
# ---------------------------------------------------------------------------


class TestReadWrite:
    def test_read_unwritten_tag_returns_zero(self, connected_driver: IEC104Driver) -> None:
        value = asyncio.run(connected_driver.read_tag("soc"))
        assert value == pytest.approx(0.0)
        assert isinstance(value, float)

    def test_write_then_read_roundtrip(self, connected_driver: IEC104Driver) -> None:
        asyncio.run(connected_driver.write_tag("p_setpoint", 750.0))
        result = asyncio.run(connected_driver.read_tag("p_setpoint"))
        assert result == pytest.approx(750.0)

    def test_write_negative_value(self, connected_driver: IEC104Driver) -> None:
        asyncio.run(connected_driver.write_tag("p_setpoint", -200.0))
        result = asyncio.run(connected_driver.read_tag("p_setpoint"))
        assert result == pytest.approx(-200.0)

    def test_watchdog_heartbeat_writable(self, connected_driver: IEC104Driver) -> None:
        asyncio.run(connected_driver.write_tag("watchdog_heartbeat", 42.0))
        result = asyncio.run(connected_driver.read_tag("watchdog_heartbeat"))
        assert result == pytest.approx(42.0)

    def test_read_unknown_tag_raises(self, connected_driver: IEC104Driver) -> None:
        with pytest.raises(IEC104TagNotFoundError):
            asyncio.run(connected_driver.read_tag("nonexistent_tag"))

    def test_write_unknown_tag_raises(self, connected_driver: IEC104Driver) -> None:
        with pytest.raises(IEC104TagNotFoundError):
            asyncio.run(connected_driver.write_tag("ghost_register", 1.0))


# ---------------------------------------------------------------------------
# General Interrogation
# ---------------------------------------------------------------------------


class TestGeneralInterrogation:
    def test_gi_returns_dict(self, connected_driver: IEC104Driver) -> None:
        snapshot = asyncio.run(connected_driver.general_interrogation())
        assert isinstance(snapshot, dict)
        assert "soc" in snapshot
        assert "p_kw" in snapshot

    def test_gi_reflects_written_values(self, connected_driver: IEC104Driver) -> None:
        asyncio.run(connected_driver.write_tag("soc", 88.5))
        snapshot = asyncio.run(connected_driver.general_interrogation())
        assert snapshot["soc"] == pytest.approx(88.5)
